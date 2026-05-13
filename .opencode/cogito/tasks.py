#!/usr/bin/env python3
"""
CogitoCode Tasks — per-response task list management.

CLI commands:
  init <desc1> <desc2> ...  — clear and create new task list
  done <id>                 — mark task completed, advance next
  add <description>         — append new task
  remove <id>               — delete a task
  list                      — print formatted task list
  clear                     — empty task list

State file: state/tasks.json (relative to this script)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


STATE_DIR = Path(__file__).resolve().parent / "state"
STATE_FILE = STATE_DIR / "tasks.json"


STATUS_ICONS = {
    "pending": "\u2b1c",     # ⬜
    "in_progress": "\u26a1",  # ⚡
    "completed": "\u2705",    # ✅
    "cancelled": "\u274c",    # ❌
}


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict:
    """Return a fresh tasks state."""
    return {"tasks": [], "updated": _now_iso()}


def _load() -> dict:
    """Read tasks.json; return default if missing or corrupt."""
    if not STATE_FILE.exists():
        return _default_state()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        data.setdefault("tasks", [])
        return data
    except (json.JSONDecodeError, OSError):
        return _default_state()


def _save(state: dict):
    """Write tasks.json with 2-space indent."""
    state["updated"] = _now_iso()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _reindex(state: dict):
    """Reassign sequential IDs after removal."""
    for i, task in enumerate(state["tasks"], start=1):
        task["id"] = str(i)


def _print_list(state: dict):
    """Print formatted task list with status icons."""
    tasks = state.get("tasks", [])
    if not tasks:
        print("No tasks.")
        return

    counts = {"pending": 0, "in_progress": 0, "completed": 0, "cancelled": 0}
    for task in tasks:
        status = task.get("status", "pending")
        icon = STATUS_ICONS.get(status, "\u2b1c")
        print(f"[{task['id']}] {icon} {task['description']}")
        counts[status] = counts.get(status, 0) + 1

    total = len(tasks)
    done = counts["completed"]
    in_prog = counts["in_progress"]
    pending = counts["pending"]
    cancelled = counts["cancelled"]

    parts = [f"{total} tasks"]
    if done:
        parts.append(f"{done} done")
    if in_prog:
        parts.append(f"{in_prog} in progress")
    if pending:
        parts.append(f"{pending} pending")
    if cancelled:
        parts.append(f"{cancelled} cancelled")

    print(f"  {', '.join(parts)}")


def cmd_init(args):
    """Clear existing tasks, create new list from descriptions."""
    state = _load()
    state["tasks"] = []
    for i, desc in enumerate(args.descriptions):
        state["tasks"].append({
            "id": str(i + 1),
            "description": desc,
            "status": "in_progress" if i == 0 else "pending",
        })
    _save(state)
    _print_list(state)
    print(json.dumps({"action": "init", "count": len(args.descriptions)}))


def cmd_done(args):
    """Mark a task completed. Auto-advance next pending to in_progress."""
    state = _load()
    tasks = state.get("tasks", [])
    task_id = args.id

    # Find the task by id
    target = None
    target_idx = None
    for i, task in enumerate(tasks):
        if task["id"] == task_id:
            target = task
            target_idx = i
            break

    if target is None:
        print(f"Task {task_id} not found.")
        print(json.dumps({"action": "done", "result": "not_found", "id": task_id}))
        return

    if target["status"] == "completed":
        print(f"Task {task_id} already completed.")
        print(json.dumps({"action": "done", "result": "already_done", "id": task_id}))
        return

    target["status"] = "completed"

    # Auto-advance: find the next pending task and set to in_progress
    for i in range(target_idx + 1, len(tasks)):
        if tasks[i]["status"] == "pending":
            tasks[i]["status"] = "in_progress"
            break

    _save(state)

    remaining = sum(1 for t in tasks if t["status"] not in ("completed", "cancelled"))
    print(f"\u2713 Task {task_id} done. {remaining} remaining.")

    _print_list(state)
    print(json.dumps({"action": "done", "id": task_id, "remaining": remaining}))


def cmd_add(args):
    """Append a new pending task."""
    state = _load()
    tasks = state.get("tasks", [])
    next_id = str(max((int(t["id"]) for t in tasks), default=0) + 1)
    tasks.append({
        "id": next_id,
        "description": args.description,
        "status": "pending",
    })
    _save(state)
    _print_list(state)
    print(json.dumps({"action": "add", "id": next_id}))


def cmd_remove(args):
    """Remove a task and re-index."""
    state = _load()
    tasks = state.get("tasks", [])
    task_id = args.id

    before = len(tasks)
    state["tasks"] = [t for t in tasks if t["id"] != task_id]
    removed = before - len(state["tasks"])

    if removed:
        _reindex(state)
        _save(state)
    _print_list(state)
    print(json.dumps({"action": "remove", "removed": removed}))


def cmd_list(args):
    """Print formatted task list."""
    state = _load()
    _print_list(state)
    print(json.dumps(state))


def cmd_clear(args):
    """Empty task list."""
    state = _load()
    state["tasks"] = []
    _save(state)
    print("Tasks cleared.")
    print(json.dumps({"action": "clear"}))


def main(argv=None):
    # Fix UnicodeEncodeError on Windows
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="CogitoCode Tasks — per-response task list management.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Clear and create new task list")
    p_init.add_argument("descriptions", nargs="+", help="Task descriptions")

    p_done = sub.add_parser("done", help="Mark task completed")
    p_done.add_argument("id", help="Task ID to mark done")

    p_add = sub.add_parser("add", help="Append a new pending task")
    p_add.add_argument("description", help="Task description")

    p_remove = sub.add_parser("remove", help="Remove a task")
    p_remove.add_argument("id", help="Task ID to remove")

    p_list = sub.add_parser("list", help="Show task list")

    p_clear = sub.add_parser("clear", help="Empty task list")

    parsed = parser.parse_args(argv)

    dispatch = {
        "init": cmd_init,
        "done": cmd_done,
        "add": cmd_add,
        "remove": cmd_remove,
        "list": cmd_list,
        "clear": cmd_clear,
    }
    dispatch[parsed.command](parsed)


if __name__ == "__main__":
    main()
