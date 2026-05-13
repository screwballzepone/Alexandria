# LCN Brain ↔ JANUS Integration Architecture Spec

**Date:** 2026-05-13  
**Agent:** @system-scientist (DeepSeek V4 Pro)  
**Method:** Scientific-method protocol — Observe → Hypothesize → Test → Conclude → Recommend → Record  
**Status:** RESEARCH FINDING — for orchestrator review

---

## Executive Summary

**HONEST VERDICT: Do NOT integrate the LCN neural substrate now.** The Brain is not a memory system — it's a PDE prediction testbed that trains a 96-parameter weight matrix on Burgers' equation. The existing LCN server (`lcn_server.py`) is a simple SQLite graph database that has nothing to do with the LCN spiking architecture. The **entity schema** (5 canonical types: Decision, Rejection, Error, Pattern, Convention) is independently useful and should be activated now via the SQLite path. The **neural substrate** should remain a research project until Phase C (4-arm testbed) validates (or disproves) the core claim: that training only W_z produces useful representations.

**Key finding:** The PIPELINE.md describes a "two minds" architecture where LCN is the implicit System-1 face. But the current code does not implement this — the LCN server is a graph DB, and the LCN neural code trains on PDEs, not agent memory. The integration path in PIPELINE.md Phase D needs revision.

---

## 1. OBSERVE — What Actually Exists

### 1.1 The "Brain" Is Two Completely Separate Things

| Component | File | What It Actually Does | Status |
|-----------|------|----------------------|--------|
| **LCN Server** (the "running server") | `Brain/lcn_brain/lcn_server.py` | Flask + SQLite graph: nodes (label, value, activation), edges (relation, weight), STDP reinforcement. 8 REST endpoints. | **Works** (Flask runs, DB initialized) |
| **LCN Neural Code** (the "spiking brain") | `Brain/lcn_brain/lcn/*.py` (14 files) | Spiking encoder → SSF → Clock → RCD → Plastic ODE → Readout. Trains 96-param W_z on Burgers' PDE prediction. | **0/49 tests pass** (JAX not installed) |

**These two components share a directory but have ZERO code-level connection.** `lcn_server.py` does not import anything from `lcn/`. The `lcn/` modules do not import anything from `lcn_server.py`. The server is a graph database; the neural code is a PDE solver.

### 1.2 The LCN Server's Actual Schema

```sql
-- nodes: associative memory entries
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    value TEXT NOT NULL,
    activation REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX idx_nodes_label_value ON nodes(label, value);

-- edges: relationships between nodes
CREATE TABLE edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    relation TEXT DEFAULT 'related-to',
    weight REAL DEFAULT 0.5,
    created_at TEXT NOT NULL
);
```

**What this can store:** A labeled property graph. Each node is a `(label, value)` pair with a scalar activation. Edges connect nodes with a relation type and weight. STDP endpoint boosts edge weights. Consolidation endpoint decays activations (0.9× multiplier) and prunes weak, disconnected nodes.

**What this cannot do:** Anything neural. No spikes, no encoding, no SSF hidden state, no clock ticks, no plastic weight matrices, no forward-mode gradients, no JVP estimation. This is a conventional knowledge graph.

### 1.3 The LCN Neural Substrate's Actual Capacity

From `constants.py`:
- `D = 64` — SSF working memory dimension (FIXED)
- `M = 32` — RCD episodic memory dimension (FIXED)  
- `P = 1` — Readout output dimension (scalar field prediction)
- **W_z: 96 parameters** — the ONLY trainable component
- SSF parameters: 1,065,024 — FIXED, never trained
- RCD parameters: 9,344 — FIXED, never trained
- **Trainable fraction: 0.009%**

**What this can encode:** At most 96 float32 values = 384 bytes of "learned memory." This is equivalent to ~12-24 semantic key-value pairs (at 16-32 bytes each). The existing SQLite AgentMemory table already stores arbitrary-length text strings — it is strictly more expressive.

