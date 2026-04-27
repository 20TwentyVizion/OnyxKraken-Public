"""Tests for the Nexus Neural Organizer — standalone knowledge graph engine.

Tests all components without requiring Ollama/LLM (uses rule-based fallbacks).
"""

import sys, os, json, time, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name}")
        failed += 1


# ---------------------------------------------------------------------------
# NX1: Data models
# ---------------------------------------------------------------------------

print("=== NX1: Data Models ===")

from nexus.models import Thought, ThoughtLink, Cluster, IngestResult, QueryResult, SynthesisResult

# Thought
t = Thought(text="Productivity habits form through neurological reward cycles.")
check("thought has id", t.id.startswith("t_"))
check("thought has text", "Productivity" in t.text)
check("thought has timestamp", t.created_at > 0)
check("thought tags empty", t.tags == [])
check("thought not hypothesis", not t.is_hypothesis)
check("thought access 0", t.access_count == 0)

t.touch()
check("thought touch increments", t.access_count == 1)
check("thought touch updates time", t.updated_at >= t.created_at)

d = t.to_dict()
check("to_dict excludes embedding", "embedding" not in d)
check("to_dict has text", d["text"] == t.text)

d_full = t.to_dict_full()
check("to_dict_full has embedding key", "embedding" in d_full)

t2 = Thought.from_dict(d_full)
check("from_dict restores text", t2.text == t.text)
check("from_dict restores id", t2.id == t.id)

# ThoughtLink
link = ThoughtLink(source_id="t_aaa", target_id="t_bbb", weight=0.85, link_type="similarity")
check("link source", link.source_id == "t_aaa")
check("link target", link.target_id == "t_bbb")
check("link weight", link.weight == 0.85)
check("link edge_key canonical", link.edge_key == "t_aaa:t_bbb")
# Reversed order should give same key
link2 = ThoughtLink(source_id="t_bbb", target_id="t_aaa", weight=0.85)
check("edge_key symmetric", link.edge_key == link2.edge_key)

ld = link.to_dict()
check("link to_dict", ld["weight"] == 0.85)
link3 = ThoughtLink.from_dict(ld)
check("link from_dict", link3.weight == 0.85)

# Cluster
c = Cluster(name="productivity loops", thought_ids=["t_1", "t_2", "t_3"])
check("cluster has id", c.id.startswith("c_"))
check("cluster name", c.name == "productivity loops")
check("cluster size", c.size == 3)
check("cluster timestamp", c.created_at > 0)

# Result types
ir = IngestResult(thoughts_created=3, thoughts_merged=1, links_created=5)
check("ingest result ok", ir.ok)
check("ingest created", ir.thoughts_created == 3)
check("ingest merged", ir.thoughts_merged == 1)

qr = QueryResult(query="focus", total_matches=5)
check("query result", qr.query == "focus")
check("query matches", qr.total_matches == 5)

sr = SynthesisResult(hypotheses_created=2, clusters_found=4)
check("synthesis result", sr.hypotheses_created == 2)


# ---------------------------------------------------------------------------
# NX1: Config
# ---------------------------------------------------------------------------

print("\n=== NX1: Config ===")

from nexus.config import NexusConfig

cfg = NexusConfig()
check("config has data_dir", len(cfg.data_dir) > 0)
check("config raw_dir", cfg.raw_dir.endswith("raw"))
check("config processed_dir", cfg.processed_dir.endswith("processed"))
check("config graph_dir", cfg.graph_dir.endswith("graph"))
check("config vectors_dir", cfg.vectors_dir.endswith("vectors"))
check("config archive_dir", cfg.archive_dir.endswith("archive"))
check("config similarity_threshold", cfg.similarity_threshold == 0.75)
check("config merge_threshold", cfg.merge_threshold == 0.95)
check("config embed_model", cfg.embed_model == "nomic-embed-text")
check("config llm_model", cfg.llm_model == "deepseek-r1:14b")

# Custom config
cfg2 = NexusConfig(data_dir="/tmp/nexus_test", similarity_threshold=0.8)
check("custom config dir", cfg2.data_dir == "/tmp/nexus_test")
check("custom threshold", cfg2.similarity_threshold == 0.8)


# ---------------------------------------------------------------------------
# NX2: Embeddings
# ---------------------------------------------------------------------------

