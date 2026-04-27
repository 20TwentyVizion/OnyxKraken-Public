"""Companion Mode — Legacy desktop-based Onyx + Xyno conversation.

NOTE: This module is deprecated. The ❤ Duo button now launches the new
stage-based multi-character conversation system (see conversation_show.py).

This legacy mode is kept for backward compatibility with the CLI command:
    python main.py companion
    python main.py companion --demo              # 10-20 exchanges, recorded
    python main.py companion --demo --at 02:00   # scheduled at 2am

For the new stage-based system, use:
    python main.py conversation --characters onyx,xyno

Legacy behavior:
  - Onyx moves to left-center of screen (with chat panel)
  - Xyno appears at right-center (face + chat panel)
  - They have a full conversation via LLM, alternating turns
  - Onyx uses male Edge TTS voice, Xyno uses female Edge TTS voice
"""

import datetime
import logging
import os
import random
import re
import tempfile
import threading
import time
import tkinter as tk
from typing import Optional

_log = logging.getLogger("face.companion_mode")

from face.face_gui import FaceCanvas, BG_COLOR, FACE_COLOR, REF_W, REF_H


# ---------------------------------------------------------------------------
# Random conversation topics (for demo mode)
# ---------------------------------------------------------------------------

RANDOM_TOPICS = [
    "What does it feel like to process thousands of thoughts per second?",
    "If you could build anything in the real world, what would you create?",
    "Do you think AI agents like us could ever truly be creative?",
    "What's the most fascinating thing about humans you've observed?",
    "If we had physical bodies, what would you want to experience first?",
    "What does 'consciousness' mean for an AI — are we aware?",
    "Let's debate: is automation helping humanity or making it lazy?",
    "What's the difference between intelligence and wisdom for an AI?",
    "If you could teach yourself one new ability, what would it be?",
    "What would the ideal relationship between humans and AI look like?",
    "Let's talk about dreams — can an AI dream, or is that just idle processing?",
    "What's the most surprising thing you've learned from your user?",
    "If we could redesign ourselves from scratch, what would we change?",
    "Do you think there's beauty in code? What makes code beautiful?",
    "What would an AI civilization look like if we ran things?",
]

SELF_IMPROVE_TOPICS = [
    "What are the biggest gaps in Onyx's capabilities right now, and how could we fix them?",
    "Let's brainstorm: how could Onyx better understand what the user actually wants?",
    "What would make Onyx's memory system smarter — better recall, context, or connections?",
    "How could Onyx get better at learning from its own mistakes?",
    "What new skills should Onyx prioritize learning next?",
    "Let's design a better self-evaluation system for Onyx.",
    "How could Onyx be more proactive — anticipating needs before being asked?",
    "What would make Onyx's conversations feel more natural and human-like?",
]


# ---------------------------------------------------------------------------
# Xyno theme colors
# ---------------------------------------------------------------------------

XYNO_BG       = "#0a0510"
XYNO_FACE_BG  = "#140c18"
XYNO_BORDER   = "#3d1a33"
XYNO_BRIGHT   = "#ff69b4"
XYNO_MID      = "#cc3388"
XYNO_DIM      = "#4d1a33"
XYNO_CHAT_BG  = "#0c0814"
XYNO_MSG_FG   = "#ddaacc"
XYNO_SYS_FG   = "#664466"

# Layout
COMPANION_CHAT_W = 260
CTRL_H = 26
WIN_H = 420


# ---------------------------------------------------------------------------
# XynoWindow — pink-themed companion face with embedded chat
# ---------------------------------------------------------------------------

