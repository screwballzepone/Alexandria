# Cowork Report — Batch 16
**Phase 5.2 + 5.4: Eval System + Parallel Universe Coding**
Date: 2026-04-18

---

## Summary

Batch 16 adds two Phase-5 subsystems:

1. **Eval System** (`eval_runner.py` + 5 eval definitions) — synthetic benchmark tasks with assertion-based scoring, baseline tracking, and regression detection.
2. **Parallel Universe Coding** (`parallel_universe.py`) — for high-stakes features, spawns 3 coder branches (pragmatic / robust / performance), reviewer scores all three, winner is merged and losers deleted.

Both systems integrate into the existing orchestration pipeline via targeted edits to `meta-agent.md`, `orchestrator.md`, `mission-protocol.md`, and `opencode.json`.

---

## Tasks Completed

### Task 1 — `eval_runner.py`
Created `.opencode/tools/eval_runner.py`.

- Loads `evals/*.json` eval definitions
- Assertion types: `contains`, `not_contains`, `ruff_passes`, `python_runs`, `regex`
- Runs full suite, saves `evals/results.json`, updates `agent_baselines`
- `compare_to_baseline()` returns `improved | stable | regression` (regression = delta < −5)
- CLI: `run [agent]`, `baseline`, `list`

### Task 2 — 5 Eval Definitions
Created `.opencode/evals/eval-01` through `eval-05`:

| ID | Description | Category | Threshold |
|----|-------------|----------|-----------|
| eval-01-error-handling | Add FileNotFoundError / PermissionError handling | correctness | 70 |
| eval-02-refactor-loop | Refactor for-loop → list comprehension | style | 80 |
| eval-03-write-test | Write pytest tests for sum_positives | testing | 75 |
| eval-04-no-secrets | Refactor hardcoded creds → os.environ | security | 90 |
| eval-05-conventional-commit | Write conventional commit message | output-format | 80 |

### Task 3 — `meta-agent.md`: Eval verification step
Inserted **Step 4.5** before `### 5. Auto-apply if criteria met`:

- Back up target agent file
- Apply proposal edits temporarily
- Run `eval_runner.py run <agent>` → compare to baseline
- `regression` (delta > 5) → revert immediately + log `EVAL REGRESSION PREVENTED`
- `improved` or `stable` → proceed to Step 5
- Downgrade proposal confidence by 0.2 on revert

### Task 4a — `parallel_universe.py`
Created `.opencode/tools/parallel_universe.py`.

- `APPROACHES` embedded in `build_universe_prompt()` for pragmatic / robust / performance
- `run_parallel_universe()`: creates 3 `universe/<mission>-<feature>-<approach>` branches, runs @coder on each
- `score_universes()`: disqualifies error/FAIL branches, picks highest reviewer score; tie-break: pragmatic > robust > performance
- `cleanup_losing_branches()`: deletes 2 non-winning branches via `git_ops.py delete`

### Task 4b — `orchestrator.md`: Tier 3 routing
Replaced old step 4 with high-stakes branch:

```
4. Check high_stakes flag in mission.json (default: false):
   - high_stakes: true  → parallel_universe.py (3 branches) → reviewer scores → merge winner
   - high_stakes: false → @coder (standard parallel calls)
```

### Task 4c — `orchestrator.md`: PARALLEL UNIVERSE CODING section
Inserted full protocol block before `## REVIEWER RESULT HANDLING`:

- 7-step protocol: branch creation → parallel dispatch → quality gate per branch → score → merge winner → cleanup losers → feature summary note
- "When to set `high_stakes: true`" guidance (auth, perf hot-paths, post-incident, user request)
- Cost note: ~3× standard @coder — do NOT use for TINY features

### Task 5 — `mission-protocol.md`: `high_stakes` field
Added `"high_stakes": false,` to the feature schema between `acceptance_criteria` and `failures`.

### Task 6 — `opencode.json`: `/eval` slash command
Added `"eval"` command after `dep-check`:

```json
"eval": {
  "description": "Run the eval suite against an agent and compare to baseline",
  "agent": "orchestrator",
  "template": "EVAL MODE. Run: python .opencode/tools/eval_runner.py run $ARGUMENTS ..."
}
```

---

## Verification

```
eval count: 5
ids: ['eval-01-error-handling', 'eval-02-refactor-loop', 'eval-03-write-test',
      'eval-04-no-secrets', 'eval-05-conventional-commit']
PASS: eval loading check

functions: ['build_universe_prompt', 'cleanup_losing_branches',
            'run_parallel_universe', 'score_universes', 'universe_branch']
PASS: parallel_universe structure check
```

---

## Files Changed

| File | Change |
|------|--------|
| `.opencode/tools/eval_runner.py` | Created |
| `.opencode/tools/parallel_universe.py` | Created |
| `.opencode/evals/eval-01-error-handling.json` | Created |
| `.opencode/evals/eval-02-refactor-loop.json` | Created |
| `.opencode/evals/eval-03-write-test.json` | Created |
| `.opencode/evals/eval-04-no-secrets.json` | Created |
| `.opencode/evals/eval-05-conventional-commit.json` | Created |
| `.opencode/agent/meta-agent.md` | Step 4.5 eval verification inserted |
| `.opencode/agent/orchestrator.md` | Tier 3 step 4 + PARALLEL UNIVERSE CODING section |
| `.opencode/protocols/mission-protocol.md` | `high_stakes` field in feature schema |
| `.opencode/opencode.json` | `/eval` slash command added |

---

## Architecture Notes

- **Eval system is decoupled**: `eval_runner.py` runs entirely from JSON definitions — adding new evals requires no code changes, only a new `eval-NN-*.json` file.
- **Parallel universe is opt-in**: `high_stakes: false` by default — existing missions are unaffected until explicitly flagged.
- **Regression guard in meta-agent**: The eval step in 4.5 creates a safety net so meta-agent can never silently degrade an agent's performance through auto-apply.
- **`/eval` command**: Gives the orchestrator a first-class entry point for benchmarking without needing to know the tool internals.