**The core empirical claim is unproven:** "Can training only a 96-parameter weight matrix produce useful memory?" — No experiment has yet tested this. The 4-arm testbed (Phase C) is designed to answer it, but the harness is a skeleton and JAX isn't installed.

### 1.4 What JANUS Already Has for Memory

| System | Storage | Capacity | Key-Value? | Graph? | Neural? |
|--------|---------|----------|-----------|--------|---------|
| **AgentMemory** (`core/memory.py`) | SQLite at `~/.local/share/opencode/agent_memory.db` | Unlimited text | ✅ (workspace, key, value, tags) | ❌ | ❌ |
| **LCN Write** (`MagnumOpus/reference/lcn_write.py`) | SQLite at `.lcn/lcn.sqlite` | 5 typed entities (Decision, Rejection, Error, Pattern, Convention) | ❌ (typed entities) | ❌ | ❌ |
| **LCN Server** (`lcn_server.py`) | SQLite at `.lcn/lcn_memory.db` | Labeled property graph with activation + edges | Sort of (label→value) | ✅ | ❌ |
| **Supermemory plugin** | npm/open-code-supermemory | 9 project + 1 user memories | ✅ (cross-session) | ❌ | ❌ |
| **Error log** (`.opencode/error-log.jsonl`) | JSONL file | Append-only error records | ✅ (timestamped events) | ❌ | ❌ |
| **LCN Neural** (`Brain/lcn_brain/lcn/`) | 96 float32 params in W_z | 384 bytes of learned weights | ❌ (continuous weights) | ❌ | ✅ |

**Key insight:** JANUS already has **five separate memory/storage systems**. Adding a sixth (LCN Server) or seventh (LCN Neural) creates fragmentation, not consolidation. The real architectural problem is that these systems don't talk to each other.

### 1.5 The Integration Path (per PIPELINE.md Phase D) Assumes a Fiction

PIPELINE.md Phase D-1 says:
> "Write Brain/lcn_brain/start-lcn.bat... Start a small HTTP server on port 3737. Endpoints: /query, /write, /health, /stats. Backed by the trained Brain weights for the real thing."

**Problem:** The LCN server already exists at port 3737 and already has these endpoints — but it's a graph database, NOT "trained Brain weights." The trained Brain weights (W_z) are a 96-parameter matrix that predicts Burgers' equation scalar fields. They have no `/query` or `/write` endpoints and no mechanism for storing agent decisions.

Phase D-3 says:
> "@memory-writer reads mission.json... Calls lcn_client.write_entity() for each."

**Problem:** `lcn_client.py` doesn't exist in active code (it's only in reference), and even if it did, it would talk to the SQLite graph server — not a neural substrate.

**The PIPELINE.md imagines an integration that the code doesn't support.** The elegant "two minds" theory hasn't been mapped to the actual codebase.

---

## 2. HYPOTHESIZE — Testable Claims About Integration

### H1: "Integrate the LCN neural substrate now"

> **Claim:** If we integrate the LCN neural substrate into JANUS now (Phase D before Phase C validates), then JANUS would gain a learned memory that improves over time, because the spiking neural architecture can encode richer patterns than SQLite key-value storage.

**Confidence: LOW**

**Test:**
1. Compare representational capacity: LCN W_z (96 params, 384 bytes) vs SQLite AgentMemory (arbitrary text)
2. Compare query capability: LCN readout produces scalar field predictions; SQLite does LIKE searches
3. Compare integration cost: install JAX + write lcn_jvp + wire 4-arm testbed + build query interface from scratch

**Expected result:** At current capacity (96 params), the neural substrate can encode fewer distinct patterns than a single SQLite text row. The entire W_z matrix (384 bytes) is smaller than the average error log entry (~500 bytes). The neural substrate is strictly less capable as a memory system right now.

### H2: "Activate the LCN server SQLite graph as a bridge"

> **Claim:** If we activate the LCN server's graph database with the 5 entity types from LCN-SCHEMA.md, then JANUS gains an associative memory with activation decay and graph relationships, which is more useful than key-value AgentMemory for cross-session learning.

