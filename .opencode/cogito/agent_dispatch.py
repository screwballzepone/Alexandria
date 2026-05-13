#!/usr/bin/env python3
"""
CogitoCode Agent Dispatch — deterministic agent routing from frontmatter.

CLI commands:
  find <phase> ["<task_description>"]  — resolve phase to best agent
  manifest                             — human-readable agent catalog
  list                                 — JSON array of all agents

The phase system replaces the old instruction-based tier dispatch.
Orchestrator calls this tool instead of reasoning from prompt rules.
"""

import argparse
import json
import re
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
AGENT_DIR = BASE_DIR / "agent"

# Phase → role lookup
PHASE_ROLE_MAP: dict[str, str] = {
    "understand": "exploration",
    "understand:research": "research",
    "plan:design": "design_review",
    "plan:preflight": "code_review",
    "build:test": "testing",
    "build:code": "code_gen",
    "verify": "code_review",
    "verify:math": "code_review",
    "cleanup": "post_mission",
    "special:prompt": "special_purpose",
    "special:vision": "special_purpose",
    "special:onboard": "special_purpose",
    "special:depcheck": "special_purpose",
}

# Phase → preferred agent name (deterministic, overrides role-based ordering)
PHASE_AGENT_MAP: dict[str, str] = {
    "understand": "explorer",
    "understand:research": "researcher",
    "plan:design": "architect",
    "plan:preflight": "nano-coder",
    "build:test": "test-writer",
    "build:code": "coder",
    "verify": "reviewer",
    "verify:math": "math-verifier",
    "special:prompt": "prompt-writer",
    "special:vision": "vision",
    "special:onboard": "onboarder",
    "special:depcheck": "dependency-scout",
}

# Research keywords in task description → prefer researcher over explorer
RESEARCH_KEYWORDS = {"api", "docs", "how to", "web", "external", "npm", "package"}

# Math verification keywords → prefer math-verifier over reviewer
MATH_KEYWORDS = {"gradient", "taylor", "numerical", "invariant"}

# Cleanup sequence order
CLEANUP_SEQUENCE = [
    "documenter",
    "security-auditor",
    "lessons",
    "meta-agent",
    "memory-writer",
]


def _parse_frontmatter(md_path: Path) -> dict:
    """Parse YAML frontmatter from --- delimited block. Returns dict."""
    meta: dict = {}
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return meta

    # Match content between first two --- markers
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return meta

    yaml_block = m.group(1)
    for line in yaml_block.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # Simple boolean parsing
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        meta[key] = value

    return meta


def _read_all_agents() -> list[dict]:
    """Parse frontmatter from every .md file in AGENT_DIR."""
    agents: list[dict] = []
    if not AGENT_DIR.is_dir():
        print(f"WARNING: Agent directory not found: {AGENT_DIR}", file=sys.stderr)
        return agents

    for md_file in sorted(AGENT_DIR.glob("*.md")):
        meta = _parse_frontmatter(md_file)
        # Add filename-derived name (strip .md)
        meta["name"] = md_file.stem
        if "role" not in meta or "phase" not in meta:
            print(
                f"WARNING: {md_file.name} missing 'role' or 'phase' — skipping",
                file=sys.stderr,
            )
            continue
        agents.append(meta)

    return agents


def _find_by_role(agents: list[dict], role: str) -> list[dict]:
    """Return all agents matching a given role."""
    return [a for a in agents if a.get("role") == role]


def cmd_find(phase: str, task_description: str | None) -> dict:
    """Resolve phase to the best agent. Returns dict to serialize as JSON."""
    agents = _read_all_agents()
    if not agents:
        return {"agent": None, "error": "No agent data available"}

    # Determine effective phase key (with or without sub-phase)
    effective_phase = phase

    # For 'understand', check if task_description suggests research
    if phase == "understand" and task_description:
        lower_desc = task_description.lower()
        if any(kw in lower_desc for kw in RESEARCH_KEYWORDS):
            effective_phase = "understand:research"

    # For 'verify', check if task_description suggests math
    if phase == "verify" and task_description:
        lower_desc = task_description.lower()
        if any(kw in lower_desc for kw in MATH_KEYWORDS):
            effective_phase = "verify:math"

    # Look up target role
    target_role = PHASE_ROLE_MAP.get(effective_phase)

    # If no sub-phase match, fall back to base phase
    if target_role is None:
        base_phase = phase.split(":")[0]
        target_role = PHASE_ROLE_MAP.get(base_phase)

    if target_role is None:
        return {
            "agent": None,
            "error": f"No agent for phase '{phase}'",
            "suggestion": "Use orchestrator directly",
        }

    # Special case: cleanup returns a sequence
    if target_role == "post_mission":
        return {
            "agent": CLEANUP_SEQUENCE[0],
            "role": "post_mission",
            "phase": "cleanup",
            "agents": CLEANUP_SEQUENCE,
            "writes_code": True,
            "confidence": 0.95,
            "note": "Cleanup: run agents in sequence",
        }

    # Determine preferred agent name from phase map
    preferred_name = PHASE_AGENT_MAP.get(effective_phase)

    # Find matching agents
    candidates = _find_by_role(agents, target_role)
    if not candidates:
        return {
            "agent": None,
            "error": f"No agent with role '{target_role}' for phase '{phase}'",
            "suggestion": "Use orchestrator directly",
        }

    # Select agent: prefer name match from phase map, else first candidate
    chosen = candidates[0]
    if preferred_name:
        named_matches = [c for c in candidates if c.get("name") == preferred_name]
        if named_matches:
            chosen = named_matches[0]

    # Determine fallback
    fallback = _get_fallback(chosen, candidates, effective_phase)

    result = {
        "agent": chosen.get("name"),
        "model": chosen.get("model", "unknown"),
        "role": chosen.get("role"),
        "writes_code": bool(chosen.get("writes_code", False)),
        "confidence": 0.95,
    }
    if fallback:
        result["fallback"] = fallback

    return result


