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
        # Filter out subagent sessions (have parent_id set)
        query = "SELECT id, title, time_updated FROM session WHERE parent_id IS NULL AND time_archived IS NULL ORDER BY time_updated DESC LIMIT 50;"
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
    def get_session_messages(cls, session_id, limit=50):
        import sqlite3
        from pathlib import Path

        limit_int = int(limit)
        db_path = Path.home() / ".local" / "share" / "opencode" / "opencode.db"
        if not db_path.exists():
            return ""

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT p.text FROM message m"
                " JOIN part p ON m.id = p.message_id"
                " WHERE m.session_id = ? AND p.text IS NOT NULL"
                " ORDER BY m.time_created ASC LIMIT ?",
                (session_id, limit_int),
            )
            rows = cursor.fetchall()
            conn.close()
            return "\n".join([row[0] for row in rows if row[0]])
        except sqlite3.Error:
            return ""
