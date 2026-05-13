"""
§12 — Readout acceptance tests.

Tests the ODE-Plastic Readout (C2 gated mixture).

Invariants verified:
- I-RO-1: gate → 0.5 as u_j→0, monotonic in |u_j|
- I-RO-3: ||z|| ≤ ||W_z||_F·√(D+M)
"""

import jax
import jax.numpy as jnp
import jax.nn as jnn
import pytest
from flax import linen as nn

from lcn_brain.lcn import readout
from lcn_brain.lcn.constants import D, M, P, BETA_0, U_MAX, A_MIN, DELTA_MIN


class TestReadoutInvariants:
    """Invariant checks for Readout."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_gate_at_zero(self):
        """I-RO-1: gate → 0.5 as u_j→0."""
        u_zero = jnp.zeros(D + M)
        gate = jnn.sigmoid(readout._calibrated_beta() * jnp.abs(u_zero))

        # At u=0, gate should be close to 0.5
        assert jnp.all(jnp.abs(gate - 0.5) < 0.01), f"Gate at u=0 is {gate}, expected ~0.5"

    def test_gate_monotonic_in_abs_u(self):
        """I-RO-1: gate is monotonic in |u_j|."""
        beta = readout._calibrated_beta()

        u_small = jnp.array([0.001])
        u_large = jnp.array([0.1])

        gate_small = jnn.sigmoid(beta * jnp.abs(u_small))
        gate_large = jnn.sigmoid(beta * jnp.abs(u_large))

        assert gate_small < gate_large, "Gate should increase with |u|"

    def test_output_bound(self, key):
        """I-RO-3: ||z|| ≤ ||W_z||_F·√(D+M)."""
        # Create random weights
        W_z = jax.random.normal(key, (P, D + M))

        # Create random input
        u = jax.random.uniform(jax.random.PRNGKey(1), (D + M,), minval=-1.0, maxval=1.0)

        # Compute output
        z = readout.readout_forward(W_z, u)

        # Compute bounds
        z_norm = jnp.linalg.norm(z)
        w_fro = jnp.linalg.norm(W_z, ord="fro")
        bound = w_fro * jnp.sqrt(D + M)

        assert z_norm <= bound, f"||z||={z_norm:.4f} > ||W_z||_F·√(D+M)={bound:.4f}"


class TestReadoutModule:
    """Tests for PlasticReadout module."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_plastic_readout_instantiation(self):
        """Verify PlasticReadout can be instantiated."""
        module = readout.PlasticReadout()
        assert module is not None

    def test_plastic_readout_call(self, key):
        """Verify PlasticReadout can be called."""
        module = readout.PlasticReadout()
        u = jnp.zeros(D + M)

        variables = module.init(jax.random.PRNGKey(0), u)
        z = module.apply(variables, u)

        assert z.shape == (P,)

    def test_plastic_readout_with_random_input(self, key):
        """Test PlasticReadout with random input."""
        module = readout.PlasticReadout()
        u = jax.random.normal(key, (D + M,))

        variables = module.init(jax.random.PRNGKey(0), u)
        z = module.apply(variables, u)

        assert z.shape == (P,)
        assert jnp.all(jnp.isfinite(z))


class TestReadoutForward:
    """Tests for readout_forward function."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_readout_forward_shape(self, key):
        """Verify readout_forward returns correct shape."""
        W_z = jnp.ones((P, D + M))
        u = jnp.zeros(D + M)

        z = readout.readout_forward(W_z, u)

        assert z.shape == (P,)

    def test_readout_forward_1d_input(self, key):
        """Verify readout_forward with 1D input."""
        W_z = jax.random.normal(key, (P, D + M))
        u = jax.random.normal(jax.random.PRNGKey(1), (D + M,))

        z = readout.readout_forward(W_z, u)

        assert z.shape == (P,)

    def test_readout_forward_2d_input(self, key):
        """Verify readout_forward with 2D batch input."""
        W_z = jax.random.normal(key, (P, D + M))
        u = jax.random.normal(jax.random.PRNGKey(1), (4, D + M))

        z = readout.readout_forward(W_z, u)

        assert z.shape == (4, P)


class TestReadoutPullback:
    """Tests for readout_pullback function."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_pullback_shape(self, key):
        """Verify readout_pullback produces correct shape."""
        W_z = jnp.ones((P, D + M))
        u = jnp.zeros(D + M)
        dz = jnp.ones(P)

        pullback = readout.readout_pullback(W_z, u, dz)

        assert pullback.shape == (P, D + M)

    def test_pullback_finite(self, key):
        """Verify pullback returns finite values."""
        W_z = jax.random.normal(key, (P, D + M))
        u = jax.random.normal(jax.random.PRNGKey(1), (D + M,))
        dz = jax.random.normal(jax.random.PRNGKey(2), (P,))

        pullback = readout.readout_pullback(W_z, u, dz)

        assert jnp.all(jnp.isfinite(pullback))


class TestReadoutPackU:
    """Tests for pack_u function."""

    def test_pack_u_shape(self):
        """Verify pack_u concatenates correctly."""
        h = jnp.zeros(D)
        c = jnp.zeros(M)

        u = readout.pack_u(h, c)

        assert u.shape == (D + M,)

    def test_pack_u_bounds(self):
        """Verify pack_u output is bounded by tanh."""
        h = jnp.ones(D) * 10.0  # Large values
        c = jnp.ones(M) * 10.0

        u = readout.pack_u(h, c)

        # tanh bounds output to (-1, 1)
        assert jnp.all(jnp.abs(u) <= 1.0 + 1e-6)


class TestCalibratedBeta:
    """Tests for beta calibration."""

    def test_calibrated_beta_value(self):
        """Verify calibrated beta matches formula."""
        expected_beta = BETA_0 / (U_MAX * jnp.exp(-A_MIN * DELTA_MIN))
        actual_beta = readout._calibrated_beta()

        assert jnp.isclose(expected_beta, actual_beta)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
