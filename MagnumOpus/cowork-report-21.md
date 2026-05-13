# Batch 21 Report

**Status**: PASS
**Commit**: 61e2e0a

## Changes
- `.opencode/opencode.json`: provider.anthropic.options.baseURL = "https://api.anthropic.com/v1"
- `.opencode/agent/orchestrator.md` line 3: model → `anthropic/claude-sonnet-4-6`

## Verification

**JSON parse**: ok
```
{'timeout': 600000, 'setCacheKey': True, 'baseURL': 'https://api.anthropic.com/v1'}
```

**grep model line**:
```
3:model: anthropic/claude-sonnet-4-6
```

**git diff --stat**:
```
 .opencode/agent/orchestrator.md | 2 +-
 .opencode/opencode.json         | 3 ++-
 2 files changed, 3 insertions(+), 2 deletions(-)
```

## What this fixes

- **Finding J** (batch 17b): Anthropic SDK was hitting `/messages` (404) instead of `/v1/messages`.
  `baseURL: "https://api.anthropic.com/v1"` makes the SDK append `/messages` to the right prefix.
- **Finding L** (batch 17c): `openrouter/anthropic/claude-sonnet-4-6` was routing to Gemini
  (confirmed by `google.thoughtSignature` on every step_finish). The orchestrator now uses the
  direct Anthropic endpoint — no OpenRouter proxy.
- **Finding M** (batch 17c): 2 hr 17 min inter-step gap was OpenRouter rate-limiting Gemini free
  tier. Direct Anthropic endpoint eliminates this.
- **Findings K/K2** (batch 17c): edit oldString prefix bug and invented `isoformat` tool are
  Gemini-style errors. May not reproduce on real Claude Sonnet — do not pre-fix.

## Expectations for next smoke test (batch 17d)

- Steps must NOT show `google.thoughtSignature` metadata — if they do, Finding L is not fixed
- Inter-step latency should drop to seconds (not 17 min or 2 hr)
- Seam observation should be completable within the 30-minute window
- Findings K/K2 and N may or may not reproduce; observe before patching
