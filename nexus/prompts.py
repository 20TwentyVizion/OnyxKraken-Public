"""Nexus LLM prompt templates — structured JSON output for all operations.

Every prompt enforces strict JSON output to keep the engine deterministic.
No personality, no chit-chat — Star Trek computer style.
"""


# ---------------------------------------------------------------------------
# Chunker — split raw text into atomic ideas
# ---------------------------------------------------------------------------

CHUNK_SYSTEM = (
    "You are a data processing engine. Your sole function is to decompose "
    "raw text into atomic ideas. Each idea should be a single, self-contained "
    "thought that can stand alone. Output ONLY valid JSON — no commentary, "
    "no markdown fences, no explanation."
)

CHUNK_PROMPT = """Decompose the following raw text into atomic ideas.

Rules:
- Each idea: 1-3 sentences, max {max_words} words.
- Preserve the original meaning — do NOT paraphrase or interpret.
- If the text contains multiple distinct topics, split them into separate ideas.
- If a sentence is already atomic, keep it as-is.
- Discard filler words, greetings, and meta-commentary (e.g. "um", "like I said").
- Number each idea sequentially starting from 1.

Output format (JSON array):
[
  {{"id": 1, "text": "The atomic idea text here."}},
  {{"id": 2, "text": "Another distinct idea."}}
]

Raw text:
---
{text}
---

JSON output:"""


# ---------------------------------------------------------------------------
# Tagger — auto-tag each thought with topics and metadata
# ---------------------------------------------------------------------------

TAG_SYSTEM = (
    "You are a classification engine. Your function is to assign topic tags "
    "and metadata to text chunks. Output ONLY valid JSON — no commentary."
)

TAG_PROMPT = """Classify the following text chunk.

Rules:
- Assign 2-5 topic tags (lowercase, no spaces — use underscores).
- Tags should capture the core subject matter, not generic words.
- Assign a sentiment: "positive", "negative", "neutral", or "mixed".
- Assign a domain: the broad area this belongs to (e.g. "technology", "health", "business", "personal", "creative").
- If this is an actionable idea, set "actionable": true.

Output format (JSON object):
{{
  "tags": ["tag_one", "tag_two", "tag_three"],
  "sentiment": "neutral",
  "domain": "technology",
  "actionable": false
}}

Text:
---
{text}
---

JSON output:"""


# ---------------------------------------------------------------------------
# Connection reasoning — explain why two thoughts are related
# ---------------------------------------------------------------------------

CONNECT_SYSTEM = (
    "You are an analytical engine. Your function is to determine if two ideas "
    "are meaningfully related and explain the connection. Output ONLY valid JSON."
)

CONNECT_PROMPT = """Analyze the relationship between these two ideas.

Idea A: "{thought_a}"
Idea B: "{thought_b}"

Rules:
- Determine if there is a meaningful connection (not just surface-level word overlap).
- Rate the connection strength: 0.0 (unrelated) to 1.0 (strongly connected).
- If strength >= 0.5, provide a brief reason (one sentence).
- If strength < 0.5, set reason to empty string.

Output format (JSON object):
{{
  "connected": true,
  "strength": 0.82,
  "reason": "Both ideas address the relationship between habit formation and neurological reward systems."
}}

JSON output:"""


# ---------------------------------------------------------------------------
# Cluster naming — generate a theme name for a group of thoughts
# ---------------------------------------------------------------------------

CLUSTER_NAME_SYSTEM = (
    "You are a classification engine. Your function is to name a group of "
    "related ideas with a concise theme label. Output ONLY valid JSON."
)

CLUSTER_NAME_PROMPT = """Name the theme that connects these ideas.

Ideas:
{ideas_text}

Rules:
- The theme name should be 2-5 words, descriptive but concise.
- It should capture the common thread, not just list topics.
- Also provide a one-sentence description.

Output format (JSON object):
{{
  "name": "habit formation loops",
  "description": "Ideas exploring how habits form through neurological reward cycles and repetition."
}}

JSON output:"""


# ---------------------------------------------------------------------------
# Synthesis — propose new ideas from a cluster
# ---------------------------------------------------------------------------

SYNTHESIS_SYSTEM = (
    "You are an analytical synthesis engine. Your function is to examine a "
    "cluster of related ideas and propose ONE new idea that emerges from "
    "their combination. This new idea should not simply restate the inputs — "
    "it should be a genuine insight or hypothesis. Output ONLY valid JSON."
)

SYNTHESIS_PROMPT = """Given these related ideas, propose one new hypothesis or insight.

Theme: "{cluster_name}"

Ideas:
{ideas_text}

Rules:
- The new idea must be a logical extension, combination, or implication of the inputs.
- It must NOT simply summarize or restate what's already there.
- It should be specific and actionable where possible.
- Tag it with relevant topics.
- Rate your confidence: 0.0 (wild guess) to 1.0 (strong logical inference).

Output format (JSON object):
{{
  "text": "The proposed new idea or hypothesis.",
  "tags": ["relevant", "tags"],
  "confidence": 0.75,
  "rationale": "One sentence explaining how this follows from the input ideas."
}}

JSON output:"""


# ---------------------------------------------------------------------------
# Query interpretation — understand what the user is asking for
# ---------------------------------------------------------------------------

QUERY_SYSTEM = (
    "You are a query parser. Your function is to extract search parameters "
    "from a natural language query. Output ONLY valid JSON."
)

QUERY_PROMPT = """Parse this search query into structured parameters.

Query: "{query}"

Rules:
- Extract topic keywords for graph traversal.
- Determine if the user wants: "search" (find existing), "connect" (find links), or "synthesize" (generate new).
- Extract any filters: time range, source type, tags.

Output format (JSON object):
{{
  "keywords": ["keyword1", "keyword2"],
  "intent": "search",
  "filters": {{
    "tags": [],
    "source": "",
    "time_range": ""
  }}
}}

JSON output:"""


# ---------------------------------------------------------------------------
# Dedup check — determine if two thoughts should be merged
# ---------------------------------------------------------------------------

DEDUP_SYSTEM = (
    "You are a deduplication engine. Your function is to determine if two "
    "text chunks express the same idea. Output ONLY valid JSON."
)

DEDUP_PROMPT = """Are these two texts expressing the same idea?

Text A: "{text_a}"
Text B: "{text_b}"

Rules:
- "same idea" means the core meaning is identical, even if wording differs.
- Minor additions or elaborations count as "same" — set merge=true.
- If they share a topic but make different points, set merge=false.
- If merge=true, provide a merged version that preserves the best of both.

Output format (JSON object):
{{
  "merge": true,
  "confidence": 0.92,
  "merged_text": "The best combined version of both texts."
}}

JSON output:"""


# ---------------------------------------------------------------------------
# Helper — format a list of thoughts for prompt injection
# ---------------------------------------------------------------------------

def format_thoughts_for_prompt(thoughts, max_items: int = 10) -> str:
    """Format a list of Thought objects into numbered text for LLM prompts."""
    lines = []
    for i, t in enumerate(thoughts[:max_items], 1):
        text = t.text if hasattr(t, "text") else t.get("text", "")
        lines.append(f"{i}. {text}")
    return "\n".join(lines)
