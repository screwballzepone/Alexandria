# JANUS PIPELINE — Strategic Roadmap (May 2026)

> **What this is**: the master sequence for getting JANUS from where it is today (17-agent coding pipeline with a non-functional Brain) to where it's going (autonomous, learning, multi-project agentic engineer that runs while you sleep).
>
> **Companion docs**:
> - `PIPELINE-NORTH-STAR.md` — the "why we're doing this" frame
> - `PIPELINE-DECISIONS.md` — open questions, trade-offs, decision log
> - `JANUS-STATE.md` (root) — current-state snapshot, updated per session
>
> **Living document.** Append at phase boundaries. Don't rewrite — annotate. Crosslink with state changes.
>
> **Last meaningful edit**: 2026-05-01 (post smoke-test attempt 12, gate cleared at 24/25, V4-Flash baseline confirmed).

---

## §0 — Preamble

This document is **the spine**. JANUS-STATE.md is the *snapshot*; PIPELINE.md is the *trajectory*. When you're disoriented, read JANUS-STATE.md to find out where you are. When you're deciding what to do next, read PIPELINE.md to find out where you're going.

Three reading modes:
1. **Tactical** — jump to the current phase, read its prerequisites + concrete steps. Skip the rest.
2. **Strategic** — read §1 (state) → §2 (north star) → §3 (the bet) → §4 (phase index). Skip phase details.
3. **Comprehensive** — read end to end. Roughly 2000 lines. Done in one sitting.

Phases A–J are sequential **dependencies**, not strict ordering. Phase E (Provider Resilience) and Phase F (GUI) can run in parallel with Phases B/C if you have spare cycles. Phase G (Autonomous Queue) gates on D. Phase H (Cortex Transition) gates on Notion spec-LCN v1 shipping, which is outside our control. Phase J (Self-Improvement Loop) is continuous from D onward.

---

## §1 — Current State (May 2026)

### What works

The smoke-test pipeline is **proven**. Phase 6.1 gate has been cleared twice:
- 2026-04-24: Cerebras Qwen 3 235B, 20/25 PASS (commit `e67d694`)
- 2026-04-26: DeepSeek V4-Flash, 24/25 PASS, 0 FAIL, 1 DEGRADED (commit `804dea2`)

A 17-agent pipeline (1 orchestrator + 16 subagents + 1 global context-optimizer) can now decompose a STANDARD-tier task into a feature branch, dispatch test-writer + nano-coder pre-flight in parallel, dispatch coder, run quality gate, dispatch reviewer, parse verdict, commit feature with explicit file paths (no `git add -A` regression risk), merge, run security-auditor, run lessons retrospective, run meta-agent, write LCN memory (when Brain is online — currently no-op), open a draft PR via GENESIS, link to source issue, status-check CI.

The competitive systems wave (2026-04-30) added Cursor/Cline-tier surface area:
- Hooks (PreToolUse / PostToolUse / Stop) for deterministic enforcement
- Repo map (zero-dep AST analysis, 590 lines, 3 modes: build/rank/context)
- Recipes (Jinja2 templates: api-builder, refactor-pattern, test-generator)
- Rules (categorized always-loaded instructions: code-style, agent-dispatch, glob-scoped)
- Directory AGENTS.md (per-module context with patterns + gotchas)
- File-based slash commands (/review, /lint, /repomap)
- Plan/Act mode (read-only plan, then execute)
- Error logging (JSONL append-only, 7 error types, crash-safe)
- Lessons tracking (post-session retrospective)

The orchestrator prompt is **skill-extracted**: 419 lines down from 506, with mission-protocol/healing-protocol/blackboard-protocol/quality-gate/parallel-universe/mission-completion all loaded on-demand via the skill mechanism. This eliminated the C-2b length-runaway failure mode (where orchestrator.md got too big and Qwen burned 32K output tokens trying to digest it).

Provider stack is **DeepSeek V4-Flash for 11/17 agents** (workhorse), with @explorer on Grok 4.20 Beta (OpenRouter), @architect on Qwen 3 235B (OpenRouter, after Cerebras stalls), @researcher on Perplexity Sonar Reasoning Pro (when key is set). Cerebras Llama 3.1 8B remains for title-gen only.

LCN integration foundation is **partially built**:
- `.opencode/tools/lcn_write.py` — write-side, 23 tests green, validates 5 entity types per LCN-SCHEMA.md
- `.opencode/tools/lcn_read.py` — 5 query types per CONSULT-PROTOCOL.md, 30 tests green
- `.opencode/tools/consult.py` — orchestrator-facing helper, 21 tests green
- `.opencode/tools/capability_assessor.py` — TIER-CLASSIFIER.md 7-rule classifier, 38 tests green
- `MagnumOpus/seeds/conventions.jsonl` — 8 seeded Conventions
- `MagnumOpus/seeds/errors.jsonl` — 8 seeded Errors
- `.lcn/lcn.sqlite` — local SQLite, 16 entities seeded

**What does NOT work**:
- `lcn_client.py` reports OFFLINE — Brain server is down, can't be started until Phase A clears
- Pre-plan / pre-dispatch / post-verify consult wiring into orchestrator.md was attempted (C-2b) and reverted because of the length-runaway. Will be re-attempted in Phase D-2 with the now-skill-extracted orchestrator (smaller surface).

### What's blocked

