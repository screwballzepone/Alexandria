# AGENTS.md — OpenCode GUI Project Context

> This file is injected by OpenCode into every session. Read it fully before doing anything.

---

## What This Project Is

A PySide6 desktop GUI that wraps the OpenCode CLI (`opencode.cmd`) into a chat interface. The user types instructions, the GUI sends them to OpenCode as a background subprocess, and streams the JSON output back into a styled Qt chat window. It also manages session history, agent/model selection, and long-term memory via SQLite.

**This is also used as a creative writing and prompt engineering workstation** — the `@prompt-writer` agent produces AI character profiles (PList format) for use on clank.world. Not purely a coding tool.

---

## How to Launch

```bat
start.bat         ← Windows launcher (uses pythonw.exe — no terminal window)
python main.py    ← Direct launch with terminal (for debugging)
```

Python version: **3.14.3**. Venv at `venv/`. Always activate before installing packages.

---

## Critical: opencode.cmd Location

OpenCode is installed globally at `C:\Users\lukas\AppData\Roaming\npm\opencode.cmd` (v1.14.31).
`opencode.cmd` resolves to `C:\Users\lukas\AppData\Roaming\npm` (global install) which is in the system/user PATH.

The `.opencode/` config directory depends on `@opencode-ai/plugin` (see `.opencode/package.json`).

### CRITICAL: Global vs Local Plugin Config

`opencode.cmd` loads its plugin from the **global** config, NOT the project-local one:

| Location | File | Used by |
|----------|------|---------|
| **Global (PRIORITY)** | `~/.config/opencode/package.json` | `opencode.cmd` runtime — this is what matters |
| Local (reference) | `.opencode/package.json` | Project docs — keep synced for consistency |

When checking/bumping the plugin version, **always update the global config first**:
```powershell
cd $env:USERPROFILE\.config\opencode && npm install @opencode-ai/plugin@<version>
```

The local `.opencode/package.json` is a secondary reference. Never bump only the local one — it has zero effect on runtime behavior. The `opencode.cmd` binary reports its version via `opencode.cmd --version`, which may differ from the plugin version in `~/.config/opencode/package.json`.

---

## File Layout