print("\n=== NX2: Embeddings ===")

from nexus.embeddings import NexusEmbeddings, cosine_similarity, centroid

# Pure math
a = [1.0, 0.0, 0.0]
b = [1.0, 0.0, 0.0]
check("cosine identical = 1.0", abs(cosine_similarity(a, b) - 1.0) < 0.001)

c_vec = [0.0, 1.0, 0.0]
check("cosine orthogonal = 0.0", abs(cosine_similarity(a, c_vec)) < 0.001)

d = [-1.0, 0.0, 0.0]
check("cosine opposite = -1.0", abs(cosine_similarity(a, d) + 1.0) < 0.001)

check("cosine empty = 0.0", cosine_similarity([], []) == 0.0)
check("cosine mismatch = 0.0", cosine_similarity([1.0], [1.0, 2.0]) == 0.0)

# Centroid
ct = centroid([[1.0, 0.0], [0.0, 1.0]])
check("centroid", abs(ct[0] - 0.5) < 0.001 and abs(ct[1] - 0.5) < 0.001)
check("centroid empty", centroid([]) == [])

# NexusEmbeddings construction
embed = NexusEmbeddings(model="nomic-embed-text")
check("embeddings created", embed is not None)
check("embeddings cache empty", embed.cache_size == 0)

# Try to check availability (may or may not work depending on Ollama)
avail = embed.is_available()
print(f"  INFO: Embeddings available: {avail}")
check("embeddings avail is bool", isinstance(avail, bool))


# ---------------------------------------------------------------------------
# NX3: Chunker (rule-based, no LLM)
# ---------------------------------------------------------------------------

print("\n=== NX3: ThoughtChunker ===")

from nexus.chunker import ThoughtChunker

chunker = ThoughtChunker(max_words=50, min_words=5)

# Rule-based chunking
sample_text = """
Productivity habits form through neurological reward cycles and repetition.
The dopamine system reinforces behaviors that lead to perceived rewards.

Morning routines can leverage this by stacking small wins early in the day.
Cold showers, meditation, and journaling are common elements.

Sleep quality directly impacts cognitive performance and decision making.
Most adults need 7-9 hours for optimal function.
"""

thoughts = chunker.chunk_without_llm(sample_text, source="test")
check("chunker produces thoughts", len(thoughts) > 0)
check("thoughts are Thought objects", all(isinstance(t, Thought) for t in thoughts))
check("thoughts have text", all(t.text for t in thoughts))
check("thoughts have tags", all(isinstance(t.tags, list) for t in thoughts))
check("thoughts have source", all(t.source == "test" for t in thoughts))
print(f"  INFO: Produced {len(thoughts)} thoughts from sample text")
for i, th in enumerate(thoughts):
    print(f"    {i+1}. [{', '.join(th.tags[:3])}] {th.text[:60]}...")

# Empty input
empty = chunker.chunk_without_llm("")
check("empty input = empty list", empty == [])

# Very short input (below min_words)
short = chunker.chunk_without_llm("hi")
check("too short = empty", short == [])

# Single paragraph
single = chunker.chunk_without_llm(
    "The brain processes information through interconnected neural pathways "
    "that strengthen with repeated use and weaken with disuse.",
    source="manual",
)
check("single paragraph works", len(single) >= 1)

# Keyword extraction
keywords = chunker._extract_keywords("Productivity habits form through neurological reward cycles")
check("keywords extracted", len(keywords) > 0)
check("keywords lowercase", all(k == k.lower() for k in keywords))
check("keywords no stopwords", "through" not in keywords)

# Text cleaning
cleaned = chunker._clean_text("  um like  basically  hello world  ")
check("clean removes filler", "um" not in cleaned.split())
check("clean normalizes space", "  " not in cleaned)


# ---------------------------------------------------------------------------
# NX4: ThoughtGraph
# ---------------------------------------------------------------------------

print("\n=== NX4: ThoughtGraph ===")

from nexus.graph import ThoughtGraph

# Create temp dir for graph persistence
tmp_dir = tempfile.mkdtemp(prefix="nexus_test_")
graph_dir = os.path.join(tmp_dir, "graph")

