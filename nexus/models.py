"""Nexus data models — the atoms of the knowledge graph.

All models are plain dataclasses with JSON serialization.
No external dependencies.
"""

import hashlib
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Thought — a single atomic idea (graph node)
# ---------------------------------------------------------------------------

@dataclass
class Thought:
    """One atomic idea extracted from raw input.

    Attributes:
        id: Unique hash-based identifier.
        text: The idea content (typically 50-200 words).
        tags: Auto-generated topic tags (e.g. ["productivity", "habits"]).
        source: Where this came from ("voice", "file:notes.md", "manual").
        source_file: Original file path if ingested from a file.
        created_at: Unix timestamp of creation.
        updated_at: Unix timestamp of last modification.
        access_count: How many times this thought has been queried/traversed.
        embedding: Cached vector (list of floats). None if not yet computed.
        is_hypothesis: True if this was synthesized, not directly ingested.
        cluster_id: Which cluster this thought belongs to (if any).
        metadata: Arbitrary extra data.
    """
    id: str = ""
    text: str = ""
    tags: List[str] = field(default_factory=list)
    source: str = ""
    source_file: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    access_count: int = 0
    embedding: Optional[List[float]] = field(default=None, repr=False)
    is_hypothesis: bool = False
    cluster_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.updated_at:
            self.updated_at = self.created_at
        if not self.id:
            self.id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate a deterministic ID from text + timestamp."""
        raw = f"{self.text[:200]}:{self.created_at}"
        return "t_" + hashlib.sha256(raw.encode()).hexdigest()[:12]

    def touch(self):
        """Mark as accessed."""
        self.access_count += 1
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-safe dict (excludes embedding by default)."""
        d = asdict(self)
        d.pop("embedding", None)
        return d

    def to_dict_full(self) -> Dict[str, Any]:
        """Serialize including embedding vector."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Thought":
        """Deserialize from dict."""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# ThoughtLink — a weighted edge between two thoughts
# ---------------------------------------------------------------------------

@dataclass
class ThoughtLink:
    """A connection between two thoughts (graph edge).

    Attributes:
        source_id: ID of the source thought.
        target_id: ID of the target thought.
        weight: Similarity score (0.0–1.0). Higher = stronger connection.
        link_type: How this link was created:
            "similarity" — auto-detected via embedding cosine.
            "manual" — user explicitly linked them.
            "synthesis" — created during hypothesis generation.
        reason: Human-readable explanation of why they're linked.
        created_at: Unix timestamp.
    """
    source_id: str = ""
    target_id: str = ""
    weight: float = 0.0
    link_type: str = "similarity"
    reason: str = ""
    created_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    @property
    def edge_key(self) -> str:
        """Canonical key — always sorted so A→B == B→A."""
        a, b = sorted([self.source_id, self.target_id])
        return f"{a}:{b}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ThoughtLink":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Cluster — a group of related thoughts (emergent theme)
# ---------------------------------------------------------------------------

@dataclass
class Cluster:
    """A group of semantically related thoughts forming a theme.

    Attributes:
        id: Unique cluster identifier.
        name: Auto-generated theme name (e.g. "productivity loops").
        thought_ids: IDs of thoughts in this cluster.
        centroid: Average embedding vector of all thoughts in the cluster.
        created_at: Unix timestamp.
        updated_at: Last time this cluster was modified.
        synthesis_count: How many hypothesis nodes were generated from this cluster.
    """
    id: str = ""
    name: str = ""
    thought_ids: List[str] = field(default_factory=list)
    centroid: Optional[List[float]] = field(default=None, repr=False)
    created_at: float = 0.0
    updated_at: float = 0.0
    synthesis_count: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.updated_at:
            self.updated_at = self.created_at
        if not self.id:
            self.id = "c_" + hashlib.md5(
                f"{self.name}:{self.created_at}".encode()
            ).hexdigest()[:10]

    @property
    def size(self) -> int:
        return len(self.thought_ids)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("centroid", None)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Cluster":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Result types — returned by engine operations
# ---------------------------------------------------------------------------

@dataclass
class IngestResult:
    """Result of ingesting raw input.

    Attributes:
        ok: Whether ingestion succeeded.
        thoughts_created: Number of new thought nodes created.
        thoughts_merged: Number of existing thoughts that were updated (dedup).
        links_created: Number of new edges created.
        source: What was ingested (filename, "voice", "manual").
        error: Error message if ok is False.
        thought_ids: IDs of all created/updated thoughts.
    """
    ok: bool = True
    thoughts_created: int = 0
    thoughts_merged: int = 0
    links_created: int = 0
    source: str = ""
    error: str = ""
    thought_ids: List[str] = field(default_factory=list)


@dataclass
class QueryResult:
    """Result of a graph query.

    Attributes:
        thoughts: Matching thoughts, sorted by relevance.
        links: Edges connecting the returned thoughts.
        clusters: Clusters that contain matching thoughts.
        query: The original query string.
        total_matches: Total matches before limit was applied.
    """
    thoughts: List[Thought] = field(default_factory=list)
    links: List[ThoughtLink] = field(default_factory=list)
    clusters: List[Cluster] = field(default_factory=list)
    query: str = ""
    total_matches: int = 0


@dataclass
class SynthesisResult:
    """Result of a synthesis pass.

    Attributes:
        ok: Whether synthesis succeeded.
        hypotheses_created: Number of new hypothesis thoughts.
        clusters_found: Number of clusters that triggered synthesis.
        error: Error message if ok is False.
        thought_ids: IDs of new hypothesis thoughts.
    """
    ok: bool = True
    hypotheses_created: int = 0
    clusters_found: int = 0
    error: str = ""
    thought_ids: List[str] = field(default_factory=list)