```
OpenCode/
├── main.py                    # Entry point — creates QApplication, loads style.qss, shows MainWindow
├── start.bat                  # Windows launcher (pythonw, no console window)
├── conftest.py                # Root-level pytest configuration
├── assets/
│   └── style.qss              # Full dark-theme Qt stylesheet (VS Code-inspired)
├── core/
│   ├── opencode_service.py    # Static helpers: run opencode.cmd, get models/agents/sessions/messages
│   ├── worker.py              # QThread that runs opencode.cmd run ... --format json and parses output
│   ├── memory.py              # SQLite-backed long-term memory (agent_memory.db in ~/.local/share/opencode/)
│   ├── hooks.py               # HookRunner — deterministic rule enforcement (PreToolUse, PostToolUse, Stop)
│   ├── drift_guard.py         # Drift detection guard for codebase state consistency
│   ├── service_worker.py      # Background service worker for periodic tasks
│   └── AGENTS.md              # Module-specific agent context patterns and gotchas
├── ui/
│   ├── main_window.py         # MainWindow: toolbar, sidebar (Files/Sessions/Memory tabs), chat area
│   ├── dialogs.py             # ProvidersDialog, StatsDialog, McpDialog
│   └── AGENTS.md              # Module-specific agent context patterns and gotchas
├── utils/
│   ├── __init__.py            # Package init
│   └── helpers.py             # format_timestamp(dt) — converts datetime to "X minutes ago" strings
├── tests/
│   ├── test_mission_status.py # Tests for mission_status.py
│   ├── test_lcn_write.py      # Tests for lcn_write.py
│   ├── test_lcn_read.py       # Tests for lcn_read.py
│   ├── test_consult.py        # Tests for consult.py
│   └── test_capability_assessor.py  # Tests for capability_assessor.py
├── .opencode/
│   ├── opencode.json          # OpenCode config: default model, small_model, provider options
│   ├── agent/                 # 18 agent definition files (frontmatter + system prompt)
│   │   ├── orchestrator.md    # PRIMARY agent — DeepSeek V4 Flash, decomposes tasks, routes to subagents
│   │   ├── coder.md           # Subagent — DeepSeek V4 Flash, writes/edits code
│   │   ├── explorer.md        # Subagent — Grok 4.20 Beta (via OpenRouter), scans files and structure
│   │   ├── architect.md       # Subagent — Cerebras Qwen 3 235B, complex design decisions only
│   │   ├── reviewer.md        # Subagent — DeepSeek V4 Flash, code quality gatekeeper
│   │   ├── prompt-writer.md   # Subagent — DeepSeek V4 Flash, PList/Ali:Chat character profiles
│   │   ├── nano-coder.md      # Subagent — DeepSeek V4 Flash, read-only minimal assistant
│   │   ├── test-writer.md     # Subagent — DeepSeek V4 Flash, TDD test writer
│   │   ├── math-verifier.md   # Subagent — DeepSeek V4 Flash, math correctness specialist
│   │   ├── vision.md          # Subagent — GPT-4o, vision/plot/screenshot analysis
│   │   ├── security-auditor.md # Subagent — DeepSeek V4 Flash, post-merge security scanner
│   │   ├── documenter.md      # Subagent — DeepSeek V4 Flash, post-commit doc sync
│   │   ├── dependency-scout.md # Subagent — DeepSeek V4 Flash, weekly dep scanner
│   │   ├── lessons.md         # Subagent — DeepSeek V4 Flash, post-mission retrospective
│   │   ├── onboarder.md       # Subagent — DeepSeek V4 Flash, codebase explorer
│   │   ├── meta-agent.md      # Subagent — DeepSeek V4 Flash, post-mission prompt editor
│   │   ├── researcher.md      # Subagent — DeepSeek V4 Flash, in-depth research agent
│   │   └── memory-writer.md   # Subagent — DeepSeek V4 Flash, persistent memory writer
│   └── tools/                 # 23 CLI tool scripts for automation, CI, quality, and mission management
│       ├── project_map.py
│       ├── git_ops.py
│       ├── repomap.py
│       ├── recipe_runner.py
│       └── ...
├── Brain/
│   └── lcn_brain/               # LCN research project — blocked on JAX (PIPELINE.md Phases A–C)
└── MagnumOpus/                # Cowork/MagnumOpus session files (session-state, reports, logs)
```

---

## The Agent System

OpenCode runs a **17-agent multi-agent system**. The orchestrator is the primary agent; all others are subagents.

| Agent | Model | Role | When Used |
|-------|-------|------|-----------|
| orchestrator | deepseek/deepseek-v4-flash | Decomposes tasks, routes to subagents. NEVER writes code itself. | Always (primary) |
| coder | deepseek/deepseek-v4-flash | Writes/edits/creates code files | All code generation |
| explorer | openrouter/x-ai/grok-4.20-beta | Scans dirs, reads files, maps structure | Before coding on unfamiliar code |
| architect | openrouter/qwen/qwen3-235b-a22b-07-25 | Complex design decisions, multi-file architecture | Only for decisions affecting 5+ files |
| reviewer | deepseek/deepseek-v4-flash | Code review: correctness, types, security, style | After significant changes |
| prompt-writer | deepseek/deepseek-v4-flash | PList/Ali:Chat character profiles, narrator engine sections | For clank.world creative work |
| nano-coder | deepseek/deepseek-v4-flash | Read-only minimal assistant for low-token tasks | Single-shot code lookups |
| test-writer | deepseek/deepseek-v4-flash | TDD test writer — writes failing tests before coder | Before new features |
| math-verifier | deepseek/deepseek-v4-flash | Math correctness — gradient checks, Taylor tests, invariant assertions | On math-heavy code changes |
| vision | openrouter/openai/gpt-4o | Vision specialist — analyzes images, plots, screenshots, diagrams | When visual data needs interpretation |
| security-auditor | deepseek/deepseek-v4-flash | Post-merge injection/auth/secrets/CVE scanner | After merges |
| documenter | deepseek/deepseek-v4-flash | Post-commit doc sync — updates docstrings and docs | After commits |
| dependency-scout | deepseek/deepseek-v4-flash | Weekly dependency scanner — finds outdated packages, CVEs | Weekly |
| lessons | deepseek/deepseek-v4-flash | Post-mission retrospective — records lessons learned | After missions |
| onboarder | deepseek/deepseek-v4-flash | One-time codebase explorer — generates project-map.json | New projects |
| meta-agent | deepseek/deepseek-v4-flash | Post-mission prompt editor — proposes agent prompt updates | After missions |

