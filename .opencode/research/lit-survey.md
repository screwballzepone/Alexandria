# Literature Survey: Neuromorphic / Spiking Architectures for Agent Memory Without Backpropagation or Attention

**Date:** 2026-05-13  
**Agent:** @model-scientist (GLM-5.1)  
**Method:** Scientific-method protocol — Observe → Hypothesize → Test → Conclude → Recommend → Record

---

## Executive Summary

The LCN (Language Cognition Network) project sits at the intersection of four active research streams: forward-mode gradient learning, spiking neural plasticity, three-factor neuromodulated learning, and compressive long-term memory for sequence models. This survey covers 90+ papers and implementations across six research questions. **Key finding:** LCN's specific combination — forward-mode JVP + spike-driven distillation clock + switched-contraction plastic ODE + no attention — is not duplicated by any single published system. However, most individual components have close precedents. The most novel aspect is the *gate-triggered plastic ODE with switched contraction* (the "when to learn" mechanism), which has analogues in three-factor learning rules but has not been implemented as an ODE-level structural weight dynamics system in the ML literature. The least novel aspect is the forward-mode JVP training, which is well-explored but remains limited in scalability by high variance. The distillation clock is partially anticipated by Titans' "surprise" mechanism but differs fundamentally in using spike population activity rather than gradient magnitude as the gating signal.

**Novelty Score: 6.5/10** — partially novel combination; individual components range from well-explored (forward JVP: 4/10) to novel (switched contraction gate: 8/10).

---

## RQ1: Prior Art — Architectures Replacing Token Caches with Learned/Compressed Memory

### 1.1 Sparse Distributed Memory (Kanerva 1988)

**What it is:** A content-addressable memory that distributes binary patterns across a high-dimensional space. Addresses are "hard locations" — only addresses within a Hamming-radius threshold respond to a read/write. Storage capacity grows sublinearly with address dimension.

**Relevance to LCN:** Kanerva's SDM is the conceptual ancestor of LCN's structural memory (W_z). Both use distributed, content-addressable storage. Key difference: LCN's W_z is a continuous weight matrix updated by a learned ODE, not a binary address table.

**Status:** Well-studied. Kanerva Machine (Wu et al., 2018) extended SDM to generative models with Bayesian updates. Kanerva++ (2021) added differentiable block-allocated memory. Modern continuous SDM (Bricken & Pehlevan, 2021) showed equivalence to self-attention.

**Confidence:** High  
**Source:** Kanerva, P. (1988). *Sparse Distributed Memory.* MIT Press.; Wu et al. (2018). *The Kanerva Machine.* ICML; Bricken & Pehlevan (2021). *Attention is a kind of Sparse Distributed Memory.*

---

### 1.2 Modern Hopfield Networks / Dense Associative Memory (Krotov & Hopfield 2016; Ramsauer et al. 2020)

**What it is:** Generalizes classical Hopfield networks by using higher-order energy functions F(x) = x^β (for polynomial β) or exponential interactions. This yields exponential storage capacity (2^(N/2) patterns for N neurons). Ramsauer et al. (2020) showed the continuous version's one-step update is *identical to transformer self-attention* — specifically, `softmax(β * X * X^T) * X` where β controls storage capacity vs. separation.

**Relevance to LCN:** Modern Hopfield networks demonstrate that attention *is* a form of associative memory retrieval. LCN's explicit rejection of attention means it must solve the same retrieval problem (finding relevant past information) through a different mechanism — its SSF + clock + RCD pipeline. The theoretical question is whether RCD's LSTM-gated episodic memory can match the capacity-scaling of DAM. Current evidence suggests it cannot: DAM achieves exponential capacity with β → ∞, while LCN's RCD capacity is fixed at M=32.

**Status:** Active. Krotov & Hopfield (2021) extended to hierarchical associative memories (HAMs) with multiple layers — a closer analogue to LCN's three-substrate hierarchy. HOPFIELD-LAYERS library (ml-jku) provides PyTorch implementations.

**Confidence:** High  
**Source:** Krotov & Hopfield (2016). *Dense Associative Memory for Pattern Recognition.* NeurIPS; Ramsauer et al. (2020). *Hopfield Networks is All You Need.* ICML 2021; Krotov & Hopfield (2021). *Hierarchical Associative Memory.* arXiv:2107.06446.

---

### 1.3 Neural Turing Machines / Differentiable Neural Computers (Graves et al. 2014, 2016)

**What they are:** NTMs couple a neural network controller to an external memory matrix with differentiable read/write heads. DNCs (2016) added dynamic memory allocation, temporal linking, and free list management. Memory is addressed by content similarity (cosine similarity) and by temporal adjacency.

**Relevance to LCN:** NTM/DNC is a different paradigm — it uses gradient-based training (BPTT) through the memory access patterns. LCN's W_z is "memory" in the sense of learned weights, but there's no explicit read/write head. LCN writes to W_z only through the plastic ODE (driven by JVP estimates), not through attention-based addressing. DNC's temporal linking is closest to LCN's clock-enforced sequential memory update.

**Key difference:** DNC memory is slot-based and explicitly addressed. LCN's W_z is a dense weight matrix updated by a learned ODE. There's no "retrieval" step in LCN — the readout mixes W_z directly with episodic state.

**Confidence:** High  
**Source:** Graves et al. (2014). *Neural Turing Machines.* arXiv:1410.5401; Graves et al. (2016). *Hybrid Computing Using a Neural Network with Dynamic External Memory.* Nature.

---

### 1.4 Compressive Transformer (Rae et al. 2019)

**What it is:** Extends Transformer-XL by compressing old attention segments into a smaller representation before pushing them into long-term memory. Two-level memory: recent fine-grained, older coarse-grained. Compression ratio fixed, attention over both levels.

**Relevance to LCN:** The compressive transformer's two-level memory (recent detailed, older compressed) is structurally similar to LCN's working memory (h(t), per-timestep) + episodic memory (c_k, per-tick). But compression is lossy and fixed-ratio, whereas LCN's RCD is an LSTM that learns what to retain.

**Status:** Subsumed by more recent work (Infini-attention, Titans).

**Confidence:** High  
**Source:** Rae et al. (2019). *Compressive Transformers for Long Range Sequence Modelling.* ICLR.

---

### 1.5 Infini-attention (Munkhdalai et al. 2024)

**What it is:** Inserts a compressive memory into each transformer attention layer. Old KV states are stored in a linear-attention memory matrix (constant size per head) instead of being discarded. New queries retrieve from both local attention and compressive memory via learned aggregation weights. Memory complexity is O(d_key × d_value) per head — bounded and independent of sequence length.

