"""Nexus embeddings — standalone vector operations via Ollama.

Thin wrapper around Ollama's embedding endpoint with:
  - Local JSON cache (avoids recomputing)
  - Cosine similarity
  - Batch embedding
  - No OnyxKraken dependencies

Falls back gracefully if Ollama is unavailable.
"""

import json
import logging
import math
import os
import time
from typing import Dict, List, Optional, Tuple

_log = logging.getLogger("nexus.embeddings")


class NexusEmbeddings:
    """Vector embedding store with Ollama backend and local cache."""

    def __init__(self, model: str = "nomic-embed-text",
                 cache_path: str = "",
                 ollama_host: str = "http://localhost:11434"):
        self.model = model
        self._host = ollama_host
        self._cache_path = cache_path
        self._cache: Dict[str, List[float]] = {}
        self._available: Optional[bool] = None
        self._ollama = None

        if cache_path:
            self._load_cache()

    # ------------------------------------------------------------------
    # Ollama client (lazy)
    # ------------------------------------------------------------------

    def _get_ollama(self):
        if self._ollama is None:
            try:
                import ollama
                self._ollama = ollama
            except ImportError:
                _log.warning("ollama package not installed. Embeddings unavailable.")
        return self._ollama

    def is_available(self) -> bool:
        """Check if the embedding model is reachable."""
        if self._available is not None:
            return self._available
        client = self._get_ollama()
        if client is None:
            self._available = False
            return False
        try:
            client.embed(model=self.model, input="test")
            self._available = True
        except Exception as e:
            _log.info("Embedding model '%s' not available: %s", self.model, e)
            self._available = False
        return self._available

    # ------------------------------------------------------------------
    # Cache I/O
    # ------------------------------------------------------------------

    def _load_cache(self):
        if self._cache_path and os.path.exists(self._cache_path):
            try:
                with open(self._cache_path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                _log.debug("Loaded %d cached embeddings", len(self._cache))
            except (json.JSONDecodeError, IOError) as e:
                _log.debug("Cache load failed: %s", e)
                self._cache = {}

    def save_cache(self):
        """Persist the embedding cache to disk."""
        if not self._cache_path:
            return
        os.makedirs(os.path.dirname(self._cache_path) or ".", exist_ok=True)
        # Cap at 2000 entries
        if len(self._cache) > 2000:
            keys = list(self._cache.keys())[-2000:]
            self._cache = {k: self._cache[k] for k in keys}
        try:
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f)
        except IOError as e:
            _log.warning("Cache save failed: %s", e)

    # ------------------------------------------------------------------
    # Embed
    # ------------------------------------------------------------------

    def embed(self, text: str) -> Optional[List[float]]:
        """Get embedding vector for text. Uses cache if available."""
        if not text or not text.strip():
            return None
        if not self.is_available():
            return None

        cache_key = f"{self.model}:{text[:300]}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            result = self._get_ollama().embed(model=self.model, input=text)
            embeddings = getattr(result, "embeddings", None)
            if embeddings is None and isinstance(result, dict):
                embeddings = result.get("embeddings", [])
            if embeddings and len(embeddings) > 0:
                vec = embeddings[0]
                self._cache[cache_key] = vec
                if len(self._cache) % 20 == 0:
                    self.save_cache()
                return vec
        except Exception as e:
            _log.debug("Embed failed: %s", e)

        return None

    def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Embed multiple texts. Returns list parallel to input."""
        return [self.embed(t) for t in texts]

    # ------------------------------------------------------------------
    # Similarity
    # ------------------------------------------------------------------

    def similarity(self, text1: str, text2: str) -> float:
        """Cosine similarity between two texts. Returns -1.0 if unavailable."""
        vec1 = self.embed(text1)
        vec2 = self.embed(text2)
        if vec1 is None or vec2 is None:
            return -1.0
        return cosine_similarity(vec1, vec2)

    def similarity_vec(self, vec1: List[float], vec2: List[float]) -> float:
        """Cosine similarity between two pre-computed vectors."""
        return cosine_similarity(vec1, vec2)

    def find_nearest(self, query: str, candidates: List[dict],
                     text_key: str = "text", limit: int = 10,
                     threshold: float = 0.5) -> List[Tuple[float, dict]]:
        """Find the most similar candidates to a query string.

        Args:
            query: Text to search for.
            candidates: List of dicts to search.
            text_key: Key in each dict containing the text.
            limit: Max results.
            threshold: Minimum similarity (0.0–1.0).

        Returns:
            List of (score, candidate) tuples, sorted descending.
        """
        query_vec = self.embed(query)
        if query_vec is None:
            return []

        scored = []
        for item in candidates:
            text = item.get(text_key, "")
            if not text:
                continue
            # Use pre-computed embedding if available
            item_vec = item.get("embedding") or self.embed(text)
            if item_vec is None:
                continue
            score = cosine_similarity(query_vec, item_vec)
            if score >= threshold:
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:limit]

    @property
    def cache_size(self) -> int:
        return len(self._cache)


# ---------------------------------------------------------------------------
# Pure math — no dependencies
# ---------------------------------------------------------------------------

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors. Returns 0.0 on error."""
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def centroid(vectors: List[List[float]]) -> List[float]:
    """Compute the mean vector (centroid) of a list of vectors."""
    if not vectors:
        return []
    dim = len(vectors[0])
    result = [0.0] * dim
    for vec in vectors:
        for i in range(dim):
            result[i] += vec[i]
    n = len(vectors)
    return [x / n for x in result]
