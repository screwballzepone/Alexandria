"""4-arm comparison plot for the Burgers' testbed.
Compares BPTT_surrogate, A_only, C_only, A_plus_C across T values.
"""
import sys; sys.path.insert(0, 'Brain')
import jax, jax.numpy as jnp
import matplotlib
matplotlib.use('Agg')  # headless
import matplotlib.pyplot as plt

from lcn_brain.lcn.testbed.arms import compare_arms

# Run comparison at multiple T values
# T=10 fast, T=100 medium, skip T=1000 for now (very slow)
T_values = [10, 100]
key = jax.random.PRNGKey(42)
results = compare_arms(key, T_values=T_values, n_steps_per_enc=1)

# Organize by arm and T
arms = ['BPTT_surrogate', 'A_only', 'C_only', 'A_plus_C']
colors = ['#569CD6', '#4CAF50', '#CE9178', '#DCDCAA']

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('4-Arm Comparison — Burgers\' Testbed', fontsize=16, fontweight='bold')

for i, arm_name in enumerate(arms):
    ax = axes[i // 2][i % 2]
    ax.set_title(arm_name, fontsize=13)
    ax.set_xlabel('Timestep')
    ax.set_ylabel('MSE Loss')
    ax.grid(True, alpha=0.3)
    
    for T in T_values:
        key = f"{arm_name}_T={T}"
        if key in results:
            result = results[key]
            loss_hist = result.get('loss_history', [])
            if loss_hist:
                # For BPTT (1 entry = avg loss), expand to constant line
                if arm_name == 'BPTT_surrogate' and len(loss_hist) == 1:
                    loss_hist = [loss_hist[0]] * T
                
                ax.plot(range(len(loss_hist)), loss_hist, 
                       color=colors[i], alpha=0.8, linewidth=1.5,
                       label=f'T={T}')
    
    ax.legend(loc='upper right', fontsize=9)

# Summary bar chart: final loss per arm per T
ax_bar = axes[1][1]
ax_bar.clear()
ax_bar.set_title('Final Loss by Arm & T', fontsize=13)
ax_bar.set_ylabel('MSE Loss')
x = jnp.arange(len(arms))
width = 0.35
for j, T in enumerate(T_values):
    losses = []
    for arm_name in arms:
        key = f"{arm_name}_T={T}"
        loss_hist = results.get(key, {}).get('loss_history', [])
        losses.append(loss_hist[-1] if loss_hist else float('nan'))
    bars = ax_bar.bar(x + j * width, losses, width, label=f'T={T}', 
                      color=[colors[i] for i in range(4)], alpha=0.7)
ax_bar.set_xticks(x + width / 2)
ax_bar.set_xticklabels([a.replace('_','\n') for a in arms], fontsize=8)
ax_bar.legend(fontsize=9)
ax_bar.grid(True, axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('Brain/comparison_plot.png', dpi=150, bbox_inches='tight')
print("Saved Brain/comparison_plot.png")

# Print summary table
print("\nLoss summary:")
print(f"{'Arm':<20} ", end='')
for T in T_values:
    print(f"{'T='+str(T):>12}", end='')
print()
print("-" * (20 + 12 * len(T_values)))
for arm_name in arms:
    print(f"{arm_name:<20} ", end='')
    for T in T_values:
        key = f"{arm_name}_T={T}"
        loss_hist = results.get(key, {}).get('loss_history', [])
        loss_final = loss_hist[-1] if loss_hist else float('nan')
        print(f"{loss_final:>12.6f}", end='')
    print()
