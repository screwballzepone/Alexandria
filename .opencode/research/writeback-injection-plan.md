# Write-Back Hook Injection Plan

**Purpose**: Design code-level changes that automatically write entity data (Decisions, Errors) to the LCN store after subagent task completion or session lifecycle events — without relying on the orchestrator LLM to remember.

**Mission**: OPENCODE-ARCH-2026-05-14 | **Feature**: F003 | **Depends on**: F001

## Design Decision

We implement a **dual-trigger** write-back system as part of the consult plugin:

1. **Primary**: `tool.execute.after` hook on `task` tool — fires after every subagent completes
2. **Secondary**: Bus event listener on `session.status` → `idle` — fires when session becomes idle (end of processing)

The write-back analyzes the subagent output, extracts structured entities (Decisions for completed work, Errors from failures), and writes them to the LCN SQLite store via `lcn_write.py`.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      WRITE-BACK TRIGGERS                              │
│                                                                       │
│  TRIGGER 1: tool.execute.after (task tool)                           │
│  ─────────────────────────────────────                                │
│  session/prompt.ts:832                                                │
│  plugin.trigger("tool.execute.after",                                 │
│    { tool: "task", sessionID, callID,                                 │
│      args: { subagent_type, description, prompt } },                  │
│    result: { title, output, metadata }                                │
│  )                                                                    │
│       │                                                               │
│       ▼                                                               │
│  ┌──────────────────────────────────────────┐                        │
│  │  WRITE-BACK LOGIC                         │                        │
│  │                                            │                        │
│  │  1. Extract: subagent_type, description,  │                        │
│  │     output text (result.output)            │                        │
│  │  2. Analyze output for structural signals  │                        │
│  │     - Did it complete? → Decision entity   │                        │
│  │     - Did it error? → Error entity         │                        │
│  │     - Is there a code pattern? → Pattern   │                        │
│  │  3. Build entity JSON payloads             │                        │
│  │  4. Spawn: echo '<json>' | python          │                        │
│  │            .opencode/tools/lcn_write.py    │                        │
│  │            write --stdin                    │                        │
│  │  5. On failure: log, continue               │                        │
│  └──────────────────────────────────────────┘                        │
│                                                                       │
│  TRIGGER 2: session.status → idle (bus event)                        │
│  ───────────────────────────────────────────                          │
│  session/status.ts:82                                                 │
│  bus.publish("session.status", { id, status: "idle" })               │
│       │                                                               │
│       ▼                                                               │
│  Plugin 'event' hook receives notification                            │
│       │                                                               │
│       ▼                                                               │
│  Flush accumulated entities for that session                          │
└──────────────────────────────────────────────────────────────────────┘
```

## Injection Points

### Primary: `tool.execute.after`

| Property | Value |
|----------|-------|
| **File** | `packages/opencode/src/session/prompt.ts` |
| **Line** | 832 |
| **Hook** | `tool.execute.after` |
| **Trigger condition** | `tool === "task"` |
| **What we can read** | `input.args` (subagent_type, description, prompt), `input.tool`, `input.sessionID` |
| **What we can modify** | `output.title`, `output.output`, `output.metadata` |

**Code context** (prompt.ts:832-836):
```typescript
yield* plugin.trigger(
  "tool.execute.after",
  { tool: TaskTool.id, sessionID, callID: part.id, args: taskArgs },
  result,  // { title, output, metadata, attachments }
)
```

`result.output` contains the subagent's full text output (from `runTask()` at `tool/task.ts:203`). `result.metadata` may contain structured data.

### Secondary: `session.status` bus event

| Property | Value |
|----------|-------|
| **File** | `packages/opencode/src/session/status.ts` |
| **Line** | 82 |
| **Mechanism** | `bus.publish("session.status", { id, status: "idle" })` |
| **How plugin receives it** | `event` hook on `Hooks` interface — all plugins receive all bus events |
| **Filter** | `event.type === "session.status" && event.properties.status === "idle"` |

## Entity Extraction from Subagent Output

The write-back analyzes the subagent output text for structured signals:

### Decision Entity
**When**: Subagent completed work successfully
**Detection**: Output contains structured completion markers OR tool calls succeeded
**Payload**:
```json
{
  "entity_type": "Decision",
  "workspace_path": "<cwd>",
  "summary": "Subagent: <type> completed: <description>",
  "natural_key": "decision:<sessionID>:<callID>",
  "outcome": "succeeded",
  "context_keywords": ["<subagent_type>", "<description keywords>"]
}
```

### Error Entity
**When**: Subagent failed or produced error output
**Detection**: 
- `result.output` contains error markers (`Error:`, `FAILED`, `Cannot`, etc.)
- `result.metadata` shows error state
- Or: no result returned (null/undefined)
**Payload**:
```json
{
  "entity_type": "Error",
  "workspace_path": "<cwd>",
  "summary": "Subagent <type> failed: <first-line-of-error>",
  "natural_key": "error:<sessionID>:<callID>",
  "error_type": "agent_stall",
  "context_keywords": ["<subagent_type>", "<model>"]
}
```

### Pattern Entity
**When**: Output contains code that matches known patterns
**Detection**: Heuristic — extract significant function/class names from output
**Payload**:
```json
{
  "entity_type": "Pattern",
  "workspace_path": "<cwd>",
  "summary": "Subagent <type> used pattern: <extracted pattern>",
  "natural_key": "pattern:<timestamp>:<short-hash>",
  "context_keywords": ["<extracted keywords>"]
}
```

## Plugin Implementation (Extension to consult-plugin.ts)

Add to `~/.config/opencode/plugins/consult-plugin.ts`:

```typescript
import type { Plugin, PluginInput } from "@opencode-ai/plugin"
import { join } from "path"

