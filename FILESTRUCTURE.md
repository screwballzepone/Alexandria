# OpenCode Project — Complete File Map

> Auto-generated 2026-04-29. Maps every file in the project workspace and OpenCode runtime footprint.
> File counts: ~500+ workspace files, ~200+ runtime files (snapshots, session diffs, tool outputs)

---

## WORKSPACE ROOT: `C:\Users\lukas\OneDrive\Documentos\OpenCode\`

```
OpenCode/                              # PROJECT ROOT (git repo)
│
├── AGENTS.md                          # docs         Project context injected into every session
├── CONTEXT.md                         # docs         This file — complete file map
├── FILESTRUCTURE.md                   # (alias)      Same as above
│
├── main.py                            # source       QApplication entry point (~300 lines)
├── start.bat                          # script       Windows launcher (pythonw.exe, no console)
├── pyproject.toml                     # config       Python project metadata
├── requirements-dev.txt               # config       Dev dependencies (ruff, etc.)
├── .gitignore                         # config       Git ignore rules
├── .gitattributes                     # config       Git line-ending rules
│
├── test_ollama_tools.py               # test         Ollama tool-calling smoke test (~100 lines)
├── test-agent.txt                     # artifact     Manual test artifact (multi-agent verification)
├── nova_profile.plist                 # artifact     Test PList character profile output
│
├── run_attempt_10.ps1                 # script       PowerShell run script (batch attempt)
├── run_attempt_11.ps1                 # script       PowerShell run script (batch attempt)
│
├── core/                              # source       Python backend package
│   ├── __init__.py                    # source       Package init (empty)
│   ├── worker.py                      # source       QThread that runs opencode.cmd (~400 lines)
│   ├── opencode_service.py            # source       Static helpers: get models/agents/sessions (~200 lines)
│   ├── memory.py                      # source       SQLite-backed long-term memory (AgentMemory) (~150 lines)
│   ├── drift_guard.py                 # source       Config drift detection on startup (~150 lines)
│   └── service_worker.py             # source       Service worker thread (~200 lines)
│
├── ui/                                # source       PySide6 GUI package
│   ├── __init__.py                    # source       Package init (empty)
│   ├── main_window.py                 # source       MainWindow: toolbar, sidebar, chat area (~600 lines)
│   └── dialogs.py                     # source       ProvidersDialog, StatsDialog, McpDialog (~200 lines)
│
├── utils/                             # source       Utility package
│   ├── __init__.py                    # source       Package init (empty)
│   └── helpers.py                     # source       format_timestamp() — "X minutes ago" strings (~50 lines)
│
├── assets/                            # config       Static assets
│   └── style.qss                      # config       VS Code-inspired dark theme stylesheet (~500 lines)
│
├── tests/                             # test         Test suite
│   ├── test_mission_status.py         # test         Mission status tests (~100 lines)
│   ├── test_lcn_write.py              # test         LCN write tests (~80 lines)
│   ├── test_lcn_read.py               # test         LCN read tests (~80 lines)
│   ├── test_consult.py                # test         Consult tool tests (~80 lines)
│   └── test_capability_assessor.py    # test         Capability assessor tests (~80 lines)
│
├── .opencode/                         # config       OpenCode project-local configuration
│   ├── opencode.json                  # config       Model/provider defaults, agent config (~100 lines)
│   ├── package.json                   # config       @opencode-ai/plugin v1.4.6 dependency
│   ├── package-lock.json              # config       NPM lockfile (50KB+)
│   ├── project-map.json               # reference    Existing project structure map (~200 lines)
│   ├── user-model.json                # config       User model state
│   ├── schedule.json                  # config       Agent schedule configuration
│   ├── mission.json                   # config       Mission state machine (PROJECT-tier tasks)
│   ├── blackboard.json                # config       Shared agent communication board
│   ├── resume.json                    # config       Session handoff packet
│   │
│   ├── agent/                         # agent-def    Agent prompt definitions (markdown with frontmatter)
│   │   ├── orchestrator.md            # agent-def    PRIMARY — task decomposition, routing (~400+ lines)
│   │   ├── coder.md                   # agent-def    Code generation and implementation
│   │   ├── nano-coder.md              # agent-def    Read-only minimal assistant
│   │   ├── explorer.md                # agent-def    File scanning, context gathering
│   │   ├── architect.md               # agent-def    Complex design decisions (5+ files)
│   │   ├── reviewer.md                # agent-def    Code/plan review, quality gatekeeper
│   │   ├── prompt-writer.md           # agent-def    PList/Ali:Chat character profiles
│   │   ├── test-writer.md             # agent-def    TDD test writer
│   │   ├── security-auditor.md        # agent-def    Post-merge security scanner
│   │   ├── documenter.md              # agent-def    Post-commit doc sync
│   │   ├── dependency-scout.md        # agent-def    Weekly dependency scanner
│   │   ├── lessons.md                 # agent-def    Post-mission retrospective
│   │   ├── meta-agent.md              # agent-def    Post-mission prompt editor
│   │   ├── onboarder.md               # agent-def    One-time codebase explorer
│   │   ├── researcher.md              # agent-def    Web research (Perplexity Sonar Reasoning Pro)
│   │   └── memory-writer.md           # agent-def    Post-mission LCN outcome writer
│   │
│   ├── evals/                         # config       Evaluation configurations
│   │   ├── eval-01-error-handling.json
│   │   ├── eval-02-refactor-loop.json
│   │   ├── eval-03-write-test.json
│   │   ├── eval-04-no-secrets.json
│   │   └── eval-05-conventional-commit.json
│   │
│   ├── features/                      # session-log  Feature summaries (per-feature .md files)
│   │
│   ├── protocols/                     # protocol-spec Mission/communication protocol specs
│   │   ├── mission-protocol.md        # protocol-spec Mission state machine protocol
│   │   └── blackboard-protocol.md     # protocol-spec Blackboard communication protocol
│   │
│   ├── meta-agent/                    # docs         Meta-agent documentation
│   │   └── README.md
│   │
│   └── tools/                         # tool-script  Custom Python tools (18 scripts)
│       ├── user_model.py              # tool-script  User model management
│       ├── scheduler.py               # tool-script  Agent scheduling
│       ├── quality_metrics.py         # tool-script  Quality metric collection
│       ├── quality_gate.py            # tool-script  Quality gate enforcement
│       ├── project_map.py             # tool-script  Project structure mapping
│       ├── parse_reviewer.py          # tool-script  Reviewer JSON output parser
│       ├── parallel_universe.py       # tool-script  Parallel implementation runner
│       ├── mission_status.py          # tool-script  Mission state queries
│       ├── lcn_write.py               # tool-script  LCN graph write operations
│       ├── lcn_read.py                # tool-script  LCN graph read operations (spec, no code)
│       ├── lcn_client.py              # tool-script  LCN client interface
│       ├── issue_monitor.py           # tool-script  GitHub issue monitoring
│       ├── git_ops.py                 # tool-script  Git operations helper
│       ├── genesis.py                 # tool-script  Project genesis/bootstrap
│       ├── eval_runner.py             # tool-script  Evaluation runner
│       ├── consult.py                 # tool-script  Consultation tool
│       ├── ci_monitor.py              # tool-script  CI pipeline monitoring
│       └── capability_assessor.py     # tool-script  Agent capability assessment
│
├── POTATO/                            # reference    Synced npm install of opencode-ai
│   └── npm/                           # reference    Contains opencode.cmd (v1.14.29), node_modules
│       ├── package.json               # config       opencode-ai package metadata
│       └── package-lock.json          # config       NPM lockfile (100KB+)
│
├── MagnumOpus/                        # session-log  Session archives, references, reports
│   ├── session-state.md               # session-log  Current session state tracker
│   ├── BACKLOG.md                     # reference    Task backlog (batch tracking)
│   ├── OPENCODE-CONFIG-MAP.md         # reference    Config layout documentation
│   ├── MASTER-PLAN.md                 # reference    Project master plan
│   ├── coworker-report-*.md           # session-log  Session reports (25+ files)
│   │
│   ├── scripts/                       # script       Utility scripts
│   │   ├── seed_lcn.py                # script       LCN data seeding (~100 lines)
│   │   └── reset_mission.py           # script       Mission state reset (~50 lines)
│   │
│   └── reference/                     # reference    Reference implementations
│       ├── lcn_write.py               # reference    LCN write-side implementation (~150 lines)
│       └── capability_assessor.py     # reference    Capability assessor reference (~150 lines)
│
├── Brain/                             # reference    Neuromorphic LCN (separate project)
│   ├── LCN Brain — Bootstrap Blueprint 42aa04d1cf8e492381970463b58d586b.md  # reference  Blueprint (~300 lines)
│   │
│   └── lcn_brain/                     # source       JAX/Flax spiking neural ODE (~2,900 lines)
│       ├── README.md                  # docs         LCN brain readme
│       ├── CONTEXT.md                 # docs         LCN architecture docs (~200 lines)
│       ├── pyproject.toml             # config       Python project config
│       ├── lcn/                       # source       Core LCN library
│       │   ├── types.py               # source       Type definitions
│       │   ├── constants.py           # source       Physical/math constants
│       │   ├── clock.py               # source       Simulation clock
│       │   ├── encoder.py             # source       Spike encoding
│       │   ├── plastic.py             # source       Plasticity rules
│       │   ├── rcd.py                 # source       Readout layer
│       │   ├── readout.py             # source       Readout interface
│       │   ├── ssf.py                 # source       State-space function
│       │   ├── diagnostics.py         # source       Diagnostic tools
│       │   └── train.py               # source       Training loop
│       ├── tests/                     # test         LCN test suite (8 test files)
│       │   └── test_*.py              # test         0/49 pass (missing lcn_jvp dependency)
│       └── lcn_brain.egg-info/        # config       Package metadata
│
└── opencode-repo/                     # reference    FULL OpenCode monorepo clone (~1000+ files)
    │                                                 (source reference, possibly stale)
    ├── turbo.json                     # config       Turborepo config
    ├── tsconfig*.json                 # config       TypeScript configs
    ├── package.json                   # config       Monorepo root package
    ├── bunfig.toml                    # config       Bun configuration
    ├── .github/workflows/*.yml        # config       CI/CD pipeline definitions (40+)
    ├── .github/ISSUE_TEMPLATE/*.yml   # config       Bug/feature templates
    ├── i18n/*.json                    # config       Internationalization (20+ languages)
    ├── themes/*.json                  # config       UI themes
    ├── sdks/vscode/*.ts               # source       VSCode extension
    ├── packages/                      # source       Core packages
    │   ├── core/src/*.ts              # source       Core logic
    │   ├── web/src/*.ts               # source       Web interface
    │   ├── ui/src/*.ts                # source       UI components
    │   ├── cli/src/*.ts               # source       CLI implementation
    │   ├── sdk/src/*.ts               # source       SDK package
    │   └── ...                        # source       (other packages)
    └── src/tool/*.txt                 # reference    Tool system prompts
```

