"""lcn_bridge.py — Public API bridge between JANUS orchestrator and LCN Cortex.

Provides a simplified interface for training the cortex on mission entities
and augmenting SQLite retrieval results with cortex relevance scores.

Graceful degradation: if the LCN brain modules (JAX, ``lcn_cortex``, etc.)
are unavailable, all operations return degraded diagnostics without crashing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# sys.path management — allow import from Brain/
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # OpenCode/
sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Graceful imports
# ---------------------------------------------------------------------------

_CORTEX_AVAILABLE = False
_lcn_cortex: Any = None
try:
    from Brain import lcn_cortex as _lcn_cortex

    _CORTEX_AVAILABLE = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Config path
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG_PATH = (
    _PROJECT_ROOT / ".opencode" / "lcn_bridge_config.json"
)
_DEFAULT_STATE_PATH = (
    Path.home() / ".local" / "share" / "opencode" / "lcn_cortex.npz"
)


def _load_config() -> dict[str, Any]:
    """Load bridge configuration, merging defaults for missing keys."""
    defaults: dict[str, Any] = {
        "enabled": True,
        "cortex_state_path": str(_DEFAULT_STATE_PATH),
        "training": {"min_entities": 3, "learning_rate": 0.001},
        "retrieval": {"alpha": 0.3},
    }
    config_path = _DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return defaults
    try:
        with open(str(config_path), "r", encoding="utf-8") as f:
            overrides = json.load(f)
        # Deep merge
        result = dict(defaults)
        result.update(overrides)
        for key in ("training", "retrieval"):
            if key in overrides and isinstance(overrides[key], dict):
                result[key].update(overrides[key])
        return result
    except (json.JSONDecodeError, OSError):
        return defaults


# ---------------------------------------------------------------------------
# LcnBridge
# ---------------------------------------------------------------------------


class LcnBridge:
    """Public bridge API for the LCN Cortex training and retrieval system.

    Usage::

        bridge = LcnBridge()
        result = bridge.train(plan_entities)
        augmented = bridge.cortex_query(sqlite_results, "my query")
        health = bridge.status()
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or _load_config()
        self._state_path: str | None = self.config.get("cortex_state_path")
        self._state: Any = None  # CortexState — loaded on first use
        self._bridge_loaded = _CORTEX_AVAILABLE

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_state(self) -> None:
        """Lazy-load the cortex state on first access."""
        if self._state is None and self._bridge_loaded:
            self._state = _lcn_cortex.init_cortex(self._state_path)  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def train(self, plan: list[dict[str, Any]]) -> dict[str, Any]:
        """Train the cortex on a mission plan's entities.

        Args:
            plan: List of LCN entity dicts (Decision, Error, Rejection,
                  Pattern, Convention).

        Returns:
            Diagnostics dict with keys:
            - ``trained``: True if training actually occurred.
            - ``degraded``: True if the cortex modules are unavailable.
            - ``entities_processed``: Count of entities used for training.
            - ``loss_before`` / ``loss_after``: Mean MSE before/after update.
            - ``g_norm``: Mean gradient norm.
            - ``step``: Current training step count.
        """
        if not self._bridge_loaded:
            return {
                "trained": False,
                "degraded": True,
                "reason": "LCN cortex modules not available",
                "entities_processed": 0,
            }

        self._ensure_state()

        alpha = self.config.get("retrieval", {}).get("alpha", 0.3)
        _ = alpha  # reserved for future blending config

        # plan format: [mode, session_id, entities, outcome]
        entities = plan[2] if isinstance(plan, list) and len(plan) > 2 and isinstance(plan[2], list) else []
        self._state, diag = _lcn_cortex.train_cortex(  # type: ignore[union-attr]
            self._state,
            entities,
            eta=self.config.get("training", {}).get("learning_rate", 0.001),
        )

        # Persist state after training
        if diag.get("trained") and self._state_path:
            _lcn_cortex.save_cortex(self._state, self._state_path)  # type: ignore[union-attr]

        return diag

    def cortex_query(
        self,
        sqlite_results: list[dict[str, Any]],
        query_text: str,
    ) -> list[dict[str, Any]]:
        """Augment SQLite results with cortex relevance scores.

        Args:
            sqlite_results: List of entity dicts returned by the LCN store.
            query_text: Natural-language query to inform relevance.

        Returns:
            Augmented results with ``_cortex_score`` and ``_blended_score``
            keys, sorted by blended score descending.  Degraded mode returns
            results unchanged.
        """
        if not self._bridge_loaded:
            return sqlite_results

        self._ensure_state()

        alpha = self.config.get("retrieval", {}).get("alpha", 0.3)
        return _lcn_cortex.cortex_rank(  # type: ignore[union-attr]
            self._state.W_z,
            sqlite_results,
            query_text,
            alpha=alpha,
        )

    def status(self) -> dict[str, Any]:
        """Health check for the bridge and underlying cortex.

        Returns:
            Dict with keys:
            - ``bridge_loaded``: True if cortex modules are importable.
            - ``state_path``: Path to the persisted ``.npz`` state.
            - ``state_exists``: Whether the state file exists on disk.
            - ``step``: Current training step count.
            - ``W_norm``: Frobenius norm of the readout weight vector.
            - ``enabled``: Whether the bridge is enabled in config.
            - ``config``: Active configuration (sensitive fields redacted).
        """
        self._ensure_state()

        state_path = self._state_path or str(_DEFAULT_STATE_PATH)
        p = Path(state_path).expanduser().resolve()

        W_norm = 0.0
        step = 0
        rho_ema = None
        if self._state is not None:
            W_norm = float(np.linalg.norm(self._state.W_z))
            step = self._state.step
            rho_ema = self._state.rho_ema

        return {
            "bridge_loaded": self._bridge_loaded,
            "cortex_available": _CORTEX_AVAILABLE,
            "state_path": str(p),
            "state_exists": p.exists(),
            "step": step,
            "W_norm": round(W_norm, 6),
            "rho_ema": round(rho_ema, 6) if rho_ema is not None else None,
            "enabled": self.config.get("enabled", True),
            "config": {
                "enabled": self.config.get("enabled", True),
                "training": self.config.get("training", {}),
                "retrieval": self.config.get("retrieval", {}),
            },
        }


# ---------------------------------------------------------------------------
# CLI entry point (quick test)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    bridge = LcnBridge()
    print(json.dumps(bridge.status(), indent=2, ensure_ascii=False))
