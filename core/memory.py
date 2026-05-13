import sqlite3
import time
from pathlib import Path


class AgentMemory:
    def __init__(self, db_path=None):
        if db_path is None:
            # Place it next to opencode's data but in a separate file
            home = Path.home()
            self.db_path = home / ".local" / "share" / "opencode" / "agent_memory.db"
        else:
            self.db_path = Path(db_path)

        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_path TEXT,
                key TEXT,
                value TEXT,
                tags TEXT,
                time_updated INTEGER
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_workspace ON project_memory(workspace_path)")
        conn.commit()
        conn.close()

    def store(self, workspace_path, key, value, tags=""):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM project_memory WHERE workspace_path=? AND key=?",
            (workspace_path, key),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE project_memory SET value=?, tags=?, time_updated=? WHERE id=?",
                (value, tags, int(time.time()), row[0]),
            )
        else:
            cursor.execute(
                "INSERT INTO project_memory"
                " (workspace_path, key, value, tags, time_updated)"
                " VALUES (?, ?, ?, ?, ?)",
                (workspace_path, key, value, tags, int(time.time())),
            )
        conn.commit()
        conn.close()

    def retrieve(self, workspace_path, key=None):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        if key:
            cursor.execute(
                "SELECT value FROM project_memory WHERE workspace_path=? AND key=?",
                (workspace_path, key),
            )
            row = cursor.fetchone()
            result = row[0] if row else None
        else:
            cursor.execute(
                "SELECT key, value FROM project_memory WHERE workspace_path=?",
                (workspace_path,),
            )
            result = cursor.fetchall()
        conn.close()
        return result

    def delete(self, workspace_path, key):
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM project_memory WHERE workspace_path=? AND key=?",
            (workspace_path, key),
        )
        conn.commit()
        conn.close()

    def list_all(self, workspace_path):
        memories = self.retrieve(workspace_path)
        if not memories:
            return "No long-term memories stored for this workspace."

        output = "### Agent Long-Term Memory\n"
        for key, value in memories:
            output += f"- **{key}**: {value}\n"
        return output
