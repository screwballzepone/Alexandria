"""
Forward-modulated probe for the LCN training loop.

``column_norm_probe`` estimates the L2 norm of a single column of the
Jacobian :math:`J_f = \\partial z / \\partial u` by perturbing the
readout input along one basis direction.
"""

import jax.numpy as jnp


def column_norm_probe(
    forward_primal_fn,
    u_tau_prev: jnp.ndarray,
    basis_idx: int,
    delta: float = 1e-3,
) -> jnp.ndarray:
    """Estimate the L2 norm of one column of the Jacobian.

    Perturbs the readout input :math:`u` along the basis vector
    :math:`e_\\text{basis\\_idx}` with step :math:`\\delta` and computes:

    .. math::
        \\hat{\\kappa} \\approx
        \\frac{\\| f(u + \\delta \\cdot e_i) - f(u) \\|}{\\delta}
        \\;\\;\\xrightarrow{\\delta \\to 0}\\;\\; \\| J_f \\cdot e_i \\|_2

    This is the norm of the **i-th column** of the Jacobian, NOT a
    condition number (which requires the ratio of extremal singular
    values).

    Args:
        forward_primal_fn: Callable ``f(u) → z`` (the primal forward pass).
        u_tau_prev:        Readout input at previous tick, shape (D+M,).
        basis_idx:         Index of the basis direction to perturb.
        delta:             Finite-difference step size (default 1e-3).

    Returns:
        Scalar estimate of :math:`\\| J_f \\cdot e_i \\|_2`, the column norm.
    """
    e_i = jnp.zeros_like(u_tau_prev)
    e_i = e_i.at[basis_idx].set(delta)

    f_u = forward_primal_fn(u_tau_prev)
    f_u_perturbed = forward_primal_fn(u_tau_prev + e_i)

    return jnp.linalg.norm(f_u_perturbed - f_u) / delta
