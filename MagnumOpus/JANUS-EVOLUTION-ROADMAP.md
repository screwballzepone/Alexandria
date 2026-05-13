# JANUS Evolution Roadmap

**Owner**: Screwball
**Drafted**: 2026-04-25 (post Phase 6.1 gate)
**Living document** — update as sessions land.

---

## North star

JANUS is **two minds yoked together**:

- **GENESIS** — the deliberate, System-2 face. Missions, role prompts, quality gates, healing.
- **LCN** — the implicit, System-1 face. Persistent memory today; cognitive substrate eventually.

The current LCN v0 (SQLite + entity schema in `.opencode/tools/lcn_write.py`) is **the bootstrap**, not the destination. The destination is a neuromorphic compute layer driving JANUS's cognitive functions — the neural network originally envisioned, currently being theorized as spec-LCN v1 by the Notion agent swarm (§4.x chain in `Language Cognition Network — Architecture Specification`, currently at §4.15).

The bridge: **LCN-SCHEMA.md's forward-compat mapping**. Entities (Convention, Pattern, Decision, Rejection, Error) map onto spec-LCN v1 readouts (stability-anchor, generalizing trajectory, etc.). When v1 lands, we swap the storage layer. Entities stay the same. **JANUS does not have to be rewritten when the cortex arrives.**

---

## What "actually works" means

A pipeline that ships features ≠ a pipeline that learns. The v0 work below is what closes the feedback loop. After it lands:

- JANUS *writes* every Decision/Error/Convention back to LCN
- JANUS *reads* prior LCN entities at the start of every mission
- JANUS *injects* relevant prior knowledge into sub-agent prompts
- The capability assessor classifies tier deterministically, not via LLM guess

When v1 ships, the same JANUS code path uses the cortex instead of SQLite. The v0 → v1 transition is a storage swap, not a feature rewrite.

---

## Session-by-session plan

Each session is sized so it fits in one Cowork morning. Each entry has:

- **Goal** — what's true after this session that wasn't before
- **Deliverables** — concrete files/commits
- **Open questions** — things we don't know enough to decide yet (tracked, not blocking)
- **Delegation** — what to outsource via Magnum Opus, what to keep on Sonnet here
- **Verification** — how we know it worked
- **Risk** — what could go wrong

### Session A — Seed LCN (TINY, ~30 min)

**Goal**: `.lcn/lcn.sqlite` exists with 16 entities (8 Convention + 8 Error). LCN is no longer empty.

**Deliverables**:
- `MagnumOpus/scripts/seed_lcn.py` — repeatable seeding script (reads both JSONL files, calls `write_many`)
- One run of the script → `.lcn/lcn.sqlite` populated
- Verification query showing 16 rows by entity_type
- Single commit: `chore: seed LCN with conventions + errors`

**Open questions**: none — mechanical work.

**Delegation**: keep on Sonnet (trivial). No Magnum Opus needed.

**Verification**: `python -c "import sqlite3; print(sqlite3.connect('.lcn/lcn.sqlite').execute('SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type').fetchall())"` → expects `[('Convention', 8), ('Error', 8)]`.

**Risk**: low. If seed validation fails on any entity, fix the JSONL file (more likely than module bug given write tests are green).

---

### Session B — Wire `capability_assessor.py` (TINY, ~30 min) ✅ DONE 2026-04-25

**Scope correction discovered during execution.** The original draft of this
session called for patching `.opencode/agent/orchestrator.md` to call
`capability_assessor.py` for runtime tier classification. **That was wrong.**

The orchestrator uses its own tier scheme (READ / TINY / STANDARD / COMPLEX
/ PROJECT / RESEARCH) for *dispatch* decisions. `capability_assessor.py`
implements TIER-CLASSIFIER.md's scheme (MVP / Production / Enterprise) for
*LCN write/consult regime* decisions. These are orthogonal concerns — they
should NOT be conflated. The orchestrator integration is deferred until
we decide whether to (a) map runtime-tier → entity-tier deterministically,
or (b) keep them parallel and call the assessor only at entity-write time
in Session D. Defer pending real data.

**Goal achieved**: `capability_assessor.py` is canonical at
`.opencode/tools/capability_assessor.py` with comprehensive test coverage.
Ready to be invoked at Session D when Decision entities are emitted.

