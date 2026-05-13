"""
§14 — Phase 7: A+C Training Loop.

Algorithm A+C (Spec §4.4) per tick:
  1. Sample v
  2. Form antithetic pair
  3. Two forwards → central-difference tangent
  4. Probe κ̂
  5. Compute active set d_k (measurement-only)
  6. Combine via jvp_activity
  7. plastic_euler_step with gate(rho_ema)

Invariants (carried from lcn_jvp):
  I1 advisory: no jax.grad/jax.vjp/jacrev reachable from lcn/ (CI grep).
  I2 load-bearing: jvp_activity is unbiased estimator of ∇_θ L_σ.
  I3 empirical variance ≤ Theorem 1* bound.
  I5 determinism under fixed RNG.
  I6 bit-identical with vs without active_proj (measurement-only invariant).

Depends on the external lcn_jvp package (Spec §4.10 reference implementation).
"""

# Ensure Brain/ is on sys.path so lcn_jvp can be found
import sys
from dataclasses import dataclass
from dataclasses import replace as dc_replace
from pathlib import Path

import jax
import jax.numpy as jnp

_BRAIN_ROOT = Path(__file__).resolve().parent.parent.parent  # Brain/
_brains = str(_BRAIN_ROOT)
if _brains not in sys.path:
    sys.path.insert(0, _brains)

# lcn_jvp imports — external package, installed alongside lcn_brain
try:
    from lcn_jvp.dual import antithetic, sample_direction
    from lcn_jvp.estimators import jvp_activity
    from lcn_jvp.probes import column_norm_probe
    from lcn_jvp.projection import active_set

    _LCN_JVP_AVAILABLE = True
except ImportError:
    _LCN_JVP_AVAILABLE = False
    # Stubs for type-checking; will raise at runtime if used
    sample_direction = None  # type: ignore
    antithetic = None  # type: ignore
    jvp_activity = None  # type: ignore
    column_norm_probe = None  # type: ignore
    active_set = None  # type: ignore

from .clock import gate_value as clock_gate_value
from .constants import N_JVP_DIRECTIONS, SIGMA_THRESHOLD
from .plastic import plastic_euler_step, plastic_heun_step


@dataclass
class TrainState:
    """Training state carried through the A+C loop."""

    W_z: jnp.ndarray  # plastic readout weights  (P, D+M)
    u_at_tick_prev: jnp.ndarray  # u at last tick         (D+M,)
    rho_ema: jnp.ndarray  # clock EMA (scalar)
    dh_trace: jnp.ndarray  # trace of past h for active set
    step: int

    def replace(self, **kw):
        return dc_replace(self, **kw)


def init_train_state(W_z0: jnp.ndarray, u0: jnp.ndarray) -> TrainState:
    """Initialise training state.

    Args:
        W_z0: Initial plastic weights, shape (P, D+M).
        u0:   Initial readout input, shape (D+M,).

    Returns:
        Fresh TrainState.
    """
    return TrainState(
        W_z=W_z0,
        u_at_tick_prev=u0,
        rho_ema=jnp.array(0.05),  # RHO_THRESHOLD0
        dh_trace=jnp.zeros_like(u0),
        step=0,
    )


def _check_lcn_jvp():
    """Raise if lcn_jvp is not installed."""
    if not _LCN_JVP_AVAILABLE:
        raise ImportError(
            "lcn_jvp package is required for training. "
            "Install from the JVP reference implementation: "
            "pip install lcn_jvp  (or add to your Python path)"
        )


