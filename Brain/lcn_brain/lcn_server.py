"""
LCN Memory Server — Flask-based persistent associative memory for OpenCode.
Listens on 127.0.0.1:3737.  SQLite-backed, zero external deps beyond Flask.

Endpoints mirroring lcn_client.py expectations:
  POST /node         upsert node, return {id, label, value, activation, ...}
  POST /edge         resolve/upsert two nodes, create edge
  POST /stdp         strengthen edge weight (STDP reinforcement)
  GET  /query        LIKE search on label/value, return nodes + connected edges
  GET  /neighborhood BFS traversal from seed node
  POST /consolidate  decay activations, prune weak nodes
  GET  /stats        aggregate counts + average activation
  GET  /health       {"status": "ok"}
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

from flask import Flask, jsonify, request

# ─── Config ───────────────────────────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 3737

# DB lives next to this script, in a hidden directory
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".lcn")
DB_PATH = os.path.join(DB_DIR, "lcn_memory.db")

app = Flask(__name__)


# ─── Database helpers ─────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    """Return a connection (autocommit via row factory)."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            value TEXT NOT NULL,
            activation REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_nodes_label_value
            ON nodes(label, value);

        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id INTEGER NOT NULL,
            to_id INTEGER NOT NULL,
            relation TEXT DEFAULT 'related-to',
            weight REAL DEFAULT 0.5,
            created_at TEXT NOT NULL,
            FOREIGN KEY(from_id) REFERENCES nodes(id),
            FOREIGN KEY(to_id) REFERENCES nodes(id)
        );
    """)
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _upsert_node(conn: sqlite3.Connection, label: str, value: str,
                 activation_inc: float = 0.0) -> dict:
    """Insert or update a node by (label, value). Returns node dict."""
    now = _now()
    row = conn.execute(
        "SELECT * FROM nodes WHERE label=? AND value=?",
        (label, value),
    ).fetchone()

    if row:
        new_activation = row["activation"] + activation_inc
        conn.execute(
            "UPDATE nodes SET activation=?, updated_at=? WHERE id=?",
            (new_activation, now, row["id"]),
        )
        conn.commit()
        return dict(
            conn.execute("SELECT * FROM nodes WHERE id=?", (row["id"],)).fetchone()
        )
    else:
        conn.execute(
            "INSERT INTO nodes (label, value, activation, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (label, value, activation_inc, now, now),
        )
        conn.commit()
        return dict(
            conn.execute(
                "SELECT * FROM nodes WHERE label=? AND value=?",
                (label, value),
            ).fetchone()
        )


def _resolve_node(conn: sqlite3.Connection, label: str, value: str) -> dict:
    """Get or create a node with default 0 activation."""
    row = conn.execute(
        "SELECT * FROM nodes WHERE label=? AND value=?",
        (label, value),
    ).fetchone()
    if row:
        return dict(row)
    return _upsert_node(conn, label, value, activation_inc=0.0)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/stats", methods=["GET"])
def stats():
    conn = _get_db()
    try:
        node_count = conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
        edge_count = conn.execute("SELECT COUNT(*) AS c FROM edges").fetchone()["c"]
        avg = conn.execute(
            "SELECT COALESCE(AVG(activation), 0.0) AS a FROM nodes"
        ).fetchone()["a"]
        return jsonify({
            "nodeCount": node_count,
            "edgeCount": edge_count,
            "avgActivation": round(avg, 4),
        })
    finally:
        conn.close()


@app.route("/node", methods=["POST"])
def create_node():
    data = request.get_json(silent=True) or {}
    label = data.get("label", "")
    value = data.get("value", "")
    confidence = float(data.get("confidence", 0.8))

    if not label or not value:
        return jsonify({"error": "label and value are required"}), 400

    conn = _get_db()
    try:
        node = _upsert_node(conn, label, value, activation_inc=confidence)
        return jsonify(node)
    finally:
        conn.close()


@app.route("/edge", methods=["POST"])
def create_edge():
    data = request.get_json(silent=True) or {}
    from_label = data.get("from_label", "")
    from_value = data.get("from_value", "")
    to_label = data.get("to_label", "")
    to_value = data.get("to_value", "")
    relation = data.get("relation_type", "related-to")
    weight = float(data.get("weight", 0.5))

    if not all([from_label, from_value, to_label, to_value]):
        return jsonify({"error": "from_label, from_value, to_label, to_value required"}), 400

    conn = _get_db()
    try:
        from_node = _resolve_node(conn, from_label, from_value)
        to_node = _resolve_node(conn, to_label, to_value)
        now = _now()
        conn.execute(
            "INSERT INTO edges (from_id, to_id, relation, weight, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (from_node["id"], to_node["id"], relation, weight, now),
        )
        conn.commit()
        return jsonify({"success": True, "edge_id": conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]})
    finally:
        conn.close()


@app.route("/stdp", methods=["POST"])
def stdp():
    data = request.get_json(silent=True) or {}
    from_label = data.get("from_label", "")
    from_value = data.get("from_value", "")
    to_label = data.get("to_label", "")
    to_value = data.get("to_value", "")
    _timing_delta = float(data.get("timing_delta_ms", 0))

    if not all([from_label, from_value, to_label, to_value]):
        return jsonify({"error": "from_label, from_value, to_label, to_value required"}), 400

    conn = _get_db()
    try:
        from_node = _resolve_node(conn, from_label, from_value)
        to_node = _resolve_node(conn, to_label, to_value)

        # STDP reinforcement: find existing edge and boost weight
        edge = conn.execute(
            "SELECT * FROM edges WHERE from_id=? AND to_id=?",
            (from_node["id"], to_node["id"]),
        ).fetchone()

        if edge:
            new_weight = min(edge["weight"] + 0.1, 1.0)
            conn.execute(
                "UPDATE edges SET weight=? WHERE id=?",
                (new_weight, edge["id"]),
            )
        else:
            now = _now()
            conn.execute(
                "INSERT INTO edges (from_id, to_id, relation, weight, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (from_node["id"], to_node["id"], "related-to", 0.6, now),
            )
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


@app.route("/query", methods=["GET"])
def query():
    text = request.args.get("text", "")
    label_filter = request.args.get("label", "")
    try:
        limit = int(request.args.get("limit", 10))
    except (ValueError, TypeError):
        limit = 10

    conn = _get_db()
    try:
        if text:
            like = f"%{text}%"
            if label_filter:
                rows = conn.execute(
                    "SELECT * FROM nodes WHERE label=? AND "
                    "(label LIKE ? OR value LIKE ?) LIMIT ?",
                    (label_filter, like, like, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM nodes WHERE label LIKE ? OR value LIKE ? LIMIT ?",
                    (like, like, limit),
                ).fetchall()
        else:
            if label_filter:
                rows = conn.execute(
                    "SELECT * FROM nodes WHERE label=? LIMIT ?",
                    (label_filter, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM nodes LIMIT ?", (limit,)
                ).fetchall()

        results = []
        for row in rows:
            node = dict(row)
            # Attach edges where this node is source or target
            edge_rows = conn.execute(
                "SELECT e.*, n.label AS target_label, n.value AS target_value "
                "FROM edges e JOIN nodes n ON "
                "(CASE WHEN e.from_id=? THEN e.to_id ELSE e.from_id END)=n.id "
                "WHERE e.from_id=? OR e.to_id=?",
                (node["id"], node["id"], node["id"]),
            ).fetchall()

            edges_out = []
            for e in edge_rows:
                e_dict = dict(e)
                edges_out.append({
                    "target": {"label": e_dict["target_label"],
                               "value": e_dict["target_value"]},
                    "relation": e_dict["relation"],
                    "weight": e_dict["weight"],
                })
            results.append({"node": node, "edges": edges_out})

        return jsonify({"results": results})
    finally:
        conn.close()


@app.route("/neighborhood", methods=["GET"])
def neighborhood():
    label = request.args.get("label", "")
    value = request.args.get("value", "")
    try:
        depth = int(request.args.get("depth", 2))
    except (ValueError, TypeError):
        depth = 2

    if not label or not value:
        return jsonify({"error": "label and value are required"}), 400

    conn = _get_db()
    try:
        seed = conn.execute(
            "SELECT * FROM nodes WHERE label=? AND value=?",
            (label, value),
        ).fetchone()

        if not seed:
            return jsonify({"error": "seed node not found"}), 404

        seed_dict = dict(seed)

        # BFS
        visited = {seed_dict["id"]}
        frontier = [(seed_dict["id"], 0, [seed_dict["id"]])]  # (node_id, dist, path)
        neighbors = []

        while frontier:
            current_id, dist, path = frontier.pop(0)
            if dist > 0:
                node_row = conn.execute(
                    "SELECT * FROM nodes WHERE id=?", (current_id,)
                ).fetchone()
                if node_row:
                    neighbors.append({
                        "node": dict(node_row),
                        "distance": dist,
                        "path": path[:],
                    })

            if dist >= depth:
                continue

            # Outgoing edges
            out_rows = conn.execute(
                "SELECT to_id FROM edges WHERE from_id=?", (current_id,)
            ).fetchall()
            for r in out_rows:
                nid = r["to_id"]
                if nid not in visited:
                    visited.add(nid)
                    frontier.append((nid, dist + 1, path + [nid]))

            # Incoming edges
            in_rows = conn.execute(
                "SELECT from_id FROM edges WHERE to_id=?", (current_id,)
            ).fetchall()
            for r in in_rows:
                nid = r["from_id"]
                if nid not in visited:
                    visited.add(nid)
                    frontier.append((nid, dist + 1, path + [nid]))

        return jsonify({
            "seed": seed_dict,
            "neighbors": neighbors,
            "count": len(neighbors),
        })
    finally:
        conn.close()


@app.route("/consolidate", methods=["POST"])
def consolidate():
    conn = _get_db()
    try:
        # Decay activations: multiply by 0.9 for all > 0.1
        conn.execute(
            "UPDATE nodes SET activation = ROUND(activation * 0.9, 6) "
            "WHERE activation > 0.1"
        )

        # Find nodes to prune: activation < 0.05 AND no edges
        prunable = conn.execute(
            "SELECT n.id FROM nodes n "
            "WHERE n.activation < 0.05 "
            "AND NOT EXISTS (SELECT 1 FROM edges e WHERE e.from_id=n.id OR e.to_id=n.id)"
        ).fetchall()

        pruned_ids = [r["id"] for r in prunable]
        pruned_count = len(pruned_ids)

        for pid in pruned_ids:
            conn.execute("DELETE FROM nodes WHERE id=?", (pid,))

        remaining_count = conn.execute(
            "SELECT COUNT(*) AS c FROM nodes"
        ).fetchone()["c"]

        conn.commit()
        return jsonify({
            "pruned": pruned_count,
            "remaining": remaining_count,
        })
    finally:
        conn.close()


# ─── Error handlers ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(_e):
    return jsonify({"error": "not found"}), 404


@app.errorhandler(500)
def server_error(_e):
    return jsonify({"error": "internal server error"}), 500


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"LCN server running on http://{HOST}:{PORT}")
    sys.stdout.flush()
    app.run(host=HOST, port=PORT, debug=False)
