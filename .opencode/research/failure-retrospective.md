# Failure Retrospective: The Memory Gap Tax

> **Date:** 2026-05-13
> **Analyst:** @failure-scientist (qwen3.6-plus)
> **Method:** Scientific Method (Observe → Hypothesize → Test → Conclude → Recommend → Record)
> **Preceded by:** model-scientist (lit survey), efficiency-scientist (crossover analysis), system-scientist (integration spec)

---

## 1. OBSERVE — Data Collection

### 1.1 Error Log Analysis

**File:** `.opencode/error-log.jsonl`
**Entries:** 1 (total)

| # | Type | Agent | Context | Resolved |
|---|------|-------|---------|----------|
| 1 | `agent_stall` | researcher | Perplexity/Sonar stalled with no output on best math model query | No |

**Classification:** The error log exists but is nearly empty. Only 1 entry recorded across the entire project lifetime. This is itself a finding — the logging infrastructure is initialized but barely exercised.

**Error types that COULD have been logged but weren't:**
- The Brain/ deletion incident (lessons.md describes it, but no error-log entry)
- Provider stalls (Cerebras Qwen, Perplexity Sonar — documented in lessons.md only)
- Any reviewer FAIL verdicts
- Any quality gate failures
- Config errors during the restoration mission

### 1.2 Decision Log Analysis

**File:** `.opencode/state/decisions.json`
**Entries:** 1 (total)

| ID | Question | Chosen | By | When |
|----|----------|--------|-----|------|
| d1 | How to fix context loss from compression system? | Structured state directory (.opencode/state/) | orchestrator | 2026-05-01 |

**Assessment:** One decision logged in 2+ weeks of operation. This is grossly underpopulated. The lessons.md file contains 3 manually-written lessons that should have been decision entries:
1. Provider stall mitigation (Cerebras/Perplexity)
2. Exa MCP auth nuance
3. BLOCKED ≠ DEAD rule (Brain/ deletion incident)

### 1.3 World Environment Staleness

**File:** `.opencode/world_env.json`
**Last scan:** 2026-05-02T12:11:48 (11 days stale as of May 13)
**Files indexed:** 3,102
**Total lines:** 1,142,666

**Staleness indicators:**
- The restoration mission (2026-05-13) reinitialized git, restored 22 agent files, fixed 3 code bugs, updated 5 docs — none of these changes are reflected in world_env.json
- File hashes are all from the May 2 snapshot
- The `in_context` flag is only `true` for 4 pinned files

### 1.4 Context Directory — Missing

**Path:** `.opencode/context/*.md`
**Status:** Directory does not exist. Zero files.

The orchestrator prompt (line 117, 354, 406-407, 440) repeatedly instructs agents to read/write `.opencode/context/` files for:
- `project-overview.md` — architecture overview
- `decisions.md` — rationale for each decision
- `conventions.md` — coding conventions
- `feature-<F00X>.md` — feature plans

**None of these files exist.** The entire context system is a ghost — referenced in prompts, designed in protocols, but never materialized on disk.

### 1.5 Consult System — Not Implemented

**Files checked:**
- `.opencode/tools/consult.py` — NOT FOUND
- `.opencode/tools/lcn_read.py` — NOT FOUND
- `.opencode/tools/lcn_write.py` — NOT FOUND
- `.opencode/tools/lcn_client.py` — NOT FOUND

These files appear in `world_env.json` summaries (lines 536-604) but do not exist on disk. The CONSULT-PROTOCOL.md in MagnumOpus/ is a 205-line design specification with zero implementation.

### 1.6 AgentMemory SQLite — Underutilized

**DB:** `~/.local/share/opencode/agent_memory.db`
**Rows:** 10

| Key | Value (truncated) |
|-----|-------------------|
| UI Tech Stack | PySide6 Desktop App with Markdown support |
| Database | Main: opencode.db, Agent: agent_memory.db |
| Key Files | main.py, ui/main_window.py, core/worker.py... |
| mission/smoke-test-01/status | complete |
| mission/smoke-test-01/quality_score | 95 |
| feat-mission-status/files | .opencode/tools/mission_status.py... |
| feat-mission-status/reviewer_score | 95/100 (PASS, 0 retries) |
| system/last_mission_completed | smoke-test-01 on 2026-04-23 |
| efficiency-analysis-jvp-vs-bptt-2026-05-13 | # Efficiency Analysis... |

