"""Sentence-transformer embedding encoder with lazy loading and batching."""
import logging
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        from src.config import EMBEDDING_MODEL
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("Embedding model loaded.")
    return _model


def encode(text: str) -> list[float]:
    """Encode a single text string into a vector."""
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def encode_batch(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """Encode a list of texts, processing in batches to manage memory."""
    model = _get_model()
    all_vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        vectors = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        all_vectors.extend(vectors.tolist())
        if i % (batch_size * 10) == 0 and i > 0:
            logger.info(f"  Encoded {i}/{len(texts)} texts...")
    return all_vectors
