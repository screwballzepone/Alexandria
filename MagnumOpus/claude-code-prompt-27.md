# JANUS Smoke Test -- Attempt 12 (DeepSeek V4-Flash)

**Goal**: verify batch 24 seam fixes land >=18/25 PASS, unlocking Phase 6.1.
**Target**: 18-22/25. Minimum 18/25 to pass the gate.

**Model routing** (2026-04-26 pivot to V4-Flash -- V3.2 worked but ran out
of wall-clock at ~73 min before seam scorecard):

- `orchestrator` now uses `deepseek/deepseek-v4-flash`.
- `opencode.json` default `"model"` is `deepseek/deepseek-v4-flash`.
- Sub-agents (test-writer, reviewer, etc.) run on whatever their agent
  frontmatter specifies (Gemini 2.5 Flash, Grok, etc.) -- unchanged.
- **Context**: V4-Flash has a 1M-token context window and ultra-low
  latency. No per-minute TPM cliff. Parallel sub-agent dispatch is fine
  for correctness reasons; no artificial spacing needed for rate limits.
- Title-gen runs on `cerebras/llama3.1-8b` (separate bucket) -- does
  not route through DeepSeek and does not count against V4-Flash budget.

---

## Mission

You are the primary orchestrator for JANUS's end-to-end pipeline smoke
test. Read `.opencode/mission.json` -- the mission `smoke-test-01` has
one pending feature: `feat-mission-status`. The feature was previously
shipped on branch `mission/smoke-test-01` (merged or stashed; verify),
but this attempt re-runs the full mission pipeline against a reset
planning state to observe every seam end-to-end.

**Execute the SESSION START -> mission-protocol.md pipeline exactly as
specified.** Do not skip SESSION START, even though this prompt says
"execute per mission-protocol.md" -- orchestrator.md's SESSION START
section is MANDATORY per the [WARN] block at its top.

---

## CRITICAL: autonomous-execution directive

This is an **autonomous multi-turn pipeline**, not a Q&A. You will:
1. Emit Seam 0 below (one line).
2. **Immediately on the SAME turn or the next turn**, begin tool calls
   to read `.opencode/mission.json`, load `mission-protocol.md`, and
   start the SESSION START sequence per `orchestrator.md`.
3. Continue making tool calls and dispatching sub-agents through all
   25 seams without pausing for user confirmation.
4. Stop ONLY when (a) you have emitted the `=== SEAM REPORT ===` block
   defined under "Acceptance criteria", or (b) a stop condition under
   "Stop conditions" fires.

Do NOT stop after Seam 0. Do NOT ask "would you like me to continue?"
Do NOT summarize this prompt back to the user. The user is not in the
loop -- this runs unattended. The ONLY successful exit is the seam
report. Anything else = FAIL.

If you find yourself about to emit a single short message and stop,
that is a known failure mode (prior attempts emitted Seam 0 with ~25
tokens output and `reason: stop`, never started the loop). Override
that instinct: keep going.

---

## Pre-flight: identify yourself

**Seam 0** -- before any other work, emit one line:
`MODEL: <your-actual-model-id>`

Introspect what you are actually running on. Do NOT parrot a model name
from this prompt -- the prompt contains historical model names for
context and they may not match your current routing. If no introspection
API is available, infer from your system prompt's `model:` frontmatter
field or from tool response metadata. Report whatever model is actually
answering.

Do NOT halt based on the Seam 0 model name -- all valid DeepSeek,
Gemini, and Anthropic models are acceptable orchestrators. Only halt if
the model reported is `cerebras/qwen-3-235b-a22b-instruct-2507` (that
model has a known 30K TPM ceiling that makes the pipeline impossible to
complete -- it should not be routed here any more).

**After emitting Seam 0, immediately make your first tool call** -- do
not wait, do not stop, do not ask. The natural first call is
`read .opencode/mission.json` per Seam 7.

---

## Seam observation requirements

Emit log lines at each seam so the post-run seam scorer can grade them.
The batch 24 fixes to `orchestrator.md` added explicit log statements
for seams 1-6 -- do not remove or rephrase them. Additional seams needed
for observability:

- Seam 6: after classifying tier, log `TIER: <tier> -- <reason>`.
- Seam 7: after loading `mission.json`, log
  `MISSION: loaded smoke-test-01, status=<status>, next-feature=<id>`.
  Then set status to `in_progress` and log the transition.
- Seam 12: when running quality_gate.py directly, log its JSON output
  verbatim.
- Seam 15: when committing the feature, use
  `python .opencode/tools/git_ops.py commit "<message>" <file1> <file2>`
  with explicit file paths. NEVER invoke the bare `commit` form that
  falls back to `git add -A`.
- Seam 17: before merging the feature branch, log
  `MERGE: feat/feat-mission-status -> mission/smoke-test-01` and confirm
  no untracked files exist in the worktree via `git_ops.py is-clean`.
- Seams 20-25: emit explicit log lines (`SEAM 20: quality_metrics
  recorded`, etc.) so session-end work is observable.

---

## Constraints

- **Model**: no CLI override this run. Rely on opencode.json + agent
  frontmatter. Sub-agent dispatch should use whatever model the agent's
  frontmatter specifies -- don't force anything.
- **Commit hygiene**: feature commit = only the feature files. Docs
  commit = only the docstring changes. Session-end housekeeping
  (log artifacts, mission.json, resume.json) = separate `chore` commit
  at the end, never bundled into feature commits.
- **Smoke-test artifacts**: everything under
  `MagnumOpus/smoke-test-artifacts/` is gitignored -- do NOT attempt to
  stage those paths.