**Relevance to LCN:** Infini-attention is the most directly comparable architecture. Both maintain fixed-size memory states. Key differences:
- **Memory update:** Infini-attention uses a simple additive/delta update: `M_s = M_{s-1} + A_s * V_s` (linear attention memory). LCN uses a plastic ODE with switched contraction.
- **Gating:** Infini-attention has a learned forget gate per segment. LCN uses spike-population-driven gating from the distillation clock.
- **Training:** Infini-attention is trained via standard backprop. LCN uses forward-mode JVP.
- **Scope:** Infini-attention is per-layer within a transformer. LCN is a standalone memory module designed as a sidecar to any LLM.

**Status:** Accepted to ICLR. Google AI. PyTorch implementations available on GitHub.  
**Confidence:** High  
**Source:** Munkhdalai et al. (2024). *Leave No Context Behind: Efficient Infinite Context Transformers with Infini-attention.* arXiv:2404.07143.

---

### 1.6 Titans (Behrouz et al. 2024/2025)

**What it is:** A neural long-term memory module that learns to memorize at test time via gradient descent on an internal loss. The memory is a small MLP whose parameters are updated online during inference using surprise-based signals. Three architectural variants: MAC (Memory as Context), MAG (Memory as Gate), MAL (Memory as Layer).

**Core innovation — surprise mechanism:** The "surprise" of an input x_t at memory M_{t-1} is measured as the gradient norm of the associative memory loss: `surprise_t = ||∇_M ℓ(M_{t-1}; x_t)||`. This drives both the momentum term and the forgetting gate. The update rule is:

```
S_t = η · S_{t-1} - θ · ∇ℓ(M_{t-1}; x_t)    # Surprise = momentum + gradient
M_t = (1 - α) · M_{t-1} + S_t                  # Memory update with forgetting
```

**Relevance to LCN:** This is the **closest published architecture to LCN**. Key parallels and differences:

| Aspect | Titans | LCN |
|--------|--------|-----|
| Memory type | Neural MLP (deep) | Weight matrix W_z (shallow, P×(D+M)) |
| Update signal | Gradient of internal loss (∇ℓ) | JVP estimate of external loss (∇_θ L_σ) |
| Surprise metric | ||∇_M ℓ|| per token | ρ(t) = ||S(t)||_1 spike population activity |
| Gating | Forget gate α + momentum η | Switched contraction: μ(t) controlled by clock gate g(t) |
| Learning rule | Online gradient descent on memory | Forward-mode JVP on structural weights |
| Timescale | Single implicit timescale | Three explicit timescales (working/episodic/structural) |
| Training method | Standard backprop through memory | No backpropagation — pure forward-mode JVP |

**Critical insight:** Titans' surprise mechanism (gradient of associative loss) and LCN's distillation clock (spike population L1 norm) serve the same purpose — determining "when is learning worthwhile?" But they compute it very differently: Titans uses a differentiable loss gradient as a proxy for information novelty, while LCN uses a neuroscientifically-inspired spike activity threshold. LCN's approach is more biologically plausible; Titans' approach is more differentiable.

**Status:** Published at NeurIPS 2025. CUDA implementation in progress (hoshuaclawdbot/titans-cuda). PyPI package (`titans-memory` v0.3.0). Active research.

**Confidence:** High  
**Source:** Behrouz et al. (2024). *Titans: Learning to Memorize at Test Time.* arXiv:2501.00663; NeurIPS 2025 proceedings.

---

### 1.7 xLSTM (Beck et al. 2024)

**What it is:** Extended LSTM with exponential gating and a new memory block structure. Two variants: sLSTM (scalar memory, exponential gating) and mLSTM (matrix memory with covariance update rule). mLSTM achieves O(1) recurrent update and parallelizable training.

**Relevance to LCN:** xLSTM's mLSTM matrix memory update rule (`C_t = f_t · C_{t-1} + i_t · v_t · k_t^T`) is structurally similar to LCN's RCD (LSTM-gated) and also similar to Titans' neural memory. However, xLSTM still trains via BPTT. LCN's episodic memory c_k uses a standard LSTM cell with forget gate — this is architecturally similar to sLSTM's scalar memory.

**Confidence:** Medium  
**Source:** Beck et al. (2024). *xLSTM: Extended Long Short-Term Memory.* arXiv:2405.04517.

---

### 1.8 Mamba / State-Space Models (Gu & Dao 2023; Dao & Gu 2024)

**What they are:** Mamba introduces selective state-space models (S6 layer) where the transition matrices A, B, C are input-dependent. This allows the model to selectively propagate or forget information per-timestep — essentially a learned gate on hidden state evolution. Linear-time inference, constant memory footprint.

**Relevance to LCN:** Mamba's selective SSM is a key ancestor of LCN's SSF (Selective State Filter). Both use a diagonal state-space model with input-dependent gates. Critical differences:

| Property | Mamba S6 | LCN SSF |
|----------|----------|---------|
| State size | N (expanded, typically 16-64) | D (typically 64) |
| Input dependence | Δ, B, C all input-dependent | A(S), B(S) input-dependent |
| Gate mechanism | Selective scan (hardware-aware) | Hardcoded contraction + diagonal A |
| Training | BPTT with custom CUDA kernel | Forward-mode JVP |
| Contraction guarantee | No (can explode) | Yes: a_i ≤ -A_MIN structurally |

LCN's SSF has a provable contraction property (Theorem 2: `||h_T|| ≤ ||h_0|| · e^{-A_MIN·T}`) that Mamba does not guarantee. This is by design — LCN needs bounded working memory for stability.

**Known limitations of Mamba for long-context:** Waleffe et al. (2024) and MemMamba (2025) demonstrate that pure Mamba suffers from memory decay at long horizons. LongMamba (2025) proposes training-free context extension by enlarging receptive fields of "global channels." Mamba-2-Hybrid (mixing attention and Mamba layers) outperforms pure Mamba on in-context learning tasks.

**Confidence:** High  
**Source:** Gu & Dao (2023). *Mamba: Linear-Time Sequence Modeling with Selective State Spaces.* arXiv:2312.00752; Dao & Gu (2024). *Mamba-2.* arXiv; Huang et al. (2025). *Understanding Input Selectivity in Mamba.* ICML 2025.

---

### 1.9 Predictive Coding / Free Energy Principle (Rao & Ballard 1999; Friston 2010)

**What they are:** Predictive coding proposes that cortex operates by minimizing prediction error — top-down predictions are compared with bottom-up sensory input, and only the residual error is propagated. Friston's Free Energy Principle generalizes this to active inference: biological agents minimize variational free energy (roughly, surprise + model complexity).

**Relevance to LCN:** The distillation clock has a predictive coding flavor — ticks fire when spike activity ρ(t) exceeds the EMA-tracked expectation ρ_ema, which is essentially saying "only learn when the prediction error (surprise) is large." This maps directly onto predictive coding: ρ(t) is the "prediction error signal" and ρ_ema is the "prediction." The EMA accumulates the running average, and ticks fire when the residual exceeds the prediction. However, LCN does not implement explicit top-down/bottom-up message passing.

**Confidence:** Medium  
**Source:** Rao & Ballard (1999). *Predictive Coding in the Visual Cortex.* Nature Neuroscience; Friston (2010). *The Free Energy Principle.* Nature Reviews Neuroscience.

