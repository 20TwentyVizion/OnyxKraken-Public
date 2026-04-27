"""Nexus Engine — main API orchestrator for the Neural Organizer.

Single entry point for all operations:
  - ingest(text_or_path) → chunks, embeds, graphs, files
  - query(search_string) → ranked thoughts + connections
  - synthesize() → new hypothesis nodes from clusters
  - status() → graph stats, health metrics
  - traverse(thought_id, depth) → connected subgraph

Standalone — uses Ollama directly. No OnyxKraken dependencies.
Star Trek computer mode: daemon-like, no personality, declarative output.
"""

import logging
import os
import time
from typing import Dict, List, Optional, Union

from nexus.config import NexusConfig
from nexus.models import (
    Thought, ThoughtLink, Cluster,
    IngestResult, QueryResult, SynthesisResult,
)
from nexus.embeddings import NexusEmbeddings
from nexus.chunker import ThoughtChunker
from nexus.graph import ThoughtGraph
from nexus.ingest import IntakePipeline
from nexus.synthesis import SynthesisEngine
from nexus.watcher import FolderWatcher

_log = logging.getLogger("nexus.engine")


class NexusEngine:
    """Main orchestrator for the Nexus Neural Organizer.

    Usage:
        engine = NexusEngine()
        result = engine.ingest("Your raw text here")
        results = engine.query("productivity habits")
        engine.synthesize()
        print(engine.status())
    """

    def __init__(self, config: Optional[NexusConfig] = None):
        self._config = config or NexusConfig()
        self._config.ensure_dirs()

        # Initialize subsystems
        self._embeddings = NexusEmbeddings(
            model=self._config.embed_model,
            cache_path=os.path.join(self._config.vectors_dir, "embed_cache.json"),
            ollama_host=self._config.ollama_host,
        )
        self._chunker = ThoughtChunker(
            llm_model=self._config.llm_model,
            llm_fallback=self._config.llm_fallback,
            max_words=self._config.max_chunk_words,
            min_words=self._config.min_chunk_words,
            ollama_host=self._config.ollama_host,
        )
        self._graph = ThoughtGraph(
            graph_dir=self._config.graph_dir,
            embeddings=self._embeddings,
            similarity_threshold=self._config.similarity_threshold,
            merge_threshold=self._config.merge_threshold,
        )
        self._intake = IntakePipeline(
            raw_dir=self._config.raw_dir,
            auto_file=self._config.auto_file,
        )
        self._synthesis = SynthesisEngine(
            llm_model=self._config.llm_model,
            llm_fallback=self._config.llm_fallback,
            min_cluster_size=self._config.cluster_min_size,
        )
        self._watcher: Optional[FolderWatcher] = None

        _log.info("NexusEngine initialized. Graph: %d nodes, %d edges.",
                  self._graph.node_count, self._graph.edge_count)

    # ------------------------------------------------------------------
    # Ingest — the primary input method
    # ------------------------------------------------------------------

    def ingest(self, input_data: str, source: str = "") -> IngestResult:
        """Ingest raw text or a file path.

        If input_data is a path to an existing file, it's read and processed.
        If input_data is a path to a directory, all supported files are ingested.
        Otherwise, it's treated as raw text.

        Args:
            input_data: Raw text string, file path, or directory path.
            source: Optional source label (e.g. "voice", "upload").

        Returns:
            IngestResult with statistics about what was created/merged.
        """
        result = IngestResult()

        # Determine input type
        if os.path.isdir(input_data):
            return self._ingest_directory(input_data, source)
        elif os.path.isfile(input_data):
            return self._ingest_file(input_data, source)
        else:
            return self._ingest_text(input_data, source)

    def _ingest_text(self, text: str, source: str = "") -> IngestResult:
        """Ingest raw text string."""
        result = IngestResult(source=source or "manual")

        # Intake: clean + dedup
        intake_data = self._intake.ingest_text(text, source=source or "manual")
        if intake_data is None:
            result.ok = False
            result.error = "Empty or duplicate input."
            return result

        # Chunk: split into atomic thoughts
        thoughts = self._chunker.chunk(
            intake_data["text"],
            source=intake_data["source"],
            source_file=intake_data.get("source_file", ""),
        )

        if not thoughts:
            # If chunker returns nothing, create a single thought from the raw text
            if len(text.split()) >= self._config.min_chunk_words:
                thoughts = self._chunker.chunk_without_llm(
                    intake_data["text"],
                    source=intake_data["source"],
                    source_file=intake_data.get("source_file", ""),
                )

        # Graph: add each thought, auto-link
        for thought in thoughts:
            added = self._graph.add_thought(thought, auto_link=True)
            if added.id == thought.id:
                result.thoughts_created += 1
            else:
                result.thoughts_merged += 1
            result.thought_ids.append(added.id)

        # Count new links
        result.links_created = self._graph.edge_count  # approximate

        # Save graph
        self._graph.save()
        self._intake.save_manifest()
        self._embeddings.save_cache()

        _log.info("Ingested: %d thoughts created, %d merged. Source: %s",
                  result.thoughts_created, result.thoughts_merged, result.source)
        return result

    def _ingest_file(self, file_path: str, source: str = "") -> IngestResult:
        """Ingest a single file."""
        result = IngestResult(source=source or f"file:{os.path.basename(file_path)}")

        intake_data = self._intake.ingest_file(file_path)
        if intake_data is None:
            result.ok = False
            result.error = f"Could not read or duplicate: {file_path}"
            return result

        # Chunk directly (intake already did dedup + filing)
        thoughts = self._chunker.chunk(
            intake_data["text"],
            source=intake_data["source"],
            source_file=intake_data.get("source_file", ""),
        )
        if not thoughts:
            thoughts = self._chunker.chunk_without_llm(
                intake_data["text"],
                source=intake_data["source"],
                source_file=intake_data.get("source_file", ""),
            )

        for thought in thoughts:
            added = self._graph.add_thought(thought, auto_link=True)
            if added.id == thought.id:
                result.thoughts_created += 1
            else:
                result.thoughts_merged += 1
            result.thought_ids.append(added.id)

        self._graph.save()
        self._intake.save_manifest()
        self._embeddings.save_cache()
        return result

    def _ingest_directory(self, dir_path: str, source: str = "") -> IngestResult:
        """Ingest all supported files from a directory."""
        result = IngestResult(source=source or f"dir:{os.path.basename(dir_path)}")

        file_dicts = self._intake.ingest_directory(dir_path)
        for fd in file_dicts:
            sub_result = self._ingest_text(fd["text"], source=fd["source"])
            result.thoughts_created += sub_result.thoughts_created
            result.thoughts_merged += sub_result.thoughts_merged
            result.thought_ids.extend(sub_result.thought_ids)

        return result

    # ------------------------------------------------------------------
    # Query — search the knowledge graph
    # ------------------------------------------------------------------

    def query(self, search: str, limit: int = 10,
              tags: Optional[List[str]] = None,
              depth: int = 1) -> QueryResult:
        """Search the knowledge graph.

        Args:
            search: Natural language query string.
            limit: Max thoughts to return.
            tags: Optional tag filter.
            depth: How many hops to traverse from matches (0 = exact matches only).

        Returns:
            QueryResult with matching thoughts, their links, and clusters.
        """
        qr = QueryResult(query=search)

        # Semantic + keyword search
        matches = self._graph.search_thoughts(search, limit=limit, tags=tags)
        qr.total_matches = len(matches)

        # Expand by depth
        seen_ids = set()
        for score, thought in matches:
            thought.touch()
            qr.thoughts.append(thought)
            seen_ids.add(thought.id)

            if depth > 0:
                neighbors = self._graph.get_neighbors(thought.id, depth=depth)
                for neighbor in neighbors:
                    if neighbor.id not in seen_ids:
                        qr.thoughts.append(neighbor)
                        seen_ids.add(neighbor.id)

        # Collect links between returned thoughts
        for thought in qr.thoughts:
            links = self._graph.get_links(thought.id)
            for link in links:
                other_id = (link.target_id if link.source_id == thought.id
                            else link.source_id)
                if other_id in seen_ids:
                    qr.links.append(link)

        # Collect clusters
        cluster_ids = set()
        for thought in qr.thoughts:
            if thought.cluster_id and thought.cluster_id not in cluster_ids:
                cluster = self._graph.get_cluster(thought.cluster_id)
                if cluster:
                    qr.clusters.append(cluster)
                    cluster_ids.add(cluster.id)

        return qr

    def traverse(self, thought_id: str, depth: int = 2) -> QueryResult:
        """Traverse the graph from a specific thought.

        Returns all thoughts within N hops and their connections.
        """
        qr = QueryResult(query=f"traverse:{thought_id}")

        root = self._graph.get_thought(thought_id)
        if not root:
            return qr

        qr.thoughts.append(root)
        neighbors = self._graph.get_neighbors(thought_id, depth=depth)
        qr.thoughts.extend(neighbors)
        qr.total_matches = len(qr.thoughts)

        # Collect edges
        seen_ids = {t.id for t in qr.thoughts}
        for thought in qr.thoughts:
            for link in self._graph.get_links(thought.id):
                other_id = (link.target_id if link.source_id == thought.id
                            else link.source_id)
                if other_id in seen_ids:
                    qr.links.append(link)

        return qr

    # ------------------------------------------------------------------
    # Synthesis — generate new ideas from clusters
    # ------------------------------------------------------------------

    def synthesize(self) -> SynthesisResult:
        """Run synthesis across all eligible clusters.

        First re-clusters the graph, then proposes hypotheses.
        New hypothesis thoughts are added to the graph automatically.
        """
        # Re-cluster
        clusters = self._graph.cluster(
            min_size=self._config.cluster_min_size,
            max_distance=self._config.cluster_distance,
        )

        if not clusters:
            return SynthesisResult(ok=True, clusters_found=0)

        # Run synthesis
        result = self._synthesis.synthesize_all(
            clusters=clusters,
            get_thoughts_fn=self._graph.get_cluster_thoughts,
        )

        # Add hypotheses to the graph
        # The synthesis engine returns thought IDs, but we need to get the actual
        # Thought objects. Since synthesize_cluster returns Thought objects directly,
        # we need to handle this differently.
        # Re-run synthesis with graph integration:
        new_result = SynthesisResult()
        new_result.clusters_found = len([c for c in clusters
                                         if c.size >= self._config.cluster_min_size])

        for cluster in clusters:
            if cluster.size < self._config.cluster_min_size:
                continue
            thoughts = self._graph.get_cluster_thoughts(cluster.id)
            if not thoughts:
                continue

            hypothesis = self._synthesis.synthesize_cluster(cluster, thoughts)
            if hypothesis:
                # Embed the hypothesis
                if self._embeddings.is_available():
                    hypothesis.embedding = self._embeddings.embed(hypothesis.text)

                # Add to graph
                self._graph.add_thought(hypothesis, auto_link=True)

                # Create explicit synthesis links to source thoughts
                for source_thought in thoughts[:5]:
                    link = ThoughtLink(
                        source_id=hypothesis.id,
                        target_id=source_thought.id,
                        weight=0.8,
                        link_type="synthesis",
                        reason=f"Synthesized from cluster '{cluster.name}'",
                    )
                    self._graph.add_link(link)

                new_result.hypotheses_created += 1
                new_result.thought_ids.append(hypothesis.id)

        new_result.ok = True
        self._graph.save()

        _log.info("Synthesis complete: %d new hypotheses from %d clusters",
                  new_result.hypotheses_created, new_result.clusters_found)
        return new_result

    def cluster(self) -> List[Cluster]:
        """Re-cluster the graph and return clusters.

        Also attempts to name clusters via LLM.
        """
        clusters = self._graph.cluster(
            min_size=self._config.cluster_min_size,
            max_distance=self._config.cluster_distance,
        )

        # Try to name clusters via LLM
        for cluster in clusters:
            thoughts = self._graph.get_cluster_thoughts(cluster.id)
            name_data = self._synthesis.name_cluster(thoughts)
            if name_data:
                cluster.name = name_data.get("name", cluster.name)

        self._graph.save()
        return clusters

    # ------------------------------------------------------------------
    # File watching
    # ------------------------------------------------------------------

    def start_watching(self, dirs: Optional[List[str]] = None,
                       poll_interval: float = 5.0):
        """Start watching directories for new files.

        New files are auto-ingested through the full pipeline.
        """
        watch_dirs = dirs or self._config.watch_dirs
        if not watch_dirs:
            _log.info("No directories to watch.")
            return

        self._watcher = FolderWatcher(
            watch_dirs=watch_dirs,
            on_new_file=self._on_watched_file,
            poll_interval=poll_interval,
        )
        self._watcher.start()

    def stop_watching(self):
        """Stop watching for new files."""
        if self._watcher:
            self._watcher.stop()
            self._watcher = None

    def _on_watched_file(self, file_path: str):
        """Callback when the watcher detects a new file."""
        _log.info("New file detected: %s. Ingesting...", file_path)
        result = self.ingest(file_path)
        _log.info("Ingested %s: %d thoughts created, %d merged.",
                  os.path.basename(file_path),
                  result.thoughts_created, result.thoughts_merged)

    # ------------------------------------------------------------------
    # Status & management
    # ------------------------------------------------------------------

    def status(self) -> Dict:
        """Full system status — Star Trek computer style.

        Returns a flat dict with all metrics.
        """
        graph_status = self._graph.status()
        return {
            "engine": "nexus",
            "version": "1.0.0",
            **graph_status,
            "embeddings_available": self._embeddings.is_available(),
            "embeddings_cached": self._embeddings.cache_size,
            "files_processed": self._intake.processed_count,
            "watcher_active": self._watcher.is_running if self._watcher else False,
            "watcher_dirs": self._watcher.watched_dirs if self._watcher else [],
            "config": {
                "llm_model": self._config.llm_model,
                "embed_model": self._config.embed_model,
                "similarity_threshold": self._config.similarity_threshold,
                "merge_threshold": self._config.merge_threshold,
                "cluster_min_size": self._config.cluster_min_size,
            },
        }

    def get_thought(self, thought_id: str) -> Optional[Thought]:
        """Get a specific thought by ID."""
        return self._graph.get_thought(thought_id)

    def get_all_thoughts(self) -> List[Thought]:
        """Get all thoughts in the graph."""
        return self._graph.get_all_thoughts()

    def get_clusters(self) -> List[Cluster]:
        """Get all current clusters."""
        return self._graph.get_clusters()

    def save(self):
        """Persist all data to disk."""
        self._graph.save()
        self._intake.save_manifest()
        self._embeddings.save_cache()

    def shutdown(self):
        """Clean shutdown — stop watcher, save everything."""
        self.stop_watching()
        self.save()
        _log.info("NexusEngine shutdown complete.")

    # ------------------------------------------------------------------
    # Accessors for subsystems (for testing / advanced use)
    # ------------------------------------------------------------------

    @property
    def graph(self) -> ThoughtGraph:
        return self._graph

    @property
    def chunker(self) -> ThoughtChunker:
        return self._chunker

    @property
    def embeddings(self) -> NexusEmbeddings:
        return self._embeddings

    @property
    def config(self) -> NexusConfig:
        return self._config
