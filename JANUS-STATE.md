# JANUS — Complete State (2026-05-01)

> **Purpose:** Full-system snapshot for JANUS planning and context.
> **Generated:** Session 2026-04-30 through 2026-05-01 | **Last commits:** b8e0e4c through f1359bf (cleanup audit)
> **Updated:** 2026-05-01 — post codebase health audit (Brain/ archived, plugin upgraded to 1.14.31)

---

## WHAT IS JANUS

JANUS is a 17-agent multi-agent coding system built on OpenCode CLI (v1.14.31), wrapped in a PySide6 desktop GUI (plugin 1.14.31, compaction v2 format). It decomposes tasks through a tiered classification system (READ→TINY→STANDARD→COMPLEX→PROJECT→RESEARCH), routes to specialized subagents, and executes multi-session missions with protocol-driven lifecycle management.

The name "JANUS" reflects its dual nature: a coding agent system AND a creative writing/prompt engineering workstation (via `@prompt-writer` for clank.world character profiles).

---

## ARCHITECTURE

### Layer 1: GUI (PySide6)

```
main.py → ui/main_window.py → core/worker.py (QThread) → opencode.cmd → JSON → QTextBrowser
```

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | ~30 | Entry point — QApplication, style.qss, MainWindow |
| `ui/main_window.py` | ~1137 | Toolbar, sidebar tabs (Files/Sessions/Memory/Plots/Mission), chat area |
| `ui/dialogs.py` | ~200 | ProvidersDialog, StatsDialog, McpDialog |
| `assets/style.qss` | ~300 | VS Code-inspired dark theme |

### Layer 2: Worker + Service (PySide6)

| File | Lines | Purpose |
|------|-------|---------|
| `core/worker.py` | ~250 | QThread wrapping opencode.cmd run, JSON parsing, signals |
| `core/opencode_service.py` | ~150 | Static helpers: get_models, get_agents, get_sessions, etc. |
| `core/memory.py` | ~100 | SQLite AgentMemory at ~/.local/share/opencode/agent_memory.db |
| `core/hooks.py` | ~238 | HookRunner — PreToolUse/PostToolUse/Stop deterministic enforcement |
| `core/drift_guard.py` | ~120 | Config validation |
| `core/service_worker.py` | ~50 | Generic QThread for background service calls |

Worker signals: `text_received`, `tool_started`, `tool_finished`, `error_received`, `process_finished`, `queue_empty`

Worker `send_input()` full signature: `send_input(text, model=None, agent=None, file=None, plan_mode=False, slash_command=False, fork=False, title=None)`

### Layer 3: Agent Roster (17 agents)

| # | Agent | Model | Role | Score | Issues |
|---|-------|-------|------|-------|--------|
| 1 | **orchestrator** (PRIMARY) | deepseek/deepseek-v4-flash | Decompose, route, synthesize. Never writes code | — | 397-line prompt, 6 skills |
| 2 | coder | deepseek/deepseek-v4-flash | All code writes | 8/10 | Needs structured report format |
| 3 | nano-coder | deepseek/deepseek-v4-flash | Tier 1 patches, pre-flight read-only | 9/10 | — |
| 4 | explorer | openrouter/x-ai/grok-4.20-beta | Context gathering, codebase scans | 9/10 | — |
| 5 | architect | openrouter/qwen/qwen3-235b-a22b-07-25 | Design review, adversarial design | 6→8/10 | Was Cerebras (stalls). Upgraded to OpenRouter |
| 6 | reviewer | deepseek/deepseek-v4-flash | Code/plan review, quality gatekeeper | 8→9/10 | Added JSON failure fallback |
| 7 | researcher | perplexity/sonar-reasoning-pro | Web research, external docs | 8/10 | Perplexity stalls intermittently |
| 8 | prompt-writer | deepseek/deepseek-v4-flash | PList/Ali:Chat, creative writing | 7/10 | — |
| 9 | test-writer | deepseek/deepseek-v4-flash | TDD: write failing tests before coder | 7→8/10 | Added edge case + fallback rules |
| 10 | security-auditor | deepseek/deepseek-v4-flash | Post-merge: injection/auth/secrets/CVE | 9/10 | — |
| 11 | documenter | deepseek/deepseek-v4-flash | Post-commit: docstring + docs sync | 7/10 | — |
| 12 | dependency-scout | deepseek/deepseek-v4-flash | Weekly: outdated packages + CVEs | 7/10 | — |
| 13 | lessons | deepseek/deepseek-v4-flash | Post-mission: retrospective to lessons.md | 7/10 | — |
| 14 | onboarder | deepseek/deepseek-v4-flash | One-time: project-map.json generator | 7/10 | — |
| 15 | meta-agent | deepseek/deepseek-v4-flash | Post-mission: agent prompt optimization | 7/10 | — |
| 16 | memory-writer | deepseek/deepseek-v4-flash | Post-mission: LCN memory writes | 7/10 | — |
| 17 | context-optimizer | (global-only) | Context deduplication | — | Not in project, global only |

