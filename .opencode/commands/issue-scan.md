# /issue-scan — Scan GitHub issues and build queue

## Usage
`/issue-scan` — fetches open issues from `screwballzepone/Alexandria`, classifies them, and writes `.opencode/issue-queue.json`

## Steps

### 1. Fetch issues
```powershell
gh issue list --repo screwballzepone/Alexandria --state open --json number,title,labels,body --limit 20
```

### 2. Classify each issue
Read the `body` field to extract acceptance criteria and file hints. Use the `Tier` header in the body if present. Otherwise classify:

| Tier | Criteria |
|------|----------|
| **TINY** | single-file, <30 lines described, ≤2 acceptance criteria, no architecture concerns |
| **STANDARD** | multi-file but known patterns, ≤10 files predicted, clear requirements |
| **SKIP** | COMPLEX/PROJECT/RESEARCH tier, requires human input, mentions "design" or "architecture" |

Parse AC from lines under `### Acceptance Criteria` or `**Acceptance Criteria:**`. Parse file hints from lines under `### File hints` or `**File hints:**`.

### 3. Write queue JSON
Write to `.opencode/issue-queue.json`:
```json
{
  "generated": "<ISO 8601 timestamp>",
  "repo": "screwballzepone/Alexandria",
  "issues": [
    {
      "number": N,
      "title": "...",
      "tier": "STANDARD",
      "ac": ["acceptance criterion 1", "acceptance criterion 2"],
      "files": ["file1.py", "file2.py"],
      "status": "queued"
    }
  ]
}
```

### 4. Report
Report to the user:
- N issues found
- N queued (TINY + STANDARD)
- N skipped (SKIP)

Do NOT modify any files. This is a read-only scan operation.
