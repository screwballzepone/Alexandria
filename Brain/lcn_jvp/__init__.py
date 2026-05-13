"""
lcn_jvp — Forward-mode JVP reference implementation (Spec §4.10).

Provides the core gradient estimator primitives used by the LCN training
loop: antithetic sampling, condition-number probes, active-set projection,
and the central-difference JVP activity estimator.

All functions are pure JAX — no side effects, no Python loops over batches.
"""
