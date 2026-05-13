#!/usr/bin/env python3
"""seed_lcn.py — populate .lcn/lcn.sqlite from MagnumOpus/seeds/*.jsonl.

Idempotent: writes go through lcn_write.write_many, which upserts on the
natural key per LCN-SCHEMA.md. Re-running the script does not duplicate
rows — it just no-ops on entities already present.

Usage:
    python MagnumOpus/scripts/seed_lcn.py

The script:
  1. Locates the project root (looks for .opencode/tools/lcn_write.py)
  2. Loads MagnumOpus/seeds/conventions.jsonl + seeds/errors.jsonl
  3. Writes both files via write_many to .lcn/lcn.sqlite
  4. Prints an entity_type count summary so you can eyeball the result

Exit code 0 on success. Non-zero with stderr trace on any failure.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path


def _find_project_root() -> Path:
    """Walk up from this script until we find .opencode/tools/lcn_write.py."""
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / ".opencode" / "tools" / "lcn_write.py").exists():
            return parent
    raise RuntimeError(
        f"Could not find project root (no .opencode/tools/lcn_write.py up from {here})"
    )


def _load_lcn_write(root: Path):
    """Load .opencode/tools/lcn_write.py as the canonical lcn_write module."""
    path = root / ".opencode" / "tools" / "lcn_write.py"
    spec = importlib.util.spec_from_file_location("lcn_write", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["lcn_write"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    root = _find_project_root()
    lcn = _load_lcn_write(root)
    db_path = root / ".lcn" / "lcn.sqlite"

    seeds_dir = root / "MagnumOpus" / "seeds"
    files = [
        seeds_dir / "conventions.jsonl",
        seeds_dir / "errors.jsonl",
    ]
    for f in files:
        if not f.exists():
            print(f"ERROR: missing seed file {f}", file=sys.stderr)
            return 1

    total_written = 0
    for f in files:
        entities = _load_jsonl(f)
        print(f"Loading {f.name}: {len(entities)} entities")
        out = lcn.write_many(entities, db_path=db_path)
        total_written += len(out)

    # Verification query — print actual row counts by entity_type
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT entity_type, COUNT(*) AS n FROM entities GROUP BY entity_type ORDER BY entity_type"
        ).fetchall()
    finally:
        conn.close()

    print()
    print(f"DB:  {db_path}")
    print(f"Wrote {total_written} entities (idempotent — replays are no-ops)")
    print()
    print("Entity counts in .lcn/lcn.sqlite:")
    for entity_type, n in rows:
        print(f"  {entity_type:12s} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
