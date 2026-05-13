# Lessons Learned

> Auto-appended by @lessons after each mission. Format: date, context, lesson.

## 2026-04-30 — Provider stall: Cerebras Qwen + Perplexity Sonar unresponsive

**Context**: During competitive analysis implementation session, @architect (cerebras/qwen-3-235b) and @researcher (perplexity/sonar-reasoning-pro) both stalled with no output on multiple dispatches. Cerebras already had `timeout: 600000` configured — the issue is provider-level request hanging, not client-side timeout. The OpenCode `task` tool has no configurable timeout for subagent dispatches.

**Impact**: Architectural design review and web research tasks silently failed, requiring orchestrator to retry with different agents or skip those steps.

**Mitigation applied**:
- Added `timeout: 600000` to Perplexity provider (was missing)
- Added orchestrator instruction: if @architect or @researcher produce no output, report stall and proceed

**Watch out for**: Cerebras Qwen provider is flaky — prefer @reviewer for design review when architect stalls. Perplexity Sonar is similarly unreliable for research. Consider switching @architect to openrouter/qwen or @researcher to openrouter/sonar as fallback paths.

## 2026-04-30 — Exa MCP auth nuance

**Context**: Exa MCP server at `https://mcp.exa.ai/mcp` uses OAuth (browser sign-in), not API key. The `Authorization: Bearer {env:EXA_API_KEY}` header in opencode.json is for direct API use (Python SDK), not the MCP server. The MCP worked anyway — OpenCode handled OAuth under the hood. Confirmed after setting env var and testing.

**Watch out for**: Don't assume MCP servers use API key auth just because the header is present. Exa MCP uses OAuth, and the env var is only needed for direct SDK calls.

## 2026-05-01 — Brain/ deleted in codebase audit: BLOCKED ≠ DEAD

**Context**: During a project-wide codebase health audit, the orchestrator flagged `Brain/` (56 tracked files, LCN research project, 49 tests) as "dead code" and deleted it. The Brain was PIPELINE.md Phase A–C — the central bet of the two-minds architecture. JANUS-STATE.md explicitly said `BLOCKED — needs JAX + lcn_jvp package`. The orchestrator conflated "0 tests pass" with "abandoned."

**Impact**: The most ambitious subsystem in the project was deleted from disk. Restored from git (`git checkout b5512ec -- Brain/`). No permanent data loss, but wasted time and confusion.

**Root cause**: Neither the orchestrator nor the explorer checked PIPELINE.md or JANUS-STATE.md before classifying Brain/ as "dead." Both agents applied "not working → delete" logic that belongs on CI build artifacts, not research subsystems.

**Mitigation applied**:
- Orchestrator: added "BLOCKED ≠ DEAD" rule — before any deletion in a health audit, grep PIPELINE.md/JANUS-STATE.md/mission.json for the path. If referenced in a phase or marked BLOCKED, skip deletion.
- Explorer: added code state classification table (DEAD / BLOCKED / ABANDONED / TEST ARTIFACT). Blocked code must be reported in its own section, never mixed with dead code.
- Project-state.md: added cleanup safety rule.

**Watch out for**: "Doesn't work right now" is not the same as "should be deleted." Read the pipeline docs before touching anything. Blocked research code is still code — it's waiting, not garbage.
