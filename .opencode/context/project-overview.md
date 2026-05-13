# Project Overview — JANUS

**Purpose**: Architecture overview, tech stack, directory layout, key conventions, and design decisions for the JANUS multi-agent system. Agents read this at session start to orient before touching any code.

## Key Decisions

- **22-agent roster with opencode-go/ provider prefix** — all agents use opencode-go as provider; models range from deepseek-v4-pro (orchestrator) to minimax-m2.5 (light agents). Rationale: unified dispatch routing; avoids provider-specific flakiness (Cerebras Qwen stalls, Perplexity Sonar unresponsive). Alternatives considered: mixed providers per agent, single model for all, OpenAI provider chain.
- **SQLite v0 for memory** — deliberately simple entity store (5 types: Decision, Rejection, Error, Pattern, Convention); swappable to neural when LCN Brain passes Phase C validation. Alternatives considered: wait for LCN Brain, JSON files (concurrent corruption risk), vector DB (overkill).
- **Forward-mode JVP for LCN** — uses lcn_jvp micro-library instead of jax.grad; avoids JAX autodiff limitations on plastic weights that depend on the forward trajectory. Alternatives considered: jax.grad with checkpointing, jax.vjp, PyTorch functorch, hand-rolled adjoint method.
- **Burgers' equation as testbed** — standard PDE benchmark for neural-PDE hybrid architectures; computationally tractable while testing nonlinear capabilities. Alternatives considered: Navier-Stokes (too expensive), Kuramoto-Sivashinsky (too chaotic), simple ODEs (too easy).
- **Task tier classification** — prevents wasted dispatches; READ/TINY skip the full agent pipeline. Tiers: READ, TINY, STANDARD, COMPLEX, PROJECT, RESEARCH, META, CREATIVE.
- **Compression-immune context files** — `.opencode/context/*.md` survive context pruning; read by all agents at session start. These files (project-overview.md, decisions.md, conventions.md, feature-*.md) are the project's cross-session memory.
- **Dual-write state bridge** — todowrite + tasks.py; error escalation + error_logger.py; session state always dual-written for persistence across sessions.
- **Keep Brain/ as separate research project** — not deleted despite cleanup audit. BLOCKED ≠ DEAD. The LCN architecture is the long-term vision; compatibility with entity schema must be maintained.
- **V2 compaction format** — `tail_turns: 2`, `preserve_recent_tokens: 50000` instead of v1 `keep_first` / `max_context_window_tokens`. Auto-compaction at >80% context usage.

## Architecture

JANUS is a 22-agent multi-agent coding system built on OpenCode CLI (v1.14.31), wrapped in a PySide6 desktop GUI. The orchestrator (opencode-go/deepseek-v4-pro) decomposes user requests, delegates to sub-agents via `task` tool dispatches, and synthesizes outputs. Each sub-agent receives a self-contained handoff prompt and operates with zero shared session context.

The system has three distinct subsystems:

1. **GUI Layer** (`main.py` -> `ui/` + `core/`) — PySide6 QMainWindow with QTextBrowser chat interface, QThread background worker for opencode.cmd subprocess, sidebar with Files/Sessions/Memory/Mission tabs, toolbar with agent/model selection
2. **Agent System** (`.opencode/agent/*.md`) — 22 agent prompt files, each with frontmatter specifying model, role, permissions. The orchestrator reads these, routes work, and manages the mission state machine
3. **Research Subsystem** (`Brain/`) — LCN (Language Cognition Network) research project, blocked on JAX. Separate from GUI and agent system. Uses Burgers' equation as PDE testbed with forward-mode JVP (no jax.grad)

### Task Tier System

| Tier | Criteria | Flow |
|------|----------|------|
| READ | Question, no file changes | Answer directly |
| TINY | Single file, <30 lines | @nano-coder only |
| STANDARD | Multi-file, known patterns | Plan -> test-writer -> coder -> quality gate -> reviewer -> security-auditor -> documenter |
| COMPLEX | New architecture, >5 files | explorer + architect -> STANDARD flow |
| PROJECT | Multi-session mission | mission.json state machine, per-feature lifecycle |
| RESEARCH | External knowledge needed | researcher + explorer synthesize |
| META | System improvement | scientist agents + scientific-method |
| CREATIVE | Narrative/character writing | @prompt-writer dispatched |

### Agent Roster Summary

