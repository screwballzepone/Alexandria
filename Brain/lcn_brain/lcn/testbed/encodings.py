"""
Encoding strategies for the Burgers' testbed.

Current: rate code (sign-separated).
Future: population code, temporal code, etc.
"""

import jax.numpy as jnp

from .burgers import rate_code as _rate_code, NX

__all__ = ["rate_code", "identity_code", "NX"]


def rate_code(u_field: jnp.ndarray) -> jnp.ndarray:
    """Sign-separated rate code: [u_+, u_-].

    Args:
        u_field: Velocity field, shape (NX,).

    Returns:
        Encoder input, shape (2*NX,).
    """
    return _rate_code(u_field)


def identity_code(u_field: jnp.ndarray) -> jnp.ndarray:
    """Pass-through encoding (requires N_ENC = NX).

    Args:
        u_field: Velocity field, shape (NX,).

    Returns:
        Same field, shape (NX,).
    """
    return u_field