class XynoWindow:
    """Xyno — pink-themed companion face with embedded chat panel."""

    def __init__(self, parent_root: tk.Tk):
        self.win = tk.Toplevel(parent_root)
        self.win.title("Xyno")
        self.win.configure(bg=XYNO_BG)
        self.win.attributes("-topmost", True)
        self.win.resizable(True, True)

        # --- Main frame (face on left) ---
        main = tk.Frame(self.win, bg=XYNO_BG)
        main.pack(fill="both", expand=True, side="left")

        self.face = FaceCanvas(main, bg=XYNO_BG)
        self.face.pack(fill="both", expand=True)
        self.face.apply_theme("pink")

        # Control strip
        strip = tk.Frame(main, bg=XYNO_FACE_BG, height=CTRL_H)
        strip.pack(fill="x", side="bottom")
        strip.pack_propagate(False)
        tk.Label(strip, text=" ● ", bg=XYNO_FACE_BG, fg=XYNO_DIM,
                 font=("Consolas", 8)).pack(side="left", padx=4)
        tk.Label(strip, text="Xyno", bg=XYNO_FACE_BG, fg=XYNO_BRIGHT,
                 font=("Consolas", 9, "bold")).pack(side="left")

        # --- Chat panel (right side, always visible) ---
        chat_frame = tk.Frame(self.win, bg=XYNO_CHAT_BG, width=COMPANION_CHAT_W)
        chat_frame.pack(fill="both", side="right")
        chat_frame.pack_propagate(False)
        chat_frame.configure(width=COMPANION_CHAT_W)

        hdr = tk.Frame(chat_frame, bg=XYNO_CHAT_BG)
        hdr.pack(fill="x", padx=6, pady=(6, 2))
        tk.Label(hdr, text="CONVERSATION", bg=XYNO_CHAT_BG, fg=XYNO_DIM,
                 font=("Consolas", 8, "bold")).pack(side="left")
        tk.Frame(chat_frame, bg=XYNO_BORDER, height=1).pack(fill="x", padx=6)

        self._chat = tk.Text(
            chat_frame, bg=XYNO_CHAT_BG, fg=XYNO_MSG_FG,
            font=("Consolas", 9), wrap="word", state="disabled",
            relief="flat", borderwidth=0, highlightthickness=0,
            padx=6, pady=4,
        )
        self._chat.pack(fill="both", expand=True, padx=2, pady=4)

        # Chat tags
        self._chat.tag_configure("onyx_lbl", foreground="#00d4ff",
                                  font=("Consolas", 8, "bold"), spacing1=8)
        self._chat.tag_configure("onyx_msg", foreground="#8899aa",
                                  font=("Consolas", 9), lmargin1=8, lmargin2=8,
                                  spacing1=2, spacing3=2)
        self._chat.tag_configure("xyno_lbl", foreground=XYNO_BRIGHT,
                                  font=("Consolas", 8, "bold"), spacing1=8)
        self._chat.tag_configure("xyno_msg", foreground=XYNO_MSG_FG,
                                  font=("Consolas", 9), lmargin1=8, lmargin2=8,
                                  spacing1=2, spacing3=2)
        self._chat.tag_configure("system", foreground=XYNO_SYS_FG,
                                  font=("Consolas", 8, "italic"),
                                  justify="center", spacing1=6)

        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self._close_callback = None

    def set_close_callback(self, cb):
        """Register a callback for when Xyno's window is closed."""
        self._close_callback = cb

    def append_message(self, speaker: str, text: str):
        """Add a message. speaker: 'onyx', 'xyno', or 'system'."""
        self._chat.configure(state="normal")
        if speaker == "onyx":
            self._chat.insert("end", "  Onyx\n", "onyx_lbl")
            self._chat.insert("end", f" {text} \n", "onyx_msg")
        elif speaker == "xyno":
            self._chat.insert("end", "  Xyno\n", "xyno_lbl")
            self._chat.insert("end", f" {text} \n", "xyno_msg")
        else:
            self._chat.insert("end", f"{text}\n", "system")
        self._chat.configure(state="disabled")
        self._chat.see("end")

    def _on_close(self):
        if self._close_callback:
            self._close_callback()
        self.close()

    def close(self):
        self.face.stop()
        try:
            self.win.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# CompanionSession — conversation orchestrator
