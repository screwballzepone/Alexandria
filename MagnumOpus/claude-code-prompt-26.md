# Batch 26 -- Smoke Test Attempt 10 (Gemini 2.5 Flash)

**Goal**: verify batch 24 seam fixes land >=18/25 PASS, unlocking Phase 6.1.
**Target**: 20-22/25 (projected under Sonnet; first Gemini run establishes
new baseline). Minimum 18/25 to pass the gate.

**Model routing** (2026-04-24 pivot -- Anthropic removed due to cost):
- `orchestrator` now uses `google/gemini-2.5-flash` (escalated from 3.1
  Flash Lite after the first run proved Lite too weak to execute
  multi-step orchestration -- it read the prompt and summarized it
  instead of following it).
- `architect` uses `google/gemini-2.5-flash` (low-volume, needs stronger
  reasoning).
- `opencode.json` default `"model"` is `google/gemini-2.5-flash`.
- Sub-agents (test-writer, reviewer, etc.) already run on DeepSeek/Grok
  per their frontmatter -- unchanged.
- **No `--model` CLI override needed** -- if Gemini honors frontmatter,
  Finding A's workaround is moot. If it doesn't, LOG which model actually
  answered and HALT so we can diagnose.
- **Rate limit constraint**: 2.5 Flash free tier is 5 RPM / 20 RPD. One
  full smoke-test run fits comfortably but leaves little headroom for
  same-day retries.

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

## Pre-flight: identify yourself

**Seam 0 (new)** -- before any other work, emit one line:
`MODEL: <your-model-id>` (e.g., `MODEL: google/gemini-2.5-flash`).
Use whatever introspection is available; if none, report the best guess
based on system context. This establishes whether opencode.json routing
actually landed on Gemini.

If you observe that you are NOT running under a `google/*` model, HALT
immediately and report: "Model routing failed -- expected google/gemini-*,
got <actual>." This is a Finding-A regression under new routing config.

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
  frontmatter specifies (test-writer -> deepseek, etc.) -- don't force
  anything.
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

- Working tree not clean at start -> HALT, do not proceed.
- Seam 0 shows non-google/* orchestrator model -> HALT (routing regression).
- Any sub-agent session hits external_directory permission prompt -> HALT.
- Feature commit contains > 5 files -> HALT (Finding C regression).
- Merge conflict on seam 17 -> HALT, emit partial seam report + git
  state + stash contents + stash pop result.
- Any step runs > 10 minutes without a tool call -> HALT, emit what you
  have.
- Total runtime > 30 minutes -> HALT.
- **Gemini rate limit hit** (429 from Google): HALT immediately, emit
  partial report. Note: 2.5 Flash free tier is 5 RPM / 20 RPD -- one full
  smoke-test run stays under the RPD cap but can bump the RPM ceiling
  during rapid dispatch bursts. If it fires, that's recoverable (wait a
  minute and retry) but still counts as HALT for this attempt.

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
- `server-b26-a10.log` -- full `opencode serve` output
- `orchestrator-b26-a10.log` -- full orchestrator trace
- `seam-report-b26-a10.md` -- your final seam scorecard in markdown

These are gitignored; they exist for post-run forensics only.

---

## Why this batch exists (context for the orchestrator)

Batch 24 (commit `847fe96`, 2026-04-23) patched findings B/C/D/E from
the attempt-9 run to unblock seams 1-5, 12, 15, 17. It was measured
under Sonnet 4.6. Between batch 24 and this run, Anthropic API spend
hit USD $3.50 in one day on Sonnet 4.6+4.5 combined -- not sustainable
for iterative smoke tests. First pivoted to Gemini 3.1 Flash Lite
(500 RPD) but that model proved too weak to execute multi-step agent
instructions -- on its first attempt (2026-04-24 ~11:02 UTC) it read
the prompt and produced a 74-token summary instead of running the
mission. Escalated to Gemini 2.5 Flash (5 RPM / 20 RPD, free tier).
This run establishes the Gemini 2.5 Flash baseline.

If Gemini fails seams that Sonnet passed in batch 24, we learn something
about Gemini's ability to follow the orchestration protocol. If Gemini
passes at equal or better rates, Phase 6.1 unlocks AND we've cut the
orchestration cost to zero. Either outcome is informative.