---

## OPencode RUNTIME FOOTPRINT (outside workspace)

### Global binary install
```
C:\Users\lukas\AppData\Roaming\npm\
├── opencode.cmd                      # script       Global npm bin wrapper (v1.14.29)
└── node_modules\opencode-ai\        # binary       Compiled OpenCode binary + deps
```

### User data (`~/.local/share/opencode/`) — EXISTS
```
C:\Users\lukas\.local\share\opencode\
├── snapshot/                          # data         File change snapshots (100s of files, git-style)
│   └── d5e2c1f6.../                  # data         Per-commit snapshot directories
│       └── *.patch                   # data         Individual file patches
├── storage/                           # data         Session storage
│   ├── session_diff/                  # data         Per-session diff JSONs (100+ sessions)
│   │   └── ses_*.json                # data         Session change records
│   └── migration/                     # data         Schema migrations
└── tool-output/                       # cache        Cached tool execution outputs
    └── tool_*                         # cache        Individual tool result files
```

### Global config directories — BOTH EXIST

```
C:\Users\lukas\.opencode\              ✅ EXISTS      GLOBAL user config (binary reads this)
│
├── opencode.json                      # config       Global provider configs (anthropic, deepseek, openrouter, google)
├── opencode.json.bak-b27              # backup       Previous config backup (624 bytes)
├── package.json                       # config       npm plugin dependency
├── package-lock.json                  # config       npm lockfile
├── .gitignore                         # config       Git ignore rules
│
├── agents/                            # agent-def    Global agent definitions (8 agents — OUTDATED)
│   ├── orchestrator.md                # agent-def    model: google/gemini-2.5-flash (OLD, 37 lines)
│   ├── coder.md                       # agent-def    model: openrouter/minimax/minimax-m2.5 (OLD, 23 lines)
│   ├── explorer.md                    # agent-def    Global explorer (655 bytes)
│   ├── architect.md                   # agent-def    Global architect (887 bytes)
│   ├── reviewer.md                    # agent-def    Global reviewer (880 bytes)
│   ├── prompt-writer.md               # agent-def    Global prompt-writer (805 bytes)
│   ├── nano-coder.md                  # agent-def    Global nano-coder (1071 bytes)
│   └── context-optimizer.md           # agent-def    Global context-optimizer (1094 bytes, NOT in project)
│
└── node_modules/                      # deps         npm plugin dependencies (@opencode-ai/plugin, @opencode-ai/sdk)

C:\Users\lukas\.config\opencode\       ✅ EXISTS      GLOBAL plugin directory (npm packages only)
│
├── package.json                       # config       npm plugin dependency
├── package-lock.json                  # config       npm lockfile
├── .gitignore                         # config       Git ignore rules
│
└── node_modules/                      # deps         npm plugin dependencies (NOT a user config dir)
    ├── @opencode-ai/plugin/           # plugin       OpenCode plugin SDK
    ├── @opencode-ai/sdk/              # sdk          OpenCode SDK package
    └── ...                            # deps         (zod, cross-spawn, etc.)
```

