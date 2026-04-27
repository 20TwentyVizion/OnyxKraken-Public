"""Vision Analyzer — screenshot capture, grid overlay, and vision model queries.

Standalone module. No OnyxKraken imports required.
When running inside OnyxKraken, the bridge injects real config and chat_fn.
"""

import base64
import io
import logging
import os
import time
from typing import Callable, Optional

_log = logging.getLogger("vision.analyzer")

from PIL import Image, ImageDraw, ImageFont
import numpy as np

try:
    import mss as _mss
except ImportError:
    _mss = None

try:
    from skimage.metrics import structural_similarity as ssim
except ImportError:
    ssim = None


# ---------------------------------------------------------------------------
# Injectable configuration — defaults work standalone
# ---------------------------------------------------------------------------

_config = {
    "save_screenshots": True,
    "screenshot_dir": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots"),
    "max_screenshots": 50,
    "ssim_stability_delay": 0.5,
    "ssim_threshold": 0.98,
}

# Injectable chat function: (task_type, messages) -> response dict
# The bridge sets this to router.chat; standalone users provide their own.
_chat_fn: Optional[Callable] = None


def configure(cfg: dict = None, chat_fn: Callable = None):
    """Inject configuration and/or chat function at runtime.

    Args:
        cfg: Dict of config overrides (keys from _config).
        chat_fn: Callable(task_type, messages) -> {"message": {"content": str}}.
    """
    global _chat_fn
    if cfg:
        _config.update(cfg)
    if chat_fn:
        _chat_fn = chat_fn


def capture_screenshot(region: Optional[dict] = None) -> Image.Image:
    """Capture a screenshot of the entire screen or a specific region.

    Args:
        region: Optional dict with keys 'left', 'top', 'width', 'height'.
                If None, captures the primary monitor.

    Returns:
        PIL Image of the screenshot.
    """
    if _mss is None:
        raise RuntimeError("Screenshot capture requires 'mss'. Install with: pip install onyxkraken[desktop]")
    with _mss.mss() as sct:
        if region:
            monitor = region
        else:
            monitor = sct.monitors[1]  # primary monitor
        raw = sct.grab(monitor)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    return img


def save_screenshot(img: Image.Image, name: Optional[str] = None) -> str:
    """Save a screenshot to disk and return the file path.

    Respects config.SAVE_SCREENSHOTS and config.MAX_SCREENSHOTS.
    Rotates out oldest files when the cap is exceeded.
    """
    if not _config["save_screenshots"]:
        return ""
    ss_dir = _config["screenshot_dir"]
    os.makedirs(ss_dir, exist_ok=True)
    if name is None:
        name = f"screen_{int(time.time())}"
    path = os.path.join(ss_dir, f"{name}.png")
    img.save(path)

    # Rotate: remove oldest screenshots if over the cap
    try:
        files = sorted(
            (os.path.join(ss_dir, f)
             for f in os.listdir(ss_dir) if f.endswith(".png")),
            key=os.path.getmtime,
        )
        while len(files) > _config["max_screenshots"]:
            os.remove(files.pop(0))
    except OSError:
        pass
    return path


def image_to_base64(img: Image.Image) -> str:
    """Convert a PIL Image to a base64-encoded PNG string."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def add_grid_overlay(img: Image.Image, cols: int = 10, rows: int = 8) -> Image.Image:
    """Overlay a labeled grid on an image for coordinate-based vision queries.

    Each cell gets a label like A1, B2, etc. so the LLM can reference
    approximate screen regions.

    Returns:
        A copy of the image with the grid drawn on top.
    """
    overlay = img.copy()
    draw = ImageDraw.Draw(overlay)
    w, h = overlay.size
    cell_w = w / cols
    cell_h = h / rows

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except (OSError, IOError):
        font = ImageFont.load_default()

    for r in range(rows):
        for c in range(cols):
            x0 = int(c * cell_w)
            y0 = int(r * cell_h)
            x1 = int((c + 1) * cell_w)
            y1 = int((r + 1) * cell_h)

            # grid lines
            draw.rectangle([x0, y0, x1, y1], outline="red", width=1)

            # cell label
            label = f"{chr(65 + c)}{r + 1}"
            draw.text((x0 + 4, y0 + 2), label, fill="red", font=font)

    return overlay


def is_screen_stable(delay: float = None, threshold: float = None) -> bool:
    """Compare two screenshots taken `delay` seconds apart using SSIM.

    Returns True if similarity exceeds `threshold` (screen is stable).
    """
    delay = delay or _config["ssim_stability_delay"]
    threshold = threshold or _config["ssim_threshold"]

    img1 = capture_screenshot()
    time.sleep(delay)
    img2 = capture_screenshot()

    # Convert to grayscale numpy arrays for SSIM
    arr1 = np.array(img1.convert("L"))
    arr2 = np.array(img2.convert("L"))

    score = ssim(arr1, arr2)
    return score >= threshold


def analyze_screenshot(
    img: Image.Image,
    prompt: str,
    use_grid: bool = False,
    model: str = None,
) -> str:
    """Send a screenshot to the vision model with a prompt and return the response.

    Args:
        img: The screenshot to analyze.
        prompt: The question/instruction for the model.
        use_grid: If True, overlay a grid before sending to help with coords.
        model: Ollama model name (unused in standalone; kept for API compat).

    Returns:
        The model's text response.

    Raises:
        RuntimeError: If no chat function has been configured.
    """
    if _chat_fn is None:
        raise RuntimeError(
            "No chat function configured. Call vision.analyzer.configure(chat_fn=...) "
            "or use the OnyxKraken bridge which injects this automatically."
        )

    if use_grid:
        img = add_grid_overlay(img)

    b64 = image_to_base64(img)

    messages = [
        {
            "role": "user",
            "content": prompt,
            "images": [b64],
        }
    ]

    response = _chat_fn("vision", messages)
    return response["message"]["content"]
