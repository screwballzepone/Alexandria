# JANUS — Master Plan
**The Autonomous Developer Platform** (formerly "OpenCode" — renamed 2026-04-19)

> From "AI that helps you code" to "AI that runs your development process."

---

## Pre-pivot notice (2026-04-19)

This master plan predates the **two-minds pivot** and the **JANUS rename**. It remains the authoritative record of what got built in Phases 1-5 (all shipped) and the endgame vision, but it is no longer the canonical source for where we are headed next.

For post-pivot architecture and sequencing, read in order:

1. `TWO-MINDS.md` — the architectural lodestar (GENESIS + LCN, the five entity types, the three mandatory consults, the tier disclosure, the AGI definition)
2. `LCN-SCHEMA.md` — entity schema v1
3. `failure-classes.md` — bounded taxonomy v1
4. `CONSULT-PROTOCOL.md` — LCN read protocol v1
5. `TIER-CLASSIFIER.md` — capability assessor spec v1
6. `ROLE-HOOKS.md` — per-agent retrieval stanzas v1
7. `reference/lcn_write.py` — working reference implementation of the write module

The Phase 6+ sections below should be read as a **superset** — some items (multi-project brain, meta-learning) have been re-scoped under the two-minds contract; others (voice, visual understanding, team mode) are unchanged.

The sections below remain valuable as: (a) history of decisions and intent, (b) scaffolding for phases that haven't been re-scoped yet, (c) the endgame framing — "you describe a product, JANUS builds it while you sleep" — which is still the goal.

---

## Vision

OpenCode starts as a GUI wrapper around a CLI. It ends as a system that watches your GitHub,
decomposes features into work, writes the code, tests it, fixes failures, opens PRs, and
deploys — while you're asleep. Every phase below moves the needle on that goal.

---

## Current State (Phase 0 — Done)

- 7-agent pipeline: orchestrator, coder, nano-coder, explorer, architect, reviewer, prompt-writer
- Mission Autonomy System: mission.json DAG, blackboard.json, resume.json, healing protocol
- PySide6 GUI: async subprocess, agent pills, grouped model menu, Stats/MCP dialogs
- Drift guard on startup, SQLite long-term memory, session history loading

---

## Phase 1 — Bulletproof Core Loop
**Goal: Zero crashes, clean git history, structured review, automatic quality gates**

### 1.1 Structured Reviewer Feedback
Replace reviewer's prose output with a structured JSON format:
```json
{ "verdict": "request_changes",
  "issues": [
    { "file": "core/worker.py", "lines": "45-52", "severity": "error",
      "issue": "Race condition on queue access", "fix": "Add threading.Lock()" }
  ]
}
```
Coder reads this and patches exact locations instead of re-reading vague prose.
Reviewer becomes 3x more effective per token.

### 1.2 Automatic Quality Gate
After every coder pass, before reviewer is called:
- Run ruff (already installed)
- Run mypy if present
- Run pytest if present, capture output
Feed results to reviewer as context. Reviewer never approves code with lint failures.

### 1.3 Git Integration — Branch Per Feature
Every mission feature gets `feat/<mission-id>-<feature-id>`.
- Coder works on feature branch
- Reviewer approves on the branch
- Orchestrator merges to main after approval
- Failed features: branch deleted, main untouched
- GUI shows current branch in Mission tab

### 1.4 Auto-Commit with Generated Messages
After reviewer approval, nano-coder writes a commit message (50 tokens max):
`feat(auth): add JWT refresh token rotation with 15min expiry`
Committed automatically. Clean git history that maps 1:1 to mission DAG.

### 1.5 Error Classifier
Before healing retry attempts, a nano-coder call classifies the failure:
- `syntax` → coder retry with specific line
- `logic` → coder retry with test case attached
- `missing-context` → explorer first, then coder
- `environment` → check deps, paths, env vars
- `spec-gap` → escalate to user
3-attempt healing loop becomes targeted instead of escalating blindly.

---

## Phase 2 — Intelligent Memory
**Goal: The system gets smarter about your project every day it runs**

