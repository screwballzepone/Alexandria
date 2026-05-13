# LCN Brain — Claude Context File

> **Generated:** 2026-04-26 | **Total:** 26 files, ~2,911 lines Python + 41 lines bash CI

---

## 1. PROJECT MAP (max 3 lines)

**What this is:** A JAX/Flax reference implementation of the Language Cognition Network — a spiking neural architecture that replaces attention with forward-mode autodiff, plastic memory, and a Burgers' equation testbed.

**What's done:** P0–P6 core modules implemented (encoder, SSF, clock, RCD, readout, plastic), constants defined, diagnostics logger, Burgers' PDE solver + 4-arm config, CI invariant grep script. All 49 acceptance/invariant/unit tests written.

**What's missing:** JAX/flax/lcn_jvp not installed (0 tests pass). P7 training loop depends on external `lcn_jvp` package (not found). P8 testbed harness is a skeleton — `run_arm()` in `arms.py` has placeholder return, no actual forward-pass integration. No `ActiveSet` dataclass wired to `train.py`. No 4-arm comparison plot.

---

## 2. ARCHITECTURE (max 10 lines)

```
x(t) → [Spike Encoder] → S(t) → [SSF] → h(t) ──→ [Clock] ──→ h(τ_k) → [RCD] → c_k
        LIF+Gaussian-CDF     diag-sel ODE         EMA-tick       LSTM-gated
                                      │                │                    │
                                      └─ g(t) ────────→ [Plastic ODE] → W_z(t)
                                                              │
                                      h(t), c_k ────→ [C2 Readout] ←───┘
                                                              │
                                                           z(t)

No attention. No KV cache. Forward-mode JVP — no surrogate gradient bias chain.
```

**Three memory substrates:**

| Substrate | Symbol | Timescale | Plastic? | Module |
|-----------|--------|-----------|----------|--------|
| Working | h(t) | 1–10 steps | No (state) | ssf.py |
| Episodic | c_k | 10²–10³ ticks | No (state) | rcd.py |
| Structural | W_z(t) | ≫10³ steps | **Yes** (plastic) | plastic.py |

**Key insight:** Forward-mode JVP (jax.jvp) estimates the gradient of the smoothed loss ∇_θ L_σ without backpropagating through surrogate gradients. This avoids the bias chain that plagues surrogate-gradient BPTT. The plastic ODE uses switched contraction: weights decay when gate g(t)≈1 (quiet) and drift freely when g(t)≈0 (active).

---

## 3. FILE MANIFEST

