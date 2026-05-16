"""
§16 — JVP gradient estimator (lcn_jvp) acceptance tests.

Tests the 5 public API surfaces of the lcn_jvp package:

  - lcn_jvp.dual:       sample_direction, antithetic
  - lcn_jvp.probes:     column_norm_probe
  - lcn_jvp.projection: active_set
  - lcn_jvp.estimators: jvp_activity, Result

Written TDD-style: these tests define the expected contract.
"""

import sys
from pathlib import Path

import jax
import jax.numpy as jnp
import pytest

# -- Path bootstrap -----------------------------------------------------------
_BRAIN_DIR = Path(__file__).resolve().parent.parent.parent
if str(_BRAIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BRAIN_DIR))

from lcn_jvp.dual import antithetic, sample_direction
from lcn_jvp.estimators import Result, jvp_activity
from lcn_jvp.probes import column_norm_probe
from lcn_jvp.projection import active_set

# -- Test dimensions (small for speed) ----------------------------------------
D_IN = 16   # Input dimension (actual D+M = 96, but 16 is faster)
P_OUT = 1   # Output dimension (scalar field)
SIGMA = 1e-2  # Default sigma for tests where we control the value explicitly


# =============================================================================
#  sample_direction
# =============================================================================

class TestSampleDirection:
    """Tests for sample_direction(key, shape, distribution)."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_output_shape(self, key):
        """Returns array of the requested shape."""
        v = sample_direction(key, shape=(D_IN,), distribution="gaussian")
        assert v.shape == (D_IN,), f"Expected shape ({D_IN},), got {v.shape}"
        assert v.ndim == 1

    def test_output_high_dimensional_shape(self, key):
        """Returns array of requested 2-D shape."""
        v = sample_direction(key, shape=(3, 4), distribution="gaussian")
        assert v.shape == (3, 4), f"Expected shape (3, 4), got {v.shape}"

    def test_zero_mean(self, key):
        """Output has approximately zero mean for large samples."""
        v = sample_direction(key, shape=(10_000,), distribution="gaussian")
        mean_val = jnp.mean(v)
        assert jnp.abs(mean_val) < 0.05, f"Expected mean \u2248 0, got {mean_val}"

    def test_deterministic_same_key(self, key):
        """Same key produces identical output."""
        v1 = sample_direction(key, shape=(D_IN,), distribution="gaussian")
        v2 = sample_direction(key, shape=(D_IN,), distribution="gaussian")
        assert jnp.allclose(v1, v2), "Expected identical output for same key"

    def test_different_key_different_output(self, key):
        """Different keys produce (almost surely) different output."""
        k1, k2 = jax.random.split(key)
        v1 = sample_direction(k1, shape=(D_IN,), distribution="gaussian")
        v2 = sample_direction(k2, shape=(D_IN,), distribution="gaussian")
        assert not jnp.allclose(v1, v2), "Expected different output for different keys"

    def test_default_distribution_is_gaussian(self, key):
        """Default distribution parameter is 'gaussian'."""
        v1 = sample_direction(key, shape=(D_IN,), distribution="gaussian")
        v2 = sample_direction(key, shape=(D_IN,))
        assert jnp.allclose(v1, v2), "Default should be identical to explicit 'gaussian'"

    def test_unsupported_distribution_raises(self, key):
        """ValueError for unsupported distribution (e.g. 'laplace')."""
        with pytest.raises(ValueError, match="laplace"):
            sample_direction(key, shape=(D_IN,), distribution="laplace")

    def test_unsupported_distribution_uniform_raises(self, key):
        """ValueError for unsupported distribution 'uniform'."""
        with pytest.raises(ValueError):
            sample_direction(key, shape=(D_IN,), distribution="uniform")

    def test_rademacher_distribution(self, key):
        """Rademacher distribution returns {+1, -1} values."""
        v = sample_direction(key, shape=(1000,), distribution="rademacher")
        assert jnp.all(jnp.abs(v) == 1.0), "Rademacher values should be +/-1"
        assert jnp.all(v != 0.0), "Rademacher values should not be 0"

    def test_0d_shape(self, key):
        """Edge case: shape () returns scalar (0-d array)."""
        v = sample_direction(key, shape=(), distribution="gaussian")
        assert v.ndim == 0, f"Expected 0-d scalar, got ndim={v.ndim}"

    def test_unit_variance(self, key):
        """Output has approximately unit variance for large samples."""
        v = sample_direction(key, shape=(10_000,), distribution="gaussian")
        var_val = jnp.var(v)
        assert jnp.abs(var_val - 1.0) < 0.1, f"Expected variance \u2248 1, got {var_val}"

    def test_output_is_finite(self, key):
        """All output values are finite."""
        v = sample_direction(key, shape=(D_IN,), distribution="gaussian")
        assert jnp.all(jnp.isfinite(v)), "Expected all-finite output"


# =============================================================================
#  antithetic
# =============================================================================

class TestAntithetic:
    """Tests for antithetic(u, v, sigma=1e-3)."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    @pytest.fixture
    def u(self, key):
        return jax.random.normal(key, (D_IN,))

    @pytest.fixture
    def v(self, key):
        k1, k2 = jax.random.split(key)
        return jax.random.normal(k1, (D_IN,))

    def test_basic_construction(self, u, v):
        """Returns (u + sigma*v, u - sigma*v)."""
        u_plus, u_minus = antithetic(u, v, sigma=SIGMA)
        expected_plus = u + SIGMA * v
        expected_minus = u - SIGMA * v
        assert jnp.allclose(u_plus, expected_plus, atol=1e-6), "u_plus mismatch"
        assert jnp.allclose(u_minus, expected_minus, atol=1e-6), "u_minus mismatch"

    def test_output_shapes(self, u, v):
        """Both pair elements have the same shape as inputs."""
        u_plus, u_minus = antithetic(u, v, sigma=SIGMA)
        assert u_plus.shape == u.shape, f"u_plus shape {u_plus.shape} != {u.shape}"
        assert u_minus.shape == u.shape, f"u_minus shape {u_minus.shape} != {u.shape}"

    def test_default_sigma(self, u, v):
        """Default sigma is 1e-3 (per implementation)."""
        u_plus_explicit, u_minus_explicit = antithetic(u, v, sigma=1e-3)
        u_plus_default, u_minus_default = antithetic(u, v)
        assert jnp.allclose(u_plus_explicit, u_plus_default, atol=1e-7)
        assert jnp.allclose(u_minus_explicit, u_minus_default, atol=1e-7)

    def test_sigma_zero(self, u, v):
        """sigma=0 returns (u, u) — degenerate pair."""
        u_plus, u_minus = antithetic(u, v, sigma=0.0)
        assert jnp.allclose(u_plus, u, atol=1e-7)
        assert jnp.allclose(u_minus, u, atol=1e-7)

    def test_v_zeros(self, u):
        """v=zeros returns (u, u)."""
        v_zero = jnp.zeros_like(u)
        u_plus, u_minus = antithetic(u, v_zero, sigma=SIGMA)
        assert jnp.allclose(u_plus, u, atol=1e-7)
        assert jnp.allclose(u_minus, u, atol=1e-7)

    def test_sum_preserves_center(self, u, v):
        """Sum of the pair is 2*u (center of mass preserved)."""
        u_plus, u_minus = antithetic(u, v, sigma=SIGMA)
        assert jnp.allclose(u_plus + u_minus, 2.0 * u, atol=1e-6)

    def test_difference(self, u, v):
        """Difference of the pair is 2*sigma*v (within numerical tolerance)."""
        u_plus, u_minus = antithetic(u, v, sigma=SIGMA)
        diff = u_plus - u_minus
        expected = 2.0 * SIGMA * v
        # Use relative tolerance because float32 accumulation can introduce
        # small errors in the difference computation
        assert jnp.allclose(diff, expected, rtol=1e-5, atol=1e-6), \
            f"Max |diff - expected| = {jnp.max(jnp.abs(diff - expected)):.2e}"

    def test_large_sigma(self, u, v):
        """Edge case: sigma=1.0 produces valid pair."""
        u_plus, u_minus = antithetic(u, v, sigma=1.0)
        assert jnp.all(jnp.isfinite(u_plus))
        assert jnp.all(jnp.isfinite(u_minus))
        assert jnp.allclose(u_plus - u_minus, 2.0 * v, atol=1e-6)

    def test_negative_sigma_flips(self, u, v):
        """Negative sigma swaps the orientation of the pair."""
        u_plus_pos, u_minus_pos = antithetic(u, v, sigma=SIGMA)
        u_plus_neg, u_minus_neg = antithetic(u, v, sigma=-SIGMA)
        assert jnp.allclose(u_plus_pos, u_minus_neg, atol=1e-6)
        assert jnp.allclose(u_minus_pos, u_plus_neg, atol=1e-6)

    def test_scalar_inputs(self, key):
        """Edge case: scalar (0-d) inputs."""
        u = jnp.array(1.0)
        v = jnp.array(0.5)
        u_plus, u_minus = antithetic(u, v, sigma=SIGMA)
        assert u_plus.shape == ()
        assert u_minus.shape == ()
        assert jnp.allclose(u_plus, u + SIGMA * v, atol=1e-7)

    def test_different_dtypes_int(self):
        """Edge case: integer inputs cast to float."""
        u_int = jnp.array([1, 2, 3], dtype=jnp.int32)
        v_int = jnp.array([1, 1, 1], dtype=jnp.int32)
        u_plus, u_minus = antithetic(u_int, v_int, sigma=SIGMA)
        assert jnp.issubdtype(u_plus.dtype, jnp.floating), \
            f"Expected float output, got {u_plus.dtype}"

    def test_3d_input(self, key):
        """Edge case: 3-D input tensors."""
        u_3d = jax.random.normal(key, (4, 4, 4))
        k1, k2 = jax.random.split(key)
        v_3d = jax.random.normal(k1, (4, 4, 4))
        u_plus, u_minus = antithetic(u_3d, v_3d, sigma=SIGMA)
        assert u_plus.shape == (4, 4, 4)
        assert u_minus.shape == (4, 4, 4)


