STATUS: PASS — 4/4 findings addressed, infrastructure ready for smoke test attempt 10

# Cowork Report — Batch 24 (Seam-Fix Remediation)
**Targeted fixes for Findings B, C, D, E from Batch 17 smoke test**
Date: 2026-04-23

---

## Summary

- Mission: Fix seam failures identified in Batch 17 before Batch 25 smoke test retry (attempt 10)
- Batch outcome: PASS — all 4 targeted findings patched
- Files changed: 4
- Tests run: `ruff check .opencode/tools/git_ops.py` → clean; function signature assertions → pass

---

## Background

Batch 17 smoke test (attempt 7 / inner run a9) achieved **11/25 seams PASS** against a ≥18/25
threshold required to unlock Phase 6.1. Four actionable findings were identified:

| Finding | Seams affected | Description |
|---------|---------------|-------------|
| B | 1–5 | SESSION START protocol skipped by orchestrator |
| C | 15, 17 | `git_ops.py commit` used `git add -A`, staging 111 untracked files |
| D | 12 | Quality gate delegated to @coder instead of run directly by orchestrator |
| E | 6 | Tier classification not logged in orchestrator output |

Additionally: `.gitignore` did not exclude `MagnumOpus/smoke-test-artifacts/`, which is why
the 75+ log files were untracked (not gitignored) when the over-commit occurred.

---

## Changes Made

### 1. `.gitignore` — exclude smoke-test artifacts directory

**Finding addressed**: C (defense-in-depth)

Added:
```
# Smoke-test and CI run artifacts (step-trace logs, tmp outputs)
MagnumOpus/smoke-test-artifacts/
```

This prevents step-trace JSON logs from being staged by any `git add` variant. The
`MagnumOpus/cowork-report-*.md` files remain tracked since they're deliverables, not logs.

---

### 2. `.opencode/tools/git_ops.py` — targeted file staging in `commit()`

**Finding addressed**: C (root cause fix)

**Before**:
```python
def commit(message, add_all=True, cwd=None):
    if add_all:
        code, _, err = run("git add -A", cwd=cwd)
```

**After**:
```python
def commit(message, files=None, add_all=True, cwd=None):
    if files:
        for f in files:
            f_norm = str(f).replace("\\", "/")
            code, _, err = run(f'git add -- "{f_norm}"', cwd=cwd)
    elif add_all:
        code, _, err = run("git add -A", cwd=cwd)
```

CLI usage updated: `git_ops.py commit <message> [files...]`

Any extra positional arguments after the commit message are treated as explicit file paths
to stage. When `files` is provided, `git add -A` is never called.

**Backward compatibility**: existing calls with no file args still use `git add -A` (the old
behavior), so session-end housekeeping commits (where the tree IS known clean) still work.

---

### 3. `.opencode/protocols/mission-protocol.md` — explicit file targeting in commit step

**Finding addressed**: C (protocol enforcement)

Updated step 8 "On success" to:
1. Instruct the orchestrator to identify feature files via `git status --porcelain` first
2. Show the commit command with explicit file paths:
   ```bash
   python .opencode/tools/git_ops.py commit "feat(<id>): <one-line summary>" \
     .opencode/tools/<file>.py tests/test_<file>.py
   ```
3. Same pattern for the docs commit after @documenter

This closes the loop between the protocol instruction and the fixed CLI.

---

### 4. `.opencode/agent/orchestrator.md` — three improvements

**Findings addressed**: B (SESSION START), D (quality gate), E (tier logging)

#### 4a. SESSION START — mandatory enforcement

The section header now reads:
```
## SESSION START — MANDATORY (run before ANY task, including mission resumption)
```

Added ⚠️ block at top:
> These steps are non-negotiable. Run them even when the user prompt says "resume mission",
> "continue", or "execute per mission-protocol.md". Skipping SESSION START is the single
> most common orchestrator failure mode.