All 16 project agents synced globally ↔ project (MD5 identical). All have `skill: true` in frontmatter.

### Layer 4: Skills (6 load-on-demand)

| Skill | Triggers on | Content |
|-------|-------------|---------|
| mission-protocol | COMPLEX/PROJECT tier | Mission state machine, feature lifecycle, token budget |
| healing-protocol | Errors, reviewer FAIL verdicts | Retry limits, escalation paths, degraded mode |
| blackboard-protocol | Multi-agent parallel work | JSON schema, agent r/w rules, stale entries, lifecycle |
| quality-gate | After @coder completes | Pre-check, reviewer verdict criteria, score tracking |
| parallel-universe | high_stakes: true | 3-branch parallel coding, scoring, merge, cleanup |
| mission-completion | PROJECT mission end | Quality metrics, memory write, lessons, meta-agent, security audit |

### Layer 5: Competitive Systems (2026-04-30 additions)

| System | File(s) | What it does |
|--------|---------|--------------|
| **Hooks** | `core/hooks.py` + `.opencode/hooks.json` | Deterministic rule enforcement. Events: PreToolUse, PostToolUse, Stop. Types: command (subprocess), prompt, agent. Regex tool-name matchers. |
| **Repo Map** | `.opencode/tools/repomap.py` (590 lines) | Zero-dep AST analysis. 3 modes: build (JSON), rank (PageRank), context (human-readable). Extracts classes, functions, signals, imports. |
| **Recipes** | `.opencode/tools/recipe_runner.py` + 3 recipes | Jinja2 task templates. 3 starters: api-builder, refactor-pattern, test-generator. |
| **Rules** | `.opencode/rules/` (4 files) | Categorized instructions: always-code-style, auto-agent-dispatch, glob-ui-pyside6, glob-core-worker |
| **Directory AGENTS.md** | `core/AGENTS.md`, `ui/AGENTS.md` | Per-module context with patterns, gotchas, unwired features |
| **Slash Commands** | `.opencode/commands/` (3 files) + `opencode.json` command section | File-based /review, /lint, /repomap + config-based /status, /plan, /dep-check, etc. |
| **Plan/Act Mode** | Orchestrator instruction | Read-only plan mode. Triggers: "plan mode", /plan. Deactivates: "execute" |
| **Error Logging** | `.opencode/tools/error_logger.py` (216 lines) | JSONL append-only log. 3 modes: log, query, stats. 7 error types. Crash-safe. |

### Layer 6: Plugins (4)

| Plugin | Type | Key features |
|--------|------|--------------|
| opencode-supermemory | npm | Cross-session persistent memory, preemptive compaction at 80% context, 9 project + 1 user memory stored |
| opencode-dcp | npm | Dynamic context pruning: dedup, error purge, smart compression |
| opencode-vibeguard | npm | Secret redaction (API keys, emails, IPs, UUIDs) before LLM calls, restoration before tool execution |
| shell-strategy | instruction file | Non-interactive shell patterns, BAD vs GOOD command table, banned commands |

### Layer 7: MCP Servers (3)

| Server | URL | Purpose | Auth |
|--------|-----|---------|------|
| context7 | https://mcp.context7.com/mcp | Library doc search | None |
| gh_grep | https://mcp.grep.app | GitHub code search | None |
| exa | https://mcp.exa.ai/mcp | Web search | OAuth (browser) + API key env var |

### Layer 8: AI Providers (7)

| Provider | Models | Reliability |
|----------|--------|-------------|
| DeepSeek | deepseek-v4-flash, v4-pro | Stable ✅ |
| Anthropic | (direct API) | Stable ✅ |
| OpenRouter | qwen-3-235b, grok-4.20-beta, sonar-* | Stable ✅ |
| Google | (gemini models) | Stable ✅ |
| Cerebras | qwen-3-235b, llama3.1-8b | **Flaky** ❌ — stalls |
| Ollama (local) | qwen2.5-coder:7b, deepseek-r1:8b, fast3b, llama3.2:1b/3b | Local ✅ (GPU-dependent) |
| Perplexity | sonar-pro, sonar-reasoning-pro | **Flaky** ❌ — stalls |

### Layer 9: Config

