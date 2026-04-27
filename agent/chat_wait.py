"""Chat Wait — SSIM-based screen change detection for chat app responses.

Extracted from orchestrator.py. Handles the polling loop that waits for
a chat AI (Grok, ChatGPT, etc.) to finish generating its response by
monitoring screen stability via structural similarity (SSIM).
"""

import logging
import time

import numpy as np

_log = logging.getLogger("agent.chat_wait")

try:
    from skimage.metrics import structural_similarity as ssim
except ImportError:
    ssim = None

try:
    from vision.analyzer import capture_screenshot, save_screenshot
except (ImportError, RuntimeError):
    capture_screenshot = save_screenshot = None


def ssim_score(img1, img2) -> float:
    """Compute SSIM between two PIL images (grayscale)."""
    arr1 = np.array(img1.convert("L"))
    arr2 = np.array(img2.convert("L"))
    return ssim(arr1, arr2)


def wait_for_chat_response(wait_config: dict) -> tuple:
    """Wait for a chat AI to finish responding using SSIM screen change detection.

    Strategy:
      1. Take a baseline screenshot right after the message is sent.
      2. Poll every `poll_interval` seconds and compare to the previous frame.
      3. When SSIM drops below `change_threshold`, content is appearing.
      4. Once content has appeared, wait for the screen to stabilize
         (SSIM above `stable_threshold` for `stable_required` consecutive checks).

    Returns (final_screenshot, {"responded": True}) or (None, {"timeout": True}).
    """
    initial_wait = wait_config.get("initial_wait", 3)
    max_wait = wait_config.get("max_wait", 90)
    poll_interval = wait_config.get("poll_interval", 2.0)
    change_threshold = wait_config.get("change_threshold", 0.95)
    stable_threshold = wait_config.get("stable_threshold", 0.985)
    stable_required = wait_config.get("stable_required", 3)

    print(f"[Chat] Waiting {initial_wait}s for response to start...")
    time.sleep(initial_wait)

    baseline = capture_screenshot()
    save_screenshot(baseline, "chat_baseline")
    prev_frame = baseline

    start = time.time()
    content_appeared = False
    stable_count = 0
    check_num = 0

    # If no change detected for this many checks, assume response loaded before baseline
    no_change_limit = int(30 / poll_interval)  # ~30 seconds

    while time.time() - start < max_wait:
        time.sleep(poll_interval)
        check_num += 1
        current = capture_screenshot()
        save_screenshot(current, f"chat_poll_{check_num}")

        score = ssim_score(prev_frame, current)

        if not content_appeared:
            # Phase 1: Waiting for content to appear
            if score < change_threshold:
                content_appeared = True
                stable_count = 0
                print(f"[Chat] Response appearing (SSIM={score:.3f}, check #{check_num})")
            else:
                print(f"[Chat] Waiting for response... (SSIM={score:.3f}, check #{check_num})")
                # Early exit: if screen is static for too long, response may have
                # appeared before our baseline (fast response from the AI)
                if check_num >= no_change_limit:
                    print(f"[Chat] No change after {check_num * poll_interval:.0f}s — "
                          f"response may have loaded before monitoring. Proceeding to read.")
                    return current, {"responded": True}
        else:
            # Phase 2: Content appeared — wait for generation to finish
            if score >= stable_threshold:
                stable_count += 1
                print(f"[Chat] Stabilizing... ({stable_count}/{stable_required}, SSIM={score:.3f})")
                if stable_count >= stable_required:
                    print(f"[Chat] Response complete — screen stable for "
                          f"{stable_count * poll_interval:.0f}s")
                    return current, {"responded": True}
            else:
                stable_count = 0
                print(f"[Chat] Still generating (SSIM={score:.3f}, check #{check_num})")

        prev_frame = current

    # Timeout — but if content appeared, we likely have the response
    if content_appeared:
        print(f"[Chat] Timed out but content was detected. Proceeding to read.")
        return capture_screenshot(), {"responded": True}

    print(f"[Chat] Timed out after {max_wait}s — no screen change detected.")
    return None, {"timeout": True}