# =============================================================================
#  column_norm_probe
# =============================================================================

class TestColumnNormProbe:
    """Tests for column_norm_probe(forward_primal_fn, u_tau_prev, basis_idx,
    delta=1e-3).

    Uses forward-difference approximation:
        ||f(u + delta*e_i) - f(u)|| / delta
    """

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_identity_forward(self):
        """f(u) = u \u2192 column norm \u2248 1.0 (forward-difference estimate)."""
        u = jnp.ones(D_IN)
        forward_fn = lambda u_vec: u_vec
        norm_val = column_norm_probe(forward_fn, u, basis_idx=0)
        assert norm_val.shape == (), f"Expected scalar, got shape {norm_val.shape}"
        # Forward-difference introduces slight numerical error
        assert jnp.allclose(norm_val, 1.0, atol=1e-3), \
            f"Expected column norm \u2248 1.0, got {norm_val}"

    def test_scaled_forward(self, key):
        """f(u) = 2*u \u2192 column norm \u2248 2.0."""
        u = jax.random.normal(key, (D_IN,))
        forward_fn = lambda u_vec: 2.0 * u_vec
        norm_val = column_norm_probe(forward_fn, u, basis_idx=0)
        assert jnp.allclose(norm_val, 2.0, atol=1e-3), \
            f"Expected column norm \u2248 2.0, got {norm_val}"

    def test_different_basis_idx_values(self, key):
        """Different basis_idx produces different column norms for non-identity maps."""
        u = jax.random.normal(key, (D_IN,))
        scales = jnp.arange(1.0, D_IN + 1.0) / D_IN
        forward_fn = lambda u_vec: u_vec * scales

        n0 = column_norm_probe(forward_fn, u, basis_idx=0)
        n5 = column_norm_probe(forward_fn, u, basis_idx=5)
        # Column j has approximate norm scales[j] (forward-difference: small error)
        assert jnp.abs(n0 - scales[0]) < 1e-2, f"Expected \u2248 {scales[0]}, got {n0}"
        assert jnp.abs(n5 - scales[5]) < 1e-2, f"Expected \u2248 {scales[5]}, got {n5}"
        assert not jnp.allclose(n0, n5, atol=1e-3), \
            "Different indices should give different norms"

    def test_constant_forward(self):
        """Constant forward f(u) = c \u2192 column norm \u2248 0.0."""
        u = jnp.ones(D_IN)
        forward_fn = lambda u_vec: jnp.array(3.0)
        norm_val = column_norm_probe(forward_fn, u, basis_idx=0)
        assert jnp.allclose(norm_val, 0.0, atol=1e-6), \
            f"Expected \u2248 0.0 for constant f, got {norm_val}"

    def test_zero_input(self, key):
        """f(u) = u with u=0 \u2192 column norm \u2248 1.0 (probe independent of u)."""
        u = jnp.zeros(D_IN)
        forward_fn = lambda u_vec: u_vec
        norm_val = column_norm_probe(forward_fn, u, basis_idx=0)
        assert jnp.allclose(norm_val, 1.0, atol=1e-3)

    def test_scalar_output_forward(self, key):
        """f(u) returning scalar still works (output dim P=1)."""
        u = jax.random.normal(key, (D_IN,))
        w = jax.random.normal(key, (D_IN,))
        forward_fn = lambda u_vec: jnp.dot(w, u_vec)
        norm_val = column_norm_probe(forward_fn, u, basis_idx=0)
        # Forward-difference approximates |w_0| at column 0:
        #   (w @ (u + delta*e_0) - w @ u) / delta = w_0
        assert jnp.allclose(norm_val, jnp.abs(w[0]), atol=1e-2), \
            f"Expected \u2248 {jnp.abs(w[0])}, got {norm_val}"

    def test_last_basis_idx(self, key):
        """The last basis index (D_IN - 1) works correctly."""
        u = jax.random.normal(key, (D_IN,))
        forward_fn = lambda u_vec: 2.0 * u_vec
        norm_val = column_norm_probe(forward_fn, u, basis_idx=D_IN - 1)
        assert jnp.allclose(norm_val, 2.0, atol=1e-3)

    def test_flax_module(self, key):
        """Works with a Flax nn.Module as forward_primal_fn."""
        flax = pytest.importorskip("flax")
        nn = flax.linen

        class IdentityModule(nn.Module):
            @nn.compact
            def __call__(self, u):
                return u

        u = jax.random.normal(key, (D_IN,))
        module = IdentityModule()
        params = module.init(key, u)

        def forward_fn(u_vec):
            return module.apply(params, u_vec)

        norm_val = column_norm_probe(forward_fn, u, basis_idx=3)
        assert jnp.allclose(norm_val, 1.0, atol=1e-3)


