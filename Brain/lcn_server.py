"""lcn_server.py — LCN HTTP JSON server for JANUS orchestrator.

Provides a REST API for querying and writing to the LCN entity store.
Zero external dependencies — uses stdlib http.server + subprocess only.

Endpoints:
  GET  /health          → {"status": "ok", "uptime": <seconds>}
  POST /query           → delegates to consult.py CLI, returns result as JSON
  POST /write           → pipes entity JSON to lcn_write.py stdin, returns {"written": true, "id": "..."}
  GET  /stats           → {"entity_count": N, "db_path": "..."}
  POST /train           → train cortex on mission entities
  POST /cortex_query    → augment SQLite results with cortex relevance scores
  GET  /cortex_status   → cortex bridge health check
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths — resolved relative to this script's location
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent  # Brain/
PROJECT_ROOT = SCRIPT_DIR.parent
TOOLS_DIR = PROJECT_ROOT / ".opencode" / "tools"
CONSULT_PY = TOOLS_DIR / "consult.py"
LCN_WRITE_PY = TOOLS_DIR / "lcn_write.py"

# Default LCN database path (mirrors lcn_write.py DEFAULT_DB_PATH)
DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "opencode" / "lcn_memory.db"

# Server config
HOST = "localhost"
PORT = 3737

# ---------------------------------------------------------------------------
# LCN Cortex bridge (lazy-initialized)
# ---------------------------------------------------------------------------


_BRIDGE: Any | None = None


def _get_bridge() -> Any:
    global _BRIDGE
    if _BRIDGE is None:
        # Graceful import — bridge handles degradation internally
        try:
            from lcn_bridge import LcnBridge

            _BRIDGE = LcnBridge()
        except ImportError:
            _BRIDGE = False  # sentinel: don't retry
    return _BRIDGE if _BRIDGE is not False else None


# ---------------------------------------------------------------------------
# Server state
# ---------------------------------------------------------------------------

_start_time = time.time()


def _uptime() -> float:
    return time.time() - _start_time


def _log(method: str, path: str, status: int) -> None:
    ts = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {method} {path} -> {status}", flush=True)


def _json_response(
    handler: BaseHTTPRequestHandler,
    data: Any,
    status: int = 200,
) -> None:
    body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_body(handler: BaseHTTPRequestHandler) -> dict[str, Any] | None:
    """Read and parse JSON request body. Returns None on failure."""
    try:
        length = int(handler.headers.get("Content-Length", 0))
        if length == 0:
            return None
        raw = handler.rfile.read(length)
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError, OSError):
        return None


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _handle_health(handler: BaseHTTPRequestHandler) -> None:
    _json_response(handler, {"status": "ok", "uptime": round(_uptime(), 2)})
    _log("GET", "/health", 200)


def _handle_query(handler: BaseHTTPRequestHandler) -> None:
    """POST /query — delegates to consult.py and returns its JSON output."""
    body = _read_body(handler)
    if body is None or "mode" not in body:
        _json_response(
            handler,
            {"status": "error", "message": "Request body must include 'mode' field"},
            status=400,
        )
        _log("POST", "/query", 400)
        return

    mode = body["mode"]
    args = body.get("args", [])

    valid_modes = {"pre_plan", "pre_dispatch", "post_verify"}
    if mode not in valid_modes:
        _json_response(
            handler,
            {
                "status": "error",
                "message": f"Invalid mode '{mode}'. Must be one of {sorted(valid_modes)}",
            },
            status=400,
        )
        _log("POST", "/query", 400)
        return

    cmd = [sys.executable, str(CONSULT_PY), mode, *args]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        _json_response(
            handler,
            {"status": "error", "message": "Consultation timed out after 60s"},
            status=504,
        )
        _log("POST", "/query", 504)
        return
    except OSError as exc:
        _json_response(
            handler,
            {"status": "error", "message": f"Failed to run consult.py: {exc}"},
            status=500,
        )
        _log("POST", "/query", 500)
        return

    try:
        out = json.loads(result.stdout)
    except json.JSONDecodeError:
        out = {"status": "degraded", "reason": "consult.py returned non-JSON output"}

    if result.returncode != 0:
        out["_warnings"] = result.stderr.strip() if result.stderr else ""

    _json_response(handler, out)
    _log("POST", "/query", 200)


def _handle_write(handler: BaseHTTPRequestHandler) -> None:
    """POST /write — pipes entity JSON to lcn_write.py stdin, returns result."""
    body = _read_body(handler)
    if body is None:
        _json_response(
            handler,
            {"status": "error", "message": "Request body must be valid JSON"},
            status=400,
        )
        _log("POST", "/write", 400)
        return

    cmd = [sys.executable, str(LCN_WRITE_PY), "write"]

    try:
        result = subprocess.run(
            cmd,
            input=json.dumps(body),
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        _json_response(
            handler,
            {"status": "error", "message": "Write timed out after 30s"},
            status=504,
        )
        _log("POST", "/write", 504)
        return
    except OSError as exc:
        _json_response(
            handler,
            {"status": "error", "message": f"Failed to run lcn_write.py: {exc}"},
            status=500,
        )
        _log("POST", "/write", 500)
        return

    if result.returncode != 0:
        err_msg = result.stderr.strip() or "lcn_write.py exited with error"
        _json_response(handler, {"status": "error", "message": err_msg}, status=422)
        _log("POST", "/write", 422)
        return

    try:
        out = json.loads(result.stdout)
        entity_id = out.get("id", "")
        _json_response(handler, {"written": True, "id": entity_id})
        _log("POST", "/write", 200)
    except json.JSONDecodeError:
        _json_response(
            handler,
            {"status": "error", "message": "lcn_write.py returned non-JSON output"},
            status=500,
        )
        _log("POST", "/write", 500)


def _handle_stats(handler: BaseHTTPRequestHandler) -> None:
    """GET /stats — returns entity count and DB path from the LCN store."""
    db_path = os.environ.get("LCN_DB_PATH", str(DEFAULT_DB_PATH))
    entity_count = 0
    db_exists = os.path.isfile(db_path)

    if db_exists:
        try:
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT COUNT(*) FROM entities").fetchone()
            entity_count = row[0] if row else 0
            conn.close()
        except (sqlite3.Error, OSError):
            entity_count = -1

    _json_response(
        handler,
        {
            "entity_count": entity_count,
            "db_path": db_path,
            "db_exists": db_exists,
        },
    )
    _log("GET", "/stats", 200)


# ---------------------------------------------------------------------------
# Cortex bridge handlers
# ---------------------------------------------------------------------------


def _handle_train(handler: BaseHTTPRequestHandler) -> None:
    """POST /train — train cortex on a mission plan's entities."""
    bridge = _get_bridge()
    if bridge is None:
        _json_response(
            handler,
            {"status": "error", "message": "LCN bridge not available (import failed)"},
            status=503,
        )
        _log("POST", "/train", 503)
        return

    body = _read_body(handler)
    if body is None or "plan" not in body:
        _json_response(
            handler,
            {"status": "error", "message": "Request body must include 'plan' (list of entities)"},
            status=400,
        )
        _log("POST", "/train", 400)
        return

    plan = body["plan"]
    if not isinstance(plan, list):
        _json_response(
            handler,
            {"status": "error", "message": "'plan' must be a JSON array"},
            status=400,
        )
        _log("POST", "/train", 400)
        return

    result = bridge.train(plan)
    status_code = 200 if result.get("trained") else 202
    _json_response(handler, result, status=status_code)
    _log("POST", "/train", status_code)