def _one_dir(
    state: TrainState,
    key: jnp.ndarray,
    *,
    forward_fn,
    forward_primal_fn,
    pullback_fn,
):
    """Compute one JVP direction estimate (A+C step internal).

    Args:
        state: Current training state.
        key:   JAX PRNG key.
        forward_fn:        Function f(W_z, u) → z.
        forward_primal_fn: Function f_primal(u) for κ probe.
        pullback_fn:       Pullback ∂z/∂W_z.

    Returns:
        (result, kappa_hat, d_k) — JVP result, condition estimate, active dim.
    """
    _check_lcn_jvp()

    k_dir, k_jvp, _ = jax.random.split(key, 3)
    u_prev = state.u_at_tick_prev

    v = sample_direction(key=k_dir, shape=u_prev.shape, distribution="gaussian")
    pair = antithetic(u=u_prev, v=v)

    kappa_hat = column_norm_probe(
        forward_primal_fn=forward_primal_fn,
        u_tau_prev=u_prev,
        basis_idx=int(state.step % u_prev.shape[-1]),
    )

    # MEASUREMENT-ONLY — proj used only for d_k, never on tangents
    proj, d_k = active_set(dh_trace=state.dh_trace, epsilon=1e-4)

    gate_val = float(clock_gate_value(state.rho_ema))

    res = jvp_activity(
        forward_fn=forward_fn,
        u_tau_prev=u_prev,
        pair=pair,
        rng_key=k_jvp,
        smoothing_sigma=SIGMA_THRESHOLD,
        active_proj=proj,
        pullback=pullback_fn,
        truncation_radius=None,
        kappa_hat=kappa_hat,
        gate_value=gate_val,
        mu_free=0.0,
        delta_k=1.0,
    )

    return res, kappa_hat, d_k


def train_one_tick(
    state: TrainState,
    key: jnp.ndarray,
    *,
    forward_fn,
    forward_primal_fn,
    pullback_fn,
) -> tuple[TrainState, dict]:
    """Execute one A+C training step at a distillation tick.

    1. Sample N_JVP_DIRECTIONS random directions.
    2. For each: form antithetic pair, run jvp_activity.
    3. Average g_hat estimates.
    4. Apply plastic Euler step.
    5. Return updated state and diagnostics.

    Args:
        state:              Current training state.
        key:                JAX PRNG key.
        forward_fn:         f(W_z, u) → z for JVP.
        forward_primal_fn:  f_primal(u) for κ probe.
        pullback_fn:        ∂z/∂W_z pullback.

    Returns:
        (new_state, diagnostics) — updated TrainState and diag dict.
    """
    _check_lcn_jvp()

    print(f"  Training tick {state.step}: sample v, antithetic pair...", flush=True)

    keys = jax.random.split(key, N_JVP_DIRECTIONS)
    results = []
    for m, k in enumerate(keys):
        res = _one_dir(state, k, forward_fn=forward_fn, forward_primal_fn=forward_primal_fn, pullback_fn=pullback_fn)
        results.append(res)
        kappa_val = float(res[1])
        d_val = int(res[2])
        g_dir_norm = float(jnp.linalg.norm(res[0].g_theta_hat))
        print(
            f"    Direction {m + 1}/{N_JVP_DIRECTIONS}: "
            f"g_norm={g_dir_norm:.6f}, kappa={kappa_val:.6f}, d_k={d_val}",
            flush=True,
        )

    # Negate: g_hat is ∇_W_z MSE but plastic step does gradient ASCENT
    g_hat = -sum(r[0].g_theta_hat for r in results) / N_JVP_DIRECTIONS
    k_mean = jnp.mean(jnp.stack([r[1] for r in results]))
    d_mean = jnp.mean(jnp.stack([r[2] for r in results]))

    # Accumulate EMA of gradient magnitudes for active set
    g_flat = jnp.abs(g_hat.ravel()[:state.dh_trace.shape[0]])  # (D+M,)
    dh_trace_new = 0.9 * state.dh_trace + 0.1 * g_flat

    W_prev = state.W_z
    W_new = plastic_euler_step(W_prev, g_hat, state.rho_ema)
    g_norm_val = float(jnp.linalg.norm(g_hat))
    W_change_val = float(jnp.linalg.norm(W_new - W_prev))
    print(f"    Plastic step: g_norm={g_norm_val:.6f}, W_norm_change={W_change_val:.6f}", flush=True)

    diag = {
        "kappa_hat": k_mean,
        "d_k": d_mean,
        "g_norm": jnp.linalg.norm(g_hat),
        "W_norm": jnp.linalg.norm(W_new),
    }

    return state.replace(W_z=W_new, dh_trace=dh_trace_new, step=state.step + 1), diag


