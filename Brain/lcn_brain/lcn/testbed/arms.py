"""
4-arm harness wrappers for the Burgers' testbed.

Each arm runs the same forward pass but differs in how weights are updated:
  - BPTT_surrogate: adjoint + surrogate gradient (external baseline)
  - A_only:         switched contraction only, no JVP
  - C_only:         JVP only, no contraction (gate forced to 0)
  - A_plus_C:       full A+C — JVP estimator + switched contraction
"""

import sys
from pathlib import Path

import jax
import jax.numpy as jnp

# Ensure Brain/ is on sys.path so lcn_jvp can be found at runtime
_lcn_root = Path(__file__).resolve().parents[3]  # Brain/
if str(_lcn_root) not in sys.path:
    sys.path.insert(0, str(_lcn_root))

from ..clock import run_clock
from ..constants import N_ENC, D, M, P, RHO_EMA_BETA, RHO_THRESHOLD0
from ..diagnostics import DiagnosticsWriter, compute_diagnostics, print_tick_summary, sanity_check
from ..encoder import encode_window, init_encoder
from ..rcd import RCDCell, init_rcd, rcd_step
from ..readout import pack_u, readout_forward, readout_pullback
from ..ssf import SSFParams, run_ssf
from .burgers import (
    ARM_A_ONLY,
    ARM_A_PLUS_C,
    ARM_BPTT_SURROGATE,
    ARM_C_ONLY,
    ArmConfig,
    loss_mse,
    rate_code,
    sample_ic,
    simulate,
)