**Confidence: MEDIUM**

**Test:**
1. Compare graph queries (BFS neighborhood, LIKE search with edges) vs key-value lookups
2. Measure whether activation decay + consolidation (pruning weak nodes) produces better signal-to-noise than static storage
3. Check whether the 5 entity types (Decision, Rejection, Error, Pattern, Convention) are more useful than free-form AgentMemory keys for agent operations

**Expected result:** The graph model IS incrementally better than key-value for associative recall (e.g., "what decisions relate to this file?" vs "retrieve key='file_config'"). But the benefit is marginal — it's still SQLite underneath, and the activation decay mechanism is a simple 0.9× multiplier.

### H3: "Wait until Phase C validates the core claim before integrating"

> **Claim:** If we defer neural integration until Phase C (4-arm testbed) produces evidence that A+C training produces useful representations, then we avoid building integration infrastructure for an architecture that may be fundamentally flawed.

**Confidence: HIGH**

**Test:**
1. Check whether Phase C (which requires Phase A + B first) can realistically complete
2. Evaluate whether delaying integration blocks any other pipeline phases
3. Assess whether v0 (SQLite entity schema) can serve as the integration bridge now, deferring the "neural swap" to Phase H

**Expected result:** Phase C is gated on Phase A (JAX install) + Phase B (write lcn_jvp) — both are engineering work, not research. But even if Phase C succeeds, the capacity question (96 params) means the neural substrate won't be useful for agent memory until full-network training works. The entity schema approach (H2) is the right bridge.

### H4: "The entity schema is independently valuable regardless of storage backend"

> **Claim:** The 5 canonical entity types (Decision, Rejection, Error, Pattern, Convention) with their query protocols (pre-plan, pre-dispatch, post-verify) provide value whether stored in SQLite v0 or a future neural cortex. The schema is the durable architectural contribution; the storage is implementation detail.

**Confidence: HIGH**

**Test (already part of PIPELINE.md):**
1. The entity schema has 5 well-defined types with natural keys and idempotency rules
2. The consult protocol (CONSULT-PROTOCOL.md) defines query semantics independent of storage
3. The capability assessor gates when to pay the consult cost
4. `lcn_write.py` (reference) already implements validation and persistence

**Evidence:** This is the forward-compat bet in PIPELINE.md §3: "The entity schema is stable; the storage is swappable." The schema has been designed correctly. What's missing is activation — wiring it into the orchestrator's dispatch flow.

---

## 3. TEST — Evidence For and Against Integration

### 3.1 Supporting Evidence (for some form of integration)

1. **The entity schema is ready.** `lcn_write.py` validates all 5 types. `capability_assessor.py` gates on mission complexity. 38+ tests green for the assessor. The schema design is sound.

2. **The LCN server already runs.** `lcn_server.py` starts on port 3737, has a SQLite graph backend, and exposes 8 REST endpoints. It's a working service — just not a neural one.

3. **The PIPELINE.md correctly identifies the problem:** "A coding agent without persistent memory re-derives every decision every session." The entity types (Decision, Rejection, Error, Pattern, Convention) directly address this.

4. **The forward-compat architecture is correctly designed.** The entity schema doesn't depend on the neural substrate. The query protocols (CONSULT-PROTOCOL.md) don't depend on spiking neurons. The swap from v0 SQLite to v1 cortex is architecturally clean.

5. **JANUS already has 5 memory systems that don't communicate.** Integrating them through a unified entity schema would be a genuine architectural improvement.

### 3.2 Contradicting Evidence (against integrating the neural substrate now)

1. **The neural substrate can't do agent memory.** W_z (96 params) is a matrix that maps (SSF hidden + RCD cell) → scalar field prediction. It was never designed to store or retrieve discrete memories. There is NO code path from "agent writes a Decision" to "neural substrate encodes it." Building that path would be months of research work.