def _handle_cortex_query(handler: BaseHTTPRequestHandler) -> None:
    """POST /cortex_query — augment SQLite results with cortex scores."""
    bridge = _get_bridge()
    if bridge is None:
        _json_response(
            handler,
            {"status": "error", "message": "LCN bridge not available (import failed)"},
            status=503,
        )
        _log("POST", "/cortex_query", 503)
        return

    body = _read_body(handler)
    if body is None or "results" not in body or "query" not in body:
        _json_response(
            handler,
            {
                "status": "error",
                "message": "Request body must include 'results' (list) and 'query' (str)",
            },
            status=400,
        )
        _log("POST", "/cortex_query", 400)
        return

    results = body["results"]
    query_text = body["query"]
    if not isinstance(results, list) or not isinstance(query_text, str):
        _json_response(
            handler,
            {"status": "error", "message": "'results' must be a list, 'query' must be a string"},
            status=400,
        )
        _log("POST", "/cortex_query", 400)
        return

    augmented = bridge.cortex_query(results, query_text)
    _json_response(handler, {"results": augmented, "count": len(augmented)})
    _log("POST", "/cortex_query", 200)


def _handle_cortex_status(handler: BaseHTTPRequestHandler) -> None:
    """GET /cortex_status — health check for the cortex bridge."""
    bridge = _get_bridge()
    if bridge is None:
        _json_response(
            handler,
            {"bridge_loaded": False, "reason": "LCN bridge import failed"},
            status=200,
        )
        _log("GET", "/cortex_status", 200)
        return

    status_data = bridge.status()
    _json_response(handler, status_data)
    _log("GET", "/cortex_status", 200)


# ---------------------------------------------------------------------------
# HTTP Request Handler
# ---------------------------------------------------------------------------


class LCNRequestHandler(BaseHTTPRequestHandler):
    """Single-threaded HTTP handler for LCN server."""

    def _respond(self, data: Any, status: int = 200) -> None:
        _json_response(self, data, status)
        _log(self.command, self.path, status)

    def do_GET(self) -> None:
        if self.path == "/health":
            _handle_health(self)
        elif self.path == "/stats":
            _handle_stats(self)
        elif self.path == "/cortex_status":
            _handle_cortex_status(self)
        else:
            self._respond({"status": "error", "message": "Not found"}, status=404)

    def do_POST(self) -> None:
        if self.path == "/query":
            _handle_query(self)
        elif self.path == "/write":
            _handle_write(self)
        elif self.path == "/train":
            _handle_train(self)
        elif self.path == "/cortex_query":
            _handle_cortex_query(self)
        else:
            self._respond({"status": "error", "message": "Not found"}, status=404)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP server logs — we use our own _log()."""
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    server = HTTPServer((HOST, PORT), LCNRequestHandler)
    print(f"[LCN] Server listening on http://{HOST}:{PORT}", flush=True)
    print(f"[LCN] consult.py  -> {CONSULT_PY}", flush=True)
    print(f"[LCN] lcn_write.py -> {LCN_WRITE_PY}", flush=True)
    print(f"[LCN] DB path     -> {DEFAULT_DB_PATH}", flush=True)
    print("[LCN] Press Ctrl+C to stop.", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[LCN] Shutting down...", flush=True)
        server.server_close()
        print("[LCN] Server stopped.", flush=True)


if __name__ == "__main__":
    main()
