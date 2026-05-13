"""
Test: 1/sqrtN variance regression for the JVP gradient estimator.

Verifies that the variance of the N-averaged JVP gradient estimate
scales as 1/N (standard error prop 1/sqrtN).

Uses the actual ``readout_forward`` / ``readout_pullback`` from the LCN
readout module as the forward/pullback pair with fixed W_z and u.
Runs M=30 independent trials at each N in {8, 16, 32, 64, 128, 256, 512, 1024}
and fits log(variance) = a + b*log(N) to confirm b ~ -1.0 (20% tolerance).

Edge cases handled:
  - ``antithetic()`` sigma matched to ``smoothing_sigma`` (SIGMA_THRESHOLD)
  - Independent PRNG keys per direction and per trial
  - Small D_in = 16 to keep GPU/CPU memory low
  - Per-dimension variance reported to check isotropy
"""

import json
import math
import sys
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

# -- Path bootstrap ----------------------------------------------------------
# lcn_brain editable install is broken; lcn_jvp is not installed at all.
# Add Brain/ so both packages resolve.
_BRAIN_DIR = Path(__file__).resolve().parent.parent.parent
if str(_BRAIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BRAIN_DIR))

from lcn_jvp.dual import sample_direction, antithetic
from lcn_jvp.estimators import jvp_activity, Result
from lcn_brain.lcn.constants import SIGMA_THRESHOLD
from lcn_brain.lcn.readout import readout_forward, readout_pullback

# -- Configuration -----------------------------------------------------------
D_IN = 16               # Input dimension (small -> fast; actual D+M = 96)
P_OUT = 1               # Output dimension (scalar field)
SIGMA = float(SIGMA_THRESHOLD)   # 1e-2 --- matches smoothing width
N_VALUES = [8, 16, 32, 64, 128, 256, 512, 1024]
M_TRIALS = 30
SEED = 20260426


# ===========================================================================
#  Test problem
# ===========================================================================

def _make_test_problem(rng_key):
    """Create a deterministic test problem with known ground-truth gradient.

    Forward:  readout_forward(W_z, u) --- C2 gated mixture readout
    Pullback: readout_pullback(W_z, u, dz)

    The *true* gradient dz/dW_z at (W_z, u) is computed by evaluating the
    pullback at dz = 1 (the identity tangent in the 1-D output space).

    Returns:
        (W_z, u, forward_fn, pullback_fn, true_grad)
    """
    k1, k2 = jax.random.split(rng_key)
    W_z = jax.random.normal(k1, (P_OUT, D_IN)) * 0.1
    u = jax.random.normal(k2, (D_IN,)) * 0.5

    forward_fn = lambda u_vec: readout_forward(W_z, u_vec)
    pullback_fn = lambda u_vec, dz: readout_pullback(W_z, u_vec, dz)

    # Ground-truth gradient --- pullback with dz = 1 (scalar output)
    true_grad = readout_pullback(W_z, u, jnp.ones(P_OUT))  # (P, D_in)

    return W_z, u, forward_fn, pullback_fn, true_grad


def _single_gradient_estimate(forward_fn, pullback_fn, u, key, n_directions):
    """Average of N single-direction JVP gradient estimates.

    Each of the *n_directions* estimates uses an independent random direction
    *v* ~ N(0, I) and the corresponding antithetic pair (u +/- sigma v).

    Returns:
        g_hat_averaged: shape (P_OUT, D_IN).
    """
    keys = jax.random.split(key, n_directions)
    g_accum = []
    for k in keys:
        v = sample_direction(k, shape=u.shape, distribution="gaussian")
        pair = antithetic(u, v, sigma=SIGMA)
        res = jvp_activity(
            forward_fn=forward_fn,
            u_tau_prev=u,
            pair=pair,
            rng_key=k,                              # unused, API compat
            smoothing_sigma=SIGMA,
            active_proj=jnp.eye(D_IN),               # no active-set mask
            pullback=pullback_fn,
            truncation_radius=None,
            kappa_hat=jnp.ones((1,)),
            gate_value=0.5,
            mu_free=0.0,
            delta_k=1.0,
        )
        g_accum.append(res.g_theta_hat)             # (P_OUT, D_IN)
    return jnp.mean(jnp.stack(g_accum), axis=0)


# ===========================================================================
#  Variance regression
# ===========================================================================