### Note on agent_memory.db
The Python `core/memory.py` stores `agent_memory.db` at `~/.local/share/opencode/`.
The binary's internal session DB (`opencode.db`) is bundled inside the binary, not exposed as a standalone SQLite file.
Both are distinct from the project-local `.opencode/*.json` configs.

---

## FILE COUNTS BY CATEGORY

| Category        | Count | Description |
|-----------------|-------|-------------|
| source          | ~45   | Python/TypeScript code (GUI, tools, LCN, VSCode ext) |
| config          | ~80   | JSON/YAML/TOML/TSS configs across all scopes |
| agent-def       | 15    | Agent prompt markdown files (`.opencode/agent/`) |
| tool-script     | 18    | Custom Python tools (`.opencode/tools/`) |
| test            | ~15   | Python test files |
| docs            | ~5    | README, CONTEXT, AGENTS files |
| session-log     | ~30   | Session reports, feature summaries |
| reference       | ~10   | Reference implementations, blueprints, config maps |
| protocol-spec   | 2     | Mission protocol, blackboard protocol |
| script          | 5     | Batch/PowerShell run scripts |
| artifact        | 2     | Test outputs (plist, txt) |
| data            | ~250  | Runtime data (snapshots, session diffs, tool outputs) |
| cache           | ~40   | Cached tool outputs |

