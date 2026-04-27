# OnyxKraken Web Face

A web-based animated face chat UI for [OnyxKraken](https://github.com/your-repo/OnyxKraken) — your private desktop AI agent.

**Live:** [onyxkraken-face.netlify.app](https://onyxkraken-face.netlify.app)

## Features

- **Animated face** — 10 emotions, eye tracking, blink, phoneme mouth sync (HTML5 Canvas)
- **Streaming chat** — Real-time token streaming from your local Ollama instance
- **Configurable** — Ollama URL + model selection via Settings panel
- **First-launch onboarding** — The face introduces itself on first visit
- **Usage stats** — Local-only analytics dashboard (📊 Stats button)
- **Mobile-responsive** — Works on phone, tablet, and desktop
- **Shared face spec** — Colors, emotions, geometry loaded from `face_spec.json` (shared with Python desktop face)
- **Privacy-first** — No cloud, no tracking. All data stays in your browser's localStorage

## Stack

- **Vite** + **React** + **Tailwind CSS v4**
- **HTML5 Canvas** face renderer (ported from Python `face/face_gui.py`)
- **Ollama** streaming API client

## Quick Start

```bash
cd onyx-web
npm install
npm run dev
```

Then open [http://localhost:5173](http://localhost:5173).

Requires a running Ollama instance (default: `http://localhost:11434`).

## Remote Access (Phone)

1. On your PC: `ngrok http 11434`
2. Set `OLLAMA_ORIGINS=*` env var before starting Ollama
3. Paste the ngrok URL into the Settings panel

## Project Structure

```
src/
├── App.jsx                    — Main layout + routing
├── lib/
│   ├── faceRenderer.js        — Canvas face animation engine
│   ├── face_spec.json         — Shared face design spec (from face/face_spec.json)
│   ├── ollama.js              — Ollama API client (streaming)
│   └── analytics.js           — Local usage analytics
├── components/
│   ├── OnyxFace.jsx           — Canvas component (60fps loop)
│   ├── ChatPanel.jsx          — Chat messages + input
│   ├── Settings.jsx           — Ollama URL/model config
│   ├── StatsPanel.jsx         — Usage stats dashboard
│   └── Onboarding.jsx         — First-launch sequence
└── index.css                  — Tailwind v4 theme (dark mode)
```

## Deployment

```bash
npm run build
npx netlify-cli deploy --prod --dir=dist
```

Netlify Project ID: `3b474152-56fe-42ae-9ae9-4e3efa2c1989`
