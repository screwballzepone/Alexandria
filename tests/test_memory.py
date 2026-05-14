"""Tests for core/memory.py — AgentMemory error handling and logging."""

import sqlite3
from unittest.mock import patch

from core.memory import AgentMemory


class TestAgentMemoryStore:
    """Tests for AgentMemory.store() error handling."""

    def test_store_success_returns_true(self, tmp_path):
        """A successful store() should return True."""
        mem = AgentMemory(db_path=tmp_path / "test.db")
        result = mem.store("/workspace", "key", "value")
        assert result is True

    def test_store_failure_returns_false(self, tmp_path):
        """A store() that hits a database error should return False."""
        mem = AgentMemory(db_path=tmp_path / "test.db")
        with patch("core.memory.sqlite3.connect") as mock_connect:
            mock_connect.side_effect = sqlite3.OperationalError("db locked")
            result = mem.store("/workspace", "key", "value")
            assert result is False

    def test_store_failure_logs_error(self, tmp_path):
        """A store() failure should call the error logger with 'log' and correct schema."""
        mem = AgentMemory(db_path=tmp_path / "test.db")
        with patch("core.memory.sqlite3.connect") as mock_connect:
            mock_connect.side_effect = sqlite3.OperationalError("db locked")
            with patch("core.memory.subprocess.run") as mock_run:
                with patch("pathlib.Path.exists", return_value=True):
                    mem.store("/workspace", "key", "value")
                    args = mock_run.call_args[0][0]
                    assert "log" in args
                    # Verify the JSON payload has required fields
                    import json
                    payload = json.loads(args[args.index("log") + 1])
                    assert payload["error_type"] == "db_error"
                    assert "context" in payload

    def test_store_upsert_updates(self, tmp_path):
        """Storing twice with the same key should update the existing value."""
        mem = AgentMemory(db_path=tmp_path / "test.db")
        mem.store("/workspace", "key", "v1")
        mem.store("/workspace", "key", "v2")
        result = mem.retrieve("/workspace", "key")
        assert result == "v2"

    def test_log_error_skips_when_tool_missing(self, tmp_path):
        """_log_error should return silently when error_logger.py does not exist."""
        mem = AgentMemory(db_path=tmp_path / "test.db")
        with patch("core.memory.sqlite3.connect") as mock_connect:
            mock_connect.side_effect = sqlite3.OperationalError("db locked")
            with patch("pathlib.Path.exists", return_value=False):
                with patch("core.memory.subprocess.run") as mock_run:
                    mem.store("/workspace", "key", "value")
                    mock_run.assert_not_called()
