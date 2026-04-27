"""Nexus configuration — models, thresholds, paths.

Standalone defaults that work with a local Ollama install.
All values can be overridden at construction time.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NexusConfig:
    """Configuration for the Nexus engine.

    Attributes:
        data_dir: Root directory for all Nexus data (graph, vectors, raw files).
        ollama_host: Ollama server URL.
        llm_model: Model for chunking, tagging, synthesis prompts.
        llm_fallback: Fallback model if primary is unavailable.
        embed_model: Model for generating embeddings.
        similarity_threshold: Minimum cosine similarity to create an edge (0.0–1.0).
        merge_threshold: Cosine similarity above which two thoughts are merged (dedup).
        cluster_min_size: Minimum thoughts in a cluster to trigger synthesis.
        cluster_distance: Maximum distance between thoughts in the same cluster.
        max_chunk_words: Target maximum words per atomic thought.
        min_chunk_words: Minimum words — shorter chunks get merged with neighbors.
        max_thoughts: Safety cap on total thoughts in the graph.
        max_links: Safety cap on total edges.
        synthesis_interval: Seconds between background synthesis passes (0 = manual only).
        watch_dirs: Directories to watch for new files (empty = no watching).
        auto_file: Whether to auto-organize ingested files into data_dir subfolders.
        log_level: Logging level for Nexus components.
    """
    data_dir: str = ""
    ollama_host: str = "http://localhost:11434"
    llm_model: str = "deepseek-r1:14b"
    llm_fallback: str = "llama3.2:3b"
    embed_model: str = "nomic-embed-text"
    similarity_threshold: float = 0.75
    merge_threshold: float = 0.95
    cluster_min_size: int = 3
    cluster_distance: float = 0.30
    max_chunk_words: int = 150
    min_chunk_words: int = 10
    max_thoughts: int = 10000
    max_links: int = 50000
    synthesis_interval: float = 0.0
    watch_dirs: list = field(default_factory=list)
    auto_file: bool = True
    log_level: str = "INFO"

    def __post_init__(self):
        if not self.data_dir:
            self.data_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data", "nexus",
            )

    @property
    def raw_dir(self) -> str:
        """Directory for raw ingested files."""
        return os.path.join(self.data_dir, "raw")

    @property
    def processed_dir(self) -> str:
        """Directory for processed/chunked output."""
        return os.path.join(self.data_dir, "processed")

    @property
    def graph_dir(self) -> str:
        """Directory for graph data (nodes.json, edges.json)."""
        return os.path.join(self.data_dir, "graph")

    @property
    def vectors_dir(self) -> str:
        """Directory for cached embedding vectors."""
        return os.path.join(self.data_dir, "vectors")

    @property
    def archive_dir(self) -> str:
        """Directory for nightly graph backups."""
        return os.path.join(self.data_dir, "archive")

    def ensure_dirs(self):
        """Create all data directories if they don't exist."""
        for d in [self.data_dir, self.raw_dir, self.processed_dir,
                  self.graph_dir, self.vectors_dir, self.archive_dir]:
            os.makedirs(d, exist_ok=True)
