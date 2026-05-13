# Code Conventions

**Purpose**: Code style rules, import patterns, naming conventions, testing patterns, and error handling patterns. Read by all code-generating sub-agents before writing or editing files. Compression-immune.

## Key Decisions

- **Match existing style** — when editing, follow the patterns already present in that file and directory. Consistency within a file beats consistency with an external standard.
- **Minimal comments** — only add comments when logic is non-obvious (non-standard algorithm, complex regex, workaround). Do NOT comment obvious code (variable assignments, simple loops, standard API calls).
- **No emojis in code** — exception: user-initiated emoji in chat content. Error messages, comments, and logs use plain text.
- **Implicit relative imports** — use `from core.worker import OpenCodeWorker`, not `from .core.worker`. Python 3.14 with venv-based layout makes these unambiguous.
- **Lazy imports for heavy modules** — import markdown, AgentMemory inside methods, not at module top. Keeps startup fast.
- **Type hints with annotations** — use `from __future__ import annotations` for deferred evaluation where needed; otherwise standard PEP 484.
- **CRLF line endings preserved** — the project runs on Windows; all files use CRLF. Never convert to LF.
- **shell=True everywhere** — required because opencode.cmd is a .cmd file requiring cmd.exe. Accepts shell injection risk for CLI arguments.
- **taskkill for process cleanup** — `.terminate()` alone kills only cmd.exe, not the child opencode process. Always use `taskkill /F /T /PID`.
- **BLOCKED ≠ DEAD** — before any deletion, grep PIPELINE.md/JANUS-STATE.md/mission.json for the path. Blocked research code is waiting, not garbage.

## Files Touched

- `main.py` — entry point, QApplication setup, imports MainWindow
- `core/worker.py` — QThread worker, message queue, send_input(), taskkill stop()
- `core/opencode_service.py` — static CLI wrappers, shell=True, 30s timeout
- `core/memory.py` — AgentMemory class, SQLite store/retrieve/delete/list_all
- `core/hooks.py` — HookRunner with PreToolUse/PostToolUse/Stop events
- `ui/main_window.py` — MainWindow with sidebar_tabs, signal/slot connections
- `ui/dialogs.py` — ProvidersDialog, StatsDialog, McpDialog
- `utils/helpers.py` — format_timestamp() only
- `assets/style.qss` — dark theme Qt stylesheet
- `tests/` — pytest test suite
- `.opencode/tools/` — all CLI tool scripts

## Constraints

- **Never block the main thread** — all opencode.cmd calls must go through QThread workers (OpenCodeWorker or ServiceWorker). Blocking the main thread freezes the UI.
- **Never touch UI from worker** — all QThread-to-UI communication must use Signal/Slot. Direct UI access from a non-main thread causes undefined behavior (crash or deadlock).
- **Never use `.terminate()` alone on Windows** — use `taskkill /F /T /PID` to kill the full process tree. `shell=True` spawns cmd.exe as intermediate parent; terminate() only kills cmd.exe, orphaning the opencode process.
- **30s timeout on CLI queries** — all `opencode.cmd` subprocess calls must have explicit timeouts. 30s default for get_models/get_agents/get_sessions.
- **SQL query sanitization** — sanitize user-controlled values before SQL insertion. Session_id uses hex-only filtering. This is explicit: multiline SQL queries must be single-line strings (Windows shell mangling).
- **Never use `QDir.rootPath()`** — loads the entire filesystem. Use `os.getcwd()` for file model root.
- **Never split memory display text on `:`** — values can contain colons. Store key in `Qt.UserRole`.
- **No UNIQUE constraint on project_memory** — existing rows may have duplicate (workspace_path, key) pairs.
- **Fragile files need extra care** — `core/opencode_service.py` and `core/worker.py` are marked as "fragile" in project-map.json due to shell interaction and process management. Larger files like `ui/main_window.py` (~1010 lines) are marked "watch" for complexity.

## Notes

- These conventions are continuously discovered, not designed top-down. If a new pattern emerges across multiple files, add it here
- The `project-map.json` file maintained by @onboarder has a `known_gotchas` section for per-file pitfalls
- `core/AGENTS.md` and `ui/AGENTS.md` have module-specific patterns loaded automatically when orchestrator touches those directories
- When in doubt about code style, check the `ruff` linter (`ruff check .`) — it enforces most formatting rules automatically
- Sub-agent handoffs must follow the TASK/CONTEXT/PLAN/CONSTRAINTS/OUTPUT/VERIFY/DONE format (see orchestrator.md DISPATCH PROTOCOL)
