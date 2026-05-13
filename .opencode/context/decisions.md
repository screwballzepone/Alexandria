# Architectural Decisions

**Purpose**: Log of key architectural decisions with rationale, alternatives considered, and trade-offs accepted. Read by all agents at session start to avoid re-debating settled questions. Append new entries — never overwrite or delete existing entries.

## Key Decisions

### 22-Agent Roster with opencode-go/ Provider Prefix
**Status**: Implemented — active. **Context**: Early versions used inconsistent provider prefixes. **Decision**: Use `opencode-go/` as the provider prefix for all 22 agents, with individual model strings selecting the actual backend. **Rationale**: Unifies dispatch routing, eliminates provider-specific failure modes (Cerebras Qwen stalls, Perplexity Sonar unresponsive). **Alternatives considered**: Mixed providers per agent (rejected — flaky), single model for all (rejected — capability mismatch), OpenAI provider (rejected — model diversity unsupported). **Trade-offs**: Locks project to opencode-go's model catalog; GLM-5.1 and Mimo V2.5 Pro are only available through opencode-go. Files: `.opencode/opencode.json`, `.opencode/agent/*.md`.

### SQLite v0 Entity Store for Memory (Swappable)
**Status**: Implemented — reference at `MagnumOpus/reference/lcn_write.py`, mission MEMORY-V0-2026-05-13 activating. **Context**: No working memory; 8-16K tokens wasted per session on re-discovery; LCN Brain blocked on JAX. **Decision**: Lightweight SQLite entity store with 5 types (Decision, Rejection, Error, Pattern, Convention). No ORM, inline ULID, idempotent upserts via natural_key + entity_type unique index. **Rationale**: SQLite is stdlib, zero dependencies, handles concurrent reads. When neural LCN matures, only the backend changes — interface stays the same. **Alternatives considered**: Wait for LCN Brain (rejected — months), JSON files (rejected — concurrent corruption), OpenCode's own DB (rejected — implementation detail coupling), vector DB (rejected — overkill). **Trade-offs**: No semantic search, no fuzzy matching, no vector similarity. Fixed entity schema.

### Forward-Mode JVP for LCN Brain (No jax.grad)
**Status**: Implemented — blocked on JAX install. **Context**: Plastic weights in ODE-based readout cannot be differentiated through backward-mode autodiff because the update depends on the forward trajectory. **Decision**: Forward-mode JVP via custom `lcn_jvp` micro-library (dual.py, estimators.py, probes.py, projection.py). **Rationale**: Directly computes directional derivative for plastic weight updates; avoids JAX autodiff limitations entirely. **Alternatives considered**: jax.grad with checkpointing (rejected — infeasible for forward-dependent updates), jax.vjp (rejected — undefined backward pass), PyTorch functorch (rejected — JAX FP model mismatch). **Trade-offs**: O(N) parameter scaling vs O(1) for backward mode; acceptable for ~10K parameters.

### Burgers' Equation as Testbed
**Status**: Implemented — blocked on JAX install. **Context**: Needed a PDE benchmark for LCN pipeline (spike encoder -> SSF -> RCD -> readout). **Decision**: 1D viscous Burgers' equation (u_t + u u_x = nu u_xx) with 4-arm comparison (LCN, LCN w/o plastic, MLP baseline, idealized small LCN). **Rationale**: Canonical "simplest nonlinear PDE" — tests convection + diffusion; analytically tractable. **Alternatives considered**: Navier-Stokes (too expensive), Kuramoto-Sivashinsky (too chaotic), advection-diffusion (too simple). **Trade-offs**: PDE performance doesn't directly measure code/decision memory capability, but architecture is domain-agnostic.

### Keep Brain/ as Separate Research Project
**Status**: Implemented — enforced after deletion incident. **Context**: Cleanup audit deleted Brain/ (56 files, 49 tests) as "dead code"; it was PIPELINE.md Phase A-C, the central bet of two-minds architecture, marked BLOCKED (needs JAX). **Decision**: Restore from git, establish "BLOCKED ≠ DEAD" rule. Brain stays in-repo as separate research project with its own pyproject.toml and test suite. **Rationale**: LCN architecture is the long-term vision; compatibility between neural memory and SQLite v0 entity schema must be maintained in-repo. **Alternatives considered**: Delete permanently (rejected — months of research abandoned), move to separate repo (rejected — schema compatibility risk). **Trade-offs**: 56 files + 49 failing tests occupy disk and confuse cleanup tooling.

### V2 Compaction Format (tail_turns, preserve_recent_tokens)
**Status**: Implemented — configured. **Context**: V1 compaction (`keep_first`, `max_context_window_tokens`) aggressively pruned from the front, losing session objectives and early decisions. **Decision**: V2 parameters: `tail_turns: 2`, `preserve_recent_tokens: 50000`, `reserved: 1000`. Auto-compaction at >80% usage. **Rationale**: Keeps session tail (recent decisions, current context) intact while compacting middle (completed tool calls, resolved errors). **Alternatives considered**: No compaction (rejected — 1M token limit), manual compression only (rejected — lossy, judgment-dependent). **Trade-offs**: Longer sessions still need manual compression; 1000-reserved margin triggers compaction slightly before hard limit.

### Task Tier Classification System
**Status**: Implemented — active. **Context**: Need to prevent wasted dispatches and ensure appropriate rigor per task complexity. **Decision**: 8 tiers (READ, TINY, STANDARD, COMPLEX, PROJECT, RESEARCH, META, CREATIVE) with increasing agent involvement. READ/TINY skip full pipeline. PROJECT uses mission.json state machine. **Rationale**: Prevents over-dispatch on simple tasks and under-planning on complex ones. **Alternatives considered**: Binary simple/complex (rejected — too coarse), single pipeline for all tasks (rejected — wasteful).

## Files Touched

- `.opencode/opencode.json` — model/provider config, compaction settings, agent routing
- `.opencode/agent/` — all 22 agent frontmatter files updated for opencode-go prefix
- `.opencode/mission.json` — mission state machine driven by task tier system
- `MagnumOpus/reference/lcn_write.py` — SQLite v0 entity write module (spec)
- `.opencode/tools/lcn_write.py` — active copy after MEMORY-V0 move
- `Brain/lcn_jvp/` — forward-mode JVP micro-library (dual.py, estimators.py, probes.py)
- `Brain/lcn_brain/` — LCN research project (blocked on JAX)
- `Brain/lcn_brain/tests/test_burgers.py` — Burgers' equation 4-arm test
- `.opencode/state/decisions.json` — machine-readable decision log
- `.opencode/project-state.md` — BLOCKED ≠ DEAD safety rule added
- `.opencode/context/` — compression-immune context files (this directory)

## Constraints

- **Decisions are never deleted** — if revisited, append a new entry with updated status (Superseded by <ID>)
- **Sections are compression-immune** — this file is never touched by the compress tool or auto-compaction
- **Dual-write rule**: when a decision changes code, update both the code AND this log in the same commit
- **Global config sync**: decisions affecting agent prompts or plugin config must be reflected in both `~/.config/opencode/` and `.opencode/`

## Notes

- The `decisions.json` file in `.opencode/state/` is the machine-readable counterpart; this markdown file is human-readable with rationale
- All agent prompts reference this file at session start (via orchestrator SESSION START Phase 2 step 13)
- The 5 entity types (Decision, Rejection, Error, Pattern, Convention) in lcn_write.py mirror the categories tracked here
- For model-specific decisions (provider selection, model cascade), see `.opencode/state/decisions.json` or `.opencode/user-model.json`
