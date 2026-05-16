"""
§12 — Readout normalization: standardize z before Burgers' comparison.

Applies z_norm = (z - mean(z)) / sqrt(var(z) + epsilon) along the last axis.
No learnable parameters — this is a deterministic preprocessing step that
ensures the readout vector has zero mean and unit variance before it enters
the loss computation against the Burgers' target.

Invariants:
  I-NORM-1: zero-mean output — mean(z_norm) ≈ 0
  I-NORM-2: unit-variance output — var(z_norm) ≈ 1 (unless epsilon dominates)
  I-NORM-3: epsilon-stable — no division by zero when var(z) = 0
"""

import jax.numpy as jnp


def normalize_readout(z: jnp.ndarray, epsilon: float = 1e-5) -> jnp.ndarray:
    """Normalize the readout vector z to zero mean and unit variance.

    Computed as: z_norm = (z - mean(z)) / sqrt(var(z) + epsilon).

    Operates along the last axis of z, so it works for both 1-D vectors
    (shape (P,)) and batched inputs (shape (batch, P)).

    Args:
        z:       Readout vector, shape (..., P).
        epsilon: Small constant to prevent division by zero (default 1e-5).

    Returns:
        z_norm: Normalized readout, same shape as z.
    """
    mean_z = jnp.mean(z, axis=-1, keepdims=True)
    var_z = jnp.var(z, axis=-1, keepdims=True)
    return (z - mean_z) / jnp.sqrt(var_z + epsilon)
