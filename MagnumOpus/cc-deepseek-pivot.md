# Claude Code Handoff — DeepSeek Pivot + Debug

You are Claude Code (Sonnet) running in the user's terminal. Cowork (also Sonnet) handed this work to you to save the user's weekly Cowork budget. **Be efficient — minimize unnecessary tool calls and exploration.**

---

## Current state

- **Phase 6.1 gate**: Cleared yesterday (2026-04-24) at 20/25 PASS, commit `e67d694`. Then `2bbd572` shipped autonomous-exec preamble + gitignore.
- **Today's failed runs** (in chronological order):
  1. **Session C-2b (commit `9172980`)** — wired pre-plan consult into `orchestrator.md` STEP 1.5. Caused a `reason: "length"` runaway: Qwen generated 32K tokens with no tool calls, no text events, hit max_tokens. Reverted in `583234c`.
  2. **Preflight smartening commit** — improved `run_attempt_11.ps1` Step 1 to only halt on untracked files (not modifications) + matched the prompt's stop condition. Working as designed.
  3. **Smoke test attempt 14** (just now, post-preflight-fix) — entered a death loop on Cerebras `token_quota_exceeded` 429s. Six consecutive 60s-spaced 429s, no progress past SESSION START. **THIS IS THE CURRENT BLOCKER.**
- **Orchestrator log shows**: orchestrator successfully read mission.json, generated project-map.json via @onboarder, classified TIER STANDARD. Then every subsequent LLM call hit Cerebras's 30K TPM ceiling because the system prompt is now ~28K (orchestrator.md + AGENTS.md) + tool history + 32K max_tokens reservation = ~70K committed against 30K/min.

## Diagnosis (do not re-derive)

Cerebras free tier (Qwen 3 235B): **5 RPM, 30K TPM**. The current orchestrator prompt+context+max_tokens reservation now exceeds 30K TPM per single request, so every call returns `token_quota_exceeded` and Cerebras's `retry-after: 60` causes a 60s wait before the *same oversized request* fails again. Infinite loop. Cerebras is not viable as the orchestrator backend at the current prompt size.

The original `claude-code-prompt-27.md` anticipated this exact failure mode: **"If Qwen 3 235B also stalls, ... fall back to DeepSeek V3.2 (paid, proven on sub-agents, ~$0.05/run)."**

## Your job

Apply the DeepSeek V3.2 pivot, verify the smoke test passes (≥18/25), commit cleanly. If the pivot fails for some other reason, debug it efficiently. Do NOT try to "fix Cerebras" — TPM is hard-bounded by the provider.

---

## Step 1 — Stop any running opencode processes

```powershell
Get-Process opencode -ErrorAction SilentlyContinue | Stop-Process -Force
```

If nothing was running, that's fine.

## Step 2 — Apply the three edits

**Edit 2a: `.opencode/opencode.json`**

Change the top-level `"model"` and `"small_model"` fields. Currently:
```json
"model": "cerebras/qwen-3-235b-a22b-instruct-2507",
"small_model": "cerebras/qwen-3-235b-a22b-instruct-2507",
```
Change to:
```json
"model": "deepseek/deepseek-chat",
"small_model": "deepseek/deepseek-chat",
```

The `agent.title.model` override (`cerebras/llama3.1-8b`) can stay — title-gen is fine on Cerebras since it's tiny single-shot.

**Edit 2b: `.opencode/agent/orchestrator.md` line 3 frontmatter**

Currently:
```yaml
model: cerebras/qwen-3-235b-a22b-instruct-2507
```
Change to:
```yaml
model: deepseek/deepseek-chat
```

**Edit 2c: `run_attempt_11.ps1`**

Find the `--model cerebras/qwen-3-235b-a22b-instruct-2507` flag in the `opencode run` command near the bottom of the file. Change to:
```
--model deepseek/deepseek-chat
```

## Step 3 — Sanity-check DeepSeek auth is configured

```powershell
opencode auth list
```

Expect to see `deepseek` listed. If not, the user needs to run `opencode auth login deepseek` and provide their DeepSeek API key. **Stop and tell the user if auth is missing — don't fabricate keys.**

## Step 4 — Commit the pivot

```powershell
git add .opencode/opencode.json .opencode/agent/orchestrator.md run_attempt_11.ps1
git commit -m "Pivot orchestrator from Cerebras Qwen to DeepSeek V3.2 (TPM ceiling untenable)

Cerebras free tier (5 RPM, 30K TPM on Qwen 3 235B A22B Instruct) cannot
accommodate the current orchestrator prompt size. The system prompt
(orchestrator.md + AGENTS.md inlined) plus tool result history plus the
32K max_tokens reservation totals ~70K committed tokens per request,
which blows the 30K TPM ceiling on every call. Cerebras retries every
60s with the same oversized request, hitting an infinite loop.

Pivot per the prompt-27.md escape clause: 'If Qwen 3 235B also stalls,
fall back to DeepSeek V3.2 (paid, proven on sub-agents, ~\$0.05/run).'

Three edits:
- .opencode/opencode.json: model + small_model -> deepseek/deepseek-chat
- .opencode/agent/orchestrator.md line 3: model frontmatter
- run_attempt_11.ps1: --model flag

Cerebras llama3.1-8b stays as the title agent (small footprint, separate
bucket, never an orchestrator path)."
```

