"""lcn_cortex.py — Cortex state management + training orchestration.

Manages the LCN readout weight ``W_z`` as a trainable cortex that learns to
predict entity outcomes from feature embeddings. Training uses the LCN brain's
functional readout and plastic ODE modules (JAX-accelerated).

Graceful degradation: if JAX or the LCN brain modules are unavailable, all
training operations return diagnostics with ``"degraded": True``.
"""

from __future__ import annotations

import dataclasses
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# sys.path management — allow import from Brain/lcn_brain/
# ---------------------------------------------------------------------------

_BRAIN_ROOT = Path(__file__).resolve().parent.parent  # OpenCode/Brain/
sys.path.insert(0, str(_BRAIN_ROOT))

# ---------------------------------------------------------------------------
# JAX / LCN brain availability
# ---------------------------------------------------------------------------

_JAX_AVAILABLE = False
try:
    import jax.numpy as jnp  # noqa: F811, I001
    from lcn_brain.lcn.readout import readout_forward, readout_pullback  # noqa: I001
    from lcn_brain.lcn.plastic import plastic_euler_step  # noqa: I001

    _JAX_AVAILABLE = True
except ImportError:
    pass

# Import entity encoder (pure numpy — always available)
from Brain.lcn_entity_encoder import EMBED_DIM, encode_entity, outcome_target  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_ETA = 0.001  # plastic ODE step size (matches ETA_PLASTIC)
_RHO_EMA_DECAY = 0.95  # EMA decay for training activity tracking
_TRAIN_TRIGGER_MIN_ENTITIES = 3
_TRAIN_TRIGGER_CONFIDENCE = 4

# ---------------------------------------------------------------------------
# Cortex state
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class CortexState:
    """Mutable state of the cortex readout.

    Attributes:
        W_z:        Readout weight vector, shape (1, EMBED_DIM).
        step:       Number of training steps performed.
        last_trained: ISO-8601 timestamp of last training, or empty string.
        rho_ema:    EMA tracking training activity (used by plastic ODE gate).
    """
    W_z: np.ndarray         # shape (1, EMBED_DIM)
    step: int = 0
    last_trained: str = ""
    rho_ema: float = 0.05   # initialized at RHO_THRESHOLD0 (low gate = active)


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


def init_cortex(state_path: str | Path | None = None) -> CortexState:
    """Load a :class:`CortexState` from ``.npz`` or initialise fresh.

    Args:
        state_path: Path to a ``.npz`` checkpoint.  If *None* or the file does
                    not exist, returns a fresh zero-initialised state.

    Returns:
        A loaded or fresh :class:`CortexState`.
    """
    if state_path is not None:
        p = Path(state_path).expanduser().resolve()
        if p.exists():
            try:
                data = np.load(str(p))
                return CortexState(
                    W_z=data["W_z"],
                    step=int(data.get("step", 0)),
                    last_trained=str(data.get("last_trained", b"").decode("utf-8")
                                      if isinstance(data.get("last_trained"), bytes)
                                      else data.get("last_trained", "")),
                    rho_ema=float(data.get("rho_ema", 0.05)),
                )
            except (OSError, IOError, KeyError, ValueError):
                pass  # fall through to fresh init

    return CortexState(
        W_z=np.zeros((1, EMBED_DIM), dtype=np.float64),
        rho_ema=0.05,
    )


