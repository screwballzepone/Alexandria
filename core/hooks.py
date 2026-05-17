"""Hook system — deterministic rule enforcement for OpenCode sessions.

Modeled after Claude Code's hooks. Hooks fire at specific points during
a session and can run shell scripts, LLM prompts, or subagents to enforce
rules that prompts alone can't guarantee.
"""

import json
import logging
import re
import shlex
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class HookRunner:
    """Loads hook config and executes matching hooks at event boundaries."""

    def __init__(self, config_path=".opencode/hooks.json"):
        self.config_path = Path(config_path)
        self.config = {}  # {event_name: [matcher_group, ...]}
        self._in_hook = False  # Guard against recursive hook triggers
        self._load()

    def _load(self):
        """Load and validate hooks config. Graceful on missing file."""
        try:
            if self.config_path.exists():
                with open(self.config_path) as f:
                    raw = json.load(f)
                self.config = raw.get("hooks", {})
                logger.info(f"Loaded hooks config: {list(self.config.keys())}")
            else:
                logger.info("No hooks.json found — hooks disabled")
                self.config = {}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load hooks config: {e}")
            self.config = {}

    def run(self, event, context):
        """Run all hooks matching the given event.

        Args:
            event: str — "PreToolUse", "PostToolUse", or "Stop"
            context: dict — {tool_name, tool_input, ...} (tool events)
                              or {exit_code, ...} (Stop event)

        Returns:
            list of dicts — hook decisions [{decision, reason, hook_type}, ...]
        """
        if self._in_hook:
            return []  # Prevent recursive triggering

        decisions = []
        matcher_groups = self.config.get(event, [])

        for group in matcher_groups:
            if not self._matches(group, context, event):
                continue

            for hook_def in group.get("hooks", []):
                try:
                    self._in_hook = True
                    result = self._execute(hook_def, context)
                    if result:
                        decisions.append(result)
                except Exception as e:
                    logger.warning(f"Hook execution failed: {e}")
                    decisions.append({
                        "decision": "error",
                        "reason": str(e),
                        "hook_type": hook_def.get("type", "unknown")
                    })
                finally:
                    self._in_hook = False

        return decisions

    def _matches(self, group, context, event):
        """Check if a matcher group applies to the current context."""
        matcher = group.get("matcher", "")
        if not matcher:
            return True  # No matcher = match everything

        if event in ("PreToolUse", "PostToolUse"):
            tool_name = context.get("tool_name", "")
            try:
                return bool(re.search(matcher, tool_name))
            except re.error:
                logger.warning(f"Invalid matcher regex: {matcher}")
                return False

        return True  # Stop/SessionStart match everything by default

    def _execute(self, hook_def, context):
        """Execute a single hook and return its decision."""
        hook_type = hook_def.get("type", "command")

        if hook_type == "command":
            return self._run_command(hook_def, context)
        elif hook_type == "prompt":
            return self._run_prompt(hook_def, context)
        elif hook_type == "agent":
            return self._run_agent(hook_def, context)
        else:
            logger.warning(f"Unknown hook type: {hook_type}")
            return None

    def _run_command(self, hook_def, context):
        """Execute a shell command hook.

        Exit codes: 0 = allow, 2 = block, other = warning.
        Stdout parsed as JSON for structured decisions.
        """
        command = hook_def.get("command", "")
        timeout = hook_def.get("timeout", 30)

        if not command:
            return None

        # Substitute context variables into command
        # $TOOL_NAME, $FILE (for Write/Edit), etc.
        expanded = self._expand_vars(command, context)

        try:
            result = subprocess.run(
                expanded,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # Parse stdout as JSON decision if possible
            try:
                decision = json.loads(result.stdout.strip())
                return decision
            except (json.JSONDecodeError, ValueError):
                pass

            # Fall back to exit-code-based decision
            if result.returncode == 0:
                return {"decision": "allow"}
            elif result.returncode == 2:
                reason = result.stderr.strip() or result.stdout.strip() or "blocked by hook"
                return {"decision": "block", "reason": reason}
            else:
                return {"decision": "warn", "reason": result.stderr.strip()[:200]}

        except subprocess.TimeoutExpired:
            return {"decision": "error", "reason": f"Hook timed out after {timeout}s"}

    def _run_prompt(self, hook_def, context):
        """LLM-based prompt hook. Placeholder for future implementation."""
        logger.info("Prompt hooks not yet implemented")
        return {"decision": "allow"}

    def _run_agent(self, hook_def, context):
        """Subagent-based hook. Placeholder for future implementation."""
        logger.info("Agent hooks not yet implemented")
        return {"decision": "allow"}

    def _expand_vars(self, command, context):
        """Expand $VARIABLES in hook commands with shell-safe quoting."""
        vars_map = {
            "TOOL_NAME": context.get("tool_name", ""),
            "TOOL_INPUT": context.get("tool_input", ""),
            "FILE": context.get("tool_input", ""),  # Best-effort for Write/Edit
        }
        expanded = command
        for var, val in vars_map.items():
            if val:
                expanded = expanded.replace(f"${var}", shlex.quote(str(val)))
        return expanded
