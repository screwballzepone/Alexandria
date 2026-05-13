# TWO-MINDS.md — the architectural lodestar

**Project**: JANUS (the agent platform — formerly known internally as "OpenCode," a name we kept by accident long after we stopped being just a wrapper around the OpenCode CLI). The filesystem layout and `opencode.json` config retain their names because the CLI dependency does; everything else points at JANUS going forward.

**Purpose**: This document is the north star JANUS steers by. Every batch, every agent prompt, every schema decision should answer to it. It is not a roadmap. It is the shape of the system we are trying to become.

**Status**: Drafted 2026-04-19 in response to the pivot toward the two-minds architecture. Lives alongside the GENESIS v2.0 and LCN notions but speaks for what *our* repo will be.

**Name rationale**: Janus is the two-faced Roman god of doorways. One face looks back (LCN — what do we know?), one face looks forward (GENESIS — what do we do?). Every mission passes through the doorway.

---

## 1. The two minds

OpenCode is converging on a dual-process architecture that maps — loosely but deliberately — to Kahneman's System-1 / System-2 split:

- **GENESIS — the deliberate mind (System-2)**. Explicit, slow, tool-using, role-aware, auditable. This is the orchestrator, the architect/builder/critic/tester/devops role stack, the quality scorer, the self-healing loop, the decision journal, the CI monitor, the budget ticker. Everything that *plans* or *judges* a change lives here.
- **LCN — the implicit mind (System-1)**. Persistent, always-on, retrieval-first, pattern-shaped. In the near term this means the memory store, the convention map, the error taxonomy, the "what did we already try and why did it fail" corpus. In the long term (spec-LCN v1) it becomes the neuromorphic compute substrate the LCN team is building — a place where learned structure lives outside any single conversation window.

Both minds are necessary. GENESIS alone is brilliant but amnesic: every mission starts from zero context, every mistake is novel, every convention has to be re-derived from the code. LCN alone is a library without a librarian: it remembers but cannot decide. The point of *two* minds is that decisions are cheap because recall is cheap, and recall is trusted because decisions annotate it.

This is also the operational definition of "some level of AGI" we care about — not a general-purpose superintelligence but something narrower and realer: an autonomous software engineering agent that **gets better at this codebase over time**, without a human pasting context into a prompt to reset it. If the same bug gets the same wrong fix three times across three missions, we don't have the system we're building. If the third mission asks LCN "what happened last time we touched the CI retry logic" and gets an honest, structured answer, we do.

---

## 2. Division of labor

The rule that keeps the two minds from blurring into each other:

- **GENESIS decides. LCN remembers.**
- **GENESIS produces. LCN indexes.**
- **GENESIS owns the write semantics. LCN owns the query semantics.**

Concretely:

GENESIS writes to LCN at well-defined seams inside a mission — never opportunistically, never at the discretion of an agent. Each seam has a schema (see §4). LCN reads are initiated by GENESIS agents at well-defined consult points (see §5). Neither side freelances.

This separation is not architectural purism. It is the only way to keep either side debuggable. If an agent can write "whatever felt important" at any moment, LCN fills with noise within a week. If an agent can skip the consult step, GENESIS keeps making the same mistake because it never looks at the answer.

---

## 3. The GENESIS ↔ LCN contract

The contract has six moving parts. Every seam in a mission touches at least one.

### 3.1 Mission-phase pass-through

A mission in OpenCode proceeds through phases: classify → plan → dispatch → execute → verify → report. Each phase is a potential seam:

