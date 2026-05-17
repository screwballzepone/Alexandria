"""consult.py — LCN consultation CLI for the orchestrator.

Called before planning, dispatching, and after feature completion to inject
LCN wisdom into agent decisions.

Usage:
    python consult.py pre_plan "<task description>"
    python consult.py pre_dispatch "<agent_name>" "<model_name>"
    python consult.py post_verify "<feature_name>" "<file_list>"

Output: Always valid JSON on stdout, errors on stderr. Exits 0 even when
the LCN database is unavailable (returns ``{"status": "degraded"}``).
"""

from __future__ import annotations

import argparse
import json
import os
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
# Helpers
# ---------------------------------------------------------------------------


def _degraded(reason: str) -> str:
    return json.dumps(
        {"results": [], "status": "degraded", "reason": reason},
        indent=2,
    )


def _ok(data: Any) -> str:
    return json.dumps(
        {"results": data, "status": "ok"},
        indent=2,
        ensure_ascii=False,
        default=str,
    )


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------


def cmd_pre_plan(task_description: str, db_path: str | None = None, cross: bool = False) -> str:
    """Query past decisions + global conventions for planning context."""
    if not _READ_AVAILABLE:
        return _degraded("lcn_read module not available")

    # Derive workspace from CWD or task hint (simple heuristic)
    workspace = str(Path.cwd())

    decisions = _read_module.query_similar_decisions(
        workspace_path=workspace,
        context_keywords=task_description,
        limit=5,
        db_path=db_path,
        cross_workspace=cross,
    )
    conventions = _read_module.query_applicable_conventions(
        scope="*",
        limit=5,
        db_path=db_path,
        cross_workspace=cross,
    )
    recent_patterns = _read_module.query_recent_by_type(
        entity_type="Pattern",
        limit=3,
        db_path=db_path,
        cross_workspace=cross,
    )

    return _ok(
        {
            "task_description": task_description,
            "workspace_path": workspace,
            "similar_decisions": [
                _summarize_entity(d) for d in decisions
            ],
            "applicable_conventions": [
                _summarize_entity(c) for c in conventions
            ],
            "recent_patterns": [
                _summarize_entity(p) for p in recent_patterns
            ],
        }
    )


def cmd_pre_dispatch(agent_name: str, model_name: str, db_path: str | None = None, cross: bool = False) -> str:
    """Query known errors for this agent + agent-scoped conventions."""
    if not _READ_AVAILABLE:
        return _degraded("lcn_read module not available")

    errors = _read_module.query_related_errors(
        agent_or_tool=agent_name,
        limit=5,
        db_path=db_path,
        cross_workspace=cross,
    )
    # Conventions scoped to the agent directory
    agent_scope = f".opencode/agent/{agent_name}"
    agent_conventions = _read_module.query_applicable_conventions(
        scope=agent_scope,
        limit=5,
        db_path=db_path,
        cross_workspace=cross,
    )

    return _ok(
        {
            "agent": agent_name,
            "model": model_name,
            "known_pitfalls": [_summarize_entity(e) for e in errors],
            "agent_conventions": [
                _summarize_entity(c) for c in agent_conventions
            ],
        }
    )


def cmd_post_verify(feature_name: str, file_list: str, db_path: str | None = None, cross: bool = False) -> str:
    """Check if changed files contradict any stored decisions or conventions."""
    if not _READ_AVAILABLE:
        return _degraded("lcn_read module not available")

    files = [f.strip() for f in file_list.split(",") if f.strip()]

    # Collect conventions applicable to each file's directory
    relevant_conventions: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for fp in files:
        path = Path(fp)
        # Check the file itself and each parent directory up to root
        parts = list(path.parts)
        for i in range(len(parts), 0, -1):
            scope = str(Path(*parts[:i])) if i > 1 else "."
            convs = _read_module.query_applicable_conventions(
                scope=scope,
                limit=10,
                db_path=db_path,
                cross_workspace=cross,
            )
            for c in convs:
                nk = c.get("natural_key", "")
                if nk not in seen_keys:
                    seen_keys.add(nk)
                    relevant_conventions.append(_summarize_entity(c))

    # Check if any decision's file_paths overlap with changed files
    workspace = str(Path.cwd())
    all_decisions = _read_module.query_similar_decisions(
        workspace_path=workspace,
        context_keywords=feature_name,
        limit=20,
        db_path=db_path,
        cross_workspace=cross,
    )
    potentially_contradicted = []
    for dec in all_decisions:
        data = dec.get("data", {})
        dec_files = data.get("file_paths", [])
        overlap = [f for f in files if f in dec_files]
        if overlap:
            potentially_contradicted.append(
                {
                    "decision": _summarize_entity(dec),
                    "overlapping_files": overlap,
                }
            )

    return _ok(
        {
            "feature": feature_name,
            "changed_files": files,
            "applicable_conventions": relevant_conventions,
            "potentially_contradicted_decisions": potentially_contradicted,
        }
    )