def run_arm(
    arm: ArmConfig,
    key: jnp.ndarray,
    u0: jnp.ndarray,
    nu: float,
    T_encoder: int,
    n_steps_per_enc: int,
    encoder_fn,
    ssf_fn,
    clock_fn,
    rcd_fn,
    readout_fn,
    train_fn=None,
) -> dict:
    """Run one arm of the Burgers' testbed.

    Args:
        arm:             ArmConfig specifying which approach.
        key:             JAX PRNG key.
        u0:              Initial condition, shape (NX,).
        nu:              Viscosity.
        T_encoder:       Number of encoder steps.
        n_steps_per_enc: RK4 steps per encoder step.
        encoder_fn:      Encode window function.
        ssf_fn:          SSF forward function.
        clock_fn:        Clock update function.
        rcd_fn:          RCD update function.
        readout_fn:      Readout forward function.
        train_fn:        Training step function (for arms with plastic update).

    Returns:
        Dict with 'loss_history', 'tick_count', 'arm_name', 'diagnostics'.
    """
    # ANSI colour helpers (Windows Terminal compatible)
    _CYAN = "\033[96m"
    _BLUE = "\033[94m"
    _YELLOW = "\033[93m"
    _GREEN = "\033[92m"
    _GREY = "\033[90m"
    _RESET = "\033[0m"

    # Diagnostics — per-tick logger
    writer = DiagnosticsWriter(output_dir="./logs")
    all_warnings: list[str] = []

    # Run PDE simulation
    n_pde_steps = T_encoder * n_steps_per_enc
    u_final, u_traj = simulate(u0, nu, n_pde_steps)

    # Subsample to encoder rate
    u_enc = u_traj[::n_steps_per_enc, :]  # (T_encoder, NX)
    if u_enc.shape[0] < T_encoder:
        # Pad if needed
        pad = T_encoder - u_enc.shape[0]
        u_enc = jnp.concatenate([u_enc, jnp.tile(u_enc[-1:], (pad, 1))], axis=0)

    # Rate code the velocity fields
    x_enc = jax.vmap(rate_code)(u_enc)  # (T_encoder, N_ENC)

    # Target: next-step velocity field (shifted by 1)
    u_target = jnp.roll(u_enc, -1, axis=0)  # (T_encoder, NX)

    # ------------------------------------------------------------------ #
    # Phase 1: Encoder — LIF + Gaussian-CDF surrogate firing             #
    # ------------------------------------------------------------------ #
    print(f"  {_BLUE}Phase 1: Encoder{_RESET}", flush=True)
    key, subkey = jax.random.split(key)
    v0, vtheta = init_encoder(subkey)
    _, S = encoder_fn(x_enc, v0, vtheta)  # (T_encoder, N_ENC)

    # ------------------------------------------------------------------ #
    # Phase 2: SSF — diagonal selective ODE over the full window         #
    # ------------------------------------------------------------------ #
    print(f"  {_BLUE}Phase 2: SSF{_RESET}", flush=True)
    key, subkey = jax.random.split(key)
    ssf_params = SSFParams()
    ssf_vars = ssf_params.init(subkey, jnp.zeros(N_ENC))
    ssf_bound = ssf_params.bind(ssf_vars)
    h0 = jnp.zeros(D)
    h_final, (h_traj, (a_traj, B_traj)) = ssf_fn(S, h0, ssf_bound)
    # h_traj: (T_encoder, D)

    # ------------------------------------------------------------------ #
    # Phase 3: Clock — EMA-triggered tick detection + gate               #
    # ------------------------------------------------------------------ #
    print(f"  {_BLUE}Phase 3: Clock{_RESET}", flush=True)
    clock_final, ticks, gates, rho_traj = clock_fn(S)
    # ticks:   (T_encoder,) bool
    # gates:   (T_encoder,) scalar
    # rho_traj: (T_encoder,) scalar

    # ------------------------------------------------------------------ #
    # Phase 4: RCD + Readout + Loss — per-timestep loop                 #
    # ------------------------------------------------------------------ #
    print(f"  {_BLUE}Phase 4: RCD + Readout + Loss ({T_encoder} steps){_RESET}", flush=True)
    key, subkey = jax.random.split(key)
    rcd_cell = RCDCell()
    rcd_vars = rcd_cell.init(subkey, jnp.zeros(D), jnp.zeros(M))
    rcd_bound = rcd_cell.bind(rcd_vars)

    c_prev = init_rcd()  # (M,)

    # Initialize plastic weights with small random values
    key, subkey = jax.random.split(key)
    W_z = jax.random.normal(subkey, (P, D + M)) * 0.01

    loss_history = []
    tick_count = 0
    train_state = None

    # Diagnostics tracking variables (updated on plastic ticks)
    last_training_kappa = 0.0
    last_training_d_k = 0
    last_training_g_norm = 0.0

    rho_ema_current = float(RHO_THRESHOLD0)  # EMA tracker, starts at gate offset

    for t in range(T_encoder):
        h_t = h_traj[t]  # (D,)
        tick = ticks[t]
        gate_t = gates[t]
        # Tick progress (print every step for real-time feedback)
        print(f"    Tick {t + 1}/{T_encoder}: gate={float(gate_t):.4f}, loss=", end="", flush=True)

        # Update clock EMA tracker from instantaneous activity
        rho_t_val = float(rho_traj[t])
        rho_ema_current = RHO_EMA_BETA * rho_ema_current + (1 - RHO_EMA_BETA) * rho_t_val

        # RCD — conditional update on tick (no-op if not tick)
        c_k, _ = rcd_fn(rcd_bound, c_prev, h_t, tick)

        if tick:
            tick_count += 1

        # Pack u = tanh([h; c]) — bounded in (-1, 1)
        u_t = pack_u(h_t, c_k)  # (D+M,)

        # Initialize TrainState on first tick (plastic arms only)
        if tick and train_state is None and arm.plastic_update and train_fn is not None:
            from ..train import init_train_state
            train_state = init_train_state(W_z, u_t)

        # Readout forward: z = f(W_z, u)
        z_t = readout_fn(W_z, u_t)  # (P,) = (1,)

        # MSE loss against target field
        loss = loss_mse(z_t, u_target[t])
        loss_val = float(loss)
        loss_history.append(loss_val)
        print(f"{loss_val:.6f}", flush=True)

        # DIAGNOSTICS — build tick record for this timestep
        record = compute_diagnostics(
            tick_idx=tick_count,
            rho_t=rho_traj[t],
            rho_ema=jnp.array(rho_ema_current),
            gate=gates[t],
            kappa_hat=last_training_kappa,
            d_k=last_training_d_k,
            r2_violation=False,
            truncated=False,
            loss_local=loss,
            W_norm=jnp.linalg.norm(W_z),
            g_norm=last_training_g_norm,
            u=u_t,
            beta_eff=16.31,
            arm=arm.name,
        )
        writer.log(record)
        print_tick_summary(record)
        warnings = sanity_check(record)
        if warnings:
            all_warnings.extend(warnings)

        # Plastic weight update (only on ticks for plastic arms)
        if tick and arm.plastic_update and train_fn is not None:
            key, tick_key = jax.random.split(key)

            # Update u_at_tick_prev to current u
            ts = train_state.replace(u_at_tick_prev=u_t)

            # Update rho_ema on train_state from instantaneous clock activity
            rho_t_current = float(rho_traj[t])
            rho_ema_updated = float(RHO_EMA_BETA * float(ts.rho_ema) + (1 - RHO_EMA_BETA) * rho_t_current)
            ts = ts.replace(rho_ema=jnp.array(rho_ema_updated))

            # Capture current W_z via closure for forward/primal/pullback
            _Wz = ts.W_z
            _target = u_target[t]  # capture for closure
            new_state, diag = train_fn(
                ts,
                tick_key,
                forward_fn=lambda u_: readout_fn(_Wz, u_),
                forward_primal_fn=lambda u_: readout_fn(_Wz, u_),
                pullback_fn=lambda u_, dz_: readout_pullback(
                    _Wz, u_, 2.0 * (readout_fn(_Wz, u_) - _target)
                ),
            )
            train_state = new_state
            W_z = new_state.W_z
            # Store training diagnostics from this tick
            last_training_kappa = float(diag.get('kappa_hat', 0.0))
            last_training_d_k = int(diag.get('d_k', 0))
            last_training_g_norm = float(diag.get('g_norm', 0.0))

        c_prev = c_k

    # Arm completion summary
    final_loss = loss_history[-1] if loss_history else float("nan")
    print(
        f"  {_GREEN}Arm {_CYAN}{arm.name}{_GREEN} completed: "
        f"{tick_count} ticks, final loss={final_loss:.6f}{_RESET}",
        flush=True,
    )

    # Flush accumulated diagnostics to Parquet
    parquet_path = writer.flush(f"{arm.name}_T={T_encoder}.parquet")
    parquet_path_str = str(parquet_path) if parquet_path else None

    return {
        "arm_name": arm.name,
        "loss_history": loss_history,
        "tick_count": tick_count,
        "u_final": u_final,
        "u_traj": u_traj,
        "W_z_final": W_z,
        "diagnostics_warnings": all_warnings,
        "parquet_path": parquet_path_str,
    }


