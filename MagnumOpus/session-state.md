# Session State — MagnumOpus
**Last updated:** 2026-05-01
**Session:** Codebase health audit + cleanup + plugin upgrade

## Session Goals
- Diagnose and fix DeepSeek V4 "reasoning_content must be passed back" API error
- Upgrade opencode binary from 1.4.6 → 1.14.31 (20 minor releases)
- Phase 1-6 codebase health audit — cleaned 142K dead files, fixed lint, removed LCN diagnostics
- Sync local POTATO/npm install with global
- Audit MagnumOpus state, fix stale references, restore missing files
- Clean up opencode.json override (no longer needed after binary upgrade)

## Active Constraints
- Windows-first codebase (shell=True, .cmd files, subprocess.Popen patterns)
- PySide6 Qt framework — all UI must use Qt widgets
- opencode.cmd resolves to global install (C:\Users\lukas\AppData\Roaming\npm) — POTATO deleted in cleanup
- Agent configs live in .opencode/agent/*.md

## Current Agent Roster (actual from .opencode/agent/*.md frontmatter)
| Agent | Model | Status |
|-------|-------|--------|
| orchestrator | deepseek/deepseek-v4-flash | Active |
| coder | deepseek/deepseek-v4-flash | ✅ Restored 2026-04-27 |
| architect | cerebras/qwen-3-235b-a22b-instruct-2507 | Active |
| explorer | openrouter/x-ai/grok-4.20-beta | Active |
| reviewer | deepseek/deepseek-v4-flash | Active (migrated from chat) |
| prompt-writer | deepseek/deepseek-v4-flash | ✅ Restored 2026-04-27 |
| nano-coder | deepseek/deepseek-v4-flash | Active (migrated from chat) |
| test-writer | deepseek/deepseek-v4-flash | Active (migrated from chat) |
| security-auditor | deepseek/deepseek-v4-flash | Active (migrated from chat) |
| documenter | deepseek/deepseek-v4-flash | Active (migrated from chat) |
| dependency-scout | deepseek/deepseek-v4-flash | Active (migrated from chat) |
| lessons | deepseek/deepseek-v4-flash | Active (migrated from chat) |
| onboarder | deepseek/deepseek-v4-flash | Active (migrated from chat) |
| meta-agent | deepseek/deepseek-v4-flash | Active (migrated from chat) |

## Decisions Made
| # | Decision | Rationale | Reversible? |
|---|----------|-----------|------------|
| 1 | Upgrade opencode to 1.14.28 | v1.4.6 binary lacked V4 model catalog — caused reasoning_content drop | Yes (undo via npm) |
| 2 | Clean opencode.json override | 1.14.28 has V4 models with correct interleaved config built-in | N/A |
| 3 | Sync POTATO/npm to 1.14.28 | Consistency — both global and local now match | Yes |
| 4 | Keep deepseek-v4-flash as default model | V4 with thinking=auto, context 1M, working reasoning round-trip | Yes |

## Git History
- d5e2c1f — bugs, model upgrades, UI improvements
- 79a06ae — feat-mission-status: mission_status.py CLI tool + drift_guard.py
- ec4986b — AGENTS.md, pyproject.toml, all baseline files
- 782ad87 — message queue, busy state, new session, timestamps, nano-coder
- 0041b35 — plan mode, undo/redo, file attach, session fork, slash palette, model refresh
- 4f231f0 — restored truncated main_window.py, zero ruff violations
- (uncommitted) — opencode.json cleanup, POTATO sync, MagnumOpus refresh

## Known Issues / Gotchas
- main_window.py truncates when Claude Code does a full file rewrite. Use targeted Edit calls only.
- The sidebar tab widget is `self.sidebar_tabs` NOT `self.tab_widget`.
- opencode resolves to global install, NOT POTATO — AGENTS.md updated to reflect this.

## Pending Items
- Batch 23 attempt 7: smoke test with V4 (≥18/25 seams target)
- Future: git branch isolation per feature, GENESIS full bridge

## Context Anchors
- Project: PySide6 GUI wrapper for OpenCode CLI + JANUS autonomous dev platform
- 14-agent system (12 active, 2 missing): orchestrator(V4-flash), architect(qwen), explorer(grok), reviewer(deepseek-chat), + nano-coder, test-writer, security-auditor, documenter, dependency-scout, lessons, onboarder, meta-agent
- Binary: opencode-ai 1.14.28 (global C:\Users\lukas\AppData\Roaming\npm) — uses @ai-sdk/openai-compatible
- DeepSeek V4: thinking=enabled by default, reasoning_effort auto=max for agent workloads, reasoning_content MUST be passed back with tool calls
- Memory: SQLite at ~/.local/share/opencode/agent_memory.db
- Orchestrator: classification tree, parallel dispatch, webfetch tool, nano-coder routing

## Tripped Breakers
- (none)

## Quality Signals
| Agent | Task Type | Sent | Accepted | Minor Edit | Major Rewrite | Rejected | Accept Rate |
|-------|-----------|------|----------|------------|---------------|----------|-------------|
| haiku | draft | 0 | 0 | 0 | 0 | 0 | — |
| gemini | code | 0 | 0 | 0 | 0 | 0 | — |
| perplexity | research | 0 | 0 | 0 | 0 | 0 | — |
| grok | search | 0 | 0 | 0 | 0 | 0 | — |
| error_monkey | debug | 0 | 0 | 0 | 0 | 0 | — |

## Delegation Stats
- Total: 0 | Accepted: 0 | Minor edits: 0 | Major rewrites: 0 | Rejected: 0
- Repairs run: 0 | Circuit trips: 0