The Brain (Language Cognition Network, JANUS's intended long-term memory) is at `Brain/lcn_brain/`. **0 of 49 tests pass** because:
1. JAX/jaxlib/flax not installed → all tests fail at import time
2. `lcn_jvp` package missing → train.py can't run
3. `arms.py:run_arm()` is a placeholder skeleton → 4-arm validation is impossible
4. Two known bugs (readout matmul precedence, SSF test trajectory unpack) → would still fail even with JAX

**Total work to unblock**: ~6 mechanical steps (~1 hour) + 1 hard step (write `lcn_jvp`, ~1-3 sessions). Without this, the entire "two minds" architecture is aspirational. With this, JANUS becomes a system that can actually learn.

### Provider/cost reality

Anthropic models scrapped from JANUS orchestration after $3.50/day burn rate. User hand-coding via Claude Code now uses DeepSeek V4 (the user's recent pivot — "since anthropic went to hell, I start using Deepseek 4 on opencode"). **DeepSeek V4 family is the dominant model for both JANUS internals and the user's IDE workflow.** Cost ceilings:
- Per-mission budget: ~$0.05–0.10 (V4-Flash baseline)
- Weekly Cowork cap: managed by handing off to Claude Code (separate Anthropic API budget)
- Brain training: minimal — Burgers' PDE testbed is small (30 timesteps × 100 grid points), local GPU is sufficient

### Hardware envelope

RTX 3060 12GB VRAM, 32GB RAM, AMD Ryzen 5 5600X. Fits Q4_K_M models up to ~10-13B params. Five Ollama models installed (qwen2.5-coder:7b, deepseek-r1:8b, fast3b, llama3.2:1b/3b). Two wired into config; three optional. JAX-on-GPU is viable for LCN training. Spec-LCN v1 (the future cortex) might exceed local hardware — that's a Phase H decision.

### The known-issue ledger (carried forward)

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | Brain/LCN not functional | CRITICAL | BLOCKED on Phase A + B |
| 2 | Perplexity apiKey eaten by vibeguard | CRITICAL | WAITING on user to set env var |
| 3 | Cerebras provider stalls | HIGH | MITIGATED — moved @architect off |
| 4 | Perplexity provider stalls | HIGH | MITIGATED — orchestrator stall instructions |
| 5 | GUI features unwired (plan_mode, file attach, slash palette, fork, title) | HIGH | ✅ DONE (commit 0041b35) — 3 stretch items remain |
| 6 | No subagent timeout (opencode.cmd has no `--timeout`) | HIGH | Partially mitigated |
| 7 | seam-13 protocol bug: is-clean returns false on expected-modified mission.json | MEDIUM | PUNCH LIST — Phase E vicinity |
| 8 | SSF test trajectory unpack bug | MEDIUM | KNOWN — Phase A fixes |
| 9 | readout_forward matmul precedence | MEDIUM | KNOWN — Phase A fixes |
| 10 | lcn_jvp package missing | CRITICAL | BLOCKED — Phase B writes it |
| 11 | Burgers' arms.py is skeleton | HIGH | BLOCKED on Phase B → Phase C |
| 12 | Duplicate `from dataclasses import dataclass` in arms.py | LOW | TRIVIAL |

---

## §2 — The North Star

JANUS exists to be the closest thing to **"AI that autonomously runs your development process"** that you can actually run on your own hardware, with your own keys, against your own repos.

The end state — call it **JANUS at maturity** — looks like:

1. You go to bed. JANUS pulls one issue from a curated GitHub queue, classifies it, designs the fix, writes failing tests first, implements until tests pass, runs the quality gate, dispatches a reviewer, addresses the verdict, commits the feature, opens a draft PR, watches the CI status, and writes a one-paragraph mission report.
2. You wake up. There are three new draft PRs, one with a failing CI check (auto-flagged), two ready for your review. The PR descriptions are honest about the trade-offs the orchestrator considered. The error log shows two failures during the night — both auto-recovered by the fallback ladder, neither escalated to you.
3. You merge two of the three. The third needs a refactor decision you don't want delegated. You leave a comment. JANUS picks it up tomorrow night.

This is not "AI in your IDE." This is **a coworker who works the night shift.**

The five AGI properties (per the user's stated north star, 2026-04-19) define when we declare success:

| Property | What it means concretely | How JANUS gets there |
|---|---|---|
| **Takes arbitrary tasks in domain** | Any GitHub issue with sufficient acceptance criteria can be classified and shipped end-to-end | Already partially true (smoke test = closed task). Phase G makes it true at issue scale. |
| **Knows what it doesn't know** | When LCN consult returns no prior art, the orchestrator acknowledges it and applies extra caution rather than fabricating confidence | Phase D-2 wires the consult; the recall-miss semantics are already in CONSULT-PROTOCOL.md |
| **Improves methodology from outcomes** | Failed missions produce Error entities with failure_class taxonomy; meta-agent proposes orchestrator/agent prompt updates; eval-runner A/B tests them | Phase J — continuous from Phase D onward |
| **Transfers knowledge across projects** | A Convention learned in one repo (e.g., "always parameterize SQL queries") applies in another via cross-repo LCN | Phase I (Phase 6.2) — gates on D |
| **Quality is measurable** | Reviewer scores, eval suite pass rates, mission outcome distributions, mean cost per mission, mean wall-clock per mission | Already partial — quality_metrics.py exists, eval_runner.py exists |

The two-minds bet (§3) is what makes #2 and #3 plausible. Without LCN, JANUS is "agent pipeline that ships features." With LCN, it's "agent pipeline that ships features *better over time*."

---

## §3 — The Two-Minds Architecture (the bet)

JANUS commits to **two minds yoked together**:

- **GENESIS** — the deliberate, System-2 face. Mission state machine, role prompts, quality gates, healing protocol, structured agent dispatch. This is what already works. It's the orchestrator.md + protocols + agent files + skills.
- **LCN (Brain)** — the implicit, System-1 face. Persistent memory today; cognitive substrate eventually. SQLite-backed entity store now (`lcn_write.py`/`lcn_read.py`/`consult.py`); spiking neural network with forward-mode JVP eventually (`Brain/lcn_brain/`).

Why two minds? Because **a coding agent without persistent memory is a coding agent that re-derives every decision every session**. Every "we tried this approach last sprint and it broke production" is a fresh discovery. Every Convention rediscovered is hours wasted.

The LCN entity schema (LCN-SCHEMA.md) defines five canonical entity types:

| Entity | When written | When read |
|---|---|---|
| **Decision** | Orchestrator chooses an approach during classify | Pre-plan consult (similar past decisions on touched files) |
| **Rejection** | Reviewer FAIL → orchestrator chose alternative; or mission complete with explicit "we considered X but didn't ship it" | Pre-plan consult (what we've already ruled out) |
| **Error** | Healing protocol fires on a failure; failure_class enforced from bounded taxonomy | Pre-dispatch consult (known pitfalls for top-5 implied failure classes) |
| **Pattern** | Reviewer flags a recurring shape; or coder uses a construct >2 times in a single mission | Implicit — patterns become Conventions when corroborated |
| **Convention** | Pattern reaches confidence ≥3, OR human explicitly canonicalizes it | Pre-dispatch (failure prevention rules) + post-verify (which conventions apply to touched files) |

The bet is that **these five entity types, queried at three mandatory consult points (pre-plan, pre-dispatch, post-verify), are sufficient to make JANUS measurably better over time**. The CONSULT-PROTOCOL.md documents the wire format. The capability_assessor.py gates which missions pay the consult cost (MVP missions skip; Production+ missions inject).

The forward-compat bet: **the entity schema is stable; the storage is swappable**. Today, SQLite + trigram similarity. Tomorrow, when the Notion swarm's spec-LCN v1 (neuromorphic substrate, spike-encoded input, SSF ODE, RCD recurrence, ODE-plastic readout) ships, we swap the storage layer, not the contract. Same five entity types, different cortex underneath. Phase H is that swap.

This is why Phase A–C are critical. They're not "build the Brain because it'd be cool." They're "build the Brain because the entire two-minds architecture has been aspirational for 14 days and remains aspirational until 49/49 tests pass."

---

## §4 — The Phases

### Phase A — Brain Unblock

**Goal**: 42/49 of the Brain's existing tests pass. Move the LCN from "0% functional" to "85% functional" with three mechanical fixes.

**Why now**: This is the bottleneck for everything in §3. Every other LCN-dependent phase (D, G, H, I, J) is downstream of this. The work is mechanical — install deps, fix two known bugs, run pytest. There's no architectural decision to make, no research to do, no judgment call.

**Prerequisites**:
- None. (Optional: confirm `Brain/lcn_brain/pyproject.toml` lists JAX/jaxlib/flax as dependencies, which per JANUS-STATE.md it does.)

**Concrete steps**:
1. Activate the Brain's venv (or create one): `cd Brain/lcn_brain && python -m venv venv && venv\Scripts\activate`
2. Install deps: `pip install jax jaxlib flax numpy` — note: JAX on Windows historically had issues; if `pip install jax[cuda12]` fails, fall back to CPU-only `pip install jax`. CPU is fine for the test suite; GPU only matters for full-scale Burgers' training in Phase C.
3. Run the test suite: `pytest tests/ -v`. Expected: ~42 of 49 tests pass with `ImportError` collection failures resolved. The 7 failing tests will be the ones that exercise `lcn_jvp` (Phase B's target).
4. Fix `lcn/readout.py` line 84 — change `return u * gate @ W_z.T` to `return (u * gate) @ W_z.T`. Re-run tests; one more should pass.
5. Fix `tests/test_ssf.py` line ~103-107 — the aux unpack is wrong. The scan returns `(final_carry, stacked_outputs)` where stacked is `(h_new, (a_t, B_t))` per step. Inspect the actual shape and fix the destructure. Re-run; one more should pass.
6. Run `bash CI/grep_no_grad.sh` to confirm the no-`grad` invariant holds. (Forward-mode autodiff means we should never use `jax.grad`; only `jax.jvp`. The CI script greps for forbidden patterns.)

**Acceptance criteria**:
- `pytest tests/ -v` reports ~42 PASS (allowing 1-2 wiggle for transient JAX setup issues).
- The 7 remaining failing tests are all `lcn_jvp`-related (e.g., `test_train.py::test_one_dir`, anything that imports `from lcn_jvp import ...`).
- `CI/grep_no_grad.sh` exits 0.
- No regression in JANUS itself — `python -m pytest tests/test_lcn_write.py tests/test_lcn_read.py tests/test_capability_assessor.py tests/test_consult.py` still all green.

**Time**: 30-90 minutes wall clock (mostly waiting for `pip install jax`).

**Cost**: ~$0.05-0.10 if delegated to Claude Code; $0 if user does it manually (mostly waiting on pip).

**Risk**: LOW.
- *JAX install fails on Windows*: mitigation — fall back to CPU wheel; if even that fails, install via WSL2 or Docker; if those fail too, this becomes a Phase A blocker that needs research-level work to resolve. Probability: ~5%. If it fires, the Brain is dead until we fix it; this becomes the single most important issue in the project.
- *More than the two known bugs surface*: mitigation — read the actual test failures; if there are 3-4 small bugs, fix them all in this phase; if there are 10+ bugs, escalate to a research-grade session.
- *The grep_no_grad invariant is violated by something we didn't expect*: mitigation — investigate and either fix the offending code or update the CI script's allowlist with rationale.

**Verification path**: pytest output, end of Phase A. Want to see ~42/49 PASS with all collection errors resolved.

**Research/spec deps**: None. This is pure engineering.

**What this unlocks**:
- Phase B becomes a contained, well-scoped problem with clear test signals (the 7 failing tests tell us exactly which `lcn_jvp` functions are needed).
- All downstream phases (C, D, G, H, I, J) become reachable.

---

### Phase B — Write `lcn_jvp` (the hard one)

**Goal**: Implement the 5 functions of the `lcn_jvp` package per Spec §4.10 (Notion: Language Cognition Network — Architecture Specification). All 49 of the Brain's tests pass. Variance regression check (1/√N) succeeds.

**Why now**: Phase A confirms that *only* `lcn_jvp` is missing. Phase B is the actually-hard intellectual work in the Brain arc — implementing JVP estimators with antithetic variates against a reference. Once shipped, the Brain has a working training loop. From there, the rest of the Brain arc (testbed, integration) is mechanical.

**Prerequisites**:
- Phase A complete (42/49 tests passing, JAX works locally)
- Read access to Spec §4.10 (Notion AI Coding Tools Research Library has the LCN spec link; `Brain/lcn_brain/CONTEXT.md` has a 500-line summary written for Claude)
- An understanding of forward-mode autodiff (or willingness to read JAX docs while implementing)

**Concrete steps**:
1. **Read Spec §4.10** end-to-end. Take notes on the JVP estimator: $\hat g_\theta = (1/N) \sum v^{(n)} (\partial_\theta L_\sigma \cdot v^{(n)})$ — antithetic means we use pairs $(v, -v)$ to reduce variance.
2. **Stub all 5 functions returning zeros**:
   - `sample_direction(key, shape, distribution="normal") -> array` — sample $v \sim N(0, I)$ given a JAX PRNGKey
   - `antithetic(u, v) -> tuple` — return $(u + \sigma v, u - \sigma v)$ pair given a stack-tunable $\sigma$
   - `jvp_activity(forward_fn, u_tau_prev, pair, rng_key, smoothing_sigma, active_proj, pullback, ...) -> dict` — the main estimator. Computes $\hat g_\theta$, returns dict with `g_hat`, `variance_estimate`, `n_samples`
    - `column_norm_probe(forward_primal_fn, u_tau_prev, basis_idx) -> float` — L2 norm of one Jacobian column via finite-difference probing
   - `active_set(dh_trace, epsilon) -> tuple` — return `(projection, d_k)` where `d_k` is the active dimension count
3. Run pytest. Expect: all 7 tests fail with assertions about correctness (not import errors). This is correct — we have stubs.
4. **Implement `sample_direction`** — straightforward `jax.random.normal(key, shape)`. Verify with the test that probes its statistics.
5. **Implement `antithetic`** — also straightforward; pair generator with σ smoothing.
6. **Implement `kappa_probe`** — random unit-vector iteration to estimate spectral norm of the Jacobian. Reference: power iteration, but adapted for forward-mode.
7. **Implement `active_set`** — given a trajectory `dh_trace` and threshold `ε`, return the indices where `|dh| > ε` and the cardinality. Spec §4.10 has the formal definition.
8. **Implement `jvp_activity`** — the heavy lifter. Uses `jax.jvp(forward_fn, (primals,), (tangents,))` with antithetic pairs. Returns the estimator $\hat g$ and its variance.
9. Run `pytest tests/test_train.py -v`. Expect: all `test_one_dir`, `test_train_one_tick`, `test_train_one_tick_heun` tests pass. The variance regression check (1/√N) might be a separate test — verify that increasing N samples drops variance at the expected rate.
10. **Write `tests/test_lcn_jvp.py`** with at least 8 cases:
    - `sample_direction` returns correct shape + reasonable statistics
    - `antithetic` returns the expected pair structure
    - `jvp_activity` matches a finite-difference baseline within tolerance
    - `jvp_activity` antithetic variance is lower than non-antithetic
    - `kappa_probe` returns a value in expected range for known matrices
    - `active_set` returns correct projections for known traces
    - Forward-mode invariant: `lcn_jvp` never calls `jax.grad` (grep test)
    - Performance smoke: estimator runtime stays under 100ms for default sizes

**Acceptance criteria**:
- `pytest tests/` → 49/49 PASS in `Brain/lcn_brain/`
- `pytest tests/test_lcn_jvp.py` → ≥8 PASS in your new test file
- Variance regression check passes: variance(N=1000) / variance(N=100) ≈ √(100/1000) ≈ 0.316 within 20% tolerance
- `bash CI/grep_no_grad.sh` still exits 0 — no `jax.grad` introduced anywhere
- The implementation is documented inline with references to Spec §4.10 equations

**Time**: 1-3 sessions of 1-2 hours each (3-6 hours total). The hard part is the conceptual leap on `jvp_activity`; once you understand the estimator, implementation is straightforward.

**Cost**: ~$0.20-0.50 if delegated to Claude Code with V4-Pro (research-grade reasoning). Use V4-Pro, not V4-Flash, for this — the cost differential is worth it.

**Risk**: MEDIUM-HIGH.
- *Spec §4.10 ambiguity*: mitigation — implement against the failing tests' expectations first; cross-reference with JAX `jvp` docs; if a test expects something the spec doesn't define, file a question to the Notion swarm.
- *Numerical instability*: mitigation — start with simple Gaussian smoothing; use `float64` where needed; add NaN guards in `jvp_activity`.
- *Performance regression*: mitigation — the spec doesn't bind us to a specific runtime; if the estimator is slow, document it and defer optimization to Phase C.
- *The math just doesn't work as designed*: this is the irreducible research risk. If after a session we can't get the variance regression to pass, we have evidence that the Brain architecture has a flaw. Mitigation: this is exactly what the 4-arm testbed (Phase C) is designed to catch — if Phase B can't ship a working `lcn_jvp`, Phase C's BPTT baseline arm gives us a fallback comparison.

**Verification path**: 49/49 tests pass + variance regression confirms 1/√N rate. If both hold, the Brain's training loop is provably working; Phase C becomes a smoke-test of the integration, not a research question.

**Research/spec deps**:
- Spec §4.10 (JVP estimator definition, antithetic variates, smoothing)
- Spec §4.11 (joint-necessity coupling — relevant if the Theorem 1 variance bound informs the test tolerances)
- The Notion swarm's "Tester" agent has been writing falsifier-designs for these theorems; if you can read the latest Tester log, do.

**What this unlocks**:
- Phase C (testbed integration)
- Phase D (LCN client wiring)
- Phase J (self-improvement via meta-agent learning loop)

---

### Phase C — 4-Arm Burgers' Testbed

**Goal**: The 4-arm comparison runs end-to-end. Loss vs T plot generated. A+C arm demonstrably outperforms BPTT baseline at T=1000 (or we discover why it doesn't).

**Why now**: Phase B shipped a working `lcn_jvp`. The 4-arm testbed is the **empirical validation** of the architecture. Without it, we've shipped untested theory; with it, we have evidence the LCN actually does what it claims.

**Prerequisites**:
- Phase A + B complete (49/49 tests passing)
- `Brain/lcn_brain/lcn/testbed/burgers.py` already exists (199 lines, code done)
- `Brain/lcn_brain/lcn/testbed/encodings.py` already exists (36 lines)
- `Brain/lcn_brain/lcn/testbed/arms.py` is currently a skeleton

**Concrete steps**:
1. **Implement `arms.py:run_arm()`** — replace the placeholder return with a full pipeline call:
   - encoder (LIF) → SSF (state filter) → clock (EMA ticks) → RCD (context distiller) → readout (plastic)
   - Each arm differs in the gradient path: BPTT uses `jax.grad`; A-only uses `jvp_activity` with active_set projection only; C-only uses plastic readout updates only; A+C uses both
2. **BPTT baseline arm** — implement reverse-mode BPTT for the comparison. Allowed to use `jax.grad` since this is the baseline (the no-grad invariant applies to LCN arms only). Add this exception to `CI/grep_no_grad.sh` with comment.
3. **Run T=10 sanity check** — quick smoke. All 4 arms should produce non-NaN loss values. If any arm produces NaN, debug before proceeding.
4. **Run T=100** — longer trajectory. Check that A+C loss is comparable to BPTT (within 2x).
5. **Run T=1000** — full validation. Generate `loss_vs_T.png` plot showing all 4 arms.
6. **1/√N variance regression** — re-run jvp_activity at N ∈ {10, 100, 1000} samples. Verify variance drops at √N rate. Plot `variance_vs_N.png`.
7. **Document findings in `Brain/lcn_brain/RESULTS-PHASE-C.md`** — include both plots, the T-loss table, the variance regression table, and a 1-paragraph honest interpretation. If A+C does NOT outperform BPTT, document that honestly — the architecture might need revision.

**Acceptance criteria**:
- All 4 arms produce non-NaN loss at T=1000
- A+C arm achieves loss within 1.5× of BPTT baseline at T=1000 (a stretch goal: A+C *beats* BPTT, which would be the architecture's flagship claim)
- Variance regression confirms 1/√N at N ∈ {10, 100, 1000}
- Two plots committed (`loss_vs_T.png`, `variance_vs_N.png`)
- `RESULTS-PHASE-C.md` documents findings honestly (success OR failure)

**Time**: 1 session of 2-3 hours. Most of the time is GPU compute for T=1000 runs.

**Cost**: ~$0.10-0.30 if delegated to CC for the implementation work. The actual training is local (RTX 3060), so no API cost.

**Risk**: MEDIUM.
- *A+C does not outperform BPTT*: this is bad but informative. Mitigation — document, file as Spec §4 issue with the Notion swarm, hold off on Phase D until architecture revision. Worst case: the "two minds" bet has a flaw and we need to revisit.
- *T=1000 doesn't fit in 12GB VRAM*: mitigation — gradient checkpointing, smaller hidden dimensions, or run on CPU for the validation run.
- *Plot generation fails because of matplotlib issues*: trivial. Use plotly/native instead.

**Verification path**: `RESULTS-PHASE-C.md` with two plots and a verdict.

**Research/spec deps**:
- Spec §4.15 (Burgers' 4-arm testbed) — the Notion swarm is currently writing this. If their version is more rigorous than what's in `Brain/lcn_brain/lcn/testbed/burgers.py`, sync.
- Spec §4.15.1 (RSC verification) — depends on §4.15.

**What this unlocks**:
- Phase D — we have empirical evidence the Brain works, so wiring it into JANUS is no longer speculative
- Confidence to declare the LCN architecture validated

---

### Phase D — LCN Client Wiring

**Goal**: The LCN server runs locally, `lcn_client.py` reports ONLINE, the orchestrator's SESSION START step 4 actually queries the Brain, and the @memory-writer agent writes Decisions/Errors back post-mission. The first feedback loop closes.

**Why now**: Phase C validated the architecture empirically. The Brain is now ready to be a real component. Wiring it into JANUS is the moment the two-minds bet stops being theoretical.

This phase has two sub-phases that can run in parallel after the LCN server is up.

#### Phase D-1 — Server + client connection

**Concrete steps**:
1. Write `Brain/lcn_brain/start-lcn.bat` (or extend if it exists). It should:
   - Activate the venv
   - Start a small HTTP server (Flask or FastAPI) on port 3737
   - Endpoints: `/query`, `/write`, `/health`, `/stats`
   - Backed by either the v0 SQLite (lcn_write/lcn_read) for simplicity, OR the trained Brain weights for the real thing — start with v0 for D-1, swap to Brain weights for D-3 (post-D-2)
2. Update `.opencode/tools/lcn_client.py` to actually hit `http://localhost:3737/health` and `…/query` and `…/write`. Currently it's offline-only.
3. Test: start the server, run `python .opencode/tools/lcn_client.py status` → expects `ONLINE`.
4. Document the server lifecycle in `Brain/lcn_brain/README.md` — how to start, how to stop, how it interacts with JANUS.

**Acceptance criteria**: `lcn_client.py status` reports ONLINE. A test query returns the expected entity from the seeded data.

**Time**: 1 session, 1-2 hours.

**Cost**: ~$0.10 CC handoff.

#### Phase D-2 — Re-attempt consult wiring (the C-2b retry)

The original C-2b was reverted because the orchestrator was 506 lines and adding a STEP 1.5 caused a length-runaway on Qwen. The orchestrator is now 419 lines (skill-extracted). Re-attempt with smaller surface.

**Concrete steps**:
1. Add STEP 1.5 to `.opencode/agent/orchestrator.md` — but **shorter than the C-2b version**. Target: 5-10 lines, not 35. Pure reference: "before any sub-agent dispatch on STANDARD+ missions, run `python .opencode/tools/consult.py --phase pre-plan --request "$REQUEST" --predicted-files "$FILES"`. Inject output verbatim into the next agent's role prompt."
2. Add corresponding instructions for pre-dispatch (in STEP 4) and post-verify (in QUALITY GATE step 1).
3. Add the "Memory Consult Protocol" section to `mission-protocol.md` — shorter than the C-2b version too.
4. Test: run a smoke test with `JANUS_CONSULT_ENABLED=1`. Confirm:
   - Orchestrator emits the consult bash call
   - Output is injected into role prompts
   - Footer signature `-- injected by CONSULT-PROTOCOL v1, queries: N, results: M` appears
   - No length-runaway (orchestrator turns stay under 5K output tokens)

**Acceptance criteria**: Smoke test attempt 13 passes with consult enabled. Seam scorecard ≥ 22/25 (no regression vs attempt 12's 24/25). Footer present in injected sections. No reason:length step_finishes.

**Time**: 1 session, 2-3 hours including smoke test.

**Cost**: ~$0.30 — most of it on the smoke test itself.

#### Phase D-3 — Memory write-back

**Concrete steps**:
1. Add post-mission hook in orchestrator.md (Tier 4 PROJECT, step 7): @memory-writer dispatched with the mission summary.
2. @memory-writer reads `mission.json`, extracts:
   - The classify Decision (chosen_approach, file_paths, outcome)
   - Any Error events from the healing protocol
   - Any new Patterns the reviewer flagged
3. Calls `lcn_client.write_entity()` for each.
4. Verify: after a smoke test, `python .opencode/tools/lcn_read.py consult '{"type": "by-mission-similarity", "title": "smoke test", "scope_hash": "", "top_k": 5}'` returns the just-completed mission.

**Acceptance criteria**: Two consecutive smoke tests; the second one's pre-plan consult includes content from the first. The feedback loop is closed.

**Time**: 1 session.

**Cost**: ~$0.30.

**Risk for Phase D overall**: MEDIUM.
- *D-2 length-runaway again*: lower probability than C-2b because of skill extraction, but not zero. Mitigation — keep STEP 1.5 short (≤10 lines); kill switch via `JANUS_CONSULT_ENABLED=0`; revert path is `git revert` of the wiring commit.
- *D-3 writes pollute LCN with low-quality entities*: confidence-floor checks already in `lcn_write.py`; periodic pruning (deferred to a v1 hygiene pass).
- *D-1 server doesn't restart on Windows reboot*: not auto-starting initially. User manually runs `start-lcn.bat` at the start of each work session. Auto-start is a Phase F-vicinity nicety.

**What this unlocks**:
- Phase G (autonomous queue) — JANUS now has feedback loops, so unattended runs accumulate value
- Phase J (self-improvement) — Decisions and Errors are actually written; meta-agent has data to work with
- The two-minds architecture is *real*, not aspirational

---

### Phase E — Provider Resilience (Session R: the fallback ladder)

**Goal**: Build the model fallback ladder I designed earlier. Detect length-runaway, silent stall, seam-0-stop, 429 death loop, wall-clock-exceeded; auto-restart on next-rung model. Audit log per-attempt.

**Why now**: Three pivots in 36 hours during the V3.2/V4-Flash arc each cost ~30-60 min of human attention. This phase amortizes that across all future runs. Especially important once Phase G (overnight queue) goes live — you can't manually intervene at 3am.

This phase **can run in parallel with Phases B/C/D** if you want a second CC track. It's not Brain-dependent.

**Prerequisites**:
- The detailed handoff prompt is already written: `MagnumOpus/cc-session-r-fallback-ladder.md`
- Just paste it into Claude Code

**Concrete steps**: see the handoff prompt. Summarized:
1. Build `MagnumOpus/scripts/run_with_fallback.py` (~300 LOC)
2. Build `tests/test_run_with_fallback.py` (~12+ tests, no live API)
3. Update `run_attempt_11.ps1` to call the wrapper instead of `opencode run` directly
4. Write `MagnumOpus/SESSION-R-FALLBACK-LADDER.md` operator doc

**Ladder (current cost rule)**:
- Rung 1: `deepseek/deepseek-v4-flash` ($0.14/$0.28, 1M context)
- Rung 2: `deepseek/deepseek-chat` (V3.2 alias, $0.27/$0.40, 164K context)
- Rung 3: `moonshotai/kimi-k2.6` ($0.95/$4.00, 256K context, agentic-tuned)

**Detection signals**:
- Length runaway: `step_finish reason:length`
- Silent stall: `step_finish reason:other AND output_tokens:0`
- Seam-0-stop: `step_finish reason:stop AND output<100 AND no tool_use AND elapsed<60s`
- 429 death loop: 3 consecutive errors within 5 min, no successful step_finish between
- Wall-clock: total elapsed > N minutes without `=== SEAM REPORT ===`

**Acceptance criteria**: ≥12 unit tests green, dry-run validates ladder, runner script integrated.

**Time**: 1 session, 30-60 min.

**Cost**: ~$0.10-0.20 CC handoff.

**Risk**: LOW. The wrapper is contained; failure modes are well-understood; tests use mocked JSON streams (no live API).

**What this unlocks**:
- Phase G (overnight queue) — required prerequisite for unattended runs
- Confidence to deploy on shakier providers (Cerebras for sub-agent work) without single-point-of-failure risk

---

### Phase F — GUI Polish

**Goal**: Wire the 6+ GUI features that exist in the worker API but have no UI widgets. The PySide6 desktop GUI feels complete and competitive with Cursor/Cline.

**Why now**: After Phases A-D the engine works; after Phase E it's resilient. Phase F makes the *experience* match. Each feature is a small surface; collectively they make JANUS feel like a real product.

**Concrete steps** (each is a separate small commit):

1. **Plan Mode toggle** — checkbox in toolbar → `worker.send_input(plan_mode=True)`. Visual indicator when active. Keyboard shortcut: Ctrl+P.

2. **File attachment** — paperclip button + `QFileDialog` → `worker.send_input(file=path)`. Show attached file name above input. Drag-and-drop into chat area.

3. **Slash command palette** — `/` key triggers popup with: `/undo`, `/redo`, `/share`, `/init`, `/review`, `/lint`, `/repomap`. Up/down to navigate, Enter to confirm. → `worker.send_input(slash_command=True)`.

4. **Undo / Redo buttons** — toolbar buttons with disabled state when nothing to undo. → `worker.send_input("/undo", slash_command=True)`. (Snapshot system already enabled in opencode.json.)

5. **Session Fork button** — in sessions tab, fork icon next to each session row. → `worker.send_input(fork=True, title=...)`. Prompts for new title via QInputDialog.

6. **Session Title on New Session** — `new_session()` opens QInputDialog asking for title. → `worker.send_input(title=...)`. Skip if user presses cancel.

7. **Model list refresh** — toolbar button + auto-poll once per session. `opencode models --refresh` → repopulate model combo. Show toast "Models refreshed (N available)".

8. **Mission tab live status** — when a PROJECT mission is running, the Mission tab shows the current feature, last action, last 5 log lines from blackboard.json. Auto-refresh every 2s.

9. **Memory tab supermemory integration** — show recent memories from the supermemory plugin (currently 9 project + 1 user memories per JANUS-STATE.md). Search box. Manual delete.

10. **Repo map sidebar** — Files tab gains a "Repo Map" sub-tab. Renders the repomap.py output as a tree with importance scores. Click a file → opens it in editor.

**Acceptance criteria**: each feature passes a manual click-through test. No regressions in existing chat flow. Style.qss honored throughout.

**Time**: 1-2 sessions, depending on how many features you ship per session. Each feature is 30-90 min.

**Cost**: ~$0.30-0.80 CC handoff (each feature is small).

**Risk**: LOW. UI work is contained; signal/slot pattern protects the worker thread; rollback per-feature is easy.

**What this unlocks**:
- Daily-use ergonomics (you actually use it for hand-coding via the GUI)
- Demo-ability (if you ever want to show JANUS to someone, the GUI matters)

---

### Phase G — Autonomous Overnight Queue

**Goal**: JANUS picks up GitHub issues from a curated queue, runs missions on them overnight, opens draft PRs, and produces an honest morning report. You sleep through it.

**Why now**: Phase D closed the LCN feedback loop. Phase E gave us provider resilience. Phase F gave us the GUI to monitor it. Phase G is the moment JANUS becomes an actual coworker.

**Prerequisites**:
- Phase D-1, D-2, D-3 complete (LCN online, consults wired, write-back working)
- Phase E complete (fallback ladder)
- GitHub CLI authenticated (`gh auth login`)
- A repository with ≥5 well-scoped issues (acceptance criteria, file hints, tier-classifiable)

**Concrete steps**:

1. **/issue-scan command (already exists)** — scans GitHub issues, classifies by complexity, queues TINY/STANDARD for automation. Refine the classifier:
   - TINY = single-file change, <30 lines, <2 acceptance criteria
   - STANDARD = multi-file, known patterns, clear requirements, ≤10 files predicted
   - SKIP for now: COMPLEX, PROJECT, RESEARCH (these need human input)
   - Queue location: `.opencode/issue-queue.json`

2. **/issue-run command (already exists)** — pulls from the queue and starts missions. Update to:
   - Respect a per-night budget cap (default $2.00)
   - Respect a per-mission cap (default $0.30)
   - Run sequentially, not parallel, to avoid Cerebras-style rate-limit cascades
   - On any mission failure, log to `error_logger.py` and move to next issue (don't halt the queue)

3. **Scheduled task wrapper** — Windows Task Scheduler entry:
   - Runs at, say, 11pm
   - Starts opencode serve in background
   - Calls `/issue-run`
   - On completion, writes `MagnumOpus/morning-report-<date>.md`
   - Stops opencode serve
   - Optional: sends a desktop notification

4. **Morning report format**:
   ```markdown
   # JANUS Morning Report — 2026-05-15
   
   ## Missions run: 3
   - issue-#142 ✅ — feat: add CSV export to user dashboard (PR #156)
   - issue-#143 ⚠️ — fix: auth retry logic (PR #157, reviewer flagged 2 medium issues)
   - issue-#144 ❌ — chore: dependency bumps (failed at quality gate, retry tomorrow)
   
   ## Cost: $0.87
   ## Wall clock: 2h 14min
   ## Errors: 1 (recovered via fallback to Kimi K2.6)
   
   ## Lessons appended: 2
   - Convention: PR descriptions should always include test plan section
   - Error: `pip-audit` doesn't ship on RTX 3060 default Python install
   ```

5. **Safety nets**:
   - Hard cost cap per night ($5.00 default; abort the queue if exceeded)
   - Hard wall-clock cap (3 hours; abort if exceeded)
   - Hard issue cap (5 missions per night; queue rest for tomorrow)
   - Pre-flight check that working tree is clean before each mission (already in run_attempt_11.ps1)
   - Each PR opens as `--draft` so nothing accidentally merges

**Acceptance criteria**:
- 5 consecutive nights with at least one successful mission per night
- 0 nights where JANUS pushed code that breaks main branch (drafts only, you review in the morning)
- Cost stays under $2/night average
- Morning report is honest about failures (not just successes)

**Time**: 1 session for the wrapper + scheduling, then 5 nights of empirical validation.

**Cost**: ~$0.30 for the wrapper build, ~$2-5/week for the actual nightly runs.

**Risk**: MEDIUM-HIGH (this is where things get scary).
- *JANUS makes a destructive commit*: mitigation — drafts only, never auto-merge, mission branch isolated from main, working-tree-clean check, explicit-paths commit (no `git add -A`), git_ops.py reset-before-staging fix already shipped.
- *Cost overrun*: mitigation — multiple cost caps (per-mission, per-night, per-week), email alert when exceeded.
- *Bad PR pollutes the project*: mitigation — drafts only, you review every PR before merge, easy to close-without-merge.
- *Provider goes down at 2am*: mitigation — Phase E fallback ladder, audit log for forensics.
- *Issue queue fills with un-doable issues*: mitigation — the classifier marks COMPLEX/PROJECT/RESEARCH as SKIP; you maintain the queue manually.

**What this unlocks**:
- Real productivity multiplier (30-50% of routine issues handled while you sleep)
- Empirical data on which mission types JANUS handles well vs poorly
- The "AI coworker working the night shift" reality (per §2 north star)

---

### Phase H — Cortex Transition (when spec-LCN v1 ships)

**Goal**: When the Notion swarm publishes spec-LCN v1 (the actual neuromorphic substrate), swap JANUS's storage layer from SQLite v0 to the cortex. Same entity contract, different substrate underneath.

**Why now**: This is **gated on Notion swarm output**, not on our work. We don't control when this is ready. We do control how cleanly we can adopt it when it is.

**Prerequisites**:
- Notion swarm publishes spec-LCN v1 (likely §4.16+ closure; could be weeks or months)
- §4.10 JVP estimator in spec-LCN matches our `lcn_jvp` (or we adapt)
- Code Synthesizer agent (Notion swarm) ports the JVP micro-library to Python (already shipped per the Apr 2026 research library — §4.10 ✅ shipped)
- Phase D complete (we have a working LCN client architecture to swap)

**Concrete steps**:

1. **Read the v1 spec end-to-end** when published. Cross-check against LCN-SCHEMA.md forward-compat mapping. Identify any contract changes.

2. **Build `.opencode/tools/lcn_cortex.py`** — same function signatures as `lcn_read.py` (by_file, by_failure_class, by_mission_similarity, by_convention_scope, search) but backed by the cortex:
   - Spike-encoded input (mission context → spike trains)
   - SSF ODE recurrent state
   - RCD context distillation
   - ODE-plastic readout for query results

3. **Dual-write phase** — for one calendar week, write entities to BOTH backends:
   - SQLite v0 (existing)
   - Cortex v1 (new)
   Confirm parity by sampling: random query, both backends, check agreement above some threshold (TBD; depends on cortex query semantics).

4. **Feature flag swap** — `JANUS_LCN_BACKEND=v0` or `=cortex`:
   - Default v0 for stability
   - Switch to cortex once dual-write parity is confirmed

5. **Decommission v0** — once cortex has been default for one calendar month with no regressions, archive `lcn_write.py`/`lcn_read.py` to `MagnumOpus/reference/` and update `consult.py` to import from `lcn_cortex` only.

**Acceptance criteria**:
- Dual-write parity within tolerance for at least 1000 sample queries
- Zero mission failures attributable to LCN backend during the dual-write phase
- After cortex-default switch, smoke test still scores ≥22/25
- Documentation: `Brain/lcn_brain/V0-TO-V1-MIGRATION.md` covers the swap

**Time**: 2-4 sessions across 1-2 calendar months (mostly waiting for v1 to ship + dual-write observation period).

**Cost**: ~$1-3 for build + dual-write smoke testing.

**Risk**: MEDIUM-LOW.
- *v1 contract differs from forward-compat assumption*: mitigation — LCN-SCHEMA.md was drafted with this in mind; semantic adapter layer can absorb minor changes.
- *Cortex query semantics produce surprising results*: mitigation — dual-write phase catches this; can revert via feature flag.
- *Hardware doesn't fit the cortex*: mitigation — measure during dual-write; if VRAM exceeded, defer until hardware upgrade.
- *v1 never ships from Notion swarm*: mitigation — v0 is good enough indefinitely. The forward-compat work cost us nothing extra (it was always going to be the right schema).

**What this unlocks**:
- The "cortex" framing becomes literal, not metaphorical
- Phase I (cross-project brain) gates here — needs the substrate to actually share state across repos, which v0 SQLite can't really do

---

### Phase I — Cross-Project Brain (Phase 6.2)

**Goal**: One LCN, shared across all your repos. Conventions learned in `OpenCode` apply to `MLP-Survival`. Errors hit in `clank.world` lorebook tooling surface as known pitfalls in `Afterlife: Equestria`. The "transfers knowledge across projects" AGI property becomes literal.

**Why now**: Single-project LCN (Phases A-H) proves the architecture. Cross-project is the multiplier — and it's only feasible after Phase H makes the substrate cortex-backed (SQLite v0 doesn't compose well across repos).

**Prerequisites**:
- Phase H complete (cortex-backed LCN)
- At least 3 repos in active use (you have OpenCode, MLP Survival, clank.world tooling, Afterlife: Equestria, lorebook tooling — at least 5 candidates)

**Concrete steps**:

1. **Scope policy** — define what crosses repos and what doesn't:
   - **Crosses**: Conventions, Patterns, Errors with non-project-specific failure_classes (model-routing, edit-shape-error, invented-tool, etc.)
   - **Stays**: Decisions tied to specific files, project-specific Conventions (like "OpenCode wraps opencode.cmd, never call it directly"), project-private secrets/credentials
   - Each entity gets a `scope` field: `repo:<name>` for project-private, `global` for cross-repo, `tag:<topic>` for topic-shared (e.g., `tag:python-cli`)

2. **Shared LCN service** — one cortex instance, multiple consumers:
   - Either: each project's `lcn_client.py` points at the same `localhost:3737` server
   - Or: each project has its own server, with a periodic sync to a `~/.lcn/global/` shared store
   - First option simpler; second option more robust to project-specific corruption

3. **Cross-repo query semantics** — `consult.py` learns to filter by scope:
   - "Show me Conventions that apply to this repo OR are global" — default
   - "Show me everything across all repos that touched a file matching this glob" — explicit cross-repo flag
   - "Show me Errors of failure_class X regardless of repo" — global query

4. **Privacy + redaction** — when an Error from clank.world is queried by JANUS-OpenCode:
   - File paths get hashed (`auth.py` is fine; `clank-world/secrets.json` is not)
   - Symptom/root_cause/fix_applied get vibeguard-style redaction (already a plugin, reuse)
   - Project tag is preserved so user can see "this Error came from clank.world" without exposing details

5. **Eval suite update** — add cross-repo evals:
   - "Given a Convention from project A and a similar mission in project B, does the orchestrator correctly invoke the Convention?"
   - "Given an Error from project A, does its failure_class surface in project B's pre-dispatch consult?"

**Acceptance criteria**:
- ≥3 projects share an LCN
- Eval suite cross-repo cases pass at ≥80%
- No leak of project-private content into cross-repo queries (manual audit)
- User can disable cross-repo lookups per-project via env var

**Time**: 2-3 sessions.

**Cost**: ~$1-3.

**Risk**: MEDIUM.
- *Privacy leak*: HIGH severity if it fires. Mitigation — vibeguard-style redaction baseline; manual audit before going live; optional kill switch per project.
- *Cross-repo entities pollute single-repo missions with irrelevant context*: mitigation — relevance threshold (similar to the SIMILARITY_FLOOR in consult.py); per-query scope filters.
- *Performance*: cross-repo queries hit a larger database. Mitigation — cortex indexing; cache layer if needed.

**What this unlocks**:
- The multi-project AGI property
- Real economy of scale on the meta-agent's prompt/routing improvements (one experiment helps all projects)
- The "I've seen this before" experience that makes JANUS feel intelligent rather than encyclopedic

---

### Phase J — Self-Improvement Loop (continuous, from D onward)

**Goal**: JANUS gets *measurably better at running JANUS over time*. Meta-agent runs after every Enterprise-tier mission, proposes prompt/routing changes, A/B tests against the eval suite, auto-applies if improvement exceeds threshold.

**Why now**: This is the closed feedback loop that closes the AGI bet. Phases A-D ship the components; Phase J makes them self-tuning. It runs continuously from Phase D-3 onward.

**Prerequisites**:
- Phase D-3 (memory write-back working — meta-agent has data)
- `eval_runner.py` (already exists)
- Sufficient mission history (~20+ Enterprise-tier missions to have meaningful data)

**Concrete steps**:

1. **Meta-agent expansion** — currently the meta-agent file at `.opencode/agent/meta-agent.md` is "post-mission: proposes agent prompt + model routing improvements." Expand it to:
   - Read the last N Decisions and Errors from LCN
   - Identify patterns: "the orchestrator chose X 12 times, 8 succeeded; chose Y 8 times, 7 succeeded — suggest preferring Y by default"
   - Identify failure clusters: "edit-shape-error fired 5 times in the last 20 missions, all on @coder, all on TypeScript files — suggest adding a TypeScript-specific guard to the @coder prompt"
   - Output structured proposals: file, line, change, rationale, expected eval delta

2. **A/B harness** — extend `eval_runner.py`:
   - Apply the proposed change to a feature branch
   - Run the eval suite on both branches (control + treatment)
   - Compare scores
   - If treatment improves by ≥5 points AND no eval regresses, mark APPROVED
   - If treatment is mixed, mark NEEDS-HUMAN
   - If treatment regresses, mark REJECTED with diagnostic

3. **Auto-apply policy** — APPROVED proposals can auto-apply with these guards:
   - Only modify files whitelist: `.opencode/agent/*.md` except `orchestrator.md` (orchestrator is high-stakes; always human-review)
   - Tagged commit: `chore(meta): auto-apply meta-agent proposal #N` with rationale + eval delta
   - Reversible: each auto-apply gets a corresponding eval-baseline snapshot for easy revert
   - Rate-limited: max 1 auto-apply per week to avoid drift cascade

4. **Drift detection** — periodically (monthly?), run the full eval suite from a *clean baseline* (orchestrator.md from 6 months ago) and compare to current. If overall score has *dropped* despite individual auto-applies "improving" things, that's drift. Halt auto-apply, escalate to human.

5. **Convention extraction** — when reviewer flags a recurring fix shape, the meta-agent proposes promoting it from Pattern to Convention. Same A/B harness; auto-apply if approved.

**Acceptance criteria**:
- After 30 days of operation, ≥3 auto-applied proposals
- Eval suite overall score has improved by ≥10 points vs the Phase D baseline
- Zero drift events
- All auto-applies are reversible (verified by random spot-check)

**Time**: 1-2 sessions for the harness build, then continuous operation.

**Cost**: ~$0.50 build, ~$5-10/month operation (eval suite runs).

**Risk**: HIGH (this is where the system can *get worse*).
- *Auto-apply makes things worse via local optimum*: mitigation — drift detection; clean-baseline reruns; eval suite needs to be diverse enough that local optima don't dominate.
- *Meta-agent proposes harmful changes that pass evals by gaming*: mitigation — manual periodic review of auto-applied changes; eval suite designed to be hard to game; can disable auto-apply entirely.
- *Eval suite becomes outdated*: needs maintenance. Quarterly review.

**What this unlocks**:
- The fifth AGI property ("improves methodology from outcomes")
- The system genuinely *learns* rather than just *remembers*
- Demonstrable trajectory: "JANUS today vs JANUS 6 months ago" should be measurably better

---

## §5 — Risk Register

Cross-cutting risks not tied to a single phase. These are the things that could derail the entire roadmap.

| # | Risk | Severity | Probability | Mitigation |
|---|---|---|---|---|
| **R1** | DeepSeek V4 family becomes expensive or unavailable | HIGH | LOW | Fallback ladder includes Kimi K2.6, GLM-4.6 (Notion research); local Ollama models for offline workflows |
| **R2** | Brain architecture has a fundamental flaw (Phase C reveals A+C doesn't outperform BPTT) | CRITICAL | LOW-MEDIUM | Phase C is exactly the test for this; if it fires, escalate to Notion swarm; v0 SQLite LCN remains useful indefinitely |
| **R3** | Notion swarm spec-LCN v1 never ships | HIGH | LOW | v0 is good enough; Phase H is "nice-to-have, not must-have"; cross-project (Phase I) might still be possible with v0 + scope adapter |
| **R4** | Self-improvement loop introduces drift (Phase J) | HIGH | MEDIUM | Drift detection; clean-baseline reruns; manual disable switch |
| **R5** | Autonomous queue (Phase G) makes a destructive commit overnight | CRITICAL | LOW | Drafts-only PRs; no auto-merge; mission branch isolation; explicit-paths commits; reviewer always runs before commit |
| **R6** | User burnout from JANUS becoming a side project that never ends | HIGH | MEDIUM | Aggressive automation (Phase G) reduces required attention; clear phase boundaries with completion criteria; explicit "stop and ship" decision points |
| **R7** | Provider lock-in / migration cost too high to leave | MEDIUM | LOW | Multi-provider config; OpenRouter aggregator option (per Notion research); LiteLLM compatibility layer if needed |
| **R8** | Hardware bottleneck (RTX 3060 12GB) limits Brain training scale | MEDIUM | MEDIUM | Phase C measures this; if exceeded, options: smaller models, gradient checkpointing, cloud GPU rental, hardware upgrade |
| **R9** | Security incident (auto-applied code commits secret to repo) | CRITICAL | LOW | Vibeguard plugin redacts secrets pre-LLM; security-auditor agent runs post-merge; PR drafts manually reviewed |
| **R10** | OpenCode CLI (upstream) breaks compatibility | MEDIUM | LOW | Local POTATO/npm install pinned to v1.14.29; can defer upgrades; CONFIG-MAP.md documents internal assumptions |

---

## §6 — Cost Projections

### Per-phase costs (one-time)

| Phase | Build cost (CC handoff) | Validation cost |
|---|---|---|
| A — Brain unblock | $0.05-0.10 | $0 (local) |
| B — lcn_jvp | $0.20-0.50 (use V4-Pro) | $0 (local) |
| C — 4-arm testbed | $0.10-0.30 | $0 (local GPU) |
| D-1 — server + client | $0.10 | $0 (local) |
| D-2 — consult wiring | $0.30 | $0.10 (smoke test) |
| D-3 — memory write-back | $0.30 | $0.10 (smoke test) |
| E — fallback ladder | $0.10-0.20 | $0 (mocked tests) |
| F — GUI polish (10 features) | $0.30-0.80 | $0 (manual click-through) |
| G — autonomous queue (build) | $0.30 | $0 (validates over 5 nights) |
| H — cortex transition | $1.00-3.00 | $0.50 (dual-write smoke tests) |
| I — cross-project | $1.00-3.00 | $0.20 (eval suite cross-repo cases) |
| J — self-improvement build | $0.50 | $0 (eval suite reused) |
| **Total one-time** | **$4.25-9.30** | **$0.90** |

### Recurring costs

| Activity | Frequency | Cost per |
|---|---|---|
| Smoke test (validation) | Per phase + ad-hoc | $0.05-0.10 |
| Phase G overnight queue | Per night | $0.50-2.00 |
| Phase G overnight queue | Per week | $3.50-14.00 |
| Phase J eval suite runs | Per meta-agent proposal | $0.20 |
| Phase J meta-agent operations | Per month | $5-10 |
| Hand-coding via Claude Code (DeepSeek V4) | Per session | varies, ~$0.10-1.00 |

### Annual cost estimate (post-Phase J, all systems live)

- Overnight queue: $3.50/week × 50 weeks = **$175/year**
- Meta-agent + evals: $10/month × 12 = **$120/year**
- Hand-coding (your work): **highly variable**, estimate $300-600/year
- One-time builds (Phase A through J): **$5-10 amortized over years**

**Realistic annual ceiling for JANUS-the-system**: $500-1000. Compares favorably to a Cursor subscription ($240/year) once you factor in that JANUS is doing the work *for* you, not just helping you do it.

---

## §7 — Decision Log (open questions)

These are deferred decisions, in `PIPELINE-DECISIONS.md`. Cross-reference here:

- **D1**: When to transition v0 → v1 LCN (Phase H gate)
- **D2**: Split Strategy (Opus + V4-Flash) vs V4-Flash-only — current default is V4-Flash-only; revisit if missions show reasoning failures
- **D3**: Third rung of fallback ladder — Kimi K2.6 (current pick) vs GLM-4.6 vs Ollama local (free)
- **D4**: Phase G scheduling — every night vs alternate nights vs on-demand
- **D5**: Cross-project scope policy (D entities cross? Just Conventions?) — needs empirical data from Phase D-3
- **D6**: Auto-apply rate limit (Phase J) — 1/week vs 1/month vs 1/quarter
- **D7**: GUI features priority order — which 3 of 10 ship first?
- **D8**: When to declare AGI properties achieved (criteria? threshold?)
- **D9**: When to open-source (if ever) — JANUS-the-engine without your LCN data could be useful to others
- **D10**: When to write a paper / blog post about the two-minds architecture (probably after Phase C empirically validates it)

---

## §8 — Research Dependencies (Notion swarm)

The Notion AI Coding Tools Research Library (April 2026) and Language Cognition Network spec are external inputs. We can't accelerate them, but we can plan around their cadence.

| Spec section | Status (last check 2026-04-26) | Blocks which phase |
|---|---|---|
| §4.10 (JVP estimator) | ✅ shipped | Phase B |
| §4.11 (joint-necessity coupling) | ⚠️ in review | Phase B test tolerances |
| §4.12 (decoupled β-calibration) | ⚠️ in review | Phase C 4-arm testbed |
| §4.13 (sparse-spike tightness) | ⚠️ active | Phase C performance interpretation |
| §4.14 (non-stationarity) | ✅ shipped | Phase D-3 (when LCN evolves over time) |
| §4.15 (Burgers' 4-arm testbed) | ⚠️ in flight | Phase C |
| §4.15.1 (RSC verification) | ⚠️ DA attack surface open | Phase C confidence |
| §4.16 (long-horizon validation) | ⚠️ scope TBD | Phase H spec-LCN v1 readiness |

If you want to monitor swarm cadence: read `Sprint Log` in Notion weekly. Hot threads currently: Tester P1 K=50 baseline (~46h pending), W1 substance Σ_K conditioning (~68h unrebutted), Lucas Abram P3 reassignment (~32h past hard SLA per the LCN Theorist log).

When §4.16 closes and the Code Synthesizer ports the v1 implementation, Phase H gates open.

---

## §9 — Hardware Envelope

| Component | Spec | Implication for pipeline |
|---|---|---|
| GPU | RTX 3060 12GB VRAM | Fits Q4_K_M models up to ~13B params; JAX-on-GPU viable for Brain training; Burgers' testbed (small) fits comfortably |
| CPU | Ryzen 5 5600X (6-core) | Bottleneck for parallel sub-agent dispatch; 6 cores ≈ 3 simultaneous OpenCode subprocess invocations |
| RAM | 32 GB | Plenty headroom; Brain training doesn't typically RAM-bottleneck before VRAM |
| Storage | 4TB SSD + 1TB HDD | LCN database + smoke artifacts + Brain checkpoints fit easily |
| OS | Windows + PowerShell 5.1 | Compatibility tax: shell=True everywhere, cmd extension, taskkill for process tree, line-ending normalization (already done via .gitattributes) |

**Hardware upgrade triggers** (when to consider):
- Brain training at T=5000+ exceeds 6 hours wall clock → bigger GPU
- Local Ollama models can't fit a 30B+ for offline orchestrator role → bigger GPU
- Cross-project LCN exceeds 12GB cortex working set → bigger GPU
- More than 2 simultaneous Cowork sessions → need more cores

None of these are currently active; revisit after Phase C completes.

---

## §10 — The Creative-Writing Thread

JANUS isn't just a coding system. It's also a workstation for:
- **clank.world** — character profile generation (PList format) via @prompt-writer
- **MLP Survival** — GDScript game development
- **Afterlife: Equestria** — CYOA writing
- **Lorebook tooling** — Python scripts for managing character-world data

These threads share the engine but diverge in the `tier` taxonomy and `.opencode/rules/` content. Some implications:

1. **Don't let JANUS-the-coding-engine eat the creative pipelines.** The competitive systems (hooks, recipes, slash commands) need to support both. A rule that's useful for Python coding might be irrelevant for GDScript. Use glob-scoped rules.

2. **Cross-pollination is real.** A Convention learned in MLP Survival ("GDScript signal naming uses snake_case with `_changed` suffix") can become a Pattern in clank.world's Godot tooling. Phase I (cross-project brain) makes this explicit; before Phase I, it's lossy.

3. **Creative work has different acceptance criteria.** A character profile isn't "passes tests" — it's "feels like the character." This requires human review, always. JANUS's @prompt-writer can draft, but the user judges. **Don't try to automate creative judgment.**

4. **The clank.world thread might become the highest-leverage use of JANUS.** If your @prompt-writer agent gets really good at PList generation (high reviewer scores from you), JANUS becomes a creative force multiplier. This isn't on the §4 pipeline — it's a parallel track that benefits from the same Phases A-D infrastructure.

5. **Creative output goes to LCN too.** When @prompt-writer ships a character profile and you accept it, that's a Decision entity. Over time, LCN learns your taste. Phase D-3 (memory write-back) applies to creative work too.

---

## §11 — Crosscutting Concerns

These touch every phase. Worth maintaining as a discipline.

### Observability

- `error_logger.py` JSONL append-only — already shipped. Use it.
- Hooks (PreToolUse / PostToolUse / Stop) — already shipped. Add deterministic rule enforcement as patterns emerge.
- Audit log (Phase E fallback ladder) — per-attempt JSON in smoke-test-artifacts/.
- Mission summaries (Tier 4 PROJECT) — `MagnumOpus/cowork-report-*.md` per mission.
- Memory tab (GUI) — supermemory plugin already integrated.

### Security

- Vibeguard plugin — already shipped. Redacts API keys, emails, IPs, UUIDs before LLM calls.
- @security-auditor — already an agent, runs post-merge. Catches injection/auth/secrets/CVE.
- `permission: external_directory: allow` — set in opencode.json for sub-agent inheritance. Don't change without understanding the seam-13 implications.
- Drafts-only for Phase G PRs — never auto-merge.
- Cross-project privacy (Phase I) — explicit redaction policy.

### Cost discipline

- Per-mission cost cap (default $0.30, configurable in scheduler.py)
- Per-night cost cap (Phase G, default $2.00)
- Per-week cost cap (default $20)
- Annual budget review at end of Q1 / Q3
- Always default to V4-Flash; escalate to V4-Pro / Kimi only when proven necessary
- Anthropic models are OFF the JANUS orchestration menu. Reverify this rule annually.

### Reliability

- Fallback ladder (Phase E) — auto-recovery from 5 documented failure modes
- Healing protocol — already a skill. Retry limits, escalation paths.
- Stall-detection in orchestrator instructions — per-provider known issues documented
- Working-tree-clean preflight — only halts on untracked files, allows modifications. Already shipped.

### Hygiene

- Conventional commits (already enforced via git_ops.py)
- Smoke artifacts gitignored
- `.lcn/` gitignored
- Per-feature commits with explicit file paths (Finding C from batch 24, fixed)
- Stash-pop debris cannot leak into commits (Finding from attempt 12, fixed in `804dea2`)

### Documentation

- JANUS-STATE.md updated at session boundaries (current state)
- PIPELINE.md updated at phase boundaries (this doc, the trajectory)
- PIPELINE-DECISIONS.md updated when decisions get made
- `cowork-report-*.md` per mission
- `lessons.md` per session (post-mission lessons learned)
- Per-module AGENTS.md for context (already in `core/`, `ui/`)
- Brain `CONTEXT.md` is 500 lines — keep it tight, don't let it grow without bound

---

## §12 — North Star Alignment Check

Periodic test: are we still aimed at the right thing?

The five AGI properties (§2) translate to falsifiable checks:

1. **Takes arbitrary tasks in domain** → Eval suite includes ≥10 unseen issue archetypes; mission success rate ≥70% on unseen → ✅ at scale
2. **Knows what it doesn't know** → LCN consult miss rate is logged; on miss, orchestrator emits "no prior art" annotation; reviewer's "did the orchestrator over-claim confidence" check → measurable from D-3 onward
3. **Improves methodology from outcomes** → Phase J eval delta over time; quarterly trend analysis → measurable from J onward
4. **Transfers knowledge across projects** → Phase I cross-repo eval cases → measurable from I onward
5. **Quality is measurable** → reviewer scores tracked, eval suite passing rate, mean cost per mission, mean wall-clock per mission → already measurable

When all five are passing at the thresholds above, JANUS has cleared its AGI bar. **This is not a binary moment** — it's a trajectory you measure quarterly. The first time all five are green simultaneously is "JANUS at maturity."

Estimated timeline (with full effort, no major setbacks):
- Phases A-D: 1-2 weeks
- Phases E-G: 2-3 weeks
- Phase H: blocked on Notion swarm; estimate 2-6 months
- Phase I: 1 month after H
- Phase J: continuous from D, full maturity in 3-6 months
- **All five AGI properties passing simultaneously**: 4-9 months from May 2026, depending on Notion swarm cadence

---

## §13 — Anti-Patterns (what we WILL NOT do)

These are the things we've learned NOT to do. Carry them forward; don't re-litigate.

1. **Anthropic models as JANUS orchestrator.** Cost ceiling violated at $3.50/day. Off the menu permanently.

2. **Cerebras for orchestrator role.** TPM ceiling is hard-bounded by provider. The accumulated context (system prompt + tool history + max_tokens reservation) exceeds 30K TPM on every call once SESSION START expands. Cerebras is fine for sub-agents (small calls); never primary.

3. **Manual smoke-test intervention.** Phase E (fallback ladder) is the systemic fix. Once it ships, manual intervention should drop to ≤1 per month.

4. **Tight coupling to clank.world.** JANUS-the-engine and clank.world-the-creative-pipeline share infrastructure (LCN, agents, GUI) but should remain logically separate. No `import clank_world.X` in `.opencode/`.

5. **Premature scaling.** Don't start Phase I (cross-project) before Phase D (single-project Brain works). Don't start Phase J (auto-apply) before Phase G (autonomous queue) has 30 days of mission history.

6. **Re-attempting failed sessions without redesign.** C-2b was reverted; D-2 is its successor with a different architectural assumption (smaller orchestrator surface). Each reattempt must materially change something, not just retry.

7. **Hardcoded model IDs in prompts.** `claude-code-prompt-27.md` was scrubbed of Qwen references because the Seam 0 hallucinated model name. Prompts stay model-agnostic; models are configured in `opencode.json`.

8. **`git add -A` in commit helpers.** Finding C from batch 24. `git_ops.py commit()` always uses explicit file paths. Stash-pop debris fix in `804dea2` reinforced this.

9. **Working-tree-clean preflight halting on modifications.** Old preflight halted on any modification (including the runner's own mission.json reset). Now halts on untracked files only. Don't regress.

10. **Letting orchestrator.md grow unbounded.** Skill extraction (current 419 lines) is the floor. Adding STEP 1.5 in C-2b at 506 lines blew the length budget. Phase D-2 must keep STEP 1.5 ≤10 lines.

---

## §14 — Living Document Maintenance

How to keep this useful as the project evolves.

**Update triggers**:
- Phase boundary (mark completed, log actuals vs estimates, link to commit hashes)
- Major architectural decision (cross-link to PIPELINE-DECISIONS.md)
- New risk surfaced (add to §5 risk register)
- Cost estimates exceeded by 2x or more (revise §6)
- Notion swarm spec change (update §8)
- AGI property crossed (update §12)

**Versioning**:
- Top-of-document "Last meaningful edit" date
- Per-phase status (NOT-STARTED / IN-PROGRESS / DONE / BLOCKED / ABANDONED)
- Append-only annotations on phases (don't rewrite history; show evolution)

**Cross-references**:
- JANUS-STATE.md for current state
- PIPELINE-DECISIONS.md for open questions
- PIPELINE-NORTH-STAR.md for the why
- Per-phase: link to the relevant CC handoff prompt, the relevant commit, the relevant test file

**When to retire / split this document**:
- If it exceeds ~3000 lines, split per-phase into individual files
- If a phase is fully shipped and stable for 3+ months, archive its details to `MagnumOpus/archive/`
- If the AGI bar is cleared, fork to `JANUS-2.md` for the next horizon

---

## End of PIPELINE.md

This is the spine. Update at phase boundaries. Don't rewrite — annotate.

The next concrete action is **Phase A**: install JAX, fix two bugs, run the test suite. Estimated 1 hour, ~$0.10. After it lands, 42/49 Brain tests pass and the entire downstream stack becomes reachable.

Phase A handoff prompt: TBD — write `MagnumOpus/cc-phase-a-brain-unblock.md` next.
