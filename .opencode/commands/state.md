/state — Development state injection command

## Usage
- `/state` — dump full development state (current phase, decisions, blockers, test data)
- `/state --summary` — one-line status
- `/state --inject` — inject full state dump into the current context window

## What it does
Runs `python .opencode/tools/state_writer.py dump` and displays the structured
state directory contents: current.json (active phase/feature/branch), decisions.json
(design choices and rationale), blocked.json (open blockers), and history.jsonl
(recent modification log).

## Purpose
Replaces the lossy compression system. Instead of compressing conversation and losing
code state, development state is written to `.opencode/state/` and loaded via this
command. State is pull-based — the orchestrator loads what it needs, when it needs it.

## Integration
- Called automatically by orchestrator SESSION START
- Written by orchestrator on commit/decision/blocker
- Used by any agent that needs development context