graph = ThoughtGraph(graph_dir=graph_dir, similarity_threshold=0.7, merge_threshold=0.95)
check("graph created", graph is not None)
check("graph empty", graph.node_count == 0)
check("graph no edges", graph.edge_count == 0)

# Add thoughts
t1 = Thought(text="Morning routines boost productivity through habit stacking.", tags=["productivity", "morning"])
t2 = Thought(text="Dopamine loops reinforce repeated behaviors over time.", tags=["dopamine", "habits"])
t3 = Thought(text="Cold showers activate the sympathetic nervous system.", tags=["cold_shower", "health"])
t4 = Thought(text="Sleep quality determines cognitive performance the next day.", tags=["sleep", "cognition"])

for t in [t1, t2, t3, t4]:
    graph.add_thought(t, auto_link=False)

check("4 thoughts added", graph.node_count == 4)
check("get_thought works", graph.get_thought(t1.id) is not None)
check("get_thought by id", graph.get_thought(t1.id).text == t1.text)
check("get missing returns None", graph.get_thought("nonexistent") is None)

# Manual links
link1 = ThoughtLink(source_id=t1.id, target_id=t2.id, weight=0.82, link_type="similarity",
                     reason="Both about habit formation")
link2 = ThoughtLink(source_id=t1.id, target_id=t3.id, weight=0.65, link_type="similarity",
                     reason="Both about morning routines")
link3 = ThoughtLink(source_id=t1.id, target_id=t4.id, weight=0.71, link_type="similarity",
                     reason="Both about productivity factors")
link4 = ThoughtLink(source_id=t2.id, target_id=t4.id, weight=0.60, link_type="similarity",
                     reason="Both about brain function")

for l in [link1, link2, link3, link4]:
    graph.add_link(l)

check("4 edges added", graph.edge_count == 4)
check("get_links works", len(graph.get_links(t1.id)) == 3)
check("get_links t2", len(graph.get_links(t2.id)) == 2)

# Neighbors
neighbors = graph.get_neighbors(t1.id, depth=1)
check("t1 has 3 neighbors at depth 1", len(neighbors) == 3)

neighbors_deep = graph.get_neighbors(t3.id, depth=2)
check("t3 depth-2 finds more", len(neighbors_deep) >= 2)

# Shortest path
path = graph.get_shortest_path(t3.id, t4.id)
check("shortest path found", len(path) >= 2)
check("path starts at t3", path[0].id == t3.id)
check("path ends at t4", path[-1].id == t4.id)

# Get all thoughts
all_thoughts = graph.get_all_thoughts()
check("get_all_thoughts", len(all_thoughts) == 4)

# Keyword search (no embeddings)
results = graph.search_thoughts("morning routine productivity", limit=5)
check("keyword search returns results", len(results) > 0)
check("keyword search scored", all(isinstance(r[0], float) for r in results))

# Remove thought
removed = graph.remove_thought(t3.id)
check("remove returns True", removed)
check("node count after remove", graph.node_count == 3)
check("edges cleaned up", graph.edge_count == 3)  # link2 removed

# Clustering
t5 = Thought(text="Exercise improves brain function and memory.", tags=["exercise", "brain"])
graph.add_thought(t5, auto_link=False)
graph.add_link(ThoughtLink(source_id=t1.id, target_id=t5.id, weight=0.7, link_type="similarity"))

clusters = graph.cluster(min_size=2)
check("clustering produces results", len(clusters) >= 1)
check("cluster has thoughts", clusters[0].size >= 2)
print(f"  INFO: {len(clusters)} clusters found")

# Stats
stats = graph.status()
check("status has nodes", "nodes" in stats)
check("status has edges", "edges" in stats)
check("status has density", "density" in stats)
check("status has top_tags", "top_tags" in stats)
print(f"  INFO: Graph status: {stats['nodes']} nodes, {stats['edges']} edges, density={stats['density']}")

# Persistence
graph.save()
check("nodes.json exists", os.path.exists(os.path.join(graph_dir, "nodes.json")))
check("edges.json exists", os.path.exists(os.path.join(graph_dir, "edges.json")))
check("clusters.json exists", os.path.exists(os.path.join(graph_dir, "clusters.json")))

