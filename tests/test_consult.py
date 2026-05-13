"""Test suite for .opencode/tools/consult.py.

Verifies the markdown sections produced by each phase match
CONSULT-PROTOCOL.md spec. We check structure (headings, footer, recall-miss
annotations, kill switch) rather than exact prose.

Coverage:
  - render_pre_plan: with prior art, with no prior art, mixed
  - render_pre_dispatch: with errors, with empty errors, with related Conventions
  - render_post_verify: with conventions, with none
  - JANUS_CONSULT_ENABLED kill switch (env var) for all 3 phases
  - Footer format invariant
  - CLI parses each phase + emits markdown to stdout
  - argparse rejects bad --phase values
"""
from __future__ import annotations

import importlib.util
import os
import re
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
    """A tmp DB with curated entities for consult exercises."""
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
        # Past Rejection on the same file
        {
            "entity_type": "Rejection",
            "mission_id": "m-002",
            "confidence": 3,
            "approach": "store passwords in plaintext",
            "reason": "trivially insecure",
            "context_that_might_change_this": "if compliance ever waives auth requirements",
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
        # Convention covering agent scope (relates to the model-routing Error)
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
    """A DB that exists but has no entities."""
    db = tmp_path / "empty.sqlite"
    # Use lcn_write to create the schema without inserting anything
    lcn_write.get_conn(db).close()
    return db


# ---------------------------------------------------------------------------
# Footer invariant
# ---------------------------------------------------------------------------


FOOTER_RE = re.compile(
    r"-- injected by CONSULT-PROTOCOL v1, queries: (\d+), results: (\d+)"
)


def _footer_counts(text: str) -> tuple[int, int]:
    m = FOOTER_RE.search(text)
    assert m is not None, f"No CONSULT-PROTOCOL footer found in: {text!r}"
    return int(m.group(1)), int(m.group(2))


# ---------------------------------------------------------------------------
# pre-plan
# ---------------------------------------------------------------------------


def test_pre_plan_with_known_decision(populated_db):
    out = consult.render_pre_plan(
        request_text="use bcrypt for password hashing on the auth path",
        predicted_files=["auth.py"],
        scope_hash="auth.py",
        db_path=populated_db,
    )
    assert "## Prior art" in out
    assert "## Decisions on touched files" in out
    # Should mention the past Decision
    assert "bcrypt" in out
    # v0 limitation: Rejection NOT surfaced via by-file (no file_paths in
    # Rejection schema). Documented in consult.py docstring.
    qn, rn = _footer_counts(out)
    assert qn >= 2  # one mission-similarity + one by-file
    assert rn >= 1  # at least the Decision matched


def test_pre_plan_no_prior_art(populated_db):
    out = consult.render_pre_plan(
        request_text="zzzzz qqqqq xxxxx wwww vvvv",  # no overlap with any seeded title
        predicted_files=["a_new_file_no_one_has_seen.py"],
        scope_hash="x_no_overlap",
        db_path=populated_db,
    )
    # Even no-results should produce structured sections
    assert "## Prior art" in out
    assert "## Decisions on touched files" in out
    # Recall-miss annotation per spec — fires when both queries empty
    assert "No prior art" in out or "No similar prior missions" in out
    # Footer present
    qn, _ = _footer_counts(out)
    assert qn >= 2


def test_pre_plan_low_similarity_filtered(populated_db):
    """Below the SIMILARITY_FLOOR (0.1), missions don't appear in injection."""
    out = consult.render_pre_plan(
        request_text="zzzzz qqqqq xxxxx",  # near-zero trigram overlap with bcrypt
        predicted_files=[],
        scope_hash="zzz",
        db_path=populated_db,
    )
    # No false-positive mention of the bcrypt Decision
    assert "bcrypt" not in out
    # Recall-miss annotation should fire
    assert "No similar prior missions" in out


def test_pre_plan_predicted_files_empty(populated_db):
    """When no predicted files, we still fire the similarity query alone."""
    out = consult.render_pre_plan(
        request_text="bcrypt hashing",
        predicted_files=[],
        scope_hash="",
        db_path=populated_db,
    )
    assert "## Prior art" in out
    qn, _ = _footer_counts(out)
    assert qn == 1  # only the similarity query


# ---------------------------------------------------------------------------
# pre-dispatch
# ---------------------------------------------------------------------------


def test_pre_dispatch_with_known_class(populated_db):
    out = consult.render_pre_dispatch(
        classes=["model-routing"], db_path=populated_db
    )
    assert "## Known pitfalls" in out
    # Should mention root cause from the error
    assert "user-home" in out
    # Should mention the prevention rule
    assert "prevented by" in out or "agent frontmatter" in out
    qn, rn = _footer_counts(out)
    assert qn == 1
    assert rn >= 1


def test_pre_dispatch_unknown_class(populated_db):
    out = consult.render_pre_dispatch(
        classes=["budget-overrun"],  # not present in fixture
        db_path=populated_db,
    )
    assert "## Known pitfalls" in out
    assert "no known pitfalls" in out.lower()
    qn, rn = _footer_counts(out)
    assert qn == 1
    assert rn == 0


def test_pre_dispatch_caps_at_5_classes(populated_db):
    """Spec: ≤5 classes processed even if more provided."""
    out = consult.render_pre_dispatch(
        classes=[
            "model-routing",
            "edit-shape-error",
            "invented-tool",
            "convention-violation",
            "budget-overrun",
            "consult-skipped",  # 6th — should not fire a 6th query
            "ci-flake-vs-real",  # 7th
        ],
        db_path=populated_db,
    )
    qn, _ = _footer_counts(out)
    assert qn == 5  # not 7


def test_pre_dispatch_empty_classes(populated_db):
    out = consult.render_pre_dispatch(classes=[], db_path=populated_db)
    assert "## Known pitfalls" in out
    qn, _ = _footer_counts(out)
    assert qn == 0


# ---------------------------------------------------------------------------
# post-verify
# ---------------------------------------------------------------------------


def test_post_verify_with_applicable_convention(populated_db):
    out = consult.render_post_verify(
        touched_files=[".opencode/agent/orchestrator.md"],
        db_path=populated_db,
    )
    assert "## Convention check" in out
    # The agent-scope Convention should be cited
    assert "Primary-session model" in out
    assert "scope:" in out
    assert "why:" in out
    qn, rn = _footer_counts(out)
    assert qn == 1
    assert rn >= 1


def test_post_verify_no_conventions(populated_db):
    out = consult.render_post_verify(
        touched_files=["unrelated_file.txt"], db_path=populated_db
    )
    assert "## Convention check" in out
    # Recall miss annotation
    assert "No conventions" in out or "no conventions" in out.lower()
    qn, rn = _footer_counts(out)
    assert qn == 1
    assert rn == 0


def test_post_verify_dedupes_conventions(populated_db):
    """If a Convention matches multiple touched files, list it once."""
    out = consult.render_post_verify(
        touched_files=[
            ".opencode/agent/orchestrator.md",
            ".opencode/agent/coder.md",
            ".opencode/agent/reviewer.md",
        ],
        db_path=populated_db,
    )
    # 3 queries, but the same Convention matches all 3 — should only appear once
    occurrences = out.count("Primary-session model")
    assert occurrences == 1, f"Convention duplicated: {occurrences} occurrences"
    qn, _ = _footer_counts(out)
    assert qn == 3


# ---------------------------------------------------------------------------
# JANUS_CONSULT_ENABLED kill switch
# ---------------------------------------------------------------------------


def test_kill_switch_pre_plan(populated_db, monkeypatch):
    monkeypatch.setenv("JANUS_CONSULT_ENABLED", "0")
    out = consult.render_pre_plan(
        request_text="x", predicted_files=["a.py"], scope_hash="", db_path=populated_db
    )
    assert "Consult disabled" in out
    assert "DISABLED" in out


def test_kill_switch_pre_dispatch(populated_db, monkeypatch):
    monkeypatch.setenv("JANUS_CONSULT_ENABLED", "0")
    out = consult.render_pre_dispatch(classes=["model-routing"], db_path=populated_db)
    assert "Consult disabled" in out


def test_kill_switch_post_verify(populated_db, monkeypatch):
    monkeypatch.setenv("JANUS_CONSULT_ENABLED", "0")
    out = consult.render_post_verify(touched_files=["a.py"], db_path=populated_db)
    assert "Consult disabled" in out


def test_kill_switch_default_is_enabled(populated_db, monkeypatch):
    """When env var is unset, consult is enabled."""
    monkeypatch.delenv("JANUS_CONSULT_ENABLED", raising=False)
    out = consult.render_pre_plan(
        request_text="bcrypt",
        predicted_files=["auth.py"],
        scope_hash="auth.py",
        db_path=populated_db,
    )
    assert "Consult disabled" not in out


# ---------------------------------------------------------------------------
# Missing DB gracefully degrades (footer still emitted)
# ---------------------------------------------------------------------------


def test_missing_db_does_not_crash(tmp_path):
    """Per CONSULT-PROTOCOL §"Recall miss semantics", an empty/missing LCN
    is a signal not silence — but it must not halt the pipeline."""
    missing = tmp_path / "nope.sqlite"
    out = consult.render_pre_plan(
        request_text="x", predicted_files=["a.py"], scope_hash="", db_path=missing
    )
    # No crash; recall-miss treatment
    assert "## Prior art" in out
    qn, rn = _footer_counts(out)
    assert rn == 0  # no results possible


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_pre_plan(populated_db):
    proc = subprocess.run(
        [
            sys.executable,
            str(CONSULT_PATH),
            "--phase",
            "pre-plan",
            "--request",
            "use bcrypt for password hashing",
            "--predicted-files",
            "auth.py",
            "--db-path",
            str(populated_db),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, f"CLI failed: stderr={proc.stderr!r}"
    assert "## Prior art" in proc.stdout
    assert "bcrypt" in proc.stdout


def test_cli_pre_dispatch(populated_db):
    proc = subprocess.run(
        [
            sys.executable,
            str(CONSULT_PATH),
            "--phase",
            "pre-dispatch",
            "--classes",
            "model-routing",
            "--db-path",
            str(populated_db),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "## Known pitfalls" in proc.stdout


def test_cli_post_verify(populated_db):
    proc = subprocess.run(
        [
            sys.executable,
            str(CONSULT_PATH),
            "--phase",
            "post-verify",
            "--touched-files",
            ".opencode/agent/orchestrator.md",
            "--db-path",
            str(populated_db),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    assert "## Convention check" in proc.stdout


def test_cli_invalid_phase_rejected():
    proc = subprocess.run(
        [
            sys.executable,
            str(CONSULT_PATH),
            "--phase",
            "what",
            "--db-path",
            "/tmp/nope.sqlite",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode != 0
    # argparse error goes to stderr
    assert "what" in (proc.stderr + proc.stdout)


def test_cli_kill_switch_via_env(populated_db, monkeypatch):
    env = os.environ.copy()
    env["JANUS_CONSULT_ENABLED"] = "0"
    proc = subprocess.run(
        [
            sys.executable,
            str(CONSULT_PATH),
            "--phase",
            "pre-plan",
            "--request",
            "x",
            "--db-path",
            str(populated_db),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    assert proc.returncode == 0
    assert "Consult disabled" in proc.stdout