def train_one_tick_heun(
    state: TrainState,
    key: jnp.ndarray,
    *,
    forward_fn,
    forward_primal_fn,
    pullback_fn,
) -> tuple[TrainState, dict]:
    """Same as train_one_tick but using Heun (2nd order) integrator.

    Args:
        state:              Current training state.
        key:                JAX PRNG key.
        forward_fn:         f(W_z, u) → z for JVP.
        forward_primal_fn:  f_primal(u) for κ probe.
        pullback_fn:        ∂z/∂W_z pullback.

    Returns:
        (new_state, diagnostics).
    """
    _check_lcn_jvp()

    print(f"  Training tick {state.step} (Heun): sample v, antithetic pair...", flush=True)

    keys = jax.random.split(key, N_JVP_DIRECTIONS)
    results = []
    for m, k in enumerate(keys):
        res = _one_dir(state, k, forward_fn=forward_fn, forward_primal_fn=forward_primal_fn, pullback_fn=pullback_fn)
        results.append(res)
        kappa_val = float(res[1])
        d_val = int(res[2])
        g_dir_norm = float(jnp.linalg.norm(res[0].g_theta_hat))
        print(
            f"    Direction {m + 1}/{N_JVP_DIRECTIONS}: "
            f"g_norm={g_dir_norm:.6f}, kappa={kappa_val:.6f}, d_k={d_val}",
            flush=True,
        )

    # Negate: g_hat is ∇_W_z MSE but plastic step does gradient ASCENT
    g_hat = -sum(r[0].g_theta_hat for r in results) / N_JVP_DIRECTIONS
    k_mean = jnp.mean(jnp.stack([r[1] for r in results]))
    d_mean = jnp.mean(jnp.stack([r[2] for r in results]))

    # Accumulate EMA of gradient magnitudes for active set
    g_flat = jnp.abs(g_hat.ravel()[:state.dh_trace.shape[0]])  # (D+M,)
    dh_trace_new = 0.9 * state.dh_trace + 0.1 * g_flat

    W_prev = state.W_z
    W_new = plastic_heun_step(W_prev, g_hat, state.rho_ema)
    g_norm_val = float(jnp.linalg.norm(g_hat))
    W_change_val = float(jnp.linalg.norm(W_new - W_prev))
    print(f"    Plastic step: g_norm={g_norm_val:.6f}, W_norm_change={W_change_val:.6f}", flush=True)

    diag = {
        "kappa_hat": k_mean,
        "d_k": d_mean,
        "g_norm": jnp.linalg.norm(g_hat),
        "W_norm": jnp.linalg.norm(W_new),
    }

    return state.replace(W_z=W_new, dh_trace=dh_trace_new, step=state.step + 1), diag