| File | Lines | Purpose | Key Exports | Status |
|------|-------|---------|-------------|--------|
| `pyproject.toml` | 32 | Package config | deps: jax, jaxlib, flax, numpy, pyarrow; dev: pytest, matplotlib | DONE |
| `README.md` | 65 | Project overview | Architecture diagram, quickstart, invariants | DONE |
| `CI/grep_no_grad.sh` | 41 | I1 invariant enforcement | Grep for jax.grad/vjp/jacrev/Heaviside | DONE |
| `lcn/__init__.py` | 5 | Package docstring | — | DONE |
| `lcn/constants.py` | 33 | All architectural constants | N_ENC, D, M, P, A_MIN, MU_MIN, BETA_0, N_JVP_DIRECTIONS… | DONE |
| `lcn/types.py` | 91 | State dataclasses | `State`, `EncoderState`, `SSFState`, `RCDState`, `ClockState`, `PlasticState`, `Window`, `TickRecord` | DONE |
| `lcn/encoder.py` | 125 | LIF encoder + Gaussian-CDF surrogate | `encoder_step`, `encode_window`, `init_encoder`, `check_i_enc_1`, `check_i_enc_2` | DONE |
| `lcn/ssf.py` | 123 | Selective State Filter (diagonal ODE) | `SSFParams(nn.Module)`, `ssf_step`, `run_ssf`, `l21_penalty` | NEEDS_FIX |
| `lcn/clock.py` | 108 | Distillation Clock (EMA-triggered ticks) | `clock_init`, `clock_step`, `run_clock`, `gate_value` | DONE |
| `lcn/rcd.py` | 88 | Recurrent Context Distiller (LSTM-gated) | `RCDCell(nn.Module)`, `init_rcd`, `rcd_step` | DONE |
| `lcn/readout.py` | 107 | C2 gated mixture readout | `PlasticReadout(nn.Module)`, `pack_u`, `readout_forward`, `readout_pullback`, `_calibrated_beta` | DONE |
| `lcn/plastic.py` | 114 | Plastic-weight ODE (switched contraction) | `gate_value`, `_mu_effective`, `plastic_euler_step`, `plastic_heun_step` | DONE |
| `lcn/train.py` | 241 | A+C training loop (JVP estimator) | `TrainState`, `init_train_state`, `train_one_tick`, `train_one_tick_heun` | KNOWN_GAP |
| `lcn/diagnostics.py` | 203 | Tick logger to Parquet + sanity checks | `DiagnosticsWriter`, `compute_diagnostics`, `print_tick_summary`, `sanity_check` | DONE |
| `lcn/testbed/__init__.py` | 1 | Testbed package docstring | — | DONE |
| `lcn/testbed/burgers.py` | 199 | Burgers' PDE solver + 4-arm configs | `simulate`, `sample_ic`, `rate_code`, `loss_mse`, `ArmConfig`, `ALL_ARMS` | DONE |
| `lcn/testbed/encodings.py` | 36 | Encoding strategy wrappers | `rate_code`, `identity_code`, `NX` | DONE |
| `lcn/testbed/arms.py` | 124 | 4-arm harness (skeleton) | `run_arm`, `compare_arms` | KNOWN_GAP |
| `tests/__init__.py` | 1 | Test suite init | — | DONE |
| `tests/test_encoder.py` | 171 | Encoder acceptance + invariant + unit tests | `TestEncoderAcceptance`, `TestEncoderInvariants`, `TestEncoderStep`, `TestEncoderInit` | DONE |
| `tests/test_clock.py` | 180 | Clock acceptance + invariant + unit tests | `TestClockAcceptance`, `TestClockInvariants`, `TestClockStep`, `TestClockInit`, `TestClockRun` | DONE |
| `tests/test_ssf.py` | 170 | SSF acceptance + invariant + unit tests | `TestSSFAcceptance`, `TestSSFInvariants`, `TestSSFStep`, `TestSSFRun` | DONE |
| `tests/test_rcd.py` | 173 | RCD invariant + cell + step + multi-tick tests | `TestRCDInvariants`, `TestRCDCell`, `TestRCDStep`, `TestRCDInit`, `TestRCDMultipleTicks` | DONE |
| `tests/test_plastic.py` | 251 | Plastic ODE invariant + euler + heun + gate tests | `TestPlasticInvariants`, `TestPlasticEulerStep`, `TestPlasticHeunStep`, `TestGateValue`, `TestMuEffective` | DONE |
| `tests/test_readout.py` | 199 | Readout invariant + module + forward + pullback tests | `TestReadoutInvariants`, `TestReadoutModule`, `TestReadoutForward`, `TestReadoutPullback`, `TestPackU`, `TestCalibratedBeta` | DONE |
| `tests/test_burgers.py` | 269 | Burgers' PDE + energy + IC + rate code + arms tests | `TestBurgersPDE`, `TestBurgersEnergy`, `TestBurgersSampleIC`, `TestBurgersRateCode`, `TestBurgersLoss`, `TestBurgersArms` | DONE |

---

## 4. CONSTANTS

All in `lcn/constants.py` line 11–33. Treat as immutable until acceptance (§21).

