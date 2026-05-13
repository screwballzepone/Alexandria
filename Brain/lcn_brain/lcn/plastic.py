"""
§13 — Phase 6: Plastic-weight ODE (Approach A).

Switched contraction:
    dW_z/dt = g_hat - mu(t) * W_z
    mu(t) = mu_free + (mu_min - mu_free) * g(t)

With g=1, g_hat=0: d||W||_F^2/dt = -2||W||_F^2  →  ||W(t)|| = ||W_0|| e^{-t}
With g=0: d||W||_F^2/dt = 2 tr(W^T g_hat)  →  weights drift freely.

This is Lemma 4's switched contraction lifted to parameters.

Invariants:
  I-PL-1: g_hat=0, g≈1 → ||W_z||_F decays at rate mu_min
  I-PL-2: free regime → W_z tracks integral of g_hat
  I-PL-3: Euler stability: eta * MU_MIN < 2
"""

import jax.numpy as jnp

from .clock import gate_value
from .constants import (
    ETA_PLASTIC,
    MU_FREE,
    MU_MIN,
)


def _mu_effective(g_t: jnp.ndarray) -> jnp.ndarray:
    """Switched contraction rate.

    μ(t) = μ_free + (μ_min - μ_free) · g(t)

    Args:
        g_t: Soft gate value in [0, 1].

    Returns:
        μ(t) — effective contraction rate.
    """
    return MU_FREE + (MU_MIN - MU_FREE) * g_t


def plastic_euler_step(
    W_z: jnp.ndarray,
    g_hat: jnp.ndarray,
    rho_ema: jnp.ndarray,
    eta: float = ETA_PLASTIC,
) -> jnp.ndarray:
    """Euler step for plastic ODE.

    W_{t+1} = W_t + η · (ĝ_θ - μ(t) · W_t)

    Args:
        W_z:     Plastic weight matrix, shape (P, D+M).
        g_hat:   JVP gradient estimate, shape (P, D+M).
        rho_ema: Clock EMA for gate computation.
        eta:     Step size (default 1e-3, safe: eta * MU_MIN < 2).

    Returns:
        Updated W_z.
    """
    g_t = gate_value(rho_ema)
    mu_t = _mu_effective(g_t)
    return W_z + eta * (g_hat - mu_t * W_z)


def plastic_heun_step(
    W_z: jnp.ndarray,
    g_hat: jnp.ndarray,
    rho_ema: jnp.ndarray,
    eta: float = ETA_PLASTIC,
) -> jnp.ndarray:
    """Heun (trapezoidal) step for plastic ODE — 2nd order.

    k1 = F(W)
    W_p = W + η·k1
    k2 = F(W_p)
    W_{t+1} = W + η/2 · (k1 + k2)

    where F(W) = ĝ_θ - μ(t)·W

    Args:
        W_z:     Plastic weight matrix, shape (P, D+M).
        g_hat:   JVP gradient estimate, shape (P, D+M).
        rho_ema: Clock EMA for gate computation.
        eta:     Step size.

    Returns:
        Updated W_z.
    """
    g_t = gate_value(rho_ema)
    mu_t = _mu_effective(g_t)

    def F(W):
        return g_hat - mu_t * W

    k1 = F(W_z)
    W_p = W_z + eta * k1
    k2 = F(W_p)
    return W_z + 0.5 * eta * (k1 + k2)
