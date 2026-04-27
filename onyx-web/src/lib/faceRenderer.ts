/**
 * AgentFace Core Renderer â€” HTML5 Canvas animated face engine.
 *
 * This is the base class that provides:
 *  - Eye blinking & gaze tracking
 *  - Phoneme-based mouth animation (lip sync)
 *  - Emotion system with smooth interpolation
 *  - Scale-factor rendering (works at any canvas size)
 *
 * Extend this class and override `draw()` to create new face styles.
 * All animation state (eyes, mouth, emotion) is managed in `update()`.
 *
 * Usage:
 *   const renderer = new FaceRenderer();
 *   // In your animation loop:
 *   renderer.update(width, height);
 *   renderer.draw(ctx, width, height);
 *   // Control:
 *   renderer.speak("Hello world");
 *   renderer.setEmotion("happy");
 *   renderer.setGaze(x, y);  // -1..1, -0.5..0.5
 */

import SPEC from "./face_spec.json";

// Design reference size
const REF_W = SPEC.reference.width;
const REF_H = SPEC.reference.height;

// Colors
const BG_COLOR = SPEC.colors.bg;
const FACE_COLOR = SPEC.colors.face;
const FACE_BORDER = SPEC.colors.face_border;
const EYE_SCLERA = SPEC.colors.eye_sclera;
const EYE_PUPIL = SPEC.colors.eye_pupil;
const EYE_GLOW_INNER = SPEC.colors.eye_glow_inner;
const EYE_GLOW_OUTER = SPEC.colors.eye_glow_outer;
const EYE_HIGHLIGHT = SPEC.colors.eye_highlight;
const MOUTH_INTERIOR = SPEC.colors.mouth_interior;
const ACCENT_BRIGHT = SPEC.colors.accent_bright;
const ACCENT_MID = SPEC.colors.accent_mid;
const ACCENT_DIM = SPEC.colors.accent_dim;
const ACCENT_VDIM = SPEC.colors.accent_vdim;

const EMOTION_ACCENT: Record<string, string> = SPEC.emotion_accents;

// Geometry
const EYE_WIDTH = SPEC.geometry.eye_width;
const EYE_HEIGHT = SPEC.geometry.eye_height;
const EYE_SPACING = SPEC.geometry.eye_spacing;
const EYE_Y = SPEC.geometry.eye_y;
const PUPIL_RADIUS = SPEC.geometry.pupil_radius;
const PUPIL_MAX_OX = SPEC.geometry.pupil_max_ox;
const PUPIL_MAX_OY = SPEC.geometry.pupil_max_oy;
const MOUTH_Y = SPEC.geometry.mouth_y;
const MOUTH_WIDTH = SPEC.geometry.mouth_width;
const MOUTH_HEIGHT = SPEC.geometry.mouth_height;

// Animation
const BLINK_INTERVAL_MIN = SPEC.animation.blink_interval_min;
const BLINK_INTERVAL_MAX = SPEC.animation.blink_interval_max;
const BLINK_DURATION = SPEC.animation.blink_duration;
const DOUBLE_BLINK_CHANCE = SPEC.animation.double_blink_chance;
const GAZE_CHANGE_MIN = SPEC.animation.gaze_change_min;
const GAZE_CHANGE_MAX = SPEC.animation.gaze_change_max;
const GAZE_SPEED = SPEC.animation.gaze_speed;

// Phoneme shapes
const PHONEME = {
  CLOSED: "closed", SMALL: "small", MEDIUM: "medium",
  WIDE: "wide", ROUND: "round", TEETH: "teeth",
};

const CHAR_TO_PHONEME: Record<string, string> = SPEC.phonemes.char_map;
const PHONEME_TARGETS: Record<string, number[]> = SPEC.phonemes.targets;

// Emotion presets
const EMOTION_PRESETS: Record<string, Record<string, number>> = SPEC.emotion_presets;

// â”€â”€â”€ Color helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export function hexToRgb(h: string): [number, number, number] {
  h = h.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

export function rgbToHex(r: number, g: number, b: number): string {
  const c = (v: number) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0");
  return `#${c(r)}${c(g)}${c(b)}`;
}

export function lerpColor(c1: string, c2: string, t: number): string {
  const [r1, g1, b1] = hexToRgb(c1);
  const [r2, g2, b2] = hexToRgb(c2);
  return rgbToHex(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t);
}

