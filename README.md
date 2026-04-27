<div align="center">

# OnyxKraken

**The AI business partner that lives on your PC.**

Research competitors. Write content. Automate tasks. Remember everything.
Runs entirely on your machine — no cloud APIs, no monthly fees, no data leaving your laptop.

[![License: BSL-1.1](https://img.shields.io/badge/license-BSL--1.1-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://python.org)
[![Local-first](https://img.shields.io/badge/local--first-100%25-00d4ff.svg)](https://markvizion.com)

[Live demo](https://markvizion.com) · [Try the face in your browser](https://markvizion.com/face) · [Built by markvizion.com](https://markvizion.com)

</div>

---

## The Problem

Solo founders end up with a Frankenstein stack of cloud AI subscriptions — ChatGPT Plus, Perplexity Pro, Otter, Calendly AI, Notion AI — paying $90–200/month for tools that don't talk to each other and require pasting client data into a different vendor every hour.

None of them remember what you worked on last week. None of them can actually *do* anything on your computer. And every month, you pay again.

**OnyxKraken replaces that stack.** One AI that lives on your Windows laptop, sees your screen, remembers your business across sessions, and acts on your behalf — via voice or text.

> *"Hey Onyx, draft a follow-up for this lead, research the company, and prep me a 3-bullet brief for the discovery call."* → 90 seconds. One tool. Zero data leaves your laptop.

---

## Who This Is For

- **Freelancers & consultants** — research clients, draft proposals, prep reports without switching tools
- **Content creators** — research trends, outline posts, generate copy that remembers your past work
- **Small agency owners** — run repeatable client workflows without hiring another person
- **E-commerce sellers** — research competitors, write listings, handle admin while you focus on sales
- **Coaches & course creators** — organize knowledge, draft curriculum, prep session materials

If you spend real time wishing your AI could just *do things* instead of just *answer questions* — that's the gap OnyxKraken fills.

---

## Use Cases

**Research a competitor:**
```
You: "Research my top 3 competitors — their pricing, what customers complain about,
     and any gap I can use in my marketing."
Onyx: [Researches, reads, synthesizes — stores findings to your local knowledge base]
      "Here's what I found. Competitor A shows $49/mo entry but users consistently
      complain about the lack of integrations..."
```

**Turn research into content without re-pasting:**
```
You: "Write a LinkedIn post using what you just found. Focus on the pricing gap."
Onyx: [Pulls stored context from memory — no copy-paste required]
      "Here's a draft: 'Most [niche] tools charge $49/mo for features that
      only matter to 10% of users...'"
```

**Automate a task you do every week:**
```
You: "Open my CRM, find contacts I haven't followed up with in 14 days,
     and draft a personalized email for each based on their last note."
Onyx: [Opens the app, reads the data, drafts the emails autonomously]
      "Done. 6 drafts saved to your drafts folder. Want me to review them first?"
```

**Full workflow, no hands:**
```
You: "Find 3 trending topics in my niche this week, pick the most actionable,
     and write a blog post outline I can publish tomorrow."
Onyx: [Research → evaluate → draft → save — all in one chain]
```

Memory persists. Every session builds on the last. Onyx doesn't forget what you asked it to research last Tuesday.

---

## What's in the Box

| Capability | What It Does for You |
|---|---|
| **Desktop Automation** | Opens apps, navigates menus, fills forms, types — any Windows software, plain English |
| **Conversational AI** | Multi-turn chat with full context memory across sessions |
| **Local RAG Knowledge Engine** | Every doc, conversation, and research finding is stored and searchable |
| **Voice I/O** | Push-to-talk + hands-free mode + TTS responses — control it while you work |
| **Screen Reading** | Windows UI Automation (primary) + vision model fallback — knows what's on your screen |
| **Animated Face GUI** | 16 emotions, personality presets, idle behaviors — feels like a real assistant |
| **Self-Improvement Engine** | Learns from failures, generates new strategies, gets more accurate over time |
| **REST API** | Programmatic access to all agent capabilities |

---

## Demo

Run the built-in demo system to see it work in under 5 minutes:

```bash
python main.py demo full          # 5-minute highlight reel — all capabilities
python main.py demo notepad       # Desktop automation (~70 seconds)
python main.py demo browser       # Web navigation and interaction (~70 seconds)
python main.py demo selfimprove   # Self-improvement loop (~45 seconds)
python main.py demo memory        # Cross-session memory (~40 seconds)
python main.py demo voice         # Voice interaction (~40 seconds)
```

Record any demo to MP4:
```bash
python main.py demo full --record
```

---

## 60-Second Install

```bash
git clone https://github.com/20TwentyVizion/OnyxKraken-Public
cd OnyxKraken-Public
pip install -r requirements.txt
python main.py
```

**Requirements:** Windows 10/11, Python 3.11+, 8 GB RAM, [Ollama](https://ollama.com).

On first launch the onboarding wizard handles model setup. 14-day full-feature trial — no API keys, no credit card.

**Recommended models:**
```bash
ollama pull llama3.2:latest           # Chat (~2 GB)
ollama pull llama3.2-vision:latest    # Screen vision (~8 GB)
ollama pull deepseek-r1:14b           # Planning & reasoning (~9 GB)
```

---

## How It Works

```
You: "Open my spreadsheet and update the revenue numbers for last week."
          │
          ▼
   ┌─────────────┐
   │   Planner    │  Goal → typed steps using your memory + current screen
   │  deepseek-r1 │
   └──────┬──────┘
          ▼
   ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
   │   Observe    │────▶│    Think      │────▶│     Act      │
   │  screenshot  │     │ vision model  │     │  click, type │
   │  a11y tree   │     │ decides next  │     │  scroll, read│
   └─────────────┘     └──────────────┘     └──────┬──────┘
                                                    │
                                                    ▼
                                           ┌─────────────┐
                                           │    Learn     │
                                           │  Success →   │
                                           │  knowledge   │
                                           │  Failure →   │
                                           │  new strategy│
                                           └─────────────┘
```

Onyx talks only to `127.0.0.1:11434` (your local Ollama) during normal operation. Run Wireshark or `pktmon` filtered by its process — the outbound log stays empty.

---

## Source Tour

If you're evaluating this for the **Skip AI Builder Grant** or a similar review, the six places to look:

| File | Why |
|---|---|
| [`main.py`](main.py) | Entry point — face GUI launch, CLI mode, single-goal execution |
| [`agent/`](agent/) | The reasoning layer — planning, task decomposition, error recovery |
| [`vision/`](vision/) | Screen reading — UI Automation + vision model fallback |
| [`memory/`](memory/) | Local RAG knowledge engine — persistent cross-session context |
| [`face/`](face/) | Animated face renderer (Canvas-based, 16 emotions, demo system) |
| [`safety.json`](safety.json) | Three-tier safety system policy — per-app allow/block rules |

---

## Why It Matters

| Stack | Annual Cost | Privacy | Memory |
|---|---|---|---|
| ChatGPT Plus + Perplexity + Otter + Calendly AI + Notion AI | $1,080–$2,400/yr | Data shared with 4–5 vendors | Each tool has amnesia |
| **OnyxKraken** | **$149 once** | **Stays on your machine** | **Persistent business memory** |

Pays itself back in 7 weeks. After that, every month is profit.

---

## What's in This Repo

OnyxKraken ships to real customer machines from a private repository. **This public mirror is curated for evaluation**, not a complete fork:

- ✅ The full operator product: chat, screen reading, memory, automation, animated face, REST API, test suite
- ✅ The full architecture, all reasoning code, and the rendering pipeline
- 🔒 License enforcement, payment-gateway integration, anti-tamper logic, and a few off-roadmap side products (Animation Studio, DJ stage, content-creation skills) are kept in the private repo. Stub modules with no-op implementations are provided where public files import them, so the public build runs as if every feature is unlocked

For the full commercial build, partnership, or integration: **intel@markvizion.com**

---

## License

**Business Source License 1.1** — source available:
- **Free** to evaluate, modify, and run for non-production use
- **$149 once** for production / commercial use — see [markvizion.com](https://markvizion.com)
- Converts to MIT after 4 years

---

<div align="center">
<sub>Built by <a href="https://markvizion.com">markvizion.com</a> · Privacy-first, local-first AI tooling designed by a solo entrepreneur for solo entrepreneurs.</sub>
</div>
