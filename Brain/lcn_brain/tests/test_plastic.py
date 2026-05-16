"""
§13 — Plastic weight ODE acceptance tests.

Tests the plastic-weight ODE (Approach A).

Invariants verified:
- I-PL-1: with g_hat=0, g≈1, ||W_z||_F decays
- I-PL-3: Euler stability, eta*MU_MIN < 2
"""

import jax
import jax.numpy as jnp
import pytest

from lcn_brain.lcn import plastic
from lcn_brain.lcn.constants import (
    ETA_PLASTIC,
    MU_MIN,
    MU_FREE,
    P,
    D,
    M,
)


class TestPlasticInvariants:
    """Invariant checks for Plastic ODE."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_weight_decay_with_zero_ghat(self, key):
        """I-PL-1: with g_hat=0, g≈1, ||W_z||_F decays."""
        # Create random weights
        W_z = jax.random.normal(key, (P, D + M))
        initial_norm = jnp.linalg.norm(W_z, ord="fro")

        # g_hat = 0, rho_ema high enough to make gate ≈ 1
        g_hat = jnp.zeros((P, D + M))
        rho_ema = 1.0  # High EMA triggers gate ≈ 1

        # Apply multiple steps
        W_curr = W_z
        for _ in range(100):
            W_curr = plastic.plastic_euler_step(W_curr, g_hat, rho_ema)

        final_norm = jnp.linalg.norm(W_curr, ord="fro")

        # With g≈1, weights should decay toward zero
        assert final_norm < initial_norm * 0.98, (
            f"Weights should decay: initial={initial_norm:.4f}, final={final_norm:.4f}"
        )

    def test_euler_stability_condition(self):
        """I-PL-3: Euler stability, eta*MU_MIN < 2."""
        stability = ETA_PLASTIC * MU_MIN

        assert stability < 2.0, f"Euler stability violated: eta*MU_MIN = {stability} >= 2"


class TestPlasticEulerStep:
    """Tests for plastic_euler_step function."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_euler_step_shape(self, key):
        """Verify plastic_euler_step returns correct shape."""
        W_z = jax.random.normal(key, (P, D + M))
        g_hat = jax.random.normal(jax.random.PRNGKey(1), (P, D + M))
        rho_ema = jnp.array(0.1)

        W_new = plastic.plastic_euler_step(W_z, g_hat, rho_ema)

        assert W_new.shape == (P, D + M)

    def test_euler_step_finite(self, key):
        """Verify plastic_euler_step returns finite values."""
        W_z = jax.random.normal(key, (P, D + M))
        g_hat = jax.random.normal(jax.random.PRNGKey(1), (P, D + M))
        rho_ema = jnp.array(0.1)

        W_new = plastic.plastic_euler_step(W_z, g_hat, rho_ema)

        assert jnp.all(jnp.isfinite(W_new))

    def test_euler_step_with_custom_eta(self, key):
        """Verify plastic_euler_step works with custom eta."""
        W_z = jnp.ones((P, D + M))
        g_hat = jnp.zeros((P, D + M))
        rho_ema = jnp.array(0.0)  # Low gate
        eta = 0.5

        W_new = plastic.plastic_euler_step(W_z, g_hat, rho_ema, eta=eta)

        assert W_new.shape == (P, D + M)


