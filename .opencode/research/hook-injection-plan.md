# Pre-Dispatch Consult Hook Injection Plan

**Purpose**: Design code-level changes that run `consult.py pre_dispatch` BEFORE any subagent handoff, making consult structurally enforced rather than optional.

**Mission**: OPENCODE-ARCH-2026-05-14 | **Feature**: F002 | **Depends on**: F001

## Design Decision

We implement an OpenCode **plugin** (TypeScript/Bun) that registers a `tool.execute.before` hook. When the `task` tool fires (subagent dispatch), the hook queries the LCN entity store and injects relevant patterns/errors into the subagent's prompt — _before_ the subagent LLM sees it.

**Why a plugin rather than patching the runtime:**
- The OpenCode hook system (`plugin.trigger("tool.execute.before", ...)`) already fires at `session/prompt.ts:753` — right before subagent spawn
- Plugins are dynamically loaded, require no TypeScript compilation of the OpenCode core
- A plugin can be distributed, versioned, and removed independently
- Graceful degradation is built-in: a failing hook doesn't block the tool

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Orchestrator calls task("explore", "find injection points")         │
│       │                                                               │
│       ▼                                                               │
│  session/prompt.ts:753                                                │
│  plugin.trigger("tool.execute.before", { tool: "task", ... },        │
│                 { args: { prompt, subagent_type, description } })    │
│       │                                                               │
│       ▼                                                               │
│  ┌──────────────────────────────────────────┐                        │
│  │  consult-plugin.ts (OUR PLUGIN)           │                        │
│  │                                            │                        │
│  │  1. Check: tool === "task" ?               │                        │
│  │  2. Extract: subagent_type, prompt         │                        │
│  │  3. Spawn: python consult.py pre_dispatch  │                        │
│  │            "<subagent_type>" "<model>"      │                        │
│  │  4. Parse JSON → patterns[], errors[]      │                        │
│  │  5. If results exist:                      │                        │
│  │     PREPEND to output.args.prompt:         │                        │
│  │     "⚠ CONSULT ADVISORY:\n                │                        │
│  │      Relevant patterns: ...\n              │                        │
│  │      Recent errors: ...\n                  │                        │
│  │      ---\n                                 │                        │
│  │      {original prompt}"                    │                        │
│  │  6. If consult fails: log, pass through    │                        │
│  └──────────────────────────────────────────┘                        │
│       │                                                               │
│       ▼                                                               │
│  taskTool.execute(mutated_taskArgs, ctx)  ← prompt now has advisory   │
│       │                                                               │
│       ▼                                                               │
│  ops.prompt({ sessionID, model, agent, parts: [mutated prompt] })    │
│       │                                                               │
│       ▼                                                               │
│  Subagent LLM receives handoff WITH consult context injected          │
└──────────────────────────────────────────────────────────────────────┘
```

## Injection Point

| Property | Value |
|----------|-------|
| **File** | `packages/opencode/src/session/prompt.ts` |
| **Line** | 753 |
| **Hook** | `tool.execute.before` |
| **Trigger condition** | `tool === "task"` (i.e., TaskTool.id) |
| **What we can modify** | `output.args.prompt` — the subagent's task description |
| **What we can read** | `output.args.subagent_type`, `output.args.description`, `input.sessionID` |

**Code context** (prompt.ts:747-757):
```typescript
const taskArgs = {
  prompt: task.prompt,
  description: task.description,
  subagent_type: task.agent,
  command: task.command,
}
yield* plugin.trigger(
  "tool.execute.before",
  { tool: TaskTool.id, sessionID, callID: part.id },
  { args: taskArgs },       // ← we MUTATE taskArgs.prompt here
)
// ... taskArgs is then passed directly to taskTool.execute(taskArgs, ...)
```

Since `taskArgs` is passed by reference, mutations to `output.args.prompt` (which is `taskArgs.prompt`) flow directly into the subagent dispatch.

## Plugin Implementation

### File: `~/.config/opencode/plugins/consult-plugin.ts`

```typescript
import type { Plugin, PluginInput } from "@opencode-ai/plugin"
import { join } from "path"

// Configuration — adjust for your system
const CONSULT_SCRIPT = join(process.cwd(), ".opencode", "tools", "consult.py")
const PYTHON_BIN = "python"  // or "python3" on some systems

interface ConsultResult {
  results: Array<{
    type: string
    entity_type: string
    summary: string
    natural_key: string
  }>
  status: "ok" | "degraded"
  reason?: string
}

