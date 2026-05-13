"""
§8 — Phase 1: Spike Encoder.

LIF neurons with Gaussian-CDF surrogate gradient.
No Heaviside anywhere — replaced by Phi_sigma in the forward pass.
Soft reset and refractory gate keep everything JVP-clean.

Invariants:
  I-ENC-1: s ∈ [0, 1]
  I-ENC-2: jax.jvp returns finite tangents
  I-ENC-3: As σ→0, mean rate → hard-threshold rate
"""

import jax
import jax.numpy as jnp
from jax.scipy.stats import norm

from .constants import (
    N_ENC,
    SIGMA_THRESHOLD,
    VTHETA_INIT,
    LEAK_TAU,
    REFRACTORY_STEPS,
)


def _refractory(t_since: jnp.ndarray, tau: float = REFRACTORY_STEPS) -> jnp.ndarray:
    """Soft multiplicative refractory gate: 0→1 over `tau` steps."""
    return 1.0 - jnp.exp(-t_since / tau)


def encoder_step(
    carry: tuple[jnp.ndarray, jnp.ndarray],
    x_t: jnp.ndarray,
    vtheta: jnp.ndarray,
    sigma: float = SIGMA_THRESHOLD,
    dt: float = 1.0,
) -> tuple[tuple[jnp.ndarray, jnp.ndarray], jnp.ndarray]:
    """Single encoder step: LIF dynamics + Gaussian-CDF surrogate firing.

    Args:
        carry: (v_prev, t_since) — membrane potentials and refractory timer.
        x_t:   Input at time t, shape (N_ENC,).
        vtheta: Threshold potentials, shape (N_ENC,).
        sigma:  Gaussian threshold smoothing width.
        dt:     Time step.

    Returns:
        ((v_new, t_new), s) — new carry and spike probability in [0, 1].
    """
    v_prev, t_since = carry
    # LIF voltage update: dv/dt = -v/tau + x
    v_new = v_prev + dt * (-(v_prev / LEAK_TAU) + x_t)
    # Refractory suppression
    refr = _refractory(t_since)
    # Smooth firing: Phi((v - theta) / sigma)  —  NEVER Heaviside
    s = refr * norm.cdf((v_new - vtheta) / sigma)  # in [0, 1]
    # Soft reset
    v_reset = v_new * (1.0 - s)
    # Refractory timer reset
    t_new = (t_since + dt) * (1.0 - s)
    return (v_reset, t_new), s


def encode_window(
    x_window: jnp.ndarray,
    v0: jnp.ndarray,
    vtheta: jnp.ndarray,
    sigma: float = SIGMA_THRESHOLD,
) -> tuple[tuple[jnp.ndarray, jnp.ndarray], jnp.ndarray]:
    """Encode a full window of input into spike probabilities.

    Args:
        x_window: Input sequence, shape (T, N_ENC).
        v0:       Initial membrane potentials, shape (N_ENC,).
        vtheta:   Threshold potentials, shape (N_ENC,).
        sigma:    Gaussian threshold smoothing width.

    Returns:
        ((v_final, t_final), S) — final carry and spike sequence (T, N_ENC).
    """
    carry0 = (v0, jnp.full_like(v0, REFRACTORY_STEPS))

    def step(c, x_t):
        return encoder_step(c, x_t, vtheta, sigma)

    return jax.lax.scan(step, carry0, x_window)


def init_encoder(key: jnp.ndarray) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Initialise encoder state.

    Args:
        key: JAX PRNG key.

    Returns:
        (v0, vtheta) — initial membrane potentials and threshold.
    """
    v0 = jnp.zeros(N_ENC)
    vtheta = jnp.full(N_ENC, VTHETA_INIT)
    return v0, vtheta


# --- Invariant checks (run after acceptance probes) ---


def check_i_enc_1(s: jnp.ndarray) -> bool:
    """I-ENC-1: All spike probabilities in [0, 1]."""
    return jnp.all((s >= 0.0) & (s <= 1.0)).item()


def check_i_enc_2(x_window: jnp.ndarray, v0: jnp.ndarray, vtheta: jnp.ndarray) -> bool:
    """I-ENC-2: jax.jvp returns finite tangents through encoder."""

    def f(v0_, vtheta_):
        _, S = encode_window(x_window, v0_, vtheta_)
        return jnp.sum(S)

    primals = (v0, vtheta)
    tangents = (
        jax.random.normal(jax.random.PRNGKey(0), v0.shape),
        jax.random.normal(jax.random.PRNGKey(1), vtheta.shape),
    )
    _, out_tangent = jax.jvp(f, primals, tangents)
    return jnp.all(jnp.isfinite(out_tangent)).item()