### 2.1 Vector Memory Store
Replace/augment SQLite with ChromaDB (local, no server needed).
Every session: file changes, reviewer comments, explorer findings, decisions get embedded.
Orchestrator queries: "what do we know about the auth module?" → ranked relevant memories.
Token budget drops because context is curated, not dumped.

### 2.2 Project Map
On first run in a new project, `onboarder` agent (one-time, thorough) generates:
```
.opencode/project-map.json
  - critical_files: [{ path, purpose, last_modified, owner_agent }]
  - entry_points: [...]
  - dependencies: { external: [], internal: [] }
  - known_gotchas: [...]
  - architecture_summary: "..."
```
Auto-updated by explorer after any structural change.
Orchestrator reads map instead of crawling blind every session.

### 2.3 User Model
`.opencode/user-model.json` — built from observations over time:
```json
{
  "style": { "prefers_functional": true, "hates_verbose_names": true, "test_first": false },
  "review_patterns": { "always_wants": ["error handling before happy path"],
                       "always_rejects": ["magic numbers", "bare except"] },
  "preferred_commit_style": "conventional",
  "domain_expertise": ["Python", "Qt", "multi-agent systems"]
}
```
All agents consult user-model before generating. Coder self-corrects against your patterns
before submitting. Reviewer weights issues by what you actually care about.

### 2.4 Cross-Session Learning
After each mission completes, a `lessons` agent writes to `.opencode/lessons.md`:
- What worked (agent, task type, approach)
- What failed and why
- Patterns discovered in this codebase
Orchestrator reads lessons at session start. Same mistake never made twice.

### 2.5 Blackboard Evolution
Add to blackboard.json:
- `timestamps` on every entry (stale after 20 turns = ignored)
- `confidence` scores (explorer can say "70% sure this is the right file")
- `conflicts` log (when two agents disagree, orchestrator sees it explicitly)

---

## Phase 3 — GENESIS: Full Autonomous PR Pipeline
**Goal: "describe feature" → mergeable PR, no human steps in between**

### 3.1 GENESIS Core
```
User describes feature
  → orchestrator classifies + creates mission
  → features execute with git branches
  → quality gate runs (lint + tests)
  → reviewer approves
  → nano-coder writes PR description
  → gh pr create runs automatically
  → PR posted with: what changed, why, test results, reviewer score
User reviews and merges
```

### 3.2 CI Feedback Loop
After PR is opened:
- System polls CI status (GitHub Actions / whatever is configured)
- If CI fails: healing protocol activates on the failing step
- System comments on PR with diagnosis
- Pushes fix commit
- Re-polls CI
You never see a PR with failing CI.

### 3.3 GitHub Issues → Missions
New mode: `issue-monitor` runs in background (or on demand).
- Pulls open unassigned issues
- Classifies by complexity: TINY / STANDARD / COMPLEX / SKIP
- For TINY/STANDARD: starts mission automatically
- For COMPLEX: flags for user input before starting
- Links mission to issue, closes issue when PR merges
You wake up to a set of draft PRs covering last night's backlog.

### 3.4 Mission Scheduler
`.opencode/schedule.json` — when to run what:
```json
{ "nightly": { "time": "02:00", "mode": "issue-queue", "budget": "$2.00" },
  "on-push": { "trigger": "main", "mode": "review-all" } }
```
Cost budget enforced. System stops when budget hit, writes resume.json.

---

## Phase 4 — Agent Expansion
**Goal: Every specialized task has a dedicated expert**

### 4.1 test-writer
Runs in parallel with architect. Writes failing tests BEFORE coder writes implementation.
Coder's goal becomes: make these tests pass.
Pure TDD. Reviewer validates tests are meaningful, not just passing.

### 4.2 security-auditor
Runs after every significant merge to main.
Not a general reviewer — laser focused on:
- Injection vectors
- Auth/authz bypass
- Secrets in code
- Dependency CVEs (checks pip-audit / npm audit)
- Known-bad patterns for the detected stack
Files security issues directly to GitHub with severity labels.

### 4.3 documenter
Watches what coder changes. After every approved commit:
- Updates docstrings for changed functions
- Updates relevant `docs/` files
- Updates AGENTS.md if agent configs changed
- Flags docs that reference deleted code
Zero documentation drift. `docs/` is always current.

