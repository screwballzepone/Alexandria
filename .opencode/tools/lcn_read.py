"""lcn_read.py — LCN entity read module (stdlib only).

Read-side companion to lcn_write.py. Queries the entity store for past
decisions, errors, patterns, and conventions.

All functions return empty results (never raise) when DB doesn't exist
or on data integrity issues — graceful degradation for non-LCN projects.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Configuration — same path as deployed lcn_write.py uses
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "opencode" / "lcn_memory.db"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _db_path(db_path: str | Path | None = None) -> Path:
    return Path(db_path) if db_path else DEFAULT_DB_PATH


def _get_conn(db_path: str | Path | None = None) -> sqlite3.Connection | None:
    """Return a connection or None if DB file doesn't exist / unreadable."""
    path = _db_path(db_path)
    if not path.exists():
        return None
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error:
        return None


def _rows_to_list(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert sqlite3.Row rows to dicts, parsing the JSON data column."""
    results: list[dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        try:
            d["data"] = json.loads(d["data"])
        except (json.JSONDecodeError, TypeError, KeyError):
            d["data"] = {}
        results.append(d)
    return results


# ---------------------------------------------------------------------------
# Public query API
# ---------------------------------------------------------------------------


def query_similar_decisions(
    workspace_path: str,
    context_keywords: str,
    limit: int = 5,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Query for past decisions relevant to a task.

    Returns decisions whose ``workspace_path`` (if recorded) matches the
    given path, and whose data payload contains any of the keywords.
    Results are scored by keyword-match count and sorted by relevance then
    recency.

    Parameters
    ----------
    workspace_path:
        Project workspace path used to scope results. Entities without a
        recorded workspace_path are included (they predate the field).
    context_keywords:
        Space-separated keywords to rank relevance against.
    limit:
        Maximum number of results to return (default 5).
    db_path:
        Override default DB location (for testing).
    """
    conn = _get_conn(db_path)
    if conn is None:
        return []

    try:
        cur = conn.cursor()
        # Fetch a bit extra so we can filter in Python without risking
        # single-digit results after workspace filtering.
        cur.execute(
            "SELECT * FROM entities WHERE LOWER(entity_type) = LOWER(?) "
            "ORDER BY created_at DESC LIMIT ?",
            ("Decision", limit * 10),
        )
        rows = cur.fetchall()
        candidates = _rows_to_list(rows)

        keywords = context_keywords.lower().split() if context_keywords else []
        filtered: list[dict[str, Any]] = []

        for ent in candidates:
            data = ent.get("data", {})

            # Workspace filter — if the entity has an explicit workspace_path
            # it must match; entities without the field pass through.
            ent_ws = data.get("workspace_path", "")
            if ent_ws and workspace_path:
                # Normalize separators for comparison
                norm_ent = ent_ws.replace("\\", "/").rstrip("/")
                norm_req = workspace_path.replace("\\", "/").rstrip("/")
                if norm_ent != norm_req:
                    # Also allow if any file_path is under workspace_path
                    fps = data.get("file_paths", [])
                    if not any(
                        fp.replace("\\", "/").startswith(norm_req + "/")
                        for fp in fps
                    ):
                        continue

            # Relevance scoring
            if keywords:
                text = json.dumps(data).lower()
                score = sum(1 for kw in keywords if kw in text)
                if score == 0:
                    continue  # skip irrelevant
                ent["_relevance_score"] = score
            else:
                ent["_relevance_score"] = 0

            filtered.append(ent)

        # Sort by relevance desc, then created_at desc as tiebreaker
        filtered.sort(
            key=lambda r: (
                r.get("_relevance_score", 0),
                r.get("created_at", "") or "",
            ),
            reverse=True,
        )
        return filtered[:limit]

    finally:
        conn.close()


def query_related_errors(
    agent_or_tool: str | None = None,
    error_type: str | None = None,
    limit: int = 5,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Query for errors matching agent/tool name or failure class.

    Used pre-dispatch to surface known pitfalls for a specific agent
    or error category.

    Parameters
    ----------
    agent_or_tool:
        Substring to search for in Error ``symptom`` / ``root_cause`` /
        ``fix_applied`` fields.
    error_type:
        Exact (case-insensitive) ``failure_class`` value to match.
    limit:
        Maximum results (default 5).
    db_path:
        Override default DB location (for testing).
    """
    conn = _get_conn(db_path)
    if conn is None:
        return []

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM entities WHERE LOWER(entity_type) = LOWER(?) "
            "ORDER BY created_at DESC",
            ("Error",),
        )
        rows = cur.fetchall()
        candidates = _rows_to_list(rows)

        results: list[dict[str, Any]] = []
        for ent in candidates:
            data = ent.get("data", {})

            # Error type filter
            if error_type:
                fc = data.get("failure_class", "")
                if fc.lower() != error_type.lower():
                    continue

            # Agent/tool text search
            if agent_or_tool:
                search_text = " ".join(
                    data.get(f, "")
                    for f in ("symptom", "root_cause", "fix_applied")
                ).lower()
                if agent_or_tool.lower() not in search_text:
                    continue

            results.append(ent)
            if len(results) >= limit:
                break

        return results

    finally:
        conn.close()


def query_applicable_conventions(
    scope: str,
    limit: int = 5,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Query for conventions applicable to a given *scope*.

    Matching rules (in priority order):
    1. Global convention (``scope == "*"``).
    2. Exact scope match.
    3. Directory prefix match — *scope* starts with the convention's scope
       followed by ``/``.

    Parameters
    ----------
    scope:
        File path, directory path, or ``"*"`` to fetch all globals.
    limit:
        Maximum results (default 5).
    db_path:
        Override default DB location (for testing).
    """
    conn = _get_conn(db_path)
    if conn is None:
        return []

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM entities WHERE LOWER(entity_type) = LOWER(?) "
            "ORDER BY confidence DESC, created_at DESC",
            ("Convention",),
        )
        rows = cur.fetchall()
        candidates = _rows_to_list(rows)

        matched: list[dict[str, Any]] = []
        for ent in candidates:
            data = ent.get("data", {})
            conv_scope = data.get("scope", "")

            # Global always applies
            if conv_scope == "*":
                matched.append(ent)
                continue

            # Exact match
            if conv_scope and conv_scope == scope:
                matched.append(ent)
                continue

            # Directory prefix match
            if conv_scope and scope:
                prefix = conv_scope.rstrip("/\\") + "/"
                norm_scope = scope.replace("\\", "/")
                norm_prefix = prefix.replace("\\", "/")
                if norm_scope.startswith(norm_prefix):
                    matched.append(ent)
                    continue

            if len(matched) >= limit:
                break

        return matched[:limit]

    finally:
        conn.close()


def query_entity_by_key(
    natural_key: str,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Direct lookup by natural key.

    Returns the entity dict or *None* if not found.
    """
    conn = _get_conn(db_path)
    if conn is None:
        return None

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM entities WHERE natural_key = ? LIMIT 1",
            (natural_key,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return _rows_to_list([row])[0]
    finally:
        conn.close()


def query_recent_by_type(
    entity_type: str,
    limit: int = 10,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Most recent entities of a given type.

    Case-insensitive on *entity_type*.
    """
    conn = _get_conn(db_path)
    if conn is None:
        return []

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM entities WHERE LOWER(entity_type) = LOWER(?) "
            "ORDER BY created_at DESC LIMIT ?",
            (entity_type, limit),
        )
        return _rows_to_list(cur.fetchall())
    finally:
        conn.close()