2. **The core claim is unvalidated.** The efficiency analysis found that both "BPTT" and "LCN" arms train only the same W_z — the SSF and RCD are FIXED. We don't know if training 96 params produces useful representations for any task, let alone agent memory.

3. **The LCN server is misrepresented in PIPELINE.md.** It's described as "Backed by the trained Brain weights" (Phase D-1 step 1) when it's actually a SQLite graph. This creates a false expectation of what integration would achieve.

4. **Adding another memory system creates fragmentation.** JANUS already has AgentMemory (SQLite), LCN server graph (SQLite), Supermemory plugin, Error log (JSONL), and LCN write target (SQLite). Adding a neural substrate with 384 bytes of capacity doesn't consolidate — it adds a seventh system with the lowest capacity of all.

5. **The "two minds" metaphor doesn't map to the code.** GENESIS (deliberate System-2) is implemented by the orchestrator + protocols. LCN (implicit System-1) was supposed to be the neural substrate — but the actual running service is a graph database, which is equally "deliberate." There's no implicit/System-1 computation happening anywhere.

6. **Phase A–C are long and uncertain.** Installing JAX on Windows is historically fraught. Writing `lcn_jvp` requires implementing a forward-mode JVP estimator from a spec. The 4-arm testbed harness is a skeleton. Total time to Phase C validation: weeks, not hours.

### 3.3 Key Evidence Table

| Claim | Evidence FOR | Evidence AGAINST | Verdict |
|-------|-------------|-----------------|---------|
| "LCN neural substrate provides useful memory" | The architecture (SSF+clock+RCD+plastic) is theoretically sound per lit-survey (6.5/10 novelty) | Only 96 params trainable; no agent-memory code path exists; 0/49 tests pass; capacity < 1 SQLite row | **DISPROVED for current state** |
| "The entity schema should be activated now" | 5 typed entities, consult protocol, capability assessor all designed; tests green; addresses real problem (re-deriving decisions) | LCN server is a graph DB, not integrated with orchestrator; adds a 6th memory system | **SUPPORTED — activate via SQLite, not neural** |
| "The LCN server graph is better than AgentMemory" | Graph edges enable associative queries; activation decay provides recency signal | Both are SQLite; graph queries cost more tokens; marginal benefit over key-value for simple recalls | **WEAKLY SUPPORTED — graph queries are nice but not critical** |
| "Wait for Phase C validation before neural integration" | Avoids building integration for unproven architecture; Phase C will produce empirical evidence | Delays the "two minds" vision; but v0 entity schema can run now without waiting | **STRONGLY SUPPORTED** |

---

## 4. CONCLUDE — Honest Verdict

### 4.1 Is the LCN Neural Substrate Worth Integrating Now?

**No. The LCN neural substrate is a research project, not a deployable memory system.**

The substrate trains a 96-parameter weight matrix on Burgers' equation. It has never been connected to agent operations. It has no read/write interface for memories. Its capacity (384 bytes) is smaller than a single error log entry. **The substrate is not blocked on integration — it's blocked on its own validation (Phase A–C).**

### 4.2 Should We Activate the Entity Schema Now?

**Yes — but through SQLite, not through the neural substrate.**

The 5 entity types (Decision, Rejection, Error, Pattern, Convention) address a real problem: JANUS re-derives decisions every session because it has no persistent memory of what it tried before. The schema has been designed, the write-side code exists, the query protocol exists, the capability assessor exists. What's missing is activation: wiring `consult.py` into the orchestrator's dispatch flow and writing entities after missions.

### 4.3 The Real Architectural Problem

The integration question is backward. The problem isn't "how do we connect the Brain to JANUS?" — it's "JANUS has 5 memory/storage systems and none of them talk to each other or to the orchestrator's decision flow."

**Current memory fragmentation:**

```
AgentMemory (SQLite) ← manually written, manually read
Error Log (JSONL)    ← appended, never consulted pre-mission
LCN Server (SQLite)  ← running but never written to
LCN Write (SQLite)   ← validation code exists, never called from orchestrator
Supermemory (plugin) ← stores context files, separate from entity schema
```

