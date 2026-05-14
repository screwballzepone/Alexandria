"""Tests for .opencode/tools/lcn_read.py — 5 real query functions.

Strategy: build a fresh tmp DB with known data via lcn_write.write_many,
then exercise each query function. Verifies contracts (return shapes, empty
results on no-match/missing-DB, ordering) against the actual deployed API
rather than planned-but-never-implemented functions.

Coverage:
  - query_similar_decisions: workspace matching, keyword scoring, limit, missing-DB
  - query_related_errors: by error_type, by agent_or_tool, both filters, empty
  - query_applicable_conventions: exact scope, dir prefix, global "*", no match
  - query_entity_by_key: found, not found, missing DB
  - query_recent_by_type: each entity type, limit, case-insensitive, empty
  - consult.py CLI: valid JSON output for each subcommand
  - Empty/missing DB: all functions return [] or None gracefully
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
# Module loaders
# ---------------------------------------------------------------------------


def _load(name: str) -> tuple:
    """Import a module from .opencode/tools/{name}.py, searching upward."""
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


lcn_read, READ_PATH = _load("lcn_read")
lcn_write, WRITE_PATH = _load("lcn_write")


def _find_tool_path(name: str) -> Path:
    """Find the absolute path to a tool script without importing it."""
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        candidate = parent / ".opencode" / "tools" / f"{name}.py"
        if candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find .opencode/tools/{name}.py")


CONSULT_PATH = _find_tool_path("consult")
TOOLS_DIR = CONSULT_PATH.parent


# ---------------------------------------------------------------------------
# Test entities — must pass lcn_write._check_entity validation
# ---------------------------------------------------------------------------

_ENTITIES: list[dict] = [
    # Decision A — workspace_path set, files include "auth.py"
    {
        "entity_type": "Decision",
        "mission_id": "m-001",
        "confidence": 4,
        "file_paths": ["auth.py", "session.py"],
        "chosen_approach": "use bcrypt for password hashing",
        "rationale": "industry standard, no rolling our own crypto",
        "outcome": "succeeded",
        "workspace_path": "/project/auth",
    },
    # Decision B — different workspace_path
    {
        "entity_type": "Decision",
        "mission_id": "m-002",
        "confidence": 3,
        "file_paths": ["payments.py"],
        "chosen_approach": "use stripe for payments",
        "rationale": "PCI compliance handed off",
        "outcome": "failed",
        "workspace_path": "/project/payments",
    },
    # Decision C — no workspace_path (legacy entity, pre-dates field)
    {
        "entity_type": "Decision",
        "mission_id": "m-003",
        "confidence": 2,
        "file_paths": ["legacy.py"],
        "chosen_approach": "use legacy auth system",
        "rationale": "migration not yet scheduled",
        "outcome": "pending",
    },
    # Error — model-routing class
    {
        "entity_type": "Error",
        "mission_id": "m-004",
        "confidence": 5,
        "failure_class": "model-routing",
        "file_paths": [".opencode/agent/orchestrator.md"],
        "symptom": "orchestrator silently routed to Gemini despite Cerebras config",
        "root_cause": "user-home opencode.json overrode project config",
        "fix_applied": "stripped model + small_model fields from user-home config",
    },
    # Error — invented-tool class (empty file_paths)
    {
        "entity_type": "Error",
        "mission_id": "m-005",
        "confidence": 4,
        "failure_class": "invented-tool",
        "file_paths": [],
        "symptom": "model called isoformat() as a tool name",
        "root_cause": "weak model hallucinated a tool that did not exist",
        "fix_applied": "added explicit tool list to system prompt",
    },
    # Convention — directory-scoped
    {
        "entity_type": "Convention",
        "mission_id": "m-006",
        "confidence": 4,
        "scope": ".opencode/agent",
        "rule": "Primary-session model is governed by opencode.json or --model.",
        "why": "Finding O: agent frontmatter ignored for primary routing.",
        "example": "set model: 'anthropic/claude-sonnet-4-5' in opencode.json",
    },
    # Convention — subdirectory scope
    {
        "entity_type": "Convention",
        "mission_id": "m-007",
        "confidence": 3,
        "scope": "tests",
        "rule": "Every new module must ship with tests/test_<module>.py",
        "why": "untested code rots fast in autonomous pipelines.",
        "example": "tests/test_lcn_write.py",
    },
    # Convention — global scope
    {
        "entity_type": "Convention",
        "mission_id": "m-008",
        "confidence": 5,
        "scope": "*",
        "rule": "Always use type hints in new code.",
        "why": "type hints prevent a class of runtime errors.",
        "example": "def greet(name: str) -> str:",
    },
    # Pattern
    {
        "entity_type": "Pattern",
        "mission_id": "m-009",
        "confidence": 4,
        "shape_description": "Use --model CLI flag for primary routing",
        "when_to_use": "When agent frontmatter model differs from desired",
        "when_not_to_use": "Sub-agent dispatch \u2014 frontmatter is honored there",
        "scope": ".opencode/agent/*",
    },
    # Rejection
    {
        "entity_type": "Rejection",
        "mission_id": "m-010",
        "confidence": 3,
        "approach": "Use JWT for API auth",
        "reason": "Overkill for internal-only service with no user base",
        "context_that_might_change_this": (
            "If the service is exposed to the public internet "
            "and needs stateless authentication"
        ),
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def populated_db(tmp_path):
    """A tmp DB seeded with entities of all 5 types."""
    db = tmp_path / "test.sqlite"
    lcn_write.write_many(_ENTITIES, db_path=db)
    return db


# ---------------------------------------------------------------------------
# 1. query_similar_decisions
# ---------------------------------------------------------------------------


class TestQuerySimilarDecisions:
    """Test query_similar_decisions(workspace_path, context_keywords, limit, db_path)."""

    def test_matching_workspace_and_keywords(self, populated_db):
        """Exact workspace_path match + keyword match returns the right decisions."""
        out = lcn_read.query_similar_decisions(
            workspace_path="/project/auth",
            context_keywords="bcrypt",
            db_path=populated_db,
        )
        assert len(out) >= 1
        data = out[0].get("data", {})
        assert data.get("chosen_approach") == "use bcrypt for password hashing"

    def test_different_workspace_excluded(self, populated_db):
        """Decision with non-matching workspace_path should not appear."""
        out = lcn_read.query_similar_decisions(
            workspace_path="/project/auth",
            context_keywords="",
            db_path=populated_db,
        )
        for ent in out:
            data = ent.get("data", {})
            assert data.get("workspace_path", "") != "/project/payments"

    def test_entity_without_workspace_path_included(self, populated_db):
        """Legacy entities without workspace_path should pass through filters."""
        out = lcn_read.query_similar_decisions(
            workspace_path="/project/auth",
            context_keywords="legacy",
            db_path=populated_db,
        )
        matches = [
            ent
            for ent in out
            if ent.get("data", {}).get("chosen_approach") == "use legacy auth system"
        ]
        assert len(matches) == 1

    def test_no_keyword_match_returns_empty(self, populated_db):
        """Keywords absent from all matching entities produce empty results."""
        out = lcn_read.query_similar_decisions(
            workspace_path="/project/auth",
            context_keywords="zzzzzzzzzzz nokeyword",
            db_path=populated_db,
        )
        assert out == []

    def test_limit_respected(self, populated_db):
        """limit parameter caps the number of results."""
        out = lcn_read.query_similar_decisions(
            workspace_path="/project/auth",
            context_keywords="",
            limit=1,
            db_path=populated_db,
        )
        assert len(out) <= 1

    def test_missing_db_returns_empty(self, tmp_path):
        """Graceful degradation when DB file does not exist."""
        out = lcn_read.query_similar_decisions(
            workspace_path="/project/auth",
            context_keywords="bcrypt",
            db_path=tmp_path / "nonexistent.sqlite",
        )
        assert out == []


# ---------------------------------------------------------------------------
# 2. query_related_errors
# ---------------------------------------------------------------------------


class TestQueryRelatedErrors:
    """Test query_related_errors(agent_or_tool, error_type, limit, db_path)."""

    def test_by_error_type(self, populated_db):
        """Filtering by error_type returns matching errors."""
        out = lcn_read.query_related_errors(
            error_type="model-routing",
            db_path=populated_db,
        )
        assert len(out) >= 1
        data = out[0].get("data", {})
        assert data.get("failure_class") == "model-routing"

    def test_by_agent_or_tool_substring(self, populated_db):
        """Substring search in symptom/root_cause/fix_applied."""
        out = lcn_read.query_related_errors(
            agent_or_tool="Gemini",
            db_path=populated_db,
        )
        assert len(out) >= 1
        data = out[0].get("data", {})
        assert "Gemini" in data.get("symptom", "")

    def test_both_filters_intersect(self, populated_db):
        """Both filters applied together narrow results."""
        out = lcn_read.query_related_errors(
            agent_or_tool="Gemini",
            error_type="model-routing",
            db_path=populated_db,
        )
        assert len(out) >= 1
        for ent in out:
            d = ent.get("data", {})
            assert d.get("failure_class") == "model-routing"
            texts = " ".join([d.get(f, "") for f in ("symptom", "root_cause", "fix_applied")])
            assert "Gemini" in texts

    def test_mismatched_type_returns_empty(self, populated_db):
        """error_type with no matches returns empty list."""
        out = lcn_read.query_related_errors(
            error_type="ci-flake-vs-real",
            db_path=populated_db,
        )
        assert out == []

    def test_mismatched_agent_returns_empty(self, populated_db):
        """agent_or_tool with no matches returns empty list."""
        out = lcn_read.query_related_errors(
            agent_or_tool="ZZZZZZNOTFOUND",
            db_path=populated_db,
        )
        assert out == []

    def test_empty_filters_return_all(self, populated_db):
        """With no filters, up to limit errors are returned."""
        out = lcn_read.query_related_errors(
            db_path=populated_db,
        )
        assert len(out) >= 1
        assert len(out) <= 5

    def test_missing_db_returns_empty(self, tmp_path):
        """Graceful degradation when DB file does not exist."""
        out = lcn_read.query_related_errors(
            error_type="model-routing",
            db_path=tmp_path / "nonexistent.sqlite",
        )
        assert out == []


# ---------------------------------------------------------------------------
# 3. query_applicable_conventions
# ---------------------------------------------------------------------------


class TestQueryApplicableConventions:
    """Test query_applicable_conventions(scope, limit, db_path)."""

    def test_global_scope_returns_globals(self, populated_db):
        """Scope '*' returns conventions with scope='*'."""
        out = lcn_read.query_applicable_conventions(
            scope="*",
            db_path=populated_db,
        )
        scopes = {ent.get("data", {}).get("scope") for ent in out}
        assert "*" in scopes

    def test_exact_scope_match(self, populated_db):
        """Querying an exact scope returns the matching convention."""
        out = lcn_read.query_applicable_conventions(
            scope="tests",
            db_path=populated_db,
        )
        scopes = {ent.get("data", {}).get("scope") for ent in out}
        assert "tests" in scopes

    def test_directory_prefix_match(self, populated_db):
        """Querying a file path matches parent directory scope."""
        out = lcn_read.query_applicable_conventions(
            scope=".opencode/agent/orchestrator.md",
            db_path=populated_db,
        )
        scopes = {ent.get("data", {}).get("scope") for ent in out}
        assert ".opencode/agent" in scopes, f"Expected dir prefix match; got {scopes}"

    def test_no_match_returns_only_globals(self, populated_db):
        """Scope with no matching directory returns only global conventions."""
        out = lcn_read.query_applicable_conventions(
            scope="nonexistent/path",
            db_path=populated_db,
        )
        for ent in out:
            assert ent.get("data", {}).get("scope") == "*"

    def test_limit_respected(self, populated_db):
        """limit parameter caps the number of results."""
        out = lcn_read.query_applicable_conventions(
            scope="*",
            limit=1,
            db_path=populated_db,
        )
        assert len(out) <= 1

    def test_ordered_by_confidence_desc(self, populated_db):
        """Higher-confidence conventions appear first."""
        out = lcn_read.query_applicable_conventions(
            scope="*",
            db_path=populated_db,
        )
        confs = [ent.get("confidence", 0) for ent in out]
        assert confs == sorted(confs, reverse=True), (
            f"Not desc by confidence: {confs}"
        )

    def test_missing_db_returns_empty(self, tmp_path):
        """Graceful degradation when DB file does not exist."""
        out = lcn_read.query_applicable_conventions(
            scope="*",
            db_path=tmp_path / "nonexistent.sqlite",
        )
        assert out == []


# ---------------------------------------------------------------------------
# 4. query_entity_by_key
# ---------------------------------------------------------------------------


class TestQueryEntityByKey:
    """Test query_entity_by_key(natural_key, db_path)."""

    def test_found_by_natural_key(self, populated_db):
        """Look up a known entity by its stored natural_key."""
        decisions = lcn_read.query_recent_by_type("Decision", db_path=populated_db)
        assert len(decisions) >= 1
        nk = decisions[0].get("natural_key", "")
        assert nk, "Entity should have a natural_key"

        found = lcn_read.query_entity_by_key(nk, db_path=populated_db)
        assert found is not None
        assert found.get("natural_key") == nk
        assert found.get("entity_type") == "Decision"

    def test_not_found_returns_none(self, populated_db):
        """Non-existent natural_key returns None."""
        out = lcn_read.query_entity_by_key(
            "this-key-does-not-exist-1234567890",
            db_path=populated_db,
        )
        assert out is None

    def test_missing_db_returns_none(self, tmp_path):
        """Graceful degradation when DB file does not exist."""
        out = lcn_read.query_entity_by_key(
            "any-key",
            db_path=tmp_path / "nonexistent.sqlite",
        )
        assert out is None


# ---------------------------------------------------------------------------
# 5. query_recent_by_type
# ---------------------------------------------------------------------------


class TestQueryRecentByType:
    """Test query_recent_by_type(entity_type, limit, db_path)."""

    def test_returns_decisions(self, populated_db):
        out = lcn_read.query_recent_by_type("Decision", db_path=populated_db)
        assert len(out) >= 1
        for ent in out:
            assert ent.get("entity_type") == "Decision"

    def test_returns_errors(self, populated_db):
        out = lcn_read.query_recent_by_type("Error", db_path=populated_db)
        assert len(out) >= 1
        for ent in out:
            assert ent.get("entity_type") == "Error"

    def test_returns_conventions(self, populated_db):
        out = lcn_read.query_recent_by_type("Convention", db_path=populated_db)
        assert len(out) >= 1
        for ent in out:
            assert ent.get("entity_type") == "Convention"

    def test_returns_patterns(self, populated_db):
        out = lcn_read.query_recent_by_type("Pattern", db_path=populated_db)
        assert len(out) >= 1
        for ent in out:
            assert ent.get("entity_type") == "Pattern"

    def test_returns_rejections(self, populated_db):
        out = lcn_read.query_recent_by_type("Rejection", db_path=populated_db)
        assert len(out) >= 1
        for ent in out:
            assert ent.get("entity_type") == "Rejection"

    def test_case_insensitive_type(self, populated_db):
        """entity_type matching is case-insensitive."""
        out = lcn_read.query_recent_by_type("decision", db_path=populated_db)
        assert len(out) >= 1
        for ent in out:
            assert ent.get("entity_type") == "Decision"

    def test_limit_respected(self, populated_db):
        out = lcn_read.query_recent_by_type("Decision", limit=1, db_path=populated_db)
        assert len(out) <= 1

    def test_no_match_returns_empty(self, populated_db):
        out = lcn_read.query_recent_by_type(
            "NonExistentType",
            db_path=populated_db,
        )
        assert out == []

    def test_missing_db_returns_empty(self, tmp_path):
        out = lcn_read.query_recent_by_type(
            "Decision",
            db_path=tmp_path / "nonexistent.sqlite",
        )
        assert out == []


# ---------------------------------------------------------------------------
# consult.py CLI — valid JSON output for each subcommand
# ---------------------------------------------------------------------------


class TestConsultCLI:
    """consult.py CLI should always produce valid JSON, even with empty DB."""

    def _run_consult(self, *args: str) -> dict:
        tools_dir = CONSULT_PATH.parent
        env = {**os.environ, "PYTHONPATH": str(tools_dir)}
        result = subprocess.run(
            [sys.executable, str(CONSULT_PATH), *args],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
        assert result.returncode == 0, (
            f"CLI '{' '.join(args)}' failed: {result.stderr}"
        )
        return json.loads(result.stdout)

    def test_pre_plan_valid_json(self):
        """pre_plan produces JSON with status and results keys."""
        data = self._run_consult("pre_plan", "implement user authentication")
        assert "status" in data, f"Missing 'status' in {list(data)}"
        assert data["status"] in ("ok", "degraded")
        if data["status"] == "ok":
            results = data.get("results", {})
            assert "similar_decisions" in results
            assert "applicable_conventions" in results

    def test_pre_dispatch_valid_json(self):
        """pre_dispatch produces JSON with agent and known_pitfalls keys."""
        data = self._run_consult("pre_dispatch", "coder", "deepseek-v4-flash")
        assert "status" in data
        assert data["status"] in ("ok", "degraded")
        if data["status"] == "ok":
            results = data.get("results", {})
            assert "agent" in results
            assert "known_pitfalls" in results

    def test_post_verify_valid_json(self):
        """post_verify produces JSON with feature and applicable_conventions keys."""
        data = self._run_consult(
            "post_verify", "test-feature", "file1.py,file2.py"
        )
        assert "status" in data
        assert data["status"] in ("ok", "degraded")
        if data["status"] == "ok":
            results = data.get("results", {})
            assert "feature" in results
            assert "applicable_conventions" in results

    def test_cli_graceful_without_env_pythonpath(self):
        """Without PYTHONPATH in env, CLI still works because consult.py's
        directory (.opencode/tools/) is auto-added to sys.path by the
        interpreter, making lcn_read importable. Verify valid JSON output."""
        clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        result = subprocess.run(
            [sys.executable, str(CONSULT_PATH), "pre_plan", "test task"],
            capture_output=True,
            text=True,
            timeout=10,
            env=clean_env,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "status" in data
        assert data["status"] in ("ok", "degraded")
        # When the module IS available (sys.path[0] pragma), status is "ok"
        # with empty results — never a crash.
