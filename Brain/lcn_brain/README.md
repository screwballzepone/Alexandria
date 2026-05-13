# LCN Brain

**Language Cognition Network** — spiking neural architecture with forward-mode autodiff, plastic memory, and a Burgers' equation testbed.

## Status

- [ ] P0 — Repo + JAX + lcn_jvp install
- [ ] P1 — Spike Encoder (LIF + Gaussian-CDF surrogate)
- [ ] P2 — Selective State Filter (diagonal selective ODE)
- [ ] P3 — Distillation Clock (EMA-triggered ticks)
- [ ] P4 — Recurrent Context Distiller (LSTM-flavored, tick-gated)
- [ ] P5 — ODE-Plastic Readout (C2 gated mixture)
- [ ] P6 — Plastic-weight ODE (switched contraction, Approach A)
- [ ] P7 — A+C Training Loop (JVP estimator + plastic updates)
- [ ] P8 — Burgers' 4-arm Testbed (PDE solver + harness)
- [ ] All acceptance probes passing on 64×64 Burgers', ν=10⁻²
- [ ] 4-arm comparison plot for T∈{10,100,1000}
- [ ] 1/√N variance regression passes at N∈{16,64,256,1024}

## Quickstart

```bash
cd lcn_brain
pip install -e ".[dev]"
pip install lcn_jvp   # external JVP micro-library (Spec §4.10)
pytest tests/ -v
```

## Architecture

```
x(t) → [Spike Encoder] → S(t) → [Selective State Filter] → h(t) ──→ [Distillation Clock] ──→ h(τ_k) → [RCD] → c_k
                                                                    │                                    │
                                                                    └─ g(t) ────────────────────────────→ [Plastic ODE] → W_z
                                                                                                             │
                                                                    h(t), c_k ──────────────────────→ [C2 Readout] ←───┘
                                                                                                             │
                                                                                                          z(t)
```

No attention. No KV cache. Three memory substrates at three timescales. Forward-mode JVP — no surrogate gradient bias chain.

## Memory Substrates

| Substrate | Symbol | Timescale | Plastic? |
|---|---|---|---|
| Working   | h(t)   | 1–10 steps | no (state) |
| Episodic  | c_k    | 10²–10³ ticks | no (state) |
| Structural | W_z(t) | ≫10³ steps | **yes** (plastic) |

## Invariants

- **I1**: No `jax.grad`/`jax.vjp`/`jacrev` reachable from `lcn/` (CI-grep enforces)
- **I2**: `jvp_activity` is unbiased estimator of ∇_θ L_σ
- **I5**: Deterministic under fixed RNG seed
- **I6**: Bit-identical with vs without `active_proj` (measurement-only)

## References

- [Language Cognition Network — Architecture Specification](https://www.notion.so/Language-Cognition-Network-Architecture-Specification-d7f7a71131be48ffafa17c5e3d822631)
- [§4.10 JVP micro-library — reference implementation (JAX)](https://www.notion.so/4-10-JVP-micro-library-Burgers-4-arm-harness-reference-implementation-JAX-ce7aea3a0d084c93820bf5c898af916a)

## License

Research code — not yet licensed.
