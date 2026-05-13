"""Reset .opencode/mission.json to planning state for smoke test attempt 10.

Run from project root (the folder containing .opencode/).
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone


def main() -> int:
    p = Path(".opencode/mission.json")
    if not p.exists():
        print(f"ERROR: {p} not found. Run this from the project root "
              f"(the folder containing .opencode/).")
        return 1

    d = json.loads(p.read_text())
    now = datetime.now(timezone.utc).isoformat()
    d["status"] = "planning"
    d["last_updated"] = now
    d["created_at"] = now
    d["features"][0]["status"] = "pending"
    d["features"][0]["branch"] = None
    d["features"][0]["summary_file"] = None
    d["features"][0]["failures"] = 0
    d["error_budget"]["failures_used"] = 0
    d["resume_from"] = "feat-mission-status"
    p.write_text(json.dumps(d, indent=2))

    print(f"Reset OK: status={d['status']}, "
          f"feature[0].status={d['features'][0]['status']}, "
          f"resume_from={d['resume_from']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
