"""EpisodePlayer — walk an Episode's beats and dispatch drive events.

Headless and programmatic; no GUI dependency. Other systems (REST,
MCP tool, autonomous agent) call play_episode(id) and the player publishes
events on the DriveBus that any subscribed renderer (desktop face,
browser canvas, recording sink) consumes.

State is kept per-run in a dict and is mutated by SetBeat. Guards
(`if`/`unless` on a beat) are evaluated as Python expressions against
that state — read-only access to vars only, no builtins.
"""

from __future__ import annotations

import logging
import string
import threading
import time
from pathlib import Path
from typing import Any, Optional

from core.drive import DriveEvent, get_bus
from core.episode.schema import (
    Episode, Beat, DialogueBeat, EmotionBeat, PoseBeat, AnimBeat,
    WaitBeat, SceneBeat, GotoBeat, SetBeat, ChoiceBeat,
    MusicBeat, SfxBeat, CameraBeat, LightingBeat, GazeBeat,
    load_episode,
)
from core.intent import classify
from core.animation import get_catalog


_log = logging.getLogger("core.episode.player")
_EPISODES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "episodes"


def _eval_guard(expr: Optional[str], vars: dict[str, Any]) -> bool:
    if not expr:
        return True
    try:
        return bool(eval(expr, {"__builtins__": {}}, dict(vars)))
    except Exception as e:
        _log.warning("Guard %r failed: %s", expr, e)
        return False


def _interpolate(text: str, vars: dict[str, Any]) -> str:
    try:
        return string.Formatter().vformat(text, (), vars)
    except Exception:
        return text