**Assessment:** 10 rows, mostly basic project metadata. Only 1 mission tracked (smoke-test-01). The restoration mission (RESTORE-2026-05-13, 6 features, all done) was NOT written to memory. The three scientist research findings from this session were NOT written to memory.

### 1.7 Always-Loaded Context — Token Cost

Files loaded into every session's system prompt:

| File | Bytes | ~Tokens |
|------|-------|---------|
| AGENTS.md | 17,142 | 4,285 |
| JANUS-STATE.md | 17,727 | 4,431 |
| .opencode/project-state.md | 4,226 | 1,056 |
| .opencode/opencode.json | 6,312 | 1,578 |
| .opencode/agent/orchestrator.md | 37,248 | 9,312 |
| **TOTAL** | **82,655** | **~20,662** |

Plus AGENTS.md is injected separately by the runtime (another ~4,285 tokens).

### 1.8 Lessons.md — Manual, Not Systematic

**File:** `.opencode/lessons.md`
**Entries:** 3 (all manually written)

| Date | Topic | Could Memory Have Prevented? |
|------|-------|------------------------------|
| 2026-04-30 | Provider stall (Cerebras/Perplexity) | Partially — if error log had entries |
| 2026-04-30 | Exa MCP auth nuance | Yes — if consult system existed |
| 2026-05-01 | Brain/ deleted (BLOCKED ≠ DEAD) | Yes — if PIPELINE.md was consulted |

---

## 2. HYPOTHESIZE — Testable Claims

### H1: Decisions are re-derived every session
**Claim:** If a working memory/consult system existed, then the orchestrator would retrieve prior decisions instead of re-deriving them, saving an estimated 2,000-5,000 tokens per session on re-discovery alone.

### H2: Error patterns repeat because they are not consulted
**Claim:** If the error log were populated and consulted before agent dispatch, then at least 30% of recurring failures (provider stalls, edit-shape-errors, convention violations) could be pre-flagged and avoided.

### H3: The context directory gap is the single largest memory failure
**Claim:** The absence of `.opencode/context/` files means the orchestrator's own instructions reference a system that doesn't exist, causing every agent to operate without project-specific architectural memory.

### H4: world_env.json staleness creates a hidden re-scan tax
**Claim:** Because world_env.json is 11 days stale, the orchestrator must re-scan the project structure on every session start, costing ~10K-20K tokens in file discovery that a fresh index would eliminate.

---

## 3. TEST — Evidence For and Against

### H1: Decisions are re-derived every session

