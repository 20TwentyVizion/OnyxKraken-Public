"""Embedding-based memory similarity — upgrades keyword matching to semantic search.

Uses Ollama's embedding endpoint to compute vector similarity between tasks,
enabling OnyxKraken to recognize "Open Notepad and type Hello" and
"Launch Notepad and write Hello" as the same intent.

Falls back gracefully to keyword matching if embeddings are unavailable.
"""

import json
import logging
import math
import os
import time
from typing import Optional

_log = logging.getLogger("embeddings")

try:
    import ollama
    _HAS_OLLAMA = True
except ImportError:
    _HAS_OLLAMA = False


# Default embedding model (small, fast)
EMBED_MODEL = os.environ.get("ONYX_EMBED_MODEL", "nomic-embed-text")

# Cache file for embeddings to avoid recomputing
_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "embeddings_cache.json")


class EmbeddingStore:
    """Manages text embeddings with local caching and cosine similarity search."""

    def __init__(self, model: str = EMBED_MODEL, cache_path: str = _CACHE_FILE):
        self.model = model
        self.cache_path = cache_path
        self._cache: dict[str, list[float]] = self._load_cache()
        self._available: Optional[bool] = None  # lazy check

    def _load_cache(self) -> dict:
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                _log.debug(f"Failed to load embedding cache: {e}")
        return {}

    def _save_cache(self):
        os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
        # Only save last 500 entries to prevent unbounded growth
        if len(self._cache) > 500:
            # Keep most recent entries (by insertion order in Python 3.7+)
            keys = list(self._cache.keys())[-500:]
            self._cache = {k: self._cache[k] for k in keys}
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f)

    def is_available(self) -> bool:
        """Check if the embedding model is available."""
        if self._available is not None:
            return self._available
        if not _HAS_OLLAMA:
            self._available = False
            return False
        try:
            ollama.embed(model=self.model, input="test")
            self._available = True
        except Exception:
            self._available = False
            print(f"[Embeddings] Model '{self.model}' not available. Using keyword fallback.")
        return self._available

    def embed(self, text: str) -> Optional[list[float]]:
        """Get embedding vector for text. Uses cache if available."""
        if not self.is_available():
            return None

        # Check cache
        cache_key = f"{self.model}:{text[:200]}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            result = ollama.embed(model=self.model, input=text)
            # ollama.embed returns {"embeddings": [[...]]} or an object with .embeddings
            embeddings = getattr(result, "embeddings", None) or (result.get("embeddings", []) if isinstance(result, dict) else [])
            if embeddings and len(embeddings) > 0:
                vec = embeddings[0]
                self._cache[cache_key] = vec
                # Periodically save cache
                if len(self._cache) % 10 == 0:
                    self._save_cache()
                return vec
        except Exception as e:
            print(f"[Embeddings] Embed failed: {e}")

        return None

    def similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts.

        Returns 0.0-1.0 (higher = more similar), or -1.0 if embeddings unavailable.
        """
        vec1 = self.embed(text1)
        vec2 = self.embed(text2)
        if vec1 is None or vec2 is None:
            return -1.0
        return _cosine_similarity(vec1, vec2)

    def find_similar(self, query: str, candidates: list[dict],
                     text_key: str = "goal", limit: int = 5,
                     threshold: float = 0.5) -> list[tuple[float, dict]]:
        """Find the most similar candidates to a query.

        Args:
            query: Text to search for.
            candidates: List of dicts to search through.
            text_key: Key in each dict that contains the text to compare.
            limit: Max results to return.
            threshold: Minimum similarity score (0-1).

        Returns:
            List of (score, candidate) tuples, sorted by score descending.
        """
        query_vec = self.embed(query)
        if query_vec is None:
            return []

        scored = []
        for item in candidates:
            text = item.get(text_key, "")
            if not text:
                continue
            item_vec = self.embed(text)
            if item_vec is None:
                continue
            score = _cosine_similarity(query_vec, item_vec)
            if score >= threshold:
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:limit]

    def flush_cache(self):
        """Save the current cache to disk."""
        self._save_cache()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# Singleton (delegates to service registry)

def get_embedding_store() -> EmbeddingStore:
    from core.service_registry import services
    if not services.has("embeddings"):
        services.register_factory("embeddings", EmbeddingStore)
    return services.get("embeddings", EmbeddingStore)
