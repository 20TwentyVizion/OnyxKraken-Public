"""Extension connector — launch/connect/use/terminate pattern for external apps.

Each extension (EVERA, SmartEngine, JustEdit) has a connector that:
  1. Checks if the service is running
  2. Launches it if needed
  3. Provides a client to call its API
  4. Terminates it when done

Connectors are lazy — they don't start anything until first use.
Nodes call connector methods; connectors call existing app modules.

Architecture (agentic AI best-practices):
  - Connectors are singletons (avoid fully independent agents)
  - ConnectorBus provides decentralized inter-agent communication
    so search/discovery results are shared, avoiding redundant calls
  - Lifecycle is centrally orchestrated by the executor
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared result bus — decentralized inter-agent communication
# ---------------------------------------------------------------------------

class ConnectorBus:
    """Thread-safe publish/subscribe bus for sharing results across nodes.

    Avoids redundant API calls when multiple nodes need the same data
    (e.g. two nodes both listing EVERA artists, or multiple SmartEngine
    discovery calls with overlapping queries).

    Usage from nodes:
        bus = get_bus()
        cached = bus.get("evera", "list_artists")
        if cached is None:
            result = connector.execute("evera_list_artists")
            bus.publish("evera", "list_artists", result)
    """

    def __init__(self, ttl: float = 300.0):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._ttl = ttl  # seconds before entries expire
        self._subscribers: Dict[str, List[Callable]] = {}

    def publish(self, extension: str, key: str, value: Any):
        """Publish a result to the bus."""
        full_key = f"{extension}:{key}"
        with self._lock:
            if extension not in self._store:
                self._store[extension] = {}
            self._store[extension][key] = value
            self._timestamps[full_key] = time.time()

        # Notify subscribers
        for cb in self._subscribers.get(full_key, []):
            try:
                cb(extension, key, value)
            except Exception as e:
                logger.warning("Bus subscriber error for %s: %s", full_key, e)

    def get(self, extension: str, key: str) -> Optional[Any]:
        """Get a cached result. Returns None if missing or expired."""
        full_key = f"{extension}:{key}"
        with self._lock:
            ts = self._timestamps.get(full_key, 0)
            if time.time() - ts > self._ttl:
                return None
            return self._store.get(extension, {}).get(key)

    def subscribe(self, extension: str, key: str, callback: Callable):
        """Subscribe to updates for a specific key."""
        full_key = f"{extension}:{key}"
        with self._lock:
            self._subscribers.setdefault(full_key, []).append(callback)

    def clear(self, extension: Optional[str] = None):
        """Clear cached results (all or for a specific extension)."""
        with self._lock:
            if extension:
                self._store.pop(extension, None)
                self._timestamps = {
                    k: v for k, v in self._timestamps.items()
                    if not k.startswith(f"{extension}:")
                }
            else:
                self._store.clear()
                self._timestamps.clear()

    def stats(self) -> Dict[str, int]:
        """Return count of cached entries per extension."""
        with self._lock:
            return {ext: len(items) for ext, items in self._store.items()}


_bus: Optional[ConnectorBus] = None


def get_bus() -> ConnectorBus:
    """Get the global ConnectorBus singleton."""
    global _bus
    if _bus is None:
        _bus = ConnectorBus()
    return _bus


class ExtensionConnector:
    """Base class for extension connectors."""

    name: str = ""
    display_name: str = ""

    def is_running(self) -> bool:
        """Check if the extension service is currently running."""
        raise NotImplementedError

    def ensure_running(self) -> bool:
        """Start the extension if not running. Returns True if ready."""
        raise NotImplementedError

    def shutdown(self) -> bool:
        """Gracefully shut down the extension. Returns True if stopped."""
        raise NotImplementedError

    def health(self) -> Dict[str, Any]:
        """Return health/status info."""
        return {"name": self.name, "running": self.is_running()}


class EveraConnector(ExtensionConnector):
    """Connector for EVERA music generation engine.

    Uses the existing EveraModule from apps/modules/evera.py.
    EVERA runs as a local service (Ollama + ACE-Step + RadioEngine SDK).
    """

    name = "evera"
    display_name = "EVERA"

    def __init__(self):
        self._module = None

    def _get_module(self):
        if self._module is None:
            from apps.modules.evera import EveraModule
            self._module = EveraModule()
        return self._module

    def is_running(self) -> bool:
        try:
            mod = self._get_module()
            h = mod.health()
            return h.get("ollama", False) or h.get("healthy", False)
        except Exception:
            return False

    def ensure_running(self) -> bool:
        try:
            mod = self._get_module()
            result = mod.ensure_ready()
            return result.get("ready", False)
        except Exception as e:
            logger.error("Failed to start EVERA: %s", e)
            return False

    def shutdown(self) -> bool:
        try:
            mod = self._get_module()
            mod.execute_action("evera_stop")
            return True
        except Exception as e:
            logger.error("Failed to stop EVERA: %s", e)
            return False

    def execute(self, action: str, params: Optional[Dict] = None) -> Dict:
        """Execute an EVERA action via the existing module."""
        mod = self._get_module()
        return mod.execute_action(action, params or {})

    def health(self) -> Dict[str, Any]:
        try:
            mod = self._get_module()
            return mod.health()
        except Exception as e:
            return {"name": self.name, "running": False, "error": str(e)}


class SmartEngineConnector(ExtensionConnector):
    """Connector for SmartEngine writing engine.

    SmartEngine runs as a FastAPI server (default port 8000).
    Uses the existing SmartEngineClient from apps/modules/smartengine.py.
    """

    name = "smartengine"
    display_name = "SmartEngine"

    def __init__(self):
        self._module = None
        self._client = None

    def _get_module(self):
        if self._module is None:
            from apps.modules.smartengine import SmartEngineModule
            self._module = SmartEngineModule()
        return self._module

    def _get_client(self):
        if self._client is None:
            from apps.modules.smartengine import SmartEngineClient
            self._client = SmartEngineClient()
        return self._client

    def is_running(self) -> bool:
        try:
            return self._get_client().is_running()
        except Exception:
            return False

    def ensure_running(self) -> bool:
        try:
            mod = self._get_module()
            mod.execute_action("smartengine_start")
            return self.is_running()
        except Exception as e:
            logger.error("Failed to start SmartEngine: %s", e)
            return False

    def shutdown(self) -> bool:
        try:
            mod = self._get_module()
            mod.execute_action("smartengine_stop")
            return True
        except Exception as e:
            logger.error("Failed to stop SmartEngine: %s", e)
            return False

    def execute(self, action: str, params: Optional[Dict] = None) -> Dict:
        """Execute a SmartEngine action via the existing module."""
        mod = self._get_module()
        return mod.execute_action(action, params or {})

    # -- Image generation (calls image_gen.py directly) --

    def _ensure_image_gen(self):
        """Add SmartEngine to sys.path so we can import api.engine.image_gen."""
        import sys
        se_dir = self._smartengine_dir()
        if se_dir not in sys.path:
            sys.path.insert(0, se_dir)

    @staticmethod
    def _smartengine_dir() -> str:
        import os
        return os.path.join(
            "I:\\", "SmartEngine",
        )

    def generate_image(self, prompt: str, output_path: str,
                       width: int = 1024, height: int = 1024,
                       negative_prompt: str = "",
                       seed: Optional[int] = None,
                       backend: Optional[str] = None,
                       max_retries: int = 1) -> Dict:
        """Generate an image from a text prompt (sync wrapper).

        Uses SmartEngine's multi-backend image_gen:
          - pollinations (free, default)
          - flux_pro (BFL API key)
          - openai_gpt_image (OpenAI API key)
        """
        self._ensure_image_gen()
        from api.engine.image_gen import (
            _generate_image_sync, _generate_flux_pro_sync,
            _generate_openai_sync, _active_backend,
        )
        from pathlib import Path
        from io import BytesIO

        use_backend = backend or _active_backend
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Generating image [%s]: %s", use_backend, prompt[:80])

        img_bytes = None
        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                if use_backend == "flux_pro":
                    img_bytes = _generate_flux_pro_sync(prompt, width, height, seed)
                elif use_backend in ("openai_gpt_image", "openai_mini"):
                    model = "gpt-image-1-mini" if use_backend == "openai_mini" else "gpt-image-1"
                    img_bytes = _generate_openai_sync(prompt, width, height, model)
                else:
                    img_bytes = _generate_image_sync(
                        prompt, negative_prompt, width, height, seed)
                break
            except Exception as e:
                last_err = e
                logger.warning("Image gen attempt %d/%d failed: %s",
                               attempt, max_retries, e)
                if attempt < max_retries:
                    import time as _t
                    _t.sleep(3 * attempt)

        from PIL import Image

        if img_bytes is None:
            logger.warning("API backends failed, using Pillow procedural fallback")
            img = self._generate_fallback_image(prompt, width, height, seed)
        else:
            img = Image.open(BytesIO(img_bytes))

        img.save(str(output), format="PNG", optimize=True)
        logger.info("Image saved: %s (%dx%d)", output, img.width, img.height)

        return {
            "path": str(output),
            "width": img.width,
            "height": img.height,
            "prompt": prompt,
            "backend": use_backend,
        }

    @staticmethod
    def _generate_fallback_image(prompt: str, width: int, height: int,
                                 seed: Optional[int] = None):
        """Generate a procedural gradient+noise image when APIs are down."""
        import random
        from PIL import Image, ImageDraw, ImageFilter
        import numpy as np

        if seed:
            random.seed(seed)

        # Pick colors based on prompt keywords
        palettes = {
            "jazz":       ((20, 15, 40), (60, 40, 100)),
            "electronic": ((5, 0, 30),   (30, 0, 90)),
            "rock":       ((30, 8, 8),   (90, 25, 15)),
            "ambient":    ((5, 15, 30),  (30, 70, 95)),
            "pop":        ((25, 10, 30), (85, 45, 95)),
            "classical":  ((15, 12, 10), (70, 60, 50)),
        }
        prompt_lower = prompt.lower()
        c1, c2 = ((10, 10, 20), (50, 40, 70))  # default
        for key, pal in palettes.items():
            if key in prompt_lower:
                c1, c2 = pal
                break

        # Gradient
        arr = np.zeros((height, width, 3), dtype=np.uint8)
        for y in range(height):
            t = y / max(height - 1, 1)
            for c in range(3):
                arr[y, :, c] = int(c1[c] + (c2[c] - c1[c]) * t)

        # Add noise texture
        noise = np.random.randint(0, 20, (height, width, 3), dtype=np.uint8)
        arr = np.clip(arr.astype(np.int16) + noise - 10, 0, 255).astype(np.uint8)

        img = Image.fromarray(arr)
        img = img.filter(ImageFilter.GaussianBlur(radius=3))
        return img

    def generate_album_cover(self, title: str, artist: str,
                             genre: str = "jazz", output_path: str = "",
                             seed: Optional[int] = None,
                             backend: Optional[str] = None) -> Dict:
        """Generate a square album cover with AI background + text overlay.

        Full pipeline:
          1. Craft visual prompt for the genre/mood
          2. Generate 1024x1024 background via Pollinations/Flux/OpenAI
          3. Overlay title + artist text using SmartEngine's typography system
          4. Save final PNG
        """
        import os, hashlib
        from pathlib import Path

        # Default output path
        if not output_path:
            covers_dir = Path(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))) / "data" / "covers"
            covers_dir.mkdir(parents=True, exist_ok=True)
            safe = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)
            safe = safe.strip().replace(" ", "_").lower()[:30] or "cover"
            h = hashlib.md5(f"{title}{artist}{genre}".encode()).hexdigest()[:6]
            output_path = str(covers_dir / f"{safe}_{h}.png")

        # Step 1: Craft prompt (keep short for Pollinations URL)
        prompt = (
            f"{genre} album cover art, {title}, "
            f"atmospheric cinematic painting, moody lighting, "
            f"no text no words no letters no writing"
        )

        # Step 2: Generate background
        result = self.generate_image(
            prompt=prompt,
            output_path=output_path,
            width=1024, height=1024,
            negative_prompt="",
            seed=seed,
            backend=backend,
        )

        # Step 3: Overlay text using SmartEngine's typography system
        try:
            self._ensure_image_gen()
            from api.engine.image_gen import _overlay_cover_text, _slugify_for_typo
            from PIL import Image

            img = Image.open(output_path)
            author_slug = _slugify_for_typo(artist) if artist else ""
            img = _overlay_cover_text(img, title, artist, author_slug=author_slug)
            img.save(output_path, format="PNG", optimize=True)
            result["text_overlay"] = True
            result["width"] = img.width
            result["height"] = img.height
            logger.info("Album cover with text saved: %s", output_path)
        except Exception as e:
            logger.warning("Text overlay failed (cover still saved without text): %s", e)
            result["text_overlay"] = False
            result["text_error"] = str(e)

        result["title"] = title
        result["artist"] = artist
        result["genre"] = genre
        return result

    def health(self) -> Dict[str, Any]:
        try:
            client = self._get_client()
            if client.is_running():
                return client.health()
            return {"name": self.name, "running": False}
        except Exception as e:
            return {"name": self.name, "running": False, "error": str(e)}


class NotionConnector(ExtensionConnector):
    """Connector for Notion workspace automation.

    Uses the NotionModule from apps/modules/notion.py.
    Notion is a cloud API — no local service to start/stop.
    """

    name = "notion"
    display_name = "Notion"

    def __init__(self):
        self._module = None

    def _get_module(self):
        if self._module is None:
            from apps.modules.notion import NotionModule
            self._module = NotionModule()
        return self._module

    def is_running(self) -> bool:
        try:
            mod = self._get_module()
            return mod._ensure_client().has_token
        except Exception:
            return False

    def ensure_running(self) -> bool:
        return self.is_running()

    def shutdown(self) -> bool:
        if self._module:
            self._module.shutdown()
        return True

    def execute(self, action: str, params: Optional[Dict] = None) -> Dict:
        """Execute a Notion action via the existing module."""
        mod = self._get_module()
        return mod.execute_action(action, params or {})

    def generate_template(self, template_type: str, parent_id: str,
                          customize: Optional[Dict] = None) -> Dict:
        """Generate a sellable Notion template pack."""
        return self.execute("notion_generate_template", {
            "template_type": template_type,
            "parent_id": parent_id,
            "customize": customize,
        })

    def health(self) -> Dict[str, Any]:
        has_token = self.is_running()
        return {"name": self.name, "running": has_token,
                "note": "Cloud API — no local service" if has_token
                        else "No NOTION_TOKEN configured"}


class JustEditConnector(ExtensionConnector):
    """Connector for JustEdit video editor.

    JustEdit runs as a Vite dev server (port 5173) in the browser.
    Uses the existing JustEditModule from apps/modules/justedit.py.
    """

    name = "justedit"
    display_name = "JustEdit"

    def __init__(self):
        self._module = None

    def _get_module(self):
        if self._module is None:
            from apps.modules.justedit import JustEditModule
            self._module = JustEditModule()
        return self._module

    def is_running(self) -> bool:
        try:
            mod = self._get_module()
            return mod.execute_action("justedit_status").get("running", False)
        except Exception:
            return False

    def ensure_running(self) -> bool:
        try:
            mod = self._get_module()
            mod.execute_action("justedit_start")
            return True
        except Exception as e:
            logger.error("Failed to start JustEdit: %s", e)
            return False

    def shutdown(self) -> bool:
        try:
            mod = self._get_module()
            mod.execute_action("justedit_stop")
            return True
        except Exception as e:
            logger.error("Failed to stop JustEdit: %s", e)
            return False

    def execute(self, action: str, params: Optional[Dict] = None) -> Dict:
        """Execute a JustEdit action via the existing module."""
        mod = self._get_module()
        return mod.execute_action(action, params or {})

    def health(self) -> Dict[str, Any]:
        running = self.is_running()
        return {"name": self.name, "running": running}


# ---------------------------------------------------------------------------
# Connector registry — singleton access
# ---------------------------------------------------------------------------

_connectors: Dict[str, ExtensionConnector] = {}


def get_connector(name: str) -> Optional[ExtensionConnector]:
    """Get a connector by extension name."""
    if not _connectors:
        _register_defaults()
    return _connectors.get(name)


def list_connectors() -> Dict[str, ExtensionConnector]:
    """Get all registered connectors."""
    if not _connectors:
        _register_defaults()
    return dict(_connectors)


def _register_defaults():
    """Register the built-in connectors."""
    _connectors["evera"] = EveraConnector()
    _connectors["smartengine"] = SmartEngineConnector()
    _connectors["notion"] = NotionConnector()
    _connectors["justedit"] = JustEditConnector()
