"""Nexus — Neural Organizer engine.

A standalone knowledge graph that ingests raw data (text, files, transcripts),
splits it into atomic ideas, embeds them as vectors, builds a graph of
connections, and synthesizes new ideas from clusters.

Standalone — no hard dependencies on OnyxKraken. Uses Ollama for LLM + embeddings.

Usage:
    from nexus import NexusEngine

    engine = NexusEngine()
    engine.ingest("Your raw text or file path here")
    results = engine.query("focus and productivity")
    engine.synthesize()
    print(engine.status())
"""

from nexus.models import (
    Thought,
    ThoughtLink,
    Cluster,
    IngestResult,
    QueryResult,
    SynthesisResult,
)
from nexus.config import NexusConfig
from nexus.engine import NexusEngine
