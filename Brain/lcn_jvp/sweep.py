#!/usr/bin/env python3
"""Hyperparameter sweep over LCN training parameters.

Performs a full factorial grid search over eta_plastic, mu_free,
sigma_smoothing, and rho_0. For each combo, runs compare_arms(T=10)
and records per-arm results. Ranks by final loss, prints top 10,
and saves all results to JSON.

Usage:
    python Brain/lcn_jvp/sweep.py
"""

import sys
import json
import itertools
import math

sys.path.insert(0, "Brain")
sys.path.insert(0, "Brain/lcn_brain")


def run_sweep():
    import jax
    import jax.numpy as jnp
    import lcn.constants as C
    from lcn.testbed.arms import compare_arms

    # Sweep grid
    eta_values = [1e-4, 1e-3, 1e-2]
    mu_free_values = [0.0, 0.1, 0.5]
    sigma_values = [1e-4, 1e-3, 1e-2]
    rho_0_values = [0.01, 0.05, 0.1]

    grid = list(itertools.product(eta_values, mu_free_values, sigma_values, rho_0_values))
    total = len(grid)
    all_results = []

    for idx, (eta, mu_free, sigma, rho_0) in enumerate(grid):
        print(f"Sweep combo {idx + 1}/{total}: eta={eta}, mu_free={mu_free}, sigma={sigma}, rho_0={rho_0}", flush=True)

        C.ETA_PLASTIC = eta
        C.MU_FREE = mu_free
        C.SIGMA_THRESHOLD = sigma
        C.RHO_THRESHOLD0 = rho_0

        key = jax.random.PRNGKey(42)

        try:
            res = compare_arms(key, nu=0.01, T_values=[10], n_steps_per_enc=20)
        except Exception as exc:
            print(f"  ERROR: {exc}", flush=True)
            all_results.append({
                "combo": idx + 1, "eta_plastic": eta, "mu_free": mu_free,
                "sigma_smoothing": sigma, "rho_0": rho_0,
                "error": str(exc), "arms": {},
            })
            continue

        arms_data = {}
        for result_key, arm_result in res.items():
            if "_T=" in result_key:
                arm_name = result_key.split("_T=")[0]
            else:
                arm_name = result_key

            loss_history = arm_result.get("loss_history", [])
            final_loss = float(loss_history[-1]) if loss_history else math.nan
            W_z = arm_result.get("W_z_final", None)
            W_z_norm = float(jnp.linalg.norm(W_z)) if W_z is not None else math.nan

            arms_data[arm_name] = {
                "final_loss": final_loss,
                "W_z_norm": W_z_norm,
                "d_k": arm_result.get("last_training_d_k", 0),
                "kappa": float(arm_result.get("last_training_kappa", 0.0)),
            }
            print(f"  {arm_name}: loss={final_loss:.6f}, W_z_norm={W_z_norm:.6f}", flush=True)

        all_results.append({
            "combo": idx + 1, "eta_plastic": eta, "mu_free": mu_free,
            "sigma_smoothing": sigma, "rho_0": rho_0,
            "error": None, "arms": arms_data,
        })

    # Rank by best-arm final loss
    for entry in all_results:
        arms = entry.get("arms", {})
        losses = [a["final_loss"] for a in arms.values() if not (isinstance(a["final_loss"], float) and math.isnan(a["final_loss"]))]
        entry["_min_loss"] = min(losses) if losses else math.nan
        entry["_mean_loss"] = sum(losses) / len(losses) if losses else math.nan
        entry["_n_arms_ok"] = len(losses)

    ranked = sorted(all_results, key=lambda e: e.get("_min_loss", math.inf))

    print("\n" + "=" * 130, flush=True)
    print("TOP 10 CONFIGURATIONS  (ranked by best-arm final loss)", flush=True)
    print("=" * 130, flush=True)
    header = f"{'Rank':<5} {'eta':<10} {'mu_free':<9} {'sigma':<10} {'rho_0':<8} {'min_loss':<12} {'mean_loss':<12} {'arms':<6} {'best_arm':<20}"
    print(header, flush=True)
    print("-" * 130, flush=True)
    for rank, entry in enumerate(ranked[:10], 1):
        arms = entry.get("arms", {})
        best_arm, best_loss = "-", math.inf
        for name, data in arms.items():
            fl = data["final_loss"]
            if isinstance(fl, float) and not math.isnan(fl) and fl < best_loss:
                best_loss, best_arm = fl, name
        print(f"{rank:<5} {entry['eta_plastic']:<10} {entry['mu_free']:<9} {entry['sigma_smoothing']:<10} {entry['rho_0']:<8} {entry['_min_loss']:<12.6f} {entry['_mean_loss']:<12.6f} {entry['_n_arms_ok']:<6} {best_arm:<20}", flush=True)
    print("=" * 130, flush=True)

    def _to_json_safe(obj):
        if hasattr(obj, "item"):
            return obj.item()
        if isinstance(obj, float):
            if math.isnan(obj):
                return "NaN"
            if math.isinf(obj):
                return "Infinity" if obj > 0 else "-Infinity"
        return obj

    cleaned = []
    for e in all_results:
        out = {k: v for k, v in e.items() if k not in ("_min_loss", "_mean_loss", "_n_arms_ok")}
        out["arms"] = {an: {ak: _to_json_safe(av) for ak, av in av.items()} for an, av in e["arms"].items()}
        cleaned.append(out)

    output_path = "Brain/hyperparameter_sweep_results.json"
    with open(output_path, "w") as f:
        json.dump(cleaned, f, indent=2)
    print(f"\nResults saved to {output_path}  ({len(cleaned)} combos)", flush=True)
    print("Done.", flush=True)


if __name__ == "__main__":
    run_sweep()
