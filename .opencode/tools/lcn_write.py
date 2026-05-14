"""lcn_write.py — LCN entity write module

Authority:
  MagnumOpus/LCN-SCHEMA.md (entity shapes, natural keys, idempotency)
  MagnumOpus/failure-classes.md (bounded Error taxonomy)
  MagnumOpus/TWO-MINDS.md §3.2

This is the write-side module for the LCN entity store. It validates and persists
the five entity types (Decision, Rejection, Error, Pattern, Convention) to SQLite.
Writes are idempotent on the natural keys defined in LCN-SCHEMA.md.

Deployed from MagnumOpus/reference/lcn_write.py. Reference copy retained there
per BLOCKED ≠ DEAD rule.

Design choices:
  - SQLite stdlib only, no ORM. Portability over ergonomics.
  - Entities stored as JSON blobs in a `data` column plus indexed
    natural_key + entity_type. Schema stays simple and extensible.
  - ULID generation is inline (no third-party dep).
  - Validation errors raise ValidationError (subclass of ValueError).
  - Read-side lives in lcn_read.py and consult.py (CLI).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "opencode" / "lcn_memory.db"

ENTITY_TYPES = {"Decision", "Rejection", "Error", "Pattern", "Convention"}

# Mirror of MagnumOpus/failure-classes.md v1. Keep in sync — any PR that
# amends the taxonomy must amend this set in the same commit.
FAILURE_CLASSES = {
    "model-routing",
    "agent-frontmatter-ignored",
    "edit-shape-error",
    "invented-tool",
    "ci-flake-vs-real",
    "convention-violation",
    "consult-skipped",
    "budget-overrun",
}

DECISION_OUTCOMES = {"pending", "succeeded", "failed", "rolled-back"}


# ---------------------------------------------------------------------------
# ULID (tiny stdlib-only implementation)
# ---------------------------------------------------------------------------

_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32


def ulid() -> str:
    """Generate a 26-char ULID. Monotonic within a process; good enough for
    our write volume (~dozens/mission)."""
    ms = int(time.time() * 1000)
    rand = os.urandom(10)
    ts_part = _encode_base32((ms).to_bytes(6, "big"), width=10)
    rand_part = _encode_base32(rand, width=16)
    return ts_part + rand_part


def _encode_base32(data: bytes, width: int) -> str:
    num = int.from_bytes(data, "big")
    out_chars = []
    for _ in range(width):
        out_chars.append(_ULID_ALPHABET[num & 0x1F])
        num >>= 5
    return "".join(reversed(out_chars))


# ---------------------------------------------------------------------------
# Canonicalization
# ---------------------------------------------------------------------------

_PUNCT_STRIP = re.compile(r"^[^\w]+|[^\w]+$")


def canonicalize(text: str) -> str:
    """LCN-SCHEMA.md canonicalization: NFKC normalize, lowercase, collapse
    whitespace, strip leading/trailing punctuation."""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = _PUNCT_STRIP.sub("", text)
    return text


def hash12(text: str) -> str:
    """SHA-1 of the canonicalized text, first 12 chars."""
    return hashlib.sha1(canonicalize(text).encode("utf-8")).hexdigest()[:12]


def file_paths_hash(paths: Iterable[str]) -> str:
    """Hash over the sorted, deduplicated, canonicalized paths."""
    seq = sorted({canonicalize(p) for p in paths})
    return hashlib.sha1("\0".join(seq).encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# SQLite schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entities (
    id            TEXT PRIMARY KEY,
    entity_type   TEXT NOT NULL,
    natural_key   TEXT NOT NULL,
    mission_id    TEXT,
    confidence    INTEGER NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    data          TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_natural_key
    ON entities(entity_type, natural_key);
CREATE INDEX IF NOT EXISTS idx_entities_mission  ON entities(mission_id);
CREATE INDEX IF NOT EXISTS idx_entities_type     ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_conf     ON entities(confidence);
"""