## Step 5 — Run the smoke test

```powershell
.\run_attempt_11.ps1
```

Watch the orchestrator log stream. You're looking for:
1. `MODEL: deepseek/deepseek-chat` (Seam 0)
2. SESSION START completion (project map, user model, lessons, LCN check)
3. Sub-agent dispatches that actually return content
4. **`=== SEAM REPORT ===`** at the end with **≥18/25 PASS**

Expected runtime: 25–45 min wall clock (DeepSeek is slower per token than Cerebras but doesn't rate-limit like this).

## Step 6 — Parse the seam report

When the report lands:
- **≥18/25 PASS** → success. Tell the user the score, the feature commit hash if any, and recommend they screenshot the report. Stop.
- **<18 PASS** → diagnose the highest-impact failure. Common cases below.

---

## Failure modes and what to do

### If DeepSeek auth is missing
Stop. Tell the user: `Run: opencode auth login deepseek` then re-run.

### If smoke test halts at SESSION START with `external_directory: ask`
The `permission: external_directory: allow` config in opencode.json may have regressed. Check `.opencode/opencode.json` has it. If not, restore.

### If orchestrator hits a `length` runaway again (output 32K tokens, no tool calls)
Different issue from Cerebras TPM — this is the C-2b failure mode. Check `git log --oneline -10` to confirm the C-2b revert (`583234c`) is in the history and that orchestrator.md does NOT have a `STEP 1.5` section. If STEP 1.5 is back, something un-reverted it. Re-revert.

### If smoke test runs but seam report shows <18 PASS
Compare against attempt 11's 20/25 baseline (commit `e67d694` for the feature). The most likely regressions:
- **Seam 13 (is-clean before merge)**: Known issue — `git_ops.py is-clean` returns `false` on expected-modified mission.json. Pre-existing punch list item. Don't fix here.
- **Seam 17 (merge)**: If the seam-13 bug halted before merge, seams 17–25 will all NOT_RUN. That's expected.
- **mission_status.py tests**: 6/17 fail due to a format mismatch in test output strings (yesterday's @coder bug). Pre-existing punch list, don't fix here.

If the failures are NOT in the known-issue list above, log them in the seam report and tell the user — don't try to fix in this session.

### If DeepSeek itself fails (auth error, model not found, etc.)
Try one fallback in this order before giving up:
1. `anthropic/claude-sonnet-4-5` (proven, but expensive — only as last resort, and tell the user the cost will be higher than DeepSeek)
2. Whatever the user has authenticated via `opencode auth list` that's a strong reasoning model

Document which fallback you used and why.

---

## Hard constraints

- **Do not modify `MagnumOpus/claude-code-prompt-27.md`** beyond what's already there. The autonomous-exec preamble is load-bearing.
- **Do not re-attempt Session C-2b** (pre-plan consult wiring into orchestrator.md). That's a separate redesign that needs its own session.
- **Do not investigate the seam-13 protocol bug** or the `mission_status.py` test format mismatch. Both are documented punch list items, not blocking the pivot.
- **Do not commit smoke-test artifacts** — `MagnumOpus/smoke-test-artifacts/` is gitignored.
- **If you find yourself making more than 2 exploratory `git log` / `read` calls before applying the edits**, stop and just apply the edits. The diagnosis is solid; you don't need to re-derive it.

## Reference files (read only if you need them)

- `MagnumOpus/JANUS-EVOLUTION-ROADMAP.md` — overall plan, Sessions A–H + cortex transition
- `MagnumOpus/claude-code-prompt-27.md` — the smoke test prompt itself
- `.opencode/agent/orchestrator.md` — the orchestrator system prompt (do not modify body)
- `MagnumOpus/cowork-report-b17-b24-full.md` — historical context if you need it (probably not)

## Reporting back

When you're done, write a 5-line summary to stdout:
1. What the seam report verdict was (≥18/25 PASS, or partial seam scorecard with score)
2. Which model actually answered each agent dispatch (orchestrator, @coder, @reviewer)
3. Estimated cost of the run (parse from orchestrator log if available)
4. Any new punch-list items discovered
5. The commit hashes (pivot commit + any feature/docs/chore commits made during the smoke run)

Then stop. Don't sprawl into related work; don't try to fix the punch list. The user's Cowork session will pick up the next thread.

---

## Why this prompt exists

Cowork (Sonnet, same model as you) hit the user's weekly cap concern after watching six 60s `token_quota_exceeded` retries with no progress. Cowork has the full multi-day context but the budget pressure is real. Handing the surgical pivot work to you (Claude Code, separate budget pool) saves Cowork's weekly cap for the architectural work that genuinely needs the long context.

If something in this prompt is ambiguous or contradicts what you find in the codebase, **trust the codebase and tell the user**. Don't proceed past ambiguity.