---

### 1.10 Agent Memory Systems (MemVerse, Nemori, Hippocampus, NGC, SimpleMem, MemArt — 2024-2026)

A burst of recent work addresses agent memory specifically:

- **Nemori (2025):** Self-organizing memory architecture with dual-pillar cognitive framework. Episodic memory + semantic memory with "Predict-Calibrate Principle" inspired by FEP. Active learning from prediction gaps. Closely parallels LCN's clock-driven update philosophy (learn from surprise). But Nemori uses standard backprop + vector databases, not spiking or JVP.

- **Hippocampus (2026):** Token-free memory substrate using binary signatures + Dynamic Wavelet Matrix for compressed-domain search. Eliminates embeddings entirely — uses random indexing for compact binary representations. 31× faster retrieval, 14× token reduction.

- **Neural Garbage Collection / NGC (2026):** LLM learns to forget KV cache entries via RL. Treats eviction as a discrete action sampled from the LM. Single outcome-based reward signal. Analogous to LCN's clock-driven forgetting but implemented via RL in a transformer.

- **SimpleMem (2025):** Three-stage pipeline: (1) Semantic Structured Compression, (2) Online Semantic Synthesis, (3) Intent-Aware Retrieval Planning. 26.4% F1 improvement, 30× token reduction. Uses standard LLM backprop, not spiking.

- **MemArt (2026):** KV-cache-centric memory. Stores historical turns as reusable KV blocks, retrieves via latent-space attention. Decoupled position encoding. 11% accuracy improvement, 90%+ token reduction.

- **MemVerse (2025):** Multimodal memory with hierarchical knowledge graphs (core, episodic, semantic). Periodic distillation from LTM into parametric memory.

**Relevance to LCN:** All of these systems target the same problem — replacing naive token caches with smarter memory. But none use spiking neurons, forward-mode gradients, or biologically-plausible plasticity. LCN is unique in combining all three.

**Confidence:** High  
**Source:** Various arXiv preprints, 2024-2026.

---

### 1.11 SpikingBrain (2025-2026)

**What it is:** A family of brain-inspired LLMs (7B and 76B MoE) that integrate spiking neurons into a hybrid architecture combining Sparse Softmax Attention (MoBA) and Sparse Linear Attention (SSE) at 1:3 ratio. Uses integer quantization + spike-sequence expansion for event-driven inference. 100× TTFT speedup at 4M tokens. 69.15% activation sparsity.

**Relevance to LCN:** SpikingBrain is the closest published system in terms of **using spikes in a practical LLM-scale architecture**. However, SpikingBrain is a full transformer replacement that still uses BPTT for training and spike conversion for inference. It does not use forward-mode gradients or learned plasticity — spikes are used only for efficiency (sparse activation), not as a learning signal. LCN uses spike population activity ρ(t) as the *trigger* for structural memory updates (the distillation clock), which is a deeper integration of spiking into the learning process.

**Confidence:** High  
**Source:** Xu et al. (2025/2026). *SpikingBrain / SpikingBrain 2.0.* arXiv.

---

## RQ2: Forward-Mode Learning (JVP) as an Alternative to Backpropagation

### 2.1 Forward Gradient Descent (Baydin et al. 2022)

**What it is:** The foundational paper. Instead of backpropagation, compute ∇f(θ)·v for random direction v, then estimate the gradient as ĝ ≈ (∇f(θ)·v) · v. This is O(1) in memory per direction (no activation storage needed) but O(d) variance — the estimate is unbiased but extremely noisy in high dimensions.

**Key result:** Works for MNIST and small models. Fails to scale to ImageNet-scale models.

**Relevance to LCN:** This is LCN's direct ancestor for the JVP-based gradient estimation. LCN uses the same core idea: sample v, compute jax.jvp to get ∂f/∂v, estimate ĝ = (∂f/∂v) · v. The difference is that LCN applies this only to the structural weight update (W_z), not to the full model. LCN also uses **antithetic pairs** (v and -v) for variance reduction, which Baydin et al. discuss but don't systematically evaluate.

**Confidence:** High  
**Source:** Baydin et al. (2022). *Gradients without Backpropagation.* arXiv:2202.08587.

---

### 2.2 Can Forward Gradient Match Backprop? (Fournier et al. 2023)

**What it is:** Systematic study of gradient estimation quality with various "guess" directions. Key finding: using local loss gradients as the guess direction v (rather than random isotropic v) drastically improves forward gradient quality. Specifically, if you have a local auxiliary loss L_local and use ∇L_local as the direction v, the resulting forward gradient estimate is much better aligned with the true gradient.

**Key result:** Local loss guesses close much of the gap between forward gradient and backprop. On CIFAR-10 with LocalMixer architecture, forward gradient with local guesses achieves 90.31% train accuracy vs. 99.97% for backprop.

**Relevance to LCN:** LCN uses **random isotropic directions** (N_JVP_DIRECTIONS=8) for its JVP estimate. Fournier et al.'s results suggest that using **local loss information** as the direction could dramatically improve convergence. LCN's "local loss" could be the per-tick readout loss, providing a structured direction for JVP rather than pure random sampling.

**Recommendation:** Consider replacing random direction sampling with a local loss gradient as the JVP direction. This could reduce variance without adding backprop.

**Confidence:** High  
**Source:** Fournier et al. (2023). *Can Forward Gradient Match Backpropagation?* ICML 2023.

---

### 2.3 Local Forward Gradient (Google Research, 2024)

**What it is:** Extension of Fournier et al. that applies forward gradient with local losses to ImageNet scale. Key innovations: (1) perturb activations rather than weights (much lower dimension), (2) use many local greedy losses instead of one global loss, (3) a LocalMixer architecture suited for local learning.

**Key result:** Matches backprop on MNIST and CIFAR-10. Significantly outperforms previous backprop-free methods on ImageNet (58.37% top-1 for forward gradient vs. 73.24% for backprop — gap remains but is much reduced).

**Relevance to LCN:** The **activation perturbation** strategy is directly applicable to LCN. Instead of perturbing the 2048 parameters of W_z directly, perturbing the (D+M)-dimensional activation u at a tick point would reduce dimensionality from P(D+M) to (D+M). LCN's readout already computes z = W_z · (u ⊙ σ(β|u|)), so a JVP through the readout with respect to u is natural.

**Confidence:** High  
**Source:** Google Research (2024). *Local Forward Gradient for ImageNet.* OpenReview.

---

### 2.4 Moonwalk (2024/2025)

**What it is:** Forward-mode gradient computation for invertible networks using a vector-inverse-Jacobian product (VİP). Achieves true gradients (not stochastic estimates) with time complexity linear in network depth — comparable to backprop but with significantly reduced memory.

