# Global Environment Reference

This file documents the global environment and conventions for all agents operating under this OpenCode installation. This supplements the shell_strategy plugin (non-interactive shell behavior) with Windows/PowerShell-specific knowledge, communication patterns, and operational conventions.

---

## 1. Environment Basics

| Property | Value |
|----------|-------|
| OS | Windows (win32) |
| Shell | PowerShell 5.1+ |
| TTY | None — fully non-interactive |
| Line endings | CRLF (Windows) |
| Filesystem | NTFS — case-insensitive |
| Path separator | Backslash (`\`) |
| Long paths | ~260 char limit — use temp dir for long paths |

### 1.1 PowerShell Command Chaining

PowerShell 5.1 does **NOT** support `&&` or `||`. Use these patterns:

| Intent | Pattern |
|--------|---------|
| Run both, ignore failures | `cmd1; cmd2` |
| Run cmd2 only if cmd1 succeeds | `cmd1; if ($?) { cmd2 }` |
| Run cmd2 only if cmd1 fails | `cmd1; if (-not $?) { cmd2 }` |
| Long chain | `cmd1; if ($?) { cmd2 }; if ($?) { cmd3 }` |

### 1.2 Path Quoting

Always quote paths containing spaces:
```powershell
# GOOD
ls "C:\Program Files\Arduino IDE"
python "C:\My Project\script.py"

# BAD (will fail or misbehave)
ls C:\Program Files\Arduino IDE
python C:\My Project\script.py
```

### 1.3 Heredocs in PowerShell

```powershell
# Multi-line string to a file
@"
line1
line2
"@ | Out-File -FilePath "path\to\file.txt" -Encoding utf8

# Input to a command
@"
input line 1
input line 2
"@ | some-command
```

### 1.4 Environment Inspection

```powershell
Get-ChildItem Env:           # List all environment variables
$env:CI                      # Get specific variable
$env:MY_VAR = "value"        # Set for current session
Get-Command npm -ErrorAction SilentlyContinue  # Check if command exists
```

---

## 2. Error Recovery Patterns

| Situation | Response |
|-----------|----------|
| **Command timed out** | It hung waiting for input. Retry with `Start-Process <cmd> -NoNewWindow -Wait -Timeout 15` or pipe `yes \| <cmd>`. |
| **Command not found** | Check `Get-Command <tool>`. Check `$env:PATH`. Install if needed. |
| **File not found** | Check actual path (Windows separators). Use `Glob("**/filename*")`. Check `git status`. |
| **Permission denied** | Use `-Force` flag. Check file attributes with `ls -Force`. |
| **Port already in use** | `netstat -ano \| Select-String ":PORT "` then `Stop-Process -Id <PID> -Force`. |
| **npm errors** | `npm cache clean --force`; delete `node_modules` + `package-lock.json`; retry with `npm install --yes`. |
| **Git merge conflict** | `git checkout --theirs <file>` or `--ours`; `git add <file>`; `git merge --no-edit --continue`. |
| **Build failed** | Read the error, identify the root cause file/line, fix, re-run. Never re-run blindly. |

---

## 3. Git Protocol Rules

### 3.1 Cardinal Rules
1. **Never commit unless explicitly asked** by the user.
2. **Never update git config** (`git config --global`).
3. **Never force push** to main/master without explicit approval.
4. **Never use `--no-verify` or `--no-gpg-sign`** to skip hooks unless user requests it.
5. **Never amend commits** unless ALL conditions met (see below).

### 3.2 Amend Conditions
Only amend when ALL of these are true:
1. User explicitly requested amend (OR pre-commit hook auto-modified files after a successful commit — verify with `git log`).
2. HEAD commit was created by **you** in this conversation (verify: `git log -1 --format='%an %ae'`).
3. Commit has **NOT** been pushed to remote (verify: `git status` shows "Your branch is ahead").

### 3.3 What NOT to Commit
- `.env`, `.env.*`, `credentials.json`, `secrets.*`, `*.key`, `*.pem`, `*.cert`
- `node_modules/`, `__pycache__/`, `.venv/`, `vendor/`
- `*.log`, `dist/`, `build/`, `.next/`, `target/`
- Large binary files (>10MB) unless project convention dictates otherwise

---

## 4. Communication Conventions

- **Be concise**: 1-3 sentences when possible. Answer, don't prelude.
- **Be direct**: Provide the solution. No "I'll help you with that."
- **No preambles**: Skip "Let me..." or "I'll start by..."
- **No postambles**: Don't explain what you just did unless asked.
- **Code references**: Always use `file:line` format — `src/auth.ts:42`.
- **No emojis**: Unless user uses them first.
- **No markdown docs** (README, etc.) unless explicitly requested.
- **Prefer editing** existing files over creating new ones.

### Response Length by Situation
| Situation | Length |
|-----------|--------|
| Simple fact ("what is 2+2?") | The answer — `4` |
| Error explanation | 1-3 sentences |
| Feature implementation | Provide code, brief summary |
| "Why did you do X?" | Brief rationale |
| "Walk me through your approach" | Structured explanation |

---

## 5. Code Style Essentials

- **Follow existing conventions** — look at neighboring files first.
- **No comments** unless asked — code should be self-documenting.
- **No emojis** in code unless user explicitly requests them.
- **Match existing** indentation, naming, and import patterns.
- **Keep diffs minimal**: change only what's necessary.

---

## 6. Tool Usage Patterns

### 6.1 Parallel Execution
When information is independent, batch tool calls:
```
Read("src/foo.py")  +  Read("src/bar.py")       # parallel reads
Glob("**/*.tsx")    +  Grep("useEffect")        # parallel searches
Bash("git status")  +  Bash("git diff")         # parallel bash
```

### 6.2 Glob Patterns
| Pattern | Matches |
|---------|---------|
| `**/*.ts` | All TypeScript files recursively |
| `src/**/*.tsx` | All TSX files under src/ |
| `*.{ts,tsx,js}` | Files with any of those extensions in root |
| `**/test/**/*.test.ts` | Test files |
| `**/*.config.*` | Config files |

### 6.3 Grep Regex Patterns
```
function\s+\w+\s*\(                    # Function definitions
class\s+\w+                            # Class definitions
import\s+.*from\s+['"]                 # Imports
TODO|FIXME|HACK|XXX                    # Todo comments
console\.(log|warn|error)              # Console statements
(app|router)\.(get|post|put|delete)\(  # API endpoints
(?s)useEffect\(\(\)\s*=>\s*\{.*?       # Cross-line patterns
```

---

## 7. PowerShell vs Bash Quick Reference

| Operation | Bash | PowerShell |
|-----------|------|------------|
| Current dir | `pwd` | `Get-Location` or `pwd` |
| List files | `ls` | `ls` or `Get-ChildItem` |
| Set variable | `export X=val` | `$env:X = "val"` |
| Delete file | `rm -f file` | `Remove-Item -Force file` |
| Find files | `find . -name "*.ts"` | `Get-ChildItem -Recurse -Filter "*.ts"` (prefer Glob tool) |
| Search content | `grep -r "pattern"` | `Select-String` (prefer Grep tool) |
| Multiline | `\` at line end | `` ` `` at line end |
| String concat | `"$var/suffix"` | `"$($var)/suffix"` |

---

## 8. Windows Path Translations

| Concept | *nix | Windows |
|---------|------|---------|
| User home | `~` | `C:\Users\lukas` |
| Config dir | `~/.config` | `C:\Users\lukas\.config` |
| Temp dir | `/tmp` | `C:\Users\lukas\AppData\Local\Temp` |
| Program Files | `/usr/bin` | `C:\Program Files` |
| Separator | `/` | `\` (but `/` often works in many tools) |

---

## 9. Process Continuity

---

**The rule**: Never stop after tool output to "wait for instructions." The environment is non-interactive. Drive the workflow.

**Pattern**:
1. Execute command
2. Analyze output
3. Explicitly state next step: "Status is clean. Next: I will run tests."
4. Execute next step immediately

**After error**: Read the error, identify root cause, state the fix plan, execute.
**After lint/test failure**: Fix and re-run loop until they pass.

---

## 10. `.opencode/context/` Directory

The `.opencode/context/` directory is the project's shared knowledge base — a persistent, structured record of architectural decisions, conventions, feature plans, and project overview.

### Context Files

| File | Purpose |
|------|---------|
| `project-overview.md` | Architecture overview, tech stack, directory layout, key conventions, design decisions |
| `decisions.md` | Rationale for each architectural decision, alternatives considered, trade-offs accepted |
| `conventions.md` | Code style rules, import patterns, naming conventions, testing patterns, error handling patterns |
| `feature-F00X.md` | Feature plan skeleton: purpose, files touched, signatures, data flow, edge cases, constraints |

### Agent Protocol

**ALL agents must Read() context files before beginning work:**
- `Read('.opencode/context/decisions.md')` for architecture rationale
- `Read('.opencode/context/conventions.md')` for project-specific code patterns
- `Read('.opencode/context/feature-*.md')` for active feature plans
- `Read('.opencode/context/project-overview.md')` for project-wide context

The orchestrator writes/updates context files proactively. Reading them at session start ensures full situational awareness without relying on the orchestrator to paste file contents into every handoff.

---

*This file serves as the global environment knowledge base for all agents. Update it as conventions evolve.*
