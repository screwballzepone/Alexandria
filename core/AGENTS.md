# core/ — AGENTS.md

## Architecture
- `worker.py`: QThread wrapping `opencode.cmd run` subprocess. Never touch UI widgets from here — always signals/slots.
- `opencode_service.py`: Static helpers. All calls to `opencode.cmd` via subprocess.
- `memory.py`: SQLite AgentMemory at `~/.local/share/opencode/agent_memory.db`. Table: `project_memory(id, workspace_path, key, value, tags, time_updated)`. NO UNIQUE constraint.
- `hooks.py`: HookRunner class. PreToolUse (advisory), PostToolUse, Stop events. Integrated in worker.py.
- `drift_guard.py`: Config validation.

## Key patterns
- `shell=True` everywhere (Windows-first design)
- `taskkill /F /T /PID` for process cleanup — never `.terminate()` alone
- `queue.Queue` for message passing from main thread to worker
- Opening brace on same line as class/def: `class Foo(QThread):`
- Lazy imports inside methods (not module top)
- All paths are backslash Windows paths

## What NOT to do
- Never add a UNIQUE constraint to `project_memory` without migration
- Never replace `taskkill` with `terminate()` — leaves orphaned subprocesses
- Never add blocking I/O to `opencode_service.py` static methods
