# /review command
# Invoke: /review (or /review <path> to review specific files)

**Agent**: reviewer
**Mode**: code review

Review all uncommitted changes (or the specified path). Check for:
- Bugs, regressions, missing error handling
- Type inconsistencies
- Security issues (injection, hardcoded secrets)
- Style violations (ruff compliance)

Report findings per file. Output as structured JSON with `verdict`, `score`, `issues[]`.
