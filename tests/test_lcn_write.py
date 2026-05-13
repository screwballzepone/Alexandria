"""Test suite for .opencode/tools/lcn_write.py.

Coverage:
  - ULID shape + Crockford alphabet
  - Canonicalization stability (NFKC + case + whitespace + edge punct)
  - hash12 / file_paths_hash determinism
  - Validation: common (entity_type, confidence), per-type required fields
  - Decision: outcome enum, alternatives shape, Enterprise alternatives floor
  - Rejection: context_that_might_change_this >= 15 chars
  - Error: failure_class taxonomy enforcement
  - Convention: confidence >= 3 floor
  - write_entity idempotency: same natural key updates in place, new id only on insert
  - write_many: multiple entities under one connection, returns same length
  - Seed JSONL files (conventions.jsonl + errors.jsonl) round-trip cleanly
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loader — locate .opencode/tools/lcn_write.py from repo root
# ---------------------------------------------------------------------------


def _load_lcn_write():
    """Load .opencode/tools/lcn_write.py as a module under a stable name.

    Walks up from this test file to find the repo root (folder containing
    .opencode/), then loads the canonical lcn_write at that location.
    """
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        candidate = parent / ".opencode" / "tools" / "lcn_write.py"
        if candidate.exists():
            spec = importlib.util.spec_from_file_location("lcn_write", candidate)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["lcn_write"] = mod
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            return mod
    raise RuntimeError(
        "Could not find .opencode/tools/lcn_write.py walking up from " + str(here)
    )


lcn = _load_lcn_write()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db(tmp_path):
    """Fresh isolated DB per test."""
    return tmp_path / "test.sqlite"


def _make_decision(**overrides):
    base = {
        "entity_type": "Decision",
        "mission_id": "test-mission-001",
        "confidence": 4,
        "file_paths": [".opencode/tools/lcn_write.py"],
        "chosen_approach": "SQLite stdlib only, no ORM",
        "rationale": "Portability over ergonomics; no third-party dependencies.",
        "outcome": "succeeded",
    }
    base.update(overrides)
    return base


def _make_rejection(**overrides):
    base = {
        "entity_type": "Rejection",
        "mission_id": "test-mission-001",
        "confidence": 3,
        "approach": "Use SQLAlchemy ORM",
        "reason": "Adds a heavy dependency for trivial CRUD.",
        "context_that_might_change_this": "Once schema mutation churn exceeds 5/month.",
    }
    base.update(overrides)
    return base


def _make_error(**overrides):
    base = {
        "entity_type": "Error",
        "mission_id": "test-mission-001",
        "confidence": 4,
        "failure_class": "model-routing",
        "file_paths": [".opencode/agent/orchestrator.md"],
        "symptom": "Orchestrator answered with google.thoughtSignature metadata",
        "root_cause": "OpenCode silent fallback to small_model when ID is unresolved.",
        "fix_applied": "Set top-level model in opencode.json to a registered ID.",
    }
    base.update(overrides)
    return base


def _make_pattern(**overrides):
    base = {
        "entity_type": "Pattern",
        "mission_id": "test-mission-001",
        "confidence": 3,
        "shape_description": "Use --model CLI flag for primary routing",
        "when_to_use": "When agent frontmatter model: differs from desired",
        "when_not_to_use": "Sub-agent dispatch — frontmatter is honored there",
        "scope": ".opencode/run-scripts/*",
    }
    base.update(overrides)
    return base


def _make_convention(**overrides):
    base = {
        "entity_type": "Convention",
        "mission_id": "test-mission-001",
        "confidence": 4,
        "scope": ".opencode/agent/*",
        "rule": "Primary-session model is governed by opencode.json or --model.",
        "why": "Finding O: frontmatter is silently ignored for primary routing.",
        "example": "Set model: 'anthropic/claude-sonnet-4-5' in opencode.json.",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. ULID shape
# ---------------------------------------------------------------------------


def test_ulid_shape():
    u = lcn.ulid()
    assert len(u) == 26, f"ULID must be 26 chars, got {len(u)}: {u!r}"
    assert set(u) <= set(lcn._ULID_ALPHABET), (
        f"ULID must use Crockford alphabet only, got: {u!r}"
    )


def test_ulid_uniqueness():
    """Two ULIDs in quick succession should differ in their random suffix."""
    a = lcn.ulid()
    b = lcn.ulid()
    assert a != b, f"Two ULIDs collided: {a}"


# ---------------------------------------------------------------------------
# 2. Canonicalization
# ---------------------------------------------------------------------------


def test_canonicalize_stability():
    # Mixed case + extra whitespace + leading/trailing punctuation
    assert lcn.canonicalize("  Hello,  World!  ") == "hello, world"
    # NFKC: full-width digit -> ASCII digit
    assert lcn.canonicalize("ｆｏｏ123") == "foo123"
    # Idempotent: f(f(x)) == f(x)
    s = "  Test  STRING  ..."
    assert lcn.canonicalize(lcn.canonicalize(s)) == lcn.canonicalize(s)


def test_hash12_deterministic():
    h1 = lcn.hash12("the same input")
    h2 = lcn.hash12("the same input")
    assert h1 == h2
    assert len(h1) == 12
    # Different input -> different hash
    assert lcn.hash12("different") != h1


def test_file_paths_hash_order_independent():
    a = lcn.file_paths_hash(["a.py", "b.py", "c.py"])
    b = lcn.file_paths_hash(["c.py", "a.py", "b.py"])
    c = lcn.file_paths_hash(["a.py", "b.py", "a.py", "c.py"])  # dup-safe
    assert a == b == c


# ---------------------------------------------------------------------------
# 3. Common validation
# ---------------------------------------------------------------------------


def test_invalid_entity_type():
    with pytest.raises(lcn.ValidationError, match="entity_type"):
        lcn._check_entity({"entity_type": "Vibe", "confidence": 3})


def test_confidence_out_of_range():
    bad_low = _make_decision(confidence=0)
    bad_high = _make_decision(confidence=6)
    with pytest.raises(lcn.ValidationError, match="confidence"):
        lcn._check_entity(bad_low)
    with pytest.raises(lcn.ValidationError, match="confidence"):
        lcn._check_entity(bad_high)


# ---------------------------------------------------------------------------
# 4. Decision rules: outcome + alternatives + Enterprise floor
# ---------------------------------------------------------------------------


def test_decision_invalid_outcome():
    with pytest.raises(lcn.ValidationError, match="outcome"):
        lcn._check_entity(_make_decision(outcome="vibes"))


def test_decision_alternatives_shape():
    e = _make_decision(alternatives=[{"approach": "x"}])  # missing reason_dropped
    with pytest.raises(lcn.ValidationError, match="reason_dropped"):
        lcn._check_entity(e)


def test_enterprise_decision_requires_alternatives():
    e = _make_decision()
    e["_tier"] = "Enterprise"
    # No alternatives set
    with pytest.raises(lcn.ValidationError, match="Enterprise"):
        lcn._check_entity(e)
    # Empty list also rejected
    e["alternatives"] = []
    with pytest.raises(lcn.ValidationError, match="Enterprise"):
        lcn._check_entity(e)
    # Properly formed alternatives -> passes
    e["alternatives"] = [
        {"approach": "use ORM", "reason_dropped": "too heavy for needs"}
    ]
    lcn._check_entity(e)  # should not raise


# ---------------------------------------------------------------------------
# 5. Rejection context floor
# ---------------------------------------------------------------------------


def test_rejection_context_too_short():
    e = _make_rejection(context_that_might_change_this="short")  # < 15 chars
    with pytest.raises(lcn.ValidationError, match="15 chars"):
        lcn._check_entity(e)


def test_rejection_context_at_floor():
    # Exactly at 15-char floor should pass
    e = _make_rejection(context_that_might_change_this="x" * 15)
    lcn._check_entity(e)


# ---------------------------------------------------------------------------
# 6. Error taxonomy enforcement
# ---------------------------------------------------------------------------


def test_error_invalid_failure_class():
    e = _make_error(failure_class="vibes-mismatch")
    with pytest.raises(lcn.ValidationError, match="failure_class"):
        lcn._check_entity(e)


def test_error_all_failure_classes_accepted():
    """Every class enumerated in lcn.FAILURE_CLASSES must validate."""
    for fc in lcn.FAILURE_CLASSES:
        e = _make_error(failure_class=fc)
        lcn._check_entity(e)  # should not raise


# ---------------------------------------------------------------------------
# 7. Convention confidence floor
# ---------------------------------------------------------------------------


def test_convention_confidence_floor():
    e = _make_convention(confidence=2)  # below 3
    with pytest.raises(lcn.ValidationError, match="confidence"):
        lcn._check_entity(e)


def test_convention_at_floor():
    e = _make_convention(confidence=3)  # at floor
    lcn._check_entity(e)


# ---------------------------------------------------------------------------
# 8. write_entity idempotency
# ---------------------------------------------------------------------------


def test_decision_write_then_reread(tmp_db):
    e = _make_decision()
    conn = lcn.get_conn(tmp_db)
    try:
        out = lcn.write_entity(e, conn=conn)
        assert "id" in out
        assert out["created_at"] == out["updated_at"]
        # Verify row exists
        cur = conn.execute("SELECT COUNT(*) AS n FROM entities")
        assert cur.fetchone()["n"] == 1
    finally:
        conn.close()


def test_decision_idempotent_upsert(tmp_db):
    e = _make_decision()
    conn = lcn.get_conn(tmp_db)
    try:
        first = lcn.write_entity(e, conn=conn)
        # Mutate a non-natural-key field and rewrite
        e2 = _make_decision(rationale="updated rationale text")
        second = lcn.write_entity(e2, conn=conn)
        # Same row: id preserved, created_at preserved
        assert second["id"] == first["id"]
        assert second["created_at"] == first["created_at"]
        # Only one row in the table
        cur = conn.execute("SELECT COUNT(*) AS n FROM entities")
        assert cur.fetchone()["n"] == 1
    finally:
        conn.close()


def test_decision_distinct_natural_keys(tmp_db):
    """Different file_paths -> different natural keys -> different rows."""
    a = _make_decision(file_paths=["a.py"])
    b = _make_decision(file_paths=["b.py"])
    conn = lcn.get_conn(tmp_db)
    try:
        out_a = lcn.write_entity(a, conn=conn)
        out_b = lcn.write_entity(b, conn=conn)
        assert out_a["id"] != out_b["id"]
        cur = conn.execute("SELECT COUNT(*) AS n FROM entities")
        assert cur.fetchone()["n"] == 2
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 9. write_many batch
# ---------------------------------------------------------------------------


def test_write_many_basic(tmp_db):
    entities = [
        _make_decision(file_paths=["a.py"]),
        _make_decision(file_paths=["b.py"]),
        _make_convention(),
        _make_pattern(),
    ]
    out = lcn.write_many(entities, db_path=tmp_db)
    assert len(out) == 4
    # All have ids assigned
    assert all("id" in o for o in out)
    # Verify count in DB
    conn = sqlite3.connect(tmp_db)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM entities")
        assert cur.fetchone()[0] == 4
    finally:
        conn.close()


def test_write_many_idempotent_on_replay(tmp_db):
    """Writing the same batch twice yields the same row count."""
    entities = [_make_decision(), _make_convention()]
    lcn.write_many(entities, db_path=tmp_db)
    lcn.write_many(entities, db_path=tmp_db)  # replay
    conn = sqlite3.connect(tmp_db)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM entities")
        assert cur.fetchone()[0] == 2  # NOT 4
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 10. Seed JSONL round-trip
# ---------------------------------------------------------------------------


def _seeds_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        candidate = parent / "MagnumOpus" / "seeds"
        if candidate.exists():
            return candidate
    raise RuntimeError("Could not locate MagnumOpus/seeds/")


def test_seed_conventions_round_trip(tmp_db):
    """Every entity in seeds/conventions.jsonl writes cleanly via write_many."""
    path = _seeds_dir() / "conventions.jsonl"
    assert path.exists()
    entities = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(entities) == 8
    out = lcn.write_many(entities, db_path=tmp_db)
    assert len(out) == 8
    # Confirm all stored
    conn = sqlite3.connect(tmp_db)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM entities WHERE entity_type='Convention'")
        assert cur.fetchone()[0] == 8
    finally:
        conn.close()


def test_seed_errors_round_trip(tmp_db):
    """Every entity in seeds/errors.jsonl writes cleanly via write_many."""
    path = _seeds_dir() / "errors.jsonl"
    assert path.exists()
    entities = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(entities) == 8
    out = lcn.write_many(entities, db_path=tmp_db)
    assert len(out) == 8
    conn = sqlite3.connect(tmp_db)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM entities WHERE entity_type='Error'")
        assert cur.fetchone()[0] == 8
    finally:
        conn.close()
