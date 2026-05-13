"""
Surrogate-gradient BPTT baseline for the Burgers' 4-arm testbed.

This file lives in testbed/ (not lcn/) per I1 — it is ALLOWED to import jax.grad.
It provides an external baseline that uses reverse-mode autodiff to train
the readout weights W_z, for comparison with the forward-mode LCN arms.
"""

import jax
import jax.numpy as jnp

from .burgers import (
    simulate,
    rate_code,
    loss_mse,
)
from ..encoder import init_encoder, encode_window
from ..ssf import SSFParams, run_ssf
from ..clock import run_clock
from ..rcd import RCDCell, init_rcd, rcd_step
from ..readout import readout_forward, pack_u
from ..constants import D, M, P, N_ENC


def run_bptt_arm(
    key: jnp.ndarray,
    u0: jnp.ndarray,
    nu: float,
    T_encoder: int,
    n_steps_per_enc: int,
    n_epochs: int = 1,
    lr: float = 1e-3,
) -> dict:
    """Run the BPTT surrogate-gradient baseline arm.

    Per I1, this uses jax.grad to train the readout weight W_z via reverse-mode
    autodiff through the *unrolled* forward pass. Only W_z is optimised (fair
    comparison vs LCN arms which also only train W_z).

    Args:
        key:             JAX PRNG key.
        u0:              Initial condition, shape (NX,).
        nu:              Viscosity.
        T_encoder:       Number of encoder steps.
        n_steps_per_enc: RK4 steps per encoder step.
        n_epochs:        Number of training epochs (full-pass optimisations).
        lr:              Adam learning rate.

    Returns:
        Dict with keys matching run_arm() plus 'W_z_final':
            'arm_name', 'loss_history', 'tick_count', 'u_final', 'u_traj',
            'W_z_final'.
    """
    # ---- 1. PDE simulation (same as arms.py) ----
    n_pde_steps = T_encoder * n_steps_per_enc
    u_final, u_traj = simulate(u0, nu, n_pde_steps)
    u_enc = u_traj[::n_steps_per_enc, :]
    if u_enc.shape[0] < T_encoder:
        pad = T_encoder - u_enc.shape[0]
        u_enc = jnp.concatenate([u_enc, jnp.tile(u_enc[-1:], (pad, 1))], axis=0)

    # Rate-code the velocity fields
    x_enc = jax.vmap(rate_code)(u_enc)  # (T_encoder, N_ENC)

    # Target: next-step velocity field (shifted by 1)
    u_target = jnp.roll(u_enc, -1, axis=0)  # (T_encoder, NX)

    # ---- 2. Encoder: precomputed (not trained) ----
    key, subkey = jax.random.split(key)
    v0, vtheta = init_encoder(subkey)
    _, S = encode_window(x_enc, v0, vtheta)  # (T_encoder, N_ENC)

    # ---- 3. SSF: precomputed (not trained) ----
    key, subkey = jax.random.split(key)
    ssf_params = SSFParams()
    ssf_vars = ssf_params.init(subkey, jnp.zeros(N_ENC))
    ssf_bound = ssf_params.bind(ssf_vars)
    h0 = jnp.zeros(D)
    _, (h_traj, _) = run_ssf(S, h0, ssf_bound)  # (T_encoder, D)

    # ---- 4. Clock: precomputed (not trained) ----
    _, ticks, _, _ = run_clock(S)  # (T_encoder,) bool

    # ---- 5. RCD cell: precomputed (not trained) ----
    key, subkey = jax.random.split(key)
    rcd_cell = RCDCell()
    rcd_vars = rcd_cell.init(subkey, jnp.zeros(D), jnp.zeros(M))
    rcd_bound = rcd_cell.bind(rcd_vars)

    # ---- 6. Initialise readout weight W_z ----
    key, subkey = jax.random.split(key)
    W_z = jax.random.normal(subkey, (P, D + M)) * 0.01

    # ---- 7. BPTT loss function (differentiable w.r.t. W_z only) ----
    def bptt_loss_fn(W_z_inner: jnp.ndarray) -> jnp.ndarray:
        """Mean MSE over all timesteps, differentiable w.r.t. W_z."""
        total_loss = 0.0
        c_prev = init_rcd()
        for t in range(T_encoder):
            h_t = h_traj[t]
            tick = ticks[t]
            c_k, _ = rcd_step(rcd_bound, c_prev, h_t, tick)
            u_t = pack_u(h_t, c_k)
            z_t = readout_forward(W_z_inner, u_t)
            loss = loss_mse(z_t, u_target[t])
            total_loss = total_loss + loss
            c_prev = c_k
        return total_loss / T_encoder

    # ---- 8. Adam optimiser (no optax dependency) ----
    m = jnp.zeros_like(W_z)
    v_arr = jnp.zeros_like(W_z)
    beta1, beta2, eps = 0.9, 0.999, 1e-8

    # Attempt JIT-compiled grad; fall back to non-jitted on tracer issues
    raw_grad_fn = jax.grad(bptt_loss_fn, argnums=0)
    use_jit = True

    loss_history = []
    for epoch in range(n_epochs):
        if use_jit:
            try:
                g = jax.jit(raw_grad_fn)(W_z)
            except Exception:
                # Fall back to non-jitted grad
                use_jit = False
                g = raw_grad_fn(W_z)
        else:
            g = raw_grad_fn(W_z)

        # Adam update
        m = beta1 * m + (1 - beta1) * g
        v_arr = beta2 * v_arr + (1 - beta2) * g**2
        m_hat = m / (1 - beta1 ** (epoch + 1))
        v_hat = v_arr / (1 - beta2 ** (epoch + 1))
        W_z = W_z - lr * m_hat / (jnp.sqrt(v_hat) + eps)

        # Record loss after this epoch
        current_loss = float(bptt_loss_fn(W_z))
        loss_history.append(current_loss)

    # ---- 9. Tick count (for cross-arm comparability) ----
    tick_count = int(jnp.sum(ticks))

    return {
        "arm_name": "BPTT_surrogate",
        "loss_history": loss_history,
        "tick_count": tick_count,
        "u_final": u_final,
        "u_traj": u_traj,
        "W_z_final": W_z,
    }
