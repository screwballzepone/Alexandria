#!/usr/bin/env python3
"""run_with_fallback.py — Model fallback ladder wrapper for opencode run.

Streams opencode JSON output, detects failure signals (length runaway, silent
stall, seam-0-stop, rate-limit death loop, wall-clock exceeded), and auto-
restarts on the next ladder rung.

Usage:
    python MagnumOpus/scripts/run_with_fallback.py --prompt-file <path> [options]

Exit codes:
    0  success (seam report received)
    1  all rungs exhausted
    2  bad CLI args
    3  cost cap exceeded
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LADDER = [
    "deepseek/deepseek-v4-flash",   # rung 1: $0.14/$0.28, 1M context
    "deepseek/deepseek-chat",        # rung 2: V3.2 alias, $0.27/$0.40, 164K context
    "moonshotai/kimi-k2.6",          # rung 3: $0.95/$4.00, 256K context, agentic-tuned
]

DEFAULT_MAX_COST = 0.50
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MAX_RUNTIME_MINUTES = 60
AUDIT_DIR_DEFAULT = "MagnumOpus/smoke-test-artifacts"

SEAM_MARKER = "=== SEAM REPORT ==="

FAILURE_REASONS = frozenset({
    "length-runaway",
    "silent-stall",
    "seam-0-stop",
    "rate-limit-death-loop",
    "wall-clock-exceeded",
    "cost-cap-exceeded",
    "success",
    "unknown",
})

# ---------------------------------------------------------------------------
# Failure detection
# ---------------------------------------------------------------------------


class FailureDetector:
    """Tracks opencode JSON events and signals failure or success.

    Pure logic — no I/O. Designed for single-threaded streaming use.
    Feed events via feed_event(), then call check_wall_clock() /
    check_cost_cap() periodically.

    Thread-safe? No — not needed (single-threaded subprocess reading).
    """

    def __init__(
        self,
        max_runtime_seconds: float = 3600,
        max_cost: float = 0.50,
        attempt_start: float | None = None,
    ):
        self.max_runtime_seconds = max_runtime_seconds
        self.max_cost = max_cost
        self.attempt_start = attempt_start or time.time()

        self.total_cost: float = 0.0
        self.consecutive_429s: int = 0
        self.last_429_time: float | None = None
        self.step_tool_uses: int = 0
        self.got_seam_report: bool = False

    def feed_event(self, event: dict) -> tuple[str | None, bool]:
        """Process one parsed JSON event from opencode.

        Returns:
            (exit_reason_or_None, is_seam_report)
            - exit_reason: ``None`` for normal events, otherwise a string
              like ``"length-runaway"`` or ``"success"``.
            - is_seam_report: ``True`` if this exact event contained the
              SEAM REPORT marker.
        """
        event_type = event.get("type")
        part = event.get("part", event) or event

        # ---- Text events (seam report detection) ----
        if event_type == "text":
            text = part.get("text", "")
            if SEAM_MARKER in text:
                self.got_seam_report = True
                return ("success", True)
            return (None, False)

        # ---- Tool use events (count per step for seam-0-stop) ----
        if event_type == "tool_use":
            self.step_tool_uses += 1
            return (None, False)

        # ---- Step finish events (length, silent stall, seam-0-stop) ----
        if event_type == "step_finish":
            reason = part.get("reason", "")
            tokens_raw = part.get("tokens")
            tokens = tokens_raw if isinstance(tokens_raw, dict) else {}
            output_tokens = tokens.get("output") if tokens else None
            cost = part.get("cost", 0)
            if cost is None:
                cost = 0
            self.total_cost += cost

            elapsed = time.time() - self.attempt_start

            # Length runaway: model hit max_tokens
            if reason == "length":
                return ("length-runaway", False)

            # Silent stall: reason=other, zero output tokens
            if reason == "other" and output_tokens is not None and output_tokens == 0:
                return ("silent-stall", False)

            # Seam-0-stop: reason=stop, minimal output, no tools, very fast
            if (
                reason == "stop"
                and output_tokens is not None
                and output_tokens < 100
                and self.step_tool_uses == 0
                and elapsed < 60
            ):
                return ("seam-0-stop", False)

            # Normal step: reset rate-limit counter, tool-use counter
            self.consecutive_429s = 0
            self.step_tool_uses = 0
            return (None, False)

        # ---- Error events (rate-limit detection) ----
        if event_type == "error":
            status_code = event.get("statusCode") or part.get("statusCode")
            if status_code == 429:
                now = time.time()
                if (
                    self.last_429_time is not None
                    and (now - self.last_429_time) < 300
                ):
                    self.consecutive_429s += 1
                else:
                    self.consecutive_429s = 1
                self.last_429_time = now

                if self.consecutive_429s >= 3:
                    return ("rate-limit-death-loop", False)
            else:
                # Non-429 error resets the counter
                self.consecutive_429s = 0
            return (None, False)

        return (None, False)

    def check_wall_clock(self) -> str | None:
        """Check if total elapsed time exceeds max runtime.

        Returns ``"wall-clock-exceeded"`` or ``None``.
        """
        if self.got_seam_report:
            return None
        elapsed = time.time() - self.attempt_start
        if elapsed > self.max_runtime_seconds:
            return "wall-clock-exceeded"
        return None

    def check_cost_cap(self) -> str | None:
        """Check if cumulative cost exceeds the cap.

        Returns ``"cost-cap-exceeded"`` or ``None``.
        """
        if self.total_cost > self.max_cost:
            return "cost-cap-exceeded"
        return None


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


def spawn_opencode(
    prompt_text: str,
    model: str,
    cwd: str | None = None,
) -> subprocess.Popen:
    """Launch ``opencode run --model <model> --format json ...``.

    Returns a ``Popen`` with ``stdout=PIPE`` for streaming.
    """
    cmd = [
        "opencode.cmd",
        "run",
        "--model",
        model,
        "--format",
        "json",
        "--dangerously-skip-permissions",
        prompt_text,
    ]
    return subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
    )


def kill_process_tree(process: subprocess.Popen | None) -> None:
    """Kill the full process tree on Windows via ``taskkill /F /T /PID``.

    Matches the pattern from ``core/worker.py`` — never use ``.terminate()``
    alone because ``shell=True`` spawns a ``cmd.exe`` intermediate.
    """
    if process is None:
        return
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        try:
            process.terminate()
        except Exception:
            pass


def stream_events(process: subprocess.Popen):
    """Yield parsed JSON events from an opencode process stdout.

    Stops when the pipe is closed (process exits or is killed).
    """
    for line in iter(process.stdout.readline, ""):
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            pass


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def format_audit_path(audit_dir: Path) -> Path:
    """Return the audit file path with a timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return audit_dir / f"fallback-audit-{ts}.json"


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


