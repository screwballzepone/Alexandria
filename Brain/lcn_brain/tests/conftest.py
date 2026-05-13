"""
Shared pytest fixtures for LCN Brain tests.

Provides a global ``key`` fixture — a JAX PRNGKey — for test classes
that don't define their own.  Used by test_burgers, test_clock, test_ssf.

Also adds real-time collection and test-run progress hooks.
"""

import jax
import pytest

# ANSI colours (Windows Terminal compatible)
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RED = "\033[91m"
GREY = "\033[90m"
RESET = "\033[0m"


@pytest.fixture
def key():
    return jax.random.PRNGKey(0)


def pytest_collection_modifyitems(config, items):
    """Print a collection summary for the LCN Brain test suite."""
    n = len(items)
    print(f"  {CYAN}[LCN Brain] Collected {n} test{'s' if n != 1 else ''}{RESET}")


def pytest_runtest_protocol(item, nextitem):
    """Print the test function name before running it."""
    nodeid = item.nodeid
    test_name = nodeid.split("::")[-1]
    print(f"    {YELLOW}>> {test_name}{RESET}", flush=True)
    return None  # Let normal pytest processing continue
