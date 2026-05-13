# CogitoCode

Modifications to OpenCode's agent runtime for smarter context management.

## State Layer
Persistent companion files read by the orchestrator at session start:

| File | Purpose | Managed by |
|------|---------|------------|
| `.opencode/world_env.json` | Workspace file index with summaries | `world_env.py` (read-only at session start) |
| `state/mission.json` | "Why are we here" — session-wide objective | `mission.py` (LLM proposes, user approves) |
| `state/tasks.json` | "What am I doing now" — per-response task list | `tasks.py` (LLM manages freely) |
| `state/checklist.json` | "Did I do this right" — verification items | `checklist.py` (template-driven, per-objective) |

## Quick start
```bash
# Set a mission
python .opencode/cogito/mission.py propose "Building CogitoCode state layer"
# (ask user for approval)
python .opencode/cogito/mission.py accept

# Start tasks
python .opencode/cogito/tasks.py init "plan feature" "implement feature" "test feature"

# Generate checklist before coding
python .opencode/cogito/checklist.py generate --objective implement --context "Building new component"

# Mark progress
python .opencode/cogito/tasks.py done 1
python .opencode/cogito/checklist.py check 1
python .opencode/cogito/checklist.py check 2
```

## Context Indexer
`../tools/world_env.py` — workspace file indexer with summaries and load/unload.

## Templates
5 checklist templates in `templates/`:
- `implement.json` — code generation checklist
- `fix-bug.json` — bug fix verification
- `refactor.json` — refactoring safety checks
- `review.json` — code review standards
- `audit.json` — codebase health audit
