# Next Steps — Self-Hosting Runbook

Follow top to bottom. Each step has a GO / STOP decision — if STOP, hand
the screenshot back to Cowork and I'll diagnose.

---

## Step 1 — Run Batch 23 Attempt 7

**Goal**: confirm commit 225fdcc (external_directory: allow in server
config) unblocks seam #15. Target ≥18/25 seams.

**Commands** (Windows PowerShell in the OpenCode repo root):
```
# Kill any lingering opencode process first
Get-Process opencode -ErrorAction SilentlyContinue | Stop-Process -Force

# Start the server with the new config loaded
opencode serve --port 4096 --print-logs
```

In a second terminal:
```
opencode run --attach --port 4096 @MagnumOpus/claude-code-prompt-17.md
```

(Use the same prompt file as attempts 4/5/6 — no changes to the smoke
prompt itself.)

**Watch for**:
- `opencode serve --print-logs` output should show every sub-agent spawn
  with `permission.external_directory=allow` resolved (not `ask`)
- Coder's step 7 (the one that hung in attempt 6) should now complete
- Final seam tally should print somewhere in the orchestrator report

**GO if**: seams passed ≥ 18
**STOP if**: seams passed < 18 OR any session hangs > 15 min
  → screenshot the seam scorecard + any hung session's last 10 log
    lines and hand back

---

## Step 2 — Paste Batch 24 into Claude Code

**Only run this if Step 1 hit ≥18/25.**

**Commands**:
```
# Confirm tree is clean and you're on main
git status
git branch --show-current
```

Both must be: clean / main.

Then in Claude Code (Sonnet), paste the entire contents of:
```
MagnumOpus/claude-code-prompt-24.md
```

Claude Code will execute the 7 tasks. Expected runtime: 3–6 minutes
(8 file touches, ~450 lines, plus pytest).

**Watch for** (in Claude Code's final output):
- `=== 29 passed in Xs ===` (8 lcn_write + 18 classifier + 3 seed = 29)
- `Convention|8` and `Error|8` printed by the sqlite3 query
- One commit landed; `git log -1 --format="%h %s"` shown

**GO if**: commit landed, 29 tests pass, SQLite shows 16 entities
**STOP if**: any test fails OR Claude Code halts on a stop condition
  → screenshot the pytest failure or stop-condition message, hand back

---

## Step 3 — Hand batch 24 report back to Cowork

Screenshot Claude Code's final report and drop it in a Cowork turn. I
will:
1. Verify the 29-test pass landed clean
2. Draft **batch 25** (Enterprise: consult bridge, ~800 line diff) with
   matching stop conditions
3. Pre-plant a rollback tag requirement (since 25 is Enterprise and
   edits load-bearing protocols)

---

## Step 4 — Paste Batch 25 (when I deliver it)

Before pasting:
```
git tag janus-pre-batch-25
git push origin janus-pre-batch-25
```

The tag is the Enterprise-tier rollback point. If batch 25 breaks
something, `git reset --hard janus-pre-batch-25` restores you.

Paste `claude-code-prompt-25.md` into Claude Code. This one is bigger
— expect 10–15 minutes and more iterative refinement steps. The
orchestrator touches `.opencode/agent/orchestrator.md` and the 5 role
agent files. Stop conditions will halt on any consult-footer
regression.

**GO if**: smoke test re-runs with 3 consult entries per mission in the
audit log AND no existing seams regressed
**STOP if**: seam count drops below the batch-24-era baseline OR any
  consult injection fires zero queries
  → screenshot the audit log + seam scorecard, hand back

---

## Step 5 — Paste Batch 26 (janus.py CLI)

No rollback tag needed (Production tier, additive — adds files, edits
nothing load-bearing).

After batch 26 lands:
```
python janus.py status      # sanity check
python janus.py seed        # idempotent reseed
python janus.py next        # should print MagnumOpus/claude-code-prompt-27.md
```

**This is the bootstrap moment.** After this step, `janus.py next` will
be the entry point for every subsequent batch.

---

## Step 6 — Paste Batch 27 (retrospective)

Tag first:
```
git tag janus-pre-batch-27
git push origin janus-pre-batch-27
```

After batch 27 lands, run a smoke mission and confirm
`.opencode/.lcn/lcn.sqlite` grew by ≥1 Decision entity:
```
sqlite3 .opencode/.lcn/lcn.sqlite "SELECT COUNT(*) FROM entities WHERE entity_type = 'Decision'"
```

If > 0 → **loop is closed**. LCN is now learning from real missions.

---

## If something goes wrong

- **Claude Code session hits API limit**: the orchestrator may still be
  running server-side. `git status` will tell you whether it finished.
  Resume the same Claude Code session after reset; Sonnet keeps context.
- **A batch's tests fail**: don't patch in Claude Code's session —
  hand back to Cowork. I draft the fix batch (24b, 25b, etc.) and you
  paste that. Patching in-session breaks the audit trail.
- **A seam regresses after batch 25**: `git reset --hard
  janus-pre-batch-25`, hand the regression evidence back, I'll split
  batch 25 into 25a + 25b.
- **opencode serve won't pick up the config**: try
  `opencode serve --port 4097` (different port — clears any stale
  listener) then re-point the run command.

---

## Milestones

- [x] Batch 22: claude-sonnet-4-5 confirmed
- [x] Batch 23 att 6: 15/25 seams, Finding S isolated, 225fdcc committed
- [ ] **Batch 23 att 7: ≥18/25 seams** ← you are here
- [ ] Batch 24: LCN write + tier classifier in .opencode/tools/
- [ ] Batch 25: consult bridge live
- [ ] Batch 26: janus.py next/status/seed/smoke/retro — **bootstrap**
- [ ] Batch 27: retrospective pipeline — **learning loop closed**

After all four boxes below the arrow are checked, JANUS builds JANUS.