# ---------------------------------------------------------------------------
# Summariser — strip verbose fields for CLI output
# ---------------------------------------------------------------------------


def _summarize_entity(ent: dict[str, Any]) -> dict[str, Any]:
    """Return a compact summary of an entity for JSON output."""
    data = ent.get("data", {})
    etype = ent.get("entity_type", "")
    summary: dict[str, Any] = {
        "natural_key": ent.get("natural_key", ""),
        "entity_type": etype,
        "confidence": ent.get("confidence"),
        "created_at": ent.get("created_at"),
    }

    if etype == "Decision":
        summary["chosen_approach"] = data.get("chosen_approach", "")
        summary["outcome"] = data.get("outcome", "")
        summary["rationale"] = data.get("rationale", "")
    elif etype == "Error":
        summary["failure_class"] = data.get("failure_class", "")
        summary["symptom"] = data.get("symptom", "")
        summary["root_cause"] = data.get("root_cause", "")
    elif etype == "Pattern":
        summary["shape_description"] = data.get("shape_description", "")
        summary["when_to_use"] = data.get("when_to_use", "")
        summary["scope"] = data.get("scope", "")
    elif etype == "Convention":
        summary["scope"] = data.get("scope", "")
        summary["rule"] = data.get("rule", "")
        summary["why"] = data.get("why", "")
    elif etype == "Rejection":
        summary["approach"] = data.get("approach", "")
        summary["reason"] = data.get("reason", "")

    return summary


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    # Kill switch — set JANUS_CONSULT_DISABLED=1 to bypass LCN injection
    if os.environ.get("JANUS_CONSULT_DISABLED", "").lower() in ("1", "true", "yes"):
        print(_degraded("Consult disabled via JANUS_CONSULT_DISABLED"))
        return

    parser = argparse.ArgumentParser(
        description="LCN consultation tool — query entity store for agent decisions",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    _DB_PATH_HELP = (
        "Override LCN database path"
        " (default: ~/.local/share/opencode/lcn_memory.db)"
    )

    # pre_plan
    p1 = sub.add_parser("pre_plan", help="Query past decisions + conventions for planning")
    p1.add_argument("task_description", help="Natural-language task description")
    p1.add_argument("--db-path", help=_DB_PATH_HELP)
    p1.add_argument(
        "--cross",
        action="store_true",
        help="Query across all workspaces (default: current only)",
    )

    # pre_dispatch
    p2 = sub.add_parser("pre_dispatch", help="Query known pitfalls for an agent before dispatch")
    p2.add_argument("agent_name", help="Agent name (e.g. 'coder', 'explorer')")
    p2.add_argument("model_name", help="Model name (e.g. 'deepseek-v4-flash')")
    p2.add_argument("--db-path", help=_DB_PATH_HELP)
    p2.add_argument(
        "--cross",
        action="store_true",
        help="Query across all workspaces (default: current only)",
    )

    # post_verify
    p3 = sub.add_parser("post_verify", help="Check if changed files contradict known decisions")
    p3.add_argument("feature_name", help="Name of the feature just implemented")
    p3.add_argument(
        "file_list",
        help="Comma-separated list of changed file paths",
    )
    p3.add_argument("--db-path", help=_DB_PATH_HELP)
    p3.add_argument(
        "--cross",
        action="store_true",
        help="Query across all workspaces (default: current only)",
    )

    args = parser.parse_args()

    try:
        db_path = args.db_path
        cross = getattr(args, "cross", False)
        if args.command == "pre_plan":
            output = cmd_pre_plan(args.task_description, db_path=db_path, cross=cross)
        elif args.command == "pre_dispatch":
            output = cmd_pre_dispatch(args.agent_name, args.model_name, db_path=db_path, cross=cross)
        elif args.command == "post_verify":
            output = cmd_post_verify(args.feature_name, args.file_list, db_path=db_path, cross=cross)
        else:
            output = _degraded(f"Unknown command: {args.command}")

        print(output)

    except Exception as exc:
        # Catch-all: degraded output, never hard-fail
        print(
            _degraded(f"Consultation error: {exc}"),
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
