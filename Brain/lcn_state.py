#!/usr/bin/env python3
"""
LCN State Inspector — snapshot of current / previous LCN training state.

Shows:
  1. LCN memory server status (online / offline) with node/edge counts.
  2. Top activated nodes from the memory server.
  3. Summary of the most recent Parquet diagnostics log.
  4. Next-tick prediction based on gate and weight trends.

Usage:
    python Brain/lcn_state.py
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from urllib.request import urlopen

# ─── Platform: try to use UTF-8 for box-drawing characters ─────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
    _ENC_OK = sys.stdout.encoding.lower() in ("utf-8", "utf8", "utf-16", "cp65001")
except Exception:
    _ENC_OK = False

# ─── Config ───────────────────────────────────────────────────────────────────
LCN_HOST = "127.0.0.1"
LCN_PORT = 3737
LCN_BASE = f"http://{LCN_HOST}:{LCN_PORT}"
TIMEOUT = 3

# Log directory: Brain/logs/ (relative to this script's location)
LOG_DIR = Path(__file__).resolve().parent / "logs"

# ─── Box-drawing chars (ASCII fallback for cp1252 consoles) ───────────────
if _ENC_OK:
    BOX_H   = "\u2550"   # ═
    BOX_V   = "\u2551"   # ║
    BOX_TL  = "\u2554"   # ╔
    BOX_TR  = "\u2557"   # ╗
    BOX_BL  = "\u255a"   # ╚
    BOX_BR  = "\u255d"   # ╝
    BOX_HL  = "\u2560"   # ╠
    BOX_HR  = "\u2563"   # ╣
    ARROW_R = "\u2192"   # →
    ARROW_U = "\u2191"   # ↑
    ARROW_D = "\u2193"   # ↓
    MU_SYM  = "\u03bc"   # μ
    EM_DASH = "\u2014"   # —
else:
    BOX_H   = "="
    BOX_V   = "|"
    BOX_TL  = "+"
    BOX_TR  = "+"
    BOX_BL  = "+"
    BOX_BR  = "+"
    BOX_HL  = "+"
    BOX_HR  = "+"
    ARROW_R = "->"
    ARROW_U = "^"
    ARROW_D = "v"
    MU_SYM  = "u"
    EM_DASH = "-"

# ─── ANSI color codes ────────────────────────────────────────────────────────


class C:
    """Terminal ANSI color constants."""
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    GREY = "\033[90m"
    RESET = "\033[0m"


def _c(val: float, lo: float = 0.3, hi: float = 0.8) -> str:
    """Return a color-wrapped string based on value thresholds."""
    if val >= hi:
        return f"{C.GREEN}{val}{C.RESET}"
    elif val >= lo:
        return f"{C.YELLOW}{val}{C.RESET}"
    else:
        return f"{C.RED}{val}{C.RESET}"


# ─── LCN Client helpers (inline, zero external deps) ─────────────────────────

def _server_running() -> bool:
    """Check whether LCN memory server is listening on the configured port."""
    try:
        with socket.create_connection((LCN_HOST, LCN_PORT), timeout=1):
            return True
    except OSError:
        return False


def _http_get(path: str, params: dict | None = None) -> dict | None:
    """Perform a GET request to the LCN server and return parsed JSON."""
    try:
        url = f"{LCN_BASE}{path}"
        if params:
            from urllib.parse import urlencode
            qs = urlencode({k: v for k, v in params.items() if v is not None})
            url += "?" + qs
        with urlopen(url, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except Exception:
        return None


# ─── Parquet reading (optional dependency) ──────────────────────────────────

try:
    import pyarrow.parquet as pq

    PARQUET_AVAILABLE = True
except ImportError:
    PARQUET_AVAILABLE = False


def _latest_log() -> Path | None:
    """Return the path to the most recently modified .parquet file."""
    if not LOG_DIR.is_dir():
        return None
    parquets = sorted(LOG_DIR.glob("*.parquet"), key=os.path.getmtime, reverse=True)
    return parquets[0] if parquets else None


def _read_parquet_summary(path: Path) -> dict | None:
    """Read a diagnostics Parquet file and return a summary dict."""
    if not PARQUET_AVAILABLE:
        return None
    try:
        table = pq.read_table(str(path))
    except Exception as e:
        return {"error": str(e)}

    col_names = {name for name in table.column_names}
    df = table.to_pandas()

    total_ticks = int(df["tau_k"].nunique())
    final_loss = float(df["loss_local"].iloc[-1])

    avg_gate = float(df["gate"].mean()) if "gate" in col_names else None
    avg_kappa = float(df["kappa_hat"].mean()) if "kappa_hat" in col_names else None
    arm_name = str(df["arm"].iloc[0]) if "arm" in col_names else "unknown"

    # Weight norm trajectory
    W_norm_first = float(df["W_norm"].iloc[0]) if "W_norm" in col_names and len(df) > 0 else None
    W_norm_last = float(df["W_norm"].iloc[-1]) if "W_norm" in col_names and len(df) > 0 else None
    W_norm_pct = (
        ((W_norm_last / max(W_norm_first, 1e-12)) - 1) * 100
        if W_norm_first is not None and W_norm_last is not None
        else None
    )

    # Gradient norm trajectory
    g_norm_first = float(df["g_norm"].iloc[0]) if "g_norm" in col_names and len(df) > 0 else None
    g_norm_last = float(df["g_norm"].iloc[-1]) if "g_norm" in col_names and len(df) > 0 else None

    # Tick value distribution
    d_k_vals = (
        sorted(int(x) for x in df["d_k"].dropna().unique())
        if "d_k" in col_names
        else None
    )

    # Extract T_encoder from filename: e.g. "arm_c_T=100.parquet"
    T_encoder: int | None = None
    if "T=" in path.stem:
        try:
            T_encoder = int(path.stem.split("T=")[1])
        except (ValueError, IndexError):
            pass

    # Gate trend: least-squares slope over last 5 gate values
    gate_trend: float | None = None
    if "gate" in col_names and len(df) >= 5:
        recent = df["gate"].tail(5).values.astype(float)
        xs = list(range(len(recent)))
        n = len(xs)
        sx = sum(xs)
        sy = sum(recent)
        sxx = sum(x * x for x in xs)
        sxy = sum(x * y for x, y in zip(xs, recent))
        denom = n * sxx - sx * sx
        if denom != 0:
            gate_trend = (n * sxy - sx * sy) / denom  # slope per tick

    return {
        "total_ticks": total_ticks,
        "final_loss": final_loss,
        "avg_gate": avg_gate,
        "avg_kappa": avg_kappa,
        "arm_name": arm_name,
        "T_encoder": T_encoder,
        "W_norm_first": W_norm_first,
        "W_norm_last": W_norm_last,
        "W_norm_pct": W_norm_pct,
        "g_norm_first": g_norm_first,
        "g_norm_last": g_norm_last,
        "d_k_vals": d_k_vals,
        "gate_trend": gate_trend,
        "num_rows": len(df),
        "file_name": path.name,
    }


# ─── Render ──────────────────────────────────────────────────────────────────

def _hr(title: str = "", width: int = 54) -> str:
    """Return a horizontal rule with optional centred title."""
    if title:
        pad = width - len(title) - 2
        left = pad // 2
        right = pad - left
        return f"{BOX_HL}{BOX_H * left} {title} {BOX_H * right}{BOX_HR}"
    return f"{BOX_HL}{BOX_H * width}{BOX_HR}"


def _box_top(width: int = 54) -> str:
    return f"{BOX_TL}{BOX_H * width}{BOX_TR}"


def _box_bot(width: int = 54) -> str:
    return f"{BOX_BL}{BOX_H * width}{BOX_BR}"


def _line(left: str, right: str = "", width: int = 54) -> str:
    """Return a boxed line with left-aligned and right-aligned content."""
    inner = left
    if right:
        fill = width - len(left) - len(right)
        inner = left + (" " * max(fill, 1)) + right
    return f"{BOX_V} {inner:<{width}} {BOX_V}"


def _color_val(val, fmt: str = ".4f") -> str:
    """Format and color a numeric value."""
    if val is None:
        return f"{C.GREY}N/A{C.RESET}"
    return f"{val:{fmt}}"


def _render(
    server_online: bool,
    stats: dict | None,
    nodes: list,
    log_summary: dict | None,
) -> None:
    """Render the full state inspector output."""
    W = 54  # box width

    # ── Header ──────────────────────────────────────────────────────────
    print()
    print(f"{C.BOLD}{_box_top(W)}{C.RESET}")
    print(f"{C.BOLD}{_line('LCN STATE INSPECTOR', '', W)}{C.RESET}")
    print(f"{C.BOLD}{_hr(width=W)}{C.RESET}")

    # ── Server status ───────────────────────────────────────────────────
    if server_online:
        status_str = f"{C.GREEN}ONLINE{C.RESET} ({LCN_HOST}:{LCN_PORT})"
        node_count = stats.get("nodeCount", "?") if stats else "?"
        edge_count = stats.get("edgeCount", "?") if stats else "?"
        avg_act = stats.get("avgActivation", "?") if stats else "?"
        print(_line(f" Memory Server: {status_str}", "", W))
        act_colored = (
            f"{C.GREEN}{avg_act}{C.RESET}"
            if isinstance(avg_act, (int, float)) and avg_act >= 0.3
            else (
                f"{C.YELLOW}{avg_act}{C.RESET}"
                if isinstance(avg_act, (int, float)) and avg_act >= 0.1
                else f"{C.GREY}{avg_act}{C.RESET}"
            )
        )
        print(
            _line(
                f" Nodes: {C.BOLD}{node_count}{C.RESET}  "
                f"Edges: {C.BOLD}{edge_count}{C.RESET}  "
                f"Avg Activation: {act_colored}",
                "",
                W,
            )
        )
    else:
        print(_line(f" Memory Server: {C.RED}OFFLINE{C.RESET}", "", W))
        print(_line(" (start with: python Brain/lcn_brain/lcn_server.py)", "", W))

    print(_hr(width=W))

    # ── Top nodes from server ───────────────────────────────────────────
    if server_online and nodes:
        print(f"{C.BOLD}{_line('TOP NODES BY ACTIVATION', '', W)}{C.RESET}")
        for i, entry in enumerate(nodes[:5], 1):
            node = entry.get("node", {})
            label = node.get("label", "?")
            value = node.get("value", "?")
            activation = node.get("activation", 0.0)
            edge_count = len(entry.get("edges", []))
            # Truncate long values
            display_value = value if len(str(value)) <= 32 else str(value)[:29] + "..."
            act_str = f"{activation:.2f}"
            if activation >= 0.5:
                act_str = f"{C.GREEN}{act_str}{C.RESET}"
            elif activation >= 0.2:
                act_str = f"{C.YELLOW}{act_str}{C.RESET}"
            else:
                act_str = f"{C.GREY}{act_str}{C.RESET}"
            print(
                _line(
                    f" {i}. {C.CYAN}{label}{C.RESET} ({display_value})",
                    f"{act_str} {ARROW_R} {edge_count} edge{'s' if edge_count != 1 else ''}",
                    W,
                )
            )
        if len(nodes) > 5:
            print(_line(f"    ... and {len(nodes) - 5} more nodes", "", W))
        print(_hr(width=W))
    elif server_online:
        print(_line(f" {C.GREY}No nodes in memory yet.{C.RESET}", "", W))
        print(_hr(width=W))

    # ── Last training run (from Parquet) ────────────────────────────────
    if log_summary and "error" not in log_summary:
        arm = log_summary["arm_name"]
        T_info = f"T={log_summary['T_encoder']}" if log_summary["T_encoder"] else ""
        run_header = f"LAST TRAINING RUN  ({arm}{', ' + T_info if T_info else ''})"
        print(f"{C.BOLD}{_line(run_header, '', W)}{C.RESET}")

        # Ticks & loss
        total = log_summary["total_ticks"]
        loss = log_summary["final_loss"]
        print(
            _line(
                f"  Ticks: {C.BOLD}{total}{C.RESET}  |  "
                f"Final Loss: {_color_val(loss)}",
                "",
                W,
            )
        )

        # Gate, kappa, d_k
        avg_g = log_summary.get("avg_gate")
        avg_k = log_summary.get("avg_kappa")
        d_k = log_summary.get("d_k_vals")
        k_str = f"{avg_k:.2f}" if avg_k is not None else "N/A"
        dk_str = (
            f"{min(d_k)}-{max(d_k)}" if d_k and len(d_k) > 1 else (str(d_k[0]) if d_k else "N/A")
        )
        print(
            _line(
                f"  Avg Gate: {_c(avg_g, 0.3, 0.7) if avg_g is not None else 'N/A'}  |  "
                f"Avg Kappa: {k_str}  |  d_k: {dk_str}",
                "",
                W,
            )
        )

        # W_norm trajectory
        W_first = log_summary.get("W_norm_first")
        W_last = log_summary.get("W_norm_last")
        W_pct = log_summary.get("W_norm_pct")
        if W_first is not None and W_last is not None:
            arrow = ARROW_U if W_pct and W_pct > 0 else ARROW_D
            pct_str = f"{abs(W_pct):.1f}%" if W_pct is not None else "N/A"
            color = C.GREEN if (W_pct or 0) > 0 else (C.RED if (W_pct or 0) < -5 else C.YELLOW)
            print(
                _line(
                    f"  W_norm: {W_first:.4f} {ARROW_R} {W_last:.4f}  "
                    f"({color}{arrow}{pct_str}{C.RESET})",
                    "",
                    W,
                )
            )

        # g_norm trajectory
        g_first = log_summary.get("g_norm_first")
        g_last = log_summary.get("g_norm_last")
        if g_first is not None and g_last is not None:
            print(
                _line(
                    f"  |g|: {g_first:.3e} {ARROW_R} {g_last:.3e}",
                    "",
                    W,
                )
            )

        print(_hr(width=W))

        # ── Next tick prediction ────────────────────────────────────────
        print(f"{C.BOLD}{_line('NEXT TICK PREDICTION', '', W)}{C.RESET}")

        gate_trend = log_summary.get("gate_trend")
        avg_gate_val = log_summary.get("avg_gate")

        if gate_trend is not None and avg_gate_val is not None:
            if gate_trend < -0.01:
                trend_dir = f"{C.RED}closing{C.RESET}"
                phase = "quiescent"
                mu_msg = (
                    f"contraction {MU_SYM} will rise to ~"
                    f"{min(0.5, 0.5 - gate_trend * 5):.2f}"
                )
                weight_msg = (
                    f"weight norm expected to decay ~"
                    f"{min(10, abs(gate_trend) * 50):.0f}%"
                )
            elif gate_trend > 0.01 and avg_gate_val < 0.8:
                trend_dir = f"{C.GREEN}opening{C.RESET}"
                phase = "active assimilation"
                mu_msg = f"contraction {MU_SYM} will drop toward 0"
                weight_msg = "weight norm expected to drift upward"
            else:
                trend_dir = f"{C.YELLOW}stable{C.RESET}"
                phase = "steady"
                mu_msg = f"contraction {MU_SYM} will remain near current level"
                weight_msg = "weight norm expected to stay flat"

            print(_line(f"  Gate trend: {trend_dir} ({gate_trend:+.3f}/tick)", "", W))
            print(_line(f"  {ARROW_R} Network in {phase} phase", "", W))
            print(_line(f"  {ARROW_R} {mu_msg}", "", W))
            print(_line(f"  {ARROW_R} {weight_msg}", "", W))
        elif avg_gate_val is not None:
            # Insufficient data for trend
            if avg_gate_val > 0.9:
                print(
                    _line(
                        f"  Gate: {C.GREEN}fully open{C.RESET} ({avg_gate_val:.2f})",
                        "",
                        W,
                    )
                )
                print(_line(f"  {ARROW_R} Network in quiescent phase", "", W))
                print(
                    _line(
                        f"  {ARROW_R} Contraction {MU_SYM} near "
                        f"{C.GREEN}0.50{C.RESET} (MU_MIN)",
                        "",
                        W,
                    )
                )
            elif avg_gate_val < 0.3:
                print(
                    _line(
                        f"  Gate: {C.RED}mostly closed{C.RESET} ({avg_gate_val:.2f})",
                        "",
                        W,
                    )
                )
                print(_line(f"  {ARROW_R} Network in active phase", "", W))
                print(
                    _line(
                        f"  {ARROW_R} Contraction {MU_SYM} near "
                        f"{C.RED}0.0{C.RESET} (MU_FREE)",
                        "",
                        W,
                    )
                )
            else:
                print(
                    _line(
                        f"  Gate: {C.YELLOW}transitional{C.RESET} "
                        f"({avg_gate_val:.2f})",
                        "",
                        W,
                    )
                )
                print(_line(f"  {ARROW_R} Network in mixed mode", "", W))
        else:
            print(_line(f"  {C.GREY}Insufficient data for prediction.{C.RESET}", "", W))

    elif log_summary and "error" in log_summary:
        print(_line(f" {C.RED}Parquet error: {log_summary['error']}{C.RESET}", "", W))
        print(_hr(width=W))
    elif not server_online:
        # No server, no logs -- show fallback
        print(_line(f" {C.YELLOW}No training logs found.{C.RESET}", "", W))
        print(_line(f" Checked: {LOG_DIR}", "", W))
        if not PARQUET_AVAILABLE:
            print(
                _line(
                    f" {C.RED}pyarrow not installed {EM_DASH} "
                    f"cannot read logs.{C.RESET}",
                    "",
                    W,
                )
            )
        print(_line(" Run compare_arms() or start the server first.", "", W))
        print(_hr(width=W))

    # ── Footer ──────────────────────────────────────────────────────────
    print(f"{_box_bot(W)}")
    print()


# ─── Main entry point ───────────────────────────────────────────────────────

def inspect() -> None:
    """Gather all LCN state info and render the report."""
    # ── Check server ────────────────────────────────────────────────────
    server_online = _server_running()

    # ── Try Parquet fallback ────────────────────────────────────────────
    log_path = _latest_log()

    # ── Gather data ─────────────────────────────────────────────────────
    server_stats = _http_get("/stats") if server_online else None

    nodes: list = []
    if server_online:
        qr = _http_get("/query", {"limit": 100})
        if qr and "results" in qr:
            nodes = sorted(
                qr["results"],
                key=lambda r: r.get("node", {}).get("activation", 0),
                reverse=True,
            )

    log_summary = _read_parquet_summary(log_path) if log_path else None

    # ── Render ──────────────────────────────────────────────────────────
    _render(server_online, server_stats, nodes, log_summary)


def main() -> None:
    """CLI entry point."""
    try:
        inspect()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
    except Exception as e:
        print(f"\n{C.RED}Error:{C.RESET} {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
