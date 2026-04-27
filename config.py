"""OnyxKraken configuration — models, timeouts, autonomy mode."""

import json
import logging
import os

_log = logging.getLogger("config")

# ---------------------------------------------------------------------------
# Ollama model assignments — multi-model routing
# Each task type has a primary and fallback model.
# The ModelRouter in agent/model_router.py handles failover automatically.
# Override with your preferred models — just ensure they're pulled in Ollama.
# ---------------------------------------------------------------------------
MODELS = {
    "vision": {
        "primary": "llama3.2-vision:latest",     # multimodal — screenshot analysis + action
        "fallback": "llava:7b",                  # lighter vision fallback
    },
    "planner": {
        "primary": "minimax-m2.7:cloud",         # MiniMax M2.7 cloud — strong at end-to-end tasks
        "fallback": "deepseek-r1:14b",           # local fallback if cloud unavailable
    },
    "reasoning": {
        "primary": "minimax-m2.7:cloud",         # MiniMax M2.7 cloud — complex logic + SE tasks
        "fallback": "deepseek-r1:14b",           # local fallback if cloud unavailable
    },
    "filesystem": {
        "primary": "minimax-m2.7:cloud",         # MiniMax M2.7 cloud — param extraction + file ops
        "fallback": "deepseek-r1:14b",           # local fallback if cloud unavailable
    },
}

# Chat model — fast model for casual conversation (Face GUI + Discord)
CHAT_MODEL = "llama3.2:latest"

# Build model — high-quality coder model for ToolForge app generation
BUILD_MODEL = "qwen3-coder:480b-cloud"

# Backward compat — used by code that hasn't migrated to ModelRouter yet
VISION_MODEL = MODELS["vision"]["primary"]
PLANNER_MODEL = MODELS["planner"]["primary"]
PLANNER_MODEL_FALLBACK = MODELS["planner"]["fallback"]

OLLAMA_HOST = "http://localhost:11434"

# ---------------------------------------------------------------------------
# Autonomy mode: "auto" | "confirm" | "smart"
# ---------------------------------------------------------------------------
AUTONOMY_MODE = "smart"

# ---------------------------------------------------------------------------
# Pricing (single source of truth)
# ---------------------------------------------------------------------------
from core.pricing import ONYXKRAKEN_PRICE as PRODUCT_PRICE  # noqa: E402
from core.pricing import PRODUCT_NAME, PRODUCT_VERSION       # noqa: E402

# ---------------------------------------------------------------------------
# Timeouts (seconds)
# ---------------------------------------------------------------------------
APP_LOAD_TIMEOUT = 10          # max wait for an app to become ready
SSIM_STABILITY_DELAY = 0.5     # delay between SSIM comparison screenshots
SSIM_THRESHOLD = 0.98          # similarity threshold for "screen is stable"
ACTION_RETRY_LIMIT = 5         # retries on malformed LLM output
MAX_AGENT_STEPS = 30           # safety cap on orchestrator loop iterations

# ---------------------------------------------------------------------------
# Screenshot settings
# ---------------------------------------------------------------------------
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
SAVE_SCREENSHOTS = True            # set False to skip saving (saves disk)
MAX_SCREENSHOTS = 50               # rotate out oldest when exceeded

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = "INFO"                 # DEBUG, INFO, WARNING, ERROR

# ---------------------------------------------------------------------------
# Chat UI settings
# ---------------------------------------------------------------------------
CHAT_TYPEWRITER_EFFECT = False  # Set to False for instant message display (faster)

# ---------------------------------------------------------------------------
# Safety rules
# ---------------------------------------------------------------------------
SAFETY_FILE = os.path.join(os.path.dirname(__file__), "safety.json")


# ---------------------------------------------------------------------------
# Blender executable discovery — cross-platform (delegates to core.platform)
# ---------------------------------------------------------------------------

def find_blender_exe() -> str:
    """Locate the Blender executable on the current platform.

    Delegates to core.platform.find_blender_exe() which checks
    Windows, Mac, and Linux paths (newest first).
    """
    from core.platform import find_blender_exe as _find
    return _find()


def load_safety_rules() -> dict:
    """Load allow/block rules from safety.json."""
    if not os.path.exists(SAFETY_FILE):
        return {"allow": [], "block": []}
    with open(SAFETY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