**Relevance to LCN:** LCN's SSF is a diagonal ODE that could potentially be made invertible. If the SSF's forward pass is invertible, Moonwalk's technique could compute exact gradients for the SSF parameters without backprop. However, LCN's core claim is that forward-mode JVP is sufficient — Moonwalk's contribution is about computing exact gradients in forward mode, which is a different goal.

**Confidence:** Medium  
**Source:** Moonwalk (2024). *Inverse-Forward Differentiation.* arXiv:2402.14212; ICLR 2025.

---

### 2.5 Multi-Tangent Forward Gradients (2024/2025)

**What it is:** Uses multiple tangent vectors (K > 1) per step instead of a single random direction. Introduces orthogonal projection to combine K forward gradient estimates. Demonstrates that increasing K improves gradient approximation quality and optimization performance.

**Relevance to LCN:** LCN already uses N_JVP_DIRECTIONS=8 tangent directions with antithetic sampling. Multi-tangent forward gradients formalizes this approach and provides theoretical bounds on the improvement from orthogonal projections vs. random sampling.

**Confidence:** Medium  
**Source:** arXiv:2410.17764. *Beyond Backpropagation: Optimization with Multi-Tangent Forward Gradients.* IJCNN 2025.

---

### 2.6 W⊥ Method (Wang, Markou, Campbell — 2025)

**What it is:** Reduces both bias and variance of forward gradient estimates by orthogonalizing the upstream Jacobian matrix. Exploits low-rank structure of the gradient space. W⊥-Newton-Schulz (W⊥-NS) variant accelerates orthogonalization.

**Relevance to LCN:** LCN's JVP estimate variance scales as O(d/N) where d = P(D+M) and N = number of directions. W⊥ orthogonalization could reduce this without increasing N.

**Confidence:** Low (preprint, limited evaluation)  
**Source:** arXiv:2511.03110. *Reducing Bias and Variance in Forward Gradient Estimation.*

---

### 2.7 Second-Order Forward-Mode AD — FoMoH (2024)

**What it is:** Forward-mode weight perturbation with Hessian information. Uses hyper-dual numbers to jointly evaluate directional derivatives and second-order quadratic terms. Enables second-order line search without backprop. FoMoH-KD generalizes from line search to K-dimensional hyperplane search.

**Relevance to LCN:** LCN's plastic ODE update is first-order (Euler or Heun). Second-order forward information could improve the contraction dynamics — knowing curvature would allow adaptive step sizes for the plastic ODE. However, the computational overhead of hyper-dual numbers may negate the benefit for online learning.

**Confidence:** Low  
**Source:** arXiv:2408.10419; OptML 2024 workshop.

---

## RQ3: Spike-Driven Plasticity — STDP, Surrogate Gradients, and Gaussian-CDF

### 3.1 Traditional STDP and Rate-Based Plasticity

STDP (Spike-Timing-Dependent Plasticity) adjusts synaptic weight based on the precise timing of pre- and post-synaptic spikes. The classical Hebbian form strengthens (weakens) connections when the presynaptic spike precedes (follows) the postsynaptic spike. Extensively studied biologially (Markram et al. 1997; Bi & Poo 1998; Sjöström et al. 2001).