const CONSULT_SCRIPT = join(process.cwd(), ".opencode", "tools", "consult.py")
const LCN_WRITE_SCRIPT = join(process.cwd(), ".opencode", "tools", "lcn_write.py")
const PYTHON_BIN = "python"

const plugin: Plugin = async (input: PluginInput) => {
  // Accumulated entities waiting for session-idle flush
  const pendingWrites: Array<object> = []

  return {
    // === F002: Pre-dispatch consult ===
    "tool.execute.before": async (hookInput, output) => {
      if (hookInput.tool !== "task") return
      const subagentType = output.args?.subagent_type ?? "unknown"
      try {
        const proc = Bun.spawnSync(
          [PYTHON_BIN, CONSULT_SCRIPT, "pre_dispatch", subagentType, "(model)"],
          { stdout: "pipe", stderr: "pipe" }
        )
        const stdout = await new Response(proc.stdout).text()
        const result = JSON.parse(stdout)
        if (result.status === "ok" && result.results?.length > 0) {
          const advisory = buildAdvisory(result.results)
          output.args.prompt = advisory + "\n---\n" + output.args.prompt
        }
      } catch (err) {
        console.error("[consult-plugin] pre_dispatch failed:", String(err))
      }
    },

    // === F003: Write-back on subagent completion ===
    "tool.execute.after": async (hookInput, output) => {
      if (hookInput.tool !== "task") return

      const subagentType = hookInput.args?.subagent_type ?? "unknown"
      const description = hookInput.args?.description ?? "unknown task"
      const outputText = output.output ?? ""
      const sessionID = hookInput.sessionID

      try {
        // Analyze output for entity extraction
        const entities = extractEntities(subagentType, description, outputText, sessionID)

        if (entities.length === 0) return

        // Write immediately (not batched — write-back should be immediate)
        const payload = JSON.stringify(entities)
        const proc = Bun.spawnSync(
          [PYTHON_BIN, LCN_WRITE_SCRIPT, "write", "--stdin"],
          { stdin: Buffer.from(payload), stdout: "pipe", stderr: "pipe" }
        )

        if (proc.exitCode !== 0) {
          const stderr = await new Response(proc.stderr).text()
          console.error("[consult-plugin] lcn_write failed:", stderr)
        }
      } catch (err) {
        console.error("[consult-plugin] write-back failed:", String(err))
      }
    },

    // === F003 (secondary): Bus event for session idle ===
    "event": async (eventInput) => {
      const event = eventInput.event
      if (event.type !== "session.status") return
      if (event.properties?.status !== "idle") return

      // Session finished — flush any remaining writes
      // (Most writes happen immediately in tool.execute.after;
      //  this is a safety net for entities that couldn't be written earlier)
    },
  }
}