# Reload
graph2 = ThoughtGraph(graph_dir=graph_dir)
check("reload node count", graph2.node_count == graph.node_count)
check("reload edge count", graph2.edge_count == graph.edge_count)
check("reload thought text", graph2.get_thought(t1.id).text == t1.text)

# Density
d = graph.density()
check("density is float", isinstance(d, float))
check("density > 0", d > 0)


# ---------------------------------------------------------------------------
# NX5: Intake Pipeline
# ---------------------------------------------------------------------------

print("\n=== NX5: Intake Pipeline ===")

from nexus.ingest import IntakePipeline

raw_dir = os.path.join(tmp_dir, "raw")
intake = IntakePipeline(raw_dir=raw_dir, auto_file=True)

# Ingest text
result = intake.ingest_text("This is a test idea about machine learning and neural networks.", source="test")
check("ingest text returns dict", result is not None)
check("ingest text has text", "machine learning" in result["text"])
check("ingest text has source", result["source"] == "test")
check("ingest text has hash", len(result["content_hash"]) > 0)

# Duplicate detection
result2 = intake.ingest_text("This is a test idea about machine learning and neural networks.", source="test")
check("duplicate returns None", result2 is None)

# Different text
result3 = intake.ingest_text("Blockchain technology enables decentralized consensus.", source="test")
check("different text accepted", result3 is not None)

# Empty input
result4 = intake.ingest_text("")
check("empty returns None", result4 is None)

# Auto-filing
check("raw dir created", os.path.isdir(raw_dir))

# Ingest file
test_file = os.path.join(tmp_dir, "test_note.txt")
with open(test_file, "w", encoding="utf-8") as f:
    f.write("Quantum computing will revolutionize cryptography and drug discovery.")
result5 = intake.ingest_file(test_file)
check("ingest file works", result5 is not None)
check("file text extracted", "Quantum" in result5["text"])
check("file source", "test_note.txt" in result5["source"])

# Ingest JSON
test_json = os.path.join(tmp_dir, "test_data.json")
with open(test_json, "w", encoding="utf-8") as f:
    json.dump({"idea": "Artificial intelligence will transform education.", "notes": "Very important topic."}, f)
result6 = intake.ingest_file(test_json)
check("ingest json works", result6 is not None)
check("json text extracted", "intelligence" in result6["text"])

# Manifest
intake.save_manifest()
manifest_path = os.path.join(raw_dir, ".manifest.json")
check("manifest saved", os.path.exists(manifest_path))

# Processed count
check("processed count", intake.processed_count >= 3)

# Missing file
result7 = intake.ingest_file("/nonexistent/file.txt")
check("missing file returns None", result7 is None)


# ---------------------------------------------------------------------------
# NX6: SynthesisEngine (structural — no LLM calls)
# ---------------------------------------------------------------------------

print("\n=== NX6: SynthesisEngine ===")

from nexus.synthesis import SynthesisEngine

synth = SynthesisEngine(min_cluster_size=2, min_confidence=0.3)
check("synthesis engine created", synth is not None)

# Parse response (unit test the parser)
test_response = '{"text": "A new idea emerges.", "tags": ["innovation"], "confidence": 0.8, "rationale": "Combines concepts."}'
parsed = synth._parse_synthesis_response(test_response)
check("parse synthesis response", parsed is not None)
check("parsed text", parsed["text"] == "A new idea emerges.")
check("parsed confidence", parsed["confidence"] == 0.8)

# Parse with markdown fences
fenced = '```json\n{"text": "Fenced idea.", "tags": [], "confidence": 0.6, "rationale": "Test."}\n```'
parsed2 = synth._parse_synthesis_response(fenced)
check("parse fenced json", parsed2 is not None)
check("parsed fenced text", parsed2["text"] == "Fenced idea.")

# Parse with think blocks
think_response = '<think>Let me analyze...</think>\n{"text": "After thinking.", "tags": ["meta"], "confidence": 0.7, "rationale": "Deep thought."}'
parsed3 = synth._parse_synthesis_response(think_response)
check("parse with think block", parsed3 is not None)
check("parsed think text", parsed3["text"] == "After thinking.")

# Invalid JSON
bad = "This is not JSON at all"
parsed4 = synth._parse_synthesis_response(bad)
check("invalid json returns None", parsed4 is None)