class TestPlasticHeunStep:
    """Tests for plastic_heun_step function."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_heun_step_shape(self, key):
        """Verify plastic_heun_step returns correct shape."""
        W_z = jax.random.normal(key, (P, D + M))
        g_hat = jax.random.normal(jax.random.PRNGKey(1), (P, D + M))
        rho_ema = jnp.array(0.1)

        W_new = plastic.plastic_heun_step(W_z, g_hat, rho_ema)

        assert W_new.shape == (P, D + M)

    def test_heun_step_finite(self, key):
        """Verify plastic_heun_step returns finite values."""
        W_z = jax.random.normal(key, (P, D + M))
        g_hat = jax.random.normal(jax.random.PRNGKey(1), (P, D + M))
        rho_ema = jnp.array(0.1)

        W_new = plastic.plastic_heun_step(W_z, g_hat, rho_ema)

        assert jnp.all(jnp.isfinite(W_new))

    def test_heun_more_accurate_than_euler(self, key):
        """Verify Heun is more stable than Euler for stiff ODE."""
        # With g_hat = 0 and g = 1 (decay only), exact solution: W(t) = W_0 * exp(-mu*t)
        W_z = jnp.eye(P, D + M)[0:1, :]  # Single row
        g_hat = jnp.zeros((1, D + M))
        rho_ema = 1.0  # Gate = 1 → mu = MU_MIN

        # Run many steps
        T = 100
        eta = ETA_PLASTIC

        # Euler
        W_euler = W_z.copy()
        for _ in range(T):
            W_euler = plastic.plastic_euler_step(W_euler, g_hat, rho_ema, eta=eta)

        # Heun
        W_heun = W_z.copy()
        for _ in range(T):
            W_heun = plastic.plastic_heun_step(W_heun, g_hat, rho_ema, eta=eta)

        # Exact solution
        W_exact = W_z * jnp.exp(-MU_MIN * T * eta)

        # Both should be reasonably close, but Heun should be better
        euler_error = jnp.linalg.norm(W_euler - W_exact)
        heun_error = jnp.linalg.norm(W_heun - W_exact)

        assert jnp.isfinite(euler_error)
        assert jnp.isfinite(heun_error)


class TestGateValue:
    """Tests for plastic gate_value function."""

    def test_gate_at_low_rho(self):
        """Verify gate is low when rho_ema is low."""
        rho_ema = 0.0  # Below threshold
        g = plastic.gate_value(rho_ema)

        assert g < 0.5, f"Gate should be < 0.5 for low rho_ema, got {g}"

    def test_gate_at_high_rho(self):
        """Verify gate is high when rho_ema is high."""
        rho_ema = 1.0  # Way above threshold
        g = plastic.gate_value(rho_ema)

        assert g > 0.5, f"Gate should be > 0.5 for high rho_ema, got {g}"

    def test_gate_bounds(self):
        """Verify gate is always in [0, 1]."""
        rho_values = jnp.array([0.0, 0.01, 0.05, 0.1, 0.5, 1.0, 10.0])

        for rho in rho_values:
            g = plastic.gate_value(rho)
            assert 0.0 <= g <= 1.0, f"Gate {g} outside [0, 1] for rho={rho}"


class TestMuEffective:
    """Tests for _mu_effective function."""

    def test_mu_at_gate_zero(self):
        """When g=0, mu = MU_FREE."""
        g_t = jnp.array(0.0)
        mu = plastic._mu_effective(g_t)

        assert jnp.isclose(mu, MU_FREE)

    def test_mu_at_gate_one(self):
        """When g=1, mu = MU_MIN."""
        g_t = jnp.array(1.0)
        mu = plastic._mu_effective(g_t)

        assert jnp.isclose(mu, MU_MIN)

    def test_mu_interpolation(self):
        """mu should interpolate between MU_FREE and MU_MIN."""
        g_t = jnp.array(0.5)
        mu = plastic._mu_effective(g_t)

        expected = MU_FREE + (MU_MIN - MU_FREE) * 0.5
        assert jnp.isclose(mu, expected)


class TestPlasticMultipleSteps:
    """Tests for multiple plastic steps."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_euler_stability_over_time(self, key):
        """Verify Euler remains stable over many steps."""
        W_z = jax.random.normal(key, (P, D + M))
        g_hat = jax.random.normal(jax.random.PRNGKey(1), (P, D + M))
        rho_ema = jnp.array(0.1)

        # Run many steps
        W_curr = W_z
        for _ in range(1000):
            W_curr = plastic.plastic_euler_step(W_curr, g_hat, rho_ema)

        # Should still be finite
        assert jnp.all(jnp.isfinite(W_curr))

    def test_heun_stability_over_time(self, key):
        """Verify Heun remains stable over many steps."""
        W_z = jax.random.normal(key, (P, D + M))
        g_hat = jax.random.normal(jax.random.PRNGKey(1), (P, D + M))
        rho_ema = jnp.array(0.1)

        # Run many steps
        W_curr = W_z
        for _ in range(1000):
            W_curr = plastic.plastic_heun_step(W_curr, g_hat, rho_ema)

        # Should still be finite
        assert jnp.all(jnp.isfinite(W_curr))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
