"""Nexus ThoughtGraph — NetworkX-based knowledge graph.

Nodes = Thoughts (atomic ideas). Edges = ThoughtLinks (weighted similarity).
Supports:
  - Add/remove thoughts and links
  - Similarity-based auto-linking
  - Graph traversal (neighbors, shortest path, connected components)
  - Clustering via community detection
  - Persistence to/from JSON files
  - Graph statistics and health metrics
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional, Set, Tuple

from nexus.models import Thought, ThoughtLink, Cluster
from nexus.embeddings import NexusEmbeddings, cosine_similarity, centroid

_log = logging.getLogger("nexus.graph")

try:
    import networkx as nx
    _HAS_NX = True
except ImportError:
    _HAS_NX = False
    _log.warning("networkx not installed. Graph features will be limited.")


class ThoughtGraph:
    """Knowledge graph with vector-based auto-linking and clustering.

    The graph stores:
      - Thoughts as nodes (keyed by thought.id)
      - ThoughtLinks as weighted edges
      - Clusters as metadata over groups of nodes

    Persistence: nodes.json, edges.json, clusters.json in the graph directory.
    """

    def __init__(self, graph_dir: str = "",
                 embeddings: Optional[NexusEmbeddings] = None,
                 similarity_threshold: float = 0.75,
                 merge_threshold: float = 0.95):
        self._graph_dir = graph_dir
        self._embeddings = embeddings
        self._similarity_threshold = similarity_threshold
        self._merge_threshold = merge_threshold

        # Internal stores
        self._thoughts: Dict[str, Thought] = {}
        self._links: Dict[str, ThoughtLink] = {}  # keyed by edge_key
        self._clusters: Dict[str, Cluster] = {}

        # NetworkX graph (optional — degrades gracefully without it)
        self._nx: Optional[object] = None
        if _HAS_NX:
            self._nx = nx.Graph()

        # Load existing data
        if graph_dir:
            self._load()

    # ------------------------------------------------------------------
    # Thought operations
    # ------------------------------------------------------------------

    def add_thought(self, thought: Thought, auto_link: bool = True) -> Thought:
        """Add a thought to the graph.

        If auto_link is True, computes embedding and links to similar thoughts.

        Returns the thought (possibly merged if a near-duplicate was found).
        """
        # Check for near-duplicate
        if self._embeddings and thought.embedding is None:
            thought.embedding = self._embeddings.embed(thought.text)

        merged = self._check_merge(thought)
        if merged:
            _log.info("Merged thought %s into existing %s (dedup)", thought.id, merged.id)
            return merged

        self._thoughts[thought.id] = thought
        if _HAS_NX and self._nx is not None:
            self._nx.add_node(thought.id, thought=thought)

        if auto_link:
            self._auto_link(thought)

        return thought

    def get_thought(self, thought_id: str) -> Optional[Thought]:
        """Get a thought by ID."""
        t = self._thoughts.get(thought_id)
        if t:
            t.touch()
        return t

    def remove_thought(self, thought_id: str) -> bool:
        """Remove a thought and all its edges."""
        if thought_id not in self._thoughts:
            return False

        # Remove edges
        to_remove = [k for k, link in self._links.items()
                     if link.source_id == thought_id or link.target_id == thought_id]
        for k in to_remove:
            del self._links[k]

        # Remove from clusters
        for cluster in self._clusters.values():
            if thought_id in cluster.thought_ids:
                cluster.thought_ids.remove(thought_id)

        # Remove from NetworkX
        if _HAS_NX and self._nx is not None and self._nx.has_node(thought_id):
            self._nx.remove_node(thought_id)

        del self._thoughts[thought_id]
        return True

    def get_all_thoughts(self) -> List[Thought]:
        """Get all thoughts in the graph."""
        return list(self._thoughts.values())

    def search_thoughts(self, query: str, limit: int = 10,
                        tags: Optional[List[str]] = None) -> List[Tuple[float, Thought]]:
        """Search thoughts by semantic similarity and/or tags.

        Returns list of (score, thought) tuples sorted by relevance.
        """
        results: List[Tuple[float, Thought]] = []

        # Filter by tags if specified
        candidates = list(self._thoughts.values())
        if tags:
            tag_set = set(t.lower() for t in tags)
            candidates = [t for t in candidates
                          if tag_set & set(tg.lower() for tg in t.tags)]

        if not candidates:
            return []

        # Embedding search
        if self._embeddings and self._embeddings.is_available():
            query_vec = self._embeddings.embed(query)
            if query_vec:
                for thought in candidates:
                    vec = thought.embedding or self._embeddings.embed(thought.text)
                    if vec:
                        score = cosine_similarity(query_vec, vec)
                        results.append((score, thought))

        # Keyword fallback if no embedding results
        if not results:
            query_words = set(query.lower().split())
            for thought in candidates:
                text_words = set(thought.text.lower().split())
                overlap = len(query_words & text_words)
                if overlap > 0:
                    score = min(1.0, overlap * 0.15)
                    results.append((score, thought))

        results.sort(key=lambda x: x[0], reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------
    # Link operations
    # ------------------------------------------------------------------

    def add_link(self, link: ThoughtLink) -> ThoughtLink:
        """Add a link (edge) between two thoughts."""
        if link.source_id not in self._thoughts or link.target_id not in self._thoughts:
            _log.warning("Cannot link %s → %s: one or both thoughts missing",
                         link.source_id, link.target_id)
            return link

        self._links[link.edge_key] = link

        if _HAS_NX and self._nx is not None:
            self._nx.add_edge(link.source_id, link.target_id,
                              weight=link.weight, link=link)

        return link

    def get_links(self, thought_id: str) -> List[ThoughtLink]:
        """Get all links connected to a thought."""
        return [link for link in self._links.values()
                if link.source_id == thought_id or link.target_id == thought_id]

    def get_neighbors(self, thought_id: str, depth: int = 1) -> List[Thought]:
        """Get thoughts connected within N hops."""
        if _HAS_NX and self._nx is not None and self._nx.has_node(thought_id):
            neighbor_ids: Set[str] = set()
            current_layer = {thought_id}

            for _ in range(depth):
                next_layer: Set[str] = set()
                for nid in current_layer:
                    if self._nx.has_node(nid):
                        for neighbor in self._nx.neighbors(nid):
                            if neighbor != thought_id:
                                next_layer.add(neighbor)
                neighbor_ids.update(next_layer)
                current_layer = next_layer

            return [self._thoughts[nid] for nid in neighbor_ids
                    if nid in self._thoughts]

        # Fallback without NetworkX
        visited: Set[str] = set()
        current = {thought_id}

        for _ in range(depth):
            next_set: Set[str] = set()
            for tid in current:
                for link in self.get_links(tid):
                    other = link.target_id if link.source_id == tid else link.source_id
                    if other != thought_id and other not in visited:
                        next_set.add(other)
            visited.update(next_set)
            current = next_set

        return [self._thoughts[tid] for tid in visited if tid in self._thoughts]

    def get_shortest_path(self, source_id: str, target_id: str) -> List[Thought]:
        """Find the shortest path between two thoughts."""
        if not _HAS_NX or self._nx is None:
            return []
        try:
            path_ids = nx.shortest_path(self._nx, source_id, target_id)
            return [self._thoughts[nid] for nid in path_ids if nid in self._thoughts]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    # ------------------------------------------------------------------
    # Auto-linking
    # ------------------------------------------------------------------

    def _auto_link(self, thought: Thought):
        """Create edges from a new thought to similar existing thoughts."""
        if not self._embeddings or thought.embedding is None:
            return

        links_created = 0
        for other_id, other in self._thoughts.items():
            if other_id == thought.id:
                continue
            if other.embedding is None:
                continue

            score = cosine_similarity(thought.embedding, other.embedding)
            if score >= self._similarity_threshold:
                link = ThoughtLink(
                    source_id=thought.id,
                    target_id=other.id,
                    weight=score,
                    link_type="similarity",
                    reason=f"Cosine similarity: {score:.3f}",
                )
                if link.edge_key not in self._links:
                    self.add_link(link)
                    links_created += 1

        if links_created:
            _log.info("Auto-linked thought %s to %d existing thoughts",
                      thought.id, links_created)

    def relink_all(self):
        """Recompute all similarity-based links. Expensive but thorough."""
        # Remove all similarity links
        to_remove = [k for k, link in self._links.items()
                     if link.link_type == "similarity"]
        for k in to_remove:
            del self._links[k]
            if _HAS_NX and self._nx is not None:
                link = self._links.get(k)

        # Rebuild NetworkX edges
        if _HAS_NX and self._nx is not None:
            self._nx.clear_edges()

        # Re-link each thought
        for thought in self._thoughts.values():
            self._auto_link(thought)

    # ------------------------------------------------------------------
    # Dedup / merge
    # ------------------------------------------------------------------

    def _check_merge(self, new_thought: Thought) -> Optional[Thought]:
        """Check if new_thought is a near-duplicate of an existing thought.

        Returns the existing thought if merged, None otherwise.
        """
        if not self._embeddings or new_thought.embedding is None:
            return None

        for existing in self._thoughts.values():
            if existing.embedding is None:
                continue
            score = cosine_similarity(new_thought.embedding, existing.embedding)
            if score >= self._merge_threshold:
                # Merge: keep existing, update text if new is longer
                if len(new_thought.text) > len(existing.text):
                    existing.text = new_thought.text
                    existing.embedding = new_thought.embedding
                # Merge tags
                existing.tags = list(set(existing.tags + new_thought.tags))
                existing.updated_at = time.time()
                existing.access_count += 1
                return existing

        return None

    # ------------------------------------------------------------------
    # Clustering
    # ------------------------------------------------------------------

    def cluster(self, min_size: int = 3,
                max_distance: float = 0.30) -> List[Cluster]:
        """Cluster thoughts into themes using connected components + embedding proximity.

        Strategy:
          1. Use NetworkX connected components if available.
          2. Further split large components by embedding distance.
          3. Name each cluster via tags or LLM.

        Returns list of Cluster objects (also stored internally).
        """
        if not self._thoughts:
            return []

        # Get connected components
        components: List[Set[str]] = []
        if _HAS_NX and self._nx is not None and self._nx.number_of_nodes() > 0:
            for comp in nx.connected_components(self._nx):
                if len(comp) >= min_size:
                    components.append(comp)
        else:
            # Fallback: group by shared edges
            visited: Set[str] = set()
            for tid in self._thoughts:
                if tid in visited:
                    continue
                group = self._bfs_component(tid)
                visited.update(group)
                if len(group) >= min_size:
                    components.append(group)

        # Build Cluster objects
        new_clusters: List[Cluster] = []
        for comp in components:
            thought_ids = sorted(comp)
            thoughts = [self._thoughts[tid] for tid in thought_ids if tid in self._thoughts]

            # Compute centroid
            vecs = [t.embedding for t in thoughts if t.embedding is not None]
            c = centroid(vecs) if vecs else None

            # Name from most common tags
            tag_freq: Dict[str, int] = {}
            for t in thoughts:
                for tag in t.tags:
                    tag_freq[tag] = tag_freq.get(tag, 0) + 1
            top_tags = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)[:3]
            name = " + ".join(t for t, _ in top_tags) if top_tags else f"cluster_{len(new_clusters)}"

            cluster = Cluster(
                name=name,
                thought_ids=thought_ids,
                centroid=c,
            )
            new_clusters.append(cluster)

            # Assign cluster_id to member thoughts
            for tid in thought_ids:
                if tid in self._thoughts:
                    self._thoughts[tid].cluster_id = cluster.id

        self._clusters = {c.id: c for c in new_clusters}
        _log.info("Clustering complete: %d clusters from %d thoughts",
                  len(new_clusters), len(self._thoughts))
        return new_clusters

    def get_cluster(self, cluster_id: str) -> Optional[Cluster]:
        return self._clusters.get(cluster_id)

    def get_clusters(self) -> List[Cluster]:
        return list(self._clusters.values())

    def get_cluster_thoughts(self, cluster_id: str) -> List[Thought]:
        """Get all thoughts in a specific cluster."""
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            return []
        return [self._thoughts[tid] for tid in cluster.thought_ids
                if tid in self._thoughts]

    def _bfs_component(self, start_id: str) -> Set[str]:
        """BFS to find all connected nodes from start_id (fallback without NX)."""
        visited = {start_id}
        queue = [start_id]
        while queue:
            current = queue.pop(0)
            for link in self.get_links(current):
                other = link.target_id if link.source_id == current else link.source_id
                if other not in visited:
                    visited.add(other)
                    queue.append(other)
        return visited

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self):
        """Save the graph to disk (nodes.json, edges.json, clusters.json)."""
        if not self._graph_dir:
            return
        os.makedirs(self._graph_dir, exist_ok=True)

        # Nodes (with embeddings in separate file for size)
        nodes_path = os.path.join(self._graph_dir, "nodes.json")
        nodes_data = [t.to_dict() for t in self._thoughts.values()]
        with open(nodes_path, "w", encoding="utf-8") as f:
            json.dump(nodes_data, f, indent=2)

        # Embeddings (separate for efficiency)
        vecs_path = os.path.join(self._graph_dir, "vectors.json")
        vecs_data = {}
        for tid, thought in self._thoughts.items():
            if thought.embedding:
                vecs_data[tid] = thought.embedding
        with open(vecs_path, "w", encoding="utf-8") as f:
            json.dump(vecs_data, f)

        # Edges
        edges_path = os.path.join(self._graph_dir, "edges.json")
        edges_data = [link.to_dict() for link in self._links.values()]
        with open(edges_path, "w", encoding="utf-8") as f:
            json.dump(edges_data, f, indent=2)

        # Clusters
        clusters_path = os.path.join(self._graph_dir, "clusters.json")
        clusters_data = [c.to_dict() for c in self._clusters.values()]
        with open(clusters_path, "w", encoding="utf-8") as f:
            json.dump(clusters_data, f, indent=2)

        _log.info("Saved graph: %d nodes, %d edges, %d clusters",
                  len(self._thoughts), len(self._links), len(self._clusters))

    def _load(self):
        """Load graph from disk."""
        if not self._graph_dir or not os.path.isdir(self._graph_dir):
            return

        # Nodes
        nodes_path = os.path.join(self._graph_dir, "nodes.json")
        if os.path.exists(nodes_path):
            try:
                with open(nodes_path, "r", encoding="utf-8") as f:
                    nodes_data = json.load(f)
                for nd in nodes_data:
                    t = Thought.from_dict(nd)
                    self._thoughts[t.id] = t
                    if _HAS_NX and self._nx is not None:
                        self._nx.add_node(t.id, thought=t)
            except (json.JSONDecodeError, IOError) as e:
                _log.warning("Failed to load nodes: %s", e)

        # Embeddings
        vecs_path = os.path.join(self._graph_dir, "vectors.json")
        if os.path.exists(vecs_path):
            try:
                with open(vecs_path, "r", encoding="utf-8") as f:
                    vecs_data = json.load(f)
                for tid, vec in vecs_data.items():
                    if tid in self._thoughts:
                        self._thoughts[tid].embedding = vec
            except (json.JSONDecodeError, IOError) as e:
                _log.debug("Failed to load vectors: %s", e)

        # Edges
        edges_path = os.path.join(self._graph_dir, "edges.json")
        if os.path.exists(edges_path):
            try:
                with open(edges_path, "r", encoding="utf-8") as f:
                    edges_data = json.load(f)
                for ed in edges_data:
                    link = ThoughtLink.from_dict(ed)
                    self._links[link.edge_key] = link
                    if _HAS_NX and self._nx is not None:
                        self._nx.add_edge(link.source_id, link.target_id,
                                          weight=link.weight, link=link)
            except (json.JSONDecodeError, IOError) as e:
                _log.warning("Failed to load edges: %s", e)

        # Clusters
        clusters_path = os.path.join(self._graph_dir, "clusters.json")
        if os.path.exists(clusters_path):
            try:
                with open(clusters_path, "r", encoding="utf-8") as f:
                    clusters_data = json.load(f)
                for cd in clusters_data:
                    c = Cluster.from_dict(cd)
                    self._clusters[c.id] = c
            except (json.JSONDecodeError, IOError) as e:
                _log.debug("Failed to load clusters: %s", e)

        _log.info("Loaded graph: %d nodes, %d edges, %d clusters",
                  len(self._thoughts), len(self._links), len(self._clusters))

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def node_count(self) -> int:
        return len(self._thoughts)

    @property
    def edge_count(self) -> int:
        return len(self._links)

    @property
    def cluster_count(self) -> int:
        return len(self._clusters)

    def density(self) -> float:
        """Graph density: ratio of actual edges to possible edges."""
        n = self.node_count
        if n < 2:
            return 0.0
        max_edges = n * (n - 1) / 2
        return self.edge_count / max_edges

    def status(self) -> Dict:
        """Full graph status report."""
        tag_freq: Dict[str, int] = {}
        for t in self._thoughts.values():
            for tag in t.tags:
                tag_freq[tag] = tag_freq.get(tag, 0) + 1
        top_tags = sorted(tag_freq.items(), key=lambda x: x[1], reverse=True)[:10]

        hypotheses = sum(1 for t in self._thoughts.values() if t.is_hypothesis)
        unlinked = sum(1 for t in self._thoughts.values()
                       if not any(l.source_id == t.id or l.target_id == t.id
                                  for l in self._links.values()))

        return {
            "nodes": self.node_count,
            "edges": self.edge_count,
            "clusters": self.cluster_count,
            "density": round(self.density(), 4),
            "hypotheses": hypotheses,
            "unlinked_nodes": unlinked,
            "top_tags": top_tags,
        }