**What should exist:**
```
Entity Store (SQLite, LCN schema)
    ↑ writes (post-mission: Decisions, Errors, Patterns)
    ↓ reads  (pre-plan: similar decisions on touched files)
    ↓ reads  (pre-dispatch: known pitfalls for failure classes)
    ↓ reads  (post-verify: conventions applying to touched files)

Orchestrator dispatch flow
    ← consults entity store at 3 points (pre-plan, pre-dispatch, post-verify)
    → writes back after missions
```

The entity store can start with SQLite v0, migrate to the neural substrate IF and WHEN the substrate proves capable at Phase C (and more realistically, after full-network training works at Phase D of the LCN pipeline).

### 4.4 Confidence Assessment

| Finding | Confidence | Basis |
|---------|-----------|-------|
| Neural substrate not ready for integration | **Very High** | 0/49 tests, 96-param capacity, no agent-memory code path, core claim unproven |
| Entity schema should be activated via SQLite | **High** | Schema designed, write code exists, problem (memory-less decisions) is real |
| LCN server graph is marginally better than AgentMemory | **Medium** | Graph edges add associative queries, but both are SQLite; marginal benefit |
| Full-network training would change the calculus | **Medium** | If SSF+RCD can be trained (1.07M params), representational capacity jumps 10,000× — but this has never been demonstrated |
| Phase C 4-arm testbed will produce useful data | **Medium-High** | A+C might outperform BPTT at long horizons — or it might flatline. Either outcome is valuable information. |

---

## 5. RECOMMEND — Concrete Actions

### R1 (CRITICAL): Do NOT wire the LCN neural substrate into JANUS now

**What:** Remove the aspirational language from PIPELINE.md Phase D that assumes the LCN server is "backed by trained Brain weights." The server is a graph database. Document this honestly.

**Change:** In `MagnumOpus/PIPELINE.md` Phase D-1, replace:
```
"Backed by either the v0 SQLite... OR the trained Brain weights for the real thing"
```
with:
```
"Backed by the v0 SQLite (lcn_write.py/lcn_read.py schema). The neural substrate
is a separate research project (Brain/lcn_brain/lcn/). Integration of neural weights
is deferred to Phase H (Cortex Transition) after Phase C validation and full-network
training are complete."
```

**Rollback:** Restore aspirational language in PIPELINE.md.

### R2 (HIGH): Activate the LCN entity schema via SQLite v0 — wire it into the orchestrator

**What:** Move `lcn_write.py` and `capability_assessor.py` from `MagnumOpus/reference/` to `.opencode/tools/`. Build `lcn_read.py` (mirrors consult protocol query types). Build `consult.py` (orchestrator-facing helper). Wire 3 consult points into orchestrator.md (pre-plan, pre-dispatch, post-verify). Wire post-mission write-back via @memory-writer.

**This is essentially PIPELINE.md Phase D-2 and D-3 — but explicitly scoped to SQLite v0, with the neural substrate swap deferred to Phase H.**

**Change:**
1. Move `MagnumOpus/reference/lcn_write.py` → `.opencode/tools/lcn_write.py`
2. Move `MagnumOpus/reference/capability_assessor.py` → `.opencode/tools/capability_assessor.py`
3. Build `.opencode/tools/lcn_read.py` with 5 query types per CONSULT-PROTOCOL.md
4. Build `.opencode/tools/consult.py` as orchestrator-facing helper
5. Add 3 consult points to `orchestrator.md` (≤10 lines each, per Phase D-2 constraints)
6. Wire post-mission write-back in mission-completion protocol

**Expected impact:** JANUS stops re-deriving decisions every session. Past Decisions/Errors/Conventions are injected into agent context. Feedback loop closes.

**Rollback:** Remove consult wiring from orchestrator.md; set `JANUS_CONSULT_ENABLED=0` env var.

