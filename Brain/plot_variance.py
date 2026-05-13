#!/usr/bin/env python3
"""B4 variance regression plot."""
import sys; sys.path.insert(0, "Brain"); sys.path.insert(0, "Brain/lcn_brain")
import json, numpy as np, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

def plot_variance():
    with open("Brain/lcn_brain/tests/variance_regression_results.json") as f:
        data = json.load(f)
    
    N_values = np.array(data["config"]["N_values"])
    variances = np.array([data["results"][str(n)]["variance"] for n in N_values])
    std_errs = np.array([data["results"][str(n)]["std_err"] for n in N_values])
    slope = data["slope"]
    r2 = data["r_squared"]
    true_grad = data.get("true_grad_norm", 2.044)
    
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.errorbar(N_values, variances, yerr=std_errs, fmt='o', capsize=4,
                color='#E06C75', markersize=8, label='Measured variance')
    
    ref = variances[0] * (N_values[0] / N_values)
    ax.plot(N_values, ref, '--', color='gray', linewidth=2, label='1/N reference (variance)')
    
    ax.set_xscale('log'); ax.set_yscale('log')
    ax.set_xlabel('N (JVP directions)', fontsize=12)
    ax.set_ylabel('Gradient estimator variance', fontsize=12)
    ax.set_title(f'JVP Estimator Variance vs N\nslope={slope:.3f}, R²={r2:.3f}, |∇|≈{true_grad:.3f}', fontsize=14)
    ax.grid(True, which='both', ls='--', alpha=0.5)
    ax.legend(fontsize=11)
    
    plt.tight_layout()
    plt.savefig("Brain/variance_vs_N.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("variance_vs_N.png saved")

if __name__ == "__main__":
    plot_variance()