| Phase | LCN read | LCN write |
|---|---|---|
| classify | recall past missions with similar title/scope/error signature | — |
| plan | recall conventions for touched files, rejected approaches, open decisions | — |
| dispatch | recall per-role failure patterns (does this role tend to over-edit?) | — |
| execute | recall per-file edit hazards, last-N commits touching the file | — |
| verify | recall past test flakes on touched paths | Decision (why this approach was chosen), Rejection (what was considered and dropped) |
| report | — | Error (what failed and why), Pattern (what worked and why), Convention (what's now settled) |

Reads are mandatory at their phases; skipping them is a classifier failure. Writes are conditional — only when the phase produced content that meets the schema.

### 3.2 Entity schema (writes)

LCN stores five entity types. These are the only things GENESIS may write:

- **Decision** — a chosen approach, with alternatives considered. `{mission_id, file_paths, chosen_approach, alternatives, rationale, outcome_when_known}`
- **Rejection** — an approach evaluated and dropped. `{mission_id, approach, reason, context_that_might_change_this}` — critical field is the last one: rejections get re-queried under changed context.
- **Error** — a failure and its diagnosis. `{mission_id, failure_class, file_paths, symptom, root_cause, fix_applied, reproduction}` — failure_class is drawn from a bounded taxonomy (not free-form).
- **Pattern** — a recurring construct that worked. `{file_paths, shape_description, when_to_use, when_not_to_use}`
- **Convention** — a settled style/rule for this codebase. `{scope, rule, why, example}`

Every write is idempotent on `{entity_type, mission_id, file_paths}`. Re-writing the same key updates; it does not accumulate.

### 3.3 Query protocol (reads)

Reads are keyed, not free-text:

- **by-file** — "what does LCN have on `.opencode/agent/orchestrator.md`"
- **by-failure-class** — "what does LCN have on class `model-routing`"
- **by-mission-similarity** — "what missions resembled `{title, scope_hash}`"
- **by-convention-scope** — "what conventions apply to scope `agent-frontmatter`"

Free-text retrieval is allowed only as a fallback when no keyed query fits. The keyed queries are what the orchestrator injects automatically at consult points; free-text is what a human (or a stuck agent) asks LCN directly.

### 3.4 Consult points (the non-negotiable ones)

Three consults are mandatory on every non-TINY mission:

1. **Pre-plan consult**: `by-mission-similarity` on the incoming request + `by-file` on every file the classifier predicted will change. Results are injected into the planner's context as `## Prior art` with entity IDs.
2. **Pre-dispatch consult**: `by-failure-class` on the five most common classes the plan implies. Results are injected into the dispatched role prompt as `## Known pitfalls`.
3. **Post-verify consult**: `by-file` on every file actually touched, filtered to Convention entries. Results become the critic's `## Convention check` rubric.

Skipping any of these at a phase where they apply is a circuit-breaker trip — the mission halts and writes an Error entity of class `consult-skipped`.

### 3.5 Role-prompt retrieval hooks

Each role prompt (architect.md, builder.md, critic.md, tester.md, devops.md) ends with a stanza:

```
## Before acting
Consult LCN with the following queries:
- <role-specific keyed query>
- <role-specific keyed query>
Treat recall misses as meaningful (nothing known → proceed with caution, annotate novelty).
```

This is the only way role prompts ever grow. They don't add clever instructions over time; they add query hooks.

### 3.6 Failure-class taxonomy (bounded)

Errors get written with a `failure_class` drawn from a fixed vocabulary, versioned in `MagnumOpus/failure-classes.md`. Initial classes, from our own scar tissue:

- `model-routing` (alias resolution, silent fallback, SDK path)
- `agent-frontmatter-ignored` (model field on primary session, etc.)
- `edit-shape-error` (line-number prefix, wrong oldString context)
- `invented-tool` (agent called a non-existent tool)
- `ci-flake-vs-real` (intermittent test failure misread)
- `convention-violation` (settled rule broken by an agent)
- `consult-skipped` (mandatory consult bypassed)
- `budget-overrun` (mission exceeded its token/time/step budget)

New classes are added by a single-file PR that amends failure-classes.md. Agents cannot mint a new class inline.

---

## 4. Progressive tier disclosure

Not every mission wants the full machinery. A TINY mission editing one line of frontmatter does not need pre-plan consult, five role dispatches, and three schema writes. The two-minds architecture is *tiered*:

- **MVP tier** — TINY mission (1-2 files, no cross-file reasoning). Consults: none mandatory. Writes: Error-on-failure only. Rationale: the mission's surface is so small that recall costs more than it saves.
- **Production tier** — STANDARD mission (3-10 files or cross-file reasoning). All three mandatory consults. Writes: Decision on plan, Error on failure, Convention on novel settled rule.
- **Enterprise tier** — COMPLEX mission (>10 files, user-facing behavior change, or architecture-touching). All of Production plus: Rejection on each seriously-considered alternative, Pattern on any new construct used >2 times in the diff, post-mission retrospective write.

The classifier chooses the tier at the `classify` phase. Tier is recorded as the first field of the decision journal entry for the mission.

---

## 5. The AGI definition

When this document says "some level of AGI for autonomous software engineering," it means five measurable properties holding simultaneously:

1. **Non-regressive learning** — the same failure class does not occur more than twice on the same file path across the rolling 30-mission window. Every recurrence beyond #2 is an investigated Error writing a new Convention.
2. **Cross-mission memory** — pre-plan consult hit rate >60% on STANDARD+ missions (at least three-fifths of the time, LCN surfaces something relevant the orchestrator did not have in its prompt).
3. **Unprompted recall** — agents invoke non-mandatory consults via the role-prompt hooks at least once per STANDARD+ mission on average.
4. **Self-correction** — self-healing loop triggers at least once per ten missions and resolves >50% of them without human intervention.
5. **Stable conventions** — convention_violation error rate is monotonically non-increasing over the rolling 30-mission window.

These are the metrics the meta-learning engine watches. They are not aspirational; they are the pass/fail criteria for calling the architecture load-bearing.

---

## 6. Consumption contract with spec-LCN v1

The LCN team is building a neuromorphic compute substrate (SSF ODE, RCD gated recurrence, ODE-plastic readout, antithetic JVP gradients). Today, "LCN" in this repo means a simpler memory store with the schema and query protocol above. That's fine. The contract is forward-compatible:

- **Today** — LCN-the-schema. Concrete storage is a SQLite file (or the LCN v0 port-3737 server if preferred). Entities, keyed queries, mandatory consult points all work.
- **Transition** — the same schema feeds into spec-LCN v1 as the *initial state* for its implicit representations. Decision/Rejection/Error/Pattern/Convention each map to a known readout target. The JVP gradient path will learn to weight them.
- **Steady state** — LCN v1 returns not rows but *weighted relevance*. The query protocol stays the same at the interface; the backing representation changes. GENESIS never knows the difference.

The point of writing the contract this way is that we get value from the discipline *today*, even before the neuromorphic layer exists, and we don't have to re-architect GENESIS when it lands. If spec-LCN v1 never lands, we still have a debuggable memory system. If it lands beautifully, we have a learning one.

---

## 7. What happens first

Listed in the order the two-minds arc actually needs them:

1. **Model routing fix** (batch 22, pending). Non-negotiable; nothing below works if the orchestrator cannot call its intended model. This is plumbing, not architecture, but it is in the critical path.
2. **Smoke test clears ≥18/25** (batch 17 attempt 5). This is the signal that the deliberate mind is actually alive end-to-end. No memory work lands before this.
3. **Failure-class taxonomy file** (`MagnumOpus/failure-classes.md`). A one-file PR codifying §3.6. Cheap, unblocks every Error write downstream.
4. **Entity schema module** — write-side only at first. A tiny Python module (`.opencode/tools/lcn_write.py`) that validates and persists the five entity types to whichever backing store we pick. Idempotent on the natural keys.
5. **Capability assessor** — a classifier that emits the mission tier (MVP/Production/Enterprise) from the incoming request. Runs at the `classify` phase. Chooses the consult and write regime.
6. **Mandatory consult injection** in the orchestrator — the three consults from §3.4, wired into the planner and dispatcher prompts. This is the first time LCN reads actually flow into GENESIS behavior.
7. **Role-prompt retrieval hooks** — the stanza from §3.5 appended to each of the five role prompts.
8. **Decision journal → Decision entity** — redirect the existing decision journal writes through the entity schema module. Nothing new; just a pipe-to.
9. **Convention extraction from critic runs** — when the critic flags a style issue the builder then fixes, write a Convention entity from the diff.
10. **Post-mission retrospective** (Enterprise tier only). A final pass that produces Pattern entities from any construct repeated in the diff.

Everything after that is a spec-LCN v1 onramp and measured against the five properties in §5.

---

## 8. Non-goals

Things this document deliberately does not commit to:

- **A chat-style memory** where agents "remember conversations." Memory is structured entities keyed on files and classes; it is not transcripts.
- **A human-facing knowledge base.** LCN is for agents. Humans read the decision journal, the CI logs, and the repo.
- **Generality across projects.** Cross-project memory is a Phase 6.1 goal but out of scope for this document; the two-minds contract is defined per-repo first.
- **Replacing GENESIS.** LCN does not decide. Ever. If we find ourselves asking LCN "what should we do," we've confused the minds.
- **Waiting on spec-LCN v1.** We build against the schema now, with whatever backing store is cheapest, and swap when v1 lands.

---

## 9. Open questions

These need answers before the corresponding items in §7 can ship. None of them block items 1 or 2.

- **Storage backend for LCN entities** — SQLite in the repo, LCN v0 server (port 3737), or something new? SQLite wins on portability; v0 wins on continuity with the LCN team.
- **Failure-class governance** — who can add classes, and does every new class require a Convention write? (Current working answer: yes, every new class gets one or more Conventions within the same PR.)
- **Tier boundaries** — the MVP/Production/Enterprise split is currently hand-wavy on the edges. Need a concrete classifier with examples.
- **Retrospective cost** — Enterprise post-mission retrospective will be expensive in tokens. How do we keep it honest without making it skippable?

---

*This document changes when the architecture changes, not when missions change. If a batch prompt requires an amendment here, the amendment is part of the batch.*
