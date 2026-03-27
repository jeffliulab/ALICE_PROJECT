"""Embedding functions using sentence-transformers (local)."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        from backend.config import EMBEDDING_MODEL_NAME
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        log.info("Loaded embedding model: %s", EMBEDDING_MODEL_NAME)
    return _model


def get_embedding(text: str) -> list[float]:
    model = _get_model()
    return model.encode(text).tolist()


def cos_sim(a, b) -> float:
    a = np.array(a)
    b = np.array(b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
