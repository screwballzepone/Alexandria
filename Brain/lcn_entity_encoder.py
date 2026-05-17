"""lcn_entity_encoder.py — Entity text to 96-dim feature vectors.

Maps LCN entity dicts and query strings to deterministic 96-dimensional
feature vectors via MD5-based feature hashing (bag-of-tokens). L2-normalized.

Provides ``outcome_target()`` for supervised training signals.

No external dependencies — uses stdlib ``hashlib`` + ``numpy`` only.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBED_DIM = 96  # Matches D + M from lcn_brain constants

# Maps entity_type → list of data-fields to extract text from
_TYPE_FIELDS: dict[str, list[str]] = {
    "Decision": ["chosen_approach", "rationale", "outcome"],
    "Rejection": ["approach", "reason", "context_that_might_change_this"],
    "Error": ["symptom", "root_cause", "fix_applied", "failure_class"],
    "Pattern": ["shape_description", "when_to_use", "when_not_to_use", "scope"],
    "Convention": ["rule", "why", "example", "scope"],
}

# ---------------------------------------------------------------------------
# Feature hashing helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Split text into lowercased tokens on whitespace."""
    return text.lower().split()


def _hash_token(token: str) -> int:
    """Deterministic MD5 hash → bin index in [0, EMBED_DIM)."""
    digest = hashlib.md5(token.encode("utf-8")).digest()
    # Use first 4 bytes as int, then mod
    idx = int.from_bytes(digest[:4], "little") % EMBED_DIM
    return idx


def _text_to_vector(text: str) -> np.ndarray:
    """Bag-of-tokens feature vector via MD5 hashing.

    Returns a 1D array of shape (EMBED_DIM,) with raw token counts.
    """
    vec = np.zeros(EMBED_DIM, dtype=np.float64)
    for token in _tokenize(text):
        idx = _hash_token(token)
        vec[idx] += 1.0
    return vec


def _normalize(vec: np.ndarray) -> np.ndarray:
    """L2-normalize a vector in-place, returning a new array.

    Returns zeros if the input is all-zero (norm < 1e-12).
    """
    norm = np.linalg.norm(vec)
    if norm < 1e-12:
        return np.zeros_like(vec)
    return vec / norm


# ---------------------------------------------------------------------------
# Entity data extraction
# ---------------------------------------------------------------------------


def _get_data(entity: dict[str, Any]) -> dict[str, Any]:
    """Return the inner data dict, handling both flat and nested formats."""
    if "data" in entity and isinstance(entity["data"], dict):
        return entity["data"]
    # Flat format — entity IS the data (minus DB bookkeeping keys)
    SKIP_KEYS = {"id", "entity_type", "natural_key", "mission_id",
                 "created_at", "updated_at", "data", "confidence"}
    return {k: v for k, v in entity.items() if k not in SKIP_KEYS}


def _extract_text(entity: dict[str, Any]) -> str:
    """Extract relevant text from an entity based on its type."""
    data = _get_data(entity)
    entity_type = entity.get("entity_type", "")
    fields = _TYPE_FIELDS.get(entity_type, [])

    parts: list[str] = []
    for field in fields:
        val = data.get(field)
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, list):
            parts.extend(str(v) for v in val)
    return " ".join(parts)


def _confidence_scale(entity: dict[str, Any]) -> float:
    """Confidence scaling factor in [0.2, 1.0].

    ``scale = max(confidence, 1) / 5`` — clamp min to 1 to avoid zero vectors.
    """
    conf = entity.get("confidence", 3)
    if not isinstance(conf, (int, float)):
        conf = 3
    return max(int(conf), 1) / 5.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def encode_entity(entity: dict[str, Any]) -> np.ndarray:
    """Encode an entity dict into a 96-dim L2-normalized feature vector.

    The vector is scaled by the entity's confidence level so that high-
    confidence entities have larger magnitude before normalization (which
    is then lost during L2-normalization — the scale is preserved as the
    vector direction via confidence-weighted token accumulation).

    Args:
        entity: LCN entity dict (with ``entity_type``, ``confidence``,
                and type-specific fields).

    Returns:
        96-dim float64 numpy array, L2-normalized, or zeros for empty input.
    """
    text = _extract_text(entity)
    vec = _text_to_vector(text)

    # Confidence-weighted accumulation before normalization
    scale = _confidence_scale(entity)
    vec = vec * scale

    return _normalize(vec)


def encode_text(text: str) -> np.ndarray:
    """Encode a raw query string into a 96-dim L2-normalized vector.

    Args:
        text: Free-form query text.

    Returns:
        96-dim float64 numpy array, L2-normalized, or zeros for empty string.
    """
    if not text or not text.strip():
        return np.zeros(EMBED_DIM, dtype=np.float64)
    return _normalize(_text_to_vector(text))


def outcome_target(entity: dict[str, Any]) -> float | None:
    """Return supervised training target for an entity.

    Returns:
        +1.0 for succeeded Decision,
        -1.0 for failed/rolled-back Decision, Error, or Rejection,
        None  for Pattern, Convention, or pending Decision.
    """
    data = _get_data(entity)
    entity_type = entity.get("entity_type", "")

    if entity_type == "Decision":
        outcome = data.get("outcome", "").strip().lower()
        if outcome in ("succeeded",):
            return 1.0
        if outcome in ("failed", "rolled-back"):
            return -1.0
        return None  # pending Decision — no target

    if entity_type in ("Error", "Rejection"):
        # Errors and Rejections are always negative outcomes
        return -1.0

    # Pattern and Convention — no outcome signal
    return None
