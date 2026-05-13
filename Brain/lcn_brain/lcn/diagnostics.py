"""
§16 — Diagnostics: log every tick to Parquet.

Flat-schema, one row per tick per arm.
LOG_FIELDS: tau_k, rho_t, rho_ema, gate, kappa_hat, d_k, r2_violation,
            truncated, loss_local, W_norm, g_norm, u_max_q, u_max_a,
            beta_eff, arm.

Why each matters (see §17 failure-mode taxonomy):
  - kappa_hat + r2_violation: persistent True = switched contraction not engaging
  - d_k ≈ D+M always: sparsity gone — (R7) failed
  - truncated: should be rare; frequent = tighten JVP_TRUNCATION_RADIUS
  - u_max_q / u_max_a > 0.1: gate isn't isolating the quiescent set
  - beta_eff: must be constant; drift = BETA_0 accidentally trainable
"""

from dataclasses import asdict
from pathlib import Path
from typing import Optional

import jax.numpy as jnp

try:
    import pyarrow as pa
    import pyarrow.parquet as pq

    _PARQUET_AVAILABLE = True
except ImportError:
    _PARQUET_AVAILABLE = False

from .types import TickRecord

# Mirroring §16 field list
LOG_FIELDS = [
    "tau_k",
    "rho_t",
    "rho_ema",
    "gate",
    "kappa_hat",
    "d_k",
    "r2_violation",
    "truncated",
    "loss_local",
    "W_norm",
    "g_norm",
    "u_max_q",
    "u_max_a",
    "beta_eff",
    "arm",
]


