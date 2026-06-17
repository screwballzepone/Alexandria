# Provider Configuration Guide

OpenCode supports multiple AI providers. Configure them in `.opencode/opencode.json`
under the `provider` key.

## DeepSeek (Recommended)

Default provider. Best cost/performance for coding tasks.

```json
"deepseek": { "baseURL": "https://api.deepseek.com/v1" }
```

Env var: `DEEPSEEK_API_KEY`

## OpenRouter

Multi-provider gateway. Use when a model isn't available on DeepSeek.

```json
"openrouter": { "baseURL": "https://openrouter.ai/api/v1" }
```

Env var: `OPENROUTER_API_KEY`

## Cerebras

Hosts Qwen 3 235B and Llama 3.1 8B. Fast inference, limited TPM.

```json
"cerebras": {
  "npm": "@ai-sdk/openai-compatible",
  "baseURL": "https://api.cerebras.ai/v1",
  "models": {
    "qwen-3-235b-a22b-instruct-2507": {},
    "llama3.1-8b": {}
  }
}
```

Env var: `CEREBRAS_API_KEY`

## Known Issues

### Cerebras Qwen 3 235B — Silent Stall
**Symptom**: Agent dispatches with zero output, no error. Process hangs indefinitely.
**Cause**: Provider-level timeout, not client-side. TPM ceiling (30K) exceeded by
system prompt + max_tokens reservation.
**Workaround**: Use fallback ladder. The `/issue-run` command auto-escalates to
DeepSeek V3.2 or Kimi K2.6 on stall.

### Cerebras — 429 Rate Limit Death Loop
**Symptom**: Consecutive 429 errors with `token_quota_exceeded`.
**Workaround**: Don't run multiple Cerebras agents in parallel. The fallback ladder
detects 3 consecutive 429s within 5 minutes and escalates.

### Gemini 2.5 Flash — Seam-0 Stop
**Symptom**: Model emits `reason:stop` with 0 output tokens and no tool calls
within first 60 seconds.
**Workaround**: Gemini is excluded from the fallback ladder. Use DeepSeek or OpenRouter.

## Model Routing

The orchestrator selects models based on task tier:

| Tier | Model |
|------|-------|
| Orchestrator | deepseek/deepseek-v4-pro |
| Coder, Reviewer, Explorer | deepseek/deepseek-v4-flash |
| Creative/Prompt | opencode-go/mimo-v2.5-pro |
| Lightweight | opencode-go/minimax-m2.5 |

## Cost Notes

- DeepSeek V4 Flash: $0.14/$0.28 per 1M tokens (input/output)
- DeepSeek V4 Pro: higher cost, used only for orchestration
- Anthropic models: disabled (cost feedback: $3.50/day trigger)
- Monthly budget: $20-50 typical for active development
