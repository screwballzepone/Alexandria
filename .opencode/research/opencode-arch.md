# OpenCode CLI Architecture Map

**Purpose**: Complete architecture analysis of the OpenCode CLI (`opencode-dev/packages/opencode/src/`) to find native injection points for the consult entity system.

**Generated**: 2026-05-14 | **Mission**: OPENCODE-ARCH-2026-05-14 | **Feature**: F001

## Executive Summary

OpenCode CLI is a TypeScript application built on Effect-TS (functional effect system) and the Vercel AI SDK. It uses event sourcing (CQRS) with SQLite for persistence, a plugin hook chain for extensibility, and a session-based architecture where the orchestrator agent dispatches subagents via a `task` tool.

The subagent dispatch follows this pipeline:

```
Orchestrator LLM → calls task() tool → task.ts creates child session → 
SessionPrompt.prompt() → SessionProcessor.process() → LLM.stream() → 
Vercel AI SDK streamText()
```

Three interception systems exist: **Plugin Hooks** (primary, active), **Bus Events** (notification), and **Sync Events** (CQRS persistence).

---

## 1. Subagent Dispatch Pipeline

### 1.1 The Task Tool (`tool/task.ts`)

The `task` tool is defined via `Tool.define("task", ...)` and registered in ToolRegistry. When an orchestrator agent wants to dispatch work:

| Step | Location | What Happens |
|------|----------|-------------|
| 1. LLM calls `task()` | `tool/task.ts:107` | `execute(params, ctx)` entry point |
| 2. Permission check | `tool/task.ts:120` | `ctx.ask(...)` — user approval gate |
| 3. Resolve agent | `tool/task.ts:131` | `agent.get(params.subagent_type)` — loads agent definition |
| 4. Create child session | `tool/task.ts:144-161` | `sessions.create()` with `parentID: ctx.sessionID` |
| 5. Resolve model | `tool/task.ts:166-169` | Subagent's pinned model ?? parent message model |
| 6. Build tools | `tool/task.ts:172-184` | Filter tools by subagent permissions |
| 7. **Execute LLM** | `tool/task.ts:188-204` | `ops.prompt({ sessionID, model, agent, tools, parts })` |
| 8. Return result | `tool/task.ts:53-61` | Wraps output in `<task_result>` XML tags |

**Key injection point**: `tool/task.ts:188` — the `ops.prompt()` call. `ops` is the `TaskPromptOps` interface injected at tool resolution time. The actual implementation is `SessionPrompt.prompt()`.

### 1.2 Agent Loading (`agent/agent.ts`)

Built-in agents are hardcoded (line 126-278):
- `build` (primary, all permissions, native)
- `plan` (primary, read-only)
- `general` (subagent, general multi-step)
- `explore` (subagent, grep/glob/bash/read)
- `compaction`, `title`, `summary` (primary, hidden)
- `scout` (subagent, experimental)

User-defined agents from `cfg.agent` are merged at line 280-307.

Each agent has a `permission` ruleset and optional `model` (pinned provider/modelID).

### 1.3 Model Resolution (`provider/provider.ts`)

- `getModel(providerID, modelID)` — resolves model definition from catalog
- `getLanguage(model)` — instantiates AI SDK `LanguageModelV3`
- Providers loaded dynamically from npm packages (`@ai-sdk/*`) 
- Custom providers configurable via `opencode.json#provider`

### 1.4 The LLM Call Chain

```
task.ts:188  ops.prompt({...})
     ↓
prompt.ts:1614  SessionPrompt.prompt() — creates user message
     ↓
prompt.ts:1632  SessionPrompt.loop() — enters run loop
     ↓
prompt.ts:1821  handle.process({ user, agent, system, messages, tools, model })
     ↓
processor.ts:745  llm.stream(streamInput)
     ↓
llm.ts:407-421  LLM.stream() — wraps run() in Stream.scoped
     ↓
llm.ts:325-404  streamText({ model, messages, tools, ... })  ← Verceal AI SDK
```

### 1.5 Permission Filtering

