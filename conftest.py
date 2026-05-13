"""
Root pytest conftest — real-time visual progress indicators for all tests.

Hooks into pytest to display:
  - Which test file is being entered (with timestamp)
  - Each test function as it starts
  - Pass/fail result inline (colored)
  - Slow-test marker (>1s)
  - Summary with pass/fail/skip/error counts
"""

import time
from datetime import datetime

import pytest


class _ProgressTracker:
    """Holds module-level state across pytest hooks."""

    def __init__(self):
        self.current_file: str | None = None
        self.test_start_times: dict[str, float] = {}
        self.results: dict[str, int] = {"PASSED": 0, "FAILED": 0, "ERROR": 0, "SKIPPED": 0}


_tracker = _ProgressTracker()


# ---------------------------------------------------------------------------
# ANSI colour helpers  (Windows Terminal compatible)
# ---------------------------------------------------------------------------
def _cyan(text: str) -> str:
    return f"\033[96m{text}\033[0m"


def _blue(text: str) -> str:
    return f"\033[94m{text}\033[0m"


def _yellow(text: str) -> str:
    return f"\033[93m{text}\033[0m"


def _green(text: str) -> str:
    return f"\033[92m{text}\033[0m"


def _red(text: str) -> str:
    return f"\033[91m{text}\033[0m"


def _grey(text: str) -> str:
    return f"\033[90m{text}\033[0m"


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------
def pytest_collection_modifyitems(config, items):
    """Print collection summary."""
    n = len(items)
    print(f"\n{_cyan('[Setup]')} Collected {_yellow(str(n))} test{'s' if n != 1 else ''}")


def pytest_runtest_protocol(item, nextitem):
    """Print test file (with timestamp) and test name before execution."""
    nodeid = item.nodeid
    file_part = nodeid.split("::")[0]

    if file_part != _tracker.current_file:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"\n{_blue(f'[{ts}]')} {_blue('>>')} {file_part}")
        _tracker.current_file = file_part

    test_name = nodeid.split("::")[-1]
    _tracker.test_start_times[nodeid] = time.time()
    print(f"    {_yellow(test_name)} ... ", end="", flush=True)
    return None  # Let normal pytest processing continue


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture test outcome after call phase and print result inline."""
    yield
    nodeid = item.nodeid
    elapsed = time.time() - _tracker.test_start_times.get(nodeid, time.time())

    if call.when == "call":
        if call.excinfo is None:
            status = "PASSED"
            _tracker.results["PASSED"] += 1
            colour = _green
        else:
            # Distinguish skip from failure
            if isinstance(call.excinfo.value, pytest.skip.Exception):
                status = "SKIPPED"
                _tracker.results["SKIPPED"] += 1
                colour = _yellow
            else:
                status = "FAILED"
                _tracker.results["FAILED"] += 1
                colour = _red

        slow = f" {_grey(f'({elapsed:.1f}s)')}" if elapsed > 1 else ""
        print(f"{colour(status)}{slow}")

    elif call.when == "setup" and call.excinfo is not None:
        # Setup error (test never reached call phase)
        _tracker.results["ERROR"] += 1
        exc_name = call.excinfo.type.__name__ if call.excinfo.type else "Exception"
        print(f"{_red('ERROR')} {_grey(f'[{exc_name}]')}")


def pytest_terminal_summary(terminalreporter):
    """Print coloured summary at end of test run."""
    total = sum(_tracker.results.values())
    if total == 0:
        return

    print(f"\n{_cyan('=' * 52)}")
    print(f"  {_cyan('Summary')}")
    for status in ("PASSED", "FAILED", "ERROR", "SKIPPED"):
        count = _tracker.results.get(status, 0)
        if count > 0:
            colour = {"PASSED": _green, "FAILED": _red, "ERROR": _red, "SKIPPED": _yellow}[status]
            print(f"    {colour(status)}: {count}")
    print(f"  {_cyan(f'Total: {total}')}")
    print(f"{_cyan('=' * 52)}\n")
