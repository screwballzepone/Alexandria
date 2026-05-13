"""
Dual number / antithetic sampling primitives for JVP estimation.

Provides two functions:
  - sample_direction: draw a random tangent direction v
  - antithetic:       form the antithetic pair (u + sigma*v, u - sigma*v)
"""

import jax
import jax.numpy as jnp


def sample_direction(
    key: jnp.ndarray,
    shape: tuple[int, ...],
    distribution: str = "gaussian",
) -> jnp.ndarray:
    """Sample a random direction vector for JVP perturbation.

    Args:
        key:          JAX PRNG key.
        shape:        Shape of the direction vector (typically (D+M,)).
        distribution: One of ``"gaussian"`` or ``"rademacher"``.

    Returns:
        Random direction vector of `shape` with expected norm ≈ 1.
    """
    if distribution == "gaussian":
        return jax.random.normal(key, shape)
    elif distribution == "rademacher":
        # {+1, -1} with equal probability
        return 2.0 * jax.random.bernoulli(key, shape=shape) - 1.0
    else:
        raise ValueError(
            f"Unknown distribution '{distribution}'. "
            f"Expected 'gaussian' or 'rademacher'."
        )


def antithetic(
    u: jnp.ndarray,
    v: jnp.ndarray,
    sigma: float = 1e-3,
) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Form an antithetic pair around *u* along direction *v*.

    .. math::
        u_\\pm = u \\pm \\sigma \\hat{v}

    Args:
        u:     Centre point, shape (..., D+M).
        v:     Direction vector, same shape as *u*.
        sigma: Perturbation scale (default 1e-3).

    Returns:
        ``(u_plus, u_minus)`` — the antithetic pair, each same shape as *u*.
    """
    return (u + sigma * v, u - sigma * v)