- `deriveSubagentSessionPermission()` (`agent/subagent-permissions.ts:17-34`): copies parent's edit-denies + session denies + disables todowrite/task unless allowed
- Tool filtering per agent in `tool/registry.ts` based on permissions + provider/model capabilities

---

## 2. Plugin / Hook System

### 2.1 Hook Types (All Interception Points)

Defined in `packages/plugin/src/index.ts` `Hooks` interface:

| Hook | Fires When | Modify Target | Pre/Post Dispatch? |
|------|-----------|---------------|---------------------|
| `tool.execute.before` | Before any tool executes | `output.args` | **PRE** — best injection point |
| `tool.execute.after` | After any tool completes | `output.title`, `output.output`, `output.metadata` | **POST** — best write-back point |
| `chat.params` | Before LLM API call | temperature, topP, options | PRE |
| `chat.headers` | Before LLM API call | HTTP headers | PRE |
| `experimental.chat.system.transform` | Before LLM call | `system[]` prompt array | PRE |
| `experimental.chat.messages.transform` | Before LLM call | `messages[]` array | PRE |
| `experimental.text.complete` | After text generation | `output.text` | POST |
| `experimental.session.compacting` | Before compaction | `context[]`, `prompt` | — |
| `shell.env` | Before shell execution | Environment variables | PRE |
| `tool.definition` | Tool registration | Tool descriptions | PRE |
| `command.execute.before` | Before slash command | `parts` | PRE |
| `chat.message` | After user message received | `output.message`, `output.parts` | POST |
| `permission.ask` | **(Defined but never triggered!)** | `status` | PRE |

### 2.2 `tool.execute.before` Trigger Locations

| File | Line | Context |
|------|------|---------|
| `session/prompt.ts` | 581 | Built-in tools — CAN MODIFY `output.args` |
| `session/prompt.ts` | 622 | MCP tools — CAN MODIFY `output.args` |
| `session/prompt.ts` | **753** | **Subagent `task` tool — fires BEFORE subagent spawns** |

**This is the #1 injection point for pre-dispatch consult.** At `prompt.ts:753`, we can:
1. Detect `tool === "task"` 
2. Read the subagent type and prompt from `input.args`
3. Run `python .opencode/tools/consult.py pre_dispatch <agent> <model>`
4. Prepend consult findings to `output.args.prompt`

### 2.3 `tool.execute.after` Trigger Locations

| File | Line | Context |
|------|------|---------|
| `session/prompt.ts` | 597 | Built-in tools |
| `session/prompt.ts` | 641 | MCP tools |
| `session/prompt.ts` | **833** | **Subagent `task` tool — fires AFTER subagent completes** |

**This is the #1 injection point for write-back.** At `prompt.ts:833`, we can:
1. Detect `tool === "task"`
2. Access subagent output from `input.output`
3. Run entity write-back via `python .opencode/tools/lcn_write.py`

### 2.4 Plugin Registration

Plugins are loaded from:
1. Internal hardcoded list (`plugin/index.ts:60-69`) — auth plugins
2. `opencode.json#plugin` array — external plugin specs
3. `{plugin,plugins}/*.{ts,js}` directories — file-based plugins
4. Tool directories `{tool,tools}/*.{ts,js}` — custom tool plugins

### 2.5 `plugin.trigger()` Mechanism

`plugin/index.ts:261-274` — iterates all loaded hooks, calls each matching handler sequentially with mutable input/output objects. Hooks can modify output in place.

---

## 3. Session Lifecycle

### 3.1 State Machine

| State | Trigger |
|-------|---------|
| `idle` → `busy` | `processor.ts:232` on stream start |
| `busy` → `idle` | `processor.ts:733` on halt, or `run-state.ts:61` on runner complete |
| `any` → `retry` | `processor.ts:784` on retryable error |
| `busy` → `idle` | `run-state.ts:81` on cancel |

Status changes publish to `session.status` bus event.

### 3.2 Session Creation (`session/session.ts`)

- `create()` (line 678): public API, fires `Session.Event.Created` sync event
- `fork()` (line 678): copies messages from source, creates new session
- CLI trigger: `cli/cmd/run.ts:430-465`

