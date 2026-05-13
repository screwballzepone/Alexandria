"""
Kuramoto-Sivashinsky equation testbed.

Periodic 1D Kuramoto-Sivashinsky equation:
    u_t + u u_x + u_xx + u_xxxx = 0
    x ∈ [0, L), L=64, N_x=64, dt_pde = 5e-4
    RK4 in time, central differences in space.

The 4th-order term u_xxxx produces spatiotemporal chaos.
IC: 4-mode random Fourier IC (same pattern as Burgers).

4 arms:
  - BPTT_surrogate:  adjoint + surrogate (baseline)
  - A_only:          adjoint + surrogate, yes contraction
  - C_only:          plastic.py with gate forced to 0, yes JVP, no contraction
  - A_plus_C:        plastic.py, yes JVP, yes contraction (default)
"""

import functools as ft
from dataclasses import dataclass

import jax
import jax.numpy as jnp

# --- PDE parameters ---
L = 64.0
NX = 64
DX = L / NX
DT = 5e-4


# ---------------------------------------------------------------------------
# PDE solver
# ---------------------------------------------------------------------------


def _rhs(u: jnp.ndarray, nu: float) -> jnp.ndarray:
    """Right-hand side of KS equation: -u*u_x - u_xx - u_xxxx.

    Central differences on periodic domain. ``nu`` is unused (included
    for API compatibility with burgers.py).

    Args:
        u:  Velocity field, shape (NX,).
        nu: Unused. Included for API compatibility.

    Returns:
        du/dt at each grid point, shape (NX,).
    """
    # First derivative: 2nd-order central
    ux = (jnp.roll(u, -1) - jnp.roll(u, 1)) / (2 * DX)
    # Second derivative: 3-point central
    uxx = (jnp.roll(u, -1) - 2 * u + jnp.roll(u, 1)) / DX ** 2
    # Fourth derivative: 5-point central stencil
    uxxxx = (
        jnp.roll(u, -2)
        - 4 * jnp.roll(u, -1)
        + 6 * u
        - 4 * jnp.roll(u, 1)
        + jnp.roll(u, 2)
    ) / DX ** 4
    return -u * ux - uxx - uxxxx


def _rk4(u: jnp.ndarray, nu: float, dt: float) -> jnp.ndarray:
    """Classical RK4 step.

    Args:
        u:  Velocity field, shape (NX,).
        nu: Unused, for API compatibility.
        dt: Time step.

    Returns:
        u at next timestep.
    """
    k1 = _rhs(u, nu)
    k2 = _rhs(u + 0.5 * dt * k1, nu)
    k3 = _rhs(u + 0.5 * dt * k2, nu)
    k4 = _rhs(u + dt * k3, nu)
    return u + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


@ft.partial(jax.jit, static_argnames=("n_steps",))
def simulate(
    u0: jnp.ndarray, nu: float, n_steps: int
) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Simulate KS equation for n_steps.

    Args:
        u0:      Initial condition, shape (NX,).
        nu:      Unused, for API compatibility.
        n_steps: Number of RK4 steps.

    Returns:
        (u_final, u_traj) — final field and trajectory (n_steps, NX).
    """

    def body(u, _):
        return _rk4(u, nu, DT), u

    return jax.lax.scan(body, u0, None, length=n_steps)


def sample_ic(key: jnp.ndarray, n_modes: int = 4) -> jnp.ndarray:
    """Sample a random 4-mode Fourier initial condition.

    u_0(x) = sum_{k=1}^{n_modes} a_k * sin(2*pi*k*x/L + phi_k)

    Args:
        key:     JAX PRNG key.
        n_modes: Number of Fourier modes.

    Returns:
        u0: Initial velocity field, shape (NX,).
    """
    k_a, k_p = jax.random.split(key)
    a = jax.random.uniform(k_a, (n_modes,), minval=-1.0, maxval=1.0)
    phi = jax.random.uniform(k_p, (n_modes,), minval=0.0, maxval=2 * jnp.pi)
    x = jnp.linspace(0.0, L, NX, endpoint=False)
    ks = jnp.arange(1, n_modes + 1)
    return jnp.sum(
        a[:, None]
        * jnp.sin(
            2 * jnp.pi * ks[:, None] * x[None, :] / L + phi[:, None]
        ),
        axis=0,
    )


# ---------------------------------------------------------------------------
# Rate coding: KS field → spike encoder input
# ---------------------------------------------------------------------------


def rate_code(u_field: jnp.ndarray) -> jnp.ndarray:
    """Convert KS velocity field to rate-coded encoder input.

    Sign-separated: positive and negative channels stacked.
    For NX=64, output is (128,) — matches N_ENC.

    Args:
        u_field: Velocity field, shape (NX,).

    Returns:
        x_enc: Encoder input, shape (2*NX,) = (N_ENC,).
    """
    up = jnp.maximum(u_field, 0.0)
    un = jnp.maximum(-u_field, 0.0)
    return jnp.concatenate([up, un])  # (N_ENC,) for N_x * 2 = 128


# ---------------------------------------------------------------------------
# 4-arm harness classes
# ---------------------------------------------------------------------------


@dataclass
class ArmConfig:
    """Configuration for one testbed arm."""

    name: str
    plastic_update: bool
    jvp_estimator: bool
    switched_contraction: bool


# Standard 4-arm configurations
ARM_BPTT_SURROGATE = ArmConfig(
    name="BPTT_surrogate",
    plastic_update=False,
    jvp_estimator=False,
    switched_contraction=False,
)

ARM_A_ONLY = ArmConfig(
    name="A_only",
    plastic_update=False,
    jvp_estimator=False,
    switched_contraction=True,
)

ARM_C_ONLY = ArmConfig(
    name="C_only",
    plastic_update=True,
    jvp_estimator=True,
    switched_contraction=False,
)

ARM_A_PLUS_C = ArmConfig(
    name="A_plus_C",
    plastic_update=True,
    jvp_estimator=True,
    switched_contraction=True,
)

ALL_ARMS = [ARM_BPTT_SURROGATE, ARM_A_ONLY, ARM_C_ONLY, ARM_A_PLUS_C]


# ---------------------------------------------------------------------------
# Loss function
# ---------------------------------------------------------------------------


def loss_mse(z_pred: jnp.ndarray, u_target: jnp.ndarray) -> jnp.ndarray:
    """Mean squared error between readout and target field.

    Args:
        z_pred:   Predicted field, shape (NX,).
        u_target: True field, shape (NX,).

    Returns:
        Scalar MSE loss.
    """
    return jnp.mean((z_pred - u_target) ** 2)


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    key = jax.random.PRNGKey(0)
    u0 = sample_ic(key)
    u_final, u_traj = simulate(u0, nu=0.0, n_steps=100)
    print(
        f"KS testbed | u_final: min={u_final.min():.4f}  "
        f"max={u_final.max():.4f}  "
        f"mean={u_final.mean():.4f}  "
        f"std={u_final.std():.4f}"
    )
    print(f"           | trajectory shape: {u_traj.shape}")