function extractEntities(
  subagentType: string,
  description: string,
  outputText: string,
  sessionID: string,
): Array<object> {
  const entities: Array<object> = []
  const timestamp = new Date().toISOString()

  // Decision: always write one per completed subagent task
  entities.push({
    entity_type: "Decision",
    workspace_path: process.cwd(),
    summary: `subagent:${subagentType}: ${description}`,
    natural_key: `decision:${sessionID}:${timestamp}`,
    outcome: "succeeded",
    context_keywords: [subagentType, ...description.split(/\s+/).slice(0, 5)],
    timestamp,
  })

  // Error detection: scan output for failure markers
  const errorLines = outputText.split("\n").filter((line) =>
    /error|failed|denied|rejected|timeout|abort/i.test(line)
  )
  if (errorLines.length > 0) {
    entities.push({
      entity_type: "Error",
      workspace_path: process.cwd(),
      summary: `subagent:${subagentType}: ${errorLines[0].substring(0, 200)}`,
      natural_key: `error:${sessionID}:${timestamp}`,
      error_type: detectErrorType(errorLines.join(" ")),
      context_keywords: [subagentType, "subagent-error"],
      timestamp,
    })
  }

  return entities
}

function detectErrorType(text: string): string {
  if (/stall|no output|zero output/i.test(text)) return "agent_stall"
  if (/permission denied/i.test(text)) return "reviewer_fail"
  if (/timeout/i.test(text)) return "tool_error"
  if (/not found/i.test(text)) return "tool_error"
  return "dispatch_fail"
}

export default plugin
```

## lcn_write.py Interface

### CLI Usage
```
echo '[{...}]' | python .opencode/tools/lcn_write.py write --stdin
```

### Input Format (JSON array on stdin)
```json
[
  {
    "entity_type": "Decision",
    "workspace_path": "/home/user/project",
    "summary": "subagent:explore: find injection points",
    "natural_key": "decision:ses_abc123:2026-05-14T12:00:00Z",
    "outcome": "succeeded",
    "context_keywords": ["explore", "injection", "points"]
  }
]
```

### Output
- Exit 0: entities written (or idempotently skipped)
- Exit non-zero: write failed (logged, not blocking)

## Entity Types Written

| Entity | When | Natural Key | Idempotency |
|--------|------|-------------|-------------|
| **Decision** | Every completed subagent task | `decision:<sessionID>:<timestamp>` | Overwrites on same key |
| **Error** | Subagent output contains error markers | `error:<sessionID>:<timestamp>` | Overwrites on same key |
| **Pattern** | (Future) Code pattern detected in output | `pattern:<timestamp>:<hash>` | Overwrites on same key |

## Graceful Degradation

| Failure Mode | Plugin Behavior |
|-------------|-----------------|
| `lcn_write.py` not found | Log warning, continue |
| Python not available | Log warning, continue |
| lcn_write.py exits non-zero | Log stderr, continue |
| JSON serialization fails | Log error, continue |
| DB locked | Log warning, retry once, continue |
| Unexpected exception | Catch all, log, continue |

**Critical rule: write-back failure MUST NOT affect subagent results.** The hook runs after the result has been captured. Write-back is fire-and-forget.

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Write-back is too noisy (writes Decision for every subagent) | Medium | Only write Decisions for non-trivial tasks; filter by output length |
| DB contention (multiple writes) | Low | SQLite WAL mode; writes are fast; idempotent keys prevent duplicates |
| Performance impact on subagent dispatch | Low | Write-back fires AFTER result is captured; non-blocking |
| Entity inflation over time | Low | Natural key idempotency prevents duplicates; DB can grow but queries are indexed |

## Verification

1. Run a session with subagent dispatch
2. After subagent completes, verify Decision entity appears in DB:  
   `sqlite3 ~/.local/share/opencode/lcn_memory.db "SELECT * FROM entities WHERE entity_type='Decision' ORDER BY created_at DESC LIMIT 1"`
3. Force a subagent error (e.g., invalid agent name)
4. Verify Error entity appears in DB
5. Verify write-back failure does not affect parent session output

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `~/.config/opencode/plugins/consult-plugin.ts` | Create/Modify | Plugin with `tool.execute.before` + `tool.execute.after` + `event` hooks |
| `~/.config/opencode/opencode.json` | Modify | Register plugin (shared with F002) |
