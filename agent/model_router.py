"""Model Router — smart cloud→local failover for all LLM calls.

Routes each task type (vision, planner, reasoning, filesystem) to the
appropriate model with automatic fallback on failure.

Supports exo distributed inference when EXO_ENDPOINT is configured —
allows splitting large models across multiple devices.
"""

import os
import config
from log import get_logger

# Lazy import — `import ollama` blocks if the Ollama server isn't running
ollama = None

def _get_ollama():
    global ollama
    if ollama is None:
        import ollama as _ollama
        ollama = _ollama
    return ollama

_log = get_logger("model_router")

# exo distributed inference endpoint (e.g. "http://192.168.1.100:52415")
# Set via env var or config. When set, the router tries exo first for
# models that benefit from distributed inference (large reasoning models).
EXO_ENDPOINT = os.environ.get("EXO_ENDPOINT", getattr(config, "EXO_ENDPOINT", ""))
EXO_ENABLED = bool(EXO_ENDPOINT)


class ModelRouter:
    """Routes LLM calls to the right model with cloud→local fallback."""

    # Phrases that indicate the model cannot process images
    _VISION_BLIND_PHRASES = (
        "can't view images",
        "cannot view images",
        "can't see the screenshot",
        "cannot see the screenshot",
        "unable to view images",
        "unable to view the screenshot",
        "i'm unable to view",
        "i cannot view",
        "no screenshot provided",
        "can't view the image",
        "cannot view the image",
        "i can't see images",
        "no rendered image",
        "no image was provided",
        "i don't see an image",
        "image is not available",
    )

    def __init__(self):
        self._models = config.MODELS
        self._exo_client = None
        if EXO_ENABLED:
            try:
                from openai import OpenAI
                self._exo_client = OpenAI(
                    base_url=EXO_ENDPOINT,
                    api_key="not-needed",  # exo doesn't require auth
                )
                from log import get_logger
                get_logger("router").info(f"exo distributed inference enabled: {EXO_ENDPOINT}")
            except ImportError:
                from log import get_logger
                get_logger("router").info("exo endpoint configured but openai package not installed")
                self._exo_client = None

    def _get_chain(self, task_type: str) -> list[str]:
        """Get the ordered model chain for a task type."""
        entry = self._models.get(task_type, {})
        chain = []
        if entry.get("primary"):
            chain.append(entry["primary"])
        if entry.get("fallback") and entry["fallback"] != entry.get("primary"):
            chain.append(entry["fallback"])
        if not chain:
            raise ValueError(f"No models configured for task type '{task_type}'")
        return chain

    def _is_vision_blind(self, content: str) -> bool:
        """Check if a response indicates the model cannot process images."""
        lower = content.lower()
        return any(phrase in lower for phrase in self._VISION_BLIND_PHRASES)

    def chat(self, task_type: str, messages: list[dict], **kwargs) -> dict:
        """Call ollama.chat with smart failover.

        Args:
            task_type: One of 'vision', 'planner', 'reasoning', 'filesystem'.
            messages: Chat messages list.
            **kwargs: Extra args passed to ollama.chat.

        Returns:
            The ollama response dict.

        Raises:
            Last exception if all models fail.
        """
        chain = self._get_chain(task_type)
        last_error = None

        for model in chain:
            # Try exo first for non-vision tasks with large models
            if self._exo_client and task_type != "vision":
                try:
                    exo_result = self._try_exo(model, messages)
                    if exo_result:
                        return exo_result
                except Exception as e:
                    _log.debug(f"exo fallback failed for {model}: {e}")

            try:
                response = _get_ollama().chat(model=model, messages=messages, **kwargs)
                content = response.get("message", {}).get("content", "")
                if not content or not content.strip():
                    continue
                # Detect vision-blind responses (model can't process images)
                if self._is_vision_blind(content) and model != chain[-1]:
                    continue
                return response
            except Exception as e:
                last_error = e
                if model == chain[-1]:
                    raise

        raise last_error or RuntimeError(f"No models available for '{task_type}'")

    def get_content(self, task_type: str, messages: list[dict], **kwargs) -> str:
        """Convenience: call chat and return just the content string."""
        response = self.chat(task_type, messages, **kwargs)
        return response["message"]["content"]

    def get_primary(self, task_type: str) -> str:
        """Get the primary model name for a task type."""
        return self._models.get(task_type, {}).get("primary", "unknown")

    def get_fallback(self, task_type: str) -> str:
        """Get the fallback model name for a task type."""
        return self._models.get(task_type, {}).get("fallback", "unknown")

    def _try_exo(self, model: str, messages: list[dict]) -> dict | None:
        """Try to get a response via exo distributed inference.

        Returns an ollama-compatible response dict, or None if exo isn't available.
        exo exposes an OpenAI-compatible API, so we use the openai client.
        """
        if not self._exo_client:
            return None

        # Convert ollama messages to OpenAI format (strip images — exo doesn't do vision)
        oai_messages = []
        for msg in messages:
            oai_msg = {"role": msg["role"], "content": msg.get("content", "")}
            if "images" in msg:
                return None  # Can't send images via exo
            oai_messages.append(oai_msg)

        try:
            completion = self._exo_client.chat.completions.create(
                model=model,
                messages=oai_messages,
                temperature=0.7,
            )
            content = completion.choices[0].message.content
            if content and content.strip():
                # Wrap in ollama-compatible format
                return {
                    "message": {"role": "assistant", "content": content},
                    "model": model,
                    "done": True,
                }
        except Exception as e:
            _log.debug(f"exo request failed for {model}: {e}")

        return None

    @property
    def exo_available(self) -> bool:
        """Whether exo distributed inference is configured."""
        return self._exo_client is not None


# Singleton instance (also registered in service registry)
router = ModelRouter()

def _register_router():
    try:
        from core.service_registry import services
        if not services.has("model_router"):
            services.register("model_router", router)
    except Exception:
        pass

_register_router()
