"""
§11 — Phase 4: Recurrent Context Distiller (RCD).

LSTM-flavored gated recurrence that fires ONLY on distillation ticks.
At each tick:
    f_k = sigma(W_f h_k + U_f c_{k-1} + b_f)
    i_k = sigma(W_i h_k + U_i c_{k-1})
    c_tilde_k = tanh(W_c h_k + U_c c_{k-1})
    c_k = f_k ⊙ c_{k-1}  +  i_k ⊙ c_tilde_k

Forget-gate bias init b_f = 1.0 (Jozefowicz trick):
sigma(1.0) ≈ 0.73 at start, encouraging retention.

Invariants:
    I-RCD-1: ||c_k||_∞ <= 2 (independent forget/input gates can sum > 1; empirically bounded by 2 at init)
  I-RCD-2: RCD invoked ONLY on ticks (CI-grep enforces)
  I-RCD-3: forget-gate mean ≈ 0.73 at init
"""

import jax
import jax.numpy as jnp
import jax.nn as jnn
from flax import linen as nn

from .constants import M, D


class RCDCell(nn.Module):
    """Recurrent Context Distiller cell — LSTM-flavored, tick-gated."""

    @nn.compact
    def __call__(self, h_k: jnp.ndarray, c_prev: jnp.ndarray) -> jnp.ndarray:
        """Apply RCD update at a tick.

        Args:
            h_k:    SSF hidden state at tick, shape (D,).
            c_prev: Previous episodic memory, shape (M,).

        Returns:
            c_k: Updated episodic memory, shape (M,).
        """
        # Forget-gate bias init = 1.0 → sigma(1.0) ≈ 0.73 (Jozefowicz trick)
        bf = self.param("bf", nn.initializers.constant(1.0), (M,))

        f = jnn.sigmoid(nn.Dense(M, name="Wf")(h_k) + nn.Dense(M, use_bias=False, name="Uf")(c_prev) + bf)
        i = jnn.sigmoid(nn.Dense(M, name="Wi")(h_k) + nn.Dense(M, use_bias=False, name="Ui")(c_prev))
        c_tilde = jnp.tanh(nn.Dense(M, name="Wc")(h_k) + nn.Dense(M, use_bias=False, name="Uc")(c_prev))

        return f * c_prev + i * c_tilde


def init_rcd() -> jnp.ndarray:
    """Initialise RCD state.

    Returns:
        c0: Zero-initialised cell state, shape (M,).
    """
    return jnp.zeros(M)


def rcd_step(
    cell: RCDCell,
    c_prev: jnp.ndarray,
    h_t: jnp.ndarray,
    tick: jnp.ndarray,
) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Conditional RCD step — only updates on ticks.

    Args:
        cell:   RCDCell module.
        c_prev: Previous cell state, shape (M,).
        h_t:    Current SSF hidden state, shape (D,).
        tick:   Boolean tick flag (scalar).

    Returns:
        (c_new, c_new_or_prev) — updated state and the actual value used
        (same on tick, prev otherwise — for trajectory logging).
    """

    def do_update(_):
        return cell(h_t, c_prev)

    def skip_update(_):
        return c_prev

    # Use cond to keep computation on-tick only
    c_new = jax.lax.cond(tick, do_update, skip_update, None)
    return c_new, c_new