**Deliverables (shipped)**:
- ✅ `.opencode/tools/capability_assessor.py` (promoted from reference, docstring updated to clarify two-scheme scope)
- ✅ `tests/test_capability_assessor.py` — 38 tests, all green:
  - 14 Rule-1 Enterprise keyword cases (4 patterns × stem variants)
  - 4 word-boundary guards (emigration / immigration / underwriter / architect's)
  - 9 cases covering rules 2–7
  - 3 first-rule-wins ordering invariants (rule 1 > rule 5, rule 4 > rule 5, rule 2 > rule 3)
  - 3 `should_escalate` cases (upward, no-change, downward-blocked)
  - 1 `to_dict` shape test
  - 1 CLI subprocess round-trip
- ✅ Single commit

**Deferred (was in original Session B scope)**:
- Patching orchestrator.md to call the classifier — moved out of Session B. Decision needed: unify schemes (a) vs run them parallel (b). Will surface again in Session D when Decision entity emission needs `_tier`.

**Verification (passed)**: `pytest tests/test_capability_assessor.py -v` → 38 passed in 0.13s. CLI round-trip confirmed via subprocess test.

---

### Session C — Build `lcn_read.py` + consult injection (STANDARD, ~2 hrs)

**Split into C-1 (read module + tests) and C-2 (orchestrator wiring) during execution** — debugging is easier with C-1 locked first.

#### Session C-1 — Read module + tests ✅ DONE 2026-04-25

**Goal achieved**: `lcn_read.py` exists at `.opencode/tools/lcn_read.py`, implementing all 5 query types from CONSULT-PROTOCOL.md, with comprehensive test coverage. The read side of the feedback loop is built but not yet wired into the orchestrator.

**Deliverables (shipped)**:
- ✅ `.opencode/tools/lcn_read.py` (~330 lines, stdlib-only):
  - `by_file(path, entity_types)` — confidence desc, updated_at desc; supports Convention/Pattern wildcard scope matching
  - `by_failure_class(class_name, limit)` — Errors + related Conventions whose scope intersects Error file_paths
  - `by_mission_similarity(title, scope_hash, top_k)` — v0 = 0.6×trigram-Jaccard(titles) + 0.4×Jaccard(scope_hash components); contract preserves [0,1] score range for v1 cortex swap
  - `by_convention_scope(scope)` — bidirectional fnmatch (query↔stored)
  - `search(query, top_k)` — free-text fallback, ranked
  - `consult(query_dict)` — unified dispatcher matching CONSULT-PROTOCOL wire format
  - CLI entry point matching `python lcn_read.py < query.json` pattern
- ✅ `tests/test_lcn_read.py` (30 tests, all green):
  - by_file: 5 tests (path match, wildcard scope, type filter, no-match, ordering)
  - by_failure_class: 4 tests (matching errors, related conventions, unknown class, no-paths→no-related)
  - by_mission_similarity: 5 tests (returns decisions, score range, ordering desc, top_k cap, exact-match high score)
  - by_convention_scope: 4 tests (exact, wildcard generalize down, wildcard generalize up, no-match)
  - search: 3 tests (results+scores shape, score range, nonsense low-score)
  - consult dispatcher: 6 tests (5 query types route + unknown-type raises)
  - missing-DB FileNotFoundError with helpful message
  - CLI subprocess round-trip
  - Real seed JSONL round-trip (uses MagnumOpus/seeds/*.jsonl through write_many → read queries)

**Verification**: `pytest tests/test_lcn_read.py -v` → 30 passed in 4.19s. Cumulative test surface: 91 tests across the LCN tooling, all green.

**Open question carried forward**: top-K caps and per-mission query budgets per CONSULT-PROTOCOL §"Open questions" — defer until Session D produces real consult traffic.

#### Session C-2 — split into C-2a (consult helper) + C-2b (orchestrator wiring)

**Why split**: orchestrator.md is the most architecturally-loaded file we touch. Yesterday's smoke at 20/25 stays clean if C-2a (the consult helper) lands first as a contained, testable module. C-2b then patches orchestrator.md to call it, with `JANUS_CONSULT_ENABLED` env-var kill switch for safe rollback.

#### Session C-2a — consult.py helper ✅ DONE 2026-04-25

**Goal achieved**: a CLI-callable bridge between orchestrator.md (markdown prompt) and lcn_read.py (Python module). The orchestrator can issue a single bash command per consult phase and get back ready-to-inject markdown matching the spec format.

**Deliverables (shipped)**:
- ✅ `.opencode/tools/consult.py` (~330 lines):
  - `render_pre_plan(request, predicted_files, scope_hash, db_path)` — fires by-mission-similarity + by-file (Decision) per file; emits "Prior art" + "Decisions on touched files" sections per spec
  - `render_pre_dispatch(classes, db_path)` — fires by-failure-class for ≤5 classes; emits "Known pitfalls" with `<root_cause excerpt> — prevented by: <related_convention rule>`
  - `render_post_verify(touched_files, db_path)` — fires by-file (Convention) per file; emits "Convention check" with dedupe across multi-file matches
  - `JANUS_CONSULT_ENABLED` env-var kill switch (default = enabled; "0" returns a placeholder section)
  - All sections end in spec footer: `-- injected by CONSULT-PROTOCOL v1, queries: <N>, results: <M>`
  - argparse CLI with `--phase {pre-plan,pre-dispatch,post-verify}` + per-phase args
- ✅ `tests/test_consult.py` (21 cases, all green):
  - 4 pre-plan tests (known decision, no prior art, low-similarity filtered, empty predicted-files)
  - 4 pre-dispatch tests (known class, unknown class, ≤5 cap, empty classes)
  - 3 post-verify tests (applicable convention, no conventions, dedupe across files)
  - 4 kill switch tests (all 3 phases + default-enabled)
  - missing-DB graceful degradation (footer still emits)
  - 5 CLI subprocess tests (each phase + invalid phase rejected + env kill switch)

**Two real spec/heuristic bugs found and fixed during execution**:

1. **Rejection-by-file is impossible in v0.** CONSULT-PROTOCOL.md says pre-plan should query Rejections by file path, but LCN-SCHEMA.md gives Rejections only mission scope (no file_paths field; natural key is mission_id+approach hash). The spec contradicts itself. v0 fix: drop Rejection from the by-file query, document the schema/spec gap in consult.py docstring + render_pre_plan body comment. Rejections are still surfaced via mission-similarity. Full join (Decisions on file → mission_ids → Rejections in those missions) deferred to v1 (cortex embeddings remove the need entirely).

2. **Trigram-Jaccard floor needed.** The v0 similarity heuristic returns nonzero scores (~0.03) even for orthogonal text, so "no prior art" recall-miss messaging never fired. Added `SIMILARITY_FLOOR = 0.1` in render_pre_plan. Empirical floor; revisit when cortex embeddings replace the heuristic.

**Verification**: `pytest tests/test_consult.py -v` → 21 passed in 2.30s. Cumulative LCN test surface: 112 tests across 4 modules, all green.

#### Session C-2b — Orchestrator wiring + first consult-enabled smoke (NOT STARTED)

**Goal**: orchestrator.md gains 3 consult-firing hooks at the right phases (pre-plan before architect dispatch; pre-dispatch before role dispatch; post-verify before reviewer dispatch). Each hook runs `python .opencode/tools/consult.py --phase X --...` and injects the output into the next agent's role prompt. mission-protocol.md gets a documentation patch for the consult contract.

**Verification**: smoke test attempt 12 against the new wiring with `JANUS_CONSULT_ENABLED=1`. Hypothesis: equal or better than attempt 11 (20/25), never worse. If worse, kill the env var and re-baseline.

**Goal**: the orchestrator queries LCN at SESSION START and injects relevant Conventions/Errors/Patterns into sub-agent prompts before dispatch. **This is the load-bearing session — closes the read side of the feedback loop.**

**Deliverables**:
- `.opencode/tools/lcn_read.py` — implements the 5 query types from CONSULT-PROTOCOL.md:
  - `by_file(paths) → relevant Conventions, Errors, Patterns`
  - `by_failure_class(class) → matching Error entities`
  - `by_mission_similarity(text) → top-K similar past Decisions`
  - `by_convention_scope(scope) → Conventions matching the scope glob`
  - `search(query) → free-text fallback over entity data column`
- `tests/test_lcn_read.py` — round-trip the seed data, prove each query type returns what it should
- Patch `.opencode/agent/orchestrator.md` SESSION START — add a step:
  > "Before any sub-agent dispatch, run `python .opencode/tools/lcn_read.py consult <mission-context>` and inject the returned Conventions + Errors into the sub-agent's role prompt."
- Patch `mission-protocol.md` — document the consult contract
- Two commits (read module + tests, then orchestrator wiring)

**Open questions**:
- **What ranking?** by_mission_similarity needs a similarity metric. v0: trigram or token-overlap on canonicalized mission text. v1 (when cortex lands): vector embedding from spec-LCN's readout layer. v0 is good enough — the seed corpus is small, and we can swap later.
- **How many results inject?** Too few = misses lessons; too many = prompt bloat. Start at top-3 per query type, capped at 1000 chars total injection. Tunable.
- **Cache?** Read should be fast enough that no cache is needed for v0. Revisit if `lcn_read` adds noticeable latency to mission start.

**Delegation**:
- **Sonnet (here)**: query-type semantics, ranking heuristic choices, consult-protocol integration into orchestrator.md. These need architectural judgment — getting the consult shape wrong silently degrades JANUS for every future session.
- **Gemini-coder via magnum-opus**: bulk implementation of the 5 query functions once Sonnet specs the signatures, plus the test scaffolding. Gemini Flash is good at "given this SQL schema and these 5 query types, implement them." We hand it the schema from `lcn_write.py` and CONSULT-PROTOCOL.md as context.
- **Perplexity via magnum-opus** (if MCP available): research how other autonomous agent systems do consult/recall (CrewAI, AutoGen, etc.) — purely informative, not blocking. Would feed an "Open question" doc.

**Verification**: 
1. All read tests green
2. End-to-end: seed LCN, run a mock mission, confirm orchestrator prompt now contains injected Conventions
3. Smoke test attempt 12 — first run with consult enabled. Compare seam scores against attempt 11. Hypothesis: equal or better, never worse.

**Risk**: 
- **Medium.** Wrong injection content can pollute sub-agent prompts and cause regression vs the cleaner runs we have now. Mitigation: 1) the consult is additive — old prompt content stays — so worst case it's noise not corruption; 2) feature-flag the injection via env var `JANUS_CONSULT_ENABLED=1` so we can A/B.
- **Schema rigidity.** If we get the by_mission_similarity ranking wrong, we'll want to change it later. Mitigation: keep the ranking function as a single named function that's easy to swap; don't bake it into SQL.

---

### Session D — Pipe Decisions + Errors back into LCN (STANDARD, ~1.5 hrs)

**Goal**: every mission writes Decision entities for choices made and Error entities for failures hit. LCN grows organically from real runs, not just seeds.

**Deliverables**:
- Patch `.opencode/agent/orchestrator.md` classify phase — when a tier/approach is chosen, emit a Decision entity via `lcn_write.write_entity`
- Patch `.opencode/protocols/healing-protocol.md` — when an Error is detected, emit an Error entity tagged with the matching failure_class (taxonomy enforced by `lcn_write` validation)
- Optional: a small helper at `.opencode/tools/lcn_log.py` that wraps the write calls in a try/except so a bad write never halts a mission
- Single commit
- Run smoke test attempt 13 — first run that *should* benefit from prior runs (Session C consults entities Session D wrote)

**Open questions**:
- **Decision granularity.** One Decision per mission (high-level: "use TDD" / "skip parallel-universe"), or per major dispatch? v0: one per mission. Promote to per-dispatch when we see what's actually useful in consults.
- **Error confidence levels.** failure-classes.md doesn't dictate confidence floor for Errors. Heuristic: confidence = 5 if it actually halted the mission, 4 if it was healed mid-run, 3 if it was logged-and-ignored. Encode this in the orchestrator.

**Delegation**:
- **Sonnet (here)**: Decision-emission insertion points in orchestrator.md, Error-emission hooks in healing-protocol.md. Both need judgment about what's worth recording vs what's noise.
- **Gemini-coder via magnum-opus**: the `lcn_log.py` wrapper if we go that route — pure boilerplate.
- **Magnum Opus discuss-bot**: helpful for brainstorming "what kinds of Decisions are worth recording" before we hardcode emission points. Round-table format would surface edge cases (e.g., "should sub-agent retries count as a Decision?").

**Verification**: 
1. Run smoke test attempt 13
2. Inspect `.lcn/lcn.sqlite` after — should contain seeds (16) + new entries from this run
3. Compare consult content from attempt 13 to attempt 14 (subsequent run) — second run should see attempt 13's Decisions in its consult

**Risk**: 
- **Medium.** Bad write can fail silently and we'd never know. Mitigation: `lcn_log.py` wrapper logs warnings to stderr for any write failure; manual periodic spot-checks of LCN row counts.
- **Prompt bloat over time.** As LCN grows, consult injection might get long. Mitigation: top-K caps on each query type, plus eventual relevance scoring (promote past where v0 ranking sufficed).

---

### Session E — Role-prompt retrieval hooks (MEDIUM, ~2 hrs)

**Goal**: each named sub-agent (architect, coder, reviewer, test-writer, security-auditor) gets per-role consult — they query LCN for *their* relevant entities, not just whatever the orchestrator hands them.

**Deliverables**:
- Apply ROLE-HOOKS.md stanzas to the 5 named agents, one at a time
- Per-agent test that the consult fires and returns role-appropriate entities
- Single commit per agent (5 commits total) — each one verifiable in isolation

**Open questions**:
- **Override semantics.** If orchestrator-injected and role-fetched entities conflict (e.g., orchestrator says "Convention X applies", role consult says "no, Pattern Y supersedes"), which wins? v0: orchestrator wins; mark conflicts in mission summary. v1: per-role ranking model.
- **Role consult timing.** Pre-prompt or mid-prompt? Mid-prompt is cleaner but harder to wire. v0: pre-prompt (replaces a section of the role's static prompt).

**Delegation**:
- **Sonnet (here)**: per-agent consult shaping (architect needs Patterns, coder needs Conventions + recent Errors, reviewer needs Decisions, etc. — these are mapped in ROLE-HOOKS.md but exact wiring is judgment work).
- **Gemini-coder via magnum-opus**: implementing each agent's consult call after Sonnet specs the wiring. 5 near-identical consult calls is exactly the work to delegate.
- **Magnum Opus error-monkey** (if MCP available): brainstorm failure modes of role-prompt consult before we ship — what edge cases break a sub-agent if we feed bad consult content?

**Verification**: smoke test attempt 14, inspect each sub-agent's expanded prompt for role-appropriate entity injection.

**Risk**: high. Each role hook is a place where bad consult content can degrade output. Mitigation: ship one role at a time, verify, only then ship the next. The 5-commit-per-agent structure makes rollback easy.

---

### Session F — Convention extraction from critic fixes (MEDIUM, ~1.5 hrs)

**Goal**: when the reviewer agent flags an issue and the coder fixes it, the fix promotes from a Pattern to a Convention automatically. JANUS captures *learned* rules, not just seeded ones.

**Deliverables**:
- New tool `.opencode/tools/extract_convention.py` — given a reviewer issue + coder fix diff, produces a Pattern entity
- Hook in mission-protocol.md post-review step — call extract, write Pattern, increment confidence on subsequent recurrences, promote to Convention at confidence ≥ 3
- Tests covering: pattern creation, confidence increment, promotion threshold
- Two commits (extractor + hook)

**Open questions**:
- **Idempotency.** If the same fix recurs, do we increment one Pattern or create a duplicate? Idempotency is in lcn_write's natural-key logic, but Pattern's natural key is `hash12(shape_description) | hash12(scope)` — fix-content-sensitive. Need to ensure shape_description canonicalizes well across similar fixes.
- **Promotion criteria.** confidence ≥ 3 is the seed convention's floor, but Patterns from real fixes might need different criteria (e.g., "seen in 2+ separate missions"). Promotion is a judgment call — defer the policy until we have ~10 real Patterns to look at.

**Delegation**:
- **Sonnet (here)**: extract_convention.py logic (parsing reviewer issues into shape_description format, deciding promotion threshold).
- **Gemini-coder via magnum-opus**: bulk test cases.
- **Discuss-bot**: round-table on promotion criteria once we have data.

**Verification**: simulate reviewer-flagged-fix scenarios, confirm Patterns appear, confirm promotion fires at threshold.

**Risk**: medium. The extractor is novel logic — easy to over- or under-extract. Mitigation: log every extraction decision; review periodically; tighten as we go.

---

### Session G — Post-mission retrospective (Enterprise tier only, MEDIUM, ~1.5 hrs)

**Goal**: at the end of every Enterprise-tier mission, JANUS runs a retrospective that synthesizes Decisions+Errors+Patterns into mission-level insights.

**Deliverables**:
- `.opencode/agent/retrospective.md` — new agent with explicit consult of mission-scoped entities + summary output
- Hook in mission-protocol.md session-end — invoke retrospective only if `tier == 'Enterprise'`
- Output written as a Pattern entity tagged `mission_id=<this-mission>`, scope=`mission-retrospectives/*`
- Single commit

**Open questions**:
- **Retro scope.** Just summarize, or actively propose new Conventions for promotion? v0: just summarize. v1: propose Conventions with confidence=3 (auto-promotable) once we trust the synthesis quality.
- **Cost.** Enterprise-only means rare — fine. But each retro is a sub-agent call. Budget impact: low (Enterprise missions are rare and high-stakes by definition).

**Delegation**:
- **Sonnet (here)**: retrospective.md authoring, scope decisions.
- **Magnum Opus magnum-opus skill**: orchestrate the actual retro pass — this is exactly the kind of "synthesize commodity content from many sources, escalate to Sonnet for the architectural insight" workflow magnum-opus is designed for.

**Verification**: mark a smoke test mission as Enterprise tier (force via prompt); confirm retro fires at session end; inspect retro output quality.

**Risk**: low — the retro is additive; it doesn't gate mission completion.

---

### Session H — Seam-13 protocol fix (TINY, ~45 min)

**Goal**: clean 25/25 smoke runs become possible. `git_ops.py is-clean` distinguishes modified-but-expected from untracked.

**Deliverables**:
- Patch `.opencode/tools/git_ops.py` — `is_clean()` returns granular state: `{ok, untracked: [...], modified: [...], staged: [...]}`
- Patch `mission-protocol.md` seam-17 (merge prep) — only halt on untracked, not on modified `mission.json`
- Update tests
- Single commit
- Smoke test attempt 15 — full 25/25 candidate

**Open questions**: none — clean engineering fix, no judgment calls.

**Delegation**: **Gemini-coder via magnum-opus** — pure mechanical patch + tests. Sonnet supplies the spec, Gemini writes it.

**Verification**: 25/25 PASS on smoke test attempt 15.

**Risk**: low. If something breaks, revert the commit.

---

## After Session H — Phase 6.1 fully complete

At this point JANUS:
1. Drives 25/25 smoke runs end-to-end ✅
2. Writes Decisions/Errors/Patterns/Conventions to LCN every mission ✅
3. Reads them back at SESSION START and per-role at dispatch ✅
4. Promotes recurring Patterns to Conventions automatically ✅
5. Runs retrospectives on Enterprise missions ✅
6. Tier classification is deterministic ✅

This is **a pipeline that learns**. Phase 6.1 ships.

---

## The cortex transition (Phase 6.5+, post Phase 6.1)

This is where the user's "LCN as the brain" framing lands. Speculative until §4.x stabilizes in Notion, but the bridge is plannable.

**Prerequisites for v1 transition**:
- Notion swarm completes §4.10 implementation (✅ shipped — JVP micro-library available)
- §4.11 / §4.12 / §4.15 / §4.15.1 stabilize (currently in review / in flight)
- Tester P1 closure on K=50 baseline (~46h pending as of 2026-04-25)
- Code Synthesizer ports the JVP micro-library to a Python-callable surface

**v0 → v1 transition shape**:
1. New module `.opencode/tools/lcn_cortex.py` — implements the same 5 query types as `lcn_read.py`, but backed by the spec-LCN v1 cortex instead of SQLite. Same function signatures.
2. Feature flag `JANUS_LCN_BACKEND=cortex` swaps which module the orchestrator imports.
3. Migration path: dual-write (both backends) for one phase, then read from cortex once it's proven.
4. Entities never change — LCN-SCHEMA.md's forward-compat mapping holds.

**What expands further**:
- **Spike-encoded input.** Mission context becomes spike trains (per spec-LCN §4.x). The encoding layer is new code, not ported from v0.
- **SSF ODE / RCD recurrence.** The actual neural net. Comes from spec-LCN v1 implementation. JANUS doesn't author this — it consumes it.
- **ODE-plastic readout.** Replaces SQLite's `data` column blob. Similar interface (entity in / entity out), different substrate.
- **Cross-project layer.** Phase 6.2 multi-project brain — one cortex serves multiple repos. Possible only after v1 lands and per-project state can be embedded into the same substrate.

**Magnum Opus delegation for cortex transition**:
- **Perplexity (when available)**: track Notion swarm progress autonomously — would summarize §4.x updates into JANUS-relevant signals. Useful but not blocking.
- **Gemini-coder**: port the JVP micro-library reference to Python once Code Synthesizer ships it.
- **Discuss-bot**: round-table on the v0 → v1 swap timing (early = risky, late = wasted v0 effort) once we have a concrete v1 release candidate.
- **Sonnet (here)**: own the architecture decisions — feature-flag design, dual-write strategy, rollback plan.

---

## Delegation strategy summary (Magnum Opus map)

| Session | Sonnet (here) keeps | Outsource via Magnum Opus |
|---|---|---|
| A | Decision: where seed script lives | (none — trivial) |
| B | orchestrator.md patch design | Gemini-coder: test cases |
| C | Query semantics, ranking, consult shape | Gemini-coder: 5 query implementations + tests; Perplexity: agent recall lit review |
| D | Decision/Error emission policy | Gemini-coder: lcn_log.py wrapper; Discuss-bot: granularity round-table |
| E | Per-role consult shaping | Gemini-coder: 5 near-identical consult calls; Error-monkey: failure-mode brainstorm |
| F | Convention extraction logic, promotion threshold | Gemini-coder: bulk tests; Discuss-bot: promotion-criteria round-table |
| G | retrospective.md design | Magnum-opus: orchestrate the retro pass itself |
| H | Spec the patch | Gemini-coder: patch + tests |
| Cortex | All architectural decisions | Perplexity: spec-LCN tracking; Gemini-coder: porting; Discuss-bot: transition timing |

**Default rule**: Sonnet keeps anything where wrong = silently degrades JANUS for every future run. Magnum Opus takes anything where the spec is concrete and the work is mechanical.

---

## Cross-cutting things to expand more

These don't fit any single session but need attention as we go:

1. **Mission-similarity ranking** (Session C). The v0 trigram heuristic is "good enough until it isn't." When the seed corpus grows past ~50 entities, we'll need real ranking. Not a v1 dependency — a separate concern.
2. **Confidence scoring** for auto-written entities. v0 hardcodes (Decision = 4, Error per healing state, Pattern = starts at 1 and increments). The right model is fuzzier. Revisit after Session F has produced ~10 Patterns to look at.
3. **Pruning policy.** As LCN grows, low-confidence Patterns and stale Errors accumulate. Need a cleanup pass — but only after we've seen what "stale" actually looks like in practice. Defer until after Session H.
4. **Consult prompt bloat.** Session C caps total injection at 1000 chars; that may not survive ROLE-HOOKS landing in Session E. Plan: token-counting helper + per-role budget cap.
5. **The v0 → v1 forward-compat audit.** Periodically (every ~5 sessions) re-read LCN-SCHEMA.md's forward-compat mapping section and verify nothing we've added breaks it. Cheap, prevents painful refactor later.

---

## Open questions we don't need to answer yet

- Does spec-LCN v1's cortex produce embeddings we can use for similarity ranking (Session C v1)? Probably yes — the readout layer should be embeddings-shaped — but confirm when v1 ships.
- Should Errors be eviction-eligible (i.e., resolved errors get archived after N missions)? Smells right but no urgency.
- Is the 5-query-type set in CONSULT-PROTOCOL.md complete? Could there be a 6th (e.g., by-time-window for "recent decisions")? Track empirically — add when we feel its absence.
- Multi-LCN federation (Phase 6.2): one cortex per repo with a shared core, or one cortex shared across repos? Decide when v1 ships and we know the cortex's actual sharing semantics.

---

## Update log

- **2026-04-25**: Document drafted post Sessions 0 + 1+2 (foundation recovery + lcn_write wiring). Phase 6.1 gate cleared 2026-04-24.
