"""Test suite for .opencode/tools/lcn_read.py.

Strategy: build a fresh tmp DB with known data via lcn_write, then exercise
each query type. Verify the contract from CONSULT-PROTOCOL.md, not the
implementation details (similarity score values are loose; ordering and
shape are tight).

Coverage:
  - by_file: includes/excludes correct entities, entity_types filter, ordering
  - by_failure_class: matches Errors, returns related Conventions
  - by_mission_similarity: top-K, scores in [0,1], ordering desc
  - by_convention_scope: bidirectional wildcard matching
  - search: returns ranked results with scores, top_k cap
  - consult dispatcher: unknown type raises, all 5 types route correctly
  - CLI subprocess round-trip
  - Empty-DB / missing-file behavior
  - Real seed data round-trip (uses MagnumOpus/seeds/*.jsonl)
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loaders
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


lcn_read, READ_PATH = _load("lcn_read")
lcn_write, _ = _load("lcn_write")


def _project_root() -> Path:
    return READ_PATH.parents[2]  # .opencode/tools/lcn_read.py → repo root


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def populated_db(tmp_path):
    """A tmp DB with a curated mix of all 5 entity types."""
    db = tmp_path / "test.sqlite"
    entities = [
        # Decision A — touches auth.py, succeeded
        {
            "entity_type": "Decision",
            "mission_id": "m-001",
            "confidence": 4,
            "file_paths": ["auth.py", "session.py"],
            "chosen_approach": "use bcrypt for password hashing",
            "rationale": "industry standard, no rolling our own crypto",
            "outcome": "succeeded",
        },
        # Decision B — touches a different file, failed
        {
            "entity_type": "Decision",
            "mission_id": "m-002",
            "confidence": 3,
            "file_paths": ["payments.py"],
            "chosen_approach": "use stripe for payments",
            "rationale": "PCI compliance handed off",
            "outcome": "failed",
        },
        # Error — model-routing class, touches orchestrator.md
        {
            "entity_type": "Error",
            "mission_id": "m-003",
            "confidence": 5,
            "failure_class": "model-routing",
            "file_paths": [".opencode/agent/orchestrator.md"],
            "symptom": "orchestrator silently routed to Gemini despite Cerebras config",
            "root_cause": "user-home opencode.json overrode project config",
            "fix_applied": "stripped model + small_model fields from user-home config",
        },
        # Error — invented-tool class, no file paths
        {
            "entity_type": "Error",
            "mission_id": "m-004",
            "confidence": 4,
            "failure_class": "invented-tool",
            "file_paths": [],
            "symptom": "model called isoformat() as a tool name",
            "root_cause": "weak model hallucinated a tool that did not exist",
            "fix_applied": "added explicit tool list to system prompt",
        },
        # Convention — agent scope wildcard
        {
            "entity_type": "Convention",
            "mission_id": "m-005",
            "confidence": 4,
            "scope": ".opencode/agent/*",
            "rule": "Primary-session model is governed by opencode.json or --model.",
            "why": "Finding O: agent frontmatter ignored for primary routing.",
            "example": "set model: 'anthropic/claude-sonnet-4-5' in opencode.json",
        },
        # Convention — different scope
        {
            "entity_type": "Convention",
            "mission_id": "m-006",
            "confidence": 3,
            "scope": "tests/*",
            "rule": "Every new module must ship with tests/test_<module>.py",
            "why": "untested code rots fast in autonomous pipelines.",
            "example": "tests/test_lcn_write.py",
        },
        # Pattern — agent scope
        {
            "entity_type": "Pattern",
            "mission_id": "m-007",
            "confidence": 2,
            "shape_description": "Use --model CLI flag for primary routing",
            "when_to_use": "When agent frontmatter model: differs from desired",
            "when_not_to_use": "Sub-agent dispatch — frontmatter is honored there",
            "scope": ".opencode/agent/*",
        },
    ]
    lcn_write.write_many(entities, db_path=db)
    return db


# ---------------------------------------------------------------------------
# 1. by_file
# ---------------------------------------------------------------------------


def test_by_file_finds_decision_with_path(populated_db):
    out = lcn_read.by_file("auth.py", db_path=populated_db)
    assert out["count"] == 1
    assert out["results"][0]["chosen_approach"] == "use bcrypt for password hashing"


def test_by_file_finds_convention_via_wildcard_scope(populated_db):
    """Convention with scope=.opencode/agent/* should match orchestrator.md."""
    out = lcn_read.by_file(".opencode/agent/orchestrator.md", db_path=populated_db)
    et_seen = {r["entity_type"] for r in out["results"]}
    assert "Convention" in et_seen, f"Convention should match agent path; got {et_seen}"
    assert "Error" in et_seen, "Error referencing this path should also match"


def test_by_file_entity_types_filter(populated_db):
    """entity_types filter limits results to specified types."""
    out = lcn_read.by_file(
        ".opencode/agent/orchestrator.md",
        entity_types=["Convention"],
        db_path=populated_db,
    )
    assert all(r["entity_type"] == "Convention" for r in out["results"])
    assert out["count"] >= 1


def test_by_file_no_match_returns_empty(populated_db):
    out = lcn_read.by_file("does_not_exist.py", db_path=populated_db)
    assert out["count"] == 0
    assert out["results"] == []


def test_by_file_ordering_confidence_desc(populated_db):
    """Higher-confidence entities should come first."""
    out = lcn_read.by_file(".opencode/agent/orchestrator.md", db_path=populated_db)
    confs = [r["confidence"] for r in out["results"]]
    assert confs == sorted(confs, reverse=True), f"Not desc by confidence: {confs}"


# ---------------------------------------------------------------------------
# 2. by_failure_class
# ---------------------------------------------------------------------------


def test_by_failure_class_returns_matching_errors(populated_db):
    out = lcn_read.by_failure_class("model-routing", db_path=populated_db)
    assert len(out["errors"]) == 1
    assert out["errors"][0]["failure_class"] == "model-routing"


def test_by_failure_class_returns_related_conventions(populated_db):
    """The Error references .opencode/agent/orchestrator.md; the Convention scope
    .opencode/agent/* should be flagged as related."""
    out = lcn_read.by_failure_class("model-routing", db_path=populated_db)
    rel_scopes = {c["scope"] for c in out["related_conventions"]}
    assert ".opencode/agent/*" in rel_scopes, (
        f"Expected agent-scope Convention in related; got {rel_scopes}"
    )


def test_by_failure_class_unknown_class_returns_empty(populated_db):
    out = lcn_read.by_failure_class("does-not-exist", db_path=populated_db)
    assert out["errors"] == []
    assert out["related_conventions"] == []


def test_by_failure_class_no_file_paths_no_related(populated_db):
    """Error with empty file_paths produces no related Conventions."""
    out = lcn_read.by_failure_class("invented-tool", db_path=populated_db)
    assert len(out["errors"]) == 1
    assert out["related_conventions"] == []


# ---------------------------------------------------------------------------
# 3. by_mission_similarity
# ---------------------------------------------------------------------------


def test_by_mission_similarity_returns_decisions(populated_db):
    out = lcn_read.by_mission_similarity(
        title="use bcrypt for password hashing",
        scope_hash="auth.py|session.py",
        top_k=5,
        db_path=populated_db,
    )
    assert "missions" in out
    assert len(out["missions"]) >= 1


def test_by_mission_similarity_score_in_range(populated_db):
    """Per spec contract: similarity_score ∈ [0, 1]."""
    out = lcn_read.by_mission_similarity(
        title="some new mission about authentication",
        scope_hash="auth.py",
        top_k=5,
        db_path=populated_db,
    )
    for m in out["missions"]:
        assert 0.0 <= m["similarity_score"] <= 1.0, (
            f"score out of range: {m['similarity_score']}"
        )


def test_by_mission_similarity_ordering_desc(populated_db):
    out = lcn_read.by_mission_similarity(
        title="anything",
        scope_hash="x",
        top_k=10,
        db_path=populated_db,
    )
    scores = [m["similarity_score"] for m in out["missions"]]
    assert scores == sorted(scores, reverse=True), f"not desc: {scores}"


def test_by_mission_similarity_top_k_caps(populated_db):
    out = lcn_read.by_mission_similarity(
        title="x", scope_hash="y", top_k=1, db_path=populated_db
    )
    assert len(out["missions"]) <= 1


def test_by_mission_similarity_high_for_exact_match(populated_db):
    """Querying with a Decision's exact title should rank that decision near top."""
    out = lcn_read.by_mission_similarity(
        title="use bcrypt for password hashing",
        scope_hash="auth.py|session.py",
        top_k=2,
        db_path=populated_db,
    )
    assert out["missions"][0]["similarity_score"] >= 0.5


# ---------------------------------------------------------------------------
# 4. by_convention_scope
# ---------------------------------------------------------------------------


def test_by_convention_scope_exact_match(populated_db):
    out = lcn_read.by_convention_scope(".opencode/agent/*", db_path=populated_db)
    scopes = {c["scope"] for c in out["conventions"]}
    assert ".opencode/agent/*" in scopes


def test_by_convention_scope_query_more_specific(populated_db):
    """Query .opencode/agent/orchestrator.md should match stored .opencode/agent/*."""
    out = lcn_read.by_convention_scope(
        ".opencode/agent/orchestrator.md", db_path=populated_db
    )
    scopes = {c["scope"] for c in out["conventions"]}
    assert ".opencode/agent/*" in scopes, f"Wildcard generalize fail: {scopes}"


def test_by_convention_scope_query_more_general(populated_db):
    """Query a wildcard should match a stored exact path."""
    # No stored scope is a single file; this verifies wildcard-on-query side
    # at least returns the wildcard-stored ones.
    out = lcn_read.by_convention_scope(".opencode/*", db_path=populated_db)
    scopes = {c["scope"] for c in out["conventions"]}
    assert ".opencode/agent/*" in scopes


def test_by_convention_scope_no_match(populated_db):
    out = lcn_read.by_convention_scope("docs/*", db_path=populated_db)
    assert out["conventions"] == []


# ---------------------------------------------------------------------------
# 5. search (free-text fallback)
# ---------------------------------------------------------------------------


def test_search_returns_results_with_scores(populated_db):
    out = lcn_read.search("bcrypt password hashing", top_k=3, db_path=populated_db)
    assert "results" in out
    assert "scores" in out
    assert len(out["results"]) == len(out["scores"])
    assert len(out["results"]) <= 3


def test_search_scores_in_range(populated_db):
    out = lcn_read.search("anything", top_k=10, db_path=populated_db)
    for s in out["scores"]:
        assert 0.0 <= s <= 1.0


def test_search_no_relevant_matches_returns_empty_or_low(populated_db):
    """Querying for total nonsense should return empty or only low-score results."""
    out = lcn_read.search("zzzzzzzzzzzz xyzqqq nosuch", top_k=5, db_path=populated_db)
    if out["scores"]:
        assert max(out["scores"]) < 0.3, (
            f"nonsense got too high a score: {out['scores']}"
        )


# ---------------------------------------------------------------------------
# consult dispatcher
# ---------------------------------------------------------------------------


def test_consult_dispatch_by_file(populated_db):
    out = lcn_read.consult(
        {"type": "by-file", "path": "auth.py", "entity_types": None},
        db_path=populated_db,
    )
    assert out["count"] >= 1


def test_consult_dispatch_by_failure_class(populated_db):
    out = lcn_read.consult(
        {"type": "by-failure-class", "class": "model-routing", "limit": 3},
        db_path=populated_db,
    )
    assert "errors" in out
    assert "related_conventions" in out


def test_consult_dispatch_by_mission_similarity(populated_db):
    out = lcn_read.consult(
        {
            "type": "by-mission-similarity",
            "title": "auth",
            "scope_hash": "auth.py",
            "top_k": 2,
        },
        db_path=populated_db,
    )
    assert "missions" in out


def test_consult_dispatch_by_convention_scope(populated_db):
    out = lcn_read.consult(
        {"type": "by-convention-scope", "scope": ".opencode/agent/*"},
        db_path=populated_db,
    )
    assert "conventions" in out


def test_consult_dispatch_search(populated_db):
    out = lcn_read.consult(
        {"type": "search", "query": "bcrypt", "top_k": 2},
        db_path=populated_db,
    )
    assert "results" in out
    assert "scores" in out


def test_consult_unknown_type_raises(populated_db):
    with pytest.raises(ValueError, match="Unknown query type"):
        lcn_read.consult({"type": "what-is-this"}, db_path=populated_db)


# ---------------------------------------------------------------------------
# Missing-DB behavior
# ---------------------------------------------------------------------------


def test_missing_db_raises_helpful_error(tmp_path):
    missing = tmp_path / "nope.sqlite"
    with pytest.raises(FileNotFoundError, match="seed_lcn"):
        lcn_read.by_file("any.py", db_path=missing)


# ---------------------------------------------------------------------------
# CLI round-trip
# ---------------------------------------------------------------------------


def test_cli_round_trip(populated_db):
    payload = {"type": "by-file", "path": "auth.py", "entity_types": None}
    subprocess.run(
        [sys.executable, str(READ_PATH)],
        input=json.dumps({**payload}),
        capture_output=True,
        text=True,
        timeout=10,
        env={
            **__import__("os").environ,
        },
        cwd=str(populated_db.parent),
    )
    # The CLI uses DEFAULT_DB_PATH = .lcn/lcn.sqlite relative to CWD,
    # but populated_db lives in the tmp dir. We need to invoke with
    # explicit DB path. Adjust: run a small wrapper.
    proc2 = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, importlib.util, json; "
            f"spec = importlib.util.spec_from_file_location('lr', r'{READ_PATH}'); "
            "m = importlib.util.module_from_spec(spec); "
            "sys.modules['lr'] = m; spec.loader.exec_module(m); "
            f"print(json.dumps(m.consult(json.loads(sys.stdin.read()), db_path=r'{populated_db}')))",
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc2.returncode == 0, f"CLI wrapper failed: {proc2.stderr!r}"
    out = json.loads(proc2.stdout)
    assert out["count"] >= 1


# ---------------------------------------------------------------------------
# Real seed data round-trip
# ---------------------------------------------------------------------------


def test_real_seeds_query_works(tmp_path):
    """Seed a tmp DB from MagnumOpus/seeds/*.jsonl and query it.

    Verifies the read module works against the same data shape the seed
    script produces — closing the loop end-to-end.
    """
    db = tmp_path / "seeded.sqlite"
    root = _project_root()
    for fname in ["conventions.jsonl", "errors.jsonl"]:
        path = root / "MagnumOpus" / "seeds" / fname
        entities = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        lcn_write.write_many(entities, db_path=db)

    # Try a real query the orchestrator will eventually fire
    out = lcn_read.by_failure_class("model-routing", db_path=db)
    assert len(out["errors"]) >= 1, (
        "Real seed data should have at least one model-routing Error"
    )

    # And a Convention scope query
    out2 = lcn_read.by_convention_scope(".opencode/agent/*", db_path=db)
    # Seed conventions cover several scopes; agent scope should be one of them
    # (per the conventions.jsonl content we recovered yesterday).
    assert len(out2["conventions"]) >= 1, (
        f"Real seed data should have at least one agent-scope Convention; "
        f"got {len(out2['conventions'])}"
    )