const plugin: Plugin = async (input: PluginInput) => {
  return {
    "tool.execute.before": async (hookInput, output) => {
      // Only intercept the task tool (subagent dispatch)
      if (hookInput.tool !== "task") return

      const subagentType = output.args?.subagent_type ?? "unknown"

      try {
        // Run consult.py pre_dispatch
        const proc = Bun.spawnSync(
          [PYTHON_BIN, CONSULT_SCRIPT, "pre_dispatch", subagentType, "(model)"],
          { stdout: "pipe", stderr: "pipe" }
        )

        const stdout = await new Response(proc.stdout).text()
        const result: ConsultResult = JSON.parse(stdout)

        if (result.status !== "ok" || !result.results?.length) return

        // Build advisory block
        const errors = result.results.filter((r) => r.entity_type === "Error")
        const decisions = result.results.filter((r) => r.entity_type === "Decision")
        const conventions = result.results.filter((r) => r.entity_type === "Convention")

        const advisory = buildAdvisory(errors, decisions, conventions)

        // Prepend advisory to the subagent's prompt
        output.args.prompt = advisory + "\n---\n" + output.args.prompt

      } catch (err) {
        // Graceful degradation: log but don't block dispatch
        console.error("[consult-plugin] consult.py failed:", String(err))
        // Pass through — subagent dispatch continues normally
      }
    },
  }
}

function buildAdvisory(
  errors: ConsultResult["results"],
  decisions: ConsultResult["results"],
  conventions: ConsultResult["results"],
): string {
  const parts: string[] = ["## CONSULT ADVISORY (injected by consult-plugin)"]

  if (errors.length > 0) {
    parts.push("\n### Recent Related Errors")
    for (const e of errors.slice(0, 3)) {
      parts.push(`- [${e.entity_type}] ${e.summary}`)
    }
  }

  if (decisions.length > 0) {
    parts.push("\n### Past Decisions")
    for (const d of decisions.slice(0, 3)) {
      parts.push(`- ${d.summary}`)
    }
  }

  if (conventions.length > 0) {
    parts.push("\n### Applicable Conventions")
    for (const c of conventions.slice(0, 3)) {
      parts.push(`- ${c.summary}`)
    }
  }

  parts.push("\nFollow these patterns. Avoid repeating listed errors.")
  return parts.join("\n")
}

export default plugin
```

### Plugin Registration

Add to `~/.config/opencode/opencode.json`:

```json
{
  "plugin": [
    {
      "name": "consult-plugin",
      "path": "~/.config/opencode/plugins/consult-plugin.ts"
    }
  ]
}
```

Or place the file in `~/.config/opencode/plugins/consult-plugin.ts` — OpenCode auto-discovers plugins from `{plugin,plugins}/*.{ts,js}` directories.

## Consult Interface

### Input
```
python .opencode/tools/consult.py pre_dispatch "<agent_name>" "<model_name>"
```

### Output (example)
```json
{
  "results": [
    {
      "type": "error",
      "entity_type": "Error",
      "summary": "Reviewer on gemini-2.5-flash produced zero output",
      "natural_key": "reviewer:gemini-2.5-flash:zero-output"
    },
    {
      "type": "pattern",
      "entity_type": "Pattern",
      "summary": "Always run ruff before pytest",
      "natural_key": "pattern:ruff-before-pytest"
    }
  ],
  "status": "ok"
}
```

### Degraded Mode
```json
{
  "results": [],
  "status": "degraded",
  "reason": "LCN database not found"
}
```

The plugin treats `status: "degraded"` identically to empty results — pass through without modification.

## Graceful Degradation

| Failure Mode | Plugin Behavior |
|-------------|-----------------|
| `consult.py` not found | Log warning, pass through |
| Python not available | Log warning, pass through |
| consult.py exits non-zero | Log stderr, pass through |
| JSON parse fails | Log error, pass through |
| Output has `status: "degraded"` | Pass through |
| Output has empty `results` | Pass through |
| Unexpected exception | Catch all, log, pass through |

**Critical rule: consult failure MUST NOT block dispatch.** The hook is advisory. If it fails, the subagent still gets spawned with the original prompt.

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Python subprocess hangs | Medium | Use `Bun.spawnSync` with timeout (or async with AbortController) |
| consult.py performance impact | Low | Subprocess call is <100ms; SQLite queries are indexed |
| Plugin breaks OpenCode updates | Low | Plugin lives in user config, not in OpenCode core |
| Plugin conflicts with other plugins | Low | Hooks are sequential; our hook only modifies prompt text |
| Consult output is too large | Low | Limit to 3 items per entity type; advisory is compact |

## Verification

1. Create a test session with known LCN entities
2. Call the `task` tool for any subagent
3. Verify the subagent's prompt includes the advisory block
4. Verify consult failure does not prevent dispatch
5. Verify the plugin loads on OpenCode startup

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `~/.config/opencode/plugins/consult-plugin.ts` | Create | Plugin with `tool.execute.before` hook |
| `~/.config/opencode/opencode.json` | Modify | Register plugin in `plugin` array |