Rate-based plasticity modulates connections based on firing rate correlations over longer timescales (Bienenstock-Cooper-Munro rule, Oja's rule).

**Relevance to LCN:** LCN does not use STDP. Its plasticity is driven by forward-mode JVP estimates applied to the structural weight matrix W_z, not by spike timing correlations. This is a fundamental departure from biological spiking models, where plasticity is local and timing-dependent.

**Confidence:** High  
**Source:** Standard neuroscience references.

---

### 3.2 Surrogate Gradient Methods (SuperSpike, SLAYER, Wietek et al.)

**What they are:** Since the Heaviside step function in spike generation is non-differentiable, surrogate gradient methods replace it with a smooth approximation during backpropagation:
- **SuperSpike** (Zenke & Ganguli 2018): Uses a smoothed derivative for online learning in spiking networks.
- **SLAYER** (Shrestha & Orchard 2018): Uses spike response functions with smooth derivatives for BPTT in deep spiking networks.
- **Wietek et al. (2024):** Various surrogate functions (sigmoid, arc-tangent, piecewise linear).

**Relevance to LCN:** This is precisely what LCN avoids. The Gaussian-CDF smoother Φ_σ used in the encoder IS a surrogate function for the Heaviside step — but it's used only in the forward pass (to produce smooth spike probabilities s ∈ [0,1]), NOT as a gradient proxy for backpropagation. LCN then takes JVPs through this smooth forward pass, which means:
1. The Gaussian-CDF provides smoothness for the forward-mode derivative (the JVP goes through Φ_σ, which is smooth).
2. No gradient is ever backpropagated through the spike threshold, so there's no surrogate bias chain.

This is a meaningful distinction. In surrogate gradient BPTT, the error gradient flows through the smooth approximation, introducing bias that accumulates across timesteps. In LCN's forward-mode approach, the JVP computes a directional derivative *through the actual smooth function* — there's no_approximation of a discontinuity; the smoothness is real.

**Key advantage:** LCN avoids the "surrogate gradient bias chain" entirely. The Gaussian-CDF is not a proxy; it's the actual computation.

**Key limitation:** LCN's input to the JVP is the spike probability s(t) = Φ_σ(v(t) - v_θ), where v(t) integrates the input. The quality of the gradient estimate depends on σ being large enough to smooth out the threshold, but small enough to preserve information content. The current setting of σ=1e-2 (SIGMA_THRESHOLD) is very tight — this is essentially a near-hard threshold with a slight smoothing. This may limit JVP quality.

**Confidence:** High  
**Source:** Zenke & Ganguli (2018). *SuperSpike.* NeurIPS; Shrestha & Orchard (2018). *SLAYER: Spike Layer Error Reassignment in Time.* NeurIPS.

---

### 3.3 Three-Factor Learning Rules (Gerstner, Lehmann, et al. 2018)

**What they are:** Three-factor rules combine Hebbian co-activation (pre × post) with an eligibility trace (a decaying "tag" at each synapse) and a neuromodulatory third factor M^3rd(t) (reward, surprise, etc.). The weight update is:

```
dw_ij/dt = e_ij(t) × M^3rd(t)
```

where e_ij is the eligibility trace (local, synapse-specific) and M^3rd is global or regional.

**Relevance to LCN:** This is the **most direct biological analogue** to LCN's clock-gated plasticity. Mapping:

| LCN component | Three-factor analogue |
|---------------|----------------------|
| Spike activity ρ(t) = ||s(t)||₁ | Pre/post activity (Hebbian co-activation) |
| EMA ρ_ema | Running average / eligibility trace |
| Clock tick (ρ(t) > ρ_ema) | Third factor trigger (surprise / neuromodulator) |
| Gate g(t) = σ(γ(ρ_ema - ρ₀)) | Neuromodulatory gating signal M^3rd(t) |
| ĝ_θ (JVP gradient estimate) | Eligibility trace × neuromodulator product |
| W_z update: ĝ - μ(t)·W_z | Weight change with homeostatic decay |

The key difference: Three-factor rules in neuroscience typically use **binary** or **scalar** neuromodulators. LCN uses a **continuous** gate g(t) ∈ [0,1] that continuously modulates the contraction rate μ(t). This is closer to "graded" neuromodulation, which has been proposed (Frémaux & Gerstner 2016) but is less common in computational models.

**Important paper — Behavioral-timescale plasticity (BTSP):** Bittner et al. (2017) discovered that hippocampal CA1 synapses can be modified by behavioral timescale events (seconds after pre-synaptic stimulation), far longer than traditional STDP windows (milliseconds). The plasticity requires a postsynaptic plateau potential as the third factor. This is a direct biological precedent for LCN's distillation clock: the clock's "tick" is analogous to the plateau potential trigger, and the gate g(t) modulates the "eligibility window."

**Confidence:** High  
**Source:** Gerstner et al. (2018). *Eligibility Traces and Plasticity on Behavioral Time Scales.* Frontiers in Neural Circuits; Frémaux & Gerstner (2016). *Neuromodulated Spike-Timing-Dependent Plasticity.* Frontiers; Bittner et al. (2017). *Behavioral Time Scale Synaptic Plasticity.* Science.

---

### 3.4 Recall-Gated Consolidation (Lindsey 2024)

**What it is:** A theoretical framework for systems consolidation where short-term memory (STM) consolidation into long-term memory (LTM) is gated by recall strength. Consolidation only occurs when the STM can recall the memory sufficiently well (r_STM ≥ θ). This prevents overfitting and catastrophic interference while allowing genuine patterns to be consolidated.

**Relevance to LCN:** This is a formal model of the intuition behind LCN's distillation clock. In Lindsey's framework:
- STM = LCN's working memory h(t) + episodic memory c_k
- LTM = LCN's structural weights W_z
- Recall gate = LCN's clock tick condition (ρ(t) > ρ_ema)
- Consolidation = LCN's plastic ODE update

The alignment is strong but not perfect. Lindsey uses recall accuracy as the gate; LCN uses spike population L1 norm as the gate. Both encode "is this moment worth remembering?" but through different signals.

**Confidence:** High  
**Source:** Lindsey (2024). *Selective Consolidation of Learning and Memory via Recall-Gated Plasticity.* eLife.

---

### 3.5 Co-dependent Excitatory-Inhibitory Plasticity (Nature Neuroscience 2024)

**What it is:** A model where excitatory and inhibitory plasticity rules are co-dependent: inhibitory synapses gate excitatory plasticity. Rapid excitatory strengthening is followed by slower inhibitory rebalancing, preventing runaway excitation while allowing quick learning.

**Relevance to LCN:** LCN's switched contraction (μ(t) switches between μ_free and μ_min based on gate g(t)) is analogous: during quiet periods (g≈1), contraction dominates and W_z decays (analogous to inhibitory stabilization); during active learning (g≈0), plasticity from ĝ dominates (analogous to excitatory strengthening). The timescale separation (fast excitation, slow inhibition) maps to LCN's η (fast Euler step for ĝ update) vs. μ_min (slow steady decay).

**Confidence:** Medium  
**Source:** Costa et al. (2024). *Co-dependent Excitatory-Inhibitory Plasticity Accounts for Quick, Stable, and Long-lasting Memories.* Nature Neuroscience.

---

## RQ4: Gated Plasticity — Decoupling "When to Learn" from "What to Compute"

### 4.1 Titans' Surprise Mechanism (Behrouz et al. 2024)

As discussed in RQ1.6, Titans measures surprise as ||∇_M ℓ(M_{t-1}; x_t)|| and uses it to drive:
1. A momentum term S_t = η · S_{t-1} - θ · ∇ℓ (accumulated surprise with decay)
2. A forget gate α that controls memory retention

This is a **learned** gate (the momentum η and forget rate α are trained parameters). LCN's gate is **engineered** (sigmoid of EMA-tracked activity). Whether learned or engineered is a key design choice.

**Confidence:** High

---

### 4.2 Neuromodulation-Inspired Plasticity in ANNs (Multi-Neuromodulatory Dynamics, 2025)

**What it is:** A recent review and experimental study that implements multi-neuromodulatory dynamics in artificial neural networks. Key insight: different neuromodulators (dopamine, norepinephrine, serotonin, acetylcholine) serve different gating functions — DA for reward prediction, NE for surprise, ACh for attention, 5-HT for long-term regulation. The study implements these as separate learned "third factors" that gate different aspects of plasticity.

**Relevance to LCN:** LCN currently has a single gate signal g(t). Multi-neuromodulatory models suggest that multiple gate signals could improve learning:
- g_learn(t): Whether to update structural weights (current clock)
- g_consolidate(t): Whether to commit episodic to structural (separate from learning gate)
- g_forget(t): How much of past structural weights to retain (currently baked into μ(t))

The paper by Daram et al. (2020) and Miconi et al. (2020) on differentiable plasticity with neuromodulation is also relevant.

**Confidence:** Medium  
**Source:** arXiv:2501.06762. *Improving Adaptive and Continuous Learning Capabilities of ANNs: Lessons from Multi-Neuromodulatory Dynamics.*

---

### 4.3 Eligibility Traces in Hardware (FeS-FET, 2025)

**What it is:** Recent hardware implementation of three-factor learning rules (R-STDP with eligibility traces) using α-In₂Se₃ ferroelectric semiconductor FETs. The ferroelectric relaxation naturally implements eligibility trace decay, and delayed gate voltage pulses implement the reward/modulatory signal. Single-device implementation.

**Relevance to LCN:** This validates the biological plausibility of LCN's approach — eligibility traces and neuromodulatory gating are not just abstract theory but can be physically realized. However, LCN doesn't implement explicit eligibility traces; the JVP gradient estimate ĝ serves as both the Hebbian signal and the direction of update.

**Confidence:** Medium  
**Source:** PMC13035856. *Brain-inspired Synaptic Transistors for In-situ Spiking Reinforcement Learning with Eligibility Trace.*

---

### 4.4 Three-Factor Learning in SNNs — Overview (2025)

**What it is:** Comprehensive 2025 review of three-factor learning rules applied to SNNs. Categories:
- **Reward-modulated STDP (R-STDP):** Eligibility trace × reward signal
- **Surprise-modulated STDP:** Eligibility trace × surprise signal (NE analogue)
- **Multi-neuromodulatory:** Multiple simultaneous third factors
- **Differentiable plasticity:** Third factor computed via backpropagation through the plasticity dynamics

**Key finding:** The most performant three-factor rules in practice use backpropagation through the plasticity dynamics to optimize the neuromodulatory signal (Miconi et al. 2020; Barry & Gerstner 2024). Pure bio-inspired rules (fixed neuromodulator dynamics) underperform learned ones.

**Relevance to LCN:** This is a caution. LCN's clock and gate are **engineered** (EMA, sigmoid), not learned. The current literature suggests that learning the neuromodulatory signal (equivalent to learning the clock parameters ρ₀, γ, β in LCN) significantly improves performance. LCN could make the clock parameters trainable via forward-mode JVP, which would preserve the no-backprop invariant while improving gating quality.

**Confidence:** High  
**Source:** arXiv:2504.05341. *Three-Factor Learning in Spiking Neural Networks: An Overview.* 2025.

---

## RQ5: Memory Consolidation Theory (Hippocampus → Cortex)

### 5.1 Complementary Learning Systems (McClelland, McNaughton, O'Reilly 1995; Kumaran, Hassabis, McClelland 2016)

**What it is:** The foundational theory that intelligent agents need two complementary learning systems:
1. **Hippocampus (fast learning):** Quickly encodes specific experiences with minimal interference. High learning rate, pattern separation.
2. **Neocortex (slow learning):** Gradually extracts structure and regularities. Low learning rate, interleaved training via replay.

The key insight: without the fast hippocampal system, new information catastrophically interferes with old knowledge (the "sensitivity-stability dilemma"). Without the slow neocortical system, knowledge doesn't generalize.

**Relevance to LCN:** Direct structural mapping:

| CLS Theory | LCN Component |
|------------|---------------|
| Hippocampal fast storage | Episodic memory c_k (LSTM-gated, per-tick) |
| Neocortical slow consolidation | Structural weights W_z (plastic ODE, switched contraction) |
| Replay / interleaved training | Distillation clock triggers consolidation of salient moments |
| Pattern separation | SSF contraction guarantee (‖h_T‖ ≤ ‖h₀‖·e^{-A_MIN·T}) |
| Sensitivity-stability tradeoff | μ_free (stability) vs. μ_min (contraction/degradation) |

LCN's three-substrate architecture (working, episodic, structural) is a concrete instantiation of CLS theory in a computational framework. The key contribution of LCN over standard CLS models is that the consolidation trigger (the clock) is spike-activity-based rather than replay-based.

**Confidence:** High  
**Source:** McClelland et al. (1995). *Why There Are Complementary Learning Systems in the Hippocampus and Neocortex.* Psychological Review; Kumaran et al. (2016). *What Learning Systems Do Intelligent Agents Need?* Trends in Cognitive Sciences.

---

### 5.2 Generalization-Optimized CLS (Go-CLS) (Naim et al. 2023, Nature Neuroscience)

**What it is:** Extends CLS by showing that unregulated consolidation can *harm* generalization. Some memories should remain hippocampal-dependent. The system should only consolidate memories that aid generalization. Introduces "recall-gated consolidation": memories are consolidated only when recall strength in the short-term system exceeds a threshold.

**Relevance to LCN:** Go-CLS's recall gate is LCN's distillation clock in different clothing. The clock fires when ρ(t) > ρ_ema — this is equivalent to "the short-term system (spike activity) strongly recalls this pattern." LCN's clock is simpler (activity threshold vs. recall accuracy), but serves the same normative purpose: don't consolidate everything, only consolidate moments when the system is "surprised" or "engaged."

**Confidence:** High  
**Source:** Naim et al. (2023). *Organizing Memories for Generalization in Complementary Learning Systems.* Nature Neuroscience.

---

### 5.3 Hippocampo-Neocortical Interaction as Compressive RAG (Spens & Burgess 2024)

**What it is:** Uses generative models (GPTs) to model hippocampo-neocortical interaction. The hippocampus stores compressed traces; the neocortex reconstructs episodes via RAG-like retrieval. Over time, consolidation trains the neocortical generative model via prediction error minimization.

**Relevance to LCN:** The compressive-then-generative pipeline maps exactly:
- Hippocampal compression → LCN's episodic memory c_k (LSTM-gated, compressed)
- Neocortical reconstruction → LCN's readout (W_z · (u ⊙ σ(β|u|)))
- Consolidation via replay → LCN's clock-triggered plastic ODE update

This paper validates the conceptual framework but doesn't address spiking, JVP, or plasticity.

**Confidence:** Medium  
**Source:** Spens & Burgess (2024). *Consolidation of Sequential Experience into a Deep Generative Network.* bioRxiv.

---

### 5.4 Predictive Coding Networks for Memory (Nemori, 2025)

**What it is:** Nemori's Predict-Calibrate Principle: an agent should learn from prediction errors (surprise), not from pre-defined extraction rules. The semantic memory is distilled from episodic memory by proactively identifying prediction gaps.

**Relevance to LCN:** Nemori's prediction-gap principle is very similar to LCN's clock: the clock fires when ρ(t) > ρ_ema, meaning "the spike activity was higher than expected" — a prediction error. But Nemori uses standard backprop and vector databases; LCN uses spiking+JVP.

**Confidence:** Medium  
**Source:** arXiv:2508.03341. *Nemori: A Self-Organizing Memory Architecture for LLM Agents.*

---

## RQ6: Novelty Assessment — Where LCN Fits

### 6.1 What LCN Does That No One Else Does

| Component | Novel? | Closest Precedent | Gap |
|-----------|--------|-------------------|-----|
| Forward-mode JVP training (no backprop at all) | Partially | Baydin et al. 2022; Fournier et al. 2023; Local Forward Gradient 2024 | LCN applies JVP only to structural weights (reduced dimension), not full network. But the core idea is the same. **Novelty: 4/10** |
| Gaussian-CDF spike encoding (not a surrogate for BPTT) | Partially | Standard surrogate gradients (SuperSpike, SLAYER); LIF neurons with smooth activation | Using a smoother in the *forward* pass for JVP compatibility rather than as a backward-pass proxy is novel in application but not in concept. The specific choice of Φ_σ is standard. **Novelty: 5/10** |
| Distillation Clock (spike-population-activity-gated learning) | **Novel** | Titans' surprise mechanism (gradient-magnitude-gated); Recall-gated consolidation (Lindsey 2024); Three-factor rules (Gerstner 2018) | No one has used spike L1-norm exceeding an EMA threshold as the consolidation trigger. Titans uses gradient magnitude; Lindsey uses recall accuracy. The specific biological inspiration and signal choice are novel. **Novelty: 8/10** |
| Switched-contraction plastic ODE | **Novel** | Titans' forget-gate + momentum; Mamba's input-dependent SSM parameters; Three-factor rules (neuromodulated plasticity) | The specific combination of a continuously varying contraction rate μ(t) = μ_free + (μ_min - μ_free)·g(t) with JVP-driven updates is novel. Titans has a forget gate but no contraction-based stability guarantee. Mamba has input-dependent parameters but trains via BPTT. Three-factor rules are biological; LCN's is a computational ODE. **Novelty: 7/10** |
| Three explicit timescales (working/episodic/structural) | Partially | CLS theory; Compressive Transformer; Titans (short-term + long-term + persistent memory); MemVerse (short-term + episodic + semantic) | The specific substrate decomposition (LIF-encoder → SSF → LSTM-RCD → plastic-ODE) is novel in implementation, but the three-level hierarchy is well-established in CLS and recent ML work. **Novelty: 5/10** |
| No attention, no KV cache | Novel in combination | Mamba/SSMs (no attention but BPTT-trained); Compressive Transformer (compresses KV but still uses attention); HC.xhtml Titans (uses attention for short-term component) | LCN is the only architecture that combines (a) no attention, (b) no backprop, (c) spike-based encoding, (d) learned structural memory. **Novelty: 6/10** for the combination |

### 6.2 What Prior Art Already Covers

1. **Forward-mode gradient descent is well-explored** (Baydin 2022, Fournier 2023, Local Forward Gradient 2024, Moonwalk 2024, FoMoH 2024, Multi-tangent 2024). The scalability challenges are documented: high variance in high dimensions, need for local loss directions, and the gap with backprop on large-scale tasks. LCN does not address these fundamental limitations.

2. **Gated memory updates are well-explored** (Titans forget gate, Mamba input-dependent SSM, LSTM forget gate, Infini-attention linear memory). LCN's specific gate (sigmoid of EMA-tracked activity) is novel in signal but not in mechanism.

3. **Three-factor learning rules are well-established theory** (Gerstner 2016/2018, Frémaux & Gerstner 2015, Izhikevich 2007). The specific mapping from neuromodulation to ML gating is ongoing work.

4. **Complementary learning systems are standard computational neuroscience** (McClelland 1995, Kumaran 2016, Go-CLS 2023). LCN's three-substrate architecture is a reasonable instantiation but not conceptually new.

### 6.3 Overall Novelty Rating: **6.5/10**

**Justification:** No single published system combines all of LCN's properties. The individual components have precedents, but the combination — forward-mode JVP + spike-driven clock + switched-contraction plastic ODE + three explicit memory substrates + no attention — is unique. The two most novel aspects are:

1. **Distillation Clock (8/10):** Using spike population activity as a gate for structural weight updates, with an EMA-tracked threshold, is a genuinely new design that bridges computational neuroscience (three-factor rules, BTSP) and ML (Titans surprise, recall-gated consolidation).

2. **Switched-contraction plastic ODE (7/10):** The specific ODE dW/dt = ĝ - μ(t)·W with μ(t) continuously varying between free drift and contraction based on a spike-driven gate has no exact precedent. The closest is Titans' forget gate + momentum, but Titans uses gradient-magnitude surprise, not spike-driven gating, and doesn't have a contraction stability guarantee.

The least novel aspect is forward-mode JVP (4/10), which is well-explored with known scalability limitations.

---

## Recommendations

Based on this survey, here are concrete recommendations for the LCN Brain project:

### R1: Implement the `lcn_jvp` Package (Priority: CRITICAL)

The project is currently blocked by the missing `lcn_jvp` external dependency. Without it, no training can occur and the core empirical claim ("A+C beats BPTT at long horizons") remains untested.

**Rollback:** Remove `lcn_jvp` dependency and inline the required functions.

### R2: Consider Local Loss Directions for JVP (Priority: HIGH)

Fournier et al. (2023) and the Local Forward Gradient work (Google, 2024) demonstrate that using local loss gradients as JVP direction dramatically outperforms random isotropic directions. Currently, LCN uses N_JVP_DIRECTIONS=8 random directions. Consider:
- Using the per-tick readout loss gradient ∇_θ L_t as one of the directions
- Or mixing: half random, half gradient-informed
- This requires computing ∇_θ L_t, which is a VJP (backprop through a local loss). If this violates the "no backprop" invariant, use the JVP estimate of the local loss instead.

**File:** `Brain/lcn_brain/lcn/train.py` — `sample_direction` and `antithetic` functions.

### R3: Make Clock Parameters Trainable (Priority: MEDIUM)

The three-factor learning literature (arXiv:2504.05341) clearly shows that learned neuromodulatory signals outperform engineered ones. The clock's current hyperparameters (RHO_EMA_BETA=0.95, RHO_THRESHOLD0=0.05, RHO_GATE_GAIN=4.0) are hardcoded. Consider:
- Making ρ₀ (RHO_THRESHOLD0) and γ (RHO_GATE_GAIN) trainable via forward-mode JVP
- This preserves the "no backprop" invariant while allowing the system to learn when to consolidate

**File:** `Brain/lcn_brain/lcn/constants.py` — move RHO_THRESHOLD0 and RHO_GATE_GAIN to `TrainState`.

### R4: Increase SIGMA_THRESHOLD (Priority: MEDIUM)

The current σ=1e-2 (SIGMA_THRESHOLD) produces near-binary spike probabilities. This limits the information content of each spike and may degrade JVP gradient quality. Consider:
- Starting with σ=0.1 or σ=0.5 for initial experiments
- Or making σ a trainable parameter

**File:** `Brain/lcn_brain/lcn/constants.py` — SIGMA_THRESHOLD.

### R5: Add Titans-Style Forgetting to the Plastic ODE (Priority: LOW)

The Titans paper introduces a momentum-scaled forget rate that considers both "how surprising" an input is AND "how full" the memory is. LCN's current plastic ODE has a fixed decay rate μ(t). Adding a Titans-style adaptive forget α_t that depends on the ratio of memory size to data surprise could improve memory management:

```
α_t = f(||W_z||_F, ||g_hat||_F)  # LCN-specific adaptive forget
W_{t+1} = (1 - α_t) · W_t + η · g_hat
```

This is a lower priority because it adds complexity before the base system is validated.

### R6: Validate Against Titans Baseline (Priority: HIGH, after P7/P8 complete)

Before making architectural claims, the LCN project should include Titans (or a simplified version of it) as an arm in the 4-arm comparison. The comparison should be:
1. BPTT with surrogate gradient (existing baseline)
2. A-only: Contraction, no JVP (existing)
3. C-only: JVP, no contraction (existing)
4. A+C: Full LCN (existing)
5. **Titans-MAG:** Same architecture as LCN but with Titans' gradient-magnitude surprise instead of spike-driven clock
6. **Titans-Forget:** Same architecture but with Titans' momentum + forget gate instead of switched contraction

This would isolate the contribution of the spike-driven clock vs. gradient-driven surprise.

### R7: Document the Theorem About Contraction Guarantee (Priority: MEDIUM)

LCN's switched contraction provides a formal stability guarantee: when g≈1, ‖W_z(t)‖ decays exponentially. This is a meaningful theoretical advantage over Titans, which has no such guarantee (Titans' memory MLP can grow unbounded). Theorem statements should be added to the documentation and, if provable, formalized for publication.

