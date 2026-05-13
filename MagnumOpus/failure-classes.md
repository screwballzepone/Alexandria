# failure-classes.md — bounded taxonomy for Error entities

**Authority**: TWO-MINDS.md §3.6. Every `Error` entity written to LCN MUST carry a `failure_class` field drawn from this list. New classes are added by a PR amending this file — agents cannot mint classes inline.

**Version**: v1 (2026-04-19). Version number bumps when any class is added, removed, or substantively reframed.

---

## The classes

### `model-routing`

Anything where the requested model is not the model actually served. Covers alias misresolution, silent fallback to `small_model`, SDK path bugs, proxy misrouting, and absent dated-snapshot IDs in a model registry.

**Diagnostic signature**: response metadata doesn't match the requested provider (e.g., `google.thoughtSignature` on a request addressed to Anthropic).

**Write guidance**: `root_cause` must name the specific routing layer that failed — `registry`, `SDK`, `proxy`, or `provider`. "The model was wrong" is not a diagnosis.

---

### `agent-frontmatter-ignored`

A frontmatter field in an agent file is silently discarded by the runtime. Known case: the `model:` field on the primary agent is ignored; only dispatched sub-agents respect it.

**Diagnostic signature**: behavior matches the default, not the frontmatter override, with no error emitted.

**Write guidance**: the Convention that pairs with this Error should be a "set primary model via opencode.json top-level `model` key or `--model` CLI flag" rule.

---

### `edit-shape-error`

An Edit tool call fails because `oldString` or `newString` does not match the actual file content. Examples: including Read's `N: ` line-number prefix in `oldString`; whitespace mismatch; operating on a closed-state file.

**Diagnostic signature**: Edit rejection with "string not found" on a substring the model believed was present.

**Write guidance**: the most useful thing to record is the *shape* of the mismatch, not the specific string. "oldString had line-number prefix" is reusable; the prefix itself is not.

---

### `invented-tool`

Agent calls a tool name that does not exist in its manifest. Often a near-miss of a real tool (e.g., `isoformat` instead of a real date utility, `readFile` when the real name is `Read`).

**Diagnostic signature**: runtime error `Unknown tool: <name>`.

**Write guidance**: record the invented name AND the manifest the agent was operating under. Missing-manifest is a meta-cause; wrong-name is a local cause.

---

### `ci-flake-vs-real`

A CI failure is read as real (and fixed unnecessarily) when it was flaky, or read as flaky (and ignored) when it was real. Applies in both directions.

**Diagnostic signature**: second run of the same commit gives a different CI result, or a previously-"flaky" failure reproduces on a clean clone.

**Write guidance**: the Convention that pairs with this Error must include a reproduction test — "rerun N times and check stability" is the shape.

---

### `convention-violation`

A settled Convention entity is contradicted by a recent diff. The violation must be deliberate and self-aware; accidental convention violations are `edit-shape-error`. The signal of deliberateness is that the agent's reasoning mentioned the convention.

**Diagnostic signature**: a Convention entity query would have returned a rule that the current change breaks.

**Write guidance**: if the agent genuinely did not see the Convention, this is actually a `consult-skipped` Error — and the mission's audit log will show the skipped consult. Only classify as `convention-violation` when the consult fired and the agent chose to proceed anyway.

---

### `consult-skipped`

A mandatory LCN consult (TWO-MINDS §3.4) was bypassed by the orchestrator or a dispatched role. Tripping this class halts the mission under the circuit breaker.

**Diagnostic signature**: mission audit log shows a phase transition with no corresponding LCN read entry.

**Write guidance**: `root_cause` should name *which* consult was skipped — pre-plan, pre-dispatch, or post-verify — and *why* — race condition, tier misclassification, explicit override.

---

### `budget-overrun`

Mission exceeded its token, time, or step budget before completion. Distinct from crashes (`model-routing` or others) and from task-completes-but-poor-quality (not an Error at all — that's a low-`confidence` Decision).

**Diagnostic signature**: budget counters exhausted with `mission_state != complete`.

**Write guidance**: record *which* budget blew, not just that one did. Token budget blowouts tend to be planner issues; time budget blowouts tend to be proxy/model-latency issues; step budget blowouts tend to be loop issues.

---

## Adding a new class

Open a PR that:

1. Adds the class here using the same shape as existing entries — one paragraph of definition, a diagnostic signature line, and a write-guidance line if non-obvious.
2. Bumps the version number at the top of this file.
3. Adds or updates one or more Convention entities describing how future missions should avoid the class. Classes without paired conventions lead to taxonomy bloat without behavior change — this is enforced by review.
4. If the class arose from a specific mission, adds that mission's Error entity as a seed example in the LCN seed data (if seeding is in effect).

**Rationale**: the point of a bounded taxonomy is that the same failure gets recognized as the same failure. Unbounded taxonomies devolve into near-duplicates, which defeats the whole point of `by-failure-class` recall.