class FallbackRunner:
    """Orchestrates model fallback ladder attempts.

    Owns the audit trail, cost tracking, and subprocess lifecycle.
    """

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.ladder: list[str] = list(args.ladder)
        self.max_attempts: int = args.max_attempts
        self.max_cost: float = args.max_cost
        self.max_runtime_seconds: int = args.max_runtime_minutes * 60
        self.audit_dir: Path = Path(args.audit_dir)
        self.prompt_file: Path = Path(args.prompt_file)
        self.dry_run: bool = args.dry_run
        self.cwd: Path = Path.cwd()

        self.audit: dict = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "prompt_file": str(self.prompt_file),
            "ladder": list(self.ladder),
            "max_cost": self.max_cost,
            "attempts": [],
        }
        self.total_cost: float = 0.0
        self.run_start_time: float = time.time()

    # -- validators ---------------------------------------------------------

    def validate(self) -> str | None:
        """Validate args. Returns an error string or ``None`` if OK."""
        if not self.prompt_file.exists():
            return f"Prompt file not found: {self.prompt_file}"
        if not self.ladder:
            return "Ladder is empty"
        if self.max_attempts < 1:
            return "max-attempts must be >= 1"
        if self.max_cost < 0:
            return "max-cost must be >= 0"
        for model_id in self.ladder:
            if "/" not in model_id:
                return f"Invalid model ID (no '/' separator): {model_id}"
        return None

    # -- helpers ------------------------------------------------------------

    def _read_prompt(self) -> str:
        return self.prompt_file.read_text(encoding="utf-8")

    def _reset_mission(self) -> None:
        """Run ``reset_mission.py`` to reset mission.json to planning state."""
        reset_script = self.cwd / "MagnumOpus" / "reset_mission.py"
        if reset_script.exists():
            subprocess.run(
                [sys.executable, str(reset_script)],
                cwd=self.cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def _clean_artifacts(self) -> None:
        """Git-clean smoke test artifacts between rungs."""
        subprocess.run(
            ["git", "clean", "-fd", "MagnumOpus/smoke-test-artifacts/"],
            cwd=self.cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _write_audit(self) -> Path:
        """Finalize and write the audit log file. Returns the path."""
        had_success = any(
            a["exit_reason"] == "success" for a in self.audit["attempts"]
        )
        self.audit["final_outcome"] = "success" if had_success else "failed"
        self.audit["total_cost"] = round(self.total_cost, 6)
        self.audit["total_elapsed_seconds"] = round(time.time() - self.run_start_time)

        self.audit_dir.mkdir(parents=True, exist_ok=True)
        path = format_audit_path(self.audit_dir)
        path.write_text(json.dumps(self.audit, indent=2), encoding="utf-8")
        return path

    # -- per-attempt logic --------------------------------------------------

    def _run_attempt(
        self,
        rung_index: int,
        model: str,
        prompt_text: str,
    ) -> tuple[str, str, float]:
        """Run one attempt with the given model.

        Returns ``(exit_reason, evidence_string, attempt_cost)``.
        """
        attempt_start = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if self.dry_run:
            print(f"  [DRY-RUN] would run: opencode run --model {model}")
            entry = {
                "rung": rung_index,
                "model": model,
                "started_at": started_at,
                "ended_at": started_at,
                "exit_reason": "dry-run",
                "elapsed_seconds": 0,
                "cost_estimate": 0.0,
                "evidence": "dry-run mode",
            }
            self.audit["attempts"].append(entry)
            return ("dry-run", "dry-run mode", 0.0)

        detector = FailureDetector(
            max_runtime_seconds=self.max_runtime_seconds,
            max_cost=self.max_cost - self.total_cost,
            attempt_start=attempt_start,
        )

        process = spawn_opencode(prompt_text, model, cwd=str(self.cwd))
        evidence_parts: list[str] = []
        exit_reason: str | None = None

        try:
            for event in stream_events(process):
                reason, _is_seam = detector.feed_event(event)

                if reason == "success":
                    evidence_parts.append("seam_report_detected")
                    exit_reason = "success"
                    break

                if reason is not None:
                    ev_part = event.get("part", event) or event
                    evidence_parts.append(
                        f"type={event.get('type', '')} "
                        f"reason={ev_part.get('reason', '')} "
                        f"output_tokens={ev_part.get('tokens', {}).get('output', '')}"
                    )
                    exit_reason = reason
                    break

                # Periodic checks
                wall = detector.check_wall_clock()
                if wall:
                    exit_reason = wall
                    break

                cost = detector.check_cost_cap()
                if cost:
                    exit_reason = cost
                    break

            # No signal from event stream — check remaining conditions
            if exit_reason is None:
                if detector.check_cost_cap():
                    exit_reason = "cost-cap-exceeded"
                else:
                    exit_reason = "unknown"

            # Let the process finish naturally (unless already killed)
            if process.poll() is None:
                process.wait()

        finally:
            kill_process_tree(process)
            # Close stdout pipe to release resources
            try:
                process.stdout.close()
            except Exception:
                pass

        ended_at = datetime.now(timezone.utc).isoformat()
        elapsed = time.time() - attempt_start
        evidence = "; ".join(evidence_parts) if evidence_parts else f"exit_reason={exit_reason}"

        entry = {
            "rung": rung_index,
            "model": model,
            "started_at": started_at,
            "ended_at": ended_at,
            "exit_reason": exit_reason,
            "elapsed_seconds": round(elapsed),
            "cost_estimate": round(detector.total_cost, 6),
            "evidence": evidence,
        }
        self.audit["attempts"].append(entry)
        self.total_cost += detector.total_cost

        return (exit_reason, evidence, detector.total_cost)

    # -- main entry point ---------------------------------------------------

    def run(self) -> int:
        """Execute the fallback ladder. Returns the exit code."""
        # Kill switch: run rung-1 only, no escalation
        if os.environ.get("JANUS_FALLBACK_DISABLED") == "1":
            print("JANUS_FALLBACK_DISABLED=1 — rung-1 only, no escalation")
            self.ladder = [self.ladder[0]] if self.ladder else []
            self.max_attempts = 1

        prompt_text = self._read_prompt()
        total_rungs = min(len(self.ladder), self.max_attempts)

        for i, model in enumerate(self.ladder):
            if i >= self.max_attempts:
                print(f"Max attempts ({self.max_attempts}) reached, stopping")
                break

            rung_display = i + 1
            print(f"Attempt {rung_display}/{total_rungs}: {model}")

            exit_reason, evidence, cost = self._run_attempt(i, model, prompt_text)
            print(f"  Result: {exit_reason} (cost=${cost:.4f})")

            # Success
            if exit_reason == "success":
                audit_path = self._write_audit()
                print(f"Success on rung {rung_display} ({model})")
                print(f"Audit: {audit_path}")
                return 0

            # Cost cap hit (non-recoverable within this session)
            if exit_reason == "cost-cap-exceeded":
                audit_path = self._write_audit()
                print(f"Cost cap ${self.max_cost} exceeded — aborting")
                print(f"Audit: {audit_path}")
                return 3

            # Escalate: reset mission state between rungs
            if not self.dry_run and exit_reason not in ("dry-run",):
                self._reset_mission()
                self._clean_artifacts()

        # All rungs exhausted
        audit_path = self._write_audit()
        print("All rungs exhausted")
        print(f"Audit: {audit_path}")
        return 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and return CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Model fallback ladder wrapper for opencode run.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exit codes:\n"
            "  0  success (seam report received)\n"
            "  1  all rungs failed\n"
            "  2  bad CLI args\n"
            "  3  cost cap exceeded\n"
            "\n"
            "Environment:\n"
            "  JANUS_FALLBACK_DISABLED=1  run rung-1 only, no escalation"
        ),
    )
    parser.add_argument(
        "--prompt-file",
        required=True,
        help="Path to the prompt file (e.g. MagnumOpus/claude-code-prompt-27.md)",
    )
    parser.add_argument(
        "--ladder",
        default=",".join(LADDER),
        help=f"Comma-separated model IDs (default: {','.join(LADDER)})",
    )
    parser.add_argument(
        "--max-cost",
        type=float,
        default=DEFAULT_MAX_COST,
        help=f"Maximum cumulative cost in USD (default: {DEFAULT_MAX_COST})",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
        help=f"Maximum number of attempts (default: {DEFAULT_MAX_ATTEMPTS})",
    )
    parser.add_argument(
        "--max-runtime-minutes",
        type=int,
        default=DEFAULT_MAX_RUNTIME_MINUTES,
        help=f"Per-rung wall clock cap in minutes (default: {DEFAULT_MAX_RUNTIME_MINUTES})",
    )
    parser.add_argument(
        "--audit-dir",
        default=AUDIT_DIR_DEFAULT,
        help=f"Directory for audit logs (default: {AUDIT_DIR_DEFAULT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate args, print ladder plan, exit 0",
    )

    args = parser.parse_args(argv)
    args.ladder = [m.strip() for m in args.ladder.split(",") if m.strip()]
    return args


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns exit code."""
    try:
        args = parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 2
    runner = FallbackRunner(args)

    error = runner.validate()
    if error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    # Print plan
    print("Model Fallback Ladder")
    print(f"  Prompt:   {args.prompt_file}")
    print(f"  Ladder:   {', '.join(args.ladder)}")
    print(f"  Max cost: ${args.max_cost}")
    print(f"  Attempts: {args.max_attempts}")
    print(f"  Timeout:  {args.max_runtime_minutes} min per rung")
    print(f"  Audit:    {args.audit_dir}")

    if args.dry_run:
        print("  [DRY-RUN] Validation OK — exiting 0")
        return 0

    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