def train_one_tick_analytic(
    state: TrainState,
    key: jnp.ndarray,  # unused — no random directions needed
    *,
    forward_fn,
    forward_primal_fn,
    pullback_fn,
) -> tuple[TrainState, dict]:
    """Analytic training step — single-call gradient via pullback.

    Skips the 8-direction JVP loop entirely. Calls the pullback closure
    directly to obtain ∂L/∂W_z in a single forward-through-pullback pass.

    Args:
        state:              Current training state.
        key:                JAX PRNG key (unused — no random sampling).
        forward_fn:         f(W_z, u) → z (unused in this variant).
        forward_primal_fn:  f_primal(u) for κ probe.
        pullback_fn:        ∂L/∂W_z pullback (returns gradient directly).

    Returns:
        (new_state, diagnostics) — updated TrainState and diag dict.
    """
    _check_lcn_jvp()

    u_prev = state.u_at_tick_prev

    # 1. Analytic gradient — pullback closure already bakes in dL/dz
    g_theta_hat = pullback_fn(u_prev, jnp.zeros(1))  # (P, D+M)

    # 2. Negate: plastic step does gradient ascent (ĝ = +∇L for ASCENT,
    #    but g_theta_hat is ∇L so we negate)
    g_hat = -g_theta_hat

    # 3. Probe kappa for diagnostics
    kappa_hat = column_norm_probe(
        forward_primal_fn=forward_primal_fn,
        u_tau_prev=u_prev,
        basis_idx=int(state.step % u_prev.shape[-1]),
    )

    # 4. Update dh_trace (EMA of gradient magnitudes)
    g_flat = jnp.abs(g_hat.ravel()[:state.dh_trace.shape[0]])  # (D+M,)
    dh_trace_new = 0.9 * state.dh_trace + 0.1 * g_flat

    # 5. Active set (measurement-only — result used for d_k diagnostic)
    _, d_k = active_set(dh_trace=dh_trace_new, epsilon=1e-4)

    # 6. Plastic Euler step
    W_prev = state.W_z
    W_new = plastic_euler_step(W_prev, g_hat, state.rho_ema)

    # 7. Print diagnostic
    g_norm_val = float(jnp.linalg.norm(g_hat))
    kappa_val = float(kappa_hat)
    d_val = int(d_k)
    print(
        f"    Analytic (Euler): g_norm={g_norm_val:.6f}, kappa={kappa_val:.6f}, d_k={d_val}",
        flush=True,
    )

    diag = {
        "kappa_hat": kappa_hat,
        "d_k": d_k,
        "g_norm": jnp.linalg.norm(g_hat),
        "W_norm": jnp.linalg.norm(W_new),
    }

    return state.replace(W_z=W_new, dh_trace=dh_trace_new, step=state.step + 1), diag


def train_one_tick_heun_analytic(
    state: TrainState,
    key: jnp.ndarray,  # unused — no random directions needed
    *,
    forward_fn,
    forward_primal_fn,
    pullback_fn,
) -> tuple[TrainState, dict]:
    """Analytic training step with Heun (2nd order) integrator.

    Same as train_one_tick_analytic but uses plastic_heun_step instead
    of plastic_euler_step.

    Args:
        state:              Current training state.
        key:                JAX PRNG key (unused — no random sampling).
        forward_fn:         f(W_z, u) → z (unused in this variant).
        forward_primal_fn:  f_primal(u) for κ probe.
        pullback_fn:        ∂L/∂W_z pullback (returns gradient directly).

    Returns:
        (new_state, diagnostics).
    """
    _check_lcn_jvp()

    u_prev = state.u_at_tick_prev

    # 1. Analytic gradient — pullback closure already bakes in dL/dz
    g_theta_hat = pullback_fn(u_prev, jnp.zeros(1))  # (P, D+M)

    # 2. Negate: plastic step does gradient ascent
    g_hat = -g_theta_hat

    # 3. Probe kappa for diagnostics
    kappa_hat = column_norm_probe(
        forward_primal_fn=forward_primal_fn,
        u_tau_prev=u_prev,
        basis_idx=int(state.step % u_prev.shape[-1]),
    )

    # 4. Update dh_trace (EMA of gradient magnitudes)
    g_flat = jnp.abs(g_hat.ravel()[:state.dh_trace.shape[0]])  # (D+M,)
    dh_trace_new = 0.9 * state.dh_trace + 0.1 * g_flat

    # 5. Active set (measurement-only — result used for d_k diagnostic)
    _, d_k = active_set(dh_trace=dh_trace_new, epsilon=1e-4)

    # 6. Plastic Heun step (2nd order)
    W_prev = state.W_z
    W_new = plastic_heun_step(W_prev, g_hat, state.rho_ema)

    # 7. Print diagnostic
    g_norm_val = float(jnp.linalg.norm(g_hat))
    kappa_val = float(kappa_hat)
    d_val = int(d_k)
    print(
        f"    Analytic (Heun): g_norm={g_norm_val:.6f}, kappa={kappa_val:.6f}, d_k={d_val}",
        flush=True,
    )

    diag = {
        "kappa_hat": kappa_hat,
        "d_k": d_k,
        "g_norm": jnp.linalg.norm(g_hat),
        "W_norm": jnp.linalg.norm(W_new),
    }

    return state.replace(W_z=W_new, dh_trace=dh_trace_new, step=state.step + 1), diag
