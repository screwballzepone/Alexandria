# Project State

## MCP Tools Available
- **context7** — Search documentation libraries. Use when you need library/framework docs.
- **gh_grep** — Search GitHub for code examples. Use when unsure about API patterns.
- **exa** — Web search engine. Use for external research. Requires `EXA_API_KEY` env var.

## Skills Available
- **mission-protocol** — PROJECT-tier mission rules, feature lifecycle, token budget, session exhaustion
- **healing-protocol** — Error escalation tiers, reviewer retry limits, degraded mode rules
- **blackboard-protocol** — Shared agent JSON communication, constraints, stale entry rules, lifecycle
- **quality-gate** — Automated pre-check procedure, reviewer verdict criteria, score tracking
- **parallel-universe** — High-stakes 3-branch parallel coding, scoring, merge, cleanup
- **mission-completion** — Post-mission: quality metrics, memory write, lessons, meta-agent, security audit, GENESIS PR, final report

## Systems Added (2026-04-30 — competitive analysis)
- **Hooks** — Deterministic rule enforcement. HookRunner in `core/hooks.py`. Events: PreToolUse (advisory), PostToolUse, Stop. Types: command (subprocess), prompt (future), agent (future). Config: `.opencode/hooks.json`. Integrated into `core/worker.py`.
- **Repo Map** — Live AST-based code analysis. `python .opencode/tools/repomap.py build|rank|context`. Extracts function signatures, class defs, imports. Zero deps.
- **Recipes** — Jinja2 parameterized task templates. `python opencode/tools/recipe_runner.py list|show|run`. Recipes in `.opencode/recipes/`. 3 starters: api-builder, refactor-pattern, test-generator.
- **Rules** — Categorized instruction files in `.opencode/rules/`. Types: `always-*`, `auto-*`, `glob-*`. 4 files covering code style, agent dispatch, UI conventions, core module rules.
- **Directory AGENTS.md** — Per-module context files. `core/AGENTS.md` and `ui/AGENTS.md` with module-specific patterns, gotchas, and unwired features. Loaded automatically when orchestrator's file list touches those directories.
- **Slash Commands** — File-based custom commands in `.opencode/commands/*.md`. Also reads from `opencode.json` command section. Orchestrator detects `/command-name` before normal classification. Built-ins: `/plan`, `/review`, `/status`, `/lint`, `/repomap`.
- **Plan Mode** — Read-only execution mode. Activated by "plan mode", "just plan", `/plan`. Orchestrator analyzes + plans but never writes files. Deactivates on "execute", "go ahead", "proceed".
- **Error Logging** — Structured JSONL error log. `python .opencode/tools/error_logger.py log|query|stats`. Records every failure (agent_stall, reviewer_fail, config_error, etc.) to `.opencode/error-log.jsonl`. Orchestrator logs all failures; healing protocol loads recent errors for pattern detection.

## Plugin Version Management (added 2026-05-01)

**Two `package.json` files exist:**

| Priority | Path | Role |
|----------|------|------|
| **1st (runtime)** | `~/.config/opencode/package.json` | Loaded by `opencode.cmd` — this controls the actual plugin version |
| 2nd (reference) | `.opencode/package.json` | Project-local pin — keep synced with global for consistency |

**Rules:**
- Always update global first: `cd ~/.config/opencode && npm install @opencode-ai/plugin@<version>`
- Sync local after: update `.opencode/package.json` to match
- `opencode.cmd --version` reports the CLI binary version (may differ from plugin version)
- The `compaction` config format changed between v1 and v2 plugin APIs (`keep_first` → `tail_turns`, `max_context_window_tokens` → `preserve_recent_tokens`)

## Instructions
- Never commit directly to master — use feature branches with `python .opencode/tools/git_ops.py`
- Run lint before tests: `ruff check .` then `pytest`
- Use conventional commits (`fix:`, `feat:`, `chore:`, `docs:`)
- Prefer concise responses with structured output
- Always read AGENTS.md for project context
- **BLOCKED ≠ DEAD** — before deleting code, check PIPELINE.md and JANUS-STATE.md. If a path appears in a pipeline phase or is marked BLOCKED, do NOT delete it. Code that "doesn't work yet" (e.g. Brain/LCN blocked on JAX) is waiting to be resumed, not garbage.
