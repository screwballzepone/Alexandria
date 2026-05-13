# Claude Code Handoff — Session R: Model Fallback Ladder

You are Claude Code (Sonnet) in the user's terminal. Cowork (also Sonnet) handed this work to you to save the weekly Cowork budget. **Stay focused — this is a defensive infrastructure session, not a feature session. Ship the ladder, write the tests, demonstrate it works, stop.**

---

## Why this exists

Over 36 hours we've manually intervened **three times** on smoke-test runs because of model-specific failure modes that the pipeline couldn't recover from:

1. **Cerebras Qwen 3 235B** (attempt 10 prep): runaway `reason:length` after a prompt size threshold, plus repeated `token_quota_exceeded` 429s in a death loop because the system prompt + max_tokens reservation exceeded the 30K TPM cap.
2. **DeepSeek V3.2** (attempt 12 first try): no rate-limit issues but ran out of wall-clock budget at ~73 min before reaching seam scorecard. Slower than expected with accumulated context.
3. **Gemini 2.5 Flash** (attempt 10 historical): emitted Seam 0 then stalled with `reason:other` and 0 output tokens — silent recursive-loop failure documented in opencode community threads.

Plus a related "Qwen-Instruct 'I'm done after Seam 0'" failure where the model emitted 25 output tokens, `reason:stop`, zero tool calls — different cause, same outcome (no seam report).

**Each manual intervention cost ~30-60 minutes of human attention.** The fallback ladder catches these failure modes automatically, restarts with the next-rung model, and lets the user sleep through the run.

The user explicitly proposed this on 2026-04-26 after watching the third pivot of the week. They said: *"I work so if I don't do it in my free time, I will have to do it every night or morning, I prefer to relax after work."*

## Current state (do not re-derive)

- **Phase 6.1 gate**: cleared at 24/25 PASS, 1 DEGRADED, 0 FAIL on attempt 12 (commit `804dea2`, model `deepseek/deepseek-v4-flash`).
- **Master**: clean. All 129 tests passing.
- **Default orchestrator**: `deepseek/deepseek-v4-flash` (V4-Flash, $0.14/$0.28, 1M context, agentic-tuned, launched 2026-04-24).
- **Hard cost rule**: Anthropic models are OFF the JANUS orchestration menu (cost feedback memory, $3.50/day was the trigger). Do NOT include any `anthropic/*` model in the ladder.

## Your job

Build `MagnumOpus/scripts/run_with_fallback.py` — a Python wrapper around `opencode run` that streams the JSON output, detects failure signals, and auto-restarts on the next ladder rung. Plus tests, plus a runner-script update, plus a one-page doc.

---

## Specification

### File layout

| File | Purpose |
|---|---|
| `MagnumOpus/scripts/run_with_fallback.py` | The wrapper. ~300 LOC Python. |
| `tests/test_run_with_fallback.py` | Unit tests for the failure detector. ~200 LOC, no live API. |
| `run_attempt_11.ps1` | Replace its `opencode run` invocation with a call to the wrapper. |
| `MagnumOpus/SESSION-R-FALLBACK-LADDER.md` | One-page operator doc: ladder rungs, failure signals, kill switches, audit log format. |

### The ladder (per current cost rule)

In order of preference. Use `--model` CLI flag to override at restart time — do NOT mutate `opencode.json` between runs (avoids dirtying tree).

```python
LADDER = [
    "deepseek/deepseek-v4-flash",  # rung 1: $0.14/$0.28, 1M context, current default
    "deepseek/deepseek-chat",       # rung 2: V3.2 alias, $0.27/$0.40, 164K context, slower but proven
    "moonshotai/kimi-k2.6",         # rung 3: $0.95/$4.00, 256K context, agentic-tuned, "200-300 sequential tool calls"
]
```

If all three rungs fail, the wrapper exits with a non-zero status and writes a final audit entry. Do NOT add Anthropic, Cerebras (TPM caps), or Gemini (proven to stall) to the ladder.

### Failure signals (detection logic)

The wrapper streams `opencode run --format json` output line by line, parses each event, and watches for:

| Signal | Detection | Notes |
|---|---|---|
| **Length runaway** | `step_finish` event with `reason: "length"` | Model hit max_tokens. Almost always a runaway-generation failure mode. Restart immediately. |
| **Silent stall** | `step_finish` with `reason: "other"` AND `tokens.output: 0` | Gemini-style stall — model returned nothing. Restart immediately. |
| **Seam-0-stop** | `step_finish` with `reason: "stop"` AND `tokens.output < 100` AND zero `tool_use` events on this step AND total elapsed < 60s | Qwen-Instruct "I'm done after Seam 0" pattern. Restart immediately. |
| **TPM/RPM death loop** | 3 consecutive `service=llm ... ERROR` events with `statusCode: 429` AND `code: token_quota_exceeded` (or `rate_limit_exceeded`) within 5 minutes, no successful `step_finish` between them | Provider rate-limit death loop. Restart on next rung. |
| **Wall-clock exceeded** | Total elapsed time > 60 minutes without final `=== SEAM REPORT ===` text | Model is too slow for this pipeline. Restart on faster rung. |
| **Final report** | Text event matches `=== SEAM REPORT ===` | Success. Stop monitoring, let the run complete naturally, exit 0. |