# Missing required key
missing_key = '{"tags": ["test"], "confidence": 0.5}'
parsed5 = synth._parse_synthesis_response(missing_key)
check("missing required key returns None", parsed5 is None)

# Cluster naming parser
name_response = '{"name": "habit formation loops", "description": "Ideas about how habits form."}'
name_parsed = synth._parse_json_response(name_response)
check("cluster name parsed", name_parsed is not None)
check("cluster name value", name_parsed["name"] == "habit formation loops")


# ---------------------------------------------------------------------------
# NX7: FolderWatcher
# ---------------------------------------------------------------------------

print("\n=== NX7: FolderWatcher ===")

from nexus.watcher import FolderWatcher

watch_dir = os.path.join(tmp_dir, "watch_test")
os.makedirs(watch_dir, exist_ok=True)

# Create a pre-existing file (should be ignored)
with open(os.path.join(watch_dir, "existing.txt"), "w") as f:
    f.write("Pre-existing content")

detected_files = []

def on_file(path):
    detected_files.append(path)

watcher = FolderWatcher(
    watch_dirs=[watch_dir],
    on_new_file=on_file,
    poll_interval=0.5,
    extensions={".txt", ".md"},
)

check("watcher created", watcher is not None)
check("watcher not running", not watcher.is_running)
check("watcher knows existing file", watcher.known_file_count >= 1)

# Start watching
watcher.start()
check("watcher started", watcher.is_running)

# Create a new file
time.sleep(0.3)
new_file = os.path.join(watch_dir, "new_idea.txt")
with open(new_file, "w") as f:
    f.write("A brand new idea about quantum computing.")

# Wait for detection
time.sleep(1.5)
check("new file detected", len(detected_files) >= 1)
if detected_files:
    check("detected correct file", "new_idea.txt" in detected_files[0])

# Ignored extension
ignored_file = os.path.join(watch_dir, "image.png")
with open(ignored_file, "w") as f:
    f.write("not a real png")

time.sleep(1.0)
check("ignored extension not detected", all(".png" not in f for f in detected_files))

# Stop watcher
watcher.stop()
check("watcher stopped", not watcher.is_running)

# Context manager
with FolderWatcher(watch_dirs=[watch_dir], poll_interval=0.5) as w:
    check("context manager started", w.is_running)
check("context manager stopped", not w.is_running)


# ---------------------------------------------------------------------------
# NX9: Prompt templates
# ---------------------------------------------------------------------------

print("\n=== NX9: Prompt Templates ===")

from nexus.prompts import (
    CHUNK_SYSTEM, CHUNK_PROMPT, TAG_SYSTEM, TAG_PROMPT,
    CONNECT_SYSTEM, CONNECT_PROMPT, SYNTHESIS_SYSTEM, SYNTHESIS_PROMPT,
    CLUSTER_NAME_SYSTEM, CLUSTER_NAME_PROMPT, QUERY_SYSTEM, QUERY_PROMPT,
    DEDUP_SYSTEM, DEDUP_PROMPT, format_thoughts_for_prompt,
)

# All system prompts are non-empty strings
check("CHUNK_SYSTEM", len(CHUNK_SYSTEM) > 20)
check("TAG_SYSTEM", len(TAG_SYSTEM) > 20)
check("CONNECT_SYSTEM", len(CONNECT_SYSTEM) > 20)
check("SYNTHESIS_SYSTEM", len(SYNTHESIS_SYSTEM) > 20)
check("CLUSTER_NAME_SYSTEM", len(CLUSTER_NAME_SYSTEM) > 20)
check("QUERY_SYSTEM", len(QUERY_SYSTEM) > 20)
check("DEDUP_SYSTEM", len(DEDUP_SYSTEM) > 20)

# Prompts format correctly
chunk_p = CHUNK_PROMPT.format(text="Hello world", max_words=150)
check("CHUNK_PROMPT formats", "Hello world" in chunk_p)

tag_p = TAG_PROMPT.format(text="Test text")
check("TAG_PROMPT formats", "Test text" in tag_p)

connect_p = CONNECT_PROMPT.format(thought_a="idea A", thought_b="idea B")
check("CONNECT_PROMPT formats", "idea A" in connect_p)

