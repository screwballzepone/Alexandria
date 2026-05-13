#!/usr/bin/env python3
"""
CogitoCode Mission Log — session-wide objective management.

CLI commands:
  show                  — print current mission
  propose <text>        — stage a new mission proposal
  accept                — move proposal → current, archive old current
  reject                — clear proposal
  complete              — archive current mission as completed

State file: state/mission.json (relative to this script)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


STATE_DIR = Path(__file__).resolve().parent / "state"
STATE_FILE = STATE_DIR / "mission.json"


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict:
    """Return a fresh mission state dictionary."""
    return {
        "current": None,
        "proposal": None,
        "history": [],
        "updated": _now_iso(),
    }


def _load() -> dict:
    """Read mission.json; return default if missing or corrupt."""
    if not STATE_FILE.exists():
        return _default_state()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        # Ensure all keys exist
        for key in ("current", "proposal", "history", "updated"):
            data.setdefault(key, None if key != "history" else [])
        return data
    except (json.JSONDecodeError, OSError):
        return _default_state()


def _save(state: dict):
    """Write mission.json with 2-space indent."""
    state["updated"] = _now_iso()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def cmd_show(args):
    """Print current mission to stdout."""
    state = _load()
    if state.get("current"):
        print(f"[MISSION] {state['current']}")
    if state.get("proposal"):
        print(f"[PROPOSAL] {state['proposal']}")
    if not state.get("current") and not state.get("proposal"):
        print("[MISSION] No mission set.")
    # Final JSON line for machine parsing
    print(json.dumps(state))


def cmd_propose(args):
    """Stage a new mission proposal."""
    text = " ".join(args.text)
    state = _load()
    state["proposal"] = text
    _save(state)
    print("Proposal staged. Awaiting user approval.")
    print(json.dumps({"action": "proposed", "proposal": text}))


def cmd_accept(args):
    """Move proposal → current, archive old current."""
    state = _load()
    if not state.get("proposal"):
        print("No proposal to accept.")
        print(json.dumps({"action": "accept", "result": "no_proposal"}))
        return

    now = _now_iso()
    # Archive old current
    old_current = state.get("current")
    if old_current:
        state.setdefault("history", []).append({
            "description": old_current,
            "started": state.get("updated", now),
            "completed": now,
        })

    state["current"] = state["proposal"]
    state["proposal"] = None
    _save(state)
    print("Mission updated.")
    print(json.dumps({"action": "accept", "current": state["current"]}))


def cmd_reject(args):
    """Clear proposal."""
    state = _load()
    if not state.get("proposal"):
        print("No proposal to reject.")
    else:
        state["proposal"] = None
        _save(state)
        print("Proposal rejected.")
    print(json.dumps({"action": "reject", "result": "ok"}))


def cmd_complete(args):
    """Archive current mission as completed, set current to null."""
    state = _load()
    if not state.get("current"):
        print("No current mission to complete.")
        print(json.dumps({"action": "complete", "result": "no_current"}))
        return

    now = _now_iso()
    state.setdefault("history", []).append({
        "description": state["current"],
        "started": state.get("updated", now),
        "completed": now,
    })
    state["current"] = None
    _save(state)
    print("Mission completed.")
    print(json.dumps({"action": "complete", "result": "ok"}))


def main(argv=None):
    # Fix UnicodeEncodeError on Windows
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="CogitoCode Mission Log — session-wide objective management.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_show = sub.add_parser("show", help="Show current mission")

    p_propose = sub.add_parser("propose", help="Stage a new mission proposal")
    p_propose.add_argument("text", nargs="+", help="Proposal text")

    p_accept = sub.add_parser("accept", help="Accept current proposal")

    p_reject = sub.add_parser("reject", help="Reject current proposal")

    p_complete = sub.add_parser("complete", help="Mark current mission complete")

    parsed = parser.parse_args(argv)

    dispatch = {
        "show": cmd_show,
        "propose": cmd_propose,
        "accept": cmd_accept,
        "reject": cmd_reject,
        "complete": cmd_complete,
    }
    dispatch[parsed.command](parsed)


if __name__ == "__main__":
    main()