function textToPhonemes(text: string, charsPerSec = 12): [number, string][] {
  const result: [number, string][] = [];
  let t = 0;
  const dt = 1.0 / charsPerSec;
  for (const ch of text.toLowerCase()) {
    result.push([t, CHAR_TO_PHONEME[ch] || PHONEME.SMALL]);
    t += dt;
  }
  result.push([t, PHONEME.CLOSED]);
  return result;
}

function rand(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

// â”€â”€â”€ Re-export constants for style subclasses â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export {
  REF_W, REF_H, BG_COLOR, FACE_COLOR, FACE_BORDER,
  EYE_SCLERA, EYE_PUPIL, EYE_GLOW_INNER, EYE_GLOW_OUTER, EYE_HIGHLIGHT,
  MOUTH_INTERIOR, ACCENT_BRIGHT, ACCENT_MID, ACCENT_DIM, ACCENT_VDIM,
  EMOTION_ACCENT, EYE_WIDTH, EYE_HEIGHT, EYE_SPACING, EYE_Y,
  PUPIL_RADIUS, PUPIL_MAX_OX, PUPIL_MAX_OY, MOUTH_Y, MOUTH_WIDTH, MOUTH_HEIGHT,
  PHONEME, EMOTION_PRESETS,
};

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// FaceRenderer â€” Base class (Classic cyberpunk style)
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
export class FaceRenderer {
  eye: {
    gazeTargetX: number; gazeTargetY: number; gazeX: number; gazeY: number;
    blinkProgress: number; isBlinking: boolean; blinkTimer: number;
    nextBlink: number; doublePending: boolean; nextGazeChange: number; squint: number;
    saccadeX: number; saccadeY: number; nextSaccade: number;
  };
  mouth: {
    targetPhoneme: string; openAmount: number; widthFactor: number;
    phonemeSeq: [number, string][]; speechStart: number; isSpeaking: boolean; phonemeIdx: number;
    audioLevel: number;
  };
  emotion: Record<string, number>;
  emotionTargets: Record<string, number>;
  emotionName: string;
  colorTemp: number;         // -1 (cool) to +1 (warm), driven by emotion
  colorTempTarget: number;
  startTime: number;
  lastTime: number;
  pulse: number;
  breath: number;            // 0..1 inhale-exhale phase
  breathY: number;           // current vertical offset in ref-space px
  pupilNoise: number;        // small random pupil-size jitter
  headTilt: number;          // current head tilt in radians
  headTiltTarget: number;    // tilt target, retargeted every few seconds
  statusText: string;
  _cursorGaze: boolean;
  s: number;
  ox: number;
  oy: number;
  _audio: {
    ctx: AudioContext;
    analyser: AnalyserNode;
    source: MediaElementAudioSourceNode;
    buf: Uint8Array;
    el: HTMLMediaElement;
    detach: () => void;
  } | null;

  constructor() {
    this.eye = {
      gazeTargetX: 0, gazeTargetY: 0, gazeX: 0, gazeY: 0,
      blinkProgress: 0, isBlinking: false, blinkTimer: 0,
      nextBlink: 3, doublePending: false, nextGazeChange: 1.5, squint: 0,
      saccadeX: 0, saccadeY: 0, nextSaccade: 0.4,
    };
    this.mouth = {
      targetPhoneme: PHONEME.CLOSED, openAmount: 0, widthFactor: 1,
      phonemeSeq: [], speechStart: 0, isSpeaking: false, phonemeIdx: 0,
      audioLevel: 0,
    };
    this.emotion = {
      squint: 0, brow_raise: 0, eye_widen: 0, mouth_curve: 0,
      pupil_size: 1, gaze_speed: 1, blink_rate: 1, intensity: 0,
    };
    this.emotionTargets = { ...this.emotion };
    this.emotionName = "neutral";
    this.colorTemp = 0;
    this.colorTempTarget = 0;

    this.startTime = performance.now() / 1000;
    this.lastTime = this.startTime;
    this.pulse = 0;
    this.statusText = "";
    this._cursorGaze = false;

    this.breath = 0;
    this.breathY = 0;
    this.pupilNoise = 0;
    this.headTilt = 0;
    this.headTiltTarget = 0;
    this._audio = null;

    this.s = 1;
    this.ox = 0;
    this.oy = 0;
  }

