"""capability_assessor.py — tier classifier (reference implementation)

Authority: MagnumOpus/TIER-CLASSIFIER.md

Runs at the `classify` phase of every mission. Returns a tier
(MVP/Production/Enterprise) plus a reason field naming the rule that
fired, so mis-tiering is auditable.

This file lives in MagnumOpus/reference/ as specification code. Move to
`.opencode/tools/capability_assessor.py` once the orchestrator is ready
to consume its output.

Design: deterministic rules first, no heuristics. A classifier that
silently makes judgement calls is harder to debug than one whose wrong
answer you can trace to a specific rule number.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from typing import Any


# Phrases that force Enterprise tier regardless of file count. Each entry is
# (pattern, human-readable label). Patterns use word-boundary regex with
# stem variants so "migrate/migrated/migration/migrating" all match the
# same rule.
ENTERPRISE_PATTERNS = (
    (re.compile(r"\bmigrat(e|es|ed|ing|ion|ions)\b", re.I), "migration"),
    (re.compile(r"\brewrit(e|ing|ten|es)\b", re.I), "rewrite"),
    (re.compile(r"\barchitectur(e|al|ally|es)\b", re.I), "architecture"),
    (re.compile(r"\bdeprecat(e|es|ed|ing|ion)\b", re.I), "deprecate"),
    (re.compile(r"\bbreaking\s+change(s)?\b", re.I), "breaking change"),
    (re.compile(r"\bnew\s+primary\s+agent\b", re.I), "new primary agent"),
)

# Paths whose mere touch forces a minimum tier.
PROTOCOL_SCOPE_PREFIX = ".opencode/protocols/"
AGENT_SCOPE_PREFIX = ".opencode/agent/"
ORCHESTRATOR_PATTERN = re.compile(r"orchestrator")


@dataclass
class TierResult:
    tier: str  # "MVP" | "Production" | "Enterprise"
    reason: str
    predicted_files: list[str]
    diff_scope_estimate: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "reason": self.reason,
            "predicted_files": self.predicted_files,
            "diff_scope_estimate": self.diff_scope_estimate,
        }


def _contains_enterprise_keyword(text: str) -> str | None:
    """Return the human-readable label of the first Enterprise pattern that
    matches the text, or None. Uses word-boundary regex with stem variants
    so "migrate/migrated/migration" all fire the same rule.
    """
    for pattern, label in ENTERPRISE_PATTERNS:
        if pattern.search(text):
            return label
    return None


def classify(
    request_text: str,
    predicted_files: list[str],
    diff_scope_estimate: int,
) -> TierResult:
    """Apply TIER-CLASSIFIER.md rules in order. First rule that fires wins.

    Rules:
      1. Enterprise keyword in request_text → Enterprise
      2. predicted_files >= 11 → Enterprise
      3. diff_scope_estimate >= 300 → Enterprise
      4. any file under .opencode/protocols/ → Enterprise
      5. predicted_files >= 3 → Production
      6. any file under .opencode/agent/ or matching orchestrator* → Production
      7. otherwise → MVP
    """
    predicted_files = list(predicted_files)

    # Rule 1
    kw = _contains_enterprise_keyword(request_text)
    if kw:
        return TierResult("Enterprise", f"rule-1 (matched: {kw!r})",
                          predicted_files, diff_scope_estimate)

    # Rule 2
    if len(predicted_files) >= 11:
        return TierResult("Enterprise",
                          f"rule-2 (predicted_files={len(predicted_files)})",
                          predicted_files, diff_scope_estimate)

    # Rule 3
    if diff_scope_estimate >= 300:
        return TierResult("Enterprise",
                          f"rule-3 (diff_scope_estimate={diff_scope_estimate})",
                          predicted_files, diff_scope_estimate)

    # Rule 4
    protocol_hits = [p for p in predicted_files if p.startswith(PROTOCOL_SCOPE_PREFIX)]
    if protocol_hits:
        return TierResult("Enterprise",
                          f"rule-4 (protocol files: {protocol_hits})",
                          predicted_files, diff_scope_estimate)

    # Rule 5
    if len(predicted_files) >= 3:
        return TierResult("Production",
                          f"rule-5 (predicted_files={len(predicted_files)})",
                          predicted_files, diff_scope_estimate)

    # Rule 6
    agent_hits = [p for p in predicted_files
                  if p.startswith(AGENT_SCOPE_PREFIX) or ORCHESTRATOR_PATTERN.search(p)]
    if agent_hits:
        return TierResult("Production",
                          f"rule-6 (agent-adjacent: {agent_hits})",
                          predicted_files, diff_scope_estimate)

    # Rule 7
    return TierResult("MVP", "rule-7 (default)",
                      predicted_files, diff_scope_estimate)


def should_escalate(current_tier: str, actually_touched_files: list[str],
                    actual_diff_lines: int) -> TierResult | None:
    """Mid-mission escalation check. TIER-CLASSIFIER.md: escalation is
    upward-only. Returns a new TierResult if escalation is required, else
    None.
    """
    new_tier_result = classify(
        request_text="",  # escalation doesn't re-inspect request
        predicted_files=actually_touched_files,
        diff_scope_estimate=actual_diff_lines,
    )
    order = {"MVP": 0, "Production": 1, "Enterprise": 2}
    if order[new_tier_result.tier] > order[current_tier]:
        new_tier_result.reason = f"escalated from {current_tier}; " + new_tier_result.reason
        return new_tier_result
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Read a JSON {request_text, predicted_files, diff_scope_estimate} from
    stdin, print the classification as JSON."""
    payload = json.load(sys.stdin)
    result = classify(
        request_text=payload.get("request_text", ""),
        predicted_files=payload.get("predicted_files", []),
        diff_scope_estimate=payload.get("diff_scope_estimate", 0),
    )
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
