# Claude Code Handoff — V4-Flash Pivot + Punch-List Cleanup

You are Claude Code (Sonnet) in the user's terminal. Cowork (also Sonnet) handed this work to you to save the weekly Cowork budget. **Stay efficient — apply the edits, run the smoke, report. Don't sprawl.**

---

## State of play (do not re-derive)

Previous CC session (handoff: `MagnumOpus/cc-deepseek-pivot.md`):
- Pivoted orchestrator Cerebras Qwen → DeepSeek V3.2. **No more TPM rate-limit loops.** ✅
- Smoke test ran ~73 min before the user killed it. Reached SESSION START + classify + quality gate (17/17 tests, 0 ruff issues) + sub-agent dispatch. Did NOT reach seam scorecard before kill — ran out of wall clock.
- Commits made last session: `76378c2` (DeepSeek pivot), `efb53e7` (gitignore), `fefac81` (ruff fixes), `ff0e0f6` (blackboard.json gitignore + LLM research).
- Cost: ~$0.027 across the partial run.

**Three findings the user surfaced after killing the run** — all addressable in this session:

1. **DeepSeek V3.2 is too slow for accumulated-context runs.** Wall-clock budget runs out before pipeline completes. Research (saved to Notion + `MagnumOpus/llm-landscape-april-2026.md`) recommends **DeepSeek V4-Flash** instead — 1M context (vs 164K), $0.14/$0.28 (vs $0.27/$0.40), "ultra-low latency + agentic reasoning" per the official launch announcement, launched 2026-04-24.

2. **Seam 0 hallucinated `Qwen` model name.** The orchestrator emitted `MODEL: cerebras/qwen-...` despite running on DeepSeek. Cause: `claude-code-prompt-27.md` is saturated with Qwen references (in title, model routing, rate-limit blocks, why-this-batch-exists section). The model parroted what it saw in the prompt instead of introspecting. Fix: scrub all Qwen / Cerebras specifics from prompt-27.md. The prompt should be model-agnostic for Seam 0 — let the orchestrator report whatever model it actually runs on.

3. **`quality_gate.py` times out at 30s on mypy** because mypy is scoped to the entire `.opencode/tools/` directory (or wider). On a real run with multiple tools+helpers it's just too much. Fix: scope mypy to **changed files only** — derive from `git diff --name-only HEAD` for staged/modified .py files, fall back to scanning a smaller targeted scope if no diff.

## Your job (in order)

### Step 1 — Apply the V4-Flash pivot

Three edits, same pattern as last session.

**Edit 1a: `.opencode/opencode.json`** — change top-level `model` and `small_model`:
```json
"model": "deepseek/deepseek-v4-flash",
"small_model": "deepseek/deepseek-v4-flash",
```
(`agent.title.model` override stays as `cerebras/llama3.1-8b` — title-gen is fine on the small Cerebras bucket.)

**Edit 1b: `.opencode/agent/orchestrator.md`** line 3 frontmatter:
```yaml
model: deepseek/deepseek-v4-flash
```

**Edit 1c: `run_attempt_11.ps1`** — change the `--model` flag in the `opencode run` command:
```
--model deepseek/deepseek-v4-flash
```

### Step 2 — Scrub Qwen / Cerebras specifics from `claude-code-prompt-27.md`

Read the whole file first. Then rewrite the model-routing-specific sections to be **model-agnostic**:

