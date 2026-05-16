# Session R — Model Fallback Ladder

## What it is

`run_with_fallback.py` wraps `opencode run` in a model fallback ladder.
When the primary model fails (length runaway, silent stall, rate-limit death
loop, etc.), the wrapper kills the process, resets mission state, and
restarts with the next model on the ladder — all without human intervention.

## The ladder

| Rung | Model | Cost (in/out) | Context | Notes |
|------|-------|---------------|---------|-------|
| 1 | `deepseek/deepseek-v4-flash` | $0.14/$0.28 | 1M | Default, fastest, agentic-tuned |
| 2 | `deepseek/deepseek-chat` | $0.27/$0.40 | 164K | V3.2 alias, slower but proven |
| 3 | `moonshotai/kimi-k2.6` | $0.95/$4.00 | 256K | "200-300 sequential tool calls" |

**Do NOT add** `anthropic/*`, `cerebras/*`, or `google/gemini-*` — these
have known failure modes that the ladder is designed to escape from.

## Failure signals

| Signal | When it fires | Detection |
|--------|---------------|-----------|
| **Length runaway** | `step_finish` with `reason: "length"` | Model hit max_tokens — almost always runaway generation. Escalate immediately. |
| **Silent stall** | `step_finish` with `reason: "other"` AND `tokens.output: 0` | Gemini-style stall. Escalate immediately. |
| **Seam-0-stop** | `step_finish` with `reason: "stop"` AND `tokens.output < 100` AND zero tool_use events AND total elapsed < 60s | Qwen-Instruct "I'm done after Seam 0" pattern. Escalate immediately. |
| **Rate-limit death loop** | 3 consecutive 429 errors within 5 minutes, no successful `step_finish` between them | Provider is rejecting all requests. Escalate. |
| **Wall-clock exceeded** | >60 minutes without `=== SEAM REPORT ===` | Model too slow. Escalate to faster rung. |
| **Cost cap exceeded** | Cumulative `step_finish.cost` > $0.50 | Abort with exit code 3. |
| **Success** | Text event contains `=== SEAM REPORT ===` | Normal completion. Exit 0. |

## How to invoke

```bash
# Basic usage
python MagnumOpus/scripts/run_with_fallback.py \
    --prompt-file MagnumOpus/claude-code-prompt-27.md

# Custom ladder & limits
python MagnumOpus/scripts/run_with_fallback.py \
    --prompt-file MagnumOpus/claude-code-prompt-27.md \
    --ladder "deepseek/deepseek-v4-flash,moonshotai/kimi-k2.6" \
    --max-cost 0.75 \
    --max-attempts 2 \
    --max-runtime-minutes 90

# Dry run (validate args only)
python MagnumOpus/scripts/run_with_fallback.py \
    --prompt-file MagnumOpus/claude-code-prompt-27.md \
    --dry-run
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success — seam report received from one rung |
| 1 | All rungs exhausted — no success |
| 2 | Bad CLI args (missing file, invalid model ID, etc.) |
| 3 | Cost cap exceeded — aborted mid-attempt |

## Audit log

Written to `MagnumOpus/smoke-test-artifacts/fallback-audit-<timestamp>.json`:

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
      "evidence": "type=step_finish reason=length output_tokens=32000"
    }
  ],
  "final_outcome": "success",
  "total_cost": 0.12,
  "total_elapsed_seconds": 3300
}
```

## Kill switches

| Env var | Effect |
|---------|--------|
| `JANUS_FALLBACK_DISABLED=1` | Run rung-1 only, no escalation. Use for A/B testing or when you want to rule out ladder logic as the source of a problem. |

## How to add a new rung

1. Edit `LADDER` in `MagnumOpus/scripts/run_with_fallback.py` (add at the end).
2. Verify the model ID is reachable: `opencode run --model <id> "Hello" --format json`.
3. Run `--dry-run` to confirm validation passes.
4. Update this doc's ladder table.
5. Push.

## Architecture notes

- Uses `--model` CLI flag per rung (never mutates `opencode.json`).
- Process tree killed via `taskkill /F /T /PID` (Windows-only, matches pattern
  from `core/worker.py`).
- Between rungs: runs `MagnumOpus/reset_mission.py` + `git clean -fd
  MagnumOpus/smoke-test-artifacts/` to reset pipeline state.
- Tests in `tests/test_run_with_fallback.py` — 12+ cases, no live API.
