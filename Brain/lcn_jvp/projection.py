"""
Active-set projection for the LCN training loop.

``active_set`` thresholds entries of a trace vector to identify which
dimensions are "active", returning a diagonal projection matrix and
the count of active dimensions.

Per invariant I6, the projection is **measurement-only** — it is *not*
applied to JVP tangents.
"""

import jax.numpy as jnp


def active_set(
    dh_trace: jnp.ndarray,
    epsilon: float = 1e-4,
) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Compute the active set from a trace vector.

    Entries of *dh_trace* with absolute value greater than *epsilon* are
    considered active.

    Args:
        dh_trace: 1-D trace array, shape (D+M,).
        epsilon:   Threshold for activation.

    Returns:
        ``(proj_matrix, d_k)`` where:

        - **proj_matrix** — diagonal 0/1 mask, shape ``(D+M, D+M)``.
        - **d_k** — number of active entries (scalar).
    """
    active_mask = jnp.abs(dh_trace) > epsilon
    d_k = jnp.sum(active_mask)
    proj_matrix = jnp.diag(active_mask.astype(jnp.float32))
    return proj_matrix, d_k
