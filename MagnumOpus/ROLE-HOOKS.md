# ROLE-HOOKS.md — per-agent LCN retrieval stanzas

**Authority**: TWO-MINDS.md §3.5, CONSULT-PROTOCOL.md §Mandatory consult injection.

**Version**: v1 (2026-04-19).

---

## Purpose

Each participating agent prompt gets a **"Before acting"** stanza that names its role-specific LCN queries. These are **additive** to the three mandatory consults that fire automatically from the orchestrator (pre-plan, pre-dispatch, post-verify). The hooks do not duplicate those consults; they extend them with role-specific signal the orchestrator can't know to inject generically.

The stanzas live at the **bottom** of each agent file, after all existing sections. They are the last thing the agent reads before beginning work. Do not interleave with the body of the prompt.

---

## How to apply

For each agent below, append the exact stanza (inside the code fence) to the end of the named file. Preserve markdown formatting. Do not add explanatory preamble — the stanza IS the preamble for the agent.

When rolling out: apply to one agent, run the next smoke test, inspect LCN consult hit rate in the audit log, adjust if needed, then apply the next. Rolling out all five at once is faster but makes attribution harder when something goes sideways.

---

## architect (`.opencode/agent/architect.md`)

```
## Before acting

Your mission is to design. Before producing the plan, consult LCN:

1. `by-convention-scope` on the architectural scope you are touching (e.g.,
   `.opencode/agent/*`, `.opencode/tools/*`, `.opencode/protocols/*`). Any
   Convention in that scope constrains your plan.
2. `by-mission-similarity` on your mission title and predicted scope_hash.
   Prior missions that did similar architectural work are training signal.

Integrate results into your plan:
- Every Convention returned MUST be addressed. Either the plan respects it,
  or the plan includes a deliberate-deviation rationale naming the
  Convention by its rule.
- Prior missions with outcome=failed get special weight — name what they
  tried and why it failed, and why your plan avoids the same trap.
- Empty results mean architectural novelty. Do not invent confidence;
  annotate the novelty in your plan and recommend Enterprise-tier review
  if the classifier hasn't already escalated.

— hook: ROLE-HOOKS v1
```

---

## coder (`.opencode/agent/coder.md`)

```
## Before acting

Your mission is to implement. Before editing any file on your plan:

1. For each file, `by-file` with entity_types=["Decision", "Pattern", "Convention"].

Integrate results:
- Conventions on the file constrain your implementation. Violating one
  requires deliberate-deviation reasoning in your commit message, named to
  the specific rule.
- Patterns on the file show the shape that has worked before. Prefer
  matching the Pattern to inventing a new shape. Inventing a new shape is
  allowed but requires explanation.
- Decisions on the file show recent directional choices. Do not contradict
  them without explicit rationale.
- Empty results mean the file is virgin territory in LCN. Your diff may
  become the seed Pattern for the next mission — write it cleanly.

— hook: ROLE-HOOKS v1
```

---

## reviewer (`.opencode/agent/reviewer.md`)

```
## Before acting

Your mission is to critique. Before reviewing the diff, for each file changed:

1. `by-file` with entity_types=["Pattern", "Convention"].
2. `by-failure-class` on the most likely class given the diff shape. The
   usual suspects:
   - large refactor → `edit-shape-error`, `convention-violation`
   - new sub-system → `agent-frontmatter-ignored`, `invented-tool`
   - CI/test touching → `ci-flake-vs-real`
   - model/routing config → `model-routing`

Integrate results into your verdict:
- Every Convention on a touched file: respected, or deliberately deviated
  with rationale? Call out either answer in the verdict.
- Patterns on touched files: does the diff use the Pattern, or introduce
  a new shape? A new shape repeated >2 times in the diff SHOULD be flagged
  for Pattern extraction in the post-verify write.
- Known failure-class pitfalls: does the diff risk any of them? If yes,
  surface with specific line references in the issues[] array.

— hook: ROLE-HOOKS v1
```

---

## test-writer (`.opencode/agent/test-writer.md`)

```
## Before acting

Your mission is to write or update tests. Before proposing tests:

1. `by-failure-class` with class="ci-flake-vs-real", limit=10. History of
   flakes helps you write tests that do not become the next flake.
2. For each file under test, `by-file` with entity_types=["Pattern",
   "Convention"]. Testing patterns ARE Patterns.

Integrate results:
- If a Convention in scope says "tests MUST X" (e.g., "integration tests
  must hit a real database, not mocks"), respect it — do not justify
  divergence with convenience.
- If a prior ci-flake-vs-real Error shows a known intermittent pattern
  (time-dependent, order-dependent, IO-dependent), structure your new
  tests to avoid the same shape, and note in the test docstring that this
  is intentional.
- Empty flake-history does NOT mean "no flake risk." It means "no known
  history on this path." Add determinism guards by default.

— hook: ROLE-HOOKS v1
```

---

## security-auditor (`.opencode/agent/security-auditor.md`)

```
## Before acting

Your mission is to find security issues. Before scanning:

1. `by-failure-class` with class="consult-skipped" AND class="convention-
   violation" on recent missions touching related scopes. Security
   failures often ride on earlier process failures — skipped consults
   tend to correlate with unchecked inputs.
2. `by-convention-scope` on security-adjacent scopes in the diff (auth,
   secrets, input-validation, network-edge, any scope Conventions have
   tagged as security-relevant).

Integrate results:
- Prior security-related convention violations are high-leverage patterns
  — check the current diff for recurrence of the same shape, not just
  the same file.
- If the diff touches a file whose Convention list includes a security
  rule, verify compliance explicitly in your audit output. No implicit
  passes.
- Empty results do NOT mean "no security concerns." They mean "no known
  history of concerns on this path," which actually INCREASES audit
  depth — novel surfaces have the weakest priors.

— hook: ROLE-HOOKS v1
```

---

## Agents deliberately NOT hooked (for now)

- **memory-writer** — writes LCN, does not read it. No hook needed; its whole purpose is the other direction of the arrow.
- **nano-coder** — handles trivial edits that classify MVP. MVP tier has no mandatory consults, so a hook would add overhead without payoff. Re-evaluate if nano-coder starts handling non-MVP work.
- **explorer**, **documenter**, **dependency-scout**, **onboarder**, **lessons** — participate in narrower workflows. Hooks will be specified when each enters the primary mission flow or when we have one data point of value from their unhookecd behavior.
- **meta-agent** — self-modification. Needs special-case treatment. A hook that lets meta-agent read LCN before rewriting orchestrator prompts is high-leverage but also high-risk; design separately once the other hooks have one smoke cycle of data.
- **orchestrator** — the orchestrator IS what injects the three mandatory consults. It does not need an additional "before acting" stanza because it has no "acting" to do that isn't covered by its dispatch logic.

---

## Verification (post-rollout)

After each agent is hooked:

1. Run a mission that touches at least one file the agent reviews/implements/tests.
2. Inspect the mission audit log for consult entries matching the agent's stanza queries.
3. Confirm the agent's output (review verdict, code diff, test file) references at least one LCN result by entity id OR explicitly annotates a recall miss.
4. If neither: the hook is not being read. Debug before rolling out the next agent.

Hook rollout is complete when all five hooked agents show >80% consult-fire rate on Production+ missions, measured over a rolling 10-mission window.

---

## Open questions

- **Prompt-length budget.** Each stanza adds 150-250 tokens to the agent's context. Across five agents over many missions this is material. Measure after rollout; compress if needed, but not preemptively — clarity matters more than token budget at this stage.
- **What happens when the same file's Conventions contradict each other?** Should be rare (Conventions are supposed to be settled) but can happen mid-transition. Working answer: surface both and let the critic call it; file a Convention-vs-Convention Error for the meta-agent to reconcile.
- **Cross-role leakage.** Should the reviewer read the coder's LCN consult results, or only its own? Leaning "own only," to keep retrieval roles separate. But it's worth checking whether reviewer queries frequently duplicate coder queries; if so, caching at the mission level would help.