### 4.4 dependency-scout
Runs weekly (or on demand).
- Checks for new versions of all dependencies
- Checks for breaking changes in minor bumps
- Checks for CVEs in current versions
- Proposes a `chore: bump dependencies` PR with changelog summary

### 4.5 performance-profiler
After coder ships a feature with performance implications:
- Instruments the relevant code with cProfile / py-spy
- Runs against a benchmark dataset
- Reads the profile output
- Files specific optimization suggestions back to blackboard
- On significant regression: blocks merge until coder addresses

### 4.6 onboarder
One-time agent for new codebases.
Explores everything, reads all entry points, traces all major flows.
Outputs: project-map.json, an `ONBOARDING.md` for humans, and a briefing
injected into every agent's context for the first 5 sessions.

### 4.7 meta-agent (the crown jewel — see Phase 5)

---

## Phase 5 — Self-Improvement
**Goal: The system trains itself on its own history**

### 5.1 Meta-Agent
After every mission, meta-agent runs a retrospective:
- Reads quality signals (accept/reject rates, retries, cost per agent)
- Identifies bottlenecks (which agent caused the most rework?)
- Proposes specific edits to that agent's `.md` file
- You approve or auto-apply

Over months: orchestrator prompt tightens, coder learns your conventions,
reviewer calibrates to your actual standards. The system compounds.

### 5.2 Eval System
`.opencode/evals/` — a suite of synthetic tasks with known correct outputs:
- "Add error handling to this function" → expected: specific patterns present
- "Refactor this loop" → expected: ruff passes, logic equivalent
- "Write a test for this function" → expected: test passes, covers edge cases

Meta-agent runs evals weekly. Tracks agent performance over time.
If an agent regresses after a prompt change: meta-agent rolls back the change.
You get a weekly "agent performance report" in the GUI.

### 5.3 Dynamic Model Routing
Meta-agent tracks cost × quality per agent per task type.
Builds a routing table: `{ "small_edit": "deepseek-chat", "architecture": "claude-opus-4-7", ... }`
Updates `.opencode/opencode.json` routing automatically.
You stop paying for Opus on tasks Flash handles fine.

### 5.4 Parallel Universe Coding
For high-stakes features: spawn 3 coder instances with different architectural approaches.
Reviewer scores all three: correctness / performance / maintainability / style match.
Orchestrator picks winner and writes a one-paragraph explanation of why.
You see the decision with the alternatives. Expensive, but worth it for critical paths.

---

## Phase 6 — Platform
**Goal: Multi-project, multi-modal, team-ready**

### 6.1 Multi-Project Brain
A global orchestrator managing N projects simultaneously.
- Project switcher in the GUI sidebar
- Shared vector memory across projects (cross-project pattern recognition)
- Global token budget split across projects by priority
- "This auth pattern worked in ProjectA — apply it here?" suggestions

### 6.2 Voice Interface
Stop typing. Talk to the orchestrator.
- Speech-to-text captures instruction
- `clarifier` agent rephrases into precise technical spec
- Reads it back: "I'll add JWT refresh token rotation to the auth module. Shall I proceed?"
- On confirmation: mission starts
For quick tasks: one sentence in, working code out.
For big ones: voice brainstorm → clarifier structures into mission DAG automatically.

### 6.3 Visual Understanding
Attach screenshots. Agents understand them.
- Screenshot of UI bug → explorer traces it to the relevant component
- Whiteboard photo of architecture diagram → architect turns it into a feature plan
- Error dialog screenshot → healing protocol activates directly
- Design mockup → coder scaffolds the component structure

### 6.4 Team Mode
Multiple users, shared project brain.
- Each user has their own agent preferences and user-model
- Shared blackboard and memory across the team
- Orchestrator knows who's best for what type of review
- Async collaboration: your agent starts a feature, colleague's agent reviews it 8 hours later
- Mission assignments: "assign auth feature to Lucas, UI feature to whoever is next"

