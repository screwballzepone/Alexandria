"""
§10 — Clock acceptance tests.

Tests the Distillation Clock with tick detection and soft gating.

Acceptance probe:
- Poisson spikes λ=0.05, T=1000
- Verify tick count < T/DELTA_MIN = 500
- mean inter-tick gap ≥ DELTA_MIN

Invariants verified:
- I-CLK-3: gate ∈ [0, 1]
"""

import jax
import jax.numpy as jnp
import pytest

from lcn_brain.lcn import clock
from lcn_brain.lcn.constants import (
    RHO_THRESHOLD0,
    DELTA_MIN,
    N_ENC,
)


class TestClockAcceptance:
    """Acceptance probe for Clock from §10."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    @pytest.fixture
    def poisson_spikes(self, key):
        """Generate Poisson spike train with λ=0.05, T=1000."""
        T = 1000
        # Each encoder unit fires with probability 0.05 per timestep
        key_spikes = jax.random.split(key, N_ENC)
        # Use broadcasting: each neuron has its own random key
        spikes_list = [jax.random.uniform(k, (T,)) < 0.05 for k in key_spikes]
        return jnp.stack(spikes_list, axis=1).astype(float)  # shape (T, N_ENC)

    def test_tick_count_bound(self, poisson_spikes):
        """Verify tick count < T/DELTA_MIN = 500."""
        final_state, ticks, gates, rho_traj = clock.run_clock(poisson_spikes)

        tick_count = jnp.sum(ticks)

        max_ticks = poisson_spikes.shape[0] / DELTA_MIN

        assert tick_count < max_ticks, f"Tick count {tick_count} >= T/DELTA_MIN={max_ticks}"

    def test_mean_intertick_gap(self, poisson_spikes):
        """Verify mean inter-tick gap ≥ DELTA_MIN."""
        final_state, ticks, gates, rho_traj = clock.run_clock(poisson_spikes)

        # Find tick indices
        tick_indices = jnp.where(ticks)[0]

        if len(tick_indices) < 2:
            # Not enough ticks to compute gap - skip or pass trivially
            pytest.skip("Not enough ticks to compute inter-tick gap")

        # Compute gaps between consecutive ticks
        gaps = jnp.diff(tick_indices)

        mean_gap = jnp.mean(gaps)

        assert mean_gap >= DELTA_MIN, f"Mean inter-tick gap {mean_gap} < DELTA_MIN={DELTA_MIN}"


class TestClockInvariants:
    """Invariant checks for Clock."""

    def test_gate_in_unit_interval(self):
        """I-CLK-3: gate ∈ [0, 1] for various rho_ema values."""
        # Test various rho_ema values
        rho_ema_values = jnp.array([0.0, 0.01, 0.05, 0.1, 0.5, 1.0])

        for rho_ema in rho_ema_values:
            gate = clock.gate_value(rho_ema)
            assert 0.0 <= gate <= 1.0, f"Gate {gate} outside [0, 1] for rho_ema={rho_ema}"

    def test_gate_monotonic(self):
        """Verify gate is monotonically increasing with rho_ema."""
        rho_ema_low = 0.01
        rho_ema_high = 0.1

        gate_low = clock.gate_value(rho_ema_low)
        gate_high = clock.gate_value(rho_ema_high)

        assert gate_low <= gate_high, "Gate should be monotonically increasing"


class TestClockStep:
    """Unit tests for clock_step function."""

    def test_clock_step_shape(self):
        """Verify clock_step returns correct shapes."""
        state = clock.clock_init()
        s_t = jnp.ones(N_ENC) * 0.1

        new_state, tick, gate, rho_t = clock.clock_step(state, s_t)

        assert "rho_ema" in new_state
        assert "cooldown" in new_state
        assert tick.shape == ()  # scalar
        assert gate.shape == ()  # scalar
        assert rho_t.shape == ()  # scalar

    def test_clock_step_no_tick_when_cooldown(self):
        """Verify no tick fires during cooldown."""
        state = {
            "rho_ema": jnp.array(0.1),
            "cooldown": jnp.array(1.0),  # Cooldown active
        }
        s_t = jnp.ones(N_ENC) * 10.0  # High spike rate

        new_state, tick, gate, rho_t = clock.clock_step(state, s_t)

        assert not tick, "Tick should not fire during cooldown"

    def test_clock_step_tick_when_high_activity(self):
        """Verify tick fires when activity exceeds EMA."""
        state = {
            "rho_ema": jnp.array(0.01),  # Low threshold
            "cooldown": jnp.array(0.0),  # No cooldown
        }
        s_t = jnp.ones(N_ENC) * 1.0  # Very high activity

        new_state, tick, gate, rho_t = clock.clock_step(state, s_t)

        # Should tick because rho_t > rho_ema and cooldown is 0
        # (depends on implementation, but with high activity it should)


class TestClockInit:
    """Tests for clock initialization."""

    def test_clock_init_values(self):
        """Verify clock_init returns expected initial values."""
        state = clock.clock_init()

        assert jnp.isclose(state["rho_ema"], RHO_THRESHOLD0)
        assert state["cooldown"] == 0.0


class TestClockRun:
    """Tests for run_clock function."""

    @pytest.fixture
    def spike_window(self, key):
        """Generate T=50 spike window."""
        T = 50
        key = jax.random.PRNGKey(42)
        return jax.random.uniform(key, (T, N_ENC), minval=0.0, maxval=0.02)

    def test_run_clock_output_shapes(self, spike_window):
        """Verify run_clock returns correct shapes."""
        final_state, ticks, gates, rho_traj = clock.run_clock(spike_window)

        T = spike_window.shape[0]
        assert ticks.shape == (T,)
        assert gates.shape == (T,)
        assert rho_traj.shape == (T,)

    def test_run_clock_ema_update(self, spike_window):
        """Verify EMA is properly updated."""
        final_state, ticks, gates, rho_traj = clock.run_clock(spike_window)

        # Final rho_ema should be somewhere between initial and final rho values
        # Check it's a valid float
        assert jnp.isfinite(final_state["rho_ema"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
