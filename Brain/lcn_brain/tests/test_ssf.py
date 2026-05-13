"""
§9 — SSF acceptance tests.

Tests the Selective State Filter (SSF) with diagonal selective ODE.

Acceptance probe:
- S≡0, T=100, random h0
- Verify ||h_T|| ≤ 1.05·||h_0||·e^{-A_MIN·T}

Invariants verified:
- I-SSF-1: a_i ≤ -A_MIN structurally
"""

import jax
import jax.numpy as jnp
import pytest
from flax import linen as nn

from lcn_brain.lcn import ssf
from lcn_brain.lcn.constants import D, N_ENC, A_MIN, B_PARAM


class TestSSFAcceptance:
    """Acceptance probe for SSF from §9."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    @pytest.fixture
    def ssf_params(self, key):
        """Create bound SSFParams module."""
        module = ssf.SSFParams()
        dummy_s = jnp.zeros(N_ENC)
        variables = module.init(key, dummy_s)
        return module.bind(variables)

    @pytest.fixture
    def zero_spike_input(self):
        """Zero spike input for T=100."""
        T = 100
        return jnp.zeros((T, N_ENC))

    def test_zero_input_contraction(self, key, ssf_params, zero_spike_input):
        """Verify ||h_T|| ≤ 1.05·||h_0||·e^{-A_MIN·T} with zero input."""
        # Random initial state
        h0 = jax.random.normal(key, (D,))

        # Run SSF with zero spikes
        h_final, (h_traj, (a_traj, B_traj)) = ssf.run_ssf(zero_spike_input, h0, ssf_params)

        # Compute expected bound
        T = zero_spike_input.shape[0]
        expected_decay = jnp.exp(-A_MIN * T)
        bound = 1.05 * jnp.linalg.norm(h0) * expected_decay

        actual_norm = jnp.linalg.norm(h_final)

        assert actual_norm <= bound, f"||h_T||={actual_norm:.4f} > 1.05·||h_0||·e^(-A_MIN*T)={bound:.4f}"


class TestSSFInvariants:
    """Invariant checks for SSF."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(123)

    @pytest.fixture
    def ssf_params(self, key):
        """Create bound SSFParams module."""
        module = ssf.SSFParams()
        dummy_s = jnp.zeros(N_ENC)
        variables = module.init(key, dummy_s)
        return module.bind(variables)

    @pytest.fixture
    def random_spike_input(self, key):
        """Random spike input, T=20."""
        T = 20
        return jax.random.uniform(key, (T, N_ENC), minval=0.0, maxval=0.1)

    def test_structural_contraction(self, key, ssf_params, random_spike_input):
        """I-SSF-1: a_i ≤ -A_MIN structurally."""
        # Run one step to get a(S)
        h0 = jnp.zeros(D)
        h1, (a_t, B_t) = ssf.ssf_step(h0, random_spike_input[0], ssf_params)

        # Check that all a_i are <= -A_MIN
        assert jnp.all(a_t <= -A_MIN), f"Some a_i values {a_t} are not <= -A_MIN={-A_MIN}"

    def test_ssfs_params_module(self, key):
        """Verify SSFParams can be instantiated and called."""
        params = ssf.SSFParams()
        s_t = jnp.ones(N_ENC)

        # Initialize and apply
        variables = params.init(jax.random.PRNGKey(0), s_t)
        a_t, B_t = params.apply(variables, s_t)

        assert a_t.shape == (D,)
        assert B_t.shape == (D, N_ENC)

    def test_l21_penalty(self, key, random_spike_input, ssf_params):
        """Verify l21_penalty computes correctly."""
        # Run SSF to get B trajectory
        h0 = jnp.zeros(D)
        _, (h_traj, (a_traj, B_traj)) = ssf.run_ssf(random_spike_input, h0, ssf_params)

        # B_traj is already shape (T, D, N_ENC) from scan stacking
        penalty = ssf.l21_penalty(B_traj)

        assert jnp.isfinite(penalty)
        assert penalty >= 0.0


class TestSSFStep:
    """Unit tests for ssf_step function."""

    @pytest.fixture
    def ssf_params(self, key):
        module = ssf.SSFParams()
        dummy_s = jnp.zeros(N_ENC)
        variables = module.init(key, dummy_s)
        return module.bind(variables)

    def test_ssf_step_shape(self, ssf_params):
        """Verify ssf_step returns correct shapes."""
        h_prev = jnp.zeros(D)
        s_t = jnp.zeros(N_ENC)

        h_new, (a_t, B_t) = ssf.ssf_step(h_prev, s_t, ssf_params)

        assert h_new.shape == (D,)
        assert a_t.shape == (D,)
        assert B_t.shape == (D, N_ENC)

    def test_ssf_step_zero_input(self, ssf_params):
        """Verify SSF step with zero input decays."""
        h_prev = jnp.ones(D)  # Start with some values
        s_t = jnp.zeros(N_ENC)

        h_new, _ = ssf.ssf_step(h_prev, s_t, ssf_params)

        # With zero input, h should decay toward zero
        assert jnp.linalg.norm(h_new) < jnp.linalg.norm(h_prev)


class TestSSFRun:
    """Tests for run_ssf function."""

    @pytest.fixture
    def ssf_params(self, key):
        module = ssf.SSFParams()
        dummy_s = jnp.zeros(N_ENC)
        variables = module.init(key, dummy_s)
        return module.bind(variables)

    @pytest.fixture
    def spike_window(self, key):
        """T=10 spike window."""
        return jax.random.uniform(key, (10, N_ENC), minval=0.0, maxval=0.05)

    def test_run_ssf_returns_trajectory(self, spike_window, ssf_params):
        """Verify run_ssf returns full trajectory."""
        h0 = jnp.zeros(D)

        h_final, (h_traj, (a_traj, B_traj)) = ssf.run_ssf(spike_window, h0, ssf_params)

        T = spike_window.shape[0]
        assert h_final.shape == (D,)
        # h_traj is a Pytree of (h_new, (a_t, B_t)) per step
        # We check it's properly structured
        assert len(h_traj) == T


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