**Supporting evidence:**
- Only 1 decision in decisions.json after 2+ weeks
- The restoration mission had to re-discover the Brain/ deletion lesson (it's in lessons.md but not in any decision log or memory)
- The orchestrator prompt says "Read .opencode/context/decisions.md" — but that file doesn't exist
- 3 lessons in lessons.md are things that were learned the hard way and could have been retrieved
- The restoration mission re-fixed bugs that were previously identified (readout.py:84 operator precedence — this was known from Phase C results)

**Contradicting evidence:**
- AGENTS.md and JANUS-STATE.md ARE loaded every session and contain substantial project knowledge
- The orchestrator does read error-log.jsonl (line 87) — the mechanism exists, just no data
- world_env.json provides file-level summaries that reduce the need for re-scanning

**Verdict:** **CONFIRMED (high confidence).** Decisions are absolutely re-derived. The evidence is the near-empty decision log combined with the existence of lessons that should have been decisions.

### H2: Error patterns repeat because they are not consulted

**Supporting evidence:**
- Error log has 1 entry — there's nothing to consult
- The Brain/ deletion incident was a repeatable error pattern (0 tests pass → delete) that could have been caught
- Provider stalls (Cerebras, Perplexity) are documented in lessons.md but not in error-log.jsonl
- The orchestrator reads error-log.jsonl at session start (line 87) but gets nothing

**Contradicting evidence:**
- With only 1 error logged, there's no statistical basis for "repeating patterns"
- The healing protocol exists and is loaded as a skill — the framework is there
- Some failures are genuinely novel (first-time provider outages)

**Verdict:** **PARTIALLY CONFIRMED (medium confidence).** The error log is too sparse to demonstrate repetition, but the structural gap (errors go to lessons.md, not error-log.jsonl) means patterns cannot be detected even if they exist.

### H3: Context directory gap is the largest memory failure

**Supporting evidence:**
- `.opencode/context/` directory doesn't exist — 0 files
- Orchestrator prompt references it 8+ times (lines 117, 229, 354, 356, 406-407, 440, 444, 461)
- All other agents (coder, reviewer, architect) are told to read it
- CONSULT-PROTOCOL.md specifies 3 mandatory consult injection points that depend on LCN reads
- The entire TWO-MINDS architecture (§3.3, §3.4) depends on this system
- System-scientist's critical discovery: lcn_server.py is Flask+SQLite graph DB with no neural read/write interface for agent data

**Contradicting evidence:**
- AGENTS.md and JANUS-STATE.md serve as partial substitutes
- The project has survived and shipped features without it

**Verdict:** **CONFIRMED (high confidence).** The context directory is the architectural center of the memory system and it doesn't exist. Every agent instruction that references it is a dead reference.

### H4: world_env.json staleness creates re-scan tax

**Supporting evidence:**
- Last scan: May 2, current date: May 13 (11 days stale)
- The restoration mission changed at least 30 files (git init, 22 agent files restored, 3 bug fixes, 5 doc updates)
- world_env.json still has old hashes for all modified files
- The file is 1.1MB with 3,102 entries — re-scanning this is non-trivial

**Contradicting evidence:**
- The orchestrator doesn't necessarily re-scan every session — it may use the cached summaries
- File summaries in world_env.json are still valid for unchanged files
- The 4 pinned files (PIPELINE.md, JANUS-STATE.md, project-state.md, AGENTS.md) are loaded regardless

**Verdict:** **CONFIRMED (medium confidence).** Staleness is real and measurable. The exact token cost of re-scanning depends on whether the orchestrator uses the cache or re-reads files, but the gap is at minimum the cost of detecting what changed (~500-1000 tokens for hash comparisons).

---

## 4. CONCLUDE — Findings

### 4.1 The Memory Gap Quantified

| Metric | Current State | With Working Memory | Delta |
|--------|--------------|---------------------|-------|
| Decisions retrievable | 1 | ~15+ (estimated from lessons + missions) | +14x |
| Error patterns detectable | 0 (1 entry, no patterns) | 3+ (provider stalls, edit-shape, convention violations) | N/A |
| Context files available | 0 of 4 expected | 4 (project-overview, decisions, conventions, feature plans) | +4 files |
| AgentMemory entries | 10 | ~50+ (all missions, features, research findings) | +5x |
| world_env.json freshness | 11 days stale | <1 day (auto-refresh) | 11x fresher |
| Consult queries per session | 0 | 3-15 (pre-plan, pre-dispatch, post-verify) | +3-15 |

### 4.2 Token Cost of Not Remembering

**Per-session overhead:**

| Source | Tokens wasted | Reason |
|--------|--------------|--------|
| Re-reading AGENTS.md (already in system prompt) | ~4,285 | Injected twice: once by runtime, once by file list |
| Re-scanning stale world_env.json entries | ~2,000-5,000 | Detecting what changed since last scan |
| Re-deriving decisions not in decisions.json | ~1,000-3,000 | Each re-discovered decision costs ~500-1500 tokens |
| Re-learning lessons from lessons.md (not consulted) | ~500-1,500 | 3 lessons × ~200-500 tokens each |
| No consult system → no pre-flagged errors | ~500-2,000 | Error recovery costs more than prevention |
| **TOTAL per session** | **~8,285-15,785** | |

**Estimated sessions per week:** 3-5 (based on mission cadence)
**Weekly token waste:** ~25,000-79,000 tokens
**Monthly token waste:** ~100,000-316,000 tokens

At DeepSeek V4-Flash pricing (~$0.07/1M input tokens), this is ~$7-22/month in pure waste. At the orchestrator's model (V4-Pro, ~$0.55/1M), it's ~$55-174/month. The real cost isn't dollars — it's **context window pressure**. Every wasted token is a token that could carry task-relevant information.

### 4.3 Concrete Examples of Memory Failure

**Example 1: Brain/ Deletion (2026-05-01)**
- **What happened:** Orchestrator deleted Brain/ (56 files, 49 tests) because "0 tests pass"
- **What should have happened:** PIPELINE.md says Brain/ is BLOCKED on JAX, not dead
- **Memory that would have prevented it:** A Decision entity "Brain/ is BLOCKED, not DEAD" in LCN, or a Convention "BLOCKED ≠ DEAD" in context/conventions.md
- **Cost:** ~30 minutes of confusion, git restore, lessons write

**Example 2: Provider Stall Repeats (2026-04-30 → ongoing)**
- **What happened:** Cerebras Qwen and Perplexity Sonar stalled
- **What should have happened:** Error logged → consult system flags "Cerebras is flaky" → next session avoids Cerebras
- **Memory that would have prevented it:** Error entity with failure_class=model-routing in LCN, or error-log.jsonl entry
- **Cost:** Each stall costs 1-2 minutes of timeout + retry

**Example 3: Operator Precedence Bug (readout.py:84)**
- **What happened:** Bug fixed in restoration mission F003
- **What should have happened:** This bug was known from Phase C results (RESULTS-PHASE-C.md)
- **Memory that would have prevented it:** Decision entity "readout.py:84 has operator precedence bug" in LCN
- **Cost:** Bug existed from Phase C through restoration — weeks of incorrect results

**Example 4: Empty Context Directory**
- **What happened:** 8+ references to `.opencode/context/` in agent prompts point to nothing
- **What should have happened:** Context files created during Phase F (GUI) or earlier
- **Memory that would have prevented it:** A decision to create context files, tracked in decisions.json
- **Cost:** Every agent dispatch operates without project-specific memory

---

## 5. RECOMMEND — Priority Actions

### P0: Create `.opencode/context/` with 4 seed files (1 hour)

**Why:** This is the single highest-leverage fix. The orchestrator already references these files. Creating them activates the entire consult architecture.

**Files to create:**
1. `project-overview.md` — Summarize AGENTS.md + JANUS-STATE.md into a compact reference
2. `decisions.md` — Migrate the 1 decision from decisions.json + 3 lessons from lessons.md
3. `conventions.md` — Extract from `.opencode/rules/` + AGENTS.md "What NOT to Do" section
4. `feature-active.md` — List current mission features from mission.json

**Rollback:** Delete the directory. No code depends on it yet.

**Estimated impact:** Eliminates 8+ dead references in agent prompts. Enables consult system. Saves ~2,000-4,000 tokens/session.

### P1: Populate error-log.jsonl from lessons.md (30 minutes)

**Why:** The error log has 1 entry but lessons.md has 3 documented failures. Backfilling creates the first detectable patterns.

**Entries to add:**
```json
{"error_type": "provider_stall", "agent_or_tool": "architect", "context": "Cerebras Qwen stalled during architectural design review", "recovery": "Retried with different agent", "resolved": true, "timestamp": "2026-04-30T00:00:00Z"}
{"error_type": "provider_stall", "agent_or_tool": "researcher", "context": "Perplexity Sonar stalled on web research query", "recovery": "Fallback to Exa web search", "resolved": true, "timestamp": "2026-04-30T00:00:00Z"}
{"error_type": "agent_stall", "agent_or_tool": "orchestrator", "context": "Deleted Brain/ (56 files) — conflated BLOCKED with DEAD", "recovery": "git checkout restore, added BLOCKED≠DEAD rule", "resolved": true, "timestamp": "2026-05-01T00:00:00Z"}
```

**Rollback:** Delete the 3 added lines. Original entry preserved.

**Estimated impact:** Creates first error patterns. Enables error pre-flagging. Saves ~500-1,000 tokens/session.

### P2: Wire AgentMemory writes to mission completion (2 hours)

**Why:** The restoration mission (6 features, all done) left no memory trace. The memory-writer agent exists but isn't triggered.

**Change:** In the orchestrator's mission-complete flow, add a step:
```
python .opencode/tools/memory_write.py --mission RESTORE-2026-05-13 --features 6 --status done
```

**Rollback:** Remove the memory_write step. Existing memory entries unaffected.

**Estimated impact:** Every mission leaves a trace. Enables mission-similarity queries. Saves ~1,000-2,000 tokens/session on re-discovery.

### P3: Implement consult.py v0 (SQLite-only, no LCN server) (4-6 hours)

**Why:** System-scientist recommended this. The LCN server is a Flask+SQLite graph DB that doesn't have a neural interface. A simple SQLite read layer would activate the consult protocol immediately.

**Approach:**
- Use `.lcn/lcn.sqlite` as the backing store (already exists)
- Implement `by-file`, `by-failure-class`, and `search` queries
- Wire into orchestrator's session-start flow
- Inject results as markdown section (per CONSULT-PROTOCOL.md)

**Rollback:** Don't wire into orchestrator. consult.py exists but isn't called.

**Estimated impact:** Activates the entire consult architecture. Saves ~3,000-5,000 tokens/session. Prevents repeat errors.

### P4: Auto-refresh world_env.json on session start (1 hour)

**Why:** 11-day staleness means the orchestrator can't trust file hashes.

**Change:** In the orchestrator's session-start flow, check world_env.json age. If >24 hours old, trigger a lightweight re-scan (hash check only, not full content).

**Rollback:** Remove the age check. world_env.json stays stale.

**Estimated impact:** Eliminates stale-hash confusion. Saves ~500-1,000 tokens/session.

---

## 6. RECORD — Summary

### Resilience Score: 22/100

| Dimension | Score | Notes |
|-----------|-------|-------|
| Error logging | 10/100 | 1 entry in 2+ weeks |
| Decision tracking | 15/100 | 1 decision, 3 lessons not migrated |
| Context system | 0/100 | Directory doesn't exist |
| Consult system | 0/100 | No implementation |
| Memory writes | 25/100 | 10 rows, mostly metadata |
| File freshness | 30/100 | world_env.json 11 days stale |
| Agent dispatch memory | 20/100 | Agents told to read files that don't exist |

### Key Finding

**JANUS has a fully designed memory architecture (LCN, consult protocol, context directory, error logging, lessons, AgentMemory) but almost none of it is wired into the orchestrator's decision flow.** The system-scientist's recommendation to "activate SQLite v0 entity store now, defer neural to post-Phase-C validation" is confirmed by this analysis. The gap is not architectural — it's implementation. The design documents exist (CONSULT-PROTOCOL.md, TWO-MINDS.md, failure-classes.md). The tools mostly exist (error_logger.py, mission_status.py, world_env.py). The connections between them do not.

### Confidence Ratings

| Finding | Confidence | Evidence Strength |
|---------|-----------|-------------------|
| Decisions re-derived every session | HIGH | 1 decision in 2+ weeks, 8+ dead references |
| Error patterns not consulted | MEDIUM | Only 1 error logged, insufficient for patterns |
| Context directory is largest gap | HIGH | 0 files, 8+ references in prompts |
| world_env.json staleness costs tokens | MEDIUM | 11 days stale, exact re-scan cost depends on behavior |
| Token waste 8K-16K/session | MEDIUM | Based on file sizes and typical re-derivation costs |
| SQLite v0 would activate consult system | HIGH | Design exists, only wiring needed |

---

*Report generated by @failure-scientist using scientific-method protocol.*
*Next step: Orchestrator reviews findings, prioritizes P0-P4 actions.*
