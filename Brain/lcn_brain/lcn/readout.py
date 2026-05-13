"""
§12 — Phase 5: ODE-Plastic Readout (C2 gated mixture).

Condition C2 (Spec §4.11): gated mixture readout.
    u = tanh([h; c])   ← gives U_max = 1 structurally
    z = W_z (u ⊙ sigma(beta * |u|))
    beta = BETA_0 / (U_max * exp(-A_MIN * DELTA_MIN))

Worked numbers: a_min=0.5, delta_min=2, U_max=1, beta_0=6
    → beta = 6e ≈ 16.31
    |u_j|=0.1 → sigma(1.63) ≈ 0.836  (sharp on active coords)
    |u_j|=0.001 → sigma(0.016) ≈ 0.504  (suppressive on quiescent)

Invariants:
  I-RO-1: quiescent suppression — gate → 0.5 at u_j→0, monotonic in |u_j|
  I-RO-2: JVP-clean — no `where` on tangents
  I-RO-3: ||z|| <= ||W_z||_F * sqrt(D+M)
"""

import jax
import jax.numpy as jnp
import jax.nn as jnn
from flax import linen as nn

from .constants import D, M, P, BETA_0, U_MAX, A_MIN, DELTA_MIN


def _calibrated_beta() -> float:
    """Compute β via §4.12 architectural calibration.

    β = β₀ / (U_max · e^{-a_min · Δ_min})

    This is constant — never trained.
    """
    return BETA_0 / (U_MAX * jnp.exp(-A_MIN * DELTA_MIN))


def pack_u(h: jnp.ndarray, c: jnp.ndarray) -> jnp.ndarray:
    """Pack SSF and RCD states into readout input vector.

    u = tanh([h; c])  → bounded in (-1, 1), U_max = 1 structurally.

    Args:
        h: SSF hidden state, shape (..., D).
        c: RCD episodic state, shape (..., M).

    Returns:
        u: Readout input, shape (..., D+M).
    """
    return jnp.tanh(jnp.concatenate([h, c], axis=-1))


class PlasticReadout(nn.Module):
    """C2 gated mixture readout: z = W_z · (u ⊙ σ(β|u|))."""

    @nn.compact
    def __call__(self, u: jnp.ndarray) -> jnp.ndarray:
        """Forward pass.

        Args:
            u: Readout input, shape (..., D+M).

        Returns:
            z: Readout output, shape (..., P).
        """
        beta = _calibrated_beta()
        gate = jnn.sigmoid(beta * jnp.abs(u))
        return nn.Dense(P, name="W_z", use_bias=False)(u * gate)


def readout_forward(W_z: jnp.ndarray, u: jnp.ndarray) -> jnp.ndarray:
    """Functional readout forward (no Flax module needed).

    Args:
        W_z: Plastic weight matrix, shape (P, D+M).
        u:   Readout input, shape (..., D+M).

    Returns:
        z: Readout output, shape (..., P).
    """
    beta = _calibrated_beta()
    gate = jnn.sigmoid(beta * jnp.abs(u))
    # u_gated shape (..., D+M), W_z shape (P, D+M) → z shape (..., P)
    return (u * gate) @ W_z.T


def readout_pullback(
    W_z: jnp.ndarray,
    u: jnp.ndarray,
    dz: jnp.ndarray,
) -> jnp.ndarray:
    """Pullback for JVP estimator: ∂z/∂W_z · dz.

    ∂z/∂W_z = u_gated^T, so the pullback is outer(dz, u_gated).

    Args:
        W_z: Plastic weight matrix, shape (P, D+M) — unused but kept for API consistency.
        u:   Readout input, shape (D+M,).
        dz:  Output tangent, shape (P,).

    Returns:
        Pullback tensor, shape (P, D+M) — same shape as W_z.
    """
    beta = _calibrated_beta()
    gate = jnn.sigmoid(beta * jnp.abs(u))
    u_gated = u * gate  # shape (D+M,)
    return jnp.outer(dz, u_gated)  # shape (P, D+M)