def get_conn(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Return a connection, creating parent dirs and schema if needed."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    return conn


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class ValidationError(ValueError):
    """Raised when an entity fails schema validation."""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValidationError(msg)


def _check_common(e: dict[str, Any]) -> None:
    _require(
        "entity_type" in e and e["entity_type"] in ENTITY_TYPES,
        f"entity_type must be one of {sorted(ENTITY_TYPES)}",
    )
    _require(
        isinstance(e.get("confidence"), int) and 1 <= e["confidence"] <= 5,
        "confidence must be an integer in [1, 5]",
    )


def _check_entity(e: dict[str, Any]) -> None:
    """Validate an entity. Raises ValidationError on any violation."""
    _check_common(e)
    t = e["entity_type"]

    if t == "Decision":
        _require(isinstance(e.get("file_paths"), list), "Decision.file_paths must be a list")
        _require(
            isinstance(e.get("chosen_approach"), str) and e["chosen_approach"].strip(),
            "Decision.chosen_approach required",
        )
        _require(
            isinstance(e.get("rationale"), str) and e["rationale"].strip(),
            "Decision.rationale required",
        )
        _require(
            e.get("outcome") in DECISION_OUTCOMES,
            f"Decision.outcome must be one of {sorted(DECISION_OUTCOMES)}",
        )
        # Enterprise tier requires non-empty alternatives; caller passes _tier.
        if e.get("_tier") == "Enterprise":
            alts = e.get("alternatives")
            _require(
                isinstance(alts, list) and alts,
                "Enterprise Decision must have non-empty alternatives",
            )
        if "alternatives" in e:
            for i, a in enumerate(e["alternatives"]):
                _require(
                    isinstance(a, dict) and "approach" in a and "reason_dropped" in a,
                    f"Decision.alternatives[{i}] must have approach + reason_dropped",
                )

    elif t == "Rejection":
        _require(
            isinstance(e.get("approach"), str) and e["approach"].strip(),
            "Rejection.approach required",
        )
        _require(
            isinstance(e.get("reason"), str) and e["reason"].strip(), "Rejection.reason required"
        )
        ctx = e.get("context_that_might_change_this")
        _require(
            isinstance(ctx, str) and ctx.strip(),
            "Rejection.context_that_might_change_this required and non-empty",
        )
        _require(
            len(ctx.strip()) >= 15,
            "Rejection.context_that_might_change_this must be specific "
            "(>=15 chars); 'if things change' will not do",
        )

    elif t == "Error":
        fc = e.get("failure_class")
        _require(
            fc in FAILURE_CLASSES,
            f"Error.failure_class must be one of {sorted(FAILURE_CLASSES)}; "
            f"got {fc!r}. Add the class to failure-classes.md first.",
        )
        _require(
            isinstance(e.get("file_paths"), list),
            "Error.file_paths must be a list (may be empty for non-file failures)",
        )
        for field in ("symptom", "root_cause", "fix_applied"):
            _require(isinstance(e.get(field), str) and e[field].strip(), f"Error.{field} required")

    elif t == "Pattern":
        for field in ("shape_description", "when_to_use", "when_not_to_use", "scope"):
            _require(
                isinstance(e.get(field), str) and e[field].strip(), f"Pattern.{field} required"
            )

    elif t == "Convention":
        _require(
            e["confidence"] >= 3,
            "Convention writes require confidence >= 3. "
            "Write a Pattern first and promote once corroborated.",
        )
        for field in ("scope", "rule", "why", "example"):
            _require(
                isinstance(e.get(field), str) and e[field].strip(), f"Convention.{field} required"
            )


def _natural_key(e: dict[str, Any]) -> str:
    """Compute the natural key per LCN-SCHEMA.md §Natural keys."""
    t = e["entity_type"]
    mid = e.get("mission_id") or ""
    if t == "Decision":
        return f"{mid}|{hash12(e['chosen_approach'])}|{file_paths_hash(e['file_paths'])}"
    if t == "Rejection":
        return f"{mid}|{hash12(e['approach'])}"
    if t == "Error":
        return f"{mid}|{e['failure_class']}|{file_paths_hash(e['file_paths'])}"
    if t == "Pattern":
        return f"{hash12(e['shape_description'])}|{hash12(e['scope'])}"
    if t == "Convention":
        # scope kept raw for later prefix/wildcard matching in reads
        return f"{e['scope']}|{hash12(e['rule'])}"
    raise ValidationError(f"Unknown entity_type: {t}")


# ---------------------------------------------------------------------------
# Write (idempotent upsert)
# ---------------------------------------------------------------------------


def write_entity(
    e: dict[str, Any],
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Write an entity idempotently.

    If a row with the same (entity_type, natural_key) exists, update it in
    place (preserving created_at, refreshing updated_at). Otherwise insert.

    Returns the persisted entity dict including id, created_at, updated_at.
    """
    _check_entity(e)
    clean = {k: v for k, v in e.items() if not k.startswith("_")}
    key = _natural_key(clean)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    close_conn = conn is None
    if conn is None:
        conn = get_conn()

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, created_at FROM entities WHERE entity_type = ? AND natural_key = ?",
            (clean["entity_type"], key),
        )
        row = cur.fetchone()
        if row:
            clean["id"] = row["id"]
            clean["created_at"] = row["created_at"]
            clean["updated_at"] = now
            cur.execute(
                "UPDATE entities "
                "SET mission_id = ?, confidence = ?, updated_at = ?, data = ? "
                "WHERE id = ?",
                (
                    clean.get("mission_id"),
                    clean["confidence"],
                    now,
                    json.dumps(clean, ensure_ascii=False, sort_keys=True),
                    clean["id"],
                ),
            )
        else:
            clean["id"] = ulid()
            clean["created_at"] = now
            clean["updated_at"] = now
            cur.execute(
                "INSERT INTO entities "
                "(id, entity_type, natural_key, mission_id, confidence, "
                " created_at, updated_at, data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    clean["id"],
                    clean["entity_type"],
                    key,
                    clean.get("mission_id"),
                    clean["confidence"],
                    now,
                    now,
                    json.dumps(clean, ensure_ascii=False, sort_keys=True),
                ),
            )
        conn.commit()
        return clean
    finally:
        if close_conn:
            conn.close()


def write_many(
    entities: Iterable[dict[str, Any]],
    db_path: Path | str = DEFAULT_DB_PATH,
) -> list[dict[str, Any]]:
    """Write a batch of entities under one connection. Returns the persisted
    list in the same order. Any validation error aborts the batch (no partial
    commits beyond what already succeeded — SQLite per-statement commits)."""
    conn = get_conn(db_path)
    try:
        return [write_entity(e, conn=conn) for e in entities]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Minimal CLI — for dev + seeding
# ---------------------------------------------------------------------------


def _cli_write() -> None:
    """Read a JSON entity from stdin, persist, print the result."""
    e = json.load(sys.stdin)
    out = write_entity(e)
    print(json.dumps(out, indent=2, sort_keys=True))


def _cli_validate() -> None:
    """Read a JSON entity from stdin, validate only. Exit 0 on OK, 1 on invalid."""
    e = json.load(sys.stdin)
    try:
        _check_entity(e)
        _natural_key(e)
        print("OK")
    except ValidationError as ex:
        print(f"INVALID: {ex}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: lcn_write.py <write|validate>", file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "write":
        _cli_write()
    elif cmd == "validate":
        _cli_validate()
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