### 6.5 Plugin System for Agents
Custom agents as installable plugins.
`.opencode/plugins/my-custom-agent/agent.md + tools/` structure.
Community can share specialized agents:
- `rails-expert` — knows Rails conventions deeply
- `sql-optimizer` — specializes in query optimization
- `accessibility-auditor` — WCAG compliance checking
Your setup is portable. Clone the repo, install plugins, full brain restored.

---

## Phase 7 — Runtime Intelligence
**Goal: The system monitors and heals production, not just development**

### 7.1 Log Monitoring
Connect to deployed services (via API key or log file).
`monitor` agent watches: error rates, response times, memory usage, exception patterns.
When anomaly detected: files incident to blackboard.
Orchestrator wakes up, explorer investigates the relevant code path.

### 7.2 Automated Hotfix Pipeline
Full incident → fix → deploy loop:
```
Anomaly detected
  → monitor files incident
  → explorer identifies root cause code
  → architect diagnoses (if complex)
  → coder writes targeted hotfix
  → test-writer adds regression test
  → quality gate runs
  → reviewer approves
  → GENESIS deploys to staging
  → monitor confirms anomaly resolved
  → deploys to production
```
An outage that takes a human 45 minutes gets fixed in 10 minutes automatically.
For critical incidents: pages you before deploying, shows the diff.

### 7.3 Performance Regression Detection
Every deployment: profiler runs baseline comparison.
If p95 latency increases >10%: blocks deployment, files issue, profiler investigates.
Your production performance only ever improves.

---

## Architecture Evolution Map

```
Phase 0  ──────────────────────────────────────────────────────────────────
         GUI + 7 agents + Mission protocol + SQLite memory

Phase 1  ──────────────────────────────────────────────────────────────────
         + Structured review format
         + Quality gate (ruff/pytest before reviewer)
         + Git branching per feature + auto-commit
         + Error classifier

Phase 2  ──────────────────────────────────────────────────────────────────
         + Vector memory (ChromaDB)
         + Project map (onboarder agent)
         + User model
         + Cross-session lessons
         + Smarter blackboard

Phase 3  ──────────────────────────────────────────────────────────────────
         + GENESIS: PR creation
         + CI feedback loop
         + GitHub issues → missions
         + Mission scheduler (overnight runs)

Phase 4  ──────────────────────────────────────────────────────────────────
         + test-writer agent (TDD)
         + security-auditor agent
         + documenter agent
         + dependency-scout agent
         + performance-profiler agent
         + onboarder agent

Phase 5  ──────────────────────────────────────────────────────────────────
         + meta-agent (self-improvement)
         + eval system
         + dynamic model routing
         + parallel universe coding

Phase 6  ──────────────────────────────────────────────────────────────────
         + multi-project brain
         + voice interface
         + visual understanding
         + team mode
         + agent plugin system

Phase 7  ──────────────────────────────────────────────────────────────────
         + runtime monitoring
         + automated hotfix pipeline
         + production performance guard
```

---

## Suggested Build Order

Start here → high value, low complexity:
1. **1.2 Quality Gate** — ruff auto-run before reviewer. One script call.
2. **1.5 Error Classifier** — nano-coder call before retry. One agent prompt edit.
3. **1.3 Git Branching** — `git checkout -b feat/...` in orchestrator prompt. Protocol change.
4. **1.4 Auto-Commit** — nano-coder commit message. One tool call.
5. **2.2 Project Map** — onboarder agent + project-map.json schema. High leverage.
6. **3.1 GENESIS Core** — `gh pr create` after reviewer approval. Pipeline already exists.
7. **1.1 Structured Review** — JSON format change to reviewer prompt. Big efficiency gain.
8. **2.1 Vector Memory** — ChromaDB, semantic context loading. Medium complexity.
9. **3.3 GitHub Issues → Missions** — GitHub API + classifier. Unlocks overnight autonomy.
10. **5.1 Meta-Agent** — the system starts improving itself. Long-term compound interest.

Everything after that is building toward the platform vision.

---

## The Endgame

You describe a product. OpenCode decomposes it, builds it feature by feature across nights and
weekends, keeps the codebase clean, the tests green, the docs current, and the PRs ready.
You make architectural decisions and do final reviews. The system does everything else.

That's the goal. Every phase above is a step toward it.