| File | Location | Purpose |
|------|----------|---------|
| `opencode.json` | `.opencode/` (project) | 7 providers, 3 MCP, 8 custom commands, permissions |
| `opencode.json` | `~/.opencode/` (global) | Same providers, global agent definitions |
| `hooks.json` | `.opencode/` | Default hook config (no-op placeholders) |
| `project-state.md` | `.opencode/` | MCP tools, skills, systems documentation |
| `lessons.md` | `.opencode/` | Session retrospectives |
| `missions.json` | `.opencode/` (optional) | Multi-session mission state machine |
| `blackboard.json` | `.opencode/` (runtime) | Agent-to-agent communication |

### Layer 10: Tools (18 scripts in .opencode/tools/)

| Tool | Purpose |
|------|---------|
| git_ops.py | Branch ops, clean check, commit with conventional commits |
| project_map.py | Project map generation + queries |
| user_model.py | User preference/persona management |
| lcn_client.py | LCN Brain connector (OFFLINE) |
| genesis.py | GitHub CLI integration check |
| quality_gate.py | Pre-review automated checks |
| repomap.py | AST-based repository map (NEW) |
| error_logger.py | JSONL error logging (NEW) |
| eval_runner.py | Agent evaluation runner |
| scheduler.py | Issue scheduling for automation |
| ci_monitor.py | CI status checker |
| issue_monitor.py | GitHub issue scanner |
| recipe_runner.py | Jinja2 recipe expander (NEW, in opencode/tools/) |
| + 5 more supporting scripts |

---

## CURRENT METRICS

| Metric | Value |
|--------|-------|
| Agents | 17 (1 primary + 16 subagents) |
| Skills | 6 load-on-demand |
| Plugins | 4 (3 npm + 1 instruction) |
| MCP servers | 3 |
| AI providers | 7 (2 flaky: Cerebras, Perplexity) |
| Local GPU models | 5 (qwen2.5-coder:7b, deepseek-r1:8b, fast3b, llama3.2:3b/1b) |
| Tools/scripts | 18 |
| OpenCode CLI | v1.14.31 (plugin 1.14.31, compaction v2) |
| Git commits | ~79 (conventional commit style) |
| Orchestrator prompt | 419 lines (down from 506 after skills extraction) |
| Total Python (project) | ~2,200 lines (GUI + worker + core modules + tools + tests) |
| Config lines (JSON) | ~168 (opencode.json) |

---

## KNOWN ISSUES & GAPS

### Severity: CRITICAL

| # | Issue | Impact | Status |
|---|-------|--------|--------|
| 1 | **Brain/LCN archived** — Brain/ directory deleted in codebase health audit. LCN integration deferred to future project. | LCN memory system offline | ARCHIVED — Brain/ removed, SQLite v0 LCN tools remain functional |
| 2 | **Perplexity config corruption** — apiKey field eaten by vibeguard. Fixed to env var reference but key not yet re-set by user | @researcher may fail silently | WAITING — user needs to set PERPLEXITY_API_KEY env var |

### Severity: HIGH

| # | Issue | Impact | Status |
|---|-------|--------|--------|
| 3 | **Cerebras provider stalls** — requests hang, no error returned. @architect moved to OpenRouter but Cerebras still configured | Can silently fail during agent dispatch | Mitigated — KNOWN PROVIDER ISSUES in orchestrator |
| 4 | **Perplexity provider stalls** — same pattern as Cerebras. Timeout added but provider-level hangs don't trigger it | @researcher may stall silently | Mitigated — orchestrator instructions + 10min timeout |
| 5 | **GUI features unwired** — plan_mode toggle, file attachment, slash command palette, fork button, session title input all exist in worker API but no UI widgets | GUI feels incomplete vs Cursor/Cline | ✅ DONE — all 7 wired in commit 0041b35 (3 stretch items remain) |
| 6 | **No subagent timeout** — opencode.cmd has no `--timeout` flag. Worker could add subprocess timeout but hasn't | Stalled agents waste context/tokens | Partially mitigated — orchestrator stall instructions |

### Severity: MEDIUM

| # | Issue | Impact | Status |
|---|-------|--------|--------|
| 7 | **Perplexity apiKey in config** — vibeguard permanently redacted the field. Set as `{env:PERPLEXITY_API_KEY}` reference, user needs to set env var | @researcher won't authenticate until fixed | WAITING |

### Severity: LOW

| # | Issue | Impact | Status |
|---|-------|--------|--------|
| 13 | Ollama model `qwen3.5:7b` still in config but not installed | Graceful failure on model selection | COSMETIC — can keep as optional |