# =============================================================================
#  active_set
# =============================================================================

class TestActiveSet:
    """Tests for active_set(dh_trace, epsilon=1e-4).

    Uses absolute-value thresholding: |dh_trace| > epsilon \u2192 active.
    """

    def test_all_zeros(self):
        """dh_trace = zeros \u2192 d_k = 0, proj = zeros(N, N)."""
        dh_trace = jnp.zeros(D_IN)
        proj, d_k = active_set(dh_trace, epsilon=1e-4)
        assert d_k == 0, f"Expected d_k=0 for all-zeros trace, got {d_k}"
        assert proj.shape == (D_IN, D_IN), f"Expected ({D_IN},{D_IN}), got {proj.shape}"
        assert jnp.all(proj == 0.0), "Expected zero matrix for inactive traces"

    def test_all_above_epsilon(self):
        """All |dh_trace| > epsilon \u2192 d_k = N, proj = identity."""
        dh_trace = jnp.full((D_IN,), 0.1)
        proj, d_k = active_set(dh_trace, epsilon=1e-4)
        assert d_k == D_IN, f"Expected d_k={D_IN}, got {d_k}"
        assert proj.shape == (D_IN, D_IN)
        assert jnp.allclose(proj, jnp.eye(D_IN)), "Expected identity matrix"

    def test_mixed_active_inactive(self):
        """Mixed: some |dh_trace| > epsilon, some \u2264 epsilon."""
        dh_trace = jnp.array([0.1, 1e-6, 0.2, 1e-8, 0.5, 0.0], dtype=jnp.float32)
        epsilon = 1e-4
        n = len(dh_trace)
        proj, d_k = active_set(dh_trace, epsilon=epsilon)
        # Active indices: 0, 2, 4 (|0.1| > 1e-4, |1e-6| < 1e-4, ...)
        assert d_k == 3, f"Expected d_k=3, got {d_k}"
        assert proj.shape == (n, n)
        expected_diag = jnp.array([1, 0, 1, 0, 1, 0], dtype=jnp.float32)
        assert jnp.allclose(jnp.diag(proj), expected_diag), \
            f"Expected diag {expected_diag}, got {jnp.diag(proj)}"
        off_diag_mask = 1 - jnp.eye(n)
        assert jnp.all(proj * off_diag_mask == 0.0), "Off-diagonal should be zero"

    def test_nan_treated_as_inactive(self):
        """NaN in dh_trace \u2192 |NaN| > epsilon is False, treated as inactive."""
        dh_trace = jnp.array([0.1, jnp.nan, 0.2, jnp.nan], dtype=jnp.float32)
        proj, d_k = active_set(dh_trace, epsilon=1e-4)
        assert d_k == 2, f"Expected d_k=2 (NaN entries inactive), got {d_k}"
        expected_diag = jnp.array([1.0, 0.0, 1.0, 0.0], dtype=jnp.float32)
        assert jnp.allclose(jnp.diag(proj), expected_diag), \
            f"NaN entries should be inactive, got diag {jnp.diag(proj)}"

    def test_epsilon_zero_all_active(self):
        """epsilon=0 \u2192 all non-zero |dh_trace| entries active."""
        dh_trace = jnp.array([1e-10, 1e-5, 0.1, 0.0], dtype=jnp.float32)
        proj, d_k = active_set(dh_trace, epsilon=0.0)
        assert d_k == 3, f"Expected d_k=3 (all non-zero), got {d_k}"
        expected_diag = jnp.array([1.0, 1.0, 1.0, 0.0], dtype=jnp.float32)
        assert jnp.allclose(jnp.diag(proj), expected_diag)

    def test_negative_values_active_by_abs(self):
        """Negative values with |value| > epsilon are active (absolute threshold)."""
        dh_trace = jnp.array([-0.5, -1.0, -0.01], dtype=jnp.float32)
        proj, d_k = active_set(dh_trace, epsilon=1e-4)
        # |-0.5| = 0.5 > 1e-4 \u2192 active; |-1.0| = 1.0 > 1e-4 \u2192 active;
        # |-0.01| = 0.01 > 1e-4 \u2192 active
        assert d_k == 3, f"Expected d_k=3 (all |vals| > 1e-4), got {d_k}"

    def test_mixed_sign_threshold(self):
        """Both positive and negative values are correctly thresholded by |val| > eps."""
        dh_trace = jnp.array([0.5, -0.001, 2.0, -1e-6], dtype=jnp.float32)
        proj, d_k = active_set(dh_trace, epsilon=1e-4)
        # |0.5| > 1e-4, |-0.001| = 0.001 > 1e-4, |2.0| > 1e-4, |-1e-6| < 1e-4
        assert d_k == 3, f"Expected d_k=3, got {d_k}"
        expected_diag = jnp.array([1.0, 1.0, 1.0, 0.0], dtype=jnp.float32)
        assert jnp.allclose(jnp.diag(proj), expected_diag)

    def test_inf_treated_as_active(self):
        """Infinity in dh_trace \u2192 |inf| > any epsilon, treated as active."""
        dh_trace = jnp.array([0.1, jnp.inf, 0.0], dtype=jnp.float32)
        proj, d_k = active_set(dh_trace, epsilon=1e-4)
        assert d_k == 2, f"Expected d_k=2 (inf counts as active), got {d_k}"

    def test_empty_trace(self):
        """Edge case: length-0 dh_trace returns empty proj and d_k=0."""
        dh_trace = jnp.array([], dtype=jnp.float32)
        proj, d_k = active_set(dh_trace, epsilon=1e-4)
        assert d_k == 0
        assert proj.shape == (0, 0), f"Expected (0,0) matrix, got {proj.shape}"

    def test_proj_is_float_diagonal(self):
        """proj is a diagonal matrix of float type."""
        dh_trace = jnp.full((D_IN,), 0.1)
        proj, d_k = active_set(dh_trace, epsilon=1e-4)
        assert jnp.issubdtype(proj.dtype, jnp.floating), \
            f"Expected float type, got {proj.dtype}"
        assert jnp.all(jnp.diag(proj) == 1.0)
        off_diag = proj - jnp.diag(jnp.diag(proj))
        assert jnp.all(off_diag == 0.0), "proj should be strictly diagonal"

    def test_d_k_is_array_or_int(self):
        """d_k is a 0-d jax.Array (converts to int via .item())."""
        dh_trace = jnp.full((D_IN,), 0.1)
        proj, d_k = active_set(dh_trace, epsilon=1e-4)
        # d_k can be jax.Array or numpy integer
        assert hasattr(d_k, "__int__") or isinstance(d_k, (int, jnp.integer)), \
            f"d_k should be int-convertible, got {type(d_k)}"
        assert int(d_k) == D_IN