Use a streaming JSON parser (or line-by-line `json.loads`) — opencode emits newline-delimited JSON.

### Restart logic

When a failure signal fires:

1. **Kill the current opencode process tree** via `taskkill /F /T /PID <pid>` on Windows. The user's `core/worker.py` does this same pattern; mimic it.
2. **Reset mission state**: run `python MagnumOpus/reset_mission.py` to put mission.json back to planning state.
3. **Clean smoke artifacts**: `git clean -fd MagnumOpus/smoke-test-artifacts/`.
4. **Append audit entry** (see audit log format below).
5. **Spawn next-rung model** via `opencode run --model <next-rung> --format json --dangerously-skip-permissions <prompt-content>` — same prompt, different model.
6. **Resume monitoring**.

Per-mission cap: max 2 escalations (so max 3 total attempts). After 3 failures, exit non-zero.

### Cost cap

The wrapper sums the `cost` field from each `step_finish` event across all attempts. If cumulative cost exceeds **$0.50**, abort even if no failure signal fired. Configurable via `--max-cost` CLI flag. Default $0.50.

### Audit log format

Write to `MagnumOpus/smoke-test-artifacts/fallback-audit-<timestamp>.json`:

```json
{
  "started_at": "2026-04-26T23:00:00Z",
  "prompt_file": "MagnumOpus/claude-code-prompt-27.md",
  "ladder": ["deepseek/deepseek-v4-flash", "deepseek/deepseek-chat", "moonshotai/kimi-k2.6"],
  "max_cost": 0.50,
  "attempts": [
    {
      "rung": 0,
      "model": "deepseek/deepseek-v4-flash",
      "started_at": "2026-04-26T23:00:00Z",
      "ended_at": "2026-04-26T23:18:00Z",
      "exit_reason": "length-runaway",
      "elapsed_seconds": 1080,
      "cost_estimate": 0.04,
      "evidence": "step_finish part_id=prt_xyz reason=length output_tokens=32000"
    },
    {
      "rung": 1,
      "model": "deepseek/deepseek-chat",
      "started_at": "2026-04-26T23:18:30Z",
      "ended_at": "2026-04-26T23:55:00Z",
      "exit_reason": "success",
      "elapsed_seconds": 2190,
      "cost_estimate": 0.08,
      "seam_report": "24 PASS, 1 DEGRADED, 0 FAIL"
    }
  ],
  "final_outcome": "success",
  "total_cost": 0.12,
  "total_elapsed_seconds": 3300
}
```

### CLI surface

```
python MagnumOpus/scripts/run_with_fallback.py \
    --prompt-file MagnumOpus/claude-code-prompt-27.md \
    [--ladder rung1,rung2,rung3]   # default = the LADDER constant
    [--max-cost 0.50]               # USD
    [--max-attempts 3]
    [--max-runtime-minutes 60]      # per-rung wall clock cap before escalation
    [--audit-dir MagnumOpus/smoke-test-artifacts]
    [--dry-run]                     # parse args, validate ladder model IDs, print plan, exit 0
```

Exit codes:
- `0` = success (one rung produced a seam report)
- `1` = all rungs failed
- `2` = bad CLI args
- `3` = aborted on cost cap before completion

### Tests (the most important deliverable)

`tests/test_run_with_fallback.py` covers the failure detector with mocked JSON event streams. **No live API.** Use synthetic fixtures.

Cases to cover (at least 12 tests):