def _get_fallback(chosen: dict, candidates: list[dict], phase: str) -> str | None:
    """Return a fallback agent name if the primary is likely to stall."""
    name = chosen.get("name", "")

    # Architect stalls are common (Cerebras provider)
    if name == "architect":
        reviewer = [c for c in candidates if c.get("name") == "reviewer"]
        return "reviewer" if reviewer else None

    # Coder stalls → nano-coder can do minimal work
    if name == "coder":
        return "nano-coder"

    # Explorer stalls → researcher can approximate
    if name == "explorer":
        return "researcher"

    return None


def cmd_manifest() -> str:
    """Return a human-readable agent table."""
    agents = _read_all_agents()
    if not agents:
        return "No agents found."

    # Column widths
    name_w = max(len(a.get("name", "")) for a in agents) + 2
    role_w = max(len(a.get("role", "")) for a in agents) + 2
    phase_w = max(len(a.get("phase", "")) for a in agents) + 2
    model_w = max(len(str(a.get("model", ""))) for a in agents)

    name_w = max(name_w, len("AGENT"))
    role_w = max(role_w, len("ROLE"))
    phase_w = max(phase_w, len("PHASE"))
    model_w = max(model_w, len("MODEL"))

    sep = "─" * name_w + " ─" + "─" * role_w + " ─" + "─" * phase_w + " ────  ─" + "─" * model_w

    lines = []
    lines.append(
        f"{'AGENT':<{name_w}} {'ROLE':<{role_w}} {'PHASE':<{phase_w}} WRITES  {'MODEL':<{model_w}}"
    )
    lines.append(sep)

    post_mission_count = 0
    special_count = 0

    for a in agents:
        name = a.get("name", "")
        role = a.get("role", "")
        phase = a.get("phase", "")
        writes = "yes" if a.get("writes_code") else "no "
        model = a.get("model", "")

        if phase == "cleanup":
            post_mission_count += 1
        if role == "special_purpose":
            special_count += 1

        lines.append(
            f"{name:<{name_w}} {role:<{role_w}} {phase:<{phase_w}} {writes}    {model:<{model_w}}"
        )

    total = len(agents)
    footer = f"\n{total} agents total | {post_mission_count} post-mission | {special_count} special-purpose"
    lines.append(footer)

    return "\n".join(lines)


def cmd_list() -> str:
    """Return JSON array of all agents."""
    agents = _read_all_agents()
    # Clean up: keep only relevant fields for JSON output
    output = []
    for a in agents:
        output.append(
            {
                "name": a.get("name"),
                "role": a.get("role"),
                "phase": a.get("phase"),
                "writes_code": bool(a.get("writes_code", False)),
                "model": a.get("model", "unknown"),
                "description": a.get("description", ""),
            }
        )
    return json.dumps(output, indent=2, ensure_ascii=False)


def main(argv=None) -> None:
    """Entry point with argparse dispatch."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="Agent Dispatch — deterministic agent routing from frontmatter."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # find
    p_find = sub.add_parser("find", help="Resolve phase to best agent")
    p_find.add_argument("phase", help="Phase key (e.g. build:code, verify)")
    p_find.add_argument(
        "task_description",
        nargs="?",
        default=None,
        help="Optional task description for sub-phase detection",
    )

    # manifest
    sub.add_parser("manifest", help="Print human-readable agent table")

    # list
    sub.add_parser("list", help="Print JSON array of all agents")

    parsed = parser.parse_args(argv)

    if parsed.command == "find":
        result = cmd_find(parsed.phase, parsed.task_description)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif parsed.command == "manifest":
        print(cmd_manifest())
    elif parsed.command == "list":
        print(cmd_list())


if __name__ == "__main__":
    main()