# =============================================================================
#  Test helpers for jvp_activity
# =============================================================================

def _make_linear_test_problem(key, d_in=D_IN, p_out=P_OUT):
    """Create a deterministic linear test problem.

    Forward:  f(u) = W_z @ u
    Pullback: \u2202f/\u2202W_z applied to dz = outer(dz, u)

    Returns:
        (W_z, u, forward_fn, pullback_fn)
    """
    k1, k2 = jax.random.split(key)
    W_z = jax.random.normal(k1, (p_out, d_in)) * 0.1
    u = jax.random.normal(k2, (d_in,)) * 0.5

    def forward_fn(u_vec):
        return W_z @ u_vec

    def pullback_fn(u_vec, dz):
        return jnp.outer(dz, u_vec)

    return W_z, u, forward_fn, pullback_fn


def _make_constant_test_problem(key, d_in=D_IN, p_out=P_OUT):
    """Create a constant test problem with zero gradient."""
    u = jax.random.normal(key, (d_in,))

    def forward_fn(u_vec):
        return jnp.zeros(p_out)

    def pullback_fn(u_vec, dz):
        return jnp.zeros((p_out, d_in))

    return u, forward_fn, pullback_fn


# =============================================================================
#  jvp_activity
# =============================================================================

class TestJvpActivity:
    """Tests for jvp_activity(...) \u2192 Result."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    @pytest.fixture
    def linear_problem(self, key):
        _, u, forward_fn, pullback_fn = _make_linear_test_problem(key)
        return u, forward_fn, pullback_fn

    def _make_pair(self, u, key):
        """Helper: make an antithetic pair for testing."""
        v = sample_direction(key, shape=u.shape, distribution="gaussian")
        return antithetic(u, v, sigma=SIGMA)

    def _make_base_kwargs(self, u, pair, forward_fn, pullback_fn):
        """Common keyword arguments for jvp_activity calls."""
        return dict(
            forward_fn=forward_fn,
            u_tau_prev=u,
            pair=pair,
            rng_key=jax.random.PRNGKey(99),
            smoothing_sigma=SIGMA,
            active_proj=jnp.eye(D_IN),
            pullback=pullback_fn,
            truncation_radius=None,
            kappa_hat=jnp.array(1.0),
            gate_value=0.5,
            mu_free=0.0,
            delta_k=1.0,
        )

    def test_result_shape(self, key, linear_problem):
        """g_theta_hat has shape (P_OUT, D_IN)."""
        u, forward_fn, pullback_fn = linear_problem
        pair = self._make_pair(u, key)
        kwargs = self._make_base_kwargs(u, pair, forward_fn, pullback_fn)
        result = jvp_activity(**kwargs)
        assert result.g_theta_hat.shape == (P_OUT, D_IN), \
            f"Expected ({P_OUT}, {D_IN}), got {result.g_theta_hat.shape}"

    def test_result_is_finite(self, key, linear_problem):
        """g_theta_hat contains no NaN or Inf values."""
        u, forward_fn, pullback_fn = linear_problem
        pair = self._make_pair(u, key)
        kwargs = self._make_base_kwargs(u, pair, forward_fn, pullback_fn)
        result = jvp_activity(**kwargs)
        assert jnp.all(jnp.isfinite(result.g_theta_hat)), \
            "g_theta_hat contains NaN or Inf"

    def test_constant_forward_zero_gradient(self, key):
        """Constant forward + pullback that returns zero \u2192 g_theta_hat = 0."""
        u, forward_fn, pullback_fn = _make_constant_test_problem(key)
        pair = self._make_pair(u, key)
        kwargs = self._make_base_kwargs(u, pair, forward_fn, pullback_fn)
        result = jvp_activity(**kwargs)
        assert jnp.all(result.g_theta_hat == 0.0), \
            f"Expected zero gradient, got max |g| = " \
            f"{jnp.max(jnp.abs(result.g_theta_hat))}"

    def test_linear_forward_nonzero_gradient(self, key):
        """Linear forward gives non-zero gradient estimate."""
        _, u, forward_fn, pullback_fn = _make_linear_test_problem(key)
        pair = self._make_pair(u, key)
        kwargs = self._make_base_kwargs(u, pair, forward_fn, pullback_fn)
        result = jvp_activity(**kwargs)
        g_norm = float(jnp.linalg.norm(result.g_theta_hat))
        assert g_norm > 0.0, \
            f"Expected non-zero gradient for linear forward, got {g_norm}"

    def test_central_difference_small_sigma(self, key):
        """Finite g_theta_hat with small sigma for nonlinear forward."""
        k1, k2, k3 = jax.random.split(key, 3)
        w = jax.random.normal(k1, (D_IN,))
        u = jax.random.normal(k2, (D_IN,))
        sigma_small = 1e-4

        def forward_fn(u_vec):
            dot = jnp.dot(w, u_vec)
            return dot ** 2

        def pullback_fn(u_vec, dz):
            return dz * 2.0 * jnp.dot(w, u_vec) * w

        v = sample_direction(key=k3, shape=u.shape, distribution="gaussian")
        pair = antithetic(u, v, sigma=sigma_small)

        kwargs = self._make_base_kwargs(u, pair, forward_fn, pullback_fn)
        kwargs["smoothing_sigma"] = sigma_small
        result = jvp_activity(**kwargs)
        assert jnp.all(jnp.isfinite(result.g_theta_hat)), \
            "g_theta_hat must be finite for small sigma"

    def test_active_proj_measurement_only_i6(self, key, linear_problem):
        """I6: active_proj is measurement-only \u2014 identical g_theta_hat
        when passing identity vs zeros projection."""
        u, forward_fn, pullback_fn = linear_problem
        pair = self._make_pair(u, key)
        base_kwargs = self._make_base_kwargs(u, pair, forward_fn, pullback_fn)

        # With identity projection
        kwargs_eye = dict(base_kwargs)
        kwargs_eye["active_proj"] = jnp.eye(D_IN)
        result_eye = jvp_activity(**kwargs_eye)

        # With zero projection
        kwargs_zero = dict(base_kwargs)
        kwargs_zero["active_proj"] = jnp.zeros((D_IN, D_IN))
        result_zero = jvp_activity(**kwargs_zero)

        # g_theta_hat must be identical (I6: projection measurement-only)
        assert jnp.allclose(result_eye.g_theta_hat, result_zero.g_theta_hat), \
            "I6 violation: active_proj changed g_theta_hat"

    def test_truncation_radius_none(self, key, linear_problem):
        """truncation_radius=None is accepted without error."""
        u, forward_fn, pullback_fn = linear_problem
        pair = self._make_pair(u, key)
        kwargs = self._make_base_kwargs(u, pair, forward_fn, pullback_fn)
        kwargs["truncation_radius"] = None
        result = jvp_activity(**kwargs)
        assert jnp.all(jnp.isfinite(result.g_theta_hat))

    def test_truncation_radius_large(self, key, linear_problem):
        """Very large truncation_radius is accepted."""
        u, forward_fn, pullback_fn = linear_problem
        pair = self._make_pair(u, key)
        kwargs = self._make_base_kwargs(u, pair, forward_fn, pullback_fn)
        kwargs["truncation_radius"] = 1e6
        result = jvp_activity(**kwargs)
        assert jnp.all(jnp.isfinite(result.g_theta_hat))

    def test_truncation_radius_small(self, key, linear_problem):
        """Small truncation_radius is accepted (no crash)."""
        u, forward_fn, pullback_fn = linear_problem
        pair = self._make_pair(u, key)
        kwargs = self._make_base_kwargs(u, pair, forward_fn, pullback_fn)
        kwargs["truncation_radius"] = 1e-6
        result = jvp_activity(**kwargs)
        assert jnp.all(jnp.isfinite(result.g_theta_hat))

    def test_truncation_radius_zero(self, key, linear_problem):
        """truncation_radius=0 is accepted (no crash)."""
        u, forward_fn, pullback_fn = linear_problem
        pair = self._make_pair(u, key)
        kwargs = self._make_base_kwargs(u, pair, forward_fn, pullback_fn)
        kwargs["truncation_radius"] = 0.0
        result = jvp_activity(**kwargs)
        assert jnp.all(jnp.isfinite(result.g_theta_hat))

    def test_gateway_parameters_accepted(self, key, linear_problem):
        """Gateway params (rng_key, gate_value, mu_free, delta_k) accepted."""
        u, forward_fn, pullback_fn = linear_problem
        pair = self._make_pair(u, key)
        kwargs = self._make_base_kwargs(u, pair, forward_fn, pullback_fn)

        kwargs["rng_key"] = jax.random.PRNGKey(123)
        kwargs["gate_value"] = 0.8
        kwargs["mu_free"] = 0.1
        kwargs["delta_k"] = 2.0

        result = jvp_activity(**kwargs)
        assert jnp.all(jnp.isfinite(result.g_theta_hat))

    def test_deterministic_given_same_inputs(self, key, linear_problem):
        """Same inputs produce identical g_theta_hat."""
        u, forward_fn, pullback_fn = linear_problem
        pair = self._make_pair(u, key)
        kwargs = self._make_base_kwargs(u, pair, forward_fn, pullback_fn)

        result1 = jvp_activity(**kwargs)
        result2 = jvp_activity(**kwargs)

        assert jnp.allclose(result1.g_theta_hat, result2.g_theta_hat), \
            "Determinism violation: same inputs gave different g_theta_hat"

    def test_smoothing_sigma_consistency(self, key):
        """For linear forward, different sigma values give consistent results
        when the pair sigma matches smoothing_sigma."""
        W_z, u, forward_fn, pullback_fn = _make_linear_test_problem(key)

        for test_sigma in [1e-3, 1e-2, 1e-1]:
            k1, k2 = jax.random.split(key)
            v = sample_direction(k1, shape=u.shape, distribution="gaussian")
            pair = antithetic(u, v, sigma=test_sigma)

            kwargs = {
                "forward_fn": forward_fn,
                "u_tau_prev": u,
                "pair": pair,
                "rng_key": k2,
                "smoothing_sigma": test_sigma,
                "active_proj": jnp.eye(D_IN),
                "pullback": pullback_fn,
                "truncation_radius": None,
                "kappa_hat": jnp.array(1.0),
                "gate_value": 0.5,
                "mu_free": 0.0,
                "delta_k": 1.0,
            }

            result = jvp_activity(**kwargs)
            assert jnp.all(jnp.isfinite(result.g_theta_hat)), \
                f"Non-finite g_theta_hat at sigma={test_sigma}"

    def test_active_proj_various_values(self, key, linear_problem):
        """Various active_proj values (all-diagonal masks) accepted."""
        u, forward_fn, pullback_fn = linear_problem
        pair = self._make_pair(u, key)
        base = self._make_base_kwargs(u, pair, forward_fn, pullback_fn)

        # Test with a projection that only keeps first 3 dimensions
        mask = jnp.zeros(D_IN)
        mask = mask.at[:3].set(1.0)
        proj_partial = jnp.diag(mask)

        kwargs = dict(base)
        kwargs["active_proj"] = proj_partial
        result = jvp_activity(**kwargs)
        assert jnp.all(jnp.isfinite(result.g_theta_hat))


# =============================================================================
#  Result dataclass
# =============================================================================

class TestResult:
    """Tests for the Result frozen dataclass."""

    @pytest.fixture
    def key(self):
        return jax.random.PRNGKey(42)

    def test_result_has_g_theta_hat_field(self):
        """Result has g_theta_hat field."""
        g = jnp.zeros((P_OUT, D_IN))
        result = Result(g_theta_hat=g)
        assert hasattr(result, "g_theta_hat"), "Missing field: g_theta_hat"

    def test_g_theta_hat_is_jnp_array(self):
        """g_theta_hat is a jax.numpy array."""
        g = jnp.zeros((P_OUT, D_IN))
        result = Result(g_theta_hat=g)
        assert isinstance(result.g_theta_hat, jnp.ndarray), \
            f"Expected jnp.ndarray, got {type(result.g_theta_hat)}"

    def test_result_is_frozen(self):
        """Result is immutable (frozen dataclass)."""
        g = jnp.zeros((P_OUT, D_IN))
        result = Result(g_theta_hat=g)
        with pytest.raises((AttributeError, TypeError, Exception)):
            result.g_theta_hat = jnp.ones((P_OUT, D_IN))

    def test_result_is_dataclass(self):
        """Result is a dataclass."""
        from dataclasses import is_dataclass
        assert is_dataclass(Result), "Result should be a dataclass"

    def test_result_is_jax_pytree(self):
        """Result is an opaque JAX PyTree leaf (the whole dataclass is one leaf
        since it's a plain `@dataclass`, not `flax.struct.dataclass`)."""
        g = jnp.zeros((P_OUT, D_IN))
        result = Result(g_theta_hat=g)
        leaves = jax.tree_util.tree_leaves(result)
        assert len(leaves) == 1, "PyTree should have 1 opaque leaf (the Result itself)"
        assert isinstance(leaves[0], Result)

        treedef = jax.tree_util.tree_structure(result)
        result_restored = jax.tree_util.tree_unflatten(treedef, leaves)
        assert jnp.allclose(result_restored.g_theta_hat, g)

    def test_result_tree_map_on_g_theta_hat(self):
        """Access g_theta_hat directly for transformations."""
        g = jnp.zeros((P_OUT, D_IN))
        result = Result(g_theta_hat=g)

        # Transform the array directly (not the opaque Result leaf)
        doubled = Result(g_theta_hat=result.g_theta_hat * 2)
        assert jnp.allclose(doubled.g_theta_hat, g * 2)
        assert isinstance(doubled, Result)

    def test_result_with_nonzero_gradient(self):
        """g_theta_hat can hold non-zero values."""
        g = jnp.ones((P_OUT, D_IN))
        result = Result(g_theta_hat=g)
        assert jnp.all(result.g_theta_hat == 1.0)

    def test_result_shape_contract(self):
        """g_theta_hat shape (P, D+M) matches gradient contract."""
        g = jnp.zeros((P_OUT, D_IN))
        result = Result(g_theta_hat=g)
        assert result.g_theta_hat.shape == (P_OUT, D_IN), \
            f"Expected ({P_OUT}, {D_IN}), got {result.g_theta_hat.shape}"

    def test_result_repr(self):
        """Result has a readable repr."""
        g = jnp.zeros((P_OUT, D_IN))
        result = Result(g_theta_hat=g)
        r = repr(result)
        assert "g_theta_hat" in r, "repr should mention g_theta_hat"

    def test_result_multiple_fields(self):
        """Only g_theta_hat field is expected, but no extra fields crash it."""
        g = jnp.zeros((P_OUT, D_IN))
        result = Result(g_theta_hat=g)
        # Access the one and only field
        assert result.g_theta_hat.shape == (P_OUT, D_IN)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