def run_variance_regression():
    """Run full 1/N variance regression and return results.

    For each N in N_VALUES:
      1. Draw M_TRIALS independent PRNG keys.
      2. For each trial, compute the N-averaged gradient estimate.
      3. Compute per-element variance across trials, then mean variance.
      4. Compute standard error = sqrt(mean variance).

    Returns:
        results: dict[N, {"variance", "std_err", "variance_times_N"}]
        true_grad: ground-truth gradient tensor.
    """
    master_key = jax.random.PRNGKey(SEED)
    _wz, _u, forward_fn, pullback_fn, true_grad = _make_test_problem(master_key)

    results = {}
    for N in N_VALUES:
        trial_keys = jax.random.split(
            jax.random.fold_in(master_key, N),
            M_TRIALS,
        )

        estimates = []
        for trial_idx in range(M_TRIALS):
            g_hat = _single_gradient_estimate(
                forward_fn, pullback_fn, _u,
                trial_keys[trial_idx], N,
            )
            estimates.append(g_hat)

        # Stack -> (M_TRIALS, P_OUT, D_IN)
        estimates_arr = jnp.stack(estimates)

        # Per-element variance -> isotropic mean variance
        var_per_elem = jnp.var(estimates_arr, axis=0)           # (P, D_in)
        mean_var = float(jnp.mean(var_per_elem))
        std_err = math.sqrt(mean_var)

        results[N] = {
            "variance": mean_var,
            "std_err": std_err,
            "variance_times_N": mean_var * N,
            "var_per_dim_min": float(jnp.min(var_per_elem)),
            "var_per_dim_max": float(jnp.max(var_per_elem)),
        }

        print(
            f"  N={N:>4}:  variance={mean_var:.6e},  "
            f"std_err={std_err:.6e},  "
            f"var*N={mean_var * N:.6e},  "
            f"var_range=[{float(jnp.min(var_per_elem)):.2e}, "
            f"{float(jnp.max(var_per_elem)):.2e}]"
        )

    return results, true_grad


# ===========================================================================
#  Regression helpers
# ===========================================================================

def _fit_slope_log_log(n_values, variances):
    """Fit log(variance) = a + b*log(N) via ordinary least squares.

    Returns:
        (b, a, r_squared)
    """
    log_n = np.log(np.array(n_values, dtype=float))
    log_v = np.log(np.maximum(np.array(variances, dtype=float), 1e-30))
    A = np.vstack([log_n, np.ones_like(log_n)]).T
    b, a = np.linalg.lstsq(A, log_v, rcond=None)[0]
    residuals = log_v - (b * log_n + a)
    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((log_v - np.mean(log_v)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-30 else 0.0
    return b, a, r2


# ===========================================================================
#  Tests
# ===========================================================================

class TestVarianceRegression:
    """Variance regression for the JVP gradient estimator."""

    def test_variance_scales_as_one_over_n(self):
        """Verify variance prop 1/N: slope in [-1.2, -0.8], R^2 > 0.6."""
        results, true_grad = run_variance_regression()

        n_vals = sorted(results.keys())
        variances = [results[n]["variance"] for n in n_vals]
        b, a, r2 = _fit_slope_log_log(n_vals, variances)

        # -- Print summary table ----------------------------------------
        print("\n" + "=" * 74)
        print(
            f"{'N':>6}  {'Variance':>16}  {'StdErr':>14}  "
            f"{'Var*N':>14}  {'Var_min':>12}  {'Var_max':>12}"
        )
        print("=" * 74)
        for n in n_vals:
            r = results[n]
            print(
                f"{n:>6}  {r['variance']:>16.8e}  {r['std_err']:>14.6e}  "
                f"{r['variance_times_N']:>14.6e}  "
                f"{r['var_per_dim_min']:>12.4e}  "
                f"{r['var_per_dim_max']:>12.4e}"
            )
        print("=" * 74)
        print(f"\n  Fitted:  log(variance) = {b:.4f} * log(N) + {a:.4f}")
        print(f"           (theoretical slope = -1.0)")
        print(f"  R^2 = {r2:.4f}")
        tgn = float(jnp.linalg.norm(true_grad))
        print(f"  ||true_grad||_2 = {tgn:.6f}")
        tgi = float(jnp.max(jnp.abs(true_grad)))
        print(f"  ||true_grad||_inf = {tgi:.6f}")
        print(f"  Per-dim var ratio (max/min) = "
              f"{max(r['var_per_dim_max'] for r in results.values()):.1f}")

        # -- Save results to JSON ---------------------------------------
        output = {
            "slope": float(b),
            "intercept": float(a),
            "r_squared": float(r2),
            "config": {
                "D_in": D_IN,
                "P_out": P_OUT,
                "sigma": SIGMA,
                "M_trials": M_TRIALS,
                "N_values": N_VALUES,
                "seed": SEED,
            },
            "results": {
                str(n): {
                    "variance": results[n]["variance"],
                    "std_err": results[n]["std_err"],
                    "variance_times_N": results[n]["variance_times_N"],
                    "var_per_dim_min": results[n]["var_per_dim_min"],
                    "var_per_dim_max": results[n]["var_per_dim_max"],
                }
                for n in n_vals
            },
            "true_grad_norm": float(jnp.linalg.norm(true_grad)),
            "true_grad": true_grad.tolist(),
        }
        out_path = (
            Path(__file__).parent / "variance_regression_results.json"
        )
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\n  Results saved to {out_path}")

        # -- Assertions -------------------------------------------------
        assert -1.2 <= b <= -0.8, (
            f"Slope b={b:.4f} is outside [-1.2, -0.8] --- "
            f"variance does NOT scale as 1/N"
        )
        assert r2 > 0.6, (
            f"R^2={r2:.4f} < 0.6 --- linear model fit is poor; "
            f"the log-log relationship is not linear"
        )

        # Flag isotropy concerns (informational, not a hard assert)
        var_ratio = max(r['var_per_dim_max'] / max(r['var_per_dim_min'], 1e-30)
                        for r in results.values())
        if var_ratio > 10:
            print(
                f"\n  WARNING: Per-dimension variance ratio = {var_ratio:.1f} "
                f"(>10) -- possible anisotropy in estimator"
            )