| Agent | Model | Role |
|-------|-------|------|
| orchestrator (PRIMARY) | opencode-go/deepseek-v4-pro | Task decomposition, routing, synthesis. NEVER writes code |
| coder | opencode-go/deepseek-v4-flash | Writes/edits/creates code files |
| nano-coder | opencode-go/deepseek-v4-flash | Read-only pre-flight, low-token tasks |
| explorer | opencode-go/deepseek-v4-flash | Codebase scanning, context gathering |
| architect | opencode-go/deepseek-v4-flash | Design proposals, tradeoff analysis |
| reviewer | opencode-go/deepseek-v4-flash | Code review + plan design review |
| test-writer | opencode-go/deepseek-v4-flash | TDD — writes failing tests first |
| security-auditor | opencode-go/deepseek-v4-flash | Post-merge: injection, auth, secrets |
| documenter | opencode-go/minimax-m2.5 | Post-commit docstring sync |
| researcher | opencode-go/deepseek-v4-flash | Web research, external specs |
| prompt-writer | opencode-go/mimo-v2.5-pro | PList/Ali:Chat, creative writing |
| 5 scientist agents | Various | META research (model, prompt, system, failure, efficiency) |
| 4 light agents | Various | Context optimization, dependency scanning, lessons, onboarding |

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| GUI Framework | PySide6 (Qt 6) | 6.11.0 |
| Python Runtime | CPython | 3.14.3 |
| CLI Backend | opencode.cmd (global npm install) | 1.14.31 |
| Plugin | @opencode-ai/plugin (global ~/.config/opencode/) | 1.14.31 |
| Markdown Rendering | markdown | 3.10.2 |
| Linting | ruff | latest |
| Testing | pytest | 9.x |
| Memory (GUI) | SQLite via AgentMemory class | stdlib |
| Memory (LCN) | SQLite via lcn_write.py | stdlib, .lcn/lcn.sqlite |
| Neural (Brain) | JAX + Flax | BLOCKED — needs install |
| ORM | None (raw SQLite) | 0 ORM deps |

## Directory Layout

```
OpenCode/
├── main.py                    # Entry point — QApplication, style.qss, MainWindow
├── start.bat                  # Windows launcher (pythonw.exe, no console)
├── conftest.py                # Root-level pytest config
├── assets/
│   └── style.qss              # Dark-theme Qt stylesheet (120 lines, VS Code-inspired)
├── core/
│   ├── opencode_service.py    # Static helpers: opencode.cmd CLI wrappers (124 lines, fragile)
│   ├── worker.py              # QThread: opencode.cmd run --format json (191 lines, fragile)
│   ├── memory.py              # SQLite AgentMemory (agent_memory.db, 95 lines, stable)
│   ├── hooks.py               # HookRunner — PreToolUse, PostToolUse, Stop events
│   ├── drift_guard.py         # Config validation on app startup (77 lines, stable)
│   ├── service_worker.py      # Generic QThread for blocking calls (24 lines, stable)
│   └── AGENTS.md              # Module-specific patterns
├── ui/
│   ├── main_window.py         # MainWindow (~1010 lines) — toolbar, sidebar, chat
│   ├── dialogs.py             # ProvidersDialog, StatsDialog, McpDialog (222 lines)
│   └── AGENTS.md              # Module-specific patterns
├── utils/
│   ├── __init__.py
│   └── helpers.py             # format_timestamp() — relative time strings (84 lines)
├── tests/                     # pytest test suite (currently Brain/LCN tests)
├── .opencode/
│   ├── opencode.json          # OpenCode CLI config
│   ├── agent/                 # 22 agent definition files with frontmatter
│   ├── context/               # Compression-immune knowledge files (this directory)
│   ├── tools/                 # CLI tool scripts (scheduler, genesis, error_logger, etc.)
│   ├── rules/                 # Categorized instruction files (always-*, auto-*, glob-*)
│   ├── recipes/               # Jinja2 task templates (api-builder, refactor-pattern, test-generator)
│   ├── commands/              # Slash command definitions
│   ├── protocols/             # Mission, healing, blackboard protocol specs
│   ├── features/              # Feature summary files per mission
│   ├── state/                 # Persistent state (mission.json, tasks.json, checklist.json, decisions.json)
│   ├── cogito/                # Agent state framework (mission.py, tasks.py, checklist.py, identity.md)
│   ├── hooks.json             # Hook rules configuration
│   ├── mission.json           # Active mission state machine
│   ├── error-log.jsonl        # Structured error log
│   ├── project-state.md       # MCP, skills, systems added, plugin management
│   └── project-map.json       # Onboarder-generated file index
├── Brain/
│   └── lcn_brain/             # LCN research — BLOCKED on JAX install
│       ├── lcn/               # Core: encoder, ssf, clock, rcd, plastic, readout, types, train
│       ├── lcn_jvp/           # Forward-mode JVP: dual, estimators, probes, projection, sweep
│       ├── lcn/testbed/       # PDE benchmarks: burgers.py, ks.py, encodings.py, baselines.py
│       └── tests/             # 8 test files (all blocked — no JAX)
└── MagnumOpus/                # Session files, reference impls, backlog, protocol specs
    └── reference/             # lcn_write.py, capability_assessor.py (spec code)
```

## Agents and Skills

**6 skills** loaded on demand (never at session start):

| Skill | When Used | What It Provides |
|-------|-----------|-----------------|
| mission-protocol | PROJECT/COMPLEX task start | Mission state machine, feature lifecycle, token budget rules |
| healing-protocol | Any error, reviewer FAIL | Escalation ladder, fallback table, circuit breaker |
| blackboard-protocol | Multi-agent parallel dispatch | Shared state schema, agent read/write rules |
| quality-gate | After @coder completes | 4-phase gate: self-review, QA+review, verify, security scan |
| parallel-universe | High-stakes mission features | 3-branch parallel codegen, scoring, merge |
| mission-completion | PROJECT mission complete | Quality metrics, memory write, lessons, security audit |

