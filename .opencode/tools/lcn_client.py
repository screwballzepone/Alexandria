"""lcn_client.py — LCN HTTP JSON client for the JANUS orchestrator.

CLI Usage:
    python lcn_client.py health                          -> {"status": "ok", "uptime": X}
    python lcn_client.py stats                           -> {"entity_count": N, "db_path": "..."}
    python lcn_client.py query <mode> [args...]          -> consult.py result
    python lcn_client.py write <json-file>               -> {"written": true, "id": "..."}
    python lcn_client.py train <json-file>               -> cortex training diagnostics
    python lcn_client.py cortex-query <json-file> <query> -> augmented results
    python lcn_client.py cortex-status                   -> cortex bridge health check

Python API:
    client = LcnClient()
    client.health() -> bool
    client.query(mode, *args) -> dict
    client.write(entity_json) -> dict
    client.stats() -> dict
    client.train(plan) -> dict
    client.cortex_query(results, query) -> dict
    client.cortex_status() -> dict

Base URL configurable via LCN_SERVER_URL env var (default http://localhost:3737).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://localhost:3737"


class LcnClient:
    """JSON HTTP client for the LCN server."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("LCN_SERVER_URL", DEFAULT_BASE_URL)).rstrip("/")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, body: Any = None) -> dict[str, Any]:
        """Send an HTTP request to the LCN server and parse JSON response."""
        url = f"{self.base_url}{path}"
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")

        req = Request(url, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")

        try:
            with urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except URLError:
            return {"status": "offline"}
        except json.JSONDecodeError:
            return {"status": "error", "message": "Non-JSON response from server"}
        except OSError:
            return {"status": "offline"}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def health(self) -> bool:
        """GET /health — returns True if server responds 200."""
        result = self._request("GET", "/health")
        return result.get("status") == "ok"

    def query(self, mode: str, *args: str) -> dict[str, Any]:
        """POST /query — consult LCN entity store.

        Args:
            mode: One of 'pre_plan', 'pre_dispatch', 'post_verify'.
            *args: Additional positional arguments for the consult command.

        Returns:
            Consult response dict, or {"status": "offline"} if unreachable.
        """
        body: dict[str, Any] = {"mode": mode}
        if args:
            body["args"] = list(args)
        return self._request("POST", "/query", body)

    def write(self, entity_json: dict[str, Any]) -> dict[str, Any]:
        """POST /write — persist an entity to the LCN store.

        Args:
            entity_json: Entity dict matching LCN schema (type, confidence, data, etc.).

        Returns:
            {"written": true, "id": "..."} on success,
            {"status": "error", "message": "..."} on failure,
            {"status": "offline"} if server unreachable.
        """
        return self._request("POST", "/write", entity_json)

    def stats(self) -> dict[str, Any]:
        """GET /stats — returns entity count and DB metadata."""
        return self._request("GET", "/stats")

    # ------------------------------------------------------------------
    # Cortex bridge API
    # ------------------------------------------------------------------

    def train(self, plan: list[dict[str, Any]]) -> dict[str, Any]:
        """POST /train — train cortex on a mission plan's entities.

        Args:
            plan: List of LCN entity dicts.

        Returns:
            Training diagnostics dict, or ``{"status": "offline"}``.
        """
        return self._request("POST", "/train", {"plan": plan})

    def cortex_query(
        self,
        results: list[dict[str, Any]],
        query: str,
    ) -> dict[str, Any]:
        """POST /cortex_query — augment results with cortex scores.

        Args:
            results: List of entity dicts from the LCN store.
            query: Natural-language query text.

        Returns:
            Dict with ``results`` and ``count`` keys,
            or ``{"status": "offline"}``.
        """
        return self._request(
            "POST", "/cortex_query", {"results": results, "query": query}
        )

    def cortex_status(self) -> dict[str, Any]:
        """GET /cortex_status — cortex bridge health check."""
        return self._request("GET", "/cortex_status")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cli_health(client: LcnClient) -> str:
    result = client._request("GET", "/health")
    return json.dumps(result, indent=2, ensure_ascii=False)


def _cli_stats(client: LcnClient) -> str:
    result = client.stats()
    return json.dumps(result, indent=2, ensure_ascii=False)


def _cli_query(client: LcnClient, args: list[str]) -> str:
    if not args:
        return json.dumps(
            {"status": "error", "message": "Usage: lcn_client.py query <mode> [args...]"},
            indent=2,
        )
    mode = args[0]
    extra = args[1:]
    result = client.query(mode, *extra)
    return json.dumps(result, indent=2, ensure_ascii=False)


def _cli_write(client: LcnClient, args: list[str]) -> str:
    if not args:
        return json.dumps(
            {"status": "error", "message": "Usage: lcn_client.py write <json-file>"},
            indent=2,
        )
    file_path = args[0]
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            entity = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return json.dumps(
            {"status": "error", "message": f"Failed to read entity file: {exc}"},
            indent=2,
        )
    result = client.write(entity)
    return json.dumps(result, indent=2, ensure_ascii=False)


def _cli_train(client: LcnClient, args: list[str]) -> str:
    if not args:
        return json.dumps(
            {"status": "error", "message": "Usage: lcn_client.py train <json-file>"},
            indent=2,
        )
    file_path = args[0]
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return json.dumps(
            {"status": "error", "message": f"Failed to read plan file: {exc}"},
            indent=2,
        )
    if not isinstance(plan, list):
        return json.dumps(
            {"status": "error", "message": "Plan file must contain a JSON array of entities"},
            indent=2,
        )
    result = client.train(plan)
    return json.dumps(result, indent=2, ensure_ascii=False)


def _cli_cortex_query(client: LcnClient, args: list[str]) -> str:
    if not args:
        return json.dumps(
            {
                "status": "error",
                "message": "Usage: lcn_client.py cortex-query <results-json-file> <query-text>",
            },
            indent=2,
        )
    file_path = args[0]
    query_text = " ".join(args[1:]) if len(args) > 1 else ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            results = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return json.dumps(
            {"status": "error", "message": f"Failed to read results file: {exc}"},
            indent=2,
        )
    if not isinstance(results, list):
        return json.dumps(
            {"status": "error", "message": "Results file must contain a JSON array"},
            indent=2,
        )
    result = client.cortex_query(results, query_text)
    return json.dumps(result, indent=2, ensure_ascii=False)


def _cli_cortex_status(client: LcnClient) -> str:
    result = client.cortex_status()
    return json.dumps(result, indent=2, ensure_ascii=False)


def main() -> None:
    client = LcnClient()

    if len(sys.argv) < 2:
        print("Usage: lcn_client.py <health|stats|query|write> [args...]", file=sys.stderr)
        sys.exit(2)

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    if cmd == "health":
        print(_cli_health(client))
    elif cmd == "stats":
        print(_cli_stats(client))
    elif cmd == "query":
        print(_cli_query(client, rest))
    elif cmd == "write":
        print(_cli_write(client, rest))
    elif cmd == "train":
        print(_cli_train(client, rest))
    elif cmd == "cortex-query":
        print(_cli_cortex_query(client, rest))
    elif cmd == "cortex-status":
        print(_cli_cortex_status(client))
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(
            "Usage: lcn_client.py <health|stats|query|write|train|cortex-query|cortex-status> [args...]",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
