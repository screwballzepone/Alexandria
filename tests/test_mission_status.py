import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Add .opencode/tools to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / ".opencode" / "tools"))
import mission_status

SAMPLE_MISSION_DATA = {
    "mission_id": "test-mission-01",
    "title": "Test Mission",
    "status": "active",
    "tier": "PROJECT",
    "created_at": "2026-04-24T10:00:00+00:00",
    "last_updated": "2026-04-24T12:00:00+00:00",
    "features": [
        {"id": "feat-1", "status": "pending", "title": "Feature 1"},
        {"id": "feat-2", "status": "in_progress", "title": "Feature 2"},
        {"id": "feat-3", "status": "completed", "title": "Feature 3"},
        {"id": "feat-4", "status": "completed", "title": "Feature 4"},
        {"id": "feat-5", "status": "blocked", "title": "Feature 5"},
        {"id": "feat-6", "status": "cancelled", "title": "Feature 6"},
    ],
    "resume_from": "feat-2",
}

MALFORMED_JSON = "{ invalid json }"


class TestMissionStatusHappyPath:
    """Tests for happy path scenarios."""

    def test_prints_mission_id(self, tmp_path, capsys):
        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(json.dumps(SAMPLE_MISSION_DATA), encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            mission_status.main()

        captured = capsys.readouterr()
        assert "test-mission-01" in captured.out

    def test_prints_title(self, tmp_path, capsys):
        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(json.dumps(SAMPLE_MISSION_DATA), encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            mission_status.main()

        captured = capsys.readouterr()
        assert "Test Mission" in captured.out

    def test_prints_status(self, tmp_path, capsys):
        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(json.dumps(SAMPLE_MISSION_DATA), encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            mission_status.main()

        captured = capsys.readouterr()
        assert "active" in captured.out

    def test_prints_tier(self, tmp_path, capsys):
        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(json.dumps(SAMPLE_MISSION_DATA), encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            mission_status.main()

        captured = capsys.readouterr()
        assert "PROJECT" in captured.out

    def test_prints_resume_from(self, tmp_path, capsys):
        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(json.dumps(SAMPLE_MISSION_DATA), encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            mission_status.main()

        captured = capsys.readouterr()
        assert "feat-2" in captured.out


class TestMissingMissionJson:
    """Tests for missing mission.json scenarios."""

    def test_missing_file_exits_zero(self, tmp_path, capsys):
        non_existent_path = tmp_path / ".opencode" / "mission.json"

        with patch.object(mission_status, "MISSION_JSON_PATH", non_existent_path):
            with pytest.raises(SystemExit) as exc_info:
                mission_status.main()
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "No active mission found" in captured.out

    def test_missing_file_prints_message(self, tmp_path, capsys):
        non_existent_path = tmp_path / ".opencode" / "mission.json"

        with patch.object(mission_status, "MISSION_JSON_PATH", non_existent_path):
            with pytest.raises(SystemExit):
                mission_status.main()

        captured = capsys.readouterr()
        assert "No active mission found." in captured.out


class TestMalformedJson:
    """Tests for malformed JSON scenarios."""

    def test_malformed_json_exits_one(self, tmp_path, capsys):
        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(MALFORMED_JSON, encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            with pytest.raises(SystemExit) as exc_info:
                mission_status.main()
            assert exc_info.value.code == 1

    def test_malformed_json_prints_to_stderr(self, tmp_path, capsys):
        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(MALFORMED_JSON, encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            with pytest.raises(SystemExit):
                mission_status.main()

        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "Malformed JSON" in captured.err


class TestFeatureCountTallying:
    """Tests for feature count tallying across all statuses."""

    def test_counts_pending_features(self, tmp_path, capsys):
        data = SAMPLE_MISSION_DATA.copy()
        data["features"] = [
            {"id": "feat-1", "status": "pending"},
            {"id": "feat-2", "status": "pending"},
        ]

        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(json.dumps(data), encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            mission_status.main()

        captured = capsys.readouterr()
        assert "Pending       2" in captured.out

    def test_counts_in_progress_features(self, tmp_path, capsys):
        data = SAMPLE_MISSION_DATA.copy()
        data["features"] = [
            {"id": "feat-1", "status": "in_progress"},
            {"id": "feat-2", "status": "in_progress"},
            {"id": "feat-3", "status": "in_progress"},
        ]

        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(json.dumps(data), encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            mission_status.main()

        captured = capsys.readouterr()
        assert "In Progress   3" in captured.out

    def test_counts_completed_features(self, tmp_path, capsys):
        data = SAMPLE_MISSION_DATA.copy()
        data["features"] = [
            {"id": "feat-1", "status": "completed"},
            {"id": "feat-2", "status": "completed"},
        ]

        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(json.dumps(data), encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            mission_status.main()

        captured = capsys.readouterr()
        assert "Completed     2" in captured.out

    def test_counts_blocked_features(self, tmp_path, capsys):
        data = SAMPLE_MISSION_DATA.copy()
        data["features"] = [{"id": "feat-1", "status": "blocked"}]

        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(json.dumps(data), encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            mission_status.main()

        captured = capsys.readouterr()
        assert "Blocked       1" in captured.out

    def test_counts_cancelled_features(self, tmp_path, capsys):
        data = SAMPLE_MISSION_DATA.copy()
        data["features"] = [
            {"id": "feat-1", "status": "cancelled"},
            {"id": "feat-2", "status": "cancelled"},
            {"id": "feat-3", "status": "cancelled"},
        ]

        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(json.dumps(data), encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            mission_status.main()

        captured = capsys.readouterr()
        assert "Cancelled     3" in captured.out

    def test_counts_all_statuses_together(self, tmp_path, capsys):
        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(json.dumps(SAMPLE_MISSION_DATA), encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            mission_status.main()

        captured = capsys.readouterr()
        assert "Pending       1" in captured.out
        assert "In Progress   1" in captured.out
        assert "Completed     2" in captured.out
        assert "Blocked       1" in captured.out
        assert "Cancelled     1" in captured.out


class TestTimeAgoFormatting:
    """Tests for time ago formatting."""

    def test_last_updated_formatted_as_minutes_ago(self, tmp_path, capsys):
        data = SAMPLE_MISSION_DATA.copy()
        now = datetime.now(timezone.utc)
        thirty_minutes_ago = now - timedelta(minutes=30)
        data["last_updated"] = thirty_minutes_ago.isoformat()

        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(json.dumps(data), encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            mission_status.main()

        captured = capsys.readouterr()
        assert "minutes ago" in captured.out

    def test_last_updated_formatted_as_hours_ago(self, tmp_path, capsys):
        data = SAMPLE_MISSION_DATA.copy()
        now = datetime.now(timezone.utc)
        three_hours_ago = now - timedelta(hours=3)
        data["last_updated"] = three_hours_ago.isoformat()

        mission_file = tmp_path / ".opencode" / "mission.json"
        mission_file.parent.mkdir(parents=True, exist_ok=True)
        mission_file.write_text(json.dumps(data), encoding="utf-8")

        with patch.object(mission_status, "MISSION_JSON_PATH", mission_file):
            mission_status.main()

        captured = capsys.readouterr()
        assert "hours ago" in captured.out