**Confidence: High** — this is what PIPELINE.md Phase D-2 already plans, minus the neural swap fiction.

### R3 (MEDIUM): Resolve or document the LCN server ambiguity

**What:** The `lcn_server.py` at port 3737 is a graph database. Decide whether it:
- (a) Becomes THE v0 entity store (replaces lcn_write.py's separate SQLite)
- (b) Remains a separate experimental service (not connected to JANUS)
- (c) Gets merged with lcn_write.py into a unified `lcn_service.py`

**Recommendation:** Option (a) — make it the v0 entity store. The graph structure (nodes with activation, edges with weights) maps naturally to the 5 entity types:
- Each entity is a node with `label=entity_type`, `value=natural_key`
- Relationships between entities (e.g., Decision→touched files, Error→failure_class) are edges
- Activation decay provides recency-based forgetting
- STDP boost endpoint reinforces entities that are queried successfully

**Change:** Extend `lcn_server.py` to accept typed entities (Decision, Rejection, etc.) at the `/node` endpoint with entity-specific validation. Add `/consult` endpoint that implements the CONSULT-PROTOCOL.md query types.

**Rollback:** Revert to treating lcn_server.py as experimental/separate.

**Confidence: Medium** — the graph model is a better fit than key-value for associative recall, but the additional complexity may not be worth it for v0.

### R4 (LOW): Proceed with Phase A (JAX install + bug fixes) as a standalone research activity

**What:** Phase A is mechanical engineering that should happen regardless of integration plans. The Brain tests should pass. But treat it as **LCN research project maintenance**, not as a blocker for JANUS feature work.

**Why:** Even if the neural substrate isn't integrated into JANUS, the LCN project is independently interesting as a neuromorphic computing experiment. Fixing the JAX dependency and two known bugs is low-effort and useful for the LCN project's own roadmap.

**Change:** Execute Phase A steps as documented in PIPELINE.md. Do not block JANUS integration on it.

**Rollback:** None needed — this is additive work.

**Confidence: High** — Phase A is low-risk engineering with clear acceptance criteria (42/49 tests pass).

### R5 (MEDIUM): Add a "Brain Readiness Gate" to PIPELINE.md Phase D

**What:** Before Phase D can begin, the following must be true:
1. Phase C complete (4-arm testbed validates A+C training)
2. LCN neural substrate has a proven read/write interface for the 5 entity types (not just PDE prediction)
3. Full-network training (SSF + RCD + W_z) demonstrated OR capacity argument resolved (96 params is acknowledged as sufficient for the use case)

**Change:** Add a §D-0 "Pre-flight Checklist" to PIPELINE.md with these 3 items.

**Rollback:** Remove the gate.

**Confidence: High** — this prevents building integration on an unvalidated foundation.

---

## 6. ARCHITECTURE SPEC: Memory Tier Mapping

If and when the neural substrate IS ready (post-Phase C validation, full-network training), here is how the mapping would work:

### 6.1 The Three LCN Memory Tiers Map to JANUS Operations

| LCN Substrate | State | Timescale | JANUS Equivalent | Encoding |
|---------------|-------|-----------|-----------------|----------|
| **Working (h)** | SSF hidden state, ℝ^64 | Per-timestep (~seconds in agent time) | Current session context: active files, recent decisions, in-flight agent dispatches | Input features (file paths, error classes, dispatch targets) encoded as spike trains via LIF encoder |
| **Episodic (c)** | RCD cell state, ℝ^32 | Per-distillation-tick (~minutes) | Individual missions: feature summaries, decisions made, errors encountered, reviewer verdicts | At mission completion: SSF state h(T) is at peak context; clock ticks (high spike activity); RCD condenses h(T) into c_k |
| **Structural (W_z)** | Plastic weight matrix, ℝ^(P×(D+M)) | Across session (~hours/days) | Cross-mission patterns: conventions learned from repeated patterns, error classes that recur, decision patterns that work | W_z is updated via plastic ODE at each tick: dW/dt = ĝ - μ(t)·W. Over many missions, W_z learns to map (working state + episodic context) → useful predictions |

### 6.2 When a "Tick" Fires in JANUS Terms

In the LCN architecture, the distillation clock fires when `ρ(t) = ||S(t)||_1 > ρ_ema` — spike population activity exceeds its EMA-tracked baseline.

**JANUS mapping:** A "tick" fires when:
1. **A mission completes** (highest spike activity — many files changed, decisions made, errors encountered)
2. **A reviewer returns a strong verdict** (high surprise — FAIL on expected-PASS, or PASS on risky change)
3. **An error triggers healing protocol** (surprise signal — unexpected failure pattern)
4. **A new Convention is canonized** (Pattern confidence ≥ 3, explicit human sign-off)

The spike population activity ρ(t) would be computed from JANUS operational signals:
- Number of files touched in current mission ÷ expected files
- Error count per mission ÷ expected error count  
- Reviewer score deviation from expected score
- Decision novelty (cosine distance from nearest prior Decision in entity store)

### 6.3 Read Protocol (Future, Post-Phase C)

```
┌─────────────┐     GET /query?type=decision&files=touched     ┌──────────────┐
│ Orchestrator │ ──────────────────────────────────────────────→│  LCN Service  │
│  (pre-plan)  │                                                │  (port 3737)  │
│              │ ←──── { "results": [{ decision, similarity }]} │               │
└─────────────┘                                                │  ┌─────────┐  │
                                                               │  │ Encoder │  │
                                                               │  │   ↓     │  │
                                                               │  │  SSF    │  │
                                                               │  │   ↓     │  │
                                                               │  │  W_z    │  │
                                                               │  └─────────┘  │
                                                               └──────────────┘
```

**Query flow:**
1. Orchestrator sends query: `{ "type": "by-file", "files": ["core/worker.py"], "entity_types": ["Decision", "Error"], "top_k": 5 }`
2. LCN service encodes the query as input to the LIF encoder
3. SSF processes the encoded query through working memory h
4. Readout W_z @ (u ⊙ σ(β|u|)) produces similarity scores
5. Top-k matching entities are returned with confidence scores

### 6.4 Write Protocol (Future, Post-Phase C)

**Encoding scheme for agent decisions as LCN input:**

```
JANUS Decision {
  "entity_type": "Decision",
  "approach": "used taskkill /F /T /PID for process cleanup",
  "touched_files": ["core/worker.py", "core/hooks.py"],
  "outcome": "merged",
  "confidence": 0.85
}
        ↓
LIF Encoder input: rate-code the decision fields
  - File paths → one-hot over project file index → rate_code
  - Outcome → binary encoding
  - Confidence → scalar input
        ↓
SSF processes spike trains → h(t) trajectory
Clock fires at mission completion → tick
RCD condenses h(τ_k) → c_k (episodic memory)
Plastic ODE: W_z ← W_z + η·(ĝ - μ(t)·W_z)
```

### 6.5 Integration Architecture (Future Process Model)

```
┌─────────────────────────────────────────────────────────┐
│                    JANUS (PySide6 GUI)                    │
│  ┌───────────┐  ┌──────────┐  ┌───────────────────────┐ │
│  │Orchestrator│  │ @coder   │  │ @memory-writer        │ │
│  │  ┌──────┐ │  │          │  │  writes Decisions/     │ │
│  │  │consult│ │  │          │  │  Errors/Patterns       │ │
│  │  └──┬───┘ │  │          │  └───────────┬───────────┘ │
│  └─────┼─────┘  └──────────┘              │             │
│        │                                   │             │
│        │ consult.py                        │ lcn_write   │
│        │                                   │             │
└────────┼───────────────────────────────────┼─────────────┘
         │                                   │
         │  HTTP (localhost:3737)             │  HTTP
         ▼                                   ▼
┌─────────────────────────────────────────────────────────┐
│              LCN Service (separate process)              │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐   │
│  │/query    │    │/write    │    │/consolidate       │   │
│  │  ↓       │    │  ↓       │    │  (activation      │   │
│  │ Encoder  │    │ Encoder  │    │   decay + prune)  │   │
│  │  ↓       │    │  ↓       │    └──────────────────┘   │
│  │ SSF      │    │ SSF      │                            │
│  │  ↓       │    │  ↓       │                            │
│  │ Readout  │    │ Plastic  │                            │
│  └──────────┘    └──────────┘                            │
│                                                          │
│  Storage: .lcn/lcn_memory.db (SQLite graph, v0)          │
│           → upgraded to W_z matrix + entity index (v1)   │
└─────────────────────────────────────────────────────────┘
```

**Process model:**
- LCN Service runs as a separate Flask process on `localhost:3737`
- Started via `start-lcn.bat` (user manually, or auto-start per Phase F)
- JANUS orchestrator calls `consult.py` which makes HTTP requests to LCN Service
- @memory-writer calls `lcn_write.py` which makes HTTP POST to LCN Service
- LCN Service manages its own lifecycle (consolidation on timer, health checks)
- **v0:** All queries go through SQLite graph (nodes/edges with LIKE search)
- **v1 (post-Phase C validation):** Queries go through encoder→SSF→readout pipeline; writes go through encoder→SSF→plastic ODE pipeline

**Error handling:**
- If LCN Service is down: `consult.py` returns empty results (graceful degradation, not mission failure)
- If a write fails: logged to error-log.jsonl with type `lcn-write-failed`; entity queued for retry
- If consolidation prunes an entity that's later needed: re-creation is idempotent (same natural key)
- The `JANUS_CONSULT_ENABLED` env var provides kill switch

---

## 7. RECOMMENDATIONS SUMMARY

| # | Recommendation | Priority | Effort | Impact | Blocks |
|---|---------------|----------|--------|--------|--------|
| R1 | Update PIPELINE.md Phase D to remove "trained Brain weights" fiction | CRITICAL | 1 edit | Prevents building on false assumptions | Nothing |
| R2 | Activate entity schema via SQLite v0 — move tools, build consult, wire orchestrator | HIGH | 1-2 sessions | Closes feedback loop; JANUS stops re-deriving decisions | Nothing |
| R3 | Resolve LCN server ambiguity — make it the v0 entity store or document it as experimental | MEDIUM | 1 session | Prevents two competing SQLite stores | R2 |
| R4 | Proceed with Phase A (JAX install + bug fixes) as standalone research | LOW | 30-90 min | Brain tests pass; LCN project unblocked | Nothing |
| R5 | Add "Brain Readiness Gate" to PIPELINE.md Phase D | MEDIUM | 1 edit | Prevents premature neural integration | R1 |

**Rollback for all recommendations:** Revert the edits or `git stash` the changes. All changes are additive or text edits to PIPELINE.md.

---

## 8. APPENDIX: The Disconnect Visualized

```
What PIPELINE.md imagines:
  
  JANUS ──writes──→ LCN Brain (neural substrate) ──returns──→ learned patterns
                        ↓
                  "Spiking neural network with forward-mode JVP"
                  "Three memory substrates at different timescales"
                  "The implicit System-1 face"

What actually exists:
  
  JANUS ──(no connection)──→ LCN Neural Code (Burgers' PDE solver, 96 params)
                                ↓ 0/49 tests pass, JAX not installed
                              "Predicts scalar fields, not agent memory"
                              
  JANUS ──(no connection)──→ LCN Server (SQLite graph, Flask on :3737)
                                ↓ runs, but never written to
                              "Labeled property graph with activation decay"
                              
  JANUS ──(key-value)──→ AgentMemory (SQLite at ~/.local/share/...)
                             ↓ works, manually used
                           "Arbitrary text key-value pairs"
```

**The integration spec must start from what exists, not from what the architecture documents imagine exists.**

---

*Report written by @system-scientist. Store to memory with type `research-finding` and scope `project`.*
