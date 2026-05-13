# CONSULT-PROTOCOL.md — LCN read protocol

**Authority**: TWO-MINDS.md §3.3, §3.4. This document specifies the query grammar, wire format, mandatory consult injection points, and recall-miss semantics.

**Version**: v1 (2026-04-19).

---

## Query types

Four keyed queries plus one fallback. All return JSON.

### 1. `by-file`

Retrieve all entities whose `file_paths` include a given path.

**Input**:
```json
{"type": "by-file", "path": "<string>", "entity_types": <list|null>}
```

**Output**:
```json
{"results": [<entity>, ...], "count": <int>}
```

When `entity_types` is `null`, all five types return. When supplied, filter to only those types. Ordering: `confidence` desc, then `updated_at` desc.

---

### 2. `by-failure-class`

Retrieve Error entities (and associated Convention entities) matching a class.

**Input**:
```json
{"type": "by-failure-class", "class": "<string>", "limit": <int>}
```

**Output**:
```json
{"errors": [<Error>, ...], "related_conventions": [<Convention>, ...]}
```

`related_conventions` = Convention entities whose `scope` intersects with the `file_paths` of any returned Error. This is the default wiring from failure diagnosis to prevention: the query that surfaces "we've seen this before" also surfaces "here's the rule we wrote to avoid it."

---

### 3. `by-mission-similarity`

Retrieve missions whose classifier input resembled a new request.

**Input**:
```json
{"type": "by-mission-similarity", "title": "<string>", "scope_hash": "<string>", "top_k": <int>}
```

**Output**:
```json
{"missions": [
  {"mission_id": "<string>", "title": "<string>", "outcome": "<enum>", "similarity_score": <float>, "entities_produced": [<entity_id>, ...]},
  ...
]}
```

Similarity = cosine over title embeddings + Jaccard over `scope_hash` components, weighted 0.6 / 0.4. This weighting is an implementation detail and may change; the **contract** is that `similarity_score ∈ [0, 1]` and higher means more similar.

---

### 4. `by-convention-scope`

Retrieve Convention entities whose scope matches a query scope.

**Input**:
```json
{"type": "by-convention-scope", "scope": "<string>"}
```

**Output**:
```json
{"conventions": [<Convention>, ...]}
```

Scope matching is prefix-aware with wildcards: query scope `.opencode/agent/*` matches stored scopes `.opencode/agent/orchestrator.md` and `.opencode/agent/*`. Query scope `.opencode/agent/orchestrator.md` also matches stored `.opencode/agent/*` (wildcard generalizes).

---

### 5. Free-text fallback (`search`)

**Input**:
```json
{"type": "search", "query": "<string>", "top_k": <int>}
```

**Output**:
```json
{"results": [<entity>, ...], "scores": [<float>, ...]}
```

Allowed **only when no keyed query fits**. Orchestrator-level injection MUST use keyed queries. Free-text is for stuck agents and human operators poking LCN directly. The write module treats a mission with too many free-text queries as a classifier-failure signal (surfaced in the post-verify phase).

---

## Mandatory consult injection

Three consults fire automatically on every Production+ mission. They are injected by the orchestrator into the next agent's context as a markdown section. No agent has to ask for them.

### Pre-plan consult (before planner dispatch)

**Queries**:
```python
queries = [
    {"type": "by-mission-similarity", "title": request_text, "scope_hash": predicted_scope_hash, "top_k": 3},
    *[{"type": "by-file", "path": p, "entity_types": ["Decision", "Rejection"]} for p in predicted_files],
]
```

**Injection into planner prompt**:
```
## Prior art
<similar missions — top 3, one line each: mission_id, title, outcome>

## Decisions and rejections on touched files
<per-file results, grouped by file>

(If all queries empty: "No prior art on file. Proceed with caution; this is new ground for LCN.")
```

---

### Pre-dispatch consult (after plan, before role dispatch)

**Queries**:
```python
queries = [
    {"type": "by-failure-class", "class": c, "limit": 5}
    for c in top_5_implied_classes(plan)
]
```

`top_5_implied_classes` is a bounded heuristic keyed off the plan's file paths and verb patterns. Implementation detail, but the **contract** is that it returns ≤5 entries from `failure-classes.md`.

**Injection into role prompt**:
```
## Known pitfalls
- <failure_class>: <root_cause excerpt> — prevented by: <related_convention rule if any>
```

---

### Post-verify consult (after execute, before report)

**Queries**:
```python
queries = [
    {"type": "by-file", "path": p, "entity_types": ["Convention"]}
    for p in actually_touched_files
]
```

**Injection into critic prompt**:
```
## Convention check
The following conventions apply to files touched in this mission. For each,
confirm the diff does not violate it, or explain the deliberate deviation:

- <rule> (scope: <scope>, why: <why>)
```

The critic's output is expected to address each Convention individually — either "respected" or "deliberately deviated because X."

---

## Skipping a consult

Any phase that fires a consult MUST record the queries sent and the results received in the mission audit log. A mission that transitions through a phase without the matching consult entry trips the circuit breaker and writes an Error entity with `failure_class = "consult-skipped"`.

The only legal skip is **by tier**: MVP missions have no mandatory consults. Production+ skipping is always an error; even "the plan is obvious" is not a valid reason, because the whole point of the consult is that "obvious" is what gets us in trouble.

---

## Recall miss semantics

An empty result is a signal, not silence. When a consult returns `count: 0`, the agent receiving the injected section must acknowledge it explicitly.

| Consult | Empty-result behavior |
|---|---|
| Pre-plan | Annotate "no prior art" in the plan. The planner acknowledges novelty in its reasoning section. |
| Pre-dispatch | Annotate "no known pitfalls for `<class>`". The role proceeds but reports any failures precisely so the taxonomy learns. |
| Post-verify | Annotate "no conventions on touched files." The critic focuses on style alone, and flags whether a Convention *should* be written. |

**Anti-pattern**: an agent sees "no prior art" and invents confidence from thin air ("since there's no prior art, this must be simple"). The correct read of a recall miss is the opposite: **the system knows it doesn't know**, which is a cue for more care, not less. This is enforced by the role prompts, not by this document — but the protocol exists to make the cue loud enough that prompts can use it.

---

## Interpretability

Every injected section ends with a line:

```
— injected by CONSULT-PROTOCOL v1, queries: <N>, results: <M>
```

This makes it trivial to tell at a glance whether the orchestrator fired the consult. If the section is absent, the consult didn't fire; if it's present with `results: 0`, the consult fired and LCN had nothing. Those are very different states and both need to be distinguishable from the agent's side.

---

## Open questions

- **Query budget**: should there be a max-queries-per-mission to prevent runaway consult loops in healing scenarios? Working answer: 50. Re-evaluate when data exists.
- **Caching**: two consults in the same phase for the same file will currently fire twice. First implementation may ignore; later, a per-mission cache is worth it.
- **Free-text fallback UX**: who sees the "too many free-text queries" signal? Leaning toward: surfaced in the post-verify critic prompt as "the planner reached for free-text N times — likely a classifier or keyed-query gap."