---

## BRAIN / LCN — DEEP DIVE

### What is the Brain?

The Language Cognition Network (LCN) is JANUS's intended long-term memory system — a spiking neural network that:
- **Replaces attention** with forward-mode autodiff (JVP) rather than backpropagation
- **Uses three memory substrates** at different timescales: working (seconds), episodic (minutes), structural (learned)
- **Avoids surrogate gradient bias** — a known issue in spiking neural networks — by using Gaussian-CDF smoothing + forward-mode JVPs
- **Tests on Burgers' equation** — a PDE benchmark with known dynamics

### Current State

**Location:** `Brain/lcn_brain/` — separate from main project. 49 tests written, 0 passing (blocked on JAX/flax not installed).

The LCN client bridge is at `.opencode/tools/lcn_client.py`. When functional, the orchestrator's SESSION START step 4 would query LCN for relevant project memories, and the @memory-writer agent would write agent decisions back.

For full unblocking steps, see PIPELINE.md Phases A–C.

---

## CURRENT PRIORITIES

### Phase F: GUI stretch goals (3 remaining items)
- Mission tab live status (auto-refresh, blackboard log lines)
- Memory tab supermemory integration (search, delete)
- Repo map sidebar sub-tab (renders repomap.py tree)

### Phase E: Provider Resilience
- Perplexity key resolution (user to set env var)
- Provider stall mitigation already in orchestrator instructions

---

## FILE REFERENCE — KEY PATHS

```
C:\Users\lukas\OneDrive\Documentos\OpenCode\
├── main.py                                    # GUI entry point
├── start.bat                                  # Windows launcher
├── AGENTS.md                                  # Top-level context (always loaded)
├── core/
│   ├── worker.py                              # QThread + hooks integration
│   ├── hooks.py                               # HookRunner (NEW)
│   ├── memory.py                              # SQLite AgentMemory
│   └── AGENTS.md                              # Core module patterns
├── ui/
│   ├── main_window.py                         # MainWindow (1137 lines)
│   └── AGENTS.md                              # UI module patterns + unwired features
├── .opencode/
│   ├── opencode.json                          # 7 providers, 3 MCP, 8 commands
│   ├── hooks.json                             # Default hook config
│   ├── lessons.md                             # Session retrospectives
│   ├── project-state.md                       # Systems documentation
│   ├── error-log.jsonl                        # Error log (runtime)
│   ├── agent/                                 # 18 agent definitions
│   │   └── orchestrator.md                    # 419-line orchestrator prompt
│   ├── skills/                                # 6 skill files
│   ├── commands/                              # 3 slash command files
│   ├── recipes/                               # 3 Jinja2 templates
│   ├── rules/                                 # 4 rule files
│   └── tools/                                 # 23 Python scripts
├── tests/                                     # 5 test files (LCN tools, mission, capability)
├── Brain/
│   └── lcn_brain/                             # LCN implementation — 49 tests, blocked on JAX
├── MagnumOpus/                                # Cowork session files, PIPELINE.md, JANUS-STATE.md
└── conftest.py                                # Root pytest configuration
```

---

## HARDWARE

| Component | Spec | Notes |
|-----------|------|-------|
| CPU | AMD Ryzen 5 5600X (6-core) |  |
| RAM | 32 GB |  |
| GPU | NVIDIA RTX 3060 (12 GB VRAM) | Fits Q4_K_M models up to ~10-13B params |
| Storage | 4TB SSD + 1TB HDD |  |
| OS | Windows | PowerShell 5.1 |
| Python | 3.14.3 | venv at `venv/` |
| Ollama | GPU-enabled | 5 models installed, 2 wired into config |

---

## RECENT GIT HISTORY (last 10 commits)

```
f1359bf chore: phase 1-6 codebase health audit — remove 142K dead files, fix lint, update docs
b5512ec chore: cleanup old test artifacts
79a36b4 chore(deps): bump @opencode-ai/plugin 1.4.6 → 1.14.31, update compaction config, document global vs local plugin
b8e0e4c feat(ollama): add qwen2.5-coder:7b + deepseek-r1:8b local models
5e11339 feat: error logging system + agent prompt audit fixes
c6e6fcd fix: config, model upgrades, global sync
f72d21f feat: directory AGENTS.md, file-based slash commands, plan/act mode
a5b1f44 fix: add Perplexity timeout, stall handling, lessons tracking
3fa3269 feat: competitive analysis-driven systems — hooks, repomap, recipes, rules, skills
804dea2 fix(git_ops): reset index before explicit-path staging in commit()
```

---

**End of JANUS state.** Ready for Claude.
