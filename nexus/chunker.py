"""Nexus ThoughtChunker — LLM-driven text splitting into atomic ideas.

Takes raw text (any length) and decomposes it into self-contained atomic
thoughts, each tagged with topics, sentiment, and domain.

Two modes:
  1. LLM chunking: Uses Ollama to intelligently split by meaning boundaries.
  2. Rule-based fallback: Splits by sentence/paragraph if LLM is unavailable.
"""

import json
import logging
import re
import time
from typing import Dict, List, Optional, Tuple

from nexus.models import Thought
from nexus.prompts import (
    CHUNK_SYSTEM, CHUNK_PROMPT,
    TAG_SYSTEM, TAG_PROMPT,
)

_log = logging.getLogger("nexus.chunker")


class ThoughtChunker:
    """Splits raw text into atomic Thought objects with auto-tagging."""

    def __init__(self, llm_model: str = "deepseek-r1:14b",
                 llm_fallback: str = "llama3.2:3b",
                 max_words: int = 150,
                 min_words: int = 10,
                 ollama_host: str = "http://localhost:11434"):
        self._model = llm_model
        self._fallback = llm_fallback
        self._max_words = max_words
        self._min_words = min_words
        self._host = ollama_host
        self._ollama = None

    def _get_ollama(self):
        if self._ollama is None:
            try:
                import ollama
                self._ollama = ollama
            except ImportError:
                _log.warning("ollama not installed. Using rule-based chunking only.")
        return self._ollama

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(self, text: str, source: str = "",
              source_file: str = "") -> List[Thought]:
        """Split raw text into atomic Thought objects.

        Args:
            text: Raw input text (any length).
            source: Source label (e.g. "voice", "file", "manual").
            source_file: Original file path if from a file.

        Returns:
            List of Thought objects, each tagged.
        """
        if not text or not text.strip():
            return []

        # Clean input
        text = self._clean_text(text)

        # Try LLM chunking first, fall back to rule-based
        raw_chunks = self._llm_chunk(text)
        if not raw_chunks:
            _log.info("LLM chunking unavailable. Using rule-based fallback.")
            raw_chunks = self._rule_based_chunk(text)

        # Filter out too-short chunks
        raw_chunks = [c for c in raw_chunks if len(c.split()) >= self._min_words]

        if not raw_chunks:
            # If everything was too short, keep the original as one chunk
            if len(text.split()) >= self._min_words:
                raw_chunks = [text]
            else:
                return []

        # Tag each chunk
        thoughts = []
        for chunk_text in raw_chunks:
            tags_data = self._tag_chunk(chunk_text)
            thought = Thought(
                text=chunk_text,
                tags=tags_data.get("tags", []),
                source=source,
                source_file=source_file,
                metadata={
                    "sentiment": tags_data.get("sentiment", "neutral"),
                    "domain": tags_data.get("domain", "general"),
                    "actionable": tags_data.get("actionable", False),
                },
            )
            thoughts.append(thought)

        _log.info("Chunked text into %d thoughts (source=%s)", len(thoughts), source)
        return thoughts

    def chunk_without_llm(self, text: str, source: str = "",
                          source_file: str = "") -> List[Thought]:
        """Rule-based chunking only — no LLM required.

        Useful for testing or when Ollama is down.
        """
        if not text or not text.strip():
            return []

        text = self._clean_text(text)
        raw_chunks = self._rule_based_chunk(text)
        raw_chunks = [c for c in raw_chunks if len(c.split()) >= self._min_words]

        if not raw_chunks and len(text.split()) >= self._min_words:
            raw_chunks = [text]

        thoughts = []
        for chunk_text in raw_chunks:
            tags = self._extract_keywords(chunk_text)
            thought = Thought(
                text=chunk_text,
                tags=tags[:5],
                source=source,
                source_file=source_file,
                metadata={"sentiment": "neutral", "domain": "general", "actionable": False},
            )
            thoughts.append(thought)

        return thoughts

    # ------------------------------------------------------------------
    # LLM chunking
    # ------------------------------------------------------------------

    def _llm_chunk(self, text: str) -> Optional[List[str]]:
        """Use LLM to intelligently split text into atomic ideas."""
        client = self._get_ollama()
        if client is None:
            return None

        prompt = CHUNK_PROMPT.format(text=text[:5000], max_words=self._max_words)

        for model in [self._model, self._fallback]:
            try:
                response = client.chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": CHUNK_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                )
                content = response.get("message", {}).get("content", "")
                if not content:
                    continue

                chunks = self._parse_chunk_response(content)
                if chunks:
                    return chunks

            except Exception as e:
                _log.debug("LLM chunk failed with %s: %s", model, e)
                continue

        return None

    def _parse_chunk_response(self, content: str) -> Optional[List[str]]:
        """Parse the LLM's JSON response into a list of text strings."""
        # Strip markdown fences if present
        content = re.sub(r"```(?:json)?\s*", "", content)
        content = content.strip().rstrip("```")

        # Strip <think> blocks from deepseek-r1
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        content = content.strip()

        # Find JSON array
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if not match:
            return None

        try:
            data = json.loads(match.group())
            if isinstance(data, list):
                texts = []
                for item in data:
                    if isinstance(item, str):
                        texts.append(item.strip())
                    elif isinstance(item, dict):
                        t = item.get("text", "")
                        if t:
                            texts.append(t.strip())
                return texts if texts else None
        except json.JSONDecodeError as e:
            _log.debug("JSON parse failed: %s", e)

        return None

    # ------------------------------------------------------------------
    # LLM tagging
    # ------------------------------------------------------------------

    def _tag_chunk(self, text: str) -> Dict:
        """Use LLM to tag a chunk with topics, sentiment, domain."""
        client = self._get_ollama()
        if client is None:
            return {
                "tags": self._extract_keywords(text)[:5],
                "sentiment": "neutral",
                "domain": "general",
                "actionable": False,
            }

        prompt = TAG_PROMPT.format(text=text[:2000])

        for model in [self._model, self._fallback]:
            try:
                response = client.chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": TAG_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                )
                content = response.get("message", {}).get("content", "")
                if not content:
                    continue

                result = self._parse_tag_response(content)
                if result:
                    return result

            except Exception as e:
                _log.debug("LLM tag failed with %s: %s", model, e)
                continue

        # Fallback: keyword extraction
        return {
            "tags": self._extract_keywords(text)[:5],
            "sentiment": "neutral",
            "domain": "general",
            "actionable": False,
        }

    def _parse_tag_response(self, content: str) -> Optional[Dict]:
        """Parse the LLM's tag JSON response."""
        content = re.sub(r"```(?:json)?\s*", "", content)
        content = content.strip().rstrip("```")
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        content = content.strip()

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None

        try:
            data = json.loads(match.group())
            if isinstance(data, dict) and "tags" in data:
                return {
                    "tags": [str(t).lower().replace(" ", "_") for t in data.get("tags", [])],
                    "sentiment": data.get("sentiment", "neutral"),
                    "domain": data.get("domain", "general"),
                    "actionable": bool(data.get("actionable", False)),
                }
        except json.JSONDecodeError:
            pass

        return None

    # ------------------------------------------------------------------
    # Rule-based fallback
    # ------------------------------------------------------------------

    def _rule_based_chunk(self, text: str) -> List[str]:
        """Split text by paragraph, then by sentence clusters if too long."""
        paragraphs = re.split(r"\n\s*\n", text)
        chunks = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            word_count = len(para.split())
            if word_count <= self._max_words:
                chunks.append(para)
            else:
                # Split long paragraphs by sentences
                sentences = re.split(r"(?<=[.!?])\s+", para)
                current = []
                current_words = 0

                for sent in sentences:
                    sent_words = len(sent.split())
                    if current_words + sent_words > self._max_words and current:
                        chunks.append(" ".join(current))
                        current = [sent]
                        current_words = sent_words
                    else:
                        current.append(sent)
                        current_words += sent_words

                if current:
                    chunks.append(" ".join(current))

        return chunks

    # ------------------------------------------------------------------
    # Keyword extraction (no LLM)
    # ------------------------------------------------------------------

    _STOP_WORDS = frozenset({
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "up", "about", "into", "through",
        "during", "before", "after", "above", "below", "between", "out",
        "off", "over", "under", "again", "further", "then", "once", "here",
        "there", "when", "where", "why", "how", "all", "both", "each",
        "few", "more", "most", "other", "some", "such", "no", "nor", "not",
        "only", "own", "same", "so", "than", "too", "very", "just", "because",
        "but", "and", "or", "if", "while", "as", "until", "that", "this",
        "these", "those", "it", "its", "i", "me", "my", "we", "our", "you",
        "your", "he", "she", "they", "them", "what", "which", "who", "whom",
        "um", "uh", "like", "basically", "really", "actually", "also",
    })

    def _extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Extract keywords from text using frequency analysis."""
        words = re.findall(r"[a-zA-Z_]{3,}", text.lower())
        words = [w for w in words if w not in self._STOP_WORDS]

        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1

        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:max_keywords]]

    # ------------------------------------------------------------------
    # Text cleaning
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean raw text — normalize whitespace, strip control chars."""
        # Remove common filler from voice transcripts
        text = re.sub(r"\b(um|uh|er|ah|like,)\b", "", text, flags=re.IGNORECASE)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        # Remove control characters
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        return text
