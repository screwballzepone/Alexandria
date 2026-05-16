"""memory_stats.py — LCN entity store statistics CLI.

Queries the LCN entity store and prints:
  - Total entities
  - Breakdown by entity_type
  - Most recent N entries of each type

Uses lcn_read.py for queries. All output is JSON. Degrades gracefully
when the LCN database is unavailable.

Usage:
    python memory_stats.py
    python memory_stats.py --db-path /custom/path/lcn_memory.db
    python memory_stats.py --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Import lcn_read — gracefully degrade if unavailable
# ---------------------------------------------------------------------------

_READ_AVAILABLE = False
_read_module: Any = None

try:
    import lcn_read as _read_module

    _READ_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_PATH_HELP = (
    "Override LCN database path"
    " (default: ~/.local/share/opencode/lcn_memory.db)"
)

ENTITY_TYPES = {"Decision", "Rejection", "Error", "Pattern", "Convention"}


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def compute_stats(db_path: str | None, limit: int) -> dict[str, Any]:
    """Gather entity store statistics.

    Returns a dict with ``status``, ``total_entities``, ``by_type``
    breakdown, and ``recent`` entries per type.  Degrades to
    ``{"status": "degraded", ...}`` when the DB is unreachable.
    """
    if not _READ_AVAILABLE:
        return {"status": "degraded", "reason": "lcn_read module not available"}

    conn = _read_module._get_conn(db_path)
    if conn is None:
        return {
            "status": "degraded",
            "reason": "LCN database not found or unreadable",
            "db_path": str(_read_module._db_path(db_path)),
        }

    try:
        cur = conn.cursor()

        # Total entity count
        cur.execute("SELECT COUNT(*) FROM entities")
        total = cur.fetchone()[0]

        # Breakdown by entity_type
        cur.execute(
            "SELECT entity_type, COUNT(*) FROM entities "
            "GROUP BY entity_type ORDER BY COUNT(*) DESC"
        )
        breakdown = {row[0]: row[1] for row in cur.fetchall()}

        # Most recent of each known type
        recent: dict[str, list[dict[str, Any]]] = {}
        for etype in sorted(ENTITY_TYPES):
            entries = _read_module.query_recent_by_type(
                entity_type=etype,
                limit=limit,
                db_path=db_path,
            )
            recent[etype] = [_summarize_entity(e) for e in entries]

        return {
            "status": "ok",
            "total_entities": total,
            "by_type": breakdown,
            "recent": recent,
            "db_path": str(_read_module._db_path(db_path)),
        }

    finally:
        conn.close()


def _summarize_entity(ent: dict[str, Any]) -> dict[str, Any]:
    """Return a compact summary of an entity for CLI output."""
    data = ent.get("data", {})
    etype = ent.get("entity_type", "")
    summary: dict[str, Any] = {
        "id": ent.get("id", ""),
        "entity_type": etype,
        "confidence": ent.get("confidence"),
        "created_at": ent.get("created_at"),
        "natural_key": ent.get("natural_key", ""),
    }

    if etype == "Decision":
        summary["chosen_approach"] = data.get("chosen_approach", "")
        summary["outcome"] = data.get("outcome", "")
    elif etype == "Rejection":
        summary["approach"] = data.get("approach", "")
        summary["reason"] = data.get("reason", "")
    elif etype == "Error":
        summary["failure_class"] = data.get("failure_class", "")
        summary["symptom"] = data.get("symptom", "")
    elif etype == "Pattern":
        summary["shape_description"] = data.get("shape_description", "")
        summary["scope"] = data.get("scope", "")
    elif etype == "Convention":
        summary["rule"] = data.get("rule", "")
        summary["scope"] = data.get("scope", "")

    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LCN entity store statistics — totals, breakdown, recent entries",
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help=DB_PATH_HELP,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Number of most recent entries to show per type (default: 3)",
    )

    args = parser.parse_args()

    try:
        stats = compute_stats(db_path=args.db_path, limit=args.limit)
        print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))
    except Exception as exc:
        print(
            json.dumps(
                {"status": "degraded", "reason": str(exc)},
                indent=2,
            ),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
