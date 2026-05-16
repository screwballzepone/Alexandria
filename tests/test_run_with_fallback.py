"""Unit tests for MagnumOpus/scripts/run_with_fallback.py.

Covers FailureDetector (pure logic, no I/O) and FallbackRunner (mocked
subprocess). No live API calls — all synthetic JSON fixtures.

Run:
    pytest tests/test_run_with_fallback.py -v
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module loader — locate MagnumOpus/scripts/run_with_fallback.py
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve()


def _load_module():
    """Import run_with_fallback from the MagnumOpus scripts directory."""
    # Walk up to find repo root (parent of MagnumOpus/)
    root = HERE
    for parent in (HERE, *HERE.parents):
        candidate = parent / "MagnumOpus" / "scripts" / "run_with_fallback.py"
        if candidate.exists():
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "run_with_fallback", candidate
            )
            mod = importlib.util.module_from_spec(spec)
            sys.modules["run_with_fallback"] = mod
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            return mod, root
    raise RuntimeError(f"Could not find run_with_fallback.py from {HERE}")


_rwf, _repo_root = _load_module()


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def detector():
    """Fresh FailureDetector with a short wall clock for testing."""
    return _rwf.FailureDetector(max_runtime_seconds=3600, max_cost=0.50)


@pytest.fixture
def fast_detector():
    """FailureDetector that times out after 0.1s."""
    return _rwf.FailureDetector(max_runtime_seconds=0.1, max_cost=0.50)


@pytest.fixture
def low_cap_detector():
    """FailureDetector with a $0.01 cost cap."""
    return _rwf.FailureDetector(max_runtime_seconds=3600, max_cost=0.01)


@pytest.fixture
def real_prompt_file(tmp_path):
    """Write a temporary prompt file."""
    pf = tmp_path / "prompt.md"
    pf.write_text("Run the smoke test, please.", encoding="utf-8")
    return pf


def _event_text(text: str) -> dict:
    return {"type": "text", "part": {"text": text}}


def _event_tool_use() -> dict:
    return {"type": "tool_use", "part": {"tool": "read", "state": {"status": "running", "input": {"path": "x.py"}}}}


def _event_step_finish(
    reason: str = "stop",
    output_tokens: int = 500,
    cost: float = 0.01,
) -> dict:
    return {
        "type": "step_finish",
        "part": {
            "reason": reason,
            "tokens": {"output": output_tokens},
            "cost": cost,
        },
    }


def _event_error(status_code: int = 429) -> dict:
    return {"type": "error", "statusCode": status_code, "part": {}}


# ===================================================================
# 1. Length runaway
# ===================================================================


class TestLengthRunaway:
    def test_detected(self, detector):
        event = _event_step_finish(reason="length", output_tokens=32000, cost=0.04)
        reason, is_seam = detector.feed_event(event)
        assert reason == "length-runaway"
        assert not is_seam

    def test_not_on_normal_stop(self, detector):
        """A normal 'stop' with high output should NOT trigger length."""
        event = _event_step_finish(reason="stop", output_tokens=500, cost=0.01)
        reason, is_seam = detector.feed_event(event)
        assert reason is None


# ===================================================================
# 2. Silent stall
# ===================================================================


class TestSilentStall:
    def test_detected(self, detector):
        event = _event_step_finish(reason="other", output_tokens=0, cost=0.0)
        reason, is_seam = detector.feed_event(event)
        assert reason == "silent-stall"

    def test_not_on_other_with_output(self, detector):
        """reason=other BUT tokens.output > 0 → NOT a stall."""
        event = _event_step_finish(reason="other", output_tokens=50, cost=0.01)
        reason, _ = detector.feed_event(event)
        assert reason is None


# ===================================================================
# 3. Seam-0-stop
# ===================================================================


class TestSeam0Stop:
    def test_detected(self, detector):
        """Minimal output, no tool uses, <60s elapsed → seam-0-stop."""
        event = _event_step_finish(reason="stop", output_tokens=25, cost=0.0)
        reason, is_seam = detector.feed_event(event)
        assert reason == "seam-0-stop"
        assert not is_seam

    def test_not_when_tools_used(self, detector):
        """Tool_use events present → legitimate stop, not seam-0."""
        detector.feed_event(_event_tool_use())
        detector.feed_event(_event_tool_use())
        detector.feed_event(_event_tool_use())
        event = _event_step_finish(reason="stop", output_tokens=50, cost=0.01)
        reason, _ = detector.feed_event(event)
        assert reason is None

    def test_not_with_high_output(self, detector):
        """Output >= 100 tokens → NOT seam-0-stop."""
        event = _event_step_finish(reason="stop", output_tokens=200, cost=0.01)
        reason, _ = detector.feed_event(event)
        assert reason is None

    def test_tool_uses_reset_on_step_finish(self, detector):
        """Tool-use counter resets after each step_finish."""
        detector.feed_event(_event_tool_use())
        detector.feed_event(_event_tool_use())  # 2 tool uses
        detector.feed_event(_event_step_finish(reason="stop", output_tokens=500, cost=0.01))
        # Now a seam-0-stop should fire (counter reset, no tools on this step)
        event2 = _event_step_finish(reason="stop", output_tokens=25, cost=0.0)
        reason, _ = detector.feed_event(event2)
        assert reason == "seam-0-stop"


# ===================================================================
# 4. Rate-limit death loop
# ===================================================================


class TestRateLimitDeathLoop:
    def test_detected(self, detector):
        """3 consecutive 429s within 5 min → death loop."""
        for _ in range(3):
            reason, _ = detector.feed_event(_event_error(429))
        assert reason == "rate-limit-death-loop"
        # Check later: the third call returns the reason
        # Actually feed_event returns (reason, _). Let me check: the first
        # two return (None, False), the third returns the death loop.

    def test_consecutive_counting(self, detector):
        """First two 429s return None, third returns death loop."""
        r1, _ = detector.feed_event(_event_error(429))
        assert r1 is None
        r2, _ = detector.feed_event(_event_error(429))
        assert r2 is None
        r3, _ = detector.feed_event(_event_error(429))
        assert r3 == "rate-limit-death-loop"

    def test_resets_on_step_finish(self, detector):
        """Two 429s + step_finish + 429 → NOT death loop (counter reset)."""
        r1, _ = detector.feed_event(_event_error(429))
        assert r1 is None
        r2, _ = detector.feed_event(_event_error(429))
        assert r2 is None

        # Step finish resets counter
        detector.feed_event(_event_step_finish(reason="stop", output_tokens=500, cost=0.01))

        r3, _ = detector.feed_event(_event_error(429))
        assert r3 is None, "Counter should have been reset"

    def test_resets_on_non_429_error(self, detector):
        """Non-429 error resets the consecutive counter."""
        for _ in range(2):
            detector.feed_event(_event_error(429))
        detector.feed_event(_event_error(500))  # non-429
        r, _ = detector.feed_event(_event_error(429))
        assert r is None, "Non-429 should have reset counter"


# ===================================================================
# 5. Wall-clock exceeded
# ===================================================================


class TestWallClock:
    def test_detected(self, fast_detector):
        """Wait longer than max_runtime_seconds → wall-clock-exceeded."""
        time.sleep(0.15)
        reason = fast_detector.check_wall_clock()
        assert reason == "wall-clock-exceeded"

    def test_not_detected_before_timeout(self, fast_detector):
        """Before timeout, wall clock returns None."""
        reason = fast_detector.check_wall_clock()
        assert reason is None

    def test_not_after_seam_report(self, fast_detector):
        """Seam report suppresses wall-clock check."""
        fast_detector.feed_event(_event_text("=== SEAM REPORT ==="))
        time.sleep(0.15)
        reason = fast_detector.check_wall_clock()
        assert reason is None


# ===================================================================
# 6. Success detection
# ===================================================================


class TestSuccess:
    def test_detected(self, detector):
        event = _event_text("Here is the === SEAM REPORT === with results")
        reason, is_seam = detector.feed_event(event)
        assert reason == "success"
        assert is_seam

    def test_seam_marker_anywhere_in_text(self, detector):
        """Marker can be embedded in longer text."""
        event = _event_text("Results: 24 PASS, 1 DEGRADED, 0 FAIL === SEAM REPORT ===")
        reason, _ = detector.feed_event(event)
        assert reason == "success"

    def test_got_seam_report_flag(self, detector):
        """got_seam_report flag persists after detection."""
        detector.feed_event(_event_text("=== SEAM REPORT ==="))
        assert detector.got_seam_report is True


# ===================================================================
# 7. Legitimate stop NOT seam-0-stop (negative case 1)
# ===================================================================


class TestLegitimateStop:
    def test_high_output_not_seam_0(self, detector):
        """Output >= 100 tokens → NOT seam-0-stop."""
        r, _ = detector.feed_event(
            _event_step_finish(reason="stop", output_tokens=200, cost=0.02)
        )
        assert r is None

    def test_with_tool_uses_not_seam_0(self, detector):
        """Tool uses present + stop → NOT seam-0-stop, even with low output."""
        detector.feed_event(_event_tool_use())
        detector.feed_event(_event_tool_use())
        r, _ = detector.feed_event(
            _event_step_finish(reason="stop", output_tokens=50, cost=0.01)
        )
        assert r is None

    def test_long_elapsed_not_seam_0(self, detector):
        """Elapsed >= 60s → NOT seam-0-stop (use a detector with past attempt_start)."""
        old_detector = _rwf.FailureDetector(
            max_runtime_seconds=3600, max_cost=0.50,
            attempt_start=time.time() - 120,  # 2 min ago
        )
        r, _ = old_detector.feed_event(
            _event_step_finish(reason="stop", output_tokens=50, cost=0.0)
        )
        assert r is None, "Elapsed > 60s should prevent seam-0-stop"


# ===================================================================
# 8. Two 429s with success between — NOT death loop (negative case 2)
# ===================================================================


class TestNotDeathLoop:
    def test_two_429s_with_step_between(self, detector):
        """Two 429s, then step_finish resets, then another 429 → NOT death."""
        for _ in range(2):
            detector.feed_event(_event_error(429))

        # Successful step
        detector.feed_event(
            _event_step_finish(reason="stop", output_tokens=500, cost=0.01)
        )

        # A third 429 should NOT trigger death loop (counter was reset)
        r, _ = detector.feed_event(_event_error(429))
        assert r is None

        # Now we'd need 2 more to trigger it
        detector.feed_event(_event_error(429))
        r, _ = detector.feed_event(_event_error(429))
        assert r == "rate-limit-death-loop"


# ===================================================================
# 9. Cost cap exceeded
# ===================================================================


class TestCostCap:
    def test_detected(self, low_cap_detector):
        """Cost exceeds $0.01 cap → cost-cap-exceeded."""
        low_cap_detector.feed_event(
            _event_step_finish(reason="stop", output_tokens=500, cost=0.008)
        )
        r = low_cap_detector.check_cost_cap()
        assert r is None

        low_cap_detector.feed_event(
            _event_step_finish(reason="stop", output_tokens=500, cost=0.008)
        )
        r = low_cap_detector.check_cost_cap()
        assert r == "cost-cap-exceeded"

    def test_total_accumulates(self, detector):
        """Multiple step_finish events accumulate cost."""
        for _ in range(5):
            detector.feed_event(
                _event_step_finish(reason="stop", output_tokens=200, cost=0.10)
            )
        assert detector.total_cost == pytest.approx(0.50)
        r = detector.check_cost_cap()
        assert r is None  # at exactly 0.50, not over

        detector.feed_event(
            _event_step_finish(reason="stop", output_tokens=200, cost=0.01)
        )
        assert detector.total_cost == pytest.approx(0.51)
        r = detector.check_cost_cap()
        assert r == "cost-cap-exceeded"


# ===================================================================
# 10. CLI dry-run
# ===================================================================


class TestDryRun:
    def test_exits_0(self, real_prompt_file):
        """--dry-run with valid args exits 0."""
        rc = _rwf.main([
            "--prompt-file", str(real_prompt_file),
            "--dry-run",
        ])
        assert rc == 0

    def test_bad_args_exits_2(self):
        """Missing --prompt-file exits 2."""
        rc = _rwf.main(["--dry-run"])
        assert rc == 2

    def test_nonexistent_prompt_file(self):
        """Non-existent prompt file exits 2."""
        rc = _rwf.main([
            "--prompt-file", "/nonexistent/prompt.md",
            "--dry-run",
        ])
        assert rc == 2

    def test_bad_model_id(self, real_prompt_file):
        """Model ID without '/' is rejected."""
        rc = _rwf.main([
            "--prompt-file", str(real_prompt_file),
            "--ladder", "badmodel",
            "--dry-run",
        ])
        assert rc == 2


# ===================================================================
# 11. Audit log correct shape
# ===================================================================


class TestAuditShape:
    def test_audit_entries_after_run(self, tmp_path, monkeypatch):
        """After a mocked run, audit log has correct structure."""
        audit_dir = tmp_path / "audit"
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt", encoding="utf-8")

        # Mock spawn_opencode to simulate seamless-success
        mock_process = MagicMock()
        mock_process.pid = 9999
        mock_process.poll.return_value = 0

        success_events = [
            json.dumps({"type": "text", "part": {"text": "Working..."}}),
            json.dumps({"type": "step_finish", "part": {"reason": "stop", "tokens": {"output": 500}, "cost": 0.02}}),
            json.dumps({"type": "text", "part": {"text": "=== SEAM REPORT === 24 PASS"}}),
        ]
        mock_process.stdout.readline.side_effect = success_events + [""]
        mock_process.stdout.close = MagicMock()

        with patch.object(_rwf, "spawn_opencode", return_value=mock_process):
            rc = _rwf.main([
                "--prompt-file", str(prompt_file),
                "--ladder", "deepseek/deepseek-v4-flash",
                "--max-attempts", "1",
                "--audit-dir", str(audit_dir),
            ])

        assert rc == 0

        # Find the audit file
        audit_files = list(audit_dir.glob("fallback-audit-*.json"))
        assert len(audit_files) == 1

        audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
        assert "started_at" in audit
        assert "prompt_file" in audit
        assert "ladder" in audit
        assert audit["ladder"] == ["deepseek/deepseek-v4-flash"]
        assert "max_cost" in audit
        assert "attempts" in audit
        assert len(audit["attempts"]) == 1

        entry = audit["attempts"][0]
        assert entry["rung"] == 0
        assert entry["model"] == "deepseek/deepseek-v4-flash"
        assert entry["exit_reason"] == "success"
        assert entry["cost_estimate"] > 0
        assert entry["elapsed_seconds"] >= 0
        assert "started_at" in entry
        assert "ended_at" in entry
        assert "evidence" in entry

        assert audit["final_outcome"] == "success"
        assert audit["total_cost"] > 0
        assert audit["total_elapsed_seconds"] >= 0


# ===================================================================
# 12. Ladder exhausted after 3 attempts
# ===================================================================


class TestLadderExhausted:
    def test_all_three_fail(self, tmp_path, monkeypatch):
        """3 attempts all fail → exit code 1."""
        audit_dir = tmp_path / "audit"
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt", encoding="utf-8")

        def _make_failing_process():
            """Simulate a length-runaway on the first step."""
            mp = MagicMock()
            mp.pid = 9999
            mp.poll.return_value = 0
            mp.stdout.readline.side_effect = [
                json.dumps({
                    "type": "step_finish",
                    "part": {"reason": "length", "tokens": {"output": 32000}, "cost": 0.04},
                }),
                "",
            ]
            mp.stdout.close = MagicMock()
            return mp

        with patch.object(_rwf, "spawn_opencode", side_effect=lambda *a, **kw: _make_failing_process()):
            rc = _rwf.main([
                "--prompt-file", str(prompt_file),
                "--ladder", "deepseek/deepseek-v4-flash,deepseek/deepseek-chat,moonshotai/kimi-k2.6",
                "--max-attempts", "3",
                "--audit-dir", str(audit_dir),
            ])

        assert rc == 1

        # Verify 3 attempts in audit
        audit_files = list(audit_dir.glob("fallback-audit-*.json"))
        assert len(audit_files) == 1
        audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
        assert len(audit["attempts"]) == 3
        assert all(a["exit_reason"] == "length-runaway" for a in audit["attempts"])
        assert audit["final_outcome"] == "failed"


# ===================================================================
# 13. Cost cap aborts
# ===================================================================


class TestCostCapAbort:
    def test_cost_cap_exits_3(self, tmp_path):
        """When cost cap exceeded mid-run, exit 3."""
        audit_dir = tmp_path / "audit"
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt", encoding="utf-8")

        # First step uses a lot of cost, second step pushes over cap
        events = [
            json.dumps({"type": "step_finish", "part": {"reason": "stop", "tokens": {"output": 500}, "cost": 0.30}}),
            json.dumps({"type": "step_finish", "part": {"reason": "stop", "tokens": {"output": 500}, "cost": 0.25}}),
        ]

        mock_process = MagicMock()
        mock_process.pid = 9999
        mock_process.poll.return_value = 0
        mock_process.stdout.readline.side_effect = events + [""]
        mock_process.stdout.close = MagicMock()

        with patch.object(_rwf, "spawn_opencode", return_value=mock_process):
            rc = _rwf.main([
                "--prompt-file", str(prompt_file),
                "--ladder", "deepseek/deepseek-v4-flash",
                "--max-cost", "0.50",
                "--max-attempts", "1",
                "--audit-dir", str(audit_dir),
            ])

        assert rc == 3

        audit_files = list(audit_dir.glob("fallback-audit-*.json"))
        assert len(audit_files) == 1
        audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
        assert audit["attempts"][0]["exit_reason"] == "cost-cap-exceeded"


# ===================================================================
# 14. Kill switch (JANUS_FALLBACK_DISABLED)
# ===================================================================


class TestKillSwitch:
    def test_disabled_only_one_rung(self, tmp_path, monkeypatch):
        """JANUS_FALLBACK_DISABLED=1 runs rung-1 only, stops after it fails."""
        audit_dir = tmp_path / "audit"
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Test prompt", encoding="utf-8")

        monkeypatch.setenv("JANUS_FALLBACK_DISABLED", "1")

        mock_process = MagicMock()
        mock_process.pid = 9999
        mock_process.poll.return_value = 0
        mock_process.stdout.readline.side_effect = [
            json.dumps({
                "type": "step_finish",
                "part": {"reason": "length", "tokens": {"output": 32000}, "cost": 0.04},
            }),
            "",
        ]
        mock_process.stdout.close = MagicMock()

        with patch.object(_rwf, "spawn_opencode", return_value=mock_process):
            rc = _rwf.main([
                "--prompt-file", str(prompt_file),
                "--ladder", "deepseek/deepseek-v4-flash,deepseek/deepseek-chat,moonshotai/kimi-k2.6",
                "--max-attempts", "3",
                "--audit-dir", str(audit_dir),
            ])

        # Only 1 rung run, then exhausted
        assert rc == 1

        audit_files = list(audit_dir.glob("fallback-audit-*.json"))
        assert len(audit_files) == 1
        audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
        assert len(audit["attempts"]) == 1
        assert audit["attempts"][0]["model"] == "deepseek/deepseek-v4-flash"


# ===================================================================
# 15. --help works
# ===================================================================


class TestHelp:
    def test_help_exits_0(self):
        """--help prints usage and exits 0 (via argparse)."""
        try:
            _rwf.parse_args(["--help"])
        except SystemExit as e:
            assert e.code == 0

    def test_parse_args_ladder_default(self):
        """Default ladder is the LADDER constant."""
        args = _rwf.parse_args(["--prompt-file", "test.md"])
        assert args.ladder == list(_rwf.LADDER)

    def test_parse_args_custom_ladder(self):
        """Comma-separated ladder parsed correctly."""
        args = _rwf.parse_args([
            "--prompt-file", "test.md",
            "--ladder", "a/b,c/d",
        ])
        assert args.ladder == ["a/b", "c/d"]


# ===================================================================
# 16. Edge case: detector ignores unknown event types
# ===================================================================


class TestUnknownEvents:
    def test_unknown_event_type(self, detector):
        """Unknown event types should be silently ignored."""
        r, _ = detector.feed_event({"type": "unknown", "part": {}})
        assert r is None

    def test_empty_event(self, detector):
        """Completely empty event should not crash."""
        r, _ = detector.feed_event({})
        assert r is None

    def test_none_cost(self, detector):
        """None cost should be treated as 0."""
        event = _event_step_finish(reason="stop", output_tokens=500, cost=None)
        detector.feed_event(event)
        assert detector.total_cost == 0.0

    def test_missing_tokens(self, detector):
        """Missing tokens field should not crash or fire seam-0-stop."""
        event = {"type": "step_finish", "part": {"reason": "stop"}}
        r, _ = detector.feed_event(event)
        assert r is None, "Missing tokens should not fire seam-0-stop"

    def test_empty_tokens_dict(self, detector):
        """Empty tokens dict: output_tokens is None, not seam-0-stop."""
        event = {"type": "step_finish", "part": {"reason": "stop", "tokens": {}}}
        r, _ = detector.feed_event(event)
        assert r is None, "Empty tokens dict should not fire seam-0-stop"

    def test_zero_output_tokens_no_tools(self, detector):
        """Explicit tokens.output=0, 0 tool_uses, stop, fast → seam-0-stop."""
        event = {"type": "step_finish", "part": {"reason": "stop", "tokens": {"output": 0}}}
        r, _ = detector.feed_event(event)
        assert r == "seam-0-stop"