### 3.3 Session Cleanup / Close

- `remove(sessionID)` (line 594): cancels background jobs, recursively removes children, fires `Event.Deleted`
- CLI lifecycle: `cli/cmd/run/runtime.lifecycle.ts:251-301` — `close()` writes exit splash, tears down UI
- **No automatic "session close" event exists** — sessions persist in DB unless explicitly removed
- `processor.ts:797` — `Effect.ensuring(cleanup())` runs on success, error, or interrupt

### 3.4 Persistence (Event Sourcing)

All state changes go through `sync/index.ts`:
1. `sync.run(event)` — opens transaction, increments sequence, runs projector
2. Projector writes to SQLite tables (`SessionTable`, `MessageTable`, `PartTable`)
3. Publishes to bus for real-time subscribers

### 3.5 Bus Events (Notifications)

| Event | Defined In | Subscribers |
|-------|------------|-------------|
| `session.status` | `session/status.ts:35` | Stream transport, UI footer |
| `session.idle` | `session/status.ts:43` (deprecated) | Stream transport |
| `session.diff` | `session/session.ts:352` | UI, share service |
| `session.error` | `session/session.ts:359` | UI, share service |
| `session.compacted` | `session/compaction.ts:28` | — |
| `global.disposed` | `server/global-lifecycle.ts:19` | Shutdown notification |

---

## 4. Injection Point Candidates (Ranked)

### TIER 1: Best (surgical, low risk)

| Rank | Injection Point | File:Line | For | Why |
|------|----------------|-----------|-----|-----|
| **#1** | `tool.execute.before` on task | `session/prompt.ts:753` | F002 (pre-dispatch) | Fires right before subagent spawns, can modify args, has access to subagent type + prompt |
| **#2** | `tool.execute.after` on task | `session/prompt.ts:833` | F003 (write-back) | Fires right after subagent completes, has access to full output |
| **#3** | `session.status` bus event → `idle` | `session/status.ts:35` | F003 (write-back) | Signals session completion, can trigger entity flush |

### TIER 2: Good (broader scope, more risk)

| Rank | Injection Point | File:Line | For | Why |
|------|----------------|-----------|-----|-----|
| **#4** | `experimental.chat.system.transform` | `session/llm.ts:118` | F002 | Can inject into system prompt for every LLM call |
| **#5** | `experimental.chat.messages.transform` | `session/prompt.ts:1810` | F002 | Can inject into message history |
| **#6** | `chat.params` | `session/llm.ts:161` | F002 | Can modify LLM parameters |
| **#7** | `Effect.ensuring(cleanup())` | `processor.ts:797` | F003 | Guaranteed to run on session end |
| **#8** | Session `remove()` | `session/session.ts:594` | F003 | Explicit session deletion trigger |

### TIER 3: Experimental (needs code changes to the runtime itself)

| Rank | Injection Point | File:Line | For | Why |
|------|----------------|-----------|-----|-----|
| **#9** | `permission.ask` hook trigger | `permission/index.ts:161` | F002 | Hook defined but never triggered — needs runtime patch |
| **#10** | Direct task.ts modification | `tool/task.ts:188` | F002 | Modify `runTask()` to call consult before `ops.prompt()` |

---