def save_cortex(state: CortexState, state_path: str | Path) -> None:
    """Persist :class:`CortexState` to a ``.npz`` file.

    Includes ``rho_ema`` in the archive (REVIEWER FIX: previously omitted).

    Args:
        state:      The current cortex state.
        state_path: Destination path (``~`` is expanded).
    """
    p = Path(state_path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        str(p),
        W_z=state.W_z,
        step=state.step,
        last_trained=state.last_trained,
        rho_ema=state.rho_ema,
    )


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def _should_train(entities: list[dict[str, Any]]) -> bool:
    """Check whether the entity batch triggers a training step.

    Triggers when at least one of:
    - Contains ≥1 Pattern or Convention.
    - Contains ≥1 Decision with confidence ≥ 4.
    - Total entity count ≥ ``_TRAIN_TRIGGER_MIN_ENTITIES``.

    Returns:
        True if training should proceed.
    """
    if not entities:
        return False

    pattern_or_convention = 0
    high_conf_decision = 0

    for ent in entities:
        etype = ent.get("entity_type", "")
        if etype in ("Pattern", "Convention"):
            pattern_or_convention += 1
        if etype == "Decision":
            conf = ent.get("confidence", 0)
            if isinstance(conf, (int, float)) and conf >= _TRAIN_TRIGGER_CONFIDENCE:
                high_conf_decision += 1

    return (
        pattern_or_convention >= 1
        or high_conf_decision >= 1
        or len(entities) >= _TRAIN_TRIGGER_MIN_ENTITIES
    )


