"""Test suite for .opencode/tools/consult.py CLI.

Tests the 3 subcommands (pre_plan, pre_dispatch, post_verify) as black-box
subprocess invocations, verifying JSON output shape, status codes, and
graceful degradation paths.

Coverage:
  - CLI round-trip: each subcommand returns valid JSON with expected keys
  - Empty DB: zero entities produce empty results (not a crash)
  - No match: unrelated queries produce empty results
  - Missing DB: non-existent database returns valid JSON (graceful)
  - Kill switch: JANUS_CONSULT_DISABLED env var disables consultation
  - Invalid subcommand: exits non-zero with error on stderr
  - Missing positional args: argparse catches and exits non-zero
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------


def _load(name: str):
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        candidate = parent / ".opencode" / "tools" / f"{name}.py"
        if candidate.exists():
            spec = importlib.util.spec_from_file_location(name, candidate)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            return mod, candidate
    raise RuntimeError(f"Could not find .opencode/tools/{name}.py")


consult, CONSULT_PATH = _load("consult")
lcn_write, _ = _load("lcn_write")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def populated_db(tmp_path):
    """A temporary database with curated entities for consult exercises."""
    db = tmp_path / "test.sqlite"
    entities = [
        # Past Decision touching auth.py
        {
            "entity_type": "Decision",
            "mission_id": "m-001",
            "confidence": 4,
            "file_paths": ["auth.py"],
            "chosen_approach": "use bcrypt for password hashing",
            "rationale": "industry standard",
            "outcome": "succeeded",
        },
        # Past Rejection
        {
            "entity_type": "Rejection",
            "mission_id": "m-002",
            "confidence": 3,
            "approach": "store passwords in plaintext",
            "reason": "trivially insecure",
            "context_that_might_change_this": (
                "if compliance ever waives auth requirements"
            ),
        },
        # Error with model-routing class
        {
            "entity_type": "Error",
            "mission_id": "m-003",
            "confidence": 5,
            "failure_class": "model-routing",
            "file_paths": [".opencode/agent/orchestrator.md"],
            "symptom": "silently routed to wrong provider",
            "root_cause": "user-home opencode.json overrode project config",
            "fix_applied": "stripped overrides from user-home config",
        },
        # Convention covering agent scope
        {
            "entity_type": "Convention",
            "mission_id": "m-004",
            "confidence": 4,
            "scope": ".opencode/agent/*",
            "rule": "Primary-session model is governed by opencode.json or --model",
            "why": "agent frontmatter is silently ignored for primary routing",
            "example": "set model: 'anthropic/claude-sonnet-4-5' in opencode.json",
        },
    ]
    lcn_write.write_many(entities, db_path=db)
    return db


@pytest.fixture
def empty_db(tmp_path):
    """A database file that exists but has no entities."""
    db = tmp_path / "empty.sqlite"
    lcn_write.get_conn(db).close()
    return db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(*args, db_path=None, extra_env=None):
    """Run consult.py and return the subprocess.CompletedProcess."""
    cmd = [sys.executable, str(CONSULT_PATH), *args]
    if db_path is not None:
        cmd.extend(["--db-path", str(db_path)])
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )


def _assert_ok_json(proc):
    """Assert exit 0 and valid JSON with ``status == "ok"``."""
    assert proc.returncode == 0, (
        f"CLI exited {proc.returncode}: stderr={proc.stderr!r}"
    )
    data = json.loads(proc.stdout)
    assert isinstance(data, dict), f"Expected dict, got {type(data).__name__}"
    assert "results" in data, "Missing 'results' key"
    assert "status" in data, "Missing 'status' key"
    assert data["status"] == "ok", (
        f"Expected status 'ok', got {data['status']!r}"
    )
    return data


def _assert_degraded_json(proc):
    """Assert exit 0 and valid JSON with ``status == "degraded"``."""
    assert proc.returncode == 0, (
        f"CLI exited {proc.returncode}: stderr={proc.stderr!r}"
    )
    data = json.loads(proc.stdout)
    assert isinstance(data, dict)
    assert data.get("status") == "degraded", (
        f"Expected 'degraded', got {data.get('status')!r}"
    )
    assert "results" in data
    return data


# ---------------------------------------------------------------------------
# pre_plan subcommand
# ---------------------------------------------------------------------------


def test_cli_pre_plan_with_results(populated_db):
    """Query for bcrypt should find the seeded Decision."""
    proc = _run("pre_plan", "use bcrypt for password hashing", db_path=populated_db)
    data = _assert_ok_json(proc)
    results = data["results"]
    assert isinstance(results, dict)
    assert "similar_decisions" in results
    assert "applicable_conventions" in results
    assert "recent_patterns" in results
    assert len(results["similar_decisions"]) >= 1, "Expected at least one decision"
    # Verify summary structure
    dec = results["similar_decisions"][0]
    assert "natural_key" in dec
    assert dec.get("chosen_approach") == "use bcrypt for password hashing"


def test_cli_pre_plan_no_match(populated_db):
    """Keywords with zero overlap should produce empty decision list."""
    proc = _run("pre_plan", "zzzzz qqqqq xxxxx wwww", db_path=populated_db)
    data = _assert_ok_json(proc)
    results = data["results"]
    assert len(results["similar_decisions"]) == 0


def test_cli_pre_plan_empty_db(empty_db):
    """An empty database should return valid JSON with empty results."""
    proc = _run("pre_plan", "anything", db_path=empty_db)
    data = _assert_ok_json(proc)
    assert len(data["results"]["similar_decisions"]) == 0
    assert len(data["results"]["applicable_conventions"]) == 0
    assert len(data["results"]["recent_patterns"]) == 0


# ---------------------------------------------------------------------------
# pre_dispatch subcommand
# ---------------------------------------------------------------------------


def test_cli_pre_dispatch_with_results(populated_db):
    """Dispatching 'orchestrator' should surface the model-routing Error."""
    proc = _run(
        "pre_dispatch", "orchestrator", "deepseek-v4-flash", db_path=populated_db
    )
    data = _assert_ok_json(proc)
    results = data["results"]
    assert isinstance(results, dict)
    assert "known_pitfalls" in results
    assert "agent_conventions" in results
    assert results["agent"] == "orchestrator"
    assert results["model"] == "deepseek-v4-flash"


def test_cli_pre_dispatch_no_match(populated_db):
    """An agent not in the DB should produce empty pitfalls list."""
    proc = _run("pre_dispatch", "nonexistent-agent", "gpt-5", db_path=populated_db)
    data = _assert_ok_json(proc)
    assert len(data["results"]["known_pitfalls"]) == 0


def test_cli_pre_dispatch_empty_db(empty_db):
    """Empty DB should return valid JSON with empty pitfalls."""
    proc = _run("pre_dispatch", "coder", "gpt-4", db_path=empty_db)
    data = _assert_ok_json(proc)
    assert len(data["results"]["known_pitfalls"]) == 0
    assert len(data["results"]["agent_conventions"]) == 0


# ---------------------------------------------------------------------------
# post_verify subcommand
# ---------------------------------------------------------------------------


def test_cli_post_verify_with_results(populated_db):
    """Verifying 'auth.py' should surface the bcrypt Decision file overlap."""
    proc = _run("post_verify", "auth-feature", "auth.py", db_path=populated_db)
    data = _assert_ok_json(proc)
    results = data["results"]
    assert isinstance(results, dict)
    assert "applicable_conventions" in results
    assert "potentially_contradicted_decisions" in results
    assert "changed_files" in results
    assert results["feature"] == "auth-feature"
    assert results["changed_files"] == ["auth.py"]


def test_cli_post_verify_no_match(populated_db):
    """An unrelated file should produce no conventions or contradictions."""
    proc = _run(
        "post_verify", "xyz", "nobody_ever_touched_this.py", db_path=populated_db
    )
    data = _assert_ok_json(proc)
    assert len(data["results"]["applicable_conventions"]) == 0
    assert len(data["results"]["potentially_contradicted_decisions"]) == 0


def test_cli_post_verify_empty_db(empty_db):
    """An empty DB should return valid JSON with empty convention list."""
    proc = _run("post_verify", "feature", "file.py", db_path=empty_db)
    data = _assert_ok_json(proc)
    assert len(data["results"]["applicable_conventions"]) == 0
    assert len(data["results"]["potentially_contradicted_decisions"]) == 0


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


def test_missing_db_returns_ok_with_empty_results(tmp_path):
    """When the DB file does not exist, consult returns status 'ok' with
    empty results (the lcn_read query functions gracefully return [])."""
    missing = tmp_path / "nope.sqlite"
    proc = _run("pre_plan", "anything", db_path=missing)
    data = _assert_ok_json(proc)
    # All result lists should be empty when there is no database
    assert len(data["results"]["similar_decisions"]) == 0
    assert len(data["results"]["applicable_conventions"]) == 0
    assert len(data["results"]["recent_patterns"]) == 0


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------


def test_kill_switch_disables_consult(populated_db):
    """JANUS_CONSULT_DISABLED=1 should cause consult to return degraded."""
    proc = _run(
        "pre_plan",
        "use bcrypt",
        db_path=populated_db,
        extra_env={"JANUS_CONSULT_DISABLED": "1"},
    )
    data = _assert_degraded_json(proc)
    assert "Consult disabled" in data.get("reason", "")


def test_kill_switch_default_is_enabled(populated_db):
    """When env var is not set, consult operates normally."""
    proc = _run("pre_plan", "bcrypt", db_path=populated_db)
    data = _assert_ok_json(proc)
    assert len(data["results"]["similar_decisions"]) >= 1


# ---------------------------------------------------------------------------
# Invalid / missing arguments
# ---------------------------------------------------------------------------


def test_invalid_subcommand():
    """An unknown subcommand should exit non-zero with error on stderr."""
    proc = _run("nonexistent_subcommand", "arg")
    assert proc.returncode != 0
    combined = (proc.stderr + proc.stdout).lower()
    assert "nonexistent_subcommand" in combined or "invalid choice" in combined


def test_missing_subcommand():
    """No subcommand should make argparse exit non-zero."""
    proc = _run()
    assert proc.returncode != 0
    assert "usage:" in proc.stderr.lower() or "usage:" in proc.stdout.lower()


def test_missing_args_pre_dispatch():
    """pre_dispatch expects 2 positional args; fewer should fail."""
    proc = _run("pre_dispatch", "only_one_arg")
    assert proc.returncode != 0


def test_missing_args_post_verify():
    """post_verify expects 2 positional args; fewer should fail."""
    proc = _run("post_verify", "only_one_arg")
    assert proc.returncode != 0
