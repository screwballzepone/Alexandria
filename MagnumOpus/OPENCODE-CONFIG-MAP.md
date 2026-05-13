# OPENCODE-CONFIG-MAP
> Machine-specific model-routing reference for `C:\Users\lukas\OneDrive\Documentos\OpenCode`
> Generated: 2026-04-24 | OpenCode v1.4.6 | Source: forensic discovery session
> **⚠ Updated: 2026-04-27** — Binary upgraded to 1.14.28, model pivoted to deepseek-v4-flash, V4 reasoning_content fixed. See update notes inline.

---

## 1. Config files actually loaded

### Load order (from `packages/opencode/src/config/paths.ts`)

Config directories are collected in this order; within each directory `config.json` →
`opencode.json` → `opencode.jsonc` are merged. **Last file wins** for scalar fields
(`model`, `small_model`). Objects (`provider`, `agent`) deep-merge.

```
1. C:\Users\lukas\.config\opencode\          ← XDG global (Global.Path.config on this machine)
2. <session-dir>\.opencode\  …walk up…       ← project hierarchy (deepest first)
3. C:\Users\lukas\.opencode\                 ← user-home
4. %OPENCODE_CONFIG_DIR%\                    ← env-var override (not set)
```

> **Windows note:** On this machine xdg resolves to `~/.config/` not `%APPDATA%`.
> Confirmed from live server startup log (2026-04-24):
> `service=config path=C:\Users\lukas\.config\opencode\config.json loading` (not APPDATA).

### Files on disk right now

| Path | Size | Exists | `model` | `small_model` | Notes |
|---|---|---|---|---|---|
| `C:\Users\lukas\.config\opencode\config.json` | — | ✗ | — | — | XDG global slot 1 |
| `C:\Users\lukas\.config\opencode\opencode.json` | — | ✗ | — | — | XDG global slot 2 |
| `C:\Users\lukas\.config\opencode\opencode.jsonc` | — | ✗ | — | — | XDG global slot 3 |
| `.opencode\opencode.json` (project) | 4 798 B | ✓ | `cerebras/qwen-3-235b-a22b-instruct-2507` | `cerebras/qwen-3-235b-a22b-instruct-2507` | also defines cerebras custom provider |
| `C:\Users\lukas\.opencode\opencode.json` (user-home) | 515 B | ✓ | *(absent)* | *(absent)* | provider option blocks only |
| `C:\Users\lukas\.local\share\opencode\auth.json` | 474 B | ✓ | — | — | API keys: google, deepseek, openrouter, anthropic. **No cerebras entry** (cerebras uses `{env:CEREBRAS_API_KEY}`) |
| `C:\Users\lukas\AppData\Roaming\opencode\` | — | ✗ | — | — | APPDATA slot absent |

**Effective merged values (after full load, as of 2026-04-24):**

| Field | Value | Source |
|---|---|---|
| `model` | `cerebras/qwen-3-235b-a22b-instruct-2507` | project config (user-home does not override) |
| `small_model` | `cerebras/qwen-3-235b-a22b-instruct-2507` | project config (user-home does not override) |
| `default_agent` | `orchestrator` | project config |

**⚠ 2026-04-27 update:** After V4 pivot, effective values are now:

| Field | Value | Source |
|---|---|---|
| `model` | `deepseek/deepseek-v4-flash` | project config (opencode.json) |
| `small_model` | `deepseek/deepseek-v4-flash` | project config (opencode.json) |
| `default_agent` | `orchestrator` | project config |
| Binary | `opencode-ai@1.14.28` | global npm (C:\Users\lukas\AppData\Roaming\npm) — V4 models in embedded catalog, interleaved config correct |

---

## 2. Agents and their model resolution

### Custom agents (`.opencode/agent/`)

| Agent file | Frontmatter `model:` | Effective routing |
|---|---|---|
| `orchestrator.md` | `cerebras/qwen-3-235b-a22b-instruct-2507` (04-24) → **`deepseek/deepseek-v4-flash`** (04-27) | DeepSeek V4 ✓ |
| `architect.md` | `cerebras/qwen-3-235b-a22b-instruct-2507` | Cerebras ✓ |
| `explorer.md` | `openrouter/x-ai/grok-4.20-beta` | OpenRouter → Grok |
| `reviewer.md` | `deepseek/deepseek-chat` | DeepSeek |
| `test-writer.md` | `deepseek/deepseek-chat` | DeepSeek |
| `nano-coder.md` | `deepseek/deepseek-chat` | DeepSeek |
| `documenter.md` | `deepseek/deepseek-chat` | DeepSeek |
| `lessons.md` | `deepseek/deepseek-chat` | DeepSeek |
| `meta-agent.md` | `deepseek/deepseek-chat` | DeepSeek |
| `onboarder.md` | `deepseek/deepseek-chat` | DeepSeek |
| `security-auditor.md` | `deepseek/deepseek-chat` | DeepSeek |
| `dependency-scout.md` | `deepseek/deepseek-chat` | DeepSeek |
| `coder.md` | ⚠ **MISSING** (file deleted) | — |
| `prompt-writer.md` | ⚠ **MISSING** (file deleted) | — |

### Built-in agents (defined in `packages/opencode/src/agent/agent.ts`)

| Agent | Frontmatter | How model resolves | Current result |
|---|---|---|---|
| `title` | `hidden: true`, `temperature: 0.5`, **no `model` field** | `getSmallModel(session.providerID)` (see §3) | `cfg.small_model` → Cerebras ✓ |
| `coder` | Built-in (not in `.opencode/agent/`) | `getSmallModel(session.providerID)` | `cfg.small_model` → Cerebras ✓ |

> The `title` agent has no per-agent model override in project config. It relies entirely
> on `cfg.small_model`. This is the historical leak vector (see §4).

---

## 3. Model resolution precedence

### For primary session startup

```
1. CLI --model flag                         ← absolute highest priority; overrides everything
2. cfg.model from merged config             ← currently cerebras/qwen-3-235b-a22b-instruct-2507
3. (no built-in default — model is required)
```

### For agent dispatches (sub-agents, title, coder)

Source: `packages/opencode/src/session/prompt.ts` + `packages/opencode/src/provider/provider.ts`

```
1. config.agent.<name>.model override       ← per-agent model in opencode.json "agent" block
2. Agent frontmatter model: field           ← loaded into agent definition at config merge time
3. provider.getSmallModel(session.providerID):
   a. cfg.small_model present?
      YES → parseModel(cfg.small_model) → getModel(providerID, modelID)  [STOP]
      NO  → continue
   b. Scan s.providers[session.providerID] models for priority strings (in order):
      "claude-haiku-4-5", "claude-haiku-4.5", "3-5-haiku", "3.5-haiku",
      "gemini-3-flash", "gemini-2.5-flash", "gpt-5-nano"
      Match found → use it  [STOP]
      No match   → return undefined
