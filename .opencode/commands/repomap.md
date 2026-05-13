# /repomap command
# Invoke: /repomap (or /repomap <module>)

Generate a repository map for context loading.

```bash
python .opencode/tools/repomap.py context --include "<module>/*.py" --max-tokens 500
```

Use this before dispatching agents to unfamiliar code. The output shows function signatures, class defs, and import patterns.
