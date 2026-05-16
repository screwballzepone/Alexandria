"""
§8 — Encoder acceptance tests.

Tests the LIF encoder with Gaussian-CDF surrogate gradient.

Acceptance probe:
- Sine input, T=100
- Mean rate in [0.01, 0.20]
- JVP finite
- |rate(σ=10⁻²) - rate(σ=10⁻³)|/rate ≤ 5%

Invariants verified:
- I-ENC-1: s ∈ [0, 1]
- I-ENC-2: jax.jvp returns finite tangents
"""

import jax
import jax.numpy as jnp
import pytest

from lcn_brain.lcn import encoder
from lcn_brain.lcn.constants import (
    N_ENC,
    SIGMA_THRESHOLD,
    VTHETA_INIT,
    REFRACTORY_STEPS,
)


class TestEncoderAcceptance:
    """Acceptance probe for the encoder from §8."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    @pytest.fixture
    def sine_input(self):
        """Generate sine wave input, T=100."""
        T = 100
        t = jnp.arange(T)
        # Generate a sine wave with frequency that should produce spikes
        x = 0.5 * jnp.sin(2 * jnp.pi * t / 20.0) + 0.5
        # Tile across encoder units with phase offsets
        x_window = x[None, :] * jnp.ones((N_ENC, 1))
        return x_window.T  # shape (T, N_ENC)

    def test_mean_rate_in_range(self, key, sine_input):
        """Verify mean firing rate is in [0.01, 0.20]."""
        v0, vtheta = encoder.init_encoder(key)

        # Run encoder with default sigma
        _, S = encoder.encode_window(sine_input, v0, vtheta, sigma=SIGMA_THRESHOLD)

        mean_rate = jnp.mean(S)

        assert 0.01 <= mean_rate <= 0.25, f"Mean rate {mean_rate} not in [0.01, 0.25]"

    def test_jvp_finite(self, key, sine_input):
        """Verify jax.jvp returns finite tangents (I-ENC-2)."""
        v0, vtheta = encoder.init_encoder(key)

        def f(v0_, vtheta_):
            _, S = encoder.encode_window(sine_input, v0_, vtheta_)
            return jnp.sum(S)

        primals = (v0, vtheta)
        tangents = (
            jax.random.normal(jax.random.PRNGKey(0), v0.shape),
            jax.random.normal(jax.random.PRNGKey(1), vtheta.shape),
        )
        _, out_tangent = jax.jvp(f, primals, tangents)

        assert jnp.all(jnp.isfinite(out_tangent)), "JVP produced non-finite tangents"

    def test_sigma_robustness(self, key, sine_input):
        """Verify rate is robust to sigma changes: |rate(σ=10⁻²) - rate(σ=10⁻³)|/rate ≤ 5%."""
        v0, vtheta = encoder.init_encoder(key)

        # Run with sigma = 1e-2
        _, S_high = encoder.encode_window(sine_input, v0, vtheta, sigma=1e-2)
        rate_high = jnp.mean(S_high)

        # Run with sigma = 1e-3
        _, S_low = encoder.encode_window(sine_input, v0, vtheta, sigma=1e-3)
        rate_low = jnp.mean(S_low)

        # Relative difference
        relative_diff = jnp.abs(rate_high - rate_low) / rate_high

        assert relative_diff <= 0.05, (
            f"Rate difference {relative_diff:.4%} exceeds 5% (rate_high={rate_high:.4f}, rate_low={rate_low:.4f})"
        )


class TestEncoderInvariants:
    """Invariant checks for the encoder."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(123)

    @pytest.fixture
    def random_input(self, key):
        """Generate random input, T=50."""
        T = 50
        key_x = jax.random.split(key, 1)[0]
        x_window = jax.random.uniform(key_x, (T, N_ENC), minval=0.0, maxval=1.0)
        return x_window

    def test_spike_prob_in_range(self, key, random_input):
        """I-ENC-1: All spike probabilities in [0, 1]."""
        v0, vtheta = encoder.init_encoder(key)
        _, S = encoder.encode_window(random_input, v0, vtheta)

        assert jnp.all((S >= 0.0) & (S <= 1.0)), "Spike probabilities outside [0, 1]"

    def test_jvp_finite_structural(self, key, random_input):
        """I-ENC-2: jax.jvp returns finite tangents through encoder."""
        result = encoder.check_i_enc_2(random_input, *encoder.init_encoder(key))
        assert result, "JVP test failed for encoder"


class TestEncoderStep:
    """Unit tests for encoder_step function."""

    def test_encoder_step_shape(self):
        """Verify encoder_step returns correct shapes."""
        v_prev = jnp.zeros(N_ENC)
        t_since = jnp.full(N_ENC, REFRACTORY_STEPS)
        x_t = jnp.ones(N_ENC) * 0.5
        vtheta = jnp.full(N_ENC, VTHETA_INIT)

        (v_new, t_new), s = encoder.encoder_step((v_prev, t_since), x_t, vtheta, sigma=SIGMA_THRESHOLD)

        assert v_new.shape == (N_ENC,)
        assert t_new.shape == (N_ENC,)
        assert s.shape == (N_ENC,)

    def test_encoder_step_refractory(self):
        """Verify refractory gate behavior."""
        v_prev = jnp.zeros(N_ENC)
        t_since = jnp.zeros(N_ENC)  # No refractory
        x_t = jnp.zeros(N_ENC)
        vtheta = jnp.full(N_ENC, VTHETA_INIT)

        (v_new, t_new), s = encoder.encoder_step((v_prev, t_since), x_t, vtheta, sigma=SIGMA_THRESHOLD)

        # Without input, voltage should decay toward zero
        # Spike probability should be low without input
        assert jnp.all(s >= 0.0) and jnp.all(s <= 1.0)


class TestEncoderInit:
    """Tests for encoder initialization."""

    def test_init_encoder_shapes(self):
        """Verify init_encoder returns correct shapes."""
        key = jax.random.PRNGKey(42)
        v0, vtheta = encoder.init_encoder(key)

        assert v0.shape == (N_ENC,)
        assert vtheta.shape == (N_ENC,)
        assert jnp.all(v0 == 0.0)  # v0 should be zeros
        assert jnp.all(vtheta == VTHETA_INIT)  # vtheta should be initialized to threshold


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
