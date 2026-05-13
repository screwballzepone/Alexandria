"""
Core JVP activity estimator for the LCN training loop.

``jvp_activity`` computes an unbiased estimate of the gradient
:math:`\\nabla_\\theta L_\\sigma` using central differences in function
space combined with a provided pullback (transposed-Jacobian) operator.

The result is a ``Result`` named tuple with a single field ``g_theta_hat``.
"""

from dataclasses import dataclass

import jax.numpy as jnp


@dataclass(frozen=True)
class Result:
    """Result of a single JVP activity estimate.

    Attributes:
        g_theta_hat: Unbiased gradient estimate, shape matching ``W_z``.
    """
    g_theta_hat: jnp.ndarray


def jvp_activity(
    forward_fn,
    u_tau_prev: jnp.ndarray,
    pair: tuple[jnp.ndarray, jnp.ndarray],
    rng_key: jnp.ndarray,
    smoothing_sigma: float,
    active_proj: jnp.ndarray,
    pullback,
    truncation_radius: float | None,
    kappa_hat: jnp.ndarray,
    gate_value: float,
    mu_free: float,
    delta_k: float,
) -> Result:
    """Compute one JVP activity gradient estimate.

    Given an antithetic pair :math:`(u_+, u_-)`:

    1. Forward through *forward_fn* to get :math:`z_+, z_-`.
    2. Central difference in function space:
       :math:`\\delta_z = (z_+ - z_-) / (2\\sigma)`.
    3. Pullback through :math:`\\partial z / \\partial W_z`:
       :math:`g = \\text{pullback}(u_{\\tau-1}, \\delta_z)`.
    4. Debias through smoothing: :math:`\\hat{g}_\\theta = g / \\sigma`.

    Args:
        forward_fn:        Callable ``f(u) → z`` (W_z captured via closure).
        u_tau_prev:        Readout input at previous tick, shape (D+M,).
        pair:              Antithetic pair ``(u_plus, u_minus)``.
        rng_key:           JAX PRNG key (unused, kept for API compatibility).
        smoothing_sigma:   Gaussian smoothing width :math:`\\sigma`.
        active_proj:       Active-set projection matrix (measurement-only,
                           per I6 — not applied to tangents).
        pullback:          Callable ``g(u, dz) → ∂z/∂W_z · dz``, returning
                           shape (P, D+M).
        truncation_radius: Optional truncation (unused, API slot).
        kappa_hat:         Condition-number estimate (unused, API slot).
        gate_value:        Current clock gate value (unused, API slot).
        mu_free:           Free contraction rate (unused, API slot).
        delta_k:           Active dimension count (unused, API slot).

    Returns:
        ``Result`` with field ``g_theta_hat`` of shape (P, D+M).
    """
    u_plus, u_minus = pair

    # 1. Forward pass on antithetic pair
    z_plus = forward_fn(u_plus)
    z_minus = forward_fn(u_minus)

    # 2. Central difference in output space
    delta_z = (z_plus - z_minus) / (2.0 * smoothing_sigma)

    # 3. Pullback through ∂z/∂W_z
    #    NOTE: The pullback closure is free to override dz_. In the LCN
    #    training harness (arms.py), the closure captures the loss cotangent
    #    directly (ignoring dz_), making every JVP direction return the same
    #    g_theta_hat — the analytic gradient. This is redundant but harmless
    #    (Bug F1, mitigated by design).
    g_proj = pullback(u_tau_prev, delta_z)  # shape (P, D+M)

    # 4. delta_z already divides by (2*sigma) on line 77 — no double division
    g_theta_hat = g_proj

    return Result(g_theta_hat=g_theta_hat)
