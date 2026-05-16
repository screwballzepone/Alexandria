"""
§12 — Readout normalization acceptance tests.

Tests the normalize_readout function against its three invariants.
"""

import jax
import jax.numpy as jnp
import pytest

from lcn_brain.lcn.normalize import normalize_readout


class TestNormalizeReadout:
    """Tests for normalize_readout invariants."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_output_has_zero_mean(self, key):
        """I-NORM-1: output has zero mean."""
        z = jax.random.normal(key, (128,))
        z_norm = normalize_readout(z)

        mean_out = jnp.mean(z_norm)
        assert jnp.allclose(mean_out, 0.0, atol=1e-6), \
            f"Expected mean ≈ 0, got {mean_out}"

    def test_output_has_unit_variance(self, key):
        """I-NORM-2: output has unit variance."""
        z = jax.random.normal(key, (128,))
        z_norm = normalize_readout(z)

        var_out = jnp.var(z_norm)
        # Epsilon in denominator slightly reduces variance: var(z)/(var(z)+eps)
        assert jnp.allclose(var_out, 1.0, atol=1e-4), \
            f"Expected variance ≈ 1, got {var_out}"

    def test_epsilon_prevents_division_by_zero(self):
        """I-NORM-3: epsilon prevents NaN when all z values are equal."""
        z = jnp.full((128,), 7.0)  # All equal → variance = 0

        z_norm = normalize_readout(z)

        # Should be all finite, not NaN or inf
        assert jnp.all(jnp.isfinite(z_norm)), \
            "Expected all-finite output, got NaN/inf"
        # With zero variance, output should be exactly zero
        assert jnp.all(z_norm == 0.0), \
            f"Expected all zeros when var=0, got {z_norm}"


class TestNormalizeReadoutBatched:
    """Tests for normalize_readout with batched input."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_batched_output_zero_mean(self, key):
        """Batch: each row has zero mean."""
        z = jax.random.normal(key, (16, 128))
        z_norm = normalize_readout(z)

        row_means = jnp.mean(z_norm, axis=-1)
        assert jnp.allclose(row_means, 0.0, atol=1e-6), \
            f"Expected row means ≈ 0, got max |mean| = {jnp.max(jnp.abs(row_means))}"

    def test_batched_output_unit_variance(self, key):
        """Batch: each row has unit variance."""
        z = jax.random.normal(key, (16, 128))
        z_norm = normalize_readout(z)

        row_vars = jnp.var(z_norm, axis=-1)
        # Epsilon in denominator slightly reduces variance: var(z)/(var(z)+eps)
        assert jnp.allclose(row_vars, 1.0, atol=1e-4), \
            f"Expected row variances ≈ 1, got min var = {jnp.min(row_vars)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
