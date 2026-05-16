# /issue-run — Execute queued issues from issue-queue.json

## Usage
`/issue-run` — reads `.opencode/issue-queue.json`, processes each queued issue, and produces a morning report.

## Prerequisites
- `.opencode/issue-queue.json` must exist (run `/issue-scan` first)
- `gh` CLI must be authenticated as `screwballzepone`
- Working tree must be clean (stash if needed)

## Steps

### 0. Load queue
Read `.opencode/issue-queue.json`. Filter issues where `status` is not `"done"` and not `"failed"`. Skip the rest.

Process in ascending issue number order.

### 1. For each queued issue

#### 1a. Create feature branch
```powershell
git checkout -b issue-<NUMBER>-auto
```

#### 1b. Run opencode with issue as prompt
Use the fallback ladder for resilience:
```powershell
python MagnumOpus/scripts/run_with_fallback.py --prompt-file <temp_prompt_file>
```

Where `<temp_prompt_file>` contains:
```
Fix issue #<N>: <title>

Acceptance criteria:
- <AC1>
- <AC2>

File hints: <files>
```

#### 1c. On success
Create a draft PR:
```powershell
gh pr create --repo screwballzepone/Alexandria --title "<title>" --body "Closes #<N>" --base master --draft
```

Update issue status to `"done"` in `.opencode/issue-queue.json`. Add `"pr_number": <N>` field.

#### 1d. On failure
Log the error:
```powershell
python C:\Users\lukas\.config\opencode\runtime\tools\error_logger.py log "{\"type\":\"agent_stall\",\"severity\":\"error\",\"msg\":\"Issue #<N> failed: <reason>\"}"
```

Update issue status to `"failed"` in `.opencode/issue-queue.json`. Add `"failure_reason": "<reason>"` field.

Proceed to next issue.

### 2. Budget and caps enforcement

| Cap | Limit | Action |
|-----|-------|--------|
| Per-night budget | $2.00 total | Abort entire queue if summed costs exceed |
| Per-mission cap | $0.30 per issue | Mark issue failed if exceeded |
| Wall clock | 3 hours total | Abort queue if exceeded |
| Issue cap | 5 missions max | Abort queue if more than 5 issues were queued |

After each mission, sum the `cost` field from all issues (track per-issue cost from opencode output). If any cap is exceeded, abort remaining issues, mark them as `"failed"` with reason.

### 3. Write morning report
Write `MagnumOpus/morning-report-<YYYY-MM-DD>.md` using the template at `MagnumOpus/morning-report-template.md`.

### 4. Return to master
```powershell
git checkout master
```