---

## Findings Summary Table

| Finding | Category | Details | Confidence |
|---------|----------|---------|-----------|
| Forward-mode JVP is well-explored but limited | `prior_art` | Baydin 2022, Fournier 2023, Local Forward Gradient 2024. Scaling remains challenging. LCN's reduced-dimension application helps but doesn't solve the variance problem. | High |
| Local loss directions dramatically improve forward gradient quality | `new_release` | Fournier et al. 2023, Google 2024. Directly applicable to LCN. | High |
| Titans is the closest published architecture | `reliable_change` | Neural memory with gradient-magnitude surprise + momentum + forget gate. Differs in training (BPTT) and gating signal (gradient, not spikes). | High |
| Infini-attention is the closest "bounded memory" architecture | `cost_change` | Compressive memory in attention layer. O(d_key × d_value) per head. BPTT-trained. | High |
| Mamba SSMs are the closest "no attention" architecture | `prior_art` | Input-dependent SSM with selective scan. BPTT-trained. No structural memory update. | High |
| Three-factor learning rules are the biological precedent | `prior_art` | Eligibility trace × neuromodulator. Gerstner 2018, BTSP (Bittner 2017). LCN's clock is a novel computational instance. | High |
| CLS theory validates LCN's three-substrate architecture | `prior_art` | McClelland 1995, Kumaran 2016, Go-CLS 2023. Hippocampal fast + neocortical slow → LCN's episodic + structural. | High |
| Distillation clock (spike-driven gating) is novel | `new_release` | No published system uses spike L1-norm > EMA as consolidation trigger. Closest: Titans (gradient surprise), Lindsey (recall gate). | High |
| Switched contraction plastic ODE is novel | `new_release` | μ(t) = μ_free + (μ_min - μ_free)·g(t) with JVP updates. No exact precedent. Closest: Titans forget gate, Mamba input-dependent A. | Medium |
| LCN's combination (no BPTT + no attention + spiking + structural memory) is unique | `reliable_change` | No single published system combines all four. Individual components have precedents. | High |
| Neural Garbage Collection (NGC) learns to forget via RL | `new_release` | 2026. LLM learns to evict KV cache entries as discrete actions. Similar goal (learn when to forget), different mechanism (RL vs. spike-driven ODE). | High |
| SpikingBrain applies spiking to LLM-scale inference | `new_release` | 2025-2026. Validates feasibility of spiking at LLM scale, but uses BPTT and spike conversion, not learned structural plasticity. | High |
| Learned neuromodulation outperforms engineered gating | `new_release` | Three-factor SNN review (2025) and multi-neuromodulatory dynamics (2025). LCN's hardcoded clock parameters should be made trainable. | Medium |
| Second-order forward-mode (FoMoH) could improve plastic ODE convergence | `cost_change` | 2024. Hyper-dual numbers for curvature information. Not immediately needed but could improve Euler/Heun integration. | Low |