**Orchestrator workflow:** UNDERSTAND → EXPLORE (@explorer) → PLAN → EXECUTE (@coder) → REVIEW (@reviewer) → REPORT

**Budget rules:**
- `@architect` only for decisions affecting 5+ files or conflicting subagent outputs
- Always `@explorer` before `@coder` on unfamiliar code
- Always `@reviewer` after significant changes

---

## The GUI Architecture

### MainWindow (`ui/main_window.py`)
- **Toolbar**: model dropdown, agent dropdown, Low Token Mode checkbox, action buttons (Providers, Agents, Sessions, MCP, GitHub, Stats), New Session, ↻ Sessions
- **Sidebar** (left, 250px): three tabs — Files (QTreeView), Sessions (QListWidget), Memory (QListWidget + buttons)
- **Chat area** (right, 850px): QTextBrowser for output, QTextEdit input (70px tall), Send button
- Enter to send, Shift+Enter for newline

### OpenCodeWorker (`core/worker.py`)
- Runs as a **QThread**
- Calls `opencode.cmd run <message> --format json --dangerously-skip-permissions`
- Parses newline-delimited JSON from stdout
- Emits signals: `text_received(str)`, `tool_started(str, str)`, `tool_finished(str)`, `error_received(str)`, `process_finished(int)`, `queue_empty()`
- **Message queue**: uses `queue.Queue` — send_input() enqueues dicts, run() dequeues and processes in order
- **stop()**: uses `taskkill /F /T /PID` on Windows to kill the full process tree (shell=True spawns cmd.exe as intermediate)

**send_input() full signature:**
```python
send_input(text, model=None, agent=None, file=None, plan_mode=False, slash_command=False, fork=False, title=None)
```
- `file` → adds `--file <path>` (attach a file to the prompt)
- `plan_mode` → prepends "PLAN MODE — do not modify files" instruction to the prompt
- `slash_command` → sends text as `--command <text>` instead of a positional prompt (use for /undo, /redo, /share, /init)
- `fork` → adds `--fork` (branches current session into a new one)
- `title` → adds `--title <title>` (sets session title on first message)

### OpenCodeService (`core/opencode_service.py`)
- Static methods, all call `opencode.cmd` via subprocess
- `get_models()` — parses `opencode.cmd models` output, filters lines containing "/"
- `get_agents()` — parses `opencode.cmd agent list`, extracts names via regex
- `get_sessions()` — queries SQLite DB directly: `opencode.cmd db "<SQL>" --format json`
- `get_session_messages(session_id, limit)` — joins message + part tables, returns text blob

### AgentMemory (`core/memory.py`)
- SQLite DB at `~/.local/share/opencode/agent_memory.db`
- Table: `project_memory(id, workspace_path, key, value, tags, time_updated)`
- No UNIQUE constraint on (workspace_path, key) — store() does SELECT first, then UPDATE or INSERT
- Methods: `store()`, `retrieve()`, `delete()`, `list_all()`

---

## OpenCode Config (`.opencode/opencode.json`)

```json
{
  "model": "deepseek/deepseek-v4-flash",
  "small_model": "deepseek/deepseek-v4-flash",
  "default_agent": "orchestrator",
  "snapshot": true,
  "autoupdate": "notify",
  "compaction": { "auto": true, "tail_turns": 2, "preserve_recent_tokens": 50000, "reserved": 1000 },
  "provider": {
    "anthropic": { "timeout": 600000, "setCacheKey": true },
    "openrouter": { "baseURL": "https://openrouter.ai/api/v1" },
    "deepseek": { "baseURL": "https://api.deepseek.com/v1" },
    "google": { "timeout": 600000 },
    "cerebras": {
      "npm": "@ai-sdk/openai-compatible",
      "baseURL": "https://api.cerebras.ai/v1",
      "models": {
        "qwen-3-235b-a22b-instruct-2507": {},
        "llama3.1-8b": {}
      }
    }
  }
}
```

