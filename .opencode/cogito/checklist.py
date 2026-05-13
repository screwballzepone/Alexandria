#!/usr/bin/env python3
"""
CogitoCode Checklist — template-driven verification step management.

CLI commands:
  generate --objective <name> --context "<text>"  — load template, fill checklist
  show                                             — print current checklist
  check <id>                                       — mark item passed
  skip <id> --reason "<text>"                      — mark item skipped
  clear                                            — reset checklist to empty

State file: state/checklist.json (relative to this script)
Templates:  templates/<name>.json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / "state"
STATE_FILE = STATE_DIR / "checklist.json"
TEMPLATES_DIR = BASE_DIR / "templates"


STATUS_ICONS = {
    "pending": "\u2b1c",     # ⬜
    "passed": "\u2705",       # ✅
    "skipped": "\u23ed\ufe0f",  # ⏭️
}


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> dict:
    """Return a fresh checklist state."""
    return {
        "objective": None,
        "context": None,
        "items": [],
        "updated": _now_iso(),
    }


def _load() -> dict:
    """Read checklist.json; return default if missing or corrupt."""
    if not STATE_FILE.exists():
        return _default_state()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        data.setdefault("objective", None)
        data.setdefault("context", None)
        data.setdefault("items", [])
        return data
    except (json.JSONDecodeError, OSError):
        return _default_state()


def _save(state: dict):
    """Write checklist.json with 2-space indent."""
    state["updated"] = _now_iso()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _print_checklist(state: dict):
    """Print current checklist with status icons."""
    items = state.get("items", [])
    objective = state.get("objective")
    context = state.get("context")

    if objective:
        print(f"Objective: {objective}")
    if context:
        print(f"Context: {context}")

    if not items:
        print("No checklist items.")
        return

    total = len(items)
    passed = 0
    skipped = 0
    pending = 0

    for item in items:
        status = item.get("status", "pending")
        icon = STATUS_ICONS.get(status, "\u2b1c")
        mandatory_mark = " *" if item.get("mandatory", False) else "  "
        skip_reason = item.get("skip_reason")
        if status == "passed":
            passed += 1
        elif status == "skipped":
            skipped += 1
            reason_text = f"  \u23ed\ufe0f Reason: {skip_reason}" if skip_reason else ""
        else:
            pending += 1

        print(f"  [{item.get('id', '?')}] {icon}{mandatory_mark} {item.get('description', '')}")

    # Print skip reasons after list
    for item in items:
        if item.get("status") == "skipped" and item.get("skip_reason"):
            print(f"  \u23ed\ufe0f [{item['id']}] {item['skip_reason']}")

    print(f"  {passed}/{total} items verified ({pending} pending, {skipped} skipped)."
          if pending or skipped else
          f"  {passed}/{total} items verified.")


def cmd_generate(args):
    """Load template, populate checklist, write state."""
    template_name = args.objective
    context_text = args.context
    template_path = TEMPLATES_DIR / f"{template_name}.json"

    if not template_path.exists():
        print(f"Template '{template_name}' not found at {template_path}.")
        print(f"Available templates: {', '.join(sorted(p.stem for p in TEMPLATES_DIR.glob('*.json')))}")
        print(json.dumps({"action": "generate", "result": "template_not_found",
                          "template": template_name}))
        return

    try:
        template = json.loads(template_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error loading template: {e}")
        print(json.dumps({"action": "generate", "result": "error", "error": str(e)}))
        return

    # Build items from template, set all to pending
    items = []
    for tpl_item in template.get("items", []):
        items.append({
            "id": tpl_item["id"],
            "description": tpl_item["description"],
            "status": "pending",
            "mandatory": tpl_item.get("mandatory", False),
            "skip_reason": None,
        })

    state = _load()
    state["objective"] = template.get("objective", template_name)
    state["context"] = context_text
    state["items"] = items
    _save(state)

    print(f"Checklist generated from '{template_name}' template.")
    _print_checklist(state)
    print(json.dumps({"action": "generate", "objective": state["objective"],
                       "item_count": len(items)}))


def cmd_show(args):
    """Print current checklist."""
    state = _load()
    _print_checklist(state)
    print(json.dumps(state))


def cmd_check(args):
    """Mark item as passed. Report progress."""
    state = _load()
    items = state.get("items", [])
    item_id = args.id

    target = None
    for item in items:
        if item["id"] == item_id:
            target = item
            break

    if target is None:
        print(f"Item {item_id} not found.")
        print(json.dumps({"action": "check", "result": "not_found", "id": item_id}))
        return

    target["status"] = "passed"
    _save(state)

    # Check if all mandatory items are now passed
    mandatory_items = [i for i in items if i.get("mandatory", False)]
    all_mandatory_passed = all(i.get("status") == "passed" for i in mandatory_items)

    passed = sum(1 for i in items if i.get("status") == "passed")
    total = len(items)

    if all_mandatory_passed:
        print("\u2705 All mandatory items completed.")

    print(f"{passed}/{total} items verified.")

    _print_checklist(state)
    print(json.dumps({"action": "check", "id": item_id,
                       "all_mandatory_passed": all_mandatory_passed,
                       "verified": f"{passed}/{total}"}))


def cmd_skip(args):
    """Mark item as skipped with reason."""
    state = _load()
    items = state.get("items", [])
    item_id = args.id
    reason = args.reason

    target = None
    for item in items:
        if item["id"] == item_id:
            target = item
            break

    if target is None:
        print(f"Item {item_id} not found.")
        print(json.dumps({"action": "skip", "result": "not_found", "id": item_id}))
        return

    target["status"] = "skipped"
    target["skip_reason"] = reason
    _save(state)

    print(f"\u23ed\ufe0f Skipped: {reason}")
    _print_checklist(state)
    print(json.dumps({"action": "skip", "id": item_id, "reason": reason}))


def cmd_clear(args):
    """Reset checklist to empty state."""
    state = _default_state()
    _save(state)
    print("Checklist cleared.")
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
        description="CogitoCode Checklist — template-driven verification.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_generate = sub.add_parser("generate", help="Load template and populate checklist")
    p_generate.add_argument("--objective", required=True, help="Template name (file stem)")
    p_generate.add_argument("--context", required=True, help="Context description")

    p_show = sub.add_parser("show", help="Show current checklist")

    p_check = sub.add_parser("check", help="Mark item as passed")
    p_check.add_argument("id", help="Item ID to check")

    p_skip = sub.add_parser("skip", help="Skip an item with reason")
    p_skip.add_argument("id", help="Item ID to skip")
    p_skip.add_argument("--reason", required=True, help="Reason for skipping")

    p_clear = sub.add_parser("clear", help="Reset checklist to empty")

    parsed = parser.parse_args(argv)

    dispatch = {
        "generate": cmd_generate,
        "show": cmd_show,
        "check": cmd_check,
        "skip": cmd_skip,
        "clear": cmd_clear,
    }
    dispatch[parsed.command](parsed)


if __name__ == "__main__":
    main()
