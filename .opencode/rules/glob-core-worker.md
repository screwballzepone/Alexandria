# Glob: core/**/*.py — Core Module Rules

## Worker (core/worker.py)
- QThread wrapping opencode.cmd subprocess
- Parses newline-delimited JSON from stdout
- Signals: text_received, tool_started, tool_finished, error_received, process_finished, queue_empty
- stop() uses `taskkill /F /T /PID` on Windows (NOT process.terminate() alone)
- send_input() enqueues dicts; run() dequeues in order

## Service (core/opencode_service.py)
- All static methods
- Calls opencode.cmd via subprocess
- get_models() filters lines containing "/"
- get_agents() parses via regex

## Memory (core/memory.py)
- SQLite at ~/.local/share/opencode/agent_memory.db
- Table: project_memory(id, workspace_path, key, value, tags, time_updated)
- No UNIQUE constraint on (workspace_path, key)
- store() does SELECT then UPDATE or INSERT

## Hooks (core/hooks.py)
- HookRunner class loads .opencode/hooks.json
- Events: PreToolUse (advisory), PostToolUse, Stop
- Types: command (subprocess), prompt (future), agent (future)
- Matcher: regex on tool name
