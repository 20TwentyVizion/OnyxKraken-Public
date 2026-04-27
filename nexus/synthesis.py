"""Nexus SynthesisEngine — proposes new hypothesis nodes from clusters.

Examines groups of related thoughts and uses the LLM to generate
new ideas that emerge from their combination. These "hypothesis" nodes
get added to the graph with synthesis-type links.
"""

import json
import logging
import re
import time
from typing import Dict, List, Optional

from nexus.models import Thought, ThoughtLink, Cluster, SynthesisResult
from nexus.prompts import (
    SYNTHESIS_SYSTEM, SYNTHESIS_PROMPT,
    CLUSTER_NAME_SYSTEM, CLUSTER_NAME_PROMPT,
    format_thoughts_for_prompt,
)

_log = logging.getLogger("nexus.synthesis")


class SynthesisEngine:
    """Proposes new ideas by analyzing clusters of related thoughts.

    Strategy:
      1. For each cluster with enough thoughts, format them as context.
      2. Prompt the LLM: "Given these ideas, propose one new insight."
      3. Parse the structured JSON response.
      4. Create a new Thought with is_hypothesis=True.
      5. Link the hypothesis to its source thoughts.
    """

    def __init__(self, llm_model: str = "deepseek-r1:14b",
                 llm_fallback: str = "llama3.2:3b",
                 min_cluster_size: int = 3,
                 min_confidence: float = 0.4):
        self._model = llm_model
        self._fallback = llm_fallback
        self._min_cluster_size = min_cluster_size
        self._min_confidence = min_confidence
        self._ollama = None

    def _get_ollama(self):
        if self._ollama is None:
            try:
                import ollama
                self._ollama = ollama
            except ImportError:
                _log.warning("ollama not installed. Synthesis unavailable.")
        return self._ollama

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def synthesize_cluster(self, cluster: Cluster,
                           thoughts: List[Thought]) -> Optional[Thought]:
        """Propose a new hypothesis from a cluster of related thoughts.

        Args:
            cluster: The cluster to synthesize from.
            thoughts: The actual Thought objects in this cluster.

        Returns:
            A new Thought with is_hypothesis=True, or None if synthesis failed.
        """
        if len(thoughts) < self._min_cluster_size:
            return None

        client = self._get_ollama()
        if client is None:
            return None

        ideas_text = format_thoughts_for_prompt(thoughts, max_items=10)
        prompt = SYNTHESIS_PROMPT.format(
            cluster_name=cluster.name,
            ideas_text=ideas_text,
        )

        for model in [self._model, self._fallback]:
            try:
                response = client.chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYNTHESIS_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                )
                content = response.get("message", {}).get("content", "")
                if not content:
                    continue

                result = self._parse_synthesis_response(content)
                if result and result.get("confidence", 0) >= self._min_confidence:
                    hypothesis = Thought(
                        text=result["text"],
                        tags=result.get("tags", []),
                        source="synthesis",
                        is_hypothesis=True,
                        cluster_id=cluster.id,
                        metadata={
                            "confidence": result.get("confidence", 0.5),
                            "rationale": result.get("rationale", ""),
                            "source_cluster": cluster.name,
                            "source_thought_count": len(thoughts),
                        },
                    )
                    cluster.synthesis_count += 1
                    _log.info("Synthesized hypothesis from cluster '%s': %s",
                              cluster.name, hypothesis.text[:80])
                    return hypothesis

            except Exception as e:
                _log.debug("Synthesis failed with %s: %s", model, e)
                continue

        return None

    def synthesize_all(self, clusters: List[Cluster],
                       get_thoughts_fn) -> SynthesisResult:
        """Run synthesis across all eligible clusters.

        Args:
            clusters: List of clusters to process.
            get_thoughts_fn: Callable(cluster_id) → List[Thought].

        Returns:
            SynthesisResult with summary statistics.
        """
        result = SynthesisResult()

        eligible = [c for c in clusters if c.size >= self._min_cluster_size]
        result.clusters_found = len(eligible)

        for cluster in eligible:
            thoughts = get_thoughts_fn(cluster.id)
            if not thoughts:
                continue

            hypothesis = self.synthesize_cluster(cluster, thoughts)
            if hypothesis:
                result.hypotheses_created += 1
                result.thought_ids.append(hypothesis.id)

        result.ok = True
        _log.info("Synthesis complete: %d hypotheses from %d clusters",
                  result.hypotheses_created, result.clusters_found)
        return result

    def name_cluster(self, thoughts: List[Thought]) -> Optional[Dict]:
        """Use LLM to generate a descriptive name for a cluster.

        Returns dict with "name" and "description", or None on failure.
        """
        client = self._get_ollama()
        if client is None or len(thoughts) < 2:
            return None

        ideas_text = format_thoughts_for_prompt(thoughts, max_items=8)
        prompt = CLUSTER_NAME_PROMPT.format(ideas_text=ideas_text)

        for model in [self._model, self._fallback]:
            try:
                response = client.chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": CLUSTER_NAME_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                )
                content = response.get("message", {}).get("content", "")
                if not content:
                    continue

                result = self._parse_json_response(content)
                if result and "name" in result:
                    return result

            except Exception as e:
                _log.debug("Cluster naming failed with %s: %s", model, e)
                continue

        return None

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_synthesis_response(self, content: str) -> Optional[Dict]:
        """Parse the LLM's synthesis JSON response."""
        return self._parse_json_response(content, required_keys=["text"])

    @staticmethod
    def _parse_json_response(content: str,
                             required_keys: Optional[List[str]] = None) -> Optional[Dict]:
        """Generic JSON response parser with deepseek-r1 think-block stripping."""
        # Strip markdown fences
        content = re.sub(r"```(?:json)?\s*", "", content)
        content = content.strip().rstrip("```")

        # Strip <think> blocks from deepseek-r1
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        content = content.strip()

        # Find JSON object
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None

        try:
            data = json.loads(match.group())
            if isinstance(data, dict):
                if required_keys:
                    if all(k in data for k in required_keys):
                        return data
                    return None
                return data
        except json.JSONDecodeError:
            pass

        return None