class EpisodePlayer:
    """Walks an Episode and dispatches events on the DriveBus."""

    def __init__(self, episode: Episode, vars: Optional[dict[str, Any]] = None) -> None:
        self.episode = episode
        self.vars: dict[str, Any] = dict(episode.vars)
        if vars:
            self.vars.update(vars)
        self.bus = get_bus()
        self._labels = episode.labels()
        self._stopped = threading.Event()

    def stop(self) -> None:
        self._stopped.set()

    # ------------------------------------------------------------------ run
    def run(self, blocking: bool = True) -> dict:
        """Walk all beats. Returns summary dict."""
        if blocking:
            return self._run()
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return {"status": "started", "episode": self.episode.id}

    def _publish(self, kind: str, character: str, **payload: Any) -> None:
        ev = DriveEvent(kind=kind, character=character, payload=payload, source="episode")
        self.bus.publish(ev)

    def _run(self) -> dict:
        self._publish("episode_beat", "*",
                      episode=self.episode.id, status="start",
                      cast=self.episode.cast, scene=self.episode.scene)
        if self.episode.scene:
            self._publish("scene", "*", scene=self.episode.scene, transition="cut")

        executed = 0
        idx = 0
        catalog = get_catalog()

        while idx < len(self.episode.beats):
            if self._stopped.is_set():
                break
            beat = self.episode.beats[idx]
            if not _eval_guard(beat.if_, self.vars):
                idx += 1
                continue
            if beat.unless and _eval_guard(beat.unless, self.vars):
                idx += 1
                continue

            jump = self._dispatch(beat, catalog)
            executed += 1

            if jump is not None:
                if jump in self._labels:
                    idx = self._labels[jump]
                else:
                    _log.warning("goto %r: label not found", jump)
                    idx = len(self.episode.beats)
                continue
            idx += 1

        self._publish("episode_beat", "*",
                      episode=self.episode.id, status="end",
                      executed=executed)
        return {
            "status": "ok",
            "episode": self.episode.id,
            "beats_executed": executed,
            "vars": dict(self.vars),
        }

    # --------------------------------------------------------- dispatch one
    def _dispatch(self, beat: Beat, catalog) -> Optional[str]:
        """Run a beat. Return a goto-target if branching, else None."""
        if isinstance(beat, DialogueBeat):
            self._dispatch_dialogue(beat, catalog)
            return None
        if isinstance(beat, EmotionBeat):
            payload: dict[str, Any] = {
                "emotion": beat.emotion,
                "intensity": beat.intensity,
                "hold_ms": 0,
            }
            if beat.mix:
                payload["mix"] = dict(beat.mix)
            self._publish("emotion", beat.who, **payload)
            return None
        if isinstance(beat, PoseBeat):
            self._publish("pose", beat.who, pose=beat.pose,
                          transition_ms=beat.transition_ms)
            return None
        if isinstance(beat, AnimBeat):
            self._publish("body_anim", beat.who, animation=beat.anim, loop=beat.loop)
            return None
        if isinstance(beat, WaitBeat):
            time.sleep(max(0.0, beat.wait_ms / 1000.0))
            return None
        if isinstance(beat, SceneBeat):
            self._publish("scene", "*", scene=beat.scene, transition=beat.transition)
            return None
        if isinstance(beat, SetBeat):
            self.vars.update(beat.set)
            return None
        if isinstance(beat, GotoBeat):
            return beat.goto
        if isinstance(beat, ChoiceBeat):
            return self._dispatch_choice(beat)
        if isinstance(beat, MusicBeat):
            self._publish("music", "*", track=beat.track, action=beat.action,
                          volume=beat.volume, fade_ms=beat.fade_ms)
            return None
        if isinstance(beat, SfxBeat):
            self._publish("sfx", "*", sound=beat.sound, volume=beat.volume,
                          delay_ms=beat.delay_ms)
            return None
        if isinstance(beat, CameraBeat):
            self._publish("camera", "*", action=beat.action, target=beat.target,
                          duration_ms=beat.duration_ms, easing=beat.easing)
            return None
        if isinstance(beat, LightingBeat):
            self._publish("lighting", "*", preset=beat.preset, intensity=beat.intensity,
                          color=beat.color, transition_ms=beat.transition_ms)
            return None
        if isinstance(beat, GazeBeat):
            self._publish("gaze", beat.who, target=beat.target, x=beat.x, y=beat.y)
            return None
        return None

    def _dispatch_dialogue(self, beat: DialogueBeat, catalog) -> None:
        text = _interpolate(beat.say, self.vars)
        result = classify(text)
        self._publish("speak", beat.who, text=result.clean_text,
                      mood=beat.mood, original=beat.say)
        primary = result.primary_emotion
        if primary:
            self._publish("emotion", beat.who, emotion=primary, intensity=1.0)
            if beat.auto_pose:
                link_pose, link_anim = catalog.link_for(primary)
                if link_pose and not result.poses:
                    result.poses.append(link_pose)
                if link_anim and not result.body_anims:
                    result.body_anims.append(link_anim)
        for p in result.poses:
            if catalog.pose(p):
                self._publish("pose", beat.who, pose=p, transition_ms=300)
        for a in result.body_anims:
            if catalog.body_anim(a):
                self._publish("body_anim", beat.who, animation=a, loop=False)

        # Approximate dialogue duration so subsequent beats wait for speech.
        approx_secs = max(0.6, len(result.clean_text) / 14.0)
        time.sleep(approx_secs)

    def _dispatch_choice(self, beat: ChoiceBeat) -> Optional[str]:
        valid = [
            o for o in beat.options
            if _eval_guard(o.if_, self.vars)
        ]
        if not valid:
            return None
        self._publish("choice", beat.who, prompt=beat.prompt,
                      options=[{"text": o.text, "goto": o.goto} for o in valid])
        # Headless default: pick the first valid option. Interactive runners
        # can override by subscribing to the "choice" event and calling
        # set_choice() — for now we auto-advance to keep the player headless.
        return valid[0].goto


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------

def _resolve_path(episode_id: str) -> Optional[Path]:
    for ext in (".yaml", ".yml", ".json"):
        candidate = _EPISODES_DIR / f"{episode_id}{ext}"
        if candidate.exists():
            return candidate
    return None


def play_episode(episode_id: str, vars: Optional[dict] = None,
                 blocking: bool = False) -> dict:
    path = _resolve_path(episode_id)
    if path is None:
        return {"error": f"Episode not found: {episode_id!r}"}
    try:
        episode = load_episode(path)
    except Exception as e:
        return {"error": f"Failed to load episode {episode_id!r}: {e}"}
    player = EpisodePlayer(episode, vars=vars)
    return player.run(blocking=blocking)


def list_episodes() -> list[dict]:
    """Return metadata for every episode under data/episodes/."""
    if not _EPISODES_DIR.exists():
        return []
    out: list[dict] = []
    for path in sorted(_EPISODES_DIR.iterdir()):
        if path.suffix.lower() not in (".yaml", ".yml", ".json"):
            continue
        try:
            ep = load_episode(path)
            out.append({
                "id": ep.id, "title": ep.title, "cast": ep.cast,
                "scene": ep.scene, "beats": len(ep.beats),
                "description": ep.description, "path": str(path.name),
            })
        except Exception as e:
            out.append({"id": path.stem, "error": str(e), "path": str(path.name)})
    return out