---

## KEY DATA FLOW

```
User (GUI input)
  │
  ▼
main_window.py ──► core/worker.py (QThread)
                      │
                      ▼
                 opencode.cmd run --format json
                      │
                      ▼
                 OpenCode Binary (v1.14.29)
                      │
                      ├──► Reads .opencode/opencode.json (model, provider configs)
                      ├──► Reads .opencode/agent/*.md (agent definitions)
                      ├──► Reads .opencode/tools/*.py (custom tools)
                      ├──► Writes ~/.local/share/opencode/snapshot/ (file tracking)
                      └──► Writes ~/.local/share/opencode/storage/ (session state)
                      │
                      ▼
                 JSON output stream (stdout)
                      │
                      ▼
core/worker.py parses JSON ──► signals ──► main_window.py displays in QTextBrowser
```

### Memory flow
```
core/memory.py (AgentMemory)
  │
  ▼
~/.local/share/opencode/agent_memory.db (SQLite)
  │
  ├── project_memory table: (workspace_path, key, value, tags, time_updated)
  └── Used by: main_window.py Memory tab, .opencode/tools/lcn_write.py
```

### LCN flow (dual-track)
```
SQLite LCN (active):          Neuromorphic LCN (stalled):
.opencode/tools/lcn_write.py  Brain/lcn_brain/
.opencode/tools/lcn_read.py   JAX/Flax spiking neural ODE
MagnumOpus/reference/         Missing lcn_jvp dependency
  lcn_write.py                0/49 tests pass
```

