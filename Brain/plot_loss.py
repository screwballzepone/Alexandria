#!/usr/bin/env python3
"""4-arm loss vs T plot for Phase C."""
import sys; sys.path.insert(0, "Brain"); sys.path.insert(0, "Brain/lcn_brain")
import json, numpy as np, jax, jax.numpy as jnp
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from lcn.testbed.arms import compare_arms

def get_final_loss(res, arm, T):
    """Extract final loss from compare_arms result dict."""
    k = f"{arm}_T={T}"
    if k in res:
        lh = res[k].get('loss_history', [])
        if lh: return float(lh[-1])
    return float('nan')

def plot_loss():
    T_values = [10, 100]  # T=1000 too slow, add later
    arms = ['BPTT_surrogate', 'A_only', 'C_only', 'A_plus_C']
    colors = ['#569CD6', '#4CAF50', '#CE9178', '#DCDCAA']
    
    # Run comparisons
    key = jax.random.PRNGKey(42)
    final_losses = {arm: [] for arm in arms}
    
    for T in T_values:
        print(f"Running compare_arms(T={T})...")
        res = compare_arms(key, T_values=[T], n_steps_per_enc=1)
        for arm in arms:
            loss = get_final_loss(res, arm, T)
            final_losses[arm].append(loss)
            print(f"  {arm} T={T}: loss={loss:.4f}")
    
    # Plot
    fig, ax = plt.subplots(figsize=(9, 6))
    x = np.arange(len(T_values))
    width = 0.18
    
    for i, arm in enumerate(arms):
        y = final_losses[arm]
        ax.bar(x + i*width, y, width, label=arm.replace('_',' '),
               color=colors[i], alpha=0.85, edgecolor='black')
    
    ax.set_xlabel('Encoder window length T', fontsize=12)
    ax.set_ylabel('Final MSE Loss', fontsize=12)
    ax.set_title('4-Arm Comparison on Burgers\' Equation\nBPTT surrogate vs A-only / C-only / A+C (LCN)', fontsize=14)
    ax.set_xticks(x + width*1.5)
    ax.set_xticklabels([f'T={t}' for t in T_values])
    ax.grid(axis='y', alpha=0.3)
    ax.legend(loc='upper right', fontsize=10)
    
    plt.tight_layout()
    plt.savefig("Brain/loss_vs_T.png", dpi=300, bbox_inches='tight')
    plt.close()
    print("loss_vs_T.png saved")

if __name__ == "__main__":
    plot_loss()
