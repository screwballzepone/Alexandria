"""self_improve.py — Phase J Self-Improvement Loop engine.

Validates, applies, and rolls back meta-agent proposals for prompt/routing
improvements. Uses git stash for rollback safety.

Usage:
    python self_improve.py validate < proposal.json
    python self_improve.py apply < proposal.json
    python self_improve.py apply --proposal-file <path.json>
    python self_improve.py rollback [proposal_id]
    python self_improve.py status

Kill switches (env vars, checked per-operation):
    JANUS_SELF_IMPROVE_DISABLED=true  — master kill switch, exits 0 immediately
    JANUS_AUTO_APPLY_DISABLED=true    — validate only, never apply
    Both unset → DISABLED=true (safe default)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KILL_DISABLED = "JANUS_SELF_IMPROVE_DISABLED"
KILL_AUTO_APPLY = "JANUS_AUTO_APPLY_DISABLED"

BASE_DIR = Path(__file__).resolve().parent.parent  # .opencode/
PROPOSALS_DIR = BASE_DIR / "meta-agent" / "proposals"
APPLIED_DIR = BASE_DIR / "meta-agent" / "applied"
ROLLBACK_DIR = BASE_DIR / "rollback"
LOG_FILE = BASE_DIR / "meta-agent" / "applied-proposals.log"

REQUIRED_FIELDS = [
    "proposal_id",
    "source",
    "mission_id",
    "target_file",
    "change_type",
    "section",
    "old_text",
    "new_text",
    "confidence",
    "expected_improvement",
    "risk",
]

VALID_CHANGE_TYPES = {"addition", "modification"}
VALID_RISKS = {"low", "medium", "high"}


# ---------------------------------------------------------------------------
# Kill switch helpers
# ---------------------------------------------------------------------------


def is_disabled() -> bool:
    """Return True if master kill switch is set (default when unset)."""
    val = os.environ.get(KILL_DISABLED, "true").strip().lower()
    return val in ("1", "true", "yes")


def is_auto_apply_disabled() -> bool:
    """Return True if auto-apply is disabled (subordinate to master kill)."""
    val = os.environ.get(KILL_AUTO_APPLY, "false").strip().lower()
    return val in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# ID generation (ULID-like, stdlib only)
# ---------------------------------------------------------------------------


def _generate_id() -> str:
    """Generate a timestamp-prefixed hex ID similar to ULID."""
    ts = int(time.time() * 1000)
    rand = random.randint(0, 2**64 - 1)
    raw = f"{ts:012x}{rand:016x}"
    return raw[:26].upper()


# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------


def _ensure_dirs() -> None:
    """Create required directories if they don't exist."""
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    APPLIED_DIR.mkdir(parents=True, exist_ok=True)
    ROLLBACK_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate(proposal: dict[str, Any]) -> bool:
    """Validate proposal structure. Returns True if valid."""
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in proposal:
            errors.append(f"Missing required field: {field}")

    if errors:
        print(json.dumps({"valid": False, "errors": errors}), file=sys.stderr)
        return False

    pid = proposal["proposal_id"]
    if not isinstance(pid, str) or len(pid) < 8:
        errors.append("proposal_id must be a string >= 8 chars")

    if proposal["change_type"] not in VALID_CHANGE_TYPES:
        errors.append(f"change_type must be one of {sorted(VALID_CHANGE_TYPES)}")

    if proposal["risk"] not in VALID_RISKS:
        errors.append(f"risk must be one of {sorted(VALID_RISKS)}")

    conf = proposal["confidence"]
    if not isinstance(conf, (int, float)):
        errors.append("confidence must be a number")
    elif not 0.0 <= conf <= 1.0:
        errors.append("confidence must be between 0.0 and 1.0")

    if not isinstance(proposal["old_text"], str):
        errors.append("old_text must be a string")

    if not isinstance(proposal["new_text"], str):
        errors.append("new_text must be a string")

    if not isinstance(proposal["expected_improvement"], str):
        errors.append("expected_improvement must be a string")

    if errors:
        print(json.dumps({"valid": False, "errors": errors}), file=sys.stderr)
        return False

    print(json.dumps({"valid": True, "proposal_id": pid}))
    return True