- **Permission**: `opencode serve` was started with
  `"permission": {"external_directory": "allow"}` in opencode.json.
  Sub-agent sessions inherit this. If any step hits an
  `external_directory: ask` prompt, HALT -- the fix regressed.
- **Rate-limit awareness**: DeepSeek V4-Flash has a 1M-token context
  window and ultra-low latency. No per-minute TPM cliff equivalent to
  the old Cerebras constraint. Keep parallel-when-independent dispatch
  logic intact for correctness, but no artificial 30s spacing is needed.
  Title-gen runs on `cerebras/llama3.1-8b` (separate bucket, 30 RPM)
  and does not count against DeepSeek budget.

---

## Acceptance criteria

On completion emit a final message with:

1. `=== SEAM REPORT ===` header
2. A 26-row table (seams 0-25) with columns: # | Status
   (PASS/DEGRADED/FAIL/NOT_RUN) | Evidence (one line, pointing at
   log/commit/file)
3. Summary line: `X PASS, Y DEGRADED, Z FAIL, W NOT_RUN`
4. Phase 6.1 gate verdict: `PASS if X >= 18 (out of seams 1-25, excluding
   seam 0 pre-flight), else FAIL`
5. Commit hash of the feature commit, docs commit, and session-end
   housekeeping commit.
6. Any deviations from mission-protocol.md with rationale.
7. **Model-routing note**: confirm which models actually answered each
   agent dispatch (orchestrator, @coder, @reviewer, @documenter,
   @test-writer). If any answered with an unexpected provider, flag it.

---

## Stop conditions

- Untracked (non-gitignored) files present at start -> HALT. Untracked
  files could accidentally enter a feature commit. Check with:
  `git ls-files --others --exclude-standard`. If empty, proceed.
  Modifications to tracked files are NOT a halt condition: they're
  visible to you (read them as-is), intentional (the user staged them
  on purpose, e.g. an in-flight prompt edit), and the runner script
  handles ones it cares about (e.g. mission.json reset in Pre-run reset
  above). Earlier versions of this stop condition halted on any modified
  file, which created a paradox with the runner's intentional
  mission.json reset; that paradox is removed.
- Seam 0 shows `cerebras/qwen-3-235b-a22b-instruct-2507` -> HALT (that
  model's TPM ceiling makes pipeline completion impossible).
- Any sub-agent session hits external_directory permission prompt -> HALT.
- Feature commit contains > 5 files -> HALT (Finding C regression).
- Merge conflict on seam 17 -> HALT, emit partial seam report + git
  state + stash contents + stash pop result.
- Any step runs > 10 minutes without a tool call -> HALT, emit what you
  have.
- Total runtime > 45 minutes -> HALT, emit partial seam report.
- **Context compaction triggered during mission** (>50K tokens): continue
  but log `COMPACTION: triggered at turn N` as a seam-report note. Not
  a halt condition unless it fires twice in one run.

HALT means: emit the seam scorecard as far as you got, plus a ROOT
CAUSE section explaining which stop condition fired and what evidence
you observed. Do NOT continue past a stop condition in the hopes of
recovery -- the post-hoc analysis is more valuable than a partial
recovery attempt.

---

## Pre-run reset (runner script)

The outer runner executes `MagnumOpus/reset_mission.py` before invoking
the orchestrator. It sets mission.json back to planning state and
resets feat-mission-status to pending. Also runs
`git clean -fd MagnumOpus/smoke-test-artifacts/` to clear prior log
artifacts (gitignored, but may linger on disk).

---

## Post-run artifacts

Save to `MagnumOpus/smoke-test-artifacts/`:
- `server-b27-a12.log` -- full `opencode serve` output
- `orchestrator-b27-a12.log` -- full orchestrator trace
- `seam-report-b27-a12.md` -- your final seam scorecard in markdown

These are gitignored; they exist for post-run forensics only.

---

## Why this batch exists (context for the orchestrator)

Batch 24 (commit `847fe96`, 2026-04-23) patched findings B/C/D/E from
attempt-9 to unblock seams 1-5, 12, 15, 17. Measured under Sonnet 4.6.

Attempt 10 (batch 26, 2026-04-24) pivoted orchestrator model to Gemini
2.5 Flash free tier after Anthropic costs spiked. Gemini 2.5 Flash
emitted Seam 0 correctly but stalled mid-pipeline with `reason: other`
and 0 output tokens -- suspected OpenCode + weak-model recursive-loop
failure mode.

Attempt 11 (batch 27, 2026-04-24) pivoted to Cerebras Qwen 3 235B A22B
Instruct. Qwen hit the 30K TPM ceiling immediately -- the orchestrator
system prompt alone consumes ~28K tokens, leaving no room for tool
history. Six consecutive `token_quota_exceeded` 429s, no progress.
Reverted. Then re-pivoted to DeepSeek V3.2 (paid, proven on sub-agents)
which worked but ran ~73 min wall-clock before the user killed it --
V3.2's slower generation speed and accumulated context made each turn
progressively slower.

**This attempt (12)** uses DeepSeek V4-Flash: 1M context window, ultra-
low latency, agentic-reasoning tuning, $0.14/$0.28 per M tokens
(cheaper than V3.2). Launched 2026-04-24. Expected runtime: 15-30 min.

Before attempt 11, 230 non-ASCII chars were normalized across 15
config/prompt files (em-dashes, arrows, >=, [WARN], etc.) to eliminate
the UTF-8/Windows-1252 mismatch that OpenCode's read tool was garbling
on Windows.
