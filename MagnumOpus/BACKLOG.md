# JANUS Backlog

Authoritative queue of work needed to reach self-sufficiency. Each batch
has a fixed schema that `janus.py next` (batch 26) will parse. Do not
reorder without updating janus.py's parser.

## Schema

Each batch is a `## Batch NN — <title>` heading followed by:

```
- **Status**: unstarted | in-progress | done | blocked
- **Tier**: MVP | Production | Enterprise
- **Depends on**: <comma-separated batch numbers or "-">
- **Prompt file**: MagnumOpus/claude-code-prompt-NN.md
- **Expected files touched**: <n>
- **Expected diff lines**: <n>
- **Completion criteria**: <one-line assertion>
```

`janus.py next` selects the first batch with status=unstarted whose
dependencies are all done.

---

## Batch 23 — Smoke test (attempt 7)

- **Status**: in-progress
- **Tier**: Production
- **Depends on**: 22
- **Prompt file**: (existing, repeated run after commit 225fdcc)
- **Expected files touched**: 0 (test run only)
- **Expected diff lines**: 0
- **Completion criteria**: ≥18/25 seams PASS
- **Note (2026-04-27)**: Binary upgraded to 1.14.28 — DeepSeek V4 models now in catalog with correct interleaved config. Previously V4 reasoning_content errors blocked agent execution; now resolved.

---

## Batch 24 — Wire LCN write + tier classifier into .opencode/tools/

- **Status**: unstarted
- **Tier**: Production
- **Depends on**: 23
- **Prompt file**: MagnumOpus/claude-code-prompt-24.md
- **Expected files touched**: 8
- **Expected diff lines**: ~450
- **Completion criteria**: `sqlite3 .opencode/.lcn/lcn.sqlite "SELECT
  COUNT(*) FROM entities"` returns 16 AND all new pytest tests pass

Rationale: gets the write-path and classifier living inside .opencode/
so subsequent batches can import them without path gymnastics. Verbatim
port of MagnumOpus/reference/ — no new code, just relocation + a
first-boot seeder + test suite.

---

## Batch 25 — Consult bridge (orchestrator + role hooks)

- **Status**: unstarted
- **Tier**: Enterprise (rule-4: edits .opencode/protocols/ implicitly
  via orchestrator spec + `new primary agent` language in role hooks)
- **Depends on**: 24
- **Prompt file**: MagnumOpus/claude-code-prompt-25.md (to be drafted)
- **Expected files touched**: 9 (orchestrator.md, 5 role agents,
  lcn_query.py, consult audit log module, tests)
- **Expected diff lines**: ~800
- **Completion criteria**: smoke-test run shows 3 consult entries in
  audit log per mission (pre-plan, pre-dispatch, post-verify), each
  tagged with query-type from CONSULT-PROTOCOL.md §query-types, and
  dispatched role prompts contain the "— injected by CONSULT-PROTOCOL
  v1" footer.

Rationale: this is the two-minds bridge going live. Without this,
batches 24 + 26 are dead weight (LCN has nothing reading from it).
Enterprise tier because it edits load-bearing protocols — rollback
tag before execution is mandatory.

---

## Batch 26 — janus.py self-hosting CLI

- **Status**: unstarted
- **Tier**: Production
- **Depends on**: 25
- **Prompt file**: MagnumOpus/claude-code-prompt-26.md (to be drafted)
- **Expected files touched**: 6 (janus.py + 4 command modules + tests)
- **Expected diff lines**: ~600
- **Completion criteria**: `python janus.py next` prints the path of
  the first unstarted unblocked batch in BACKLOG.md; `janus status`
  returns non-zero if tree is dirty; `janus seed` is idempotent;
  `janus smoke` runs the seam test and returns a seam count.

Rationale: the bootstrap moment. After this lands, Screwball's manual
work on each mission is curation, not authorship. `janus next` picks
the batch → he reviews + pastes into Claude Code. Two-tier human
control: BACKLOG edits (rare, deliberate) + batch approval (per-run).

---

## Batch 27 — Retrospective pipeline (Decisions + Errors → LCN)

- **Status**: unstarted
- **Tier**: Enterprise (touches protocols, new primary agent)
- **Depends on**: 25, 26
- **Prompt file**: MagnumOpus/claude-code-prompt-27.md (to be drafted)
- **Expected files touched**: 7 (.opencode/agent/retrospective.md,
  mission-journal schema, post-mission hook in orchestrator.md,
  retrospective tool module, tests)
- **Expected diff lines**: ~900
- **Completion criteria**: after a smoke-test mission finishes,
  `.opencode/.lcn/lcn.sqlite` has grown by ≥1 Decision entity; any
  step that produced a non-trivial failure has a matching Error
  entity with a closed-taxonomy failure_class.

Rationale: closes the learning loop. LCN stops being a seeded corpus
and starts accumulating from real missions. Enterprise tier — a bug
here poisons the knowledge base.

---

## Batch 28+ — deferred

- 28: second-project brain (shared LCN across repos) — Phase 6.1
- 29: Convention extraction from reviewer rejections (automatic)
- 30: Pattern entity generator from successful-mission clustering
- 31: Rollback tag automation (`janus rollback`)
- 32: Mission budget enforcement (per TIER-CLASSIFIER escalation rules)

These are on hold until batches 24–27 land and surface their real
dependency shape.
