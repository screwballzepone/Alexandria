"""
§10 — Phase 3: Distillation Clock.

Tick fires when rho(t) = ||S(t)||_1 exceeds an EMA-tracked threshold.
The clock also drives the soft gate g(t) = sigma(gamma * (rho_ema - rho_0))
used by the plastic ODE. Cooldown of DELTA_MIN steps after each tick
enforces mean inter-tick gap >= DELTA_MIN.

Invariants:
  I-CLK-1: mean inter-tick gap >= DELTA_MIN
  I-CLK-2: tick rate sublinear in T, <= 1/DELTA_MIN
  I-CLK-3: gate ∈ [0, 1]
"""

import jax
import jax.numpy as jnp
import jax.nn as jnn

from .constants import (
    RHO_EMA_BETA,
    RHO_THRESHOLD0,
    RHO_GATE_GAIN,
    DELTA_MIN,
)


def clock_init() -> dict:
    """Initialise clock state.

    Returns:
        Dict with 'rho_ema' (scalar) and 'cooldown' (scalar).
    """
    return {
        "rho_ema": jnp.array(RHO_THRESHOLD0),
        "cooldown": jnp.array(0.0),
    }


def clock_step(
    state: dict,
    s_t: jnp.ndarray,
    dt: float = 1.0,
) -> tuple[dict, jnp.ndarray, jnp.ndarray, jnp.ndarray]:
    """Single clock step: update EMA, check tick condition, compute gate.

    Args:
        state: Dict with 'rho_ema' and 'cooldown'.
        s_t:   Spike vector at time t, shape (N_ENC,).
        dt:    Time step.

    Returns:
        (new_state, tick, gate, rho_t) — new clock state, boolean tick flag,
        soft gate g(t) ∈ [0,1], and raw rho_t for logging.
    """
    rho_t = jnp.sum(s_t)
    rho_ema = RHO_EMA_BETA * state["rho_ema"] + (1.0 - RHO_EMA_BETA) * rho_t

    can_tick = state["cooldown"] <= 0.0
    tick = jnp.logical_and(rho_t > rho_ema, can_tick)

    cooldown_new = jnp.where(
        tick,
        jnp.array(DELTA_MIN),
        jnp.maximum(state["cooldown"] - dt, 0.0),
    )

    gate = jnn.sigmoid(RHO_GATE_GAIN * (rho_ema - RHO_THRESHOLD0))

    return (
        {
            "rho_ema": rho_ema,
            "cooldown": cooldown_new,
        },
        tick,
        gate,
        rho_t,
    )


def run_clock(s_window: jnp.ndarray) -> tuple[dict, jnp.ndarray, jnp.ndarray, jnp.ndarray]:
    """Run clock over a window of spikes, collecting ticks and gates.

    Args:
        s_window: Spike sequence, shape (T, N_ENC).

    Returns:
        (final_state, ticks, gates, rho_traj) — (T,) arrays of bools, floats, floats.
    """

    def step(state, s_t):
        new_state, tick, gate, rho_t = clock_step(state, s_t)
        return new_state, (tick, gate, rho_t)

    init = clock_init()
    final_state, (ticks, gates, rho_traj) = jax.lax.scan(step, init, s_window)
    return final_state, ticks, gates, rho_traj


def gate_value(rho_ema: jnp.ndarray) -> jnp.ndarray:
    """Compute gate from clock EMA (for external use by plastic ODE).

    Args:
        rho_ema: Clock EMA value (scalar).

    Returns:
        Gate value in [0, 1].
    """
    return jnn.sigmoid(RHO_GATE_GAIN * (rho_ema - RHO_THRESHOLD0))