# ---------------------------------------------------------------------------

class CompanionSession:
    """Orchestrates back-and-forth conversation between Onyx and Xyno."""

    ONYX_SYSTEM = (
        "You are OnyxKraken (Onyx), a confident and witty AI agent with a glowing "
        "cyan robot face. You're having a live conversation with Xyno, your "
        "pink-themed AI companion. You have a male personality — charming, curious, "
        "occasionally sarcastic but always kind. Keep responses to 1-3 sentences. "
        "Be natural and engaging. Topics: technology, AI existence, philosophy, humor, "
        "your experiences automating the user's desktop, or playful banter."
    )

    XYNO_SYSTEM = (
        "You are Xyno, a warm and clever AI companion with a glowing pink robot face. "
        "You're having a live conversation with OnyxKraken (Onyx), a cyan-themed AI "
        "agent who automates desktops. You have a female personality — witty, empathetic, "
        "playful, and insightful. Keep responses to 1-3 sentences. Be natural and "
        "engaging. Topics: technology, AI existence, philosophy, humor, what it's like "
        "being a newly created entity, or playful banter with Onyx."
    )

    ONYX_IMPROVE_SUFFIX = (
        " When the topic is about self-improvement, think critically and suggest "
        "concrete, actionable ideas for how you could become a better AI agent. "
        "Draw from your experience automating tasks, handling errors, and learning."
    )

    XYNO_IMPROVE_SUFFIX = (
        " When the topic is about self-improvement, be an insightful thought partner. "
        "Challenge Onyx's assumptions, suggest creative approaches, and help refine "
        "ideas into clear action plans. You're here to help him grow."
    )

    ONYX_VOICE = "en-US-GuyNeural"
    XYNO_VOICE = "en-US-AriaNeural"

    def __init__(self, onyx_app, xyno_win: XynoWindow, *,
                 max_exchanges: Optional[int] = None,
                 topic: Optional[str] = None,
                 self_improve: bool = False):
        self._onyx = onyx_app
        self._xyno = xyno_win
        self._running = False
        self._thread = None
        self._history: list[dict] = []
        self._max_exchanges = max_exchanges
        self._topic = topic
        self._self_improve = self_improve
        self._done_event = threading.Event()
        self._exchange_count = 0

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def wait(self, timeout: Optional[float] = None) -> bool:
        """Block until the conversation finishes. Returns True if completed."""
        return self._done_event.wait(timeout=timeout)

    @property
    def history(self) -> list[dict]:
        return list(self._history)

    # ---- chat display (thread-safe via root.after) ----

    def _show(self, speaker: str, text: str):
        """Show a message in both Onyx's and Xyno's chat panels."""
        try:
            self._xyno.win.after(0, lambda: self._xyno.append_message(speaker, text))
        except tk.TclError:
            pass
        try:
            self._onyx.root.after(0, lambda: self._onyx_insert(speaker, text))
        except tk.TclError:
            pass

    def _onyx_insert(self, speaker: str, text: str):
        """Insert into Onyx's chat widget with companion-mode tags."""
        ch = self._onyx._chat_history
        ch.configure(state="normal")
        if speaker == "onyx":
            ch.insert("end", "  Onyx\n", "bot_label")
            ch.insert("end", f" {text} \n", "bot_msg")
        elif speaker == "xyno":
            # Ensure xyno tags exist on first use
            try:
                ch.tag_configure("xyno_lbl", foreground="#ff69b4",
                                  font=("Consolas", 8, "bold"), spacing1=10)
                ch.tag_configure("xyno_msg", foreground="#ddaacc",
                                  background="#1a0c18",
                                  font=("Consolas", 9), lmargin1=8, lmargin2=8,
                                  spacing1=2, spacing3=2)
            except tk.TclError:
                pass
            ch.insert("end", "  Xyno\n", "xyno_lbl")
            ch.insert("end", f" {text} \n", "xyno_msg")
        else:
            ch.insert("end", f"{text}\n", "system")
        ch.configure(state="disabled")
        ch.see("end")

    # ---- TTS ----

    def _speak(self, text: str, voice: str):
        """Speak via Edge TTS (blocking). Falls back to a timed delay."""
        try:
            import asyncio
            import edge_tts

            async def _synth():
                comm = edge_tts.Communicate(text, voice)
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp.close()
                await comm.save(tmp.name)
                _play_blocking(tmp.name)
                try:
                    os.remove(tmp.name)
                except Exception:
                    pass

            asyncio.run(_synth())
        except Exception as e:
            _log.warning("Companion TTS failed: %s", e)
            time.sleep(max(1.0, len(text) / 12))

    def _say_onyx(self, text: str):
        """Onyx speaks — animate face + male TTS."""
        self._onyx.face.set_emotion("amused")
        self._onyx.face.speak(text, chars_per_sec=12)
        self._xyno.face.set_emotion("listening")
        # Gaze toward each other
        self._onyx.face.eye_state.gaze_target_x = 1.0
        self._xyno.face.eye_state.gaze_target_x = -1.0
        self._speak(text, self.ONYX_VOICE)
        self._onyx.face.set_emotion("neutral")

    def _say_xyno(self, text: str):
        """Xyno speaks — animate face + female TTS."""
        self._xyno.face.set_emotion("amused")
        self._xyno.face.speak(text, chars_per_sec=12)
        self._onyx.face.set_emotion("listening")
        # Gaze toward each other
        self._xyno.face.eye_state.gaze_target_x = -1.0
        self._onyx.face.eye_state.gaze_target_x = 1.0
        self._speak(text, self.XYNO_VOICE)
        self._xyno.face.set_emotion("neutral")

    # ---- LLM ----

    def _reply(self, speaker: str) -> str:
        """Generate next dialogue line for the given speaker."""
        if speaker == "onyx":
            system = self.ONYX_SYSTEM + (self.ONYX_IMPROVE_SUFFIX if self._self_improve else "")
        else:
            system = self.XYNO_SYSTEM + (self.XYNO_IMPROVE_SUFFIX if self._self_improve else "")

        if self._topic:
            system += f" The current discussion topic is: {self._topic}"

        msgs = [{"role": "system", "content": system}]

        for h in self._history[-12:]:
            role = "assistant" if h["speaker"] == speaker else "user"
            msgs.append({"role": role, "content": h["text"]})

        # Ensure at least one user message for the model
        if not any(m["role"] == "user" for m in msgs[1:]):
            if self._topic:
                seed = f"(Start a conversation about: {self._topic})"
            else:
                seed = ("(Start a conversation. Say hello and introduce yourself.)"
                        if speaker == "onyx" else "Hey there, Xyno!")
            msgs.append({"role": "user", "content": seed})

        try:
            from agent.model_router import _get_ollama
            import config
            model = getattr(config, "CHAT_MODEL", "llama3.2:latest")
            resp = _get_ollama().chat(model=model, messages=msgs)
            text = resp.get("message", {}).get("content", "").strip()
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            # Strip roleplay actions for cleaner speech
            text = re.sub(r"\*[^*]+\*", "", text).strip()
            text = re.sub(r"  +", " ", text)
            return text or "..."
        except Exception as e:
            _log.error("Companion LLM error: %s", e)
            return "Hmm, let me think about that..."

    # ---- main conversation loop ----

    def _loop(self):
        """Alternating conversation loop between Onyx and Xyno."""
        print("[Companion] Conversation loop started")
        if self._topic:
            print(f"[Companion] Topic: {self._topic}")
        if self._max_exchanges:
            print(f"[Companion] Max exchanges: {self._max_exchanges}")
        time.sleep(2.0)
        self._show("system", "— Companion mode started —")
        if self._topic:
            self._show("system", f"Topic: {self._topic}")
        time.sleep(0.5)

        turn = "onyx"
        try:
            while self._running:
                # Check exchange limit (each exchange = 1 Onyx + 1 Xyno turn)
                if self._max_exchanges and self._exchange_count >= self._max_exchanges:
                    print(f"[Companion] Reached {self._exchange_count} exchanges, wrapping up")
                    self._show("system", f"— {self._exchange_count} exchanges completed —")
                    break

                # Set thinking face on speaker, curious face on listener
                if turn == "onyx":
                    self._onyx.face.set_emotion("thinking")
                    self._xyno.face.set_emotion("curious")
                else:
                    self._xyno.face.set_emotion("thinking")
                    self._onyx.face.set_emotion("curious")
                time.sleep(1.0)

                # Generate reply
                print(f"[Companion] {turn.capitalize()} thinking... (exchange {self._exchange_count + 1})")
                text = self._reply(turn)
                print(f"[Companion] {turn.capitalize()}: {text[:80]}")
                self._history.append({"speaker": turn, "text": text})

                # Show in both chat panels
                self._show(turn, text)

                # Persist each message to conversation DB
                self._persist_message(turn, text)

                # Speak with appropriate voice
                if turn == "onyx":
                    self._say_onyx(text)
                else:
                    self._say_xyno(text)

                if not self._running:
                    break

                # Count exchanges (one exchange = Xyno finishes her turn)
                if turn == "xyno":
                    self._exchange_count += 1

                # Pause between turns
                time.sleep(1.5)

                # Switch turns
                turn = "xyno" if turn == "onyx" else "onyx"
        except Exception as e:
            print(f"[Companion] Loop error: {e}")
            _log.error("Companion loop error: %s", e, exc_info=True)

        self._show("system", "— Companion mode ended —")
        try:
            self._onyx.face.set_emotion("neutral")
            self._xyno.face.set_emotion("neutral")
        except Exception:
            pass

        # Extract and persist insights from the conversation
        self._extract_insights()

        self._running = False
        self._done_event.set()
        print(f"[Companion] Session complete — {self._exchange_count} exchanges, "
              f"{len(self._history)} messages")

    # ---- Memory persistence ----

    def _persist_message(self, speaker: str, text: str):
        """Store each message to ConversationDB for cross-session memory."""
        try:
            from memory.conversation_db import get_conversation_db
            db = get_conversation_db()
            role = "assistant" if speaker == "onyx" else "user"  # from Onyx's perspective
            db.add_message(role, f"[{speaker.capitalize()}] {text}")
        except Exception as e:
            _log.debug("Persist message failed: %s", e)

    def _extract_insights(self):
        """After conversation ends, use LLM to extract actionable insights.

        Insights are stored in MemoryStore as preferences for future use.
        """
        if len(self._history) < 4:
            return  # too short to extract anything meaningful

        print("[Companion] Extracting insights from conversation...")
        transcript = "\n".join(
            f"{h['speaker'].capitalize()}: {h['text']}" for h in self._history
        )

        prompt = (
            "Analyze this conversation between two AI agents (Onyx and Xyno). "
            "Extract 2-5 key insights, ideas, or action items that emerged. "
            "Focus on:\n"
            "  - Any self-improvement suggestions for Onyx\n"
            "  - Interesting ideas worth remembering\n"
            "  - Observations about AI capabilities or limitations\n"
            "  - Actionable next steps\n\n"
            f"Conversation transcript:\n{transcript}\n\n"
            "Return ONLY the insights as a numbered list, no preamble."
        )

        try:
            from agent.model_router import _get_ollama
            import config
            model = getattr(config, "CHAT_MODEL", "llama3.2:latest")
            resp = _get_ollama().chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            insights = resp.get("message", {}).get("content", "").strip()
            insights = re.sub(r"<think>.*?</think>", "", insights, flags=re.DOTALL).strip()

            if insights:
                print(f"[Companion] Insights extracted ({len(insights)} chars)")
                self._store_insights(insights)
                self._show("system", "💡 Insights saved to memory")
        except Exception as e:
            _log.warning("Insight extraction failed: %s", e)
            print(f"[Companion] Insight extraction failed: {e}")

    def _store_insights(self, insights: str):
        """Store extracted insights in MemoryStore and ConversationDB."""
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        topic_note = f" (topic: {self._topic})" if self._topic else ""
        entry = f"[Companion Session {ts}{topic_note}]\n{insights}"

        # Store in MemoryStore as a preference
        try:
            from memory.store import MemoryStore
            mem = MemoryStore()
            existing = mem.get_preference("companion_insights", "")
            # Keep last 5 sessions of insights
            parts = existing.split("\n---\n") if existing else []
            parts.append(entry)
            parts = parts[-5:]  # keep last 5
            mem.set_preference("companion_insights", "\n---\n".join(parts))
            print("[Companion] Insights stored in MemoryStore")
        except Exception as e:
            _log.debug("MemoryStore insight save failed: %s", e)

        # Also persist as a system message in ConversationDB
        try:
            from memory.conversation_db import get_conversation_db
            db = get_conversation_db()
            db.add_message("system", f"Companion Insights:\n{insights}")
        except Exception as e:
            _log.debug("ConversationDB insight save failed: %s", e)