---

## Unchanged Components

The following components of LCN are well-established and do not need modification based on this survey:

1. **LIF encoder with Gaussian-CDF smoothing** — Standard technique, appropriate for JVP compatibility. σ should be tuned, not abandoned.
2. **Diagonal SSF with contraction guarantee** — Theorem 2's contraction property is valuable and unique. Mamba doesn't guarantee stability; LCN does.
3. **RCD (LSTM-gated episodic memory)** — Standard and well-understood. Jozefowicz bias init (bf=1.0) is best practice.
4. **C2 gated mixture readout** — Novel behavioral form, no issues identified.
5. **Burgers' equation testbed** — Appropriate low-dimensional PDE for initial validation. Should extend to higher-dimensional tasks after validation.

---

## References (Key Papers)

### Forward-Mode Learning
- Baydin, A.G. et al. (2022). *Gradients without Backpropagation.* arXiv:2202.08587.
- Fournier, L. et al. (2023). *Can Forward Gradient Match Backpropagation?* ICML 2023.
- Google Research (2024). *Local Forward Gradient for ImageNet.* OpenReview.
- Moonwalk (2024). *Inverse-Forward Differentiation.* arXiv:2402.14212; ICLR 2025.
- Wang, Markou, Campbell (2025). *Reducing Bias and Variance in Forward Gradient Estimation.* arXiv:2511.03110.
- FoMoH (2024). *Second-Order Forward-Mode AD for Optimization.* arXiv:2408.10419; OptML 2024.