4. Fallback: provider.getModel(session.providerID, session.modelID)
   (uses same model as primary session)
```

**Key observations:**
- Agent frontmatter `model:` is step 2 — it wins over `small_model` (step 3).
- `getSmallModel` scans only `session.providerID`'s models, not all authenticated providers.
- If session runs on Cerebras and `cfg.small_model` is missing:
  - Cerebras models are `qwen-3-235b-a22b-instruct-2507`, `llama3.1-8b` — neither matches the
    hardcoded priority list → returns `undefined` → falls back to session model (also Cerebras).
  - So Cerebras sessions are safe even without `small_model` set.
- If session runs on Google and `cfg.small_model` is missing:
  - Google models include `gemini-2.5-flash` → matches priority list → Google wins.
  - This is why the leak was silent and hard to trace.

### Config loading — when does it happen?

- **Server startup** (`opencode serve`): loads only XDG global configs (step 1 above).
  Project configs are NOT loaded at server start.
- **Session connect** (`opencode run --attach`): calls `directories(sessionDir, worktree)`,
  loads all config layers, merges fully. Provider + model resolution happens here.

---

## 4. The title-agent leak — root cause and fix

### Historical root cause (confirmed, server-b27-a11.log)

```
Config load sequence (from actual server log):
  line 22: .opencode\opencode.json loaded    → small_model = cerebras/qwen-3-235b-a22b-instruct-2507
  line 26: C:\Users\lukas\.opencode\opencode.json loaded  ← USER HOME, LOADED LAST, WINS
            → small_model = google/gemini-2.5-flash        ← OVERRIDE

Result:
  line 91:  service=llm providerID=google modelID=gemini-2.5-flash small=true agent=title  ← leak
  line 313: service=llm providerID=google modelID=gemini-2.5-flash small=false agent=orchestrator
  line 317: ERROR 429 quota exceeded