def compare_arms(
    key: jnp.ndarray,
    nu: float = 1e-2,
    T_values: list[int] = None,
    n_steps_per_enc: int = 1,
) -> dict:
    """Run all 4 arms and compare results.

    Args:
        key:             JAX PRNG key.
        nu:              Viscosity.
        T_values:        List of T (encoder steps) to test.
        n_steps_per_enc: RK4 steps per encoder step.

    Returns:
        Dict mapping arm name → results dict per T.
    """
    if T_values is None:
        T_values = [10, 100, 1000]

    results = {}
    for T in T_values:
        key, ic_key = jax.random.split(key)
        u0 = sample_ic(ic_key)

        for arm in [ARM_BPTT_SURROGATE, ARM_A_ONLY, ARM_C_ONLY, ARM_A_PLUS_C]:
            key, run_key = jax.random.split(key)

            if arm == ARM_BPTT_SURROGATE:
                # BPTT surrogate uses external jax.grad baseline (testbed/baselines.py)
                from .baselines import run_bptt_arm

                result = run_bptt_arm(
                    key=run_key,
                    u0=u0,
                    nu=nu,
                    T_encoder=T,
                    n_steps_per_enc=n_steps_per_enc,
                    n_epochs=1,
                    lr=1e-3,
                )
            else:
                # Select training function based on arm type.
                # If lcn_jvp is not installed, train_fn stays None and plastic
                # arms run forward-pass only (skip weight updates).
                train_fn_to_pass = None
                if arm.plastic_update:
                    try:
                        from ..train import _LCN_JVP_AVAILABLE

                        if _LCN_JVP_AVAILABLE:
                            if arm.switched_contraction:
                                from ..train import train_one_tick_heun_analytic as train_variant
                            else:
                                from ..train import train_one_tick_analytic as train_variant
                            train_fn_to_pass = train_variant
                    except ImportError:
                        train_fn_to_pass = None

                result = run_arm(
                    arm=arm,
                    key=run_key,
                    u0=u0,
                    nu=nu,
                    T_encoder=T,
                    n_steps_per_enc=n_steps_per_enc,
                    encoder_fn=encode_window,
                    ssf_fn=run_ssf,
                    clock_fn=run_clock,
                    rcd_fn=rcd_step,
                    readout_fn=readout_forward,
                    train_fn=train_fn_to_pass,
                )
            results[f"{arm.name}_T={T}"] = result

    return results