- `snapshot: true` — OpenCode tracks file changes; enables /undo and /redo
- `autoupdate: "notify"` — OpenCode shows a notification when updates are available (does not auto-install)
- `compaction` — auto-compacts context, keeps 2 recent turns verbatim, preserves 50000 tokens

---

## Key Conventions

- **Windows-first**: `shell=True` everywhere, `.cmd` file extensions, `taskkill` for process cleanup, backslash paths
- **Qt threading**: never touch UI widgets from the worker thread — always use signals/slots
- **Lazy imports**: some imports (e.g. `markdown`, `AgentMemory`) are done inside methods, not at module top — match this style when adding new functionality
- **HTML in chat**: all chat output is formatted as inline HTML and appended to `QTextBrowser`. Use dark theme colors: background `#252526`, accent `#569CD6`, user text `#4CAF50`, error `#F44336`
- **opencode.cmd output**: arrives as newline-delimited JSON with `type` field — values are `"text"`, `"tool_use"`. Session ID captured from first `sessionID` field seen

---

## Installed Dependencies (venv)

- PySide6 6.11.0
- markdown 3.10.2
- ruff (dev — linting/formatting)

---

## What NOT to Do

- **Never block the main thread** — all opencode.cmd calls must go through the QThread worker
- **Never call `self.process.terminate()` alone on Windows** — it only kills cmd.exe, not the opencode subprocess. Always use `taskkill /F /T /PID`
- **Never use `QDir.rootPath()` as the file model root** — it loads the entire filesystem. Use `os.getcwd()`
- **Never split memory display text on `:` to extract keys** — values can contain colons. Store key in `Qt.UserRole` on the list item
- **Never add a UNIQUE constraint to project_memory** without a migration plan — the table has existing rows

---

## GUI Features Status

### ✅ Implemented (shipped in commit 0041b35)
1. **Plan Mode toggle** — `QCheckBox` in toolbar, wired via `plan_mode=checkbox.isChecked()` in send_message()
2. **File attachment** — 📎 button + `QFileDialog` + `pick_attachment()`, passed as `file=path` in send_message()
3. **Slash command palette** — `/` key in `eventFilter()` pops QMenu with `/undo`, `/redo`, `/share`, `/init`
4. **Undo / Redo** — ↩ ↪ toolbar actions (line 133-134), calls `worker.send_input("/undo", slash_command=True)`
5. **Session Fork** — "Fork Session" button in Sessions tab, `fork_session()` calls `worker.send_input(fork=True)`
6. **New Session Title** — `QInputDialog.getText()` in `new_session()`, passed via `_pending_title` in send_message()
7. **Model list refresh** — "↻ Models" toolbar action, `refresh_models()` via ServiceWorker

### ⏳ Pending (Phase F stretch goals from PIPELINE.md)
8. **Mission tab live status** — auto-refresh every 2s, show current feature + last 5 blackboard log lines
9. **Memory tab supermemory** — show supermemory plugin entries, search box, manual delete
10. **Repo map sidebar** — "Repo Map" sub-tab in Files, renders repomap.py output as tree

## Mission Autonomy System (added 2026-04-16)

For PROJECT-tier tasks (multi-session, multi-feature), the orchestrator uses:
- `.opencode/mission.json` — mission state machine (created automatically on PROJECT tasks)
- `.opencode/blackboard.json` — shared agent communication board
- `.opencode/resume.json` — session handoff packet
- `.opencode/features/<id>.md` — feature summaries (written by @nano-coder after each feature)
- `.opencode/protocols/` — mission, healing, and blackboard protocol specs

The Python GUI shows mission state in the "Mission" tab. Resume button injects the
resume context. Clear Mission button resets mission.json.

### When to trigger a PROJECT-tier mission
Use the **🚀 Mission** button in the GUI (left of Send) — it auto-frames the input as a PROJECT-tier task.
Or tell the orchestrator directly: "This is a PROJECT-tier task: [description]"

### GUI tab widget attribute name
The sidebar tab widget is `self.sidebar_tabs` — NOT `self.tab_widget`.
Always use `self.sidebar_tabs` when switching tabs in main_window.py code.