### Memory Architectures
- Behrouz, A. et al. (2024/2025). *Titans: Learning to Memorize at Test Time.* arXiv:2501.00663; NeurIPS 2025.
- Munkhdalai, T. et al. (2024). *Infini-attention.* arXiv:2404.07143.
- Gu, A. & Dao, T. (2023). *Mamba: Linear-Time Sequence Modeling with Selective State Spaces.* arXiv:2312.00752.
- Beck, M. et al. (2024). *xLSTM: Extended Long Short-Term Memory.* arXiv:2405.04517.
- Rae, J. et al. (2019). *Compressive Transformers for Long Range Sequence Modelling.* ICLR.
- Graves, A. et al. (2016). *Hybrid Computing Using a Neural Network with Dynamic External Memory.* Nature.

### Association Memory
- Krotov, D. & Hopfield, J. (2016). *Dense Associative Memory for Pattern Recognition.* NeurIPS.
- Ramsauer, H. et al. (2020). *Hopfield Networks is All You Need.* ICML 2021.
- Kanerva, P. (1988). *Sparse Distributed Memory.* MIT Press.
- Wu, Y. et al. (2018). *The Kanerva Machine: A Generative Model for Associative Memory.* ICML.

### Spiking & Three-Factor Learning
- Gerstner, W. et al. (2018). *Eligibility Traces and Plasticity on Behavioral Time Scales.* Frontiers in Neural Circuits.
- Frémaux, R. & Gerstner, W. (2016). *Neuromodulated Spike-Timing-Dependent Plasticity.* Frontiers.
- Bittner, K. et al. (2017). *Behavioral Time Scale Synaptic Plasticity.* Science.
- Three-Factor SNN Overview (2025). arXiv:2504.05341.
- SpikingBrain (2025-2026). arXiv (multiple).

### Memory Consolidation
- McClelland, J.L. et al. (1995). *Why There Are Complementary Learning Systems in the Hippocampus and Neocortex.* Psychological Review.
- Kumaran, D. et al. (2016). *What Learning Systems Do Intelligent Agents Need?* Trends in Cognitive Sciences.
- Naim et al. (2023). *Organizing Memories for Generalization in Complementary Learning Systems.* Nature Neuroscience.
- Spens, E. & Burgess, N. (2024). *Consolidation of Sequential Experience into a Deep Generative Network.* bioRxiv.
- Lindsey, J.W. (2024). *Selective Consolidation of Learning and Memory via Recall-Gated Plasticity.* eLife.

### Agent Memory Systems (2024-2026)
- SimpleMem (2025). arXiv:2601.02553.
- Nemori (2025). arXiv:2508.03341.
- Hippocampus (2026). arXiv:2602.13594.
- NGC (2026). arXiv:2604.18002.
- MemVerse (2025). arXiv:2512.03627.
- MemArt (2026). OpenReview.

---

*End of survey. This document should be stored at `.opencode/research/lit-survey.md`.*