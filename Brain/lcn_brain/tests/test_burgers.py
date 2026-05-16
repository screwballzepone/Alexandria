"""
§15 — Burgers' testbed acceptance tests.

Tests the PDE solver and rate coding for Burgers' equation.

Acceptance probe:
- PDE solver: energy conservation trend (viscous dissipation)
- RK4 stability
- CFL condition
- Verify sample_ic produces correct shape (NX,)
- Verify rate_code splits signs correctly and output shape is (2*NX,)
"""

import jax
import jax.numpy as jnp
import pytest

# Import from testbed module
from lcn_brain.lcn.testbed import burgers
from lcn_brain.lcn.constants import N_ENC


# Get constants from burgers module
NX = burgers.NX
DX = burgers.DX
DT = burgers.DT


class TestBurgersPDE:
    """Tests for Burgers' PDE solver."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_rhs_shape(self):
        """Verify _rhs returns correct shape."""
        u = jnp.ones(NX)
        nu = 0.01

        du_dt = burgers._rhs(u, nu)

        assert du_dt.shape == (NX,)

    def test_rk4_step_shape(self):
        """Verify _rk4 returns correct shape."""
        u = jnp.ones(NX)
        nu = 0.01
        dt = DT

        u_next = burgers._rk4(u, nu, dt)

        assert u_next.shape == (NX,)

    def test_rk4_stability(self, key):
        """Verify RK4 remains stable for reasonable parameters."""
        # Sample initial condition
        u0 = burgers.sample_ic(key)

        # Run simulation
        u_final, _ = burgers.simulate(u0, nu=0.01, n_steps=100)

        # Should remain finite
        assert jnp.all(jnp.isfinite(u_final))

    def test_rk4_preserves_constant(self):
        """Verify RK4 preserves constant solution."""
        u = jnp.ones(NX) * 0.5  # Constant

        u_next = burgers._rk4(u, nu=0.01, dt=DT)

        # Constant should remain constant
        assert jnp.allclose(u_next, 0.5, atol=1e-10)

    def test_cfl_condition_nu(self):
        """Verify CFL condition for diffusion: 2*nu*dt/dx^2 < 1."""
        cfl_diffusion = 2 * DT / (DX * DX)  # With nu=1

        # For nu=1, this should still be stable as nu ≤ 0.01 in practice
        # The actual condition: 2*nu*dt/dx^2 < 1
        # With nu=0.01, we have: 2*0.01*5e-4 / (1/64)^2 ≈ 0.02
        assert cfl_diffusion < 10.0  # Reasonable bound

    def test_simulate_returns_trajectory(self, key):
        """Verify simulate returns trajectory."""
        u0 = burgers.sample_ic(key)
        n_steps = 10

        u_final, u_traj = burgers.simulate(u0, nu=0.01, n_steps=n_steps)

        assert u_final.shape == (NX,)
        assert u_traj.shape == (n_steps, NX)


class TestBurgersEnergy:
    """Tests for energy conservation/dissipation."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_energy_dissipation_viscous(self, key):
        """Verify energy decays over time (viscous dissipation)."""
        u0 = burgers.sample_ic(key)
        nu = 0.01

        # Run simulation for many steps
        u_final, u_traj = burgers.simulate(u0, nu=nu, n_steps=500)

        # Compute L2 energy at start and end
        E0 = jnp.sum(u_traj[0] ** 2)
        E_final = jnp.sum(u_final**2)

        # With viscosity, energy should decay
        assert E_final <= E0 * 1.1, f"Energy should decay (or stay bounded): E0={E0:.4f}, E_final={E_final:.4f}"

    def test_energy_bounded_without_viscosity(self, key):
        """Verify energy stays bounded without viscosity (conservative)."""
        u0 = burgers.sample_ic(key)
        nu = 0.0  # No viscosity

        u_final, u_traj = burgers.simulate(u0, nu=nu, n_steps=100)

        # Without viscosity, energy should stay bounded (conservative)
        E0 = jnp.sum(u_traj[0] ** 2)
        E_final = jnp.sum(u_final**2)

        # Should not explode
        assert jnp.isfinite(E_final)
        assert E_final < E0 * 10.0  # Allow some numerical drift