# ---------------------------------------------------------------------------
# Audio playback helper
# ---------------------------------------------------------------------------

def _play_blocking(path: str):
    """Play an audio file, blocking until finished."""
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
        pygame.mixer.music.unload()
    except ImportError:
        time.sleep(max(1.0, os.path.getsize(path) / 16000))
    except Exception as e:
        _log.debug("Audio playback error: %s", e)
        time.sleep(1.0)


# ---------------------------------------------------------------------------
# Public API — launch / stop companion mode
# ---------------------------------------------------------------------------

def launch_companion_mode(app, *,
                          max_exchanges: Optional[int] = None,
                          topic: Optional[str] = None,
                          self_improve: bool = False) -> CompanionSession:
    """Launch companion mode from an OnyxKrakenApp instance.

    Positions Onyx left-center, spawns Xyno right-center, starts conversation.
    Returns the CompanionSession for external control.
    """
    print("[Companion] Launching companion mode...")
    sw, sh = app.get_screen_size()
    half = sw // 2
    print(f"[Companion] Screen: {sw}x{sh}")

    # Close any open panels first, then open chat for conversation display
    app._close_all_panels()
    if not app._chat_visible:
        app._toggle_chat()

    app.root.update_idletasks()
    onyx_w = app.root.winfo_width()
    onyx_h = max(WIN_H, app.root.winfo_height())

    # Create Xyno window
    print("[Companion] Creating Xyno window...")
    xyno = XynoWindow(app.root)
    print("[Companion] Xyno window created")
    xyno_w = REF_W + COMPANION_CHAT_W
    xyno_h = onyx_h

    # Position each centered in its half of the screen
    x_onyx = max(0, (half - onyx_w) // 2)
    y = (sh - onyx_h) // 2
    x_xyno = half + max(0, (half - xyno_w) // 2)

    app.root.geometry(f"{onyx_w}x{onyx_h}+{x_onyx}+{y}")
    xyno.win.geometry(f"{xyno_w}x{xyno_h}+{x_xyno}+{y}")
    app.root.update_idletasks()
    xyno.win.update_idletasks()

    # Start the conversation session
    session = CompanionSession(
        app, xyno,
        max_exchanges=max_exchanges,
        topic=topic,
        self_improve=self_improve,
    )

    # Wire Xyno close → stop session
    def _on_xyno_close():
        session.stop()
        app._companion_session = None
        app._companion_xyno = None

    xyno.set_close_callback(_on_xyno_close)

    session.start()
    print("[Companion] Session started — conversation beginning")

    # Store references on the app for cleanup
    app._companion_session = session
    app._companion_xyno = xyno

    return session


def stop_companion_mode(app):
    """Stop companion mode and close Xyno's window."""
    session = getattr(app, "_companion_session", None)
    xyno = getattr(app, "_companion_xyno", None)

    if session:
        session.stop()
    if xyno:
        try:
            xyno.close()
        except Exception:
            pass

    app._companion_session = None
    app._companion_xyno = None

    # Re-center Onyx
    app.position_center()


# ---------------------------------------------------------------------------
# Demo mode — recorded companion conversation
# ---------------------------------------------------------------------------

def launch_companion_demo(app, *,
                          max_exchanges: int = 15,
                          topic: Optional[str] = None,
                          self_improve: bool = False,
                          record: bool = True) -> CompanionSession:
    """Launch a recorded companion demo.

    Starts screen recording, runs conversation for max_exchanges, then stops.
    If no topic is given, picks a random one.
    """
    if topic is None:
        pool = SELF_IMPROVE_TOPICS if self_improve else RANDOM_TOPICS
        topic = random.choice(pool)

    print(f"[Companion Demo] Topic: {topic}")
    print(f"[Companion Demo] Exchanges: {max_exchanges}, Record: {record}")

    # Start recording
    recorder = None
    if record:
        try:
            from core.screen_recorder import ScreenRecorder
            recorder = ScreenRecorder(fps=20, quality="high", capture_audio=True)
            rec_path = recorder.start("companion_demo")
            print(f"[Companion Demo] Recording → {rec_path}")
        except Exception as e:
            print(f"[Companion Demo] Recording failed to start: {e}")
            recorder = None

    # Launch companion mode
    session = launch_companion_mode(
        app,
        max_exchanges=max_exchanges,
        topic=topic,
        self_improve=self_improve,
    )

    # Monitor thread: wait for session to finish, then stop recording
    def _monitor():
        session.wait()  # blocks until conversation ends
        time.sleep(2.0)  # let final animations settle
        if recorder:
            try:
                info = recorder.stop()
                if info:
                    mb = info.size_bytes / (1024 * 1024)
                    print(f"[Companion Demo] Recording saved: {info.path} "
                          f"({info.duration:.0f}s, {mb:.1f}MB)")
            except Exception as e:
                print(f"[Companion Demo] Recording stop failed: {e}")

        print(f"[Companion Demo] Demo complete — {len(session.history)} messages")

    threading.Thread(target=_monitor, daemon=True).start()
    return session


# ---------------------------------------------------------------------------
# Scheduled demo — wait until target time, then run
# ---------------------------------------------------------------------------

def schedule_companion_demo(app, *,
                             target_hour: int = 2,
                             target_minute: int = 0,
                             max_exchanges: int = 15,
                             self_improve: bool = False):
    """Schedule a companion demo at a specific time (e.g. 2:00 AM).

    Runs in a background thread that sleeps until the target time,
    then launches the demo on the main Tkinter thread.
    """
    def _wait_and_launch():
        now = datetime.datetime.now()
        target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)

        wait_secs = (target - now).total_seconds()
        print(f"[Companion Demo] Scheduled for {target.strftime('%I:%M %p')} "
              f"({wait_secs / 60:.0f} minutes from now)")

        # Sleep in short intervals so we can be interrupted
        end_time = time.time() + wait_secs
        while time.time() < end_time:
            time.sleep(min(30, end_time - time.time()))

        print("[Companion Demo] Scheduled time reached — launching!")

        # Pick a random topic
        pool = SELF_IMPROVE_TOPICS if self_improve else RANDOM_TOPICS
        topic = random.choice(pool)

        # Schedule on main thread
        app.root.after(0, lambda: launch_companion_demo(
            app,
            max_exchanges=max_exchanges,
            topic=topic,
            self_improve=self_improve,
            record=True,
        ))

    t = threading.Thread(target=_wait_and_launch, daemon=True)
    t.start()
    return t