**3 MCP tools** available: context7 (library docs), gh_grep (GitHub code search), exa (web search).

## Files Touched

- `main.py` — Entry point for the PySide6 GUI application
- `start.bat` — Windows launcher (pythonw.exe, no console window)
- `core/worker.py` — QThread worker running opencode.cmd run --format json with message queue
- `core/opencode_service.py` — Static helpers wrapping opencode.cmd CLI calls
- `core/memory.py` — SQLite-backed AgentMemory (agent_memory.db)
- `core/hooks.py` — HookRunner for PreToolUse, PostToolUse, Stop events
- `core/drift_guard.py` — Config validation on app startup
- `core/service_worker.py` — Generic QThread wrapper for blocking calls
- `ui/main_window.py` — MainWindow: toolbar, sidebar (Files/Sessions/Memory/Mission tabs), chat area
- `ui/dialogs.py` — ProvidersDialog, StatsDialog, McpDialog
- `utils/helpers.py` — format_timestamp() — relative time strings
- `assets/style.qss` — Dark-theme Qt stylesheet (VS Code-inspired)
- `.opencode/opencode.json` — OpenCode CLI configuration
- `.opencode/agent/` — 22 agent definition files with frontmatter (model, role, permissions)
- `.opencode/tools/` — CLI tool scripts (scheduler, genesis, error_logger, etc.)
- `.opencode/mission.json` — Active mission state machine
- `.opencode/protocols/` — Mission, healing, blackboard protocol specs
- `.opencode/error-log.jsonl` — Structured error log
- `.opencode/hooks.json` — Hook rules configuration
- `.opencode/rules/` — Categorized instruction files (always-*, auto-*, glob-*)
- `.opencode/recipes/` — Jinja2 task templates (api-builder, refactor-pattern, test-generator)
- `.opencode/commands/` — Slash command definitions
- `.opencode/cogito/` — Agent state framework (mission.py, tasks.py, checklist.py)
- `.opencode/features/` — Feature summary files per mission
- `Brain/lcn_brain/` — LCN research project (blocked on JAX, 56 tracked files, 49 tests)
- `MagnumOpus/reference/` — lcn_write.py, capability_assessor.py (spec code, not yet moved)

## Constraints

- **Windows-first**: all subprocess calls use `shell=True` (required for .cmd files on Windows); introduces shell injection risk if arguments contain user-controlled characters. `stop()` in worker.py must use `taskkill /F /T /PID` — never `.terminate()` alone, which only kills cmd.exe, not the child opencode process.
- **QThread signals only**: never touch UI widgets from a worker thread — always emit signals. PySide6 will crash or deadlock if UI is accessed off the main thread.
- **CRLF line endings**: files use CRLF; preserve when editing. The project runs on Windows exclusively.
- **No emojis**: unless user uses them first. This applies to code, comments, error messages, and logs.
- **No new dependencies without review**: all core tools use stdlib only (sqlite3, json, pathlib). The only third-party deps are PySide6 and markdown.
- **BLOCKED ≠ DEAD**: code marked BLOCKED in PIPELINE.md or JANUS-STATE.md must NOT be deleted. Check these files before any bulk cleanup.
- **Global config priority**: `~/.config/opencode/` takes precedence over `.opencode/` for plugin version and agent definitions. Always sync both.
- **30s timeout on CLI commands**: all opencode.cmd subprocess calls have a 30-second timeout via process.communicate(timeout=30). Model listing or heavy DB queries may timeout on slower systems.
- **Path length limit**: Windows ~260 char path limit applies. Use `C:\Users\lukas\AppData\Local\Temp\opencode` for temporary work that might exceed this.
- **Dual-write persistence**: every state change (errors, tasks, checklist items, mission transitions) must be written both natively (todowrite, signals) and persistently (tasks.py, error_logger.py, mission.py).

## Notes

- The `.opencode/` directory is the project's control plane — config, agents, tools, context, state, protocols
- The Brain/ directory is a separate research project using JAX/Flax, not wired into the GUI or agent system
- Two plugin configs exist: global (`~/.config/opencode/package.json`, runtime priority) and local (`.opencode/package.json`, reference only). Always update global first.
- `opencode.cmd --version` reports the CLI binary version, which may differ from the plugin version in `package.json`
- The compaction config uses v2 format: `tail_turns`, `preserve_recent_tokens` (not v1 `keep_first`, `max_context_window_tokens`)
- The sidebar tab widget is `self.sidebar_tabs` — NOT `self.tab_widget` in main_window.py
- Model/agent dropdowns store names in `Qt.UserRole` on each QComboBox item
- The `send_input()` method on OpenCodeWorker accepts `text, model, agent, file, plan_mode, slash_command, fork, title` parameters
- Lazy imports are used for heavy modules (markdown, AgentMemory) — always import inside methods, not at module top
- All agent prompts reference `.opencode/context/*.md` at session start — keep these files up to date
- For META research, dispatch 1-2 scientist agents weekly on a rotation: model -> prompt -> system -> failure -> efficiency
