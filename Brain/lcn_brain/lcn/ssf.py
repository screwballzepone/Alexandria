"""
§9 — Phase 2: Selective State Filter (SSF).

Mamba-style diagonal selective ODE:
    dh/dt = A(S) h + B(S) S

with A diagonal and a_i(S) <= -a_min < 0 structurally.
Diagonality buys: (i) parallel scan in O(log T),
(ii) per-coordinate contraction (Lemma 4),
(iii) spectral interpretability.

ZOH discretisation (exact for linear segment):
    h_{t+1} = e^{a*dt} h_t + a^{-1}(e^{a*dt} - 1) B S

Invariants:
  I-SSF-1: a_i <= -A_MIN structurally
  I-SSF-2: zero input => ||h_T|| <= ||h_0|| e^{-A_MIN * T}
  I-SSF-3: ZOH error O(dt^2)
"""

import jax
import jax.numpy as jnp
import jax.nn as jnn
from flax import linen as nn

from .constants import D, N_ENC, A_MIN, B_PARAM


class SSFParams(nn.Module):
    """Parameter module for the SSF: a(S) and B(S).

    a(S) = -A_MIN - softplus(W_a * S + b_a)  ← structural floor
    B(S) = linear or MLP (Theorem 2 only proven for linear).
    """

    hidden: int = 32

    @nn.compact
    def __call__(self, s_t: jnp.ndarray) -> tuple[jnp.ndarray, jnp.ndarray]:
        """Compute a(S) and B(S) for one timestep.

        Args:
            s_t: Spike input at time t, shape (N_ENC,).

        Returns:
            (a_t, B_t) — a_t shape (D,), B_t shape (D, N_ENC).
        """
        # a(S): structural floor ensures contraction
        a_raw = nn.Dense(D, name="a_proj")(s_t)
        a_t = -A_MIN - jnn.softplus(a_raw)  # a_t_i <= -A_MIN < 0

        # B(S): linear (proven) or MLP (open item g)
        if B_PARAM == "linear":
            B_flat = nn.Dense(D * N_ENC, name="B_lin")(s_t)
        else:
            h = jnn.gelu(nn.Dense(self.hidden, name="B_h")(s_t))
            B_flat = nn.Dense(D * N_ENC, name="B_o")(h)

        return a_t, B_flat.reshape(D, N_ENC)


def ssf_step(
    h_prev: jnp.ndarray,
    s_t: jnp.ndarray,
    params: SSFParams,
    dt: float = 1.0,
) -> tuple[jnp.ndarray, tuple[jnp.ndarray, jnp.ndarray]]:
    """Single SSF step with ZOH discretisation.

    h_{t+1} = exp(a*dt) * h_t  +  (-expm1(a*dt) / a) * (B @ s)

    Args:
        h_prev: Previous hidden state, shape (D,).
        s_t:    Spike input at time t, shape (N_ENC,).
        params: SSFParams module.
        dt:     Time step.

    Returns:
        (h_new, (a_t, B_t)) — new state and auxiliary tensors.
    """
    a_t, B_t = params(s_t)
    decay = jnp.exp(a_t * dt)
    one_minus = -jnp.expm1(a_t * dt)  # 1 - exp(a*dt), numerically stable
    drive = (one_minus / -a_t) * (B_t @ s_t)
    return decay * h_prev + drive, (a_t, B_t)


def run_ssf(
    s_window: jnp.ndarray,
    h0: jnp.ndarray,
    params: SSFParams,
) -> tuple[jnp.ndarray, tuple[jnp.ndarray, jnp.ndarray]]:
    """Run SSF over a window of spikes.

    Args:
        s_window: Spike sequence, shape (T, N_ENC).
        h0:       Initial hidden state, shape (D,).
        params:   SSFParams module.

    Returns:
        (h_final, (h_traj, (a_traj, B_traj))) — final state, trajectory, and aux.
    """

    def step(h, s_t):
        h_new, aux = ssf_step(h, s_t, params)
        return h_new, (h_new, aux)

    return jax.lax.scan(step, h0, s_window)


def l21_penalty(B_traj: jnp.ndarray) -> jnp.ndarray:
    """Column-l21 sparsity penalty for B(S) (Theorem 2).

    L_{2,1}(B) = sum_j ||B_{:,j}||_2  averaged over time.

    Args:
        B_traj: B(S) trajectory, shape (T, D, N_ENC).

    Returns:
        Scalar penalty.
    """
    col_norms = jnp.linalg.norm(B_traj, axis=1)  # (T, N_ENC)
    return col_norms.sum(axis=-1).mean()
