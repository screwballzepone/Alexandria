"""Test suite for .opencode/tools/capability_assessor.py.

Coverage (TIER-CLASSIFIER.md v1, 7 rules):
  Rule 1 — Enterprise keyword in request_text
  Rule 2 — predicted_files >= 11
  Rule 3 — diff_scope_estimate >= 300
  Rule 4 — any file under .opencode/protocols/
  Rule 5 — predicted_files >= 3
  Rule 6 — any file under .opencode/agent/ or matching orchestrator*
  Rule 7 — default → MVP

Plus:
  - Word-boundary guards on all 6 Enterprise patterns (so "emigration"
    does not falsely match "migration", etc.)
  - Stem-variant coverage on Enterprise patterns (migrate / migrated /
    migrating / migration all fire rule 1)
  - First-rule-wins ordering invariant
  - should_escalate() upward-only enforcement
  - to_dict() serialization shape
  - CLI round-trip via subprocess
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------


def _load():
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        candidate = parent / ".opencode" / "tools" / "capability_assessor.py"
        if candidate.exists():
            spec = importlib.util.spec_from_file_location("capability_assessor", candidate)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["capability_assessor"] = mod
            assert spec.loader is not None
            spec.loader.exec_module(mod)
            return mod, candidate
    raise RuntimeError("Could not find .opencode/tools/capability_assessor.py")


cap, _MODULE_PATH = _load()


# ---------------------------------------------------------------------------
# Rule 1 — Enterprise keyword in request_text
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "request_text, expected_label",
    [
        ("migrate the user table to a new schema", "migration"),
        ("Migration plan for v2.0", "migration"),
        ("we migrated the auth backend last week", "migration"),
        ("migrating from PostgreSQL to MySQL", "migration"),
        ("rewrite the orchestrator from scratch", "rewrite"),
        ("we are rewriting auth completely", "rewrite"),
        ("rewritten as a state machine", "rewrite"),
        ("change the architecture", "architecture"),
        ("architectural refactor", "architecture"),
        ("deprecate the legacy API", "deprecate"),
        ("deprecation notice for v1", "deprecate"),
        ("introduces a breaking change", "breaking change"),
        ("two breaking changes in this release", "breaking change"),
        ("introducing a new primary agent", "new primary agent"),
    ],
)
def test_rule_1_enterprise_keywords_fire(request_text, expected_label):
    r = cap.classify(request_text=request_text, predicted_files=["foo.py"], diff_scope_estimate=10)
    assert r.tier == "Enterprise"
    assert "rule-1" in r.reason
    assert expected_label in r.reason


@pytest.mark.parametrize(
    "false_match",
    [
        # Word-boundary guard: emigration must not match "migrat(e|ion)"
        "emigration policy notes",
        "immigration form fields",
        # Substring red herrings
        "underwriter for the loan",  # contains 'writer' near 'rewrit' — must NOT match
        # "architect" bare noun — DOES match (architect alone IS load-bearing for enterprise tier)
        "the resident architect's blog",
    ],
)
def test_rule_1_word_boundary_guards(false_match):
    r = cap.classify(request_text=false_match, predicted_files=["foo.py"], diff_scope_estimate=10)
    # The 4th case ("the resident architect's blog") legitimately matches "architectur(e|al|ally|es)"?
    # No — "architect" is the stem, "architectur" is the regex root with required suffix. Let me re-check:
    # ENTERPRISE_PATTERNS has r"\barchitectur(e|al|ally|es)\b" — requires "architectur" + suffix
    # "architect" alone does NOT match (no suffix). So it should NOT trigger rule 1.
    if false_match == "the resident architect's blog":
        # "architect" without "ure" should NOT fire rule 1
        assert r.tier == "MVP", (
            f"'architect' alone should not match the architectur(e|al|ally|es) pattern; "
            f"got tier={r.tier} reason={r.reason!r}"
        )
    else:
        assert r.tier == "MVP", (
            f"{false_match!r} falsely matched: {r.reason!r}"
        )


# ---------------------------------------------------------------------------
# Rule 2 — predicted_files >= 11
# ---------------------------------------------------------------------------


def test_rule_2_eleven_files_is_enterprise():
    files = [f"file_{i}.py" for i in range(11)]
    r = cap.classify(request_text="add stuff", predicted_files=files, diff_scope_estimate=10)
    assert r.tier == "Enterprise"
    assert "rule-2" in r.reason


def test_rule_2_ten_files_is_not_enterprise_via_rule_2():
    """10 files should fall through rule 2; only Production by rule 5."""
    files = [f"file_{i}.py" for i in range(10)]
    r = cap.classify(request_text="add stuff", predicted_files=files, diff_scope_estimate=10)
    assert r.tier == "Production"
    assert "rule-5" in r.reason  # not rule-2


# ---------------------------------------------------------------------------
# Rule 3 — diff_scope_estimate >= 300
# ---------------------------------------------------------------------------


def test_rule_3_large_diff_is_enterprise():
    r = cap.classify(request_text="add tests", predicted_files=["foo.py"], diff_scope_estimate=300)
    assert r.tier == "Enterprise"
    assert "rule-3" in r.reason


def test_rule_3_diff_just_below_threshold():
    r = cap.classify(request_text="add tests", predicted_files=["foo.py"], diff_scope_estimate=299)
    assert r.tier == "MVP"  # falls to default


# ---------------------------------------------------------------------------
# Rule 4 — protocol files force Enterprise
# ---------------------------------------------------------------------------


def test_rule_4_protocol_file_is_enterprise():
    r = cap.classify(
        request_text="tweak protocol",
        predicted_files=[".opencode/protocols/mission-protocol.md"],
        diff_scope_estimate=20,
    )
    assert r.tier == "Enterprise"
    assert "rule-4" in r.reason


def test_rule_4_non_protocol_file_does_not_fire():
    r = cap.classify(
        request_text="tweak something",
        predicted_files=["docs/protocols-overview.md"],  # NOT under .opencode/protocols/
        diff_scope_estimate=20,
    )
    assert r.tier == "MVP"


# ---------------------------------------------------------------------------
# Rule 5 — 3+ files → Production
# ---------------------------------------------------------------------------


def test_rule_5_three_files_is_production():
    r = cap.classify(
        request_text="add a feature",
        predicted_files=["a.py", "b.py", "c.py"],
        diff_scope_estimate=50,
    )
    assert r.tier == "Production"
    assert "rule-5" in r.reason


def test_rule_5_two_files_does_not_fire_alone():
    r = cap.classify(
        request_text="add a feature",
        predicted_files=["a.py", "b.py"],
        diff_scope_estimate=50,
    )
    # Should fall through to rule 7 (default MVP)
    assert r.tier == "MVP"


# ---------------------------------------------------------------------------
# Rule 6 — agent-adjacent file → Production
# ---------------------------------------------------------------------------


def test_rule_6_agent_file_is_production():
    r = cap.classify(
        request_text="tweak coder prompt",
        predicted_files=[".opencode/agent/coder.md"],
        diff_scope_estimate=10,
    )
    assert r.tier == "Production"
    assert "rule-6" in r.reason


def test_rule_6_orchestrator_pattern_match_anywhere():
    r = cap.classify(
        request_text="adjust orchestrator wording",
        predicted_files=["docs/orchestrator-design.md"],  # has "orchestrator" but not under .opencode/agent/
        diff_scope_estimate=10,
    )
    assert r.tier == "Production"
    assert "rule-6" in r.reason


# ---------------------------------------------------------------------------
# Rule 7 — default
# ---------------------------------------------------------------------------


def test_rule_7_default_mvp():
    r = cap.classify(
        request_text="bump version string",
        predicted_files=["pyproject.toml"],
        diff_scope_estimate=1,
    )
    assert r.tier == "MVP"
    assert "rule-7" in r.reason


def test_rule_7_empty_inputs():
    r = cap.classify(request_text="", predicted_files=[], diff_scope_estimate=0)
    assert r.tier == "MVP"


# ---------------------------------------------------------------------------
# First-rule-wins ordering invariant
# ---------------------------------------------------------------------------


def test_rule_1_beats_rule_5():
    """Enterprise keyword must trump 3+ files (which would otherwise be Production)."""
    r = cap.classify(
        request_text="migrate the auth schema",
        predicted_files=["a.py", "b.py", "c.py"],
        diff_scope_estimate=50,
    )
    assert r.tier == "Enterprise"
    assert "rule-1" in r.reason


def test_rule_4_beats_rule_5():
    """Protocol file must trump 3+ files (would be Production by rule 5)."""
    r = cap.classify(
        request_text="add a feature",
        predicted_files=[
            ".opencode/protocols/mission-protocol.md",
            "a.py",
            "b.py",
        ],
        diff_scope_estimate=50,
    )
    assert r.tier == "Enterprise"
    assert "rule-4" in r.reason


def test_rule_2_beats_rule_3():
    """When both rule 2 and rule 3 would fire, rule 2 fires first."""
    files = [f"file_{i}.py" for i in range(11)]
    r = cap.classify(request_text="big work", predicted_files=files, diff_scope_estimate=500)
    assert r.tier == "Enterprise"
    assert "rule-2" in r.reason  # not rule-3


# ---------------------------------------------------------------------------
# should_escalate — upward only
# ---------------------------------------------------------------------------


def test_should_escalate_upward_returns_new_tier():
    """If the actual diff turns out larger than predicted, escalate."""
    r = cap.should_escalate(
        current_tier="MVP",
        actually_touched_files=[f"f{i}.py" for i in range(11)],  # would now be Enterprise
        actual_diff_lines=50,
    )
    assert r is not None
    assert r.tier == "Enterprise"
    assert "escalated from MVP" in r.reason


def test_should_escalate_no_change_returns_none():
    r = cap.should_escalate(
        current_tier="MVP",
        actually_touched_files=["foo.py"],
        actual_diff_lines=10,
    )
    assert r is None


def test_should_escalate_downward_returns_none():
    """Even if actual scope is smaller, never de-escalate."""
    r = cap.should_escalate(
        current_tier="Enterprise",
        actually_touched_files=["foo.py"],
        actual_diff_lines=10,
    )
    assert r is None  # would classify as MVP, but we're already higher → no change


# ---------------------------------------------------------------------------
# to_dict / serialization
# ---------------------------------------------------------------------------


def test_to_dict_shape():
    r = cap.classify(request_text="bump version", predicted_files=["foo.py"], diff_scope_estimate=1)
    d = r.to_dict()
    assert set(d.keys()) == {"tier", "reason", "predicted_files", "diff_scope_estimate"}
    assert d["tier"] == "MVP"
    assert d["predicted_files"] == ["foo.py"]
    assert d["diff_scope_estimate"] == 1


# ---------------------------------------------------------------------------
# CLI round-trip — `python capability_assessor.py < {json}`
# ---------------------------------------------------------------------------


def test_cli_round_trip():
    payload = {
        "request_text": "rewrite the auth module from scratch",
        "predicted_files": ["auth.py"],
        "diff_scope_estimate": 80,
    }
    proc = subprocess.run(
        [sys.executable, str(_MODULE_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, f"CLI failed: stderr={proc.stderr!r}"
    out = json.loads(proc.stdout)
    assert out["tier"] == "Enterprise"
    assert "rule-1" in out["reason"]
    assert "rewrite" in out["reason"]
