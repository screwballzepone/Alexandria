"""State and Window dataclasses for the LCN pipeline."""

from dataclasses import dataclass

import jax.numpy as jnp



@dataclass
class State:
    """Full LCN state at time t."""

    v: jnp.ndarray  # encoder membrane potentials   (N_ENC,)
    t_since: jnp.ndarray  # refractory timer              (N_ENC,)
    h: jnp.ndarray  # SSF working memory            (D,)
    c: jnp.ndarray  # RCD episodic memory           (M,)
    W_z: jnp.ndarray  # plastic readout weights       (P, D+M)
    rho_ema: jnp.ndarray  # clock EMA scalar
    cooldown: jnp.ndarray  # clock cooldown scalar
    tick: jnp.ndarray  # boolean tick flag (scalar)
    gate: jnp.ndarray  # soft gate g(t) in [0,1] (scalar)


@dataclass
class EncoderState:
    """Encoder-specific carry state."""

    v: jnp.ndarray  # membrane potentials  (N_ENC,)
    t_since: jnp.ndarray  # refractory timer      (N_ENC,)


@dataclass
class SSFState:
    """SSF-specific carry state."""

    h: jnp.ndarray  # hidden state  (D,)


@dataclass
class RCDState:
    """RCD-specific carry state."""

    c: jnp.ndarray  # cell state  (M,)


@dataclass
class ClockState:
    """Clock-specific carry state."""

    rho_ema: jnp.ndarray  # EMA scalar
    cooldown: jnp.ndarray  # cooldown counter scalar


@dataclass
class PlasticState:
    """Plastic ODE state."""

    W_z: jnp.ndarray  # readout weights  (P, D+M)
    rho_ema: jnp.ndarray  # gate signal


@dataclass
class Window:
    """A window of input data for batch processing."""

    x: jnp.ndarray  # input sequence  (T, N_ENC)
    u0: jnp.ndarray  # Burgers' IC      (N_X,)
    nu: float  # viscosity
    n_steps: int  # PDE steps per encoder step


@dataclass
class TickRecord:
    """Diagnostic record for one distillation tick."""

    tau_k: int
    rho_t: float
    rho_ema: float
    gate: float
    kappa_hat: float
    d_k: int
    r2_violation: bool
    truncated: bool
    loss_local: float
    W_norm: float
    g_norm: float
    u_max_q: float
    u_max_a: float
    beta_eff: float
    arm: str