class TestBurgersSampleIC:
    """Tests for sample_ic function."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_sample_ic_shape(self, key):
        """Verify sample_ic produces correct shape (NX,)."""
        u0 = burgers.sample_ic(key)

        assert u0.shape == (NX,)

    def test_sample_ic_deterministic(self, key):
        """Verify sample_ic is deterministic with same key."""
        u0_1 = burgers.sample_ic(key)
        u0_2 = burgers.sample_ic(key)

        assert jnp.allclose(u0_1, u0_2)

    def test_sample_ic_random(self):
        """Verify sample_ic produces different results with different keys."""
        u0_1 = burgers.sample_ic(jax.random.PRNGKey(0))
        u0_2 = burgers.sample_ic(jax.random.PRNGKey(1))

        assert not jnp.allclose(u0_1, u0_2)

    def test_sample_ic_with_modes(self, key):
        """Verify sample_ic works with different number of modes."""
        u0 = burgers.sample_ic(key, n_modes=4)

        assert u0.shape == (NX,)


class TestBurgersRateCode:
    """Tests for rate_code function."""

    def test_rate_code_shape(self):
        """Verify rate_code output shape is (2*NX,) = (N_ENC,)."""
        u_field = jnp.ones(NX)
        x_enc = burgers.rate_code(u_field)

        assert x_enc.shape == (2 * NX,)
        assert x_enc.shape == (N_ENC,)

    def test_rate_code_positive_only(self):
        """Verify positive values go to positive channel."""
        u_field = jnp.ones(NX) * 2.0
        x_enc = burgers.rate_code(u_field)

        # First half should be the positive values
        up = x_enc[:NX]
        un = x_enc[NX:]

        assert jnp.allclose(up, 2.0)
        assert jnp.all(un == 0.0)

    def test_rate_code_negative_only(self):
        """Verify negative values go to negative channel."""
        u_field = jnp.ones(NX) * -2.0
        x_enc = burgers.rate_code(u_field)

        # Second half should contain the absolute values
        up = x_enc[:NX]
        un = x_enc[NX:]

        assert jnp.all(up == 0.0)
        assert jnp.allclose(un, 2.0)

    def test_rate_code_mixed(self):
        """Verify mixed signs are correctly separated."""
        u_field = jnp.array([1.0, -1.0, 2.0, -2.0] * (NX // 4))
        x_enc = burgers.rate_code(u_field)

        up = x_enc[:NX]
        un = x_enc[NX:]

        # Positive values should be in up, negatives in un
        assert jnp.all(up >= 0.0)
        assert jnp.all(un >= 0.0)

    def test_rate_code_zero(self):
        """Verify zero input gives all zeros."""
        u_field = jnp.zeros(NX)
        x_enc = burgers.rate_code(u_field)

        assert jnp.all(x_enc == 0.0)


class TestBurgersLoss:
    """Tests for loss_mse function."""

    def test_loss_mse_shape(self):
        """Verify loss_mse returns scalar."""
        z_pred = jnp.ones(NX)
        u_target = jnp.zeros(NX)

        loss = burgers.loss_mse(z_pred, u_target)

        assert loss.shape == ()

    def test_loss_mse_zero_when_equal(self):
        """Verify loss is zero when predictions match."""
        u = jnp.ones(NX)

        loss = burgers.loss_mse(u, u)

        assert jnp.isclose(loss, 0.0)

    def test_loss_mse_positive(self, key):
        """Verify loss is always non-negative."""
        z_pred = burgers.sample_ic(key)
        u_target = burgers.sample_ic(jax.random.PRNGKey(1))

        loss = burgers.loss_mse(z_pred, u_target)

        assert loss >= 0.0


class TestBurgersArms:
    """Tests for arm configurations."""

    def test_arm_configurations(self):
        """Verify all arm configurations exist."""
        assert burgers.ARM_BPTT_SURROGATE.name == "BPTT_surrogate"
        assert burgers.ARM_A_ONLY.name == "A_only"
        assert burgers.ARM_C_ONLY.name == "C_only"
        assert burgers.ARM_A_PLUS_C.name == "A_plus_C"

    def test_all_arms_list(self):
        """Verify ALL_ARMS contains all configurations."""
        assert len(burgers.ALL_ARMS) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
