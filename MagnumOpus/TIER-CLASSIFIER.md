# TIER-CLASSIFIER.md — capability assessor spec

**Authority**: TWO-MINDS.md §4. The classifier runs at the `classify` phase and emits a tier that determines consult and write behavior for the rest of the mission.

**Version**: v1 (2026-04-19).

---

## Tiers

### MVP

**Bounds**:
- ≤2 files touched
- No cross-file reasoning required (the change in one file does not depend on understanding another)
- No user-facing behavior change
- No migration, no schema change, no API surface change

**Examples**: bumping a version string, fixing a typo, toggling a config flag, renaming a single variable within its scope.

**Consult regime**: none mandatory. Agents may use free-text LCN queries ad hoc.

**Write regime**: Error-on-failure only. No Decision, no Convention, no Pattern writes — the surface is too small to pay back the write cost.

---

### Production

**Bounds**:
- 3–10 files touched, OR cross-file reasoning required, OR public API touched
- No architecture change
- No migration involving live data

**Examples**: adding a new agent role, wiring a new tool into the orchestrator, implementing a well-scoped feature, routine refactor within a subsystem.

**Consult regime**: all three mandatory consults (pre-plan, pre-dispatch, post-verify).

**Write regime**: Decision on plan (outcome `pending`, later updated), Error on failure, Convention on novel settled rule (when critic flags a style issue the builder then fixes).

---

### Enterprise

**Bounds**:
- >10 files touched, OR architecture-touching, OR user-facing behavior change, OR live-data migration, OR cross-project impact

**Examples**: migrating a storage backend, changing the orchestrator's dispatch protocol, introducing a new primary agent, deprecating a subsystem, refactoring how LCN is consumed.

**Consult regime**: all three mandatory, plus a `by-convention-scope` consult on the architectural scope(s) touched — because Enterprise changes can silently wipe out conventions that govern areas the diff doesn't obviously touch.

**Write regime**: Decision with non-empty `alternatives` (required), Rejection for each seriously-considered alternative, Error on failure, Pattern on any new construct used >2 times in the diff, Convention on any promoted pattern, and a post-mission retrospective that re-reads the full set of entities produced and writes a meta-Decision about what the arc actually did.

---

## Classifier inputs

The classifier receives:

| Input | Source | Notes |
|---|---|---|
| `request_text` | User or issue body | Raw; not sanitized. |
| `predicted_files` | Cheap pre-plan | Distinct from the full planner phase — just enough to sniff scope. Wrong predictions are fine; they trigger tier escalation mid-mission (see below). |
| `diff_scope_estimate` | Cheap pre-plan | Integer, approximate line count expected. |

The "cheap pre-plan" is a few-hundred-token call that asks "which files, roughly how big?" It is not a real plan and does not replace the planner phase.

---

## Classifier rules

Deterministic first, heuristic second. Applied in order. First rule that fires wins.

1. If `request_text` contains any of `{migration, rewrite, architecture, deprecate, breaking change, new primary agent}` → **Enterprise**.
2. If `predicted_files` ≥ 11 → **Enterprise**.
3. If `diff_scope_estimate` ≥ 300 → **Enterprise**.
4. If request touches any file under `.opencode/protocols/` → **Enterprise**. (Protocols are the highest-leverage surface in the repo; changes ripple into every mission.)
5. If `predicted_files` ≥ 3 → **Production**.
6. If request touches any file under `.opencode/agent/` or matches `orchestrator*` → **Production** (minimum), even for 1–2 files. Orchestrator-adjacent changes have amplification risk — a single wrong word propagates to every dispatched role.
7. Otherwise → **MVP**.

Rule ordering matters. Rule 1 beats rule 6 because an architecture change to the agent directory is still Enterprise, not just Production.

---

## Classifier output

```json
{
  "tier": "MVP" | "Production" | "Enterprise",
  "reason": "rule-<N> (<debug-context>)",
  "predicted_files": ["..."],
  "diff_scope_estimate": <int>
}
```

The `reason` field names the rule that fired plus a short debug context — e.g., `"rule-5 (predicted_files=5)"` or `"rule-1 (matched: migration)"`.

This is for auditability. When a mission outcome seems mis-tiered, the rule that fired is the first thing to inspect.

---

## Tier escalation mid-mission

Only **upward** escalation is legal. If a mission classified MVP reaches the execute phase having actually touched 6 files, the mission auto-escalates to Production and **backfills** the pre-plan and pre-dispatch consults retroactively. The backfilled consults may produce warnings in the audit log ("this consult should have fired earlier"); that's expected and informative, not a circuit-breaker trip.

**De-escalation is never legal.** A mission classified Enterprise that ends up being smaller than expected still pays the full consult and write cost. Better to over-consult than to miss prior art.

**Escalation triggers**:
- File count exceeds the next tier's lower bound
- Any file under `.opencode/protocols/` is actually touched (even if not predicted)
- Any Enterprise-keyword phrase appears in an agent's plan reasoning, even if absent from the request

---

## Worked examples

From our own batch history:

| Batch | Request | Files | Predicted tier | Rule fired |
|---|---|---|---|---|
| 20 | Swap orchestrator model (frontmatter line 3) | 1 | Production | Rule 6 (orchestrator.md under `.opencode/agent/`) |
| 21 | Add baseURL + revert orchestrator line | 2 | Production | Rule 6 |
| 19 | Ruff/pytest seam fixes | 5 (under `.opencode/tools/`) | Production | Rule 5 (predicted_files ≥ 3) |
| (hypothetical) Bump a version string in one file | | 1 | MVP | Rule 7 |
| (hypothetical) Replace LCN v0 backend with SQLite | | ~8 | Enterprise | Rule 1 ("migration") |

Note that Batch 20 (one line changed) still classifies as Production. This is the correct behavior — the single line is the model routing for the orchestrator itself, and getting it wrong burns an entire smoke test cycle. Rule 6 exists to prevent exactly that kind of amplification surprise.

---

## Evaluating the classifier

The classifier is evaluable against past missions. Add `eval-tier-classifier` to the eval suite once the write module lands. Seed test cases from this document's worked examples.

**Target accuracy**: ≥ 90% on the eval set.

Misclassifications are themselves material: they write Convention entities about how to clarify `request_text` phrasing, or propose new rules (via PR) when a pattern of mis-tiering emerges.

---

## Open questions

- **`top_5_implied_classes`**: the pre-dispatch consult (CONSULT-PROTOCOL §Pre-dispatch) depends on a heuristic that predicts which failure classes apply. That heuristic lives close to this classifier and may merit its own doc once it matures.
- **"Cheap pre-plan" cost**: how cheap is cheap? Working answer: ≤500 tokens, no tool calls, no real planning. If a pre-plan costs more than that, collapse it into the real planner and accept worse tier accuracy.
- **Tier for healing missions**: when the self-healing loop fires a sub-mission to fix a failure, does that sub-mission inherit the parent's tier or reclassify? Leaning *inherit*, because healing is part of the parent's surface, not an independent change.
