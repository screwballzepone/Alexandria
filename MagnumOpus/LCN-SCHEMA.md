# LCN-SCHEMA.md — entity schema for LCN writes

**Authority**: TWO-MINDS.md §3.2. The five-entity schema is closed: no other entity types may be written. This document specifies field types, natural keys, idempotency rules, validation, and examples.

**Version**: v1 (2026-04-19).

---

## Common fields

Every entity carries the following regardless of type:

| Field | Type | Assigned by | Notes |
|---|---|---|---|
| `id` | ULID | write module | Monotonic, sortable by creation time. |
| `entity_type` | enum | author | One of the five types below. |
| `created_at` | ISO-8601 UTC | write module | Never changes after first write. |
| `updated_at` | ISO-8601 UTC | write module | Refreshed on idempotent re-write. |
| `mission_id` | string \| null | author | The mission that produced the write. `null` only for manual seeds. |
| `confidence` | integer 1-5 | author | 1 = anecdotal (one data point); 5 = reproduced across many missions. |

---

## Natural keys

Writes are idempotent on these tuples. Re-writing the same key updates `updated_at` and any changed fields; it does not create a new row.

| Entity | Natural key |
|---|---|
| Decision | `(mission_id, chosen_approach_hash, file_paths_hash)` |
| Rejection | `(mission_id, approach_hash)` |
| Error | `(mission_id, failure_class, file_paths_hash)` |
| Pattern | `(shape_description_hash, scope_hash)` |
| Convention | `(scope, rule_hash)` |

`*_hash` = SHA-1 of the canonicalized text, first 12 chars. Canonicalization: lowercase, collapse whitespace, strip leading/trailing punctuation. `file_paths_hash` is over the sorted, deduplicated list.

Rationale for no `mission_id` in Pattern/Convention keys: these cross mission boundaries by design. Two missions independently deriving the same Convention must produce the same natural key, or the value-of-Convention is lost.

---

## Decision

A chosen approach with alternatives explicitly considered.

| Field | Type | Required | Notes |
|---|---|---|---|
| `file_paths` | list[string] | yes | Repo-relative. |
| `chosen_approach` | string | yes | 1–3 sentences. |
| `alternatives` | list[{approach, reason_dropped}] | tier-dependent | Required for Enterprise tier; may omit for MVP/Production. |
| `rationale` | string | yes | Why chosen_approach beat alternatives. |
| `outcome` | enum | yes | `pending \| succeeded \| failed \| rolled-back`. Starts `pending`. |

**Outcome progression**: written `pending` at plan-phase. Updated to `succeeded` or `failed` by post-verify. Becomes `rolled-back` if a later mission reverts the change; that later mission is responsible for the update.

**Validation**: for Enterprise tier, `alternatives` MUST have at least one entry. Empty alternatives on an Enterprise Decision is a schema error.

### Example

```json
{
  "entity_type": "Decision",
  "mission_id": "batch-21",
  "file_paths": [".opencode/opencode.json"],
  "chosen_approach": "Set provider.anthropic.options.baseURL to https://api.anthropic.com/v1 so the SDK's /messages suffix resolves correctly.",
  "alternatives": [
    {"approach": "Proxy through OpenRouter", "reason_dropped": "Finding L — alias misresolved to Gemini under the proxy."},
    {"approach": "Patch the SDK directly", "reason_dropped": "Out of repo scope; upstream fix belongs elsewhere."}
  ],
  "rationale": "baseURL is the supported config extension point; OpenRouter path was unreliable in observed runs.",
  "outcome": "succeeded",
  "confidence": 4
}
```

---

## Rejection

An approach seriously considered and dropped. Rejections are distinct from the `alternatives` array inside a Decision because they get **re-queried under changed context** — this is their whole reason to exist.

| Field | Type | Required | Notes |
|---|---|---|---|
| `approach` | string | yes | 1–3 sentences. |
| `reason` | string | yes | Why dropped. |
| `context_that_might_change_this` | string | yes | The specific condition under which this rejection should be re-evaluated. |