def train_cortex(
    state: CortexState,
    entities: list[dict[str, Any]],
    outcome: float | None = None,
    eta: float = _DEFAULT_ETA,
) -> tuple[CortexState, dict[str, Any]]:
    """Run one analytic training step over the entity batch.

    For each entity:
        1. Encode → feature vector ``u``.
        2. Get target ``y`` (from ``outcome_target()`` or the provided ``outcome``).
        3. Forward: ``z = readout_forward(W_z, u)``.
        4. MSE cotangent: ``dz = 2 * (z - y)``.
        5. Pullback: ``g_hat = readout_pullback(W_z, u, dz)``.
        6. Plastic Euler step: ``W_z += eta * (-g_hat - mu * W_z)``.

    Args:
        state:    Current cortex state (mutated in place and returned).
        entities: List of LCN entity dicts.
        outcome:  Optional override target.  If *None*, inferred from each
                  entity via ``outcome_target()``.
        eta:      Plastic ODE step size (default 0.001).

    Returns:
        Tuple of (updated state, diagnostics dict).
    """
    diag: dict[str, Any] = {
        "trained": False,
        "degraded": False,
        "entities_processed": 0,
        "entities_skipped": 0,
        "loss_before": None,
        "loss_after": None,
        "g_norm": None,
        "step": state.step,
    }

    if not _JAX_AVAILABLE:
        diag["degraded"] = True
        diag["reason"] = "JAX or LCN brain modules not available"
        return state, diag

    if not _should_train(entities):
        diag["trained"] = False
        diag["reason"] = "Training trigger conditions not met"
        return state, diag

    # Convert state W_z to JAX array
    W_z = jnp.array(state.W_z)  # type: ignore[name-defined]  # noqa: F821

    losses_before: list[float] = []
    losses_after: list[float] = []
    g_norms: list[float] = []
    processed = 0
    skipped = 0

    for entity in entities:
        # Determine target
        y_val = outcome if outcome is not None else outcome_target(entity)
        if y_val is None:
            skipped += 1
            continue  # skip entities without a target

        # Encode entity → feature vector
        u_np = encode_entity(entity)  # shape (EMBED_DIM,)
        if np.linalg.norm(u_np) < 1e-12:
            skipped += 1
            continue

        u = jnp.array(u_np)  # type: ignore[name-defined]  # noqa: F821
        y = jnp.array(y_val, dtype=jnp.float32)  # type: ignore[name-defined]  # noqa: F821

        # Forward
        z = readout_forward(W_z, u)  # scalar
        loss_before = float(jnp.squeeze((z - y) ** 2))  # type: ignore[union-attr]
        losses_before.append(loss_before)

        # MSE cotangent
        dz = 2.0 * (z - y)  # scalar

        # Pullback — gradient of loss w.r.t. W_z
        g_hat = readout_pullback(W_z, u, dz)  # shape (1, EMBED_DIM)
        g_norm = float(jnp.linalg.norm(g_hat))  # type: ignore[union-attr]
        g_norms.append(g_norm)

        # Plastic Euler step (negative gradient for descent)
        W_z = plastic_euler_step(W_z, -g_hat, jnp.array(state.rho_ema), eta=eta)  # type: ignore[name-defined]  # noqa: F821

        # Forward after update
        z_after = readout_forward(W_z, u)
        loss_after = float(jnp.squeeze((z_after - y) ** 2))  # type: ignore[union-attr]
        losses_after.append(loss_after)

        processed += 1

    if processed == 0:
        diag["trained"] = False
        diag["reason"] = "No entities with valid targets"
        return state, diag

    # Update state
    state.W_z = np.asarray(W_z)  # type: ignore[union-attr]
    state.step += 1
    state.last_trained = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state.rho_ema = _RHO_EMA_DECAY * state.rho_ema + (1 - _RHO_EMA_DECAY) * 1.0

    # Diagnostics
    diag["trained"] = True
    diag["entities_processed"] = processed
    diag["entities_skipped"] = skipped
    diag["loss_before"] = float(np.mean(losses_before)) if losses_before else None
    diag["loss_after"] = float(np.mean(losses_after)) if losses_after else None
    diag["g_norm"] = float(np.mean(g_norms)) if g_norms else None
    diag["step"] = state.step
    diag["rho_ema"] = state.rho_ema

    return state, diag


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def cortex_rank(
    W_z: np.ndarray,
    sqlite_results: list[dict[str, Any]],
    query_text: str,
    alpha: float = 0.3,
) -> list[dict[str, Any]]:
    """Augment SQLite retrieval results with cortex relevance scores.

    For each result:
        1. Encode the entity via ``encode_entity()`` → ``u``.
        2. Compute ``z = readout_forward(W_z, u)``.
        3. **Signed score**: ``score = max(0, z / W_norm)``
           (REVIEWER FIX: clamp negative z to 0).
        4. Blend: ``combined = alpha * cortex_score + (1 - alpha) * sqlite_score``.

    When JAX is unavailable, results pass through with a cortex score of 0.0.

    Args:
        W_z:            Readout weight, shape (1, EMBED_DIM).
        sqlite_results: List of entity dicts from the LCN store, each
                        optionally containing ``_relevance_score``.
        query_text:     Query text used to compute a query vector (not yet
                        used in per-entity scoring — see note below).
        alpha:          Blend weight for cortex score vs. SQLite score.

    Returns:
        List of result dicts augmented with keys ``_cortex_score``,
        ``_blended_score`` (sorted descending).
    """
    _ = query_text  # reserved for future query-entity similarity

    # Compute W_norm once
    W_norm = float(np.linalg.norm(W_z))

    augmented: list[dict[str, Any]] = []
    for result in sqlite_results:
        u_np = encode_entity(result)

        cortex_score = 0.0
        if _JAX_AVAILABLE and W_norm > 1e-12 and np.linalg.norm(u_np) > 1e-12:
            u = jnp.array(u_np)  # type: ignore[name-defined]  # noqa: F821
            W = jnp.array(W_z)  # type: ignore[name-defined]  # noqa: F821
            z = float(jnp.squeeze(readout_forward(W, u)))  # type: ignore[union-attr]
            # Signed score, clamp negative to 0 (REVIEWER FIX)
            cortex_score = max(0.0, z / W_norm)

        # SQLite relevance (default 0 if absent)
        sqlite_score = float(result.get("_relevance_score", 0))

        blended = alpha * cortex_score + (1.0 - alpha) * sqlite_score

        result["_cortex_score"] = round(cortex_score, 6)
        result["_blended_score"] = round(blended, 6)
        augmented.append(result)

    # Sort by blended score descending
    augmented.sort(key=lambda r: r["_blended_score"], reverse=True)
    return augmented
