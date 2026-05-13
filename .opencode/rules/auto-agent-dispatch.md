# Auto: Agent Dispatch Rules

## When to use which agent
- @nano-coder: single-file, <30 line changes, read-only pre-flight
- @coder: all code generation and editing
- @explorer: unfamiliar codebase areas, before any significant change
- @architect: decisions affecting 5+ files or cross-cutting concerns
- @reviewer: after every STANDARD+ change

## Subagent dispatch format
Always include: TASK, CONTEXT (files + exports + patterns), PLAN (skeleton), CONSTRAINTS, OUTPUT format.

## Blackboard protocol
Before parallel agent dispatch: add file constraints to `.opencode/blackboard.json`.
After parallel batch completes: remove expired constraints.
