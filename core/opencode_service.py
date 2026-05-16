import json
import re
import subprocess


class OpenCodeService:
    @staticmethod
    def run_cmd(cmd, as_json=False):
        try:
            # We use shell=True to run .cmd files easily on Windows
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            try:
                stdout, stderr = process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                print(f"Command timed out: {cmd}")
                return None
            if as_json:
                try:
                    return json.loads(stdout.strip())
                except json.JSONDecodeError:
                    return None
            return stdout.strip()
        except Exception as e:
            print(f"Error running cmd {cmd}: {e}")
            return None

    @classmethod
    def get_models(cls):
        output = cls.run_cmd("opencode.cmd models")
        if not output:
            return []

        # Output is line-separated models, filter out empty lines or log noise
        models = []
        for line in output.split("\n"):
            line = line.strip()
            if line and not line.startswith("[") and not line.startswith("\x1b") and "/" in line:
                models.append(line)
        return models

    @classmethod
    def get_agents_from_files(cls, project_root=None):
        """Read agent names from .opencode/agent/*.md filenames — reliable, no CLI parsing."""
        import os
        from pathlib import Path

        root = Path(project_root) if project_root else Path(os.getcwd())
        agent_dir = root / ".opencode" / "agent"
        if not agent_dir.exists():
            return []
        return sorted(md.stem for md in agent_dir.glob("*.md"))

    @classmethod
    def get_agents(cls):
        output = cls.run_cmd("opencode.cmd agent list")
        if not output:
            return []

        # Agent names are usually at the beginning of the line before a space and parenthesis,
        # e.g., "build (primary)" or "explore (subagent)"
        agents = []
        for line in output.split("\n"):
            line = line.strip()
            if (
                "(" in line
                and ")" in line
                and "{" not in line
                and "}" not in line
                and "[" not in line
                and "]" not in line
                and '"' not in line
            ):
                match = re.match(r"^([a-zA-Z0-9_-]+)\s+\(", line)
                if match:
                    agents.append(match.group(1))
        return agents

    @classmethod
    def get_sessions(cls):
        # We query the DB directly to get the latest sessions
        query = "SELECT id, title, time_updated FROM session ORDER BY time_updated DESC LIMIT 50;"
        output = cls.run_cmd(f'opencode.cmd db "{query}" --format json', as_json=True)

        if not output:
            return []

        sessions = []
        for row in output:
            sessions.append(
                {
                    "id": row.get("id"),
                    "title": row.get("title", "Untitled Session"),
                    "updated_at": row.get("time_updated"),
                }
            )
        return sessions

    @classmethod
    def get_sessions_export(cls):
        query = (
            "SELECT s.id, s.title, s.model, s.agent, s.time_created, "
            "COUNT(m.id) as message_count "
            "FROM session s "
            "LEFT JOIN message m ON m.session_id = s.id "
            "WHERE s.time_archived IS NULL "
            "GROUP BY s.id "
            "ORDER BY s.time_updated DESC LIMIT 50"
        )
        output = cls.run_cmd(f'opencode.cmd db "{query}" --format json', as_json=True)
        if not output:
            return []
        sessions = []
        for row in output:
            sessions.append({
                "id": row.get("id"),
                "title": row.get("title", "Untitled"),
                "model": row.get("model", ""),
                "agent": row.get("agent", ""),
                "created_at": row.get("time_created"),
                "message_count": row.get("message_count", 0),
            })
        return sessions

    @classmethod
    def get_session_messages(cls, session_id, limit=50):
        # Sanitize session_id: only allow hex chars and hyphens (UUID format)
        sanitized = ''.join(c for c in session_id if c in '0123456789abcdefABCDEF-')
        limit_int = int(limit)  # safe conversion, will raise ValueError if not int

        # Single-line query required — Windows shell (shell=True) mangles multiline strings
        query = (
            f"SELECT p.text FROM message m "
            f"JOIN part p ON m.id = p.message_id "
            f"WHERE m.session_id = '{sanitized}' "
            f"AND p.text IS NOT NULL "
            f"ORDER BY m.time_created ASC "
            f"LIMIT {limit_int};"
        )
        output = cls.run_cmd(f'opencode.cmd db "{query}" --format json', as_json=True)
        if not output:
            return ""

        full_text = "\n".join([row.get("text", "") for row in output if row.get("text")])
        return full_text