  // â”€â”€â”€ Audio-reactive mouth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  attachAudio(el: HTMLMediaElement) {
    this.detachAudio();
    try {
      const AC: typeof AudioContext =
        (window as unknown as { AudioContext: typeof AudioContext; webkitAudioContext?: typeof AudioContext }).AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AC();
      const source = ctx.createMediaElementSource(el);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.5;
      source.connect(analyser);
      analyser.connect(ctx.destination);
      const buf = new Uint8Array(analyser.fftSize);
      const detach = () => {
        try { source.disconnect(); } catch { /* noop */ }
        try { analyser.disconnect(); } catch { /* noop */ }
        try { void ctx.close(); } catch { /* noop */ }
      };
      this._audio = { ctx, analyser, source, buf, el, detach };
    } catch {
      this._audio = null;
    }
  }

  detachAudio() {
    if (this._audio) {
      this._audio.detach();
      this._audio = null;
    }
  }

  _readAudioLevel(): number {
    const a = this._audio;
    if (!a) return 0;
    a.analyser.getByteTimeDomainData(a.buf as Uint8Array<ArrayBuffer>);
    let sum = 0;
    for (let i = 0; i < a.buf.length; i++) {
      const v = (a.buf[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / a.buf.length);
    return Math.min(1, rms * 3.5);
  }

  // â”€â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  speak(text: string, charsPerSec = 13) {
    this.mouth.phonemeSeq = textToPhonemes(text, charsPerSec);
    this.mouth.speechStart = performance.now() / 1000;
    this.mouth.isSpeaking = true;
    this.mouth.phonemeIdx = 0;
  }

  setEmotion(name: string) {
    this.emotionName = name;
    const p = EMOTION_PRESETS[name] || EMOTION_PRESETS.neutral;
    this.emotionTargets = { ...p };
    this._setColorTempTarget(name);
  }

  /** Blend multiple emotion presets by weight, e.g. { curious: 0.7, amused: 0.3 }. */
  setEmotionMix(weights: Record<string, number>) {
    const keys = ["squint", "brow_raise", "eye_widen", "mouth_curve", "pupil_size", "gaze_speed", "blink_rate", "intensity"];
    const blended: Record<string, number> = Object.fromEntries(keys.map((k) => [k, 0]));
    let total = 0;
    let dominant = "neutral";
    let dominantW = -Infinity;
    for (const [name, w] of Object.entries(weights)) {
      if (w <= 0) continue;
      const p = EMOTION_PRESETS[name];
      if (!p) continue;
      total += w;
      if (w > dominantW) { dominantW = w; dominant = name; }
      for (const k of keys) blended[k] += (p[k] ?? 0) * w;
    }
    if (total <= 0) {
      this.setEmotion("neutral");
      return;
    }
    for (const k of keys) blended[k] /= total;
    this.emotionName = dominant;
    this.emotionTargets = blended;
    this._setColorTempTarget(dominant);
  }

  /** Map emotion to color temperature: excited/happy = warm, sad/thinking = cool. */
  _setColorTempTarget(emotionName: string) {
    const warmEmotions = ["excited", "happy", "amused", "confident", "playful"];
    const coolEmotions = ["sad", "thinking", "focused", "tired", "skeptical"];
    if (warmEmotions.includes(emotionName)) {
      this.colorTempTarget = 0.6;  // warm
    } else if (coolEmotions.includes(emotionName)) {
      this.colorTempTarget = -0.5; // cool
    } else {
      this.colorTempTarget = 0;    // neutral
    }
  }

  setStatus(text: string) {
    this.statusText = text;
  }

  setGaze(x: number, y: number) {
    this._cursorGaze = true;
    this.eye.gazeTargetX = Math.max(-1, Math.min(1, x));
    this.eye.gazeTargetY = Math.max(-0.5, Math.min(0.5, y));
  }

  /** Set gaze to a world-space target (for multi-character scenes). */
  setGazeTarget(targetX: number, targetY: number, myX: number, myY: number) {
    this._cursorGaze = true;
    // Convert world-space delta to normalized gaze coordinates
    const dx = targetX - myX;
    const dy = targetY - myY;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < 1) {
      this.clearGaze();
      return;
    }
    // Normalize to -1..1 range with distance falloff
    const gazeX = Math.max(-1, Math.min(1, dx / 300));
    const gazeY = Math.max(-0.5, Math.min(0.5, dy / 300));
    this.eye.gazeTargetX = gazeX;
    this.eye.gazeTargetY = gazeY;
  }

  clearGaze() {
    this._cursorGaze = false;
  }

  getAccent(): string {
    return EMOTION_ACCENT[this.emotionName] || ACCENT_BRIGHT;
  }

  // â”€â”€â”€ Update + Draw â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  update(w: number, h: number) {
    const now = performance.now() / 1000;
    const dt = Math.min(now - this.lastTime, 0.1);
    this.lastTime = now;
    this.pulse = (now - this.startTime) * 0.8;
    this.breath = (this.breath + dt * 0.25) % 1;
    this.breathY = Math.sin(this.breath * Math.PI * 2) * 2.5;
    this.pupilNoise = this.pupilNoise * 0.92 + (Math.random() - 0.5) * 0.04;

    // Head tilt: re-target every ~3-7s, scaled by emotion intensity.
    if (Math.random() < dt / rand(3, 7)) {
      const range = 0.04 + this.emotion.intensity * 0.06; // ~2.3Â°..5.7Â°
      this.headTiltTarget = (Math.random() - 0.5) * 2 * range;
    }
    this.headTilt += (this.headTiltTarget - this.headTilt) * Math.min(1.5 * dt, 1.0);

    this._updateEmotion(dt);
    this._updateEyes(dt);
    this._updateMouth(dt, now);
    this._updateColorTemp(dt);
    this._recomputeScale(w, h);
  }

  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = BG_COLOR;
    ctx.fillRect(0, 0, w, h);

    if (this.s < 0.01) return;
    const cx = REF_W / 2;

    ctx.save();
    const cxPx = this._sx(cx);
    const cyPx = this._sy(REF_H / 2);
    ctx.translate(cxPx, cyPx + this.breathY * this.s);
    ctx.rotate(this.headTilt);
    ctx.translate(-cxPx, -cyPx);

    this._drawFacePlate(ctx, cx);

    const es = this.eye;
    const em = this.emotion;
    let blink = 1.0;
    if (es.isBlinking) {
      blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    }
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    this._drawEye(ctx, cx - EYE_SPACING / 2, EYE_Y, -1, blink);
    this._drawEye(ctx, cx + EYE_SPACING / 2, EYE_Y, 1, blink);

    // Brow micro-pulse: while speaking, modulate brow_raise by mouth openness
    // so accented syllables get a tiny lift (~0.05 max). Audio-driven when
    // attached, phoneme-driven otherwise.
    const speechBoost = this.mouth.isSpeaking || this.mouth.audioLevel > 0.05
      ? (this.mouth.audioLevel || this.mouth.openAmount) * 0.05
      : 0;
    const browActive = em.brow_raise + speechBoost;
    if (Math.abs(browActive) > 0.02) {
      this._drawBrows(ctx, cx, browActive);
    }

    this._drawMouth(ctx, cx, MOUTH_Y);
    this._drawDetails(ctx, cx);

    ctx.restore();
  }

  // â”€â”€â”€ Scale helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  _sx(x: number) { return this.ox + x * this.s; }
  _sy(y: number) { return this.oy + y * this.s; }
  _ss(v: number) { return v * this.s; }

  _recomputeScale(cw: number, ch: number) {
    if (cw < 2 || ch < 2) return;
    const sx = cw / REF_W;
    const sy = ch / REF_H;
    this.s = Math.min(sx, sy);
    this.ox = (cw - REF_W * this.s) / 2;
    this.oy = (ch - REF_H * this.s) / 2;
  }

  _updateColorTemp(dt: number) {
    const speed = Math.min(1.5 * dt, 1.0);
    this.colorTemp += (this.colorTempTarget - this.colorTemp) * speed;
  }

  /** Shift a color toward warm (orange) or cool (blue) based on colorTemp. */
  _applyColorTemp(baseColor: string): string {
    if (Math.abs(this.colorTemp) < 0.05) return baseColor;
    const [r, g, b] = hexToRgb(baseColor);
    const t = this.colorTemp;
    // Warm: boost red/yellow, reduce blue. Cool: boost blue, reduce red.
    const rShift = t > 0 ? t * 30 : t * 20;
    const gShift = t > 0 ? t * 15 : t * 10;
    const bShift = t > 0 ? -t * 25 : -t * 35;
    return rgbToHex(r + rShift, g + gShift, b + bShift);
  }

  _updateEmotion(dt: number) {
    const speed = Math.min(3.0 * dt, 1.0);
    const keys = ["squint", "brow_raise", "eye_widen", "mouth_curve", "pupil_size", "gaze_speed", "blink_rate", "intensity"];
    for (const k of keys) {
      this.emotion[k] += (this.emotionTargets[k] - this.emotion[k]) * speed;
    }
    this.eye.squint = this.emotion.squint;
  }

  _updateEyes(dt: number) {
    const es = this.eye;
    const em = this.emotion;
    es.blinkTimer += dt;
    const blinkMult = Math.max(0.2, em.blink_rate);
    if (!es.isBlinking && es.blinkTimer >= es.nextBlink) {
      es.isBlinking = true;
      es.blinkProgress = 0;
      es.blinkTimer = 0;
      es.nextBlink = rand(BLINK_INTERVAL_MIN, BLINK_INTERVAL_MAX) / blinkMult;
      if (Math.random() < DOUBLE_BLINK_CHANCE) es.doublePending = true;
    }
    if (es.isBlinking) {
      es.blinkProgress += dt / BLINK_DURATION;
      if (es.blinkProgress >= 2.0) {
        es.blinkProgress = 0;
        es.isBlinking = false;
        if (es.doublePending) {
          es.doublePending = false;
          es.nextBlink = 0.15;
          es.blinkTimer = 0;
        }
      }
    }
    es.nextGazeChange -= dt;
    if (es.nextGazeChange <= 0 && !this._cursorGaze) {
      es.gazeTargetX = rand(-1, 1);
      es.gazeTargetY = rand(-0.5, 0.5);
      if (Math.random() < 0.4) {
        es.gazeTargetX = rand(-0.1, 0.1);
        es.gazeTargetY = rand(-0.08, 0.08);
      }
      es.nextGazeChange = rand(GAZE_CHANGE_MIN, GAZE_CHANGE_MAX);
    }
    const speed = Math.min(GAZE_SPEED * em.gaze_speed * dt, 1.0);
    es.gazeX += (es.gazeTargetX - es.gazeX) * speed;
    es.gazeY += (es.gazeTargetY - es.gazeY) * speed;

    es.nextSaccade -= dt;
    if (es.nextSaccade <= 0) {
      es.saccadeX = (Math.random() - 0.5) * 0.18;
      es.saccadeY = (Math.random() - 0.5) * 0.12;
      es.nextSaccade = rand(0.2, 0.6);
    }
    es.saccadeX *= 0.85;
    es.saccadeY *= 0.85;
  }

  _updateMouth(dt: number, now: number) {
    const ms = this.mouth;
    if (ms.isSpeaking && ms.phonemeSeq.length > 0) {
      const elapsed = now - ms.speechStart;
      while (ms.phonemeIdx < ms.phonemeSeq.length - 1 && ms.phonemeSeq[ms.phonemeIdx + 1][0] <= elapsed) {
        ms.phonemeIdx++;
      }
      if (ms.phonemeIdx >= ms.phonemeSeq.length) {
        ms.isSpeaking = false;
        ms.targetPhoneme = PHONEME.CLOSED;
      } else {
        ms.targetPhoneme = ms.phonemeSeq[ms.phonemeIdx][1];
      }
      if (elapsed > ms.phonemeSeq[ms.phonemeSeq.length - 1][0] + 0.3) {
        ms.isSpeaking = false;
        ms.targetPhoneme = PHONEME.CLOSED;
      }
    } else {
      ms.targetPhoneme = PHONEME.CLOSED;
    }
    const [to, tw] = PHONEME_TARGETS[ms.targetPhoneme] || [0, 1];
    const ls = Math.min(14.0 * dt, 1.0);

    if (this._audio && (ms.isSpeaking || !this._audio.el.paused)) {
      const level = this._readAudioLevel();
      ms.audioLevel += (level - ms.audioLevel) * Math.min(20.0 * dt, 1.0);
      const audioOpen = Math.max(to, ms.audioLevel);
      ms.openAmount += (audioOpen - ms.openAmount) * Math.min(22.0 * dt, 1.0);
    } else {
      ms.audioLevel *= 0.9;
      ms.openAmount += (to - ms.openAmount) * ls;
    }
    ms.widthFactor += (tw - ms.widthFactor) * ls;
  }

  // â”€â”€â”€ Drawing methods â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  _drawFacePlate(ctx: CanvasRenderingContext2D, _cx: number) {
    const pad = 18, topPad = 22, botPad = 18;
    const x0 = pad, y0 = topPad;
    const x1 = REF_W - pad, y1 = REF_H - botPad;

    const pulse = 0.5 + 0.5 * Math.sin(this.pulse);
    const accent = this.getAccent();
    const accentDim = lerpColor(BG_COLOR, accent, 0.25);
    const accentMid = lerpColor(BG_COLOR, accent, 0.45);

    // Apply color temperature to border and glow
    const borderColor = this._applyColorTemp(lerpColor(accentDim, accentMid, pulse * 0.4));
    const glowColor = this._applyColorTemp(lerpColor(BG_COLOR, accentDim, pulse * 0.3));

    ctx.strokeStyle = glowColor;
    ctx.lineWidth = Math.max(1, this._ss(2));
    ctx.strokeRect(this._sx(x0 - 3), this._sy(y0 - 3), this._ss(x1 - x0 + 6), this._ss(y1 - y0 + 6));

    this._roundedRect(ctx, x0, y0, x1, y1, 16, FACE_COLOR, borderColor, Math.max(1, this._ss(2)));

    const barC = lerpColor(accentMid, accent, pulse * 0.5);
    ctx.fillStyle = barC;
    ctx.fillRect(this._sx(x0 + 30), this._sy(y0 + 1), this._ss(x1 - x0 - 60), this._ss(3));

    ctx.fillStyle = ACCENT_VDIM;
    ctx.fillRect(this._sx(x0 + 8), this._sy(y0 + 12), this._ss(x1 - x0 - 16), this._ss(1));

    ctx.fillStyle = accentDim;
    ctx.fillRect(this._sx(x0 + 50), this._sy(y1 - 4), this._ss(x1 - x0 - 100), this._ss(3));
  }

  _drawEye(ctx: CanvasRenderingContext2D, ex: number, ey: number, _side: number, blinkFactor: number) {
    void _side;
    const es = this.eye;
    const hw = EYE_WIDTH / 2;
    const hh = (EYE_HEIGHT / 2) * Math.max(blinkFactor, 0.03);

    ctx.strokeStyle = ACCENT_DIM;
    ctx.lineWidth = 1;
    this._ellipse(ctx, ex, ey, hw + 3, hh + 3, null, ACCENT_DIM);
    this._ellipse(ctx, ex, ey, hw, hh, EYE_SCLERA, FACE_BORDER);

    if (blinkFactor < 0.15) {
      ctx.strokeStyle = ACCENT_DIM;
      ctx.lineWidth = Math.max(1, this._ss(2));
      ctx.beginPath();
      ctx.moveTo(this._sx(ex - hw + 4), this._sy(ey));
      ctx.lineTo(this._sx(ex + hw - 4), this._sy(ey));
      ctx.stroke();
      return;
    }

    const px = ex + (es.gazeX + es.saccadeX) * PUPIL_MAX_OX;
    const py = ey + (es.gazeY + es.saccadeY) * PUPIL_MAX_OY;
    const pulse = 0.5 + 0.5 * Math.sin(this.pulse);
    const ps = this.emotion.pupil_size * (1 + this.pupilNoise);

    const glows: [number, string][] = [
      [PUPIL_RADIUS + 12, lerpColor("#001018", EYE_GLOW_OUTER, 0.5 + pulse * 0.3)],
      [PUPIL_RADIUS + 6, lerpColor(EYE_GLOW_OUTER, EYE_GLOW_INNER, 0.4 + pulse * 0.2)],
    ];
    for (const [radius, color] of glows) {
      const r = this._ss(radius * ps);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(this._sx(px), this._sy(py), r, 0, Math.PI * 2);
      ctx.fill();
    }

    const ir = this._ss((PUPIL_RADIUS + 2) * ps);
    ctx.strokeStyle = ACCENT_MID;
    ctx.lineWidth = Math.max(1, this._ss(2));
    ctx.beginPath();
    ctx.arc(this._sx(px), this._sy(py), ir, 0, Math.PI * 2);
    ctx.stroke();

    const pr = this._ss(PUPIL_RADIUS * ps);
    const pc = lerpColor(EYE_PUPIL, "#40e8ff", pulse * 0.3);
    ctx.fillStyle = pc;
    ctx.beginPath();
    ctx.arc(this._sx(px), this._sy(py), pr, 0, Math.PI * 2);
    ctx.fill();

    const dr = pr * 0.4;
    ctx.fillStyle = "#001520";
    ctx.beginPath();
    ctx.arc(this._sx(px), this._sy(py), dr, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = EYE_HIGHLIGHT;
    ctx.beginPath();
    ctx.arc(this._sx(px) - pr * 0.3, this._sy(py) - pr * 0.35, pr * 0.25, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#88ccdd";
    ctx.beginPath();
    ctx.arc(this._sx(px) + pr * 0.25, this._sy(py) + pr * 0.2, pr * 0.12, 0, Math.PI * 2);
    ctx.fill();
  }

  _drawBrows(ctx: CanvasRenderingContext2D, cx: number, browRaise: number) {
    const pulse = 0.5 + 0.5 * Math.sin(this.pulse);
    const bc = lerpColor(ACCENT_DIM, ACCENT_MID, 0.3 + Math.abs(browRaise) * 0.5 + pulse * 0.1);
    ctx.strokeStyle = bc;
    ctx.lineWidth = Math.max(1, this._ss(2.5));

    for (const side of [-1, 1]) {
      const ex = cx + side * (EYE_SPACING / 2);
      const hw = EYE_WIDTH / 2;
      const browY = EYE_Y - EYE_HEIGHT / 2 - 8;
      const raiseOffset = -browRaise * 12;
      const innerTilt = browRaise * 6 * side;
      const outerTilt = -browRaise * 3 * side;

      ctx.beginPath();
      for (let i = 0; i <= 10; i++) {
        const t = i / 10;
        const x = ex - hw * 0.8 + t * hw * 1.6;
        const arch = Math.sin(t * Math.PI) * (3 + browRaise * 6);
        const tilt = innerTilt * (1 - t) + outerTilt * t;
        const y = browY + raiseOffset - arch + tilt;
        if (i === 0) ctx.moveTo(this._sx(x), this._sy(y));
        else ctx.lineTo(this._sx(x), this._sy(y));
      }
      ctx.stroke();
    }
  }

  _drawMouth(ctx: CanvasRenderingContext2D, mx: number, my: number) {
    const ms = this.mouth;
    const w = MOUTH_WIDTH * ms.widthFactor;
    const hOpen = Math.max(MOUTH_HEIGHT * ms.openAmount * 4.0, 2);
    const hw = w / 2;
    const now = performance.now() / 1000;
    let sp = 0;
    if (ms.isSpeaking) sp = 0.5 + 0.5 * Math.sin(now * 15);

    if (ms.openAmount < 0.05) {
      const pulse = 0.5 + 0.5 * Math.sin(this.pulse);
      const mc = this.emotion.mouth_curve;
      const smileBoost = Math.max(0, mc) * 0.3;
      const lc = lerpColor(ACCENT_DIM, ACCENT_MID, pulse * 0.4 + smileBoost);
      ctx.strokeStyle = lc;
      ctx.lineWidth = Math.max(1, this._ss(2));
      ctx.beginPath();
      for (let i = 0; i <= 20; i++) {
        const t = i / 20;
        const x = mx - hw + t * w;
        const curve = Math.sin(t * Math.PI) * (3 + mc * 8);
        if (i === 0) ctx.moveTo(this._sx(x), this._sy(my - curve));
        else ctx.lineTo(this._sx(x), this._sy(my - curve));
      }
      ctx.stroke();
    } else {
      const top = my - hOpen * 0.35;
      const bot = my + hOpen * 0.65;
      const gp = 4;
      const gc = lerpColor("#000510", ACCENT_VDIM, sp * 0.5);

      this._ellipse(ctx, mx, (top + bot) / 2, hw + gp, (bot - top) / 2 + gp, gc, null);

      const mc = lerpColor(ACCENT_MID, ACCENT_BRIGHT, sp * 0.3);
      ctx.lineWidth = Math.max(1, this._ss(2));
      this._ellipse(ctx, mx, (top + bot) / 2, hw, (bot - top) / 2, MOUTH_INTERIOR, mc);

      const ins = 4;
      this._ellipse(ctx, mx, (top + bot) / 2, hw - ins, (bot - top) / 2 - ins, "#020508", null);

      if (ms.targetPhoneme === PHONEME.TEETH && ms.openAmount > 0.1) {
        const ty = top + (bot - top) * 0.22;
        const tw = hw * 0.55;
        ctx.fillStyle = "#223344";
        ctx.fillRect(this._sx(mx - tw), this._sy(ty), this._ss(tw * 2), this._ss(3));
      }

      if (ms.openAmount > 0.6) {
        const tgy = bot - (bot - top) * 0.3;
        const tgr = hw * 0.3;
        this._ellipse(ctx, mx, (tgy + bot - ins) / 2, tgr, (bot - ins - tgy) / 2, "#0a1520", null);
      }
    }
  }

  _drawDetails(ctx: CanvasRenderingContext2D, cx: number) {
    const pad = 18;
    const x0 = pad, y0 = 22;
    const x1 = REF_W - pad, y1 = REF_H - 18;

    ctx.strokeStyle = ACCENT_VDIM;
    ctx.lineWidth = 1;
    for (let i = 0; i < 3; i++) {
      const ly = y0 + 25 + i * 8;
      ctx.beginPath();
      ctx.moveTo(this._sx(x0 + 6), this._sy(ly));
      ctx.lineTo(this._sx(x0 + 22), this._sy(ly));
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(this._sx(x1 - 22), this._sy(ly));
      ctx.lineTo(this._sx(x1 - 6), this._sy(ly));
      ctx.stroke();
    }

    const pulse = 0.5 + 0.5 * Math.sin(this.pulse * 1.5);
    const dc = lerpColor(ACCENT_DIM, ACCENT_MID, pulse);
    const dr = this._ss(3);
    for (const dx of [x0 + 12, x1 - 12]) {
      ctx.fillStyle = dc;
      ctx.beginPath();
      ctx.arc(this._sx(dx), this._sy(y1 - 14), dr, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.strokeStyle = ACCENT_VDIM;
    ctx.beginPath();
    ctx.moveTo(this._sx(cx - 25), this._sy(MOUTH_Y + 35));
    ctx.lineTo(this._sx(cx + 25), this._sy(MOUTH_Y + 35));
    ctx.stroke();

    const ny = EYE_Y + EYE_HEIGHT / 2 + 5;
    ctx.fillStyle = ACCENT_VDIM;
    ctx.beginPath();
    ctx.moveTo(this._sx(cx - 4), this._sy(ny));
    ctx.lineTo(this._sx(cx + 4), this._sy(ny));
    ctx.lineTo(this._sx(cx), this._sy(ny + 8));
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = ACCENT_DIM;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(y0 + 21), this._ss(3), 0, Math.PI * 2);
    ctx.stroke();

    const step = Math.max(4, Math.round(4 / Math.max(this.s, 0.3)));
    const sy0 = Math.round(this._sy(y0));
    const sy1 = Math.round(this._sy(y1));
    const sx0 = this._sx(x0);
    const sxw = this._ss(x1 - x0);
    ctx.fillStyle = "rgba(0,0,0,0.07)";
    for (let y = sy0; y < sy1; y += step) {
      ctx.fillRect(sx0, y, sxw, 1);
    }

    if (this.statusText) {
      ctx.fillStyle = ACCENT_MID;
      ctx.font = `${Math.max(8, Math.round(this._ss(10)))}px Consolas, monospace`;
      ctx.textAlign = "center";
      ctx.fillText(this.statusText, this._sx(cx), this._sy(REF_H - 30));
    }
  }

  _ellipse(ctx: CanvasRenderingContext2D, cx: number, cy: number, rx: number, ry: number, fill: string | null, stroke: string | null) {
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(cy), this._ss(rx), this._ss(ry), 0, 0, Math.PI * 2);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.stroke(); }
  }

  _roundedRect(ctx: CanvasRenderingContext2D, x0: number, y0: number, x1: number, y1: number, radius: number, fill: string, stroke: string, lineWidth: number) {
    const r = Math.min(radius, (x1 - x0) / 2, (y1 - y0) / 2);
    ctx.beginPath();
    ctx.moveTo(this._sx(x0 + r), this._sy(y0));
    ctx.lineTo(this._sx(x1 - r), this._sy(y0));
    ctx.arcTo(this._sx(x1), this._sy(y0), this._sx(x1), this._sy(y0 + r), this._ss(r));
    ctx.lineTo(this._sx(x1), this._sy(y1 - r));
    ctx.arcTo(this._sx(x1), this._sy(y1), this._sx(x1 - r), this._sy(y1), this._ss(r));
    ctx.lineTo(this._sx(x0 + r), this._sy(y1));
    ctx.arcTo(this._sx(x0), this._sy(y1), this._sx(x0), this._sy(y1 - r), this._ss(r));
    ctx.lineTo(this._sx(x0), this._sy(y0 + r));
    ctx.arcTo(this._sx(x0), this._sy(y0), this._sx(x0 + r), this._sy(y0), this._ss(r));
    ctx.closePath();
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lineWidth || 1; ctx.stroke(); }
  }
}