class DiagnosticsWriter:
    """Accumulate tick records and flush to Parquet."""

    def __init__(self, output_dir: str = "./logs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._records: list[dict] = []

    def log(self, record: TickRecord) -> None:
        """Record one tick's diagnostics.

        Args:
            record: TickRecord dataclass with all 15+ fields.
        """
        self._records.append(asdict(record))

    def flush(self, filename: str = "diagnostics.parquet") -> Optional[Path]:
        """Write all accumulated records to Parquet.

        Args:
            filename: Output filename.

        Returns:
            Path to written file, or None if no records or pyarrow missing.
        """
        if not self._records:
            return None
        if not _PARQUET_AVAILABLE:
            print("[diagnostics] pyarrow not installed — skipping Parquet write.")
            return None

        out_path = self.output_dir / filename
        table = pa.Table.from_pylist(self._records)
        pq.write_table(table, out_path)
        self._records = []
        return out_path

    @property
    def record_count(self) -> int:
        return len(self._records)


def compute_diagnostics(
    tick_idx: int,
    rho_t: jnp.ndarray,
    rho_ema: jnp.ndarray,
    gate: jnp.ndarray,
    kappa_hat: jnp.ndarray,
    d_k: jnp.ndarray,
    r2_violation: bool,
    truncated: bool,
    loss_local: jnp.ndarray,
    W_norm: jnp.ndarray,
    g_norm: jnp.ndarray,
    u: jnp.ndarray,
    beta_eff: jnp.ndarray,
    arm: str,
) -> TickRecord:
    """Compute all diagnostic fields from raw tensors.

    Derives u_max_q (quiescent) and u_max_a (active) from the readout input u.

    Args:
        tick_idx:     Tick number (tau_k).
        rho_t:        Raw spike norm at tick.
        rho_ema:      EMA tracked norm.
        gate:         Soft gate g(t).
        kappa_hat:    Condition estimate.
        d_k:          Active dimension.
        r2_violation: R² violation flag.
        truncated:    Truncation flag.
        loss_local:   Local loss value.
        W_norm:       Frobenius norm of W_z.
        g_norm:       Norm of gradient estimate.
        u:            Readout input vector (D+M,).
        beta_eff:     Effective β.
        arm:          Arm name.

    Returns:
        Populated TickRecord.
    """
    # Separate quiescent (|u_j| < threshold) vs active
    threshold = 0.05
    u_abs = jnp.abs(u)
    u_q = jnp.where(u_abs < threshold, u_abs, 0.0)
    u_a = jnp.where(u_abs >= threshold, u_abs, 0.0)
    u_max_q = jnp.max(u_q).item()
    u_max_a = jnp.max(u_a).item()

    return TickRecord(
        tau_k=tick_idx,
        rho_t=float(rho_t),
        rho_ema=float(rho_ema),
        gate=float(gate),
        kappa_hat=float(kappa_hat),
        d_k=int(d_k),
        r2_violation=r2_violation,
        truncated=truncated,
        loss_local=float(loss_local),
        W_norm=float(W_norm),
        g_norm=float(g_norm),
        u_max_q=u_max_q,
        u_max_a=u_max_a,
        beta_eff=float(beta_eff),
        arm=arm,
    )


def print_tick_summary(record: TickRecord) -> None:
    """Print a one-line summary of a tick record for console monitoring.

    Args:
        record: TickRecord to summarise.
    """
    flags = []
    if record.r2_violation:
        flags.append("R2!")
    if record.truncated:
        flags.append("TRUNC!")
    flag_str = " ".join(flags) if flags else "—"

    print(
        f"  t={record.tau_k:4d} | gate={record.gate:.3f} | "
        f"d_k={record.d_k:3d} | loss={record.loss_local:.4e} | "
        f"|W|={record.W_norm:.3f} | |g|={record.g_norm:.3e} | "
        f"k={record.kappa_hat:.3f} | flags: {flag_str}"
    )


def sanity_check(record: TickRecord) -> list[str]:
    """Run quick sanity checks on a tick record.

    Args:
        record: TickRecord to check.

    Returns:
        List of warning strings (empty if all clear).
    """
    warnings = []
    if record.gate < 0.25 and record.r2_violation:
        warnings.append("Gate low + R2 violation — contraction may not be engaging")
    if record.d_k >= 128:  # D+M = 96, so this is "nearly all"
        warnings.append(f"d_k={record.d_k} is high — active set may not be sparsifying")
    if record.truncated:
        warnings.append("Truncation flag set — check JVP_TRUNCATION_RADIUS")
    if record.u_max_q / max(record.u_max_a, 1e-8) > 0.1:
        warnings.append(
            f"u_max_q/u_max_a = {record.u_max_q / max(record.u_max_a, 1e-8):.3f} > 0.1 "
            "— gate may not be isolating quiescent set"
        )
    return warnings


def summarize_last_run(log_dir: str = "./logs") -> Optional[dict]:
    """Read the most recent Parquet diagnostics file and return a summary.

    Args:
        log_dir: Directory containing .parquet diagnostic files.

    Returns:
        Dict with keys: total_ticks, final_loss, avg_gate, avg_kappa,
        arm_name, T_encoder, W_norm_first, W_norm_last, W_norm_pct,
        g_norm_first, g_norm_last, d_k_vals, gate_trend, num_rows, file_name.
        Returns None if no files found or pyarrow unavailable.
        Returns {"error": <msg>} on I/O or parse failure.
    """
    import os
    from pathlib import Path

    if not _PARQUET_AVAILABLE:
        return None

    log_dir_path = Path(log_dir)
    if not log_dir_path.is_dir():
        return None

    parquets = sorted(
        log_dir_path.glob("*.parquet"),
        key=os.path.getmtime,
        reverse=True,
    )
    if not parquets:
        return None

    path = parquets[0]
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

    W_norm_first = float(df["W_norm"].iloc[0]) if "W_norm" in col_names and len(df) > 0 else None
    W_norm_last = float(df["W_norm"].iloc[-1]) if "W_norm" in col_names and len(df) > 0 else None
    W_norm_pct = (
        ((W_norm_last / max(W_norm_first, 1e-12)) - 1) * 100
        if W_norm_first is not None and W_norm_last is not None
        else None
    )
    g_norm_first = float(df["g_norm"].iloc[0]) if "g_norm" in col_names and len(df) > 0 else None
    g_norm_last = float(df["g_norm"].iloc[-1]) if "g_norm" in col_names and len(df) > 0 else None
    d_k_vals = (
        sorted(int(x) for x in df["d_k"].dropna().unique())
        if "d_k" in col_names
        else None
    )

    # Extract T_encoder from filename: e.g. "arm_c_T=100.parquet"
    T_encoder: Optional[int] = None
    if "T=" in path.stem:
        try:
            T_encoder = int(path.stem.split("T=")[1])
        except (ValueError, IndexError):
            pass

    # Gate trend: least-squares slope over last 5 ticks
    gate_trend: Optional[float] = None
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
            gate_trend = (n * sxy - sx * sy) / denom

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