- **Title** — drop "Qwen 3 235B on Cerebras". Replace with something like "Smoke Test Attempt 12 (DeepSeek V4-Flash)" or just "JANUS smoke test — Phase 6.1 gate verification".
- **Model routing block** at the top — rewrite to say the orchestrator runs on whatever opencode.json points at, currently `deepseek/deepseek-v4-flash`. Drop the Qwen-specific RPM/TPM tables (those were Cerebras-only).
- **Rate-limit awareness section under Constraints** — DeepSeek doesn't have the 30K-TPM cliff Cerebras did. Replace with: "DeepSeek V4-Flash has 1M context and ultra-low latency. Sub-agent dispatch spacing of 30s is no longer required for rate-limit reasons — but keep parallel-when-independent dispatch logic intact for correctness."
- **Seam 0 expected-value line** — remove the hardcoded `MODEL: cerebras/qwen-3-235b-a22b-instruct-2507`. Replace with "emit `MODEL: <your-actual-model-id>`. Use whatever introspection is available; introspect, do NOT parrot what's in this prompt." That's the load-bearing change to fix the Seam 0 hallucination.
- **Why-this-batch-exists section at the bottom** — keep the historical narrative (it's useful context) but mark Cerebras attempt as historical. The "fall back to DeepSeek V3.2" escape clause has been triggered and superseded by V4-Flash.
- **Stop conditions** — drop the Cerebras 429 retry semantics. DeepSeek doesn't fail that way.

Keep the autonomous-execution directive intact — that one is load-bearing.

Keep the working-tree-clean stop condition (the version with `git ls-files --others --exclude-standard` that allows modifications). That's the post-revert version, do not regress it.

### Step 3 — Fix `quality_gate.py` mypy scope

Read `.opencode/tools/quality_gate.py`. Find the mypy invocation. It's probably running mypy against a fixed path or `.opencode/tools/`.

Replace it with a **changed-files-only** scope:
1. Run `git diff --name-only HEAD` to get changed .py files
2. If empty (no changes), fall back to running mypy only on the currently-staged files: `git diff --cached --name-only`
3. If both are empty (clean tree), skip mypy entirely with a "no .py changes to check" pass-through and move to the next gate
4. Pass the `--explicit-package-bases` flag if mypy complains about modules-vs-packages (common with single-file scripts)
5. Cap timeout at 30s per file or 90s total — whichever fires first
6. On timeout: log it as DEGRADED rather than FAIL (mypy hanging shouldn't kill the gate; it's a tooling hiccup, not a code defect)

After the fix, run `python .opencode/tools/quality_gate.py` once with no args to confirm it returns clean JSON output and doesn't hang.

### Step 4 — Commit (one commit per concern, three total)

```powershell
# Commit 1: the V4-Flash pivot
git add .opencode/opencode.json .opencode/agent/orchestrator.md run_attempt_11.ps1
git commit -m "Pivot orchestrator to DeepSeek V4-Flash (faster, cheaper, larger context)

V3.2 worked (no TPM loops) but ran out of wall clock at ~73 min before
seam scorecard. V4-Flash: 1M context (vs 164K), \$0.14/\$0.28 (vs
\$0.27/\$0.40), ultra-low latency, agentic-reasoning tuning. Launched
2026-04-24 per api-docs.deepseek.com."

# Commit 2: prompt-27 scrub
git add MagnumOpus/claude-code-prompt-27.md
git commit -m "Scrub Qwen/Cerebras specifics from prompt-27 to fix Seam 0 hallucination

Prior session's Seam 0 emitted MODEL: cerebras/qwen-... despite running
on DeepSeek. The orchestrator parroted the prompt's saturated Qwen
references instead of introspecting. Made the prompt model-agnostic:
Seam 0 introspects whatever's actually running, model-routing block
references opencode.json instead of hardcoding a model, rate-limit
awareness drops the Cerebras-specific 30K TPM cliff (DeepSeek doesn't
have one). Autonomous-execution directive and working-tree-clean stop
condition preserved."

# Commit 3: quality_gate.py scope fix
git add .opencode/tools/quality_gate.py
git commit -m "fix(quality_gate): scope mypy to changed files; degrade on timeout

mypy was timing out at 30s scanning the full .opencode/tools/ tree.
Now derives scope from git diff --name-only HEAD (or --cached if no
unstaged), skips with pass-through when tree is clean, caps at 90s
total, treats timeout as DEGRADED rather than FAIL since hangs are
tooling hiccups not code defects."
```

If any of the three commits has nothing to actually commit (because the file you tried to edit didn't actually need a change), skip that commit cleanly. Don't fabricate.

### Step 5 — Run the smoke test

```powershell
.\run_attempt_11.ps1
```

Watch for:
1. **Seam 0**: should now emit `MODEL: deepseek/deepseek-v4-flash` (not Qwen)
2. SESSION START completion
3. Quality gate: should run faster now (mypy scoped, no 30s hang)
4. Sub-agent dispatches actually returning content
5. **`=== SEAM REPORT ===`** block at the end with **≥18/25 PASS**

Expected runtime: **15–30 min wall clock** with V4-Flash (significantly faster than V3.2's 73+).

### Step 6 — Report back

5-line summary:
1. Final seam score (X PASS, Y DEGRADED, Z FAIL, W NOT_RUN)
2. Which model actually answered Seam 0 (must be `deepseek/deepseek-v4-flash` for the scrub to be confirmed working)
3. Estimated total cost
4. Wall-clock runtime
5. New punch list items if any (likely seam-13 protocol bug + the mission_status.py format mismatch — both pre-existing, do NOT try to fix them)

---

## Hard constraints (same as last session)

- **Do not** re-attempt Session C-2b (pre-plan consult wiring into orchestrator.md). Reverted, off-limits.
- **Do not** investigate the seam-13 protocol bug or mission_status.py test format mismatch. Punch list, not blocking.
- **Do not** modify autonomous-execution directive in prompt-27.md.
- **Do not** modify the working-tree-clean stop condition in prompt-27.md (the post-revert version).
- **Do not** commit smoke-test-artifacts/ (gitignored).
- **If exploration exceeds 5 read/grep calls before applying edits**, stop reading and just apply. The diagnosis is solid.
- **If V4-Flash is not authenticated** (run `opencode auth list`), tell the user `Run: opencode auth login deepseek` and stop. Don't fabricate keys.
- **If V4-Flash returns "model not found" errors** at runtime, fall back to `deepseek/deepseek-chat` (the V3.2 alias) and tell the user the V4-Flash model ID needs verification on their account. Don't try other model families.

## Reference files

- `MagnumOpus/llm-landscape-april-2026.md` — your prior session's research output, has V4-Flash pricing/spec details
- `MagnumOpus/JANUS-EVOLUTION-ROADMAP.md` — overall plan
- `.opencode/agent/orchestrator.md` — the orchestrator system prompt (do not modify body, only line 3 frontmatter)

---

## Why this prompt exists

Cowork verified the V4-Flash pricing/spec against the Notion research library Claude Code wrote last session ([AI Coding Tools Research Library April 2026](https://www.notion.so/34ea6ab90fd78002aeaae3c7062e30cb)). V4-Flash is the right next move — 5× the context window, faster, cheaper, agentic-tuned. The two cleanup items (Qwen scrub + mypy scope) are the user's direct findings from watching the V3.2 run.

Bundling all three into one CC session because they're all small surgical edits with the same verification path (smoke test). Doing them separately would mean three smoke runs.

When you're done, the user gets back a clean ≥18/25 report under 30 min wall clock and we can move to Session R (model fallback ladder) or back to feature work without further pivoting.