# ---------------------------------------------------------------------------
# Section-based text matching
# ---------------------------------------------------------------------------


def _find_section_offsets(
    content: str, section_heading: str
) -> tuple[int, int] | None:
    """Find section by heading in markdown content.

    Returns (start_line, end_line) 0-indexed, or None if not found.
    Matches exact heading text after stripping ``##`` / ``###`` prefix.
    """
    lines = content.splitlines(keepends=True)
    start_idx = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            heading_text = stripped.lstrip("#").strip()
            if heading_text == section_heading:
                start_idx = i
                break

    if start_idx == -1:
        return None

    for i in range(start_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            return (start_idx, i)

    return (start_idx, len(lines))


def _find_text_in_section(
    content: str, section_heading: str, old_text: str
) -> tuple[int, int] | None:
    """Find old_text exactly once within a specific section.

    Returns (global_start_offset, global_end_offset) or None if not
    found or ambiguous (0 or >1 matches).
    """
    section_range = _find_section_offsets(content, section_heading)
    if section_range is None:
        return None

    start_line, end_line = section_range
    lines = content.splitlines(keepends=True)
    section_text = "".join(lines[start_line:end_line])

    count = section_text.count(old_text)
    if count == 0 or count > 1:
        return None

    pre_section_offset = sum(len(lines[i]) for i in range(start_line))
    local_offset = section_text.index(old_text)
    global_start = pre_section_offset + local_offset
    global_end = global_start + len(old_text)
    return (global_start, global_end)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run git command, returning CompletedProcess."""
    cmd = ["git"] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or str(BASE_DIR.parent),
        timeout=30,
    )


def _git_stash_pre_apply() -> bool:
    """Stash working tree for rollback safety. Uses named stash."""
    result = _git("status", "--porcelain")
    if not result.stdout.strip():
        return True
    result = _git("stash", "push", "-m", "self-improve-pre-apply")
    return result.returncode == 0


def _git_stash_pop() -> bool:
    """Pop the most recent stash. Returns True if successful."""
    result = _git("stash", "list")
    if not result.stdout.strip():
        return True
    result = _git("stash", "pop")
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def apply(proposal: dict[str, Any]) -> dict[str, Any]:
    """Apply a validated proposal with git-backed rollback safety.

    Returns dict with status and details. Never raises — always returns
    a result dict.
    """
    _ensure_dirs()

    proposal_id: str = proposal["proposal_id"]
    target_file: str = proposal["target_file"]
    section: str = proposal["section"]
    old_text: str = proposal["old_text"]
    new_text: str = proposal["new_text"]

    target_path = Path(BASE_DIR.parent) / target_file
    if not target_path.exists():
        return {
            "status": "error",
            "error": f"Target file does not exist: {target_file}",
            "proposal_id": proposal_id,
        }

    if not _git_stash_pre_apply():
        return {
            "status": "error",
            "error": "Git stash failed — working tree may be dirty",
            "proposal_id": proposal_id,
        }

    content = target_path.read_text(encoding="utf-8")

    # Capture diff BEFORE any changes
    before_diff = _git("diff", "--", target_file).stdout

    match_range = _find_text_in_section(content, section, old_text)
    if match_range is None:
        _git_stash_pop()
        return {
            "status": "error",
            "error": (
                f"old_text not found exactly once in section '{section}' "
                f"of {target_file}. Either missing or ambiguous."
            ),
            "proposal_id": proposal_id,
            "diff": before_diff,
        }

    start_offset, end_offset = match_range

    new_content = content[:start_offset] + new_text + content[end_offset:]
    try:
        target_path.write_text(new_content, encoding="utf-8")
    except OSError as e:
        _git_stash_pop()
        return {
            "status": "error",
            "error": f"Failed to write {target_file}: {e}",
            "proposal_id": proposal_id,
        }

    after_diff = _git("diff", "--", target_file).stdout

    # Write rollback metadata
    rollback_meta = {
        "proposal_id": proposal_id,
        "target_file": target_file,
        "section": section,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_diff": before_diff,
    }
    (ROLLBACK_DIR / f"{proposal_id}.json").write_text(
        json.dumps(rollback_meta, indent=2), encoding="utf-8"
    )
    (ROLLBACK_DIR / f"{proposal_id}.diff").write_text(
        after_diff, encoding="utf-8"
    )

    # Log to applied-proposals.log (JSONL)
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "proposal_id": proposal_id,
        "target_file": target_file,
        "section": section,
        "change_type": proposal["change_type"],
        "confidence": proposal["confidence"],
        "risk": proposal["risk"],
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

    # Move proposal to applied/
    proposal_src = PROPOSALS_DIR / f"{proposal_id}.json"
    if proposal_src.exists():
        proposal_src.rename(APPLIED_DIR / f"{proposal_id}.json")

    return {
        "status": "applied",
        "proposal_id": proposal_id,
        "target_file": target_file,
        "rollback_file": str(ROLLBACK_DIR / f"{proposal_id}.json"),
    }


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def rollback(proposal_id: str | None = None) -> dict[str, Any]:
    """Rollback a previously applied proposal.

    If proposal_id is None, rolls back the most recent one.
    """
    _ensure_dirs()

    if proposal_id is None:
        rollback_files = sorted(
            ROLLBACK_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not rollback_files:
            return {"status": "error", "error": "No rollback files found"}
        rollback_path = rollback_files[0]
        proposal_id = rollback_path.stem
    else:
        rollback_path = ROLLBACK_DIR / f"{proposal_id}.json"

    if not rollback_path.exists():
        return {
            "status": "error",
            "error": f"Rollback file not found: {rollback_path}",
            "proposal_id": proposal_id,
        }

    rollback_meta = json.loads(rollback_path.read_text(encoding="utf-8"))
    target_file = rollback_meta["target_file"]
    diff_path = ROLLBACK_DIR / f"{proposal_id}.diff"

    result: subprocess.CompletedProcess | None = None
    # Stash current changes before rollback
    _git_stash_pre_apply()

    if diff_path.exists():
        temp_reverse = ROLLBACK_DIR / f"{proposal_id}.reverse.diff"
        temp_reverse.write_text(diff_path.read_text(encoding="utf-8"), encoding="utf-8")
        result = _git("apply", "--reverse", str(temp_reverse))
        try:
            temp_reverse.unlink()
        except OSError:
            pass

    if result is None or result.returncode != 0:
        # Fallback: git checkout -- <file>
        result2 = _git("checkout", "--", target_file)
        if result2.returncode != 0:
            _git_stash_pop()
            return {
                "status": "error",
                "error": (
                    f"Git apply --reverse and checkout fallback both failed. "
                    f"Reverse diff stderr: {result.stderr if result else 'N/A'}"
                ),
                "proposal_id": proposal_id,
            }

    # Log rollback
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "rollback",
        "proposal_id": proposal_id,
        "target_file": target_file,
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

    # Cleanup rollback files
    try:
        rollback_path.unlink()
        if diff_path.exists():
            diff_path.unlink()
    except OSError:
        pass

    return {
        "status": "rolled_back",
        "proposal_id": proposal_id,
        "target_file": target_file,
    }


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def status() -> dict[str, Any]:
    """Return current self-improvement state."""
    _ensure_dirs()

    pending: list[dict[str, Any]] = []
    for p in sorted(PROPOSALS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            pending.append({
                "proposal_id": data.get("proposal_id", p.stem),
                "target_file": data.get("target_file", "unknown"),
                "confidence": data.get("confidence"),
                "risk": data.get("risk"),
            })
        except (json.JSONDecodeError, OSError):
            pending.append({"proposal_id": p.stem, "error": "unreadable"})

    applied_list: list[dict[str, Any]] = []
    if LOG_FILE.exists():
        for line in LOG_FILE.read_text(encoding="utf-8").strip().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                if entry.get("action") != "rollback":
                    applied_list.append({
                        "timestamp": entry.get("timestamp", ""),
                        "proposal_id": entry.get("proposal_id", ""),
                        "target_file": entry.get("target_file", ""),
                    })
            except json.JSONDecodeError:
                pass

    available_rollbacks: list[dict[str, Any]] = []
    for r in sorted(
        ROLLBACK_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            data = json.loads(r.read_text(encoding="utf-8"))
            available_rollbacks.append({
                "proposal_id": data.get("proposal_id", r.stem),
                "target_file": data.get("target_file", "unknown"),
                "timestamp": data.get("timestamp", ""),
            })
        except (json.JSONDecodeError, OSError):
            available_rollbacks.append({"proposal_id": r.stem, "error": "unreadable"})

    return {
        "disabled": is_disabled(),
        "auto_apply_disabled": is_auto_apply_disabled(),
        "pending_count": len(pending),
        "applied_count": len(applied_list),
        "rollback_available_count": len(available_rollbacks),
        "pending": pending,
        "applied": applied_list[:20],
        "available_rollbacks": available_rollbacks,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point. Exits 0 on all paths (never blocks mission)."""
    try:
        _main()
    except Exception as exc:
        print(
            json.dumps({"status": "error", "error": str(exc)}, indent=2),
            file=sys.stderr,
        )
        sys.exit(0)


def _main() -> None:
    """Inner CLI logic with kill switch check per-operation."""
    if is_disabled():
        print(
            json.dumps({
                "status": "disabled",
                "reason": f"{KILL_DISABLED} is set",
            })
        )
        sys.exit(0)

    parser = argparse.ArgumentParser(description="JANUS Self-Improvement Loop Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    val_p = subparsers.add_parser("validate", help="Validate a proposal JSON")
    val_p.add_argument("--proposal-file", type=str, help="Path to proposal JSON file")

    apply_p = subparsers.add_parser("apply", help="Apply a validated proposal")
    apply_p.add_argument("--proposal-file", type=str, help="Path to proposal JSON file")

    rb_p = subparsers.add_parser("rollback", help="Rollback a proposal")
    rb_p.add_argument(
        "proposal_id", nargs="?", type=str, help="Proposal ID to rollback"
    )

    subparsers.add_parser("status", help="Show self-improvement status")

    args = parser.parse_args()

    if args.command == "status":
        print(json.dumps(status(), indent=2))
        return

    proposal: dict[str, Any] | None = None
    if getattr(args, "proposal_file", None):
        proposal_path = Path(args.proposal_file)
        if not proposal_path.exists():
            print(
                json.dumps({
                    "status": "error",
                    "error": f"File not found: {args.proposal_file}",
                })
            )
            sys.exit(0)
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    else:
        if sys.stdin.isatty():
            print(
                json.dumps({
                    "status": "error",
                    "error": "Pipe proposal JSON to stdin or use --proposal-file",
                })
            )
            sys.exit(0)
        proposal = json.loads(sys.stdin.read())

    if args.command == "validate":
        validate(proposal)
        return

    if args.command == "apply":
        if not validate(proposal):
            sys.exit(0)

        if is_auto_apply_disabled():
            print(
                json.dumps({
                    "status": "validate_only",
                    "reason": f"{KILL_AUTO_APPLY} is set — validated but not applied",
                    "proposal_id": proposal.get("proposal_id"),
                })
            )
            sys.exit(0)

        print(json.dumps(apply(proposal), indent=2))
        return

    if args.command == "rollback":
        print(json.dumps(rollback(args.proposal_id), indent=2))
        return


if __name__ == "__main__":
    main()
