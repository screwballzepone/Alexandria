# Smoke Test Pre-flight Diagnostics (Retry — Batch 17 v2)
**2026-04-18 — Post batch 18+19 remediation**

---

## Commands and outputs

### `python --version`
```
Python 3.14.3
```

### `ruff --version`
```
ruff 0.15.11
```

### `python -c "import pytest; print('pytest', pytest.__version__)"`
```
pytest 9.0.3
```

### `python .opencode/tools/lcn_client.py`
```
LCN offline. Start with:  cd lcn && start-lcn.bat
```

### `python .opencode/tools/genesis.py check`
```json
{"gh_available": false, "gh_authenticated": false}
```

### `gh --version`
```
/usr/bin/bash: line 1: gh: command not found
```

### `gh auth status`
```
/usr/bin/bash: line 1: gh: command not found
```

### `git status --short` (tracked modifications only — untracked files omitted)
```
(no tracked modifications — only ?? untracked working notes)
```

### `git log --oneline -5`
```
50b8b3e fix(batch-19): clear pre-existing ruff violations in tools/; quality_gate handles pytest exit-5 as skipped
2ab24dc chore(batch-18): env remediation — ruff/pytest deps, prompt patches, is-clean fix
12fe882 docs+ui: session-state log, AGENTS.md mission autonomy section, Mission btn layout, main.py import order
6988d1a docs(batch-17): smoke-test pre-flight — STOP CONDITION 1 (dirty tree)
66e10b8 feat(batch-16): eval system + parallel universe coding
```

### `python .opencode/tools/project_map.py exists`
```
no
```

### `python .opencode/tools/quality_gate.py` (head -30)
```json
{
  "ruff": {"passed": true, "issues": [], "count": 0},
  "mypy": {"passed": true, "issues": [], "count": 0, "skipped": true},
  "pytest": {"passed": true, "issues": [], "count": 0, "skipped": true},
  "overall": "PASS",
  "blocker_count": 0,
  "summary": "All checks passed. Safe to call @reviewer."
}
```

### `python .opencode/tools/git_ops.py is-clean`
```json
{"ok": true, "data": {"clean": true}}
```

---

## Pre-flight check answers

| Check | Result | Detail |
|-------|--------|--------|
| **LCN online?** | ❌ NO | Offline — memory-writer will gracefully no-op |
| **gh authenticated?** | ❌ NO | gh not installed — GENESIS will skip PR creation with logged reason |
| **Working tree clean?** | ✅ YES | `git_ops.py is-clean` → `{"clean": true}`; no tracked modifications |

**All STOP conditions: GREEN. Proceeding with smoke test.**