```

The user-home config `C:\Users\lukas\.opencode\opencode.json` contained
`"small_model": "google/gemini-2.5-flash"` and loaded after the project config.

### Current state (as of 2026-04-24)

User-home config was fixed: `model` and `small_model` fields removed.
Effective `small_model` = Cerebras from project config.
Title agent should now route to Cerebras correctly.

### Structural fragility (future risk)

The `title` agent has NO explicit `model` override and NO entry in the config `agent` block.
It relies on `cfg.small_model` surviving the merge. Any config file that overwrites
`small_model` — including a future edit to the user-home config — will silently redirect it.

### Belt-and-suspenders fix (not yet applied — user to decide)

Add to `.opencode/opencode.json` → `agent` block:

```json
"agent": {
  "title": {
    "model": "cerebras/qwen-3-235b-a22b-instruct-2507"
  }
}
```

This routes title via step 1 (per-agent config override), bypassing `getSmallModel` entirely.
Immune to `small_model` config drift.

### `{env:CEREBRAS_API_KEY}` syntax — confirmed valid

Binary source contains:
```js
H = H.replace(/\{env:([^}]+)\}/g, (D, O) => { return process.env[O] || "" })
```
The substitution runs at runtime. Confirmed working: line 85 of server log shows
`service=provider providerID=cerebras found` — provider registered successfully.

---

## 5. Stale state inventory

| Location | Files | Model fields? | Impact |
|---|---|---|---|
| `C:\Users\lukas\.local\share\opencode\` | `opencode.db` (22 MB), `agent_memory.db` (16 KB), `storage/session_diff/` (75+ JSON stubs) | none | Session history only, no runtime config |
| `C:\Users\lukas\.local\share\opencode\snapshot/` | One snapshot chain active (Apr 24 19:31) | none | Snapshot of working tree, no config |
| `.opencode\mission.json` | status=`planning`, resume_from=`feat-mission-status` | none | Stale unfinished mission; will be resumed by orchestrator if not reset |
| `.opencode\schedule.json` | `nightly.model = "google/gemini-2.5-flash"` | `google/gemini-2.5-flash` | `enabled: false` — **not active**; would burn Gemini quota if enabled |
| `.opencode\user-model.json` | Style preferences | none | Safe |

---

## 6. Reference commands

### Verify routing before a real run (no quota cost)

```powershell
# Terminal 1: start server with log capture
opencode serve --port 4099 --print-logs 2>&1 | Tee-Object MagnumOpus\smoke-test-artifacts\route-verify.log

# Terminal 2: probe with 3-word prompt
opencode run --attach http://localhost:4099 --model cerebras/qwen-3-235b-a22b-instruct-2507 "say hi"

# Verify: look for providerID=cerebras for BOTH agent=title AND agent=orchestrator
Select-String "service=llm" MagnumOpus\smoke-test-artifacts\route-verify.log
```

Expected good output:
```
service=llm providerID=cerebras modelID=qwen-3-235b-a22b-instruct-2507 small=true  agent=title
service=llm providerID=cerebras modelID=qwen-3-235b-a22b-instruct-2507 small=false agent=orchestrator
```

### Audit config merge result

```powershell
# Which config files does THIS session see (run from project root)?
opencode serve --port 4099 --print-logs 2>&1 | Select-String "service=config"
# Expected: 3 XDG probes (all not found), then project + user-home on first run --attach
```

### Check all model dispatch events in a server log

```powershell
Select-String "service=llm" MagnumOpus\smoke-test-artifacts\server-XXXX.log |
  Select-Object -ExpandProperty Line
```

### Dump effective model fields from project config

```powershell
python3 -c "
import json
with open('.opencode/opencode.json') as f:
    c = json.load(f)
print('model:', c.get('model'))
print('small_model:', c.get('small_model'))
print('agent overrides:', list(c.get('agent', {}).keys()))
"
```

### Force-pin title agent (add to .opencode/opencode.json manually)

```json
"agent": {
  "title": {
    "model": "cerebras/qwen-3-235b-a22b-instruct-2507"
  }
}
```

---

## 7. Provider authentication map

| Provider | How authenticated | Credential location | Status |
|---|---|---|---|
| cerebras | `{env:CEREBRAS_API_KEY}` in project config | Shell environment variable | ✓ resolves at runtime |
| google | `auth.json` key | `~/.local/share/opencode/auth.json` | ✓ has key (20/20 RPD quota burned) |
| anthropic | `auth.json` key | `~/.local/share/opencode/auth.json` | ✓ has key |
| deepseek | `auth.json` key | `~/.local/share/opencode/auth.json` | ✓ has key |
| openrouter | `auth.json` key | `~/.local/share/opencode/auth.json` | ✓ has key |

> `auth.json` is NOT the same as config. It stores keys set via `opencode auth` / settings UI.
> Provider blocks in `opencode.json` configure endpoints and options; `auth.json` supplies secrets.
> For cerebras, the secret bypasses `auth.json` entirely via `{env:}` substitution.

---

## 8. Source file index (for future digging)

| Topic | File in `opencode-src/` |
|---|---|
| Config schema (all fields) | `packages/opencode/src/config/config.ts` |
| Config directory resolution | `packages/opencode/src/config/paths.ts` |
| `getSmallModel` + priority list | `packages/opencode/src/provider/provider.ts` |
| Title agent dispatch | `packages/opencode/src/session/prompt.ts` lines 182-187 |
| Built-in agent definitions | `packages/opencode/src/agent/agent.ts` |
| `{env:}` substitution | opencode binary (minified JS, pattern: `replace(/\{env:([^}]+)\}/g`) |
| Config load order (global) | `config.ts` → `loadGlobal` |
| Config load order (project) | `config.ts` + `paths.ts` → `directories()` |
