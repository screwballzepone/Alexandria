"""
§6 — Architectural constants.

All defaults from Spec §4.4, §4.6, §4.12.
Treat as immutable until acceptance (§21).

A_MIN, U_MAX, BETA_0, DELTA_MIN are **architectural** — never trained.
Spec §4.12 only severs the β-calibration circularity if these are constants of the design.
"""

N_ENC = 128  # LIF encoder units
D = 64  # SSF state dim
M = 32  # RCD episodic dim
P = 1  # readout dim (Burgers' 1D scalar field)
SIGMA_THRESHOLD = 1e-2  # Gaussian threshold smoothing
VTHETA_INIT = 1.0  # firing threshold
LEAK_TAU = 5.0  # encoder time constant in steps
REFRACTORY_STEPS = 2  # soft refractory gate
A_MIN = 0.5  # SSF: a_i(S) <= -A_MIN < 0 always
DELTA_MIN = 2.0  # min inter-tick gap; design pressure A_MIN*DELTA_MIN >= 1
B_PARAM = "linear"  # 'linear' | 'mlp'; Theorem 2 holds only under linear
RHO_EMA_BETA = 0.95  # clock EMA gain
RHO_THRESHOLD0 = 0.05  # gate offset rho_0
RHO_GATE_GAIN = 4.0  # gate sharpness gamma
U_MAX = 1.0  # readout activation bound (enforced upstream)
BETA_0 = 6.0  # §4.12: beta_0 in [4, 8]
MU_MIN = 0.5  # plastic ODE contraction rate when gated
MU_FREE = 0.0  # contraction rate when free
ETA_PLASTIC = 1e-3  # plastic ODE step size
LAMBDA_B_SPARSITY = 1e-2  # §4.11 Theorem 2 column-l21
N_JVP_DIRECTIONS = 8  # variance ~ 1/N_JVP_DIRECTIONS
DTYPE = "float32"
RNG_SEED = 20260426