1. Length runaway is detected → returns "length-runaway"
2. Silent stall (`reason:other` + 0 output) → "silent-stall"
3. Seam-0-stop pattern → "seam-0-stop"
4. Three consecutive 429s → "rate-limit-death-loop"
5. Wall-clock cap exceeded → "wall-clock-exceeded"
6. Successful seam report → "success" (no escalation)
7. `reason:stop` with output > 100 tokens AND tool calls present → NOT seam-0-stop (negative case — don't false-positive on legitimate stops)
8. Two 429s separated by a successful step → NOT death loop (negative case — counter resets on success)
9. Cost cap exceeded mid-run → "cost-cap-exceeded"
10. Ladder exhausted after 3 attempts → "ladder-exhausted"
11. Audit log has correct shape (one attempt per restart, ordered, cost summed correctly)
12. CLI `--dry-run` validates ladder + exits 0 without spawning

### Runner script integration

In `run_attempt_11.ps1`, replace the existing `opencode run --attach http://localhost:4096 --agent orchestrator --model ... --format json --dangerously-skip-permissions @MagnumOpus/...` block with:

```powershell
python MagnumOpus/scripts/run_with_fallback.py `
    --prompt-file MagnumOpus/claude-code-prompt-27.md
```

The wrapper handles `--model` and the prompt content inlining itself. Remove the `--attach http://localhost:4096` if you wire the wrapper to manage `opencode serve` lifecycle too — but for v0, leave the user starting `opencode serve` separately like they do today, and the wrapper just calls `opencode run` against `localhost:4096`.

### One-page doc: `MagnumOpus/SESSION-R-FALLBACK-LADDER.md`

Cover:
- What it is (one paragraph)
- The ladder (current rungs + cost notes)
- Failure signals (the table from this prompt)
- How to invoke (CLI surface)
- Audit log location and format
- Kill switches (env var: `JANUS_FALLBACK_DISABLED=1` should make the wrapper run rung-1 only with no escalation, useful for A/B testing whether ladder logic is causing issues)
- How to add a new rung (edit LADDER constant, verify auth, run --dry-run)

Keep it short — under 200 lines. The detail goes in code comments and tests.

---

## Hard constraints

- **No live API in tests.** All tests use mocked JSON event fixtures. The CI cost should be zero.
- **Do not include `anthropic/*`, `cerebras/*`, or `google/gemini-*` in the LADDER constant.** Per project memory: Anthropic is off the menu (cost), Cerebras-Qwen has TPM ceiling issues, Gemini stalls. The ladder is DeepSeek-V4-Flash → DeepSeek-V3.2 → Kimi K2.6.
- **Do not mutate `opencode.json` between runs.** Use `--model` CLI flag to override.
- **Do not modify `claude-code-prompt-27.md`.** That file is now scrubbed and model-agnostic; the wrapper passes it as-is.
- **Do not modify `orchestrator.md` or `mission-protocol.md`.** Out of scope.
- **Do not add the wrapper to existing tests' run path.** New file, new test file, isolated.
- **If exploration exceeds 8 read/grep calls before starting to write the wrapper**, stop reading and start writing. The spec above is sufficient; you don't need to re-derive it from project state.
- **Do not run a real smoke test as the final verification.** Run the unit tests instead. The user has spent enough on smoke runs today.

## Verification path

1. `pytest tests/test_run_with_fallback.py -v` → all tests green
2. `python MagnumOpus/scripts/run_with_fallback.py --dry-run --prompt-file MagnumOpus/claude-code-prompt-27.md` → prints validated ladder + exits 0
3. `git status` → only the four new/modified files staged
4. Three commits (script + tests in one, runner script update in second, doc in third)

Do NOT run a real smoke test. The user wants this to land cleanly so it's ready for tomorrow's first unattended run.

## Reporting back

5-line summary:
1. LOC added (script + tests + doc)
2. Number of tests, all passing (e.g., "14 tests, all green in 0.X s")
3. Commit hashes (3 commits expected)
4. Anything you discovered during implementation that's worth flagging (e.g., opencode JSON event format quirks, edge cases in the ladder logic)
5. Recommended next step from your perspective

---

## Reference

- `MagnumOpus/JANUS-EVOLUTION-ROADMAP.md` — Session R was queued in the roadmap as defensive infra
- `core/worker.py` — has the Windows process-tree-kill pattern (`taskkill /F /T /PID`) you can reference
- `.opencode/tools/quality_gate.py` — example of a similar wrapper-style Python script in this codebase
- `tests/test_lcn_write.py` — example test style for this codebase (pytest, parametrize-friendly)
- `MagnumOpus/cc-deepseek-pivot.md` and `MagnumOpus/cc-v4flash-and-cleanup.md` — prior CC handoffs, same author, same expectations

---

## Why this prompt exists

Cowork is conserving its weekly cap. The user wants this defensive infrastructure to land tonight so future smoke runs (Phase 6.2 and beyond) can run unattended overnight without manual intervention if a model fails. Three failure modes have already cost ~3 hours of manual recovery this week. Session R amortizes that cost across all future runs.

The user is good with you taking 30-60 minutes on this. Cost ceiling for the build itself: ~$0.20 of CC API time should be plenty for a 700-LOC delivery + tests + doc.

When you're done, the user closes the laptop and goes to bed. Tomorrow morning's first smoke run is the first real-world test of the wrapper.