Each step now has an explicit log statement:
- Step 0: `log "SESSION START: working tree clean ✓"`
- Step 1: `log "SESSION START: checking project map"`
- Step 2: `log "SESSION START: loading user model"`
- Step 3: `log "SESSION START: reading lessons"`
- Step 4: `log "SESSION START: checking LCN"`
- Step 5: `log "SESSION START: checking genesis/gh"`

**Also fixed**: the duplicate step-4 numbering bug. The original had step 4 appear twice
(LCN check and LCN query). These are now steps 4, 5, 6, 7 (with dep-scout short-circuit
at step 6 and LCN query at step 7).

#### 4b. STEP 1 classification — explicit tier logging

Added after the tier table:
```
After classifying, log your decision explicitly, e.g.:
TIER: STANDARD — multi-file feature, clear acceptance criteria, no cross-cutting changes
```

This makes seam 6 (tier classification) directly observable in the log.

#### 4c. Tier 2 STANDARD routing — quality gate explicit

Changed step 5 from the ambiguous:
```
5. Quality gate → @reviewer — reviewer also checks...
```

To explicit:
```
5. Quality gate — YOU run this directly (not delegated to @coder):
   python .opencode/tools/quality_gate.py
   Parse the JSON output. PASS → proceed to @reviewer. FAIL → dispatch @coder with issues.
6. @reviewer — also checks that tests are meaningful (not trivially passing)
```

---

## Verification

```
$ ruff check .opencode/tools/git_ops.py
All checks passed!

$ python -c "from git_ops import commit; import inspect; print(inspect.signature(commit))"
(message, files=None, add_all=True, cwd=None)

$ python .opencode/tools/git_ops.py
commit <message> [files...]  — stage files (or all) and commit
```

---

## Expected Seam Impact (Batch 25 estimate)

| Seam | Finding | Before | Expected After |
|------|---------|--------|---------------|
| 1–5 | B | NOT_RUN | PASS (SESSION START logs now observable) |
| 6 | E | NOT_RUN | PASS (tier logged explicitly) |
| 12 | D | DEGRADED | PASS (orchestrator runs quality_gate.py itself) |
| 15 | C | FAIL | PASS (targeted staging prevents over-commit) |
| 17 | C | FAIL | PASS (clean feat branch → clean merge) |
| 18–25 | (blocked by 17) | NOT_RUN | Observable for first time |

Previous: **11/25 PASS**
Estimated after fixes: **20–22/25 PASS** (≥18 threshold met → Phase 6.1 unlocked)

Remaining NOT_RUN seams most likely to still fail:
- Seam 4 (LCN online check): LCN is offline — graceful no-op path, not a pipeline failure
- Seam 21 (@memory-writer LCN write): same, offline graceful no-op
- Seam 24 (GENESIS PR): gh CLI not installed — logged skip, not a failure

These three are environment constraints, not pipeline bugs. They will show as DEGRADED
(graceful skip) rather than FAIL once seams 1-5 are observed. Seam 24 (GENESIS) at worst
logs "gh not installed — skipping PR creation."

---

## Recommended Next Batch (Batch 25)

Pre-conditions before running attempt 10:
1. Reset `mission.json` to `planning` state (same script as previous attempts)
2. Run `git clean -fd MagnumOpus/smoke-test-artifacts/` to clear any old log artifacts
   (they're now gitignored but may still be present in the working tree)
3. Verify working tree is clean: `python .opencode/tools/git_ops.py is-clean`

Run command (same `--model` workaround as a9):
```bash
opencode serve --port 4096 --print-logs 2>&1 | tee MagnumOpus/smoke-test-artifacts/server-b25-a10.log &
opencode run --attach http://localhost:4096 --model anthropic/claude-sonnet-4-6 \
  --agent orchestrator --format json --dangerously-skip-permissions \
  @MagnumOpus/claude-code-prompt-25.md \
  2>&1 | tee MagnumOpus/smoke-test-artifacts/orchestrator-b25-a10.log
```

Success threshold: **≥18/25 seams PASS** → Phase 6.1 (multi-project brain) unlocked.