synth_p = SYNTHESIS_PROMPT.format(cluster_name="test cluster", ideas_text="1. idea one")
check("SYNTHESIS_PROMPT formats", "test cluster" in synth_p)

# format_thoughts_for_prompt
test_thoughts = [Thought(text=f"Idea {i}") for i in range(5)]
formatted = format_thoughts_for_prompt(test_thoughts, max_items=3)
check("format_thoughts has 3 items", formatted.count("\n") == 2)
check("format_thoughts numbered", "1." in formatted and "3." in formatted)
check("format_thoughts limited", "4." not in formatted)


# ---------------------------------------------------------------------------
# NX8: NexusEngine (integration — no LLM, uses rule-based fallbacks)
# ---------------------------------------------------------------------------

print("\n=== NX8: NexusEngine (integration) ===")

from nexus.engine import NexusEngine

engine_dir = os.path.join(tmp_dir, "engine_test")
engine_config = NexusConfig(
    data_dir=engine_dir,
    max_chunk_words=80,
    min_chunk_words=5,
    similarity_threshold=0.7,
    cluster_min_size=2,
)

engine = NexusEngine(config=engine_config)
check("engine created", engine is not None)
check("engine dirs created", os.path.isdir(engine_config.graph_dir))

# Ingest text
r1 = engine.ingest(
    "Morning routines boost productivity through habit stacking. "
    "Small wins early in the day create momentum for larger tasks.",
    source="voice",
)
check("ingest ok", r1.ok)
check("ingest created thoughts", r1.thoughts_created > 0)
print(f"  INFO: Ingested {r1.thoughts_created} thoughts, {r1.thoughts_merged} merged")

# Ingest more
r2 = engine.ingest(
    "Sleep quality directly impacts cognitive performance. "
    "Most adults need seven to nine hours for optimal brain function. "
    "Melatonin production is affected by blue light exposure in the evening.",
    source="manual",
)
check("second ingest ok", r2.ok)
check("second ingest created", r2.thoughts_created > 0)

# Ingest from a file
test_note = os.path.join(tmp_dir, "note.md")
with open(test_note, "w", encoding="utf-8") as f:
    f.write("# Exercise and Brain Health\n\n"
            "Regular aerobic exercise increases hippocampal volume and improves memory. "
            "Even 30 minutes of walking per day shows measurable cognitive benefits.")
r3 = engine.ingest(test_note)
check("file ingest ok", r3.ok)
check("file ingest created", r3.thoughts_created > 0)

# Query
qr = engine.query("productivity morning")
check("query returns results", len(qr.thoughts) > 0)
check("query has query string", qr.query == "productivity morning")
print(f"  INFO: Query returned {len(qr.thoughts)} thoughts")

# Get all thoughts
all_t = engine.get_all_thoughts()
check("get_all_thoughts", len(all_t) > 0)
total = len(all_t)
print(f"  INFO: Total thoughts in graph: {total}")

# Status
status = engine.status()
check("status has nodes", status["nodes"] > 0)
check("status has engine", status["engine"] == "nexus")
check("status has config", "config" in status)
print(f"  INFO: Status: {status['nodes']} nodes, {status['edges']} edges")

# Get specific thought
if all_t:
    tid = all_t[0].id
    t_get = engine.get_thought(tid)
    check("get_thought by id", t_get is not None)
    check("get_thought text matches", t_get.text == all_t[0].text)

# Traverse
if all_t:
    tr = engine.traverse(all_t[0].id, depth=2)
    check("traverse returns results", len(tr.thoughts) > 0)

# Cluster
clusters = engine.cluster()
print(f"  INFO: {len(clusters)} clusters found")

# Save and verify persistence
engine.save()
check("graph saved", os.path.exists(os.path.join(engine_config.graph_dir, "nodes.json")))

# Duplicate detection (same content should be skipped)
r4 = engine.ingest(
    "Morning routines boost productivity through habit stacking. "
    "Small wins early in the day create momentum for larger tasks.",
    source="voice",
)
check("duplicate detection", r4.thoughts_created == 0 or not r4.ok)

# Shutdown
engine.shutdown()
check("engine shutdown", True)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

try:
    shutil.rmtree(tmp_dir)
except Exception:
    pass


# ===========================================================================
print(f"\n{'='*50}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"FAILURES: {failed}")
    sys.exit(1)