| Constant | Value | Controls | Never train? |
|----------|-------|----------|--------------|
| N_ENC | 128 | LIF encoder units (== 2×NX for Burgers') | yes |
| D | 64 | SSF hidden state dim | yes |
| M | 32 | RCD episodic memory dim | yes |
| P | 1 | Readout output dim (scalar field) | yes |
| SIGMA_THRESHOLD | 1e-2 | Gaussian-CDF smoothing width | no (tunable) |
| VTHETA_INIT | 1.0 | Encoder firing threshold initial | yes (init only, trainable) |
| LEAK_TAU | 5.0 | Encoder leak time constant (steps) | yes |
| REFRACTORY_STEPS | 2 | Soft refractory gate tau | yes |
| A_MIN | 0.5 | SSF diagonal contraction floor | **architectural** |
| DELTA_MIN | 2.0 | Min inter-tick gap | **architectural** |
| B_PARAM | "linear" | SSF B(S) parameterisation | yes (Theorem 2 requires linear) |
| RHO_EMA_BETA | 0.95 | Clock EMA decay | yes |
| RHO_THRESHOLD0 | 0.05 | Clock gate offset ρ₀ | yes |
| RHO_GATE_GAIN | 4.0 | Clock gate sharpness γ | yes |
| U_MAX | 1.0 | Readout activation bound (enforced by tanh) | **architectural** |
| BETA_0 | 6.0 | β calibration numerator ∈ [4,8] | **architectural** |
| MU_MIN | 0.5 | Plastic ODE contraction rate (gated) | yes |
| MU_FREE | 0.0 | Plastic ODE contraction rate (free) | yes |
| ETA_PLASTIC | 1e-3 | Plastic ODE Euler step size | yes (safety: η·μ_min < 2) |
| LAMBDA_B_SPARSITY | 1e-2 | Theorem 2 column-l21 weight | no (hyperparam) |
| N_JVP_DIRECTIONS | 8 | JVP Monte Carlo directions | no (variance ~ 1/N) |
| DTYPE | "float32" | Default dtype | yes |
| RNG_SEED | 20260426 | Determinism seed | yes |

---

## 5. INVARIANTS

| ID | Description | Enforced where | Status |
|----|-------------|----------------|--------|
| I1 | No `jax.grad`/`jax.vjp`/`jacrev`/`Heaviside` reachable from `lcn/` | `CI/grep_no_grad.sh` + `_check_lcn_jvp()` in train.py:86 | ENFORCED |
| I2 | `jvp_activity` is unbiased estimator of ∇_θ L_σ | External `lcn_jvp` package (not installed) | EXTERNAL |
| I5 | Deterministic under fixed RNG seed | `RNG_SEED` constant + all key-based | DESIGN |
| I6 | Bit-identical with vs without `active_proj` (measurement-only) | `_one_dir()` in train.py:128 — proj used only for d_k | DESIGN |
| I-ENC-1 | Spike probabilities s ∈ [0, 1] | `check_i_enc_1()` in encoder.py:107 + test_encoder.py:113 | ✅ |
| I-ENC-2 | `jax.jvp` returns finite tangents through encoder | `check_i_enc_2()` in encoder.py:112 + test_encoder.py:120 | ✅ |
| I-ENC-3 | As σ→0, mean rate → hard-threshold rate | test_encoder.py:78 (sigma robustness <= 5%) | ✅ |
| I-SSF-1 | a_i ≤ -A_MIN structurally | `SSFParams.__call__()` line 50: `-A_MIN - softplus(a_raw)` + test_ssf.py:76 | ✅ |
| I-SSF-2 | Zero input ⇒ ‖h_T‖ ≤ ‖h₀‖ e^(-A_MIN·T) | test_ssf.py:41 (1.05× bound) | ✅ |
| I-SSF-3 | ZOH error O(dt²) | By construction (exact ZOH for linear segment) | DESIGN |
| I-CLK-1 | Mean inter-tick gap ≥ DELTA_MIN | `clock_step()` cooldown logic line 61-64 + test_clock.py:56 | ✅ |
| I-CLK-2 | Tick rate sublinear in T, ≤ 1/DELTA_MIN | test_clock.py:46 | ✅ |
| I-CLK-3 | Gate ∈ [0, 1] | sigmoid output + test_clock.py:78 | ✅ |
| I-RCD-1 | ‖c_k‖_∞ ≤ 1 (tanh + convex gate) | test_rcd.py:31 | ✅ |
| I-RCD-2 | RCD invoked ONLY on ticks | `rcd_step()` line 87: `jax.lax.cond(tick, ...)` + CI grep | ENFORCED |
| I-RCD-3 | Forget-gate mean ≈ 0.73 at init (Jozefowicz) | `RCDCell` bf=1.0 init line 43 + test_rcd.py:44 | ✅ |
| I-PL-1 | g_hat=0, g≈1 ⇒ ‖W_z‖_F decays | test_plastic.py:35 | ✅ |
| I-PL-2 | Free regime ⇒ W_z tracks integral of g_hat | By construction of Euler ODE | DESIGN |
| I-PL-3 | Euler stability: η·μ_min < 2 | test_plastic.py:57 | ✅ |
| I-RO-1 | Gate → 0.5 at u_j→0, monotonic in \|u_j\| | test_readout.py:28,36 | ✅ |
| I-RO-2 | JVP-clean — no `where` on tangents | `readout_forward` uses only mul/sigmoid | DESIGN |
| I-RO-3 | ‖z‖ ≤ ‖W_z‖_F·√(D+M) | test_readout.py:48 | ✅ |

---

## 6. ACCEPTANCE CRITERIA (§21)

Status key: `[ ]` pending, `[x]` done, `[~]` partial, `[!]` blocked

| Criterion | Status | Notes |
|-----------|--------|-------|
| P0 — Repo + JAX + lcn_jvp install | [!] | JAX/flax not installed in current env; `lcn_jvp` package not available |
| P1 — Spike Encoder | [~] | Code done, 4 test classes written, 0 pass (no JAX) |
| P2 — Selective State Filter | [~] | Code done, 4 test classes written, 0 pass (no JAX). See known issue #1 |
| P3 — Distillation Clock | [~] | Code done, 5 test classes written, 0 pass (no JAX) |
| P4 — Recurrent Context Distiller | [~] | Code done, 5 test classes written, 0 pass (no JAX) |
| P5 — ODE-Plastic Readout | [~] | Code done, 6 test classes written, 0 pass (no JAX) |
| P6 — Plastic-weight ODE | [~] | Code done, 6 test classes written, 0 pass (no JAX) |
| P7 — A+C Training Loop | [!] | Code written but depends on external `lcn_jvp` (not found). No tests for train.py |
| P8 — Burgers' 4-arm Testbed | [~] | PDE solver done, arm configs done, harness skeleton only (arms.py:80-90 is placeholder). PDE tests written, 0 pass (no JAX) |
| All acceptance probes passing on 64×64 Burgers', ν=10⁻² | [!] | Blocked by JAX + lcn_jvp + harness |
| 4-arm comparison plot for T∈{10,100,1000} | [ ] | Not started |
| 1/√N variance regression at N∈{16,64,256,1024} | [ ] | Not started |

---

## 7. API REFERENCE

### `lcn.constants` — 23 named constants (see §4 table above)

### `lcn.types` — 7 dataclasses

```python
class State:
    Fields: v(N_ENC,), t_since(N_ENC,), h(D,), c(M,), W_z(P,D+M), rho_ema scalar, cooldown scalar, tick scalar, gate scalar
class EncoderState: v(N_ENC,), t_since(N_ENC,)
class SSFState: h(D,)
class RCDState: c(M,)
class ClockState: rho_ema scalar, cooldown scalar
class PlasticState: W_z(P,D+M), rho_ema scalar
class Window: x(T,N_ENC), u0(NX,), nu float, n_steps int
class TickRecord: tau_k, rho_t, rho_ema, gate, kappa_hat, d_k, r2_violation, truncated, loss_local, W_norm, g_norm, u_max_q, u_max_a, beta_eff, arm
```

### `lcn.encoder`

```python
def encoder_step(carry: tuple[jnp.ndarray, jnp.ndarray], x_t: jnp.ndarray, vtheta: jnp.ndarray, sigma: float = 1e-2, dt: float = 1.0) -> tuple[tuple[jnp.ndarray, jnp.ndarray], jnp.ndarray]
    """Single LIF step + Gaussian-CDF surrogate firing. Returns ((v_new, t_new), s)."""

def encode_window(x_window: jnp.ndarray, v0: jnp.ndarray, vtheta: jnp.ndarray, sigma: float = 1e-2) -> tuple[tuple[jnp.ndarray, jnp.ndarray], jnp.ndarray]
    """Encode full window T×N_ENC → spike sequence. Returns ((v_final, t_final), S(T,N_ENC))."""

def init_encoder(key: jnp.ndarray) -> tuple[jnp.ndarray, jnp.ndarray]
    """Initialize v0=zeros, vtheta=VTHETA_INIT. Returns (v0, vtheta)."""

def check_i_enc_1(s: jnp.ndarray) -> bool
    """I-ENC-1: All spikes in [0, 1]."""

def check_i_enc_2(x_window: jnp.ndarray, v0: jnp.ndarray, vtheta: jnp.ndarray) -> bool
    """I-ENC-2: jax.jvp returns finite tangents."""

def _refractory(t_since: jnp.ndarray, tau: float = 2) -> jnp.ndarray
    """Soft refractory gate: 1 - exp(-t_since/tau)."""
```

### `lcn.ssf`

```python
class SSFParams(nn.Module):
    """Parameter module: a(S) = -A_MIN - softplus(W_a·S+b_a), B(S) linear/MLP."""
    hidden: int = 32
    def __call__(self, s_t: jnp.ndarray) -> tuple[jnp.ndarray, jnp.ndarray]
        """Returns (a_t(D,), B_t(D,N_ENC))."""

def ssf_step(h_prev: jnp.ndarray, s_t: jnp.ndarray, params: SSFParams, dt: float = 1.0) -> tuple[jnp.ndarray, tuple[jnp.ndarray, jnp.ndarray]]
    """ZOH-discretised SSF step. Returns (h_new, (a_t, B_t))."""

def run_ssf(s_window: jnp.ndarray, h0: jnp.ndarray, params: SSFParams) -> tuple[jnp.ndarray, tuple[jnp.ndarray, jnp.ndarray]]
    """Run SSF over window. Returns (h_final, (h_traj, (a_traj, B_traj)))."""

def l21_penalty(B_traj: jnp.ndarray) -> jnp.ndarray
    """Column-l2,1 sparsity penalty for B(S). Input (T,D,N_ENC) → scalar."""
```

### `lcn.clock`

```python
def clock_init() -> dict
    """Returns {'rho_ema': RHO_THRESHOLD0, 'cooldown': 0.0}."""

def clock_step(state: dict, s_t: jnp.ndarray, dt: float = 1.0) -> tuple[dict, jnp.ndarray, jnp.ndarray, jnp.ndarray]
    """EMA update + tick detection + gate. Returns (new_state, tick bool, gate, rho_t)."""

def run_clock(s_window: jnp.ndarray) -> tuple[dict, jnp.ndarray, jnp.ndarray, jnp.ndarray]
    """Run clock over window. Returns (final_state, ticks(T,), gates(T,), rho_traj(T,))."""

def gate_value(rho_ema: jnp.ndarray) -> jnp.ndarray
    """σ(γ·(ρ_ema - ρ₀)) — for external use by plastic ODE."""
```

### `lcn.rcd`

```python
class RCDCell(nn.Module):
    """LSTM-flavored RCD with forget-gate bias init=1.0."""
    def __call__(self, h_k: jnp.ndarray, c_prev: jnp.ndarray) -> jnp.ndarray
        """Apply RCD at a tick. Returns c_k(M,)."""

def init_rcd() -> jnp.ndarray
    """Returns c0 = zeros(M,)."""

def rcd_step(cell: RCDCell, c_prev: jnp.ndarray, h_t: jnp.ndarray, tick: jnp.ndarray) -> tuple[jnp.ndarray, jnp.ndarray]
    """Conditional update on tick via jax.lax.cond. Returns (c_new, c_new_or_prev)."""
```

### `lcn.readout`

```python
class PlasticReadout(nn.Module):
    """C2 gated mixture: z = W_z·(u ⊙ σ(β|u|))."""
    def __call__(self, u: jnp.ndarray) -> jnp.ndarray
        """Forward pass. Input (…,D+M) → output (…,P)."""

def pack_u(h: jnp.ndarray, c: jnp.ndarray) -> jnp.ndarray
    """Pack [h; c] through tanh. Returns u(…,D+M) bounded in (-1,1)."""

def readout_forward(W_z: jnp.ndarray, u: jnp.ndarray) -> jnp.ndarray
    """Functional readout: (u*gate) @ W_z.T. Input u(…,D+M) → z(…,P)."""

def readout_pullback(W_z: jnp.ndarray, u: jnp.ndarray, dz: jnp.ndarray) -> jnp.ndarray
    """Pullback ∂z/∂W_z·dz = outer(dz, u_gated). Returns (P,D+M)."""

def _calibrated_beta() -> float
    """β = BETA_0 / (U_MAX · e^(-A_MIN·DELTA_MIN)) ≈ 16.31. Never trained."""
```

### `lcn.plastic`

```python
def gate_value(rho_ema: jnp.ndarray) -> jnp.ndarray
    """σ(γ·(ρ_ema - ρ₀)). Returns scalar in [0,1]."""

def _mu_effective(g_t: jnp.ndarray) -> jnp.ndarray
    """Switched contraction: μ_free + (μ_min - μ_free)·g(t)."""

def plastic_euler_step(W_z: jnp.ndarray, g_hat: jnp.ndarray, rho_ema: jnp.ndarray, eta: float = 1e-3) -> jnp.ndarray
    """W_{t+1} = W_t + η·(ĝ - μ(t)·W_t). Returns W_z(P,D+M)."""

def plastic_heun_step(W_z: jnp.ndarray, g_hat: jnp.ndarray, rho_ema: jnp.ndarray, eta: float = 1e-3) -> jnp.ndarray
    """Trapezoidal Heun step (2nd order). Returns W_z(P,D+M)."""
```

### `lcn.train`

**⚠️ Depends on external `lcn_jvp` package (Spec §4.10) — NOT installed. All functions raise `ImportError` at runtime if `lcn_jvp` is missing.**

```python
class TrainState:
    Fields: W_z(P,D+M), u_at_tick_prev(D+M,), rho_ema scalar, dh_trace(D+M,), step int
    def replace(self, **kw) -> TrainState

def init_train_state(W_z0: jnp.ndarray, u0: jnp.ndarray) -> TrainState
    """Initialize fresh training state."""

def train_one_tick(state: TrainState, key: jnp.ndarray, *, forward_fn, forward_primal_fn, pullback_fn) -> tuple[TrainState, dict]
    """One A+C training step: N_JVP_DIRECTIONS antithetic pairs → avg g_hat → Euler step."""

def train_one_tick_heun(state: TrainState, key: jnp.ndarray, *, forward_fn, forward_primal_fn, pullback_fn) -> tuple[TrainState, dict]
    """Same as train_one_tick but with Heun integrator."""

def _one_dir(state: TrainState, key: jnp.ndarray, *, forward_fn, forward_primal_fn, pullback_fn) -> tuple
    """Internal: one JVP direction estimate. Returns (Result, kappa_hat, d_k)."""
```

**Required external imports (from `lcn_jvp`):**
- `sample_direction(key, shape, distribution)` — sample random direction v
- `antithetic(u, v)` — returns (u+σv, u-σv) pair
- `jvp_activity(forward_fn, u_tau_prev, pair, rng_key, smoothing_sigma, active_proj, pullback, ...)` — returns Result with g_theta_hat
- `column_norm_probe(forward_primal_fn, u_tau_prev, basis_idx)` — L2 norm of a single Jacobian column
- `active_set(dh_trace, epsilon)` — returns (projection, d_k)

### `lcn.diagnostics`

```python
class DiagnosticsWriter:
    def __init__(self, output_dir: str = "./logs")
    def log(self, record: TickRecord) -> None
    def flush(self, filename: str = "diagnostics.parquet") -> Optional[Path]
    @property record_count: int

def compute_diagnostics(tick_idx, rho_t, rho_ema, gate, kappa_hat, d_k, r2_violation, truncated, loss_local, W_norm, g_norm, u, beta_eff, arm) -> TickRecord
    """Build TickRecord with u_max_q/u_max_a derived from u."""

def print_tick_summary(record: TickRecord) -> None
    """One-line console tick summary."""

def sanity_check(record: TickRecord) -> list[str]
    """Run quick sanity checks; returns list of warning strings."""
```

### `lcn.testbed.burgers`

```python
def simulate(u0: jnp.ndarray, nu: float, n_steps: int) -> tuple[jnp.ndarray, jnp.ndarray]
    """RK4 Burgers' simulation. Returns (u_final(NX,), u_traj(n_steps,NX))."""

def sample_ic(key: jnp.ndarray, n_modes: int = 4) -> jnp.ndarray
    """Random 4-mode Fourier IC. Returns u0(NX,)."""

def rate_code(u_field: jnp.ndarray) -> jnp.ndarray
    """Sign-separated: [max(u,0); max(-u,0)]. Returns (2*NX,) == (N_ENC,)."""

def loss_mse(z_pred: jnp.ndarray, u_target: jnp.ndarray) -> jnp.ndarray
    """MSE loss. Returns scalar."""

class ArmConfig:
    Fields: name str, plastic_update bool, jvp_estimator bool, switched_contraction bool

ARM_BPTT_SURROGATE, ARM_A_ONLY, ARM_C_ONLY, ARM_A_PLUS_C: ArmConfig
ALL_ARMS = [ARM_BPTT_SURROGATE, ARM_A_ONLY, ARM_C_ONLY, ARM_A_PLUS_C]
```

### `lcn.testbed.encodings`

```python
def rate_code(u_field: jnp.ndarray) -> jnp.ndarray
    """Sign-separated rate code (delegates to burgers.rate_code)."""

def identity_code(u_field: jnp.ndarray) -> jnp.ndarray
    """Pass-through encoding (requires N_ENC == NX)."""
```

### `lcn.testbed.arms`

```python
def run_arm(arm: ArmConfig, key, u0, nu, T_encoder, n_steps_per_enc, encoder_fn, ssf_fn, clock_fn, rcd_fn, readout_fn, train_fn=None) -> dict
    """SKELETON — runs PDE + rate coding, returns dict with placeholders. Forward pass NOT integrated."""

def compare_arms(key, nu=1e-2, T_values=[10,100,1000]) -> dict
    """SKELETON — iterates arms, returns {'arm_T': {'pending': True}}. No actual training."""
```

---

## 8. DEPENDENCY GRAPH

```
lcn.constants         ← (no lcn imports)
lcn.types             ← lcn.constants
lcn.encoder           ← lcn.constants, jax
lcn.ssf               ← lcn.constants, jax, flax
lcn.clock             ← lcn.constants, jax
lcn.rcd               ← lcn.constants, jax, flax
lcn.readout           ← lcn.constants, jax, flax
lcn.plastic           ← lcn.constants, jax
lcn.train             ← lcn.constants, lcn.clock, lcn.plastic, lcn_jvp (EXTERNAL, missing)
lcn.diagnostics       ← lcn.types, pyarrow (optional)
lcn.testbed.burgers   ← jax
lcn.testbed.encodings ← lcn.testbed.burgers
lcn.testbed.arms      ← lcn.testbed.burgers

External deps: jax, jaxlib, flax, numpy, pyarrow, lcn_jvp (not found)
Tests import from: lcn_brain.lcn.<module> (require editable install)
```

**From train.py internal imports:**
```
train.py → lcn.clock.gate_value (as clock_gate_value)
train.py → lcn.plastic.plastic_euler_step, plastic_heun_step
train.py → lcn.constants (N_JVP_DIRECTIONS, SIGMA_THRESHOLD, DTYPE)
train.py → lcn_jvp.dual (sample_direction, antithetic)
train.py → lcn_jvp.estimators (jvp_activity)
train.py → lcn_jvp.probes (kappa_probe)
train.py → lcn_jvp.projection (active_set)
```

---

## 9. KNOWN ISSUES

1. **JAX NOT INSTALLED** — `jax`, `jaxlib`, `flax` missing from the current Python 3.14.3 environment. All 7 test files fail at collection with `ModuleNotFoundError: No module named 'jax'`. **Blocks all tests.** Fix: `pip install jax jaxlib flax` in the target venv.

2. **`lcn_jvp` PACKAGE NOT AVAILABLE** — `train.py` imports from `lcn_jvp.dual`, `lcn_jvp.estimators`, `lcn_jvp.probes`, `lcn_jvp.projection`. This is an external reference implementation (Spec §4.10) that does not exist in the repo. Without it, P7 (training loop) cannot run. **Blocks: P7, P8, all acceptance probes.** Fix: write the `lcn_jvp` package (or locate the reference implementation) with these 5 functions: `sample_direction`, `antithetic`, `jvp_activity`, `kappa_probe`, `active_set`.

3. **TRAINING LOOP NOT TESTED** — No `tests/test_train.py` exists. `train.py` stubs to `None` when `lcn_jvp` import fails. **Blocks: P7 validation.** Fix: create `test_train.py` after lcn_jvp is available.

4. **TESTBED HARNESS IS A SKELETON** — `arms.py:run_arm()` lines 79-90 run the PDE but return a dict with `loss_history=[]`, `tick_count=0` and no actual forward-pass integration. `compare_arms()` returns `{'pending': True}` for all entries. **Blocks: P8, 4-arm comparison.** Fix: wire up the full pipeline (encoder→SSF→clock→RCD→readout→training) inside `run_arm()`.

5. **SSF `run_ssf` RETURN TYPE MISMATCH?** — `run_ssf` returns `(h_final, (h_traj, (a_traj, B_traj)))` but `test_ssf.py:107` iterates `h_traj` as if it's a list of `(a_t, B_t)` pairs via `[aux[1] for aux in h_traj]`. The scan return is `(final_carry, stacked_outputs)` where stacked_outputs is `(h_new, (a_t, B_t))` per step. The test assumes `h_traj` is a list of `(a_t, B_t)` — need to verify actual scan output structure. **Impact: test_ssf.py:107 may fail even with JAX installed.** Fix: unpack correctly — `h_traj` is the stacked `h_new` values; the aux trajectory is separate.

6. **`readout_forward` MATMUL ORDER** — Line 84: `u * gate @ W_z.T`. Python operator precedence: `@` binds tighter than `*`, so this is `(u * (gate @ W_z.T))` which is wrong. Should be `(u * gate) @ W_z.T`. **Impact: readout produces incorrect values, I-RO-3 violation.** Fix: add parentheses: `(u * gate) @ W_z.T`.

7. **NO `ActiveSet` DATACLASS** — `train.py:128` calls `active_set(dh_trace, epsilon)` which returns `(proj, d_k)`, but `TrainState` stores `dh_trace` as an array, not a structured `ActiveSet`. The `proj` from `lcn_jvp` is used only for `d_k` (measurement-only invariant I6), not applied to tangents. **Impact: unclear if `active_set` return type matches expectations.** Fix: clarify `lcn_jvp.projection.active_set` API contract.

8. **DUPLICATE `from dataclasses import dataclass`** — `burgers.py` line 20 and 22 both import `dataclass`. Harmless but messy. Fix: remove line 22.

---

## 10. BUILD ORDER

| Phase | Description | Produces | Depends on | Status |
|-------|-------------|----------|------------|--------|
| P0 | Repo setup + venv + JAX + flax install | Runnable Python package | pyproject.toml | [!] JAX/flax missing |
| P1 | Spike Encoder | `lcn/encoder.py` + tests | P0, constants | [~] code done |
| P2 | Selective State Filter | `lcn/ssf.py` + tests | P0, constants | [~] code done |
| P3 | Distillation Clock | `lcn/clock.py` + tests | P0, constants | [~] code done |
| P4 | Recurrent Context Distiller | `lcn/rcd.py` + tests | P2, P3, constants | [~] code done |
| P5 | ODE-Plastic Readout | `lcn/readout.py` + tests | P2, P4, constants | [~] code done |
| P6 | Plastic-weight ODE | `lcn/plastic.py` + tests | P3, constants | [~] code done |
| P7 | A+C Training Loop | `lcn/train.py` + tests | P5, P6, **lcn_jvp** | [!] blocked by lcn_jvp |
| P8 | Burgers' 4-arm Testbed | `lcn/testbed/*.py` + integration | P7, P1-P6 | [~] PDE done, harness skeleton |
| — | Acceptance probes | All tests green on 64×64 ν=10⁻² | P8 | [ ] |
| — | 4-arm comparison plot | Matplotlib figure T∈{10,100,1000} | P8 | [ ] |
| — | 1/√N variance regression | Variance vs N plot | P7 | [ ] |

---

## 11. QUICK FIXES (to get tests green fast)

Ranked by (impact × ease):

1. **Install JAX + flax** (unblocks 49 tests across 7 files)
   ```bash
   pip install jax jaxlib flax
   ```
   Impact: all collection errors fixed. Tests may still fail on logic bugs (see #5, #6).

2. **Fix `readout_forward` matmul precedence** (fixes incorrect readout values)
   In `lcn/readout.py` line 84, change:
   ```python
   return u * gate @ W_z.T
   ```
   to:
   ```python
   return (u * gate) @ W_z.T
   ```

3. **Fix SSF test trajectory unpacking** (test_ssf.py line 103-107)
   The `run_ssf` returns `(h_final, (h_traj, (a_traj, B_traj)))` where `h_traj` is a sequence of `h` states, not `(a_t, B_t)` tuples. The test at line 107 tries `aux[1]` but aux is a single tensor, not a tuple. Need to use the actual aux trajectory from the third return element.

4. **Write the `lcn_jvp` package** (unblocks P7 training loop)
   Create minimal implementations of the 5 required functions. The reference is at Spec §4.10. Start with stubs that raise or return zeros, then implement properly.

5. **Wire up `run_arm()` in `arms.py`** (unblocks P8 integration testing)
   Replace the placeholder return (lines 80-90) with actual encoder→SSF→clock→RCD→readout pipeline calls. This is the integration point where all modules connect.

---

## 12. NEXT STEPS (after tests green)

Per §22 and README status list, in priority order:

1. **Complete P7 testing** — write `tests/test_train.py` with unit tests for `_one_dir`, `train_one_tick`, `train_one_tick_heun`. Verify g_hat estimates are finite, W_z norms change appropriately, active set dimension d_k is plausible.

2. **Integrate P7 into P8** — wire `train_one_tick` into `run_arm()` for the `A_plus_C` and `C_only` arms. Wire `plastic_euler_step` with gate forced to 0 for `A_only`.

3. **BPTT baseline arm** — implement reverse-mode surrogate-gradient BPTT for the `BPTT_surrogate` arm (this arm is allowed to use `jax.grad` since it's the baseline, but keep it outside `lcn/` proper).

4. **4-arm comparison plot** — run all 4 arms at T∈{10,100,1000}, plot loss vs T per arm. Validate that A+C outperforms baselines.

5. **1/√N variance regression** — measure JVP estimator variance at N_JVP_DIRECTIONS∈{16,64,256,1024}, verify slope ≈ -0.5 on log-log.

6. **Diagnostics integration** — connect `DiagnosticsWriter` to the training loop, flush Parquet logs after each run.

7. **`B_PARAM = "mlp"` exploration** — Theorem 2 only holds for linear B(S), but MLP may give better representational capacity. Implement and measure l21 penalty.

8. **Remove duplicate `from dataclasses import dataclass`** in `burgers.py` line 22.