**Validation**: `context_that_might_change_this` MUST be non-empty and specific enough to match against. "If things change" is rejected. "If we move off OpenRouter" or "if Python bumps to 3.12" is accepted. A human reviewer can override on PR.

### Example

```json
{
  "entity_type": "Rejection",
  "mission_id": "batch-21",
  "approach": "Route all agents through OpenRouter for uniformity.",
  "reason": "Finding L showed OpenRouter silently falls back to Gemini on unresolved Sonnet aliases.",
  "context_that_might_change_this": "If OpenRouter adds a dated-snapshot aliasing guarantee, or if we only need a model they don't proxy-fallback on.",
  "confidence": 3
}
```

---

## Error

A failure and its diagnosis.

| Field | Type | Required | Notes |
|---|---|---|---|
| `failure_class` | enum | yes | From `failure-classes.md`. |
| `file_paths` | list[string] | yes | Files implicated. May be empty for non-file failures (budget, routing). |
| `symptom` | string | yes | What went wrong observably. |
| `root_cause` | string | yes | The underlying cause. May differ from symptom. |
| `fix_applied` | string | yes | What was done to resolve. |
| `reproduction` | string | no | Steps or conditions. Empty if not reproducible. |

---

## Pattern

A recurring construct that worked.

| Field | Type | Required | Notes |
|---|---|---|---|
| `shape_description` | string | yes | 1–2 sentences naming the shape abstractly. |
| `when_to_use` | string | yes | |
| `when_not_to_use` | string | yes | Missing this field is the single most common way Patterns degrade into noise. |
| `scope` | string | yes | Where this applies. Wildcards allowed (e.g., `.opencode/agent/*`, `python-cli-tools`, `*`). |

**Validation**: Patterns may only be written when the same shape appears in ≥2 Decision entities, OR is extracted by the post-verify phase from a diff with ≥2 structurally similar blocks. The write module enforces this — attempts to write a single-instance Pattern are rejected (write a Decision with `confidence: 2` instead).

---

## Convention

A settled style/rule for the codebase.

| Field | Type | Required | Notes |
|---|---|---|---|
| `scope` | string | yes | Same form as Pattern.scope. |
| `rule` | string | yes | Imperative mood. "Do X" or "Never Y". |
| `why` | string | yes | |
| `example` | string | yes | A concrete example of the rule applied. |

**Validation**: Convention writes require `confidence >= 3`. Brand-new conventions (confidence 1–2) should be Patterns first, promoted to Conventions once a second concurring mission raises the confidence.

**Promotion path**: Pattern with ≥3 occurrences and ≥2 missions → Convention. The write module can auto-propose the promotion; a human or a high-tier mission confirms.

---

## Forward compatibility with spec-LCN v1

When spec-LCN v1 (the neuromorphic substrate in the LCN Architecture Specification) lands, each entity type maps to a readout target:

| Entity | spec-LCN v1 readout |
|---|---|
| Decision | action-approach readout |
| Rejection | approach-inhibition readout |
| Error | failure-signature readout |
| Pattern | construct-similarity readout |
| Convention | rule-enforcement readout |

The write interface defined in this document stays identical. What changes: the backing store replaces tabular rows with learned representations; `by-file` and `by-failure-class` become vector queries weighted by the JVP-trained readouts. GENESIS agents issue the same keyed queries and don't need to know.

**Implication for the near-term write module**: every entity written today is a training example for spec-LCN v1 tomorrow. Do not write sloppy entities on the assumption that the schema is "temporary." It is not; only the backing representation is.

---

## Open questions

Not blocking v1 writes, but flagged for resolution before heavy volume lands:

- **Who owns `outcome` updates on Decision?** Spec says post-verify or the next mission touching the file. Needs a pointer implementation when the write module exists.
- **Storage backend** — SQLite in repo, LCN v0 server on port 3737, or something else? Leaning SQLite for portability and because LCN v0 may get disrupted during LCN v1 work.
- **Pattern auto-extraction heuristics** — "structurally similar" is hand-wavy. First implementation: AST-fingerprint match for code, regex-skeleton match for prose.
