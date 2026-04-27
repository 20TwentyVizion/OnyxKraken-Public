# OnyxKraken — Quick Start Guide

Welcome to **OnyxKraken**, your autonomous AI desktop companion.

---

## System Requirements

- **OS**: Windows 10/11 (64-bit), macOS 12+, or Linux (Ubuntu 22.04+)
- **RAM**: 8 GB minimum, 16 GB recommended
- **Disk**: 2 GB free space
- **AI Backend**: [Ollama](https://ollama.com) installed locally (free, runs on your machine)

## Installation

### Windows
1. Run `OnyxKraken-Setup-win64.exe`
2. If Windows SmartScreen shows "Windows protected your PC":
   - Click **"More info"**
   - Click **"Run anyway"**
   - This is normal for new software — OnyxKraken is safe to install
3. Follow the installer prompts
4. Launch from the Start Menu or Desktop shortcut

### macOS / Linux
1. Extract the archive
2. Run the `OnyxCore` executable

## First Launch

On first launch, you'll see:
1. **EULA** — Read and accept the license agreement
2. **Trial starts** — You get a **14-day free trial** with full access
3. **Onyx's face** — The animated face GUI will appear

## Activating Your License

After purchasing, you'll receive a license key (format: `ONYX-XXXX-XXXX-XXXX-XXXX`).

**GUI**: Click the menu → Help → Activate License → Paste your key

**CLI**:
```
OnyxCore.exe activate ONYX-XXXX-XXXX-XXXX-XXXX
```

## Setting Up Ollama (AI Backend)

OnyxKraken uses Ollama for local AI — no cloud API keys needed.

1. Install Ollama from [ollama.com](https://ollama.com)
2. Pull a model:
   ```
   ollama pull deepseek-r1:14b
   ```
3. Ollama runs automatically in the background

## What Can Onyx Do?

| Feature | Description |
|---------|-------------|
| **Chat** | Natural conversation with memory |
| **Desktop Automation** | Control apps, type, click, navigate (Windows) |
| **Animation Studio** | Create animated episodes with multiple characters |
| **Music Production** | Generate beats and music with AI |
| **Blender Integration** | 3D modeling assistance |
| **Knowledge Engine** | RAG-powered document Q&A |
| **Voice** | Text-to-speech with character voices |

## Demo Mode Limits

Without a license key (after trial expires):
- 3 tasks per session
- Limited to: Chat, Desktop Automation, Knowledge, Personality, Face GUI
- Locked: Voice, Self-Improvement, Daemon, Blender, Music, Shows

## Pricing

| Product | Price | Includes |
|---------|-------|----------|
| **Onyx Core** | $149 | Face + Chat + Memory + AI |
| **Starter Pack** | $199 | Core + Voice + Agent |
| **Creator Pack** | $349 | Starter + Studio + 3D + DJ |
| **Founder's Edition** | $499 | Everything + lifetime updates |

All prices are **one-time purchases**. No subscriptions.

**Purchase**: [markvizion.gumroad.com/l/onyxkraken](https://markvizion.gumroad.com/l/onyxkraken)

## Support

- **Email**: support@markvizion.com
- **Website**: [markvizion.com](https://markvizion.com)

## License

OnyxKraken is proprietary software by markvizion.
See the `LICENSE` file for full terms.

---

*Built with 🔥 by markvizion*
