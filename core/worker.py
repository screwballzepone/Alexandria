import json
import queue
import subprocess

from PySide6.QtCore import QThread, Signal

from core.hooks import HookRunner


class OpenCodeWorker(QThread):
    # Signals for different types of output
    text_received = Signal(str)
    tool_started = Signal(str, str)
    tool_finished = Signal(str)
    error_received = Signal(str)
    process_finished = Signal(int)
    queue_empty = Signal()
    cost_updated = Signal(float, int, int)  # cost, tokens_in, tokens_out

    def __init__(self, parent=None):
        super().__init__(parent)
        self.message = ""
        self.session_id = None
        self.model = None
        self.agent = None
        self.running = False
        self.process = None
        self._queue = queue.Queue()
        self.hook_runner = HookRunner()

    def send_input(
        self,
        text,
        model=None,
        agent=None,
        file=None,
        plan_mode=False,
        slash_command=False,
        fork=False,
        title=None,
    ):
        """
        Enqueue a message for processing.

        Args:
            text:          The prompt text, or the slash command string (e.g. "/undo").
            model:         Optional model override string.
            agent:         Optional agent name override.
            file:          Optional path to attach via --file.
            plan_mode:     If True, prepends a "do not modify files" instruction.
            slash_command: If True, sends text as --command <text> instead of a prompt.
            fork:          If True, forks the current session into a new one.
            title:         Optional title for the session (applied on first message).
        """
        self._queue.put(
            {
                "text": text,
                "model": model,
                "agent": agent,
                "file": file,
                "plan_mode": plan_mode,
                "slash_command": slash_command,
                "fork": fork,
                "title": title,
            }
        )
        if not self.isRunning():
            self.start()

    def run(self):
        self.running = True
        try:
            while not self._queue.empty():
                item = self._queue.get()
                text = item["text"]
                model = item.get("model")
                agent = item.get("agent")
                file_path = item.get("file")
                plan_mode = item.get("plan_mode", False)
                slash_command = item.get("slash_command", False)
                fork = item.get("fork", False)
                title = item.get("title")

                cmd = ["opencode.cmd", "run"]

                if self.session_id:
                    cmd.extend(["--session", self.session_id])

                if fork:
                    cmd.append("--fork")

                if title:
                    cmd.extend(["--title", title])

                # Slash commands use --command flag; regular prompts are positional
                if slash_command:
                    cmd.extend(["--command", text])
                else:
                    if plan_mode:
                        text = (
                            "PLAN MODE — Do NOT modify, create, or delete any files. "
                            "Analyze the request and describe exactly what changes you "
                            "would make, step by step. Output the plan only.\n\n" + text
                        )
                    cmd.append(text)

                cmd.extend(["--format", "json", "--dangerously-skip-permissions"])

                if model and model != "Default Model (Auto)":
                    cmd.extend(["--model", model])

                if agent and agent != "Default Agent (Auto)":
                    cmd.extend(["--agent", agent])

                if file_path:
                    cmd.extend(["--file", file_path])

                self.process = subprocess.Popen(
                    cmd,
                    shell=True,  # Keeps shell=True for finding .cmd but passes list on Windows
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                )

                # Continuously read from stdout
                for line in iter(self.process.stdout.readline, ""):
                    if not self.running:
                        break

                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)

                        # Capture session ID if we don't have it yet
                        if not self.session_id and "sessionID" in data:
                            self.session_id = data["sessionID"]

                        event_type = data.get("type")
                        part = data.get("part", {})

                        cost = data.get("cost")
                        if cost is not None:
                            tokens_in = data.get("tokens_input", 0) or 0
                            tokens_out = data.get("tokens_output", 0) or 0
                            self.cost_updated.emit(float(cost), int(tokens_in), int(tokens_out))

                        if event_type == "text":
                            text_content = part.get("text", "")
                            if text_content:
                                self.text_received.emit(text_content)

                        elif event_type == "tool_use":
                            tool_name = part.get("tool", "unknown")
                            state = part.get("state", {})
                            status = state.get("status", "")
                            input_data = str(state.get("input", ""))

                            if status == "completed":
                                self.tool_finished.emit(tool_name)

                                # Run PostToolUse hooks
                                hook_ctx = {"tool_name": tool_name, "tool_input": input_data}
                                decisions = self.hook_runner.run("PostToolUse", hook_ctx)
                                for d in decisions:
                                    decision = d.get("decision", "allow")
                                    if decision == "block":
                                        self.error_received.emit(
                                            f"🚫 PostToolUse hook blocked '{tool_name}': {d.get('reason', 'no reason')}"
                                        )
                                    elif decision == "warn":
                                        self.error_received.emit(
                                            f"⚠️ PostToolUse hook warning for '{tool_name}': {d.get('reason', '')}"
                                        )
                            else:
                                self.tool_started.emit(tool_name, input_data)

                                # Run PreToolUse hooks (advisory — tool already executing)
                                hook_ctx = {"tool_name": tool_name, "tool_input": input_data}
                                decisions = self.hook_runner.run("PreToolUse", hook_ctx)
                                for d in decisions:
                                    decision = d.get("decision", "allow")
                                    if decision == "block":
                                        reason = d.get('reason', 'no reason')
                                        msg = f"⚠️ PreToolUse hook warning for '{tool_name}': {reason}"
                                        self.error_received.emit(msg)

                    except json.JSONDecodeError:
                        # If it's not JSON (e.g. an error log or pure text fallback)
                        if "npm" not in line.lower() and "opencode" not in line.lower():
                            pass  # Ignore random CLI noise

                self.process.stdout.close()
                self.process.wait()
                self.process_finished.emit(self.process.returncode)

                # Run Stop hooks
                hook_ctx = {"exit_code": self.process.returncode}
                decisions = self.hook_runner.run("Stop", hook_ctx)
                for d in decisions:
                    decision = d.get("decision", "allow")
                    if decision == "block":
                        self.error_received.emit(
                            f"🛑 Stop hook: {d.get('reason', 'verification failed')}"
                        )
                    elif decision == "warn":
                        self.error_received.emit(
                            f"⚠️ Stop hook warning: {d.get('reason', '')}"
                        )

        except Exception as e:
            self.error_received.emit(f"Error starting opencode: {str(e)}")
            self.process_finished.emit(-1)
        finally:
            # Always signal that the queue is drained — re-enables Send button
            self.queue_empty.emit()

    def stop(self):
        self.running = False
        if self.process:
            # On Windows, shell=True spawns a cmd.exe child — terminate() only
            # kills the shell, not the opencode subprocess. Use taskkill to
            # nuke the entire process tree so no orphan processes linger.
            try:
                import subprocess as _sp

                _sp.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                    stdout=_sp.DEVNULL,
                    stderr=_sp.DEVNULL,
                )
            except Exception:
                self.process.terminate()