## 5. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SUBAGENT DISPATCH FLOW                            │
│                                                                          │
│  Orchestrator LLM                                                        │
│       │                                                                  │
│       │ calls task(description, prompt, subagent_type)                   │
│       ▼                                                                  │
│  ┌─────────────┐     ┌──────────────────┐                               │
│  │ task.ts:107  │────▶│ Permission Check │                               │
│  │ execute()    │     │ task.ts:120      │                               │
│  └─────────────┘     └──────────────────┘                               │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────┐                                                     │
│  │ Resolve Agent    │  agent/agent.ts:310-323                            │
│  │ Resolve Model    │  tool/task.ts:166-169                              │
│  │ Create Session   │  tool/task.ts:144-161 → session/session.ts:678     │
│  │ Filter Tools     │  tool/task.ts:172-184                              │
│  └─────────────────┘                                                     │
│       │                                                                  │
│       │ ╔═══════════════════════════════════════════════╗                │
│       │ ║  ★ INJECTION POINT #1: tool.execute.before   ║                │
│       │ ║  session/prompt.ts:753                        ║                │
│       │ ║  Can modify output.args (prompt, agent, etc)  ║                │
│       │ ╚═══════════════════════════════════════════════╝                │
│       ▼                                                                  │
│  ┌─────────────────┐                                                     │
│  │ ops.prompt()     │  tool/task.ts:188                                  │
│  │ = SessionPrompt  │  → prompt.ts:1614                                  │
│  │   .prompt()      │                                                    │
│  └─────────────────┘                                                     │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────┐     ┌──────────────────┐                           │
│  │ SessionPrompt    │────▶│ resolveTools()    │  prompt.ts:521-699       │
│  │ .loop()          │     │ (permission check)│                           │
│  └─────────────────┘     └──────────────────┘                           │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────┐                                                     │
│  │ Processor        │  processor.ts:736-804                              │
│  │ .process()       │  handles stream events                             │
│  └─────────────────┘                                                     │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────┐                                                     │
│  │ LLM.stream()     │  llm.ts:325-404                                    │
│  │ = streamText()   │  Vercel AI SDK                                     │
│  └─────────────────┘                                                     │
│       │                                                                  │
│       │ (subagent runs, produces output)                                 │
│       ▼                                                                  │
│  ┌─────────────────┐                                                     │
│  │ task result      │  tool/task.ts:53-61                                │
│  │ <task_result>    │                                                    │
│  └─────────────────┘                                                     │
│       │                                                                  │
│       │ ╔═══════════════════════════════════════════════╗                │
│       │ ║  ★ INJECTION POINT #2: tool.execute.after    ║                │
│       │ ║  session/prompt.ts:833                        ║                │
│       │ ║  Can access output for entity write-back      ║                │
│       │ ╚═══════════════════════════════════════════════╝                │
│       ▼                                                                  │
│  Return to orchestrator                                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

## 6. Key Constraints

- **No Runtime Modification Needed**: The existing plugin hook system (`tool.execute.before/after`) provides the interception points we need. We do NOT need to modify OpenCode's TypeScript source — we build a plugin.
- **Python Subprocess**: The plugin runs in Bun/Node.js. Calling Python scripts (`consult.py`, `lcn_write.py`) requires `Bun.spawn()` or `child_process.execSync()`.
- **Graceful Degradation Required**: Consult failures must not block dispatch. The plugin must catch errors and pass through.
- **Plugin Must Be Loaded**: The plugin needs to be registered in the global `~/.config/opencode/opencode.json` under `plugin` array, or placed in the `{plugin,plugins}/` directory.
- **Permissions**: The plugin won't need special permissions — it's running code, not calling tools.

## 7. Files Referenced

| File | Purpose |
|------|---------|
| `tool/task.ts` | Task tool definition, `execute()`, `runTask()` |
| `tool/registry.ts` | Tool registration, permission filtering |
| `agent/agent.ts` | Agent definitions, model routing |
| `agent/subagent-permissions.ts` | Subagent permission derivation |
| `session/prompt.ts` | Main prompt lifecycle, `tool.execute.before/after` triggers |
| `session/llm.ts` | LLM API call, `chat.params`, `system.transform` triggers |
| `session/processor.ts` | Stream processor, cleanup, status transitions |
| `session/session.ts` | Session CRUD, create/remove/fork |
| `session/status.ts` | Session status state machine |
| `session/compaction.ts` | Compaction triggers |
| `plugin/index.ts` | Plugin loader, `trigger()` |
| `plugin/src/index.ts` | `Hooks` interface (plugin package) |
| `provider/provider.ts` | Model/provider resolution |
| `permission/index.ts` | Permission.ask() gate |
| `bus/index.ts` | Event bus, publish/subscribe |
| `sync/index.ts` | Event sourcing, projectors |