---

## CONFIG LAYER PRECEDENCE (binary reads ALL of these)

```
Priority (highest to lowest):
1. CLI flags (--model, --agent, --provider)
2. Project-local .opencode/opencode.json          ← workspace root
3. Project-local .opencode/agent/*.md             ← 15 agents (comprehensive, V4 models)
4. Global ~/.opencode/opencode.json               ← user config (providers only, no model default)
5. Global ~/.opencode/agents/*.md                 ← 8 agents (OUTDATED stubs, old models)
6. Global ~/.config/opencode/                     ← plugin directory (npm only, no config)
7. Binary built-in defaults                       ← hardcoded fallbacks
```

---

## GLOBAL → PROJECT SYNC STATUS

> ✅ **Synced 2026-04-29** — 16 project agents copied to `~/.opencode/agents/`, global `opencode.json` updated with all providers and model defaults.

| File | Global (`~/.opencode/`) | Project (`OpenCode/.opencode/`) | Status |
|------|------------------------|-------------------------------|--------|
| `opencode.json` | Full config: ALL providers, model, small_model, compaction, snapshot | Full config + project-specific commands/instructions | **SYNCED** |
| `orchestrator.md` | 400+ lines, STEP 1-5 workflow, deepseek-v4-flash | Same | **SYNCED** |
| `coder.md` | ~80 lines, deepseek-v4-flash | Same | **SYNCED** |
| `explorer.md` | ~50 lines, grok-4.20-beta | Same | **SYNCED** |
| `architect.md` | ~80 lines, cerebras/qwen-3-235b | Same | **SYNCED** |
| `reviewer.md` | ~70 lines, deepseek-v4-flash | Same | **SYNCED** |
| `prompt-writer.md` | ~60 lines, deepseek-v4-flash | Same | **SYNCED** |
| `nano-coder.md` | ~50 lines, deepseek-v4-flash | Same | **SYNCED** |
| `test-writer.md` | ✅ NOW IN GLOBAL | ✅ in project | **SYNCED** |
| `security-auditor.md` | ✅ NOW IN GLOBAL | ✅ in project | **SYNCED** |
| `documenter.md` | ✅ NOW IN GLOBAL | ✅ in project | **SYNCED** |
| `dependency-scout.md` | ✅ NOW IN GLOBAL | ✅ in project | **SYNCED** |
| `lessons.md` | ✅ NOW IN GLOBAL | ✅ in project | **SYNCED** |
| `onboarder.md` | ✅ NOW IN GLOBAL | ✅ in project | **SYNCED** |
| `meta-agent.md` | ✅ NOW IN GLOBAL | ✅ in project | **SYNCED** |
| `memory-writer.md` | ✅ NOW IN GLOBAL | ✅ in project | **SYNCED** |
| `researcher.md` | ✅ NOW IN GLOBAL | ✅ in project | **SYNCED** |
| `context-optimizer.md` | ✅ Preserved | ❌ NOT IN PROJECT | **GLOBAL-ONLY** |

**17 agents in `~/.opencode/agents/`** — 16 from project + 1 global-only (`context-optimizer`).
