/**
 * BotKree8r — Character Creator Page
 *
 * Three-tab creator (Body / Face / Profile) with a live animated preview.
 * Exports portable .botkree8r.json files for desktop import.
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft, Download, Upload, RotateCcw,
  User, Palette, Sparkles, ChevronDown,
} from "lucide-react";

import { drawRobotBody, THEME_PRESETS, BODY_TYPES, type ThemeColors, type BodyType, type BodyBuild } from "../lib/robotBody";
import { FaceRenderer } from "../lib/faceRenderer";
import { FACE_STYLES, type FaceStyleDef } from "../lib/faceStyles";
import {
  defaultCharacter,
  BUILD_OPTIONS,
  EYE_STYLES,
  FACE_SHAPES,
  ACCESSORIES,
  PERSONALITIES,
  DEFAULT_POSES,
  IDLE_ANIMATIONS,
  type BotKree8rCharacter,
  type EyeStyle,
  type FaceShape,
  type Accessory,
  type Personality,
  type DefaultPose,
  type IdleAnimation,
} from "../lib/botkree8rSchema";

// ── Tabs ─────────────────────────────────────────────────────
type Tab = "body" | "face" | "profile";

const TABS: { id: Tab; label: string; icon: typeof Palette }[] = [
  { id: "body", label: "Body", icon: Palette },
  { id: "face", label: "Face", icon: Sparkles },
  { id: "profile", label: "Profile", icon: User },
];

// ── Color picker helper ──────────────────────────────────────
function ColorField({ label, value, onChange }: {
  label: string; value: string; onChange: (v: string) => void;
}) {
  return (
    <label className="flex items-center gap-3 group">
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-9 h-9 rounded-lg border-2 border-onyx-border/30 cursor-pointer bg-transparent
                   group-hover:border-onyx-accent/50 transition-colors appearance-none
                   [&::-webkit-color-swatch-wrapper]:p-0.5 [&::-webkit-color-swatch]:rounded-md [&::-webkit-color-swatch]:border-0"
      />
      <span className="text-sm text-onyx-text-dim font-mono">{label}</span>
    </label>
  );
}

// ── Select helper ────────────────────────────────────────────
function SelectField<T extends string>({ label, value, options, onChange }: {
  label: string; value: T; options: T[]; onChange: (v: T) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs text-onyx-text-dim font-mono uppercase tracking-wider mb-1 block">{label}</span>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value as T)}
          className="w-full bg-onyx-surface border border-onyx-border/30 rounded-lg px-3 py-2
                     text-sm text-white font-mono appearance-none cursor-pointer
                     hover:border-onyx-accent/40 focus:border-onyx-accent/60 focus:outline-none transition-colors"
        >
          {options.map((o) => (
            <option key={o} value={o}>{o.charAt(0).toUpperCase() + o.slice(1)}</option>
          ))}
        </select>
        <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-onyx-text-dim pointer-events-none" />
      </div>
    </label>
  );
}

// ═══════════════════════════════════════════════════════════════
// Live Preview Component
// ═══════════════════════════════════════════════════════════════
function LivePreview({ char }: { char: BotKree8rCharacter }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const faceRef = useRef<FaceRenderer | null>(null);
  const animRef = useRef<number>(0);
  const breathRef = useRef(0);

  // Get the selected face style's renderer class
  const styleDef = FACE_STYLES.find((s) => s.id === char.face.style) ?? FACE_STYLES[0];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Create face renderer
    const Ctor = styleDef.renderer;
    const face = new Ctor();
    face.setEmotion("neutral");
    faceRef.current = face;

    let running = true;
    let emotionTimer = 0;
    const emotions = ["neutral", "happy", "thinking", "confident", "excited"];
    let emotionIdx = 0;

    const loop = () => {
      if (!running) return;
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const w = rect.width;
      const h = rect.height;

      // Clear
      ctx.clearRect(0, 0, w, h);

      // Breathing
      breathRef.current += 0.012;
      if (breathRef.current > 1) breathRef.current -= 1;

      // Draw robot body
      const bodyScale = Math.min(w, h) / 500;
      const bodyCx = w / 2;
      const bodyCy = h * 0.28;
      const headPos = drawRobotBody(
        ctx, bodyCx, bodyCy, bodyScale,
        char.body.colors, char.body.type, char.body.build,
        breathRef.current,
      );

      // Draw face on top of the head position
      const faceSize = 130 * bodyScale;
      face.update(faceSize, faceSize);

      // Draw the face at the head position
      ctx.save();
      ctx.translate(headPos.x - faceSize / 2, headPos.y - faceSize + 5 * bodyScale);
      face.draw(ctx, faceSize, faceSize);
      ctx.restore();

      // Emotion cycling
      emotionTimer++;
      if (emotionTimer > 180) {
        emotionTimer = 0;
        emotionIdx = (emotionIdx + 1) % emotions.length;
        face.setEmotion(emotions[emotionIdx]);
      }

      animRef.current = requestAnimationFrame(loop);
    };

    animRef.current = requestAnimationFrame(loop);

    return () => {
      running = false;
      cancelAnimationFrame(animRef.current);
    };
  }, [styleDef, char.body.colors, char.body.type, char.body.build]);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full"
      style={{ imageRendering: "auto" }}
    />
  );
}

// ═══════════════════════════════════════════════════════════════
// Face Style Mini Preview
// ═══════════════════════════════════════════════════════════════
function FaceMiniPreview({ style, selected, onSelect }: {
  style: FaceStyleDef; selected: boolean; onSelect: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const Ctor = style.renderer;
    const face = new Ctor();
    face.setEmotion("happy");

    let running = true;
    const loop = () => {
      if (!running) return;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = 80 * dpr;
      canvas.height = 80 * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, 80, 80);

      face.update(80, 80);
      face.draw(ctx, 80, 80);
      animRef.current = requestAnimationFrame(loop);
    };

    animRef.current = requestAnimationFrame(loop);
    return () => { running = false; cancelAnimationFrame(animRef.current); };
  }, [style]);

  return (
    <button
      onClick={onSelect}
      className={`relative rounded-xl border-2 p-1 transition-all cursor-pointer group
        ${selected
          ? "border-onyx-accent bg-onyx-accent/10 shadow-lg shadow-onyx-accent/20"
          : "border-onyx-border/20 hover:border-onyx-accent/40 bg-onyx-surface/50"
        }`}
    >
      <canvas ref={canvasRef} className="w-20 h-20 rounded-lg" style={{ width: 80, height: 80 }} />
      <span className={`block text-[10px] font-mono mt-1 truncate px-1 ${selected ? "text-onyx-accent" : "text-onyx-text-dim"}`}>
        {style.name}
      </span>
    </button>
  );
}

// ═══════════════════════════════════════════════════════════════
// Body Type Mini Preview
// ═══════════════════════════════════════════════════════════════
function BodyTypeMiniPreview({ bodyType, colors, build, selected, onSelect }: {
  bodyType: import("../lib/robotBody").BodyTypeDef;
  colors: ThemeColors;
  build: BodyBuild;
  selected: boolean;
  onSelect: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const breathRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let running = true;
    const loop = () => {
      if (!running) return;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = 80 * dpr;
      canvas.height = 100 * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, 80, 100);

      breathRef.current += 0.01;
      if (breathRef.current > 1) breathRef.current -= 1;

      drawRobotBody(ctx, 40, 18, 0.42, colors, bodyType.id as BodyType, build, breathRef.current);
      animRef.current = requestAnimationFrame(loop);
    };

    animRef.current = requestAnimationFrame(loop);
    return () => { running = false; cancelAnimationFrame(animRef.current); };
  }, [bodyType, colors, build]);

  return (
    <button
      onClick={onSelect}
      className={`relative rounded-xl border-2 p-1 transition-all cursor-pointer group
        ${selected
          ? "border-onyx-accent bg-onyx-accent/10 shadow-lg shadow-onyx-accent/20"
          : "border-onyx-border/20 hover:border-onyx-accent/40 bg-onyx-surface/50"
        }`}
    >
      <canvas ref={canvasRef} className="w-20 h-[100px] rounded-lg" style={{ width: 80, height: 100 }} />
      <span className={`block text-[10px] font-mono mt-0.5 truncate px-1 ${selected ? "text-onyx-accent" : "text-onyx-text-dim"}`}>
        {bodyType.name}
      </span>
    </button>
  );
}

// ═══════════════════════════════════════════════════════════════
// Main Page Component
// ═══════════════════════════════════════════════════════════════
export default function BotKree8r() {
  const [char, setChar] = useState<BotKree8rCharacter>(defaultCharacter());
  const [tab, setTab] = useState<Tab>("body");
  const [showAllFaces, setShowAllFaces] = useState(false);

  // ── Updaters ─────────────────────────────────────────────
  const updateBody = useCallback((patch: Partial<BotKree8rCharacter["body"]>) => {
    setChar((prev) => ({ ...prev, body: { ...prev.body, ...patch } }));
  }, []);

  const updateBodyColors = useCallback((patch: Partial<ThemeColors>) => {
    setChar((prev) => ({
      ...prev,
      body: { ...prev.body, colors: { ...prev.body.colors, ...patch } },
    }));
  }, []);

  const updateFace = useCallback((patch: Partial<BotKree8rCharacter["face"]>) => {
    setChar((prev) => ({ ...prev, face: { ...prev.face, ...patch } }));
  }, []);

  const updateTraits = useCallback((patch: Partial<BotKree8rCharacter["traits"]>) => {
    setChar((prev) => ({ ...prev, traits: { ...prev.traits, ...patch } }));
  }, []);

  // ── Export ───────────────────────────────────────────────
  const handleExport = useCallback(() => {
    const exportChar: BotKree8rCharacter = {
      ...char,
      metadata: { ...char.metadata, created: new Date().toISOString() },
    };
    const json = JSON.stringify(exportChar, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${char.name || "my_bot"}.botkree8r.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [char]);

  // ── Import ───────────────────────────────────────────────
  const handleImport = useCallback(() => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json,.botkree8r.json";
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const data = JSON.parse(reader.result as string) as BotKree8rCharacter;
          if (data.version === "1.0" && data.body && data.face) {
            setChar(data);
          }
        } catch { /* ignore malformed files */ }
      };
      reader.readAsText(file);
    };
    input.click();
  }, []);

  // ── Reset ────────────────────────────────────────────────
  const handleReset = useCallback(() => setChar(defaultCharacter()), []);

  // ── Apply theme preset ──────────────────────────────────
  const applyTheme = useCallback((themeKey: string) => {
    const colors = THEME_PRESETS[themeKey];
    if (colors) updateBodyColors(colors);
  }, [updateBodyColors]);

  // ── Apply face style ────────────────────────────────────
  const applyFaceStyle = useCallback((style: FaceStyleDef) => {
    updateFace({ style: style.id, accent: style.accent, bg: style.bg });
  }, [updateFace]);

  // ── Visible faces ───────────────────────────────────────
  const visibleFaces = showAllFaces ? FACE_STYLES : FACE_STYLES.slice(0, 12);

  return (
    <div className="min-h-screen bg-onyx-bg text-white">
      {/* ── Header ── */}
      <header className="fixed top-0 w-full z-50 bg-onyx-bg/80 backdrop-blur-xl border-b border-onyx-border/20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" className="text-onyx-text-dim hover:text-white transition-colors">
              <ArrowLeft size={20} />
            </Link>
            <h1 className="font-mono font-bold text-lg">
              Bot<span className="text-onyx-accent">Kree8r</span>
            </h1>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleImport}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-mono
                         text-onyx-text-dim hover:text-white border border-onyx-border/20
                         hover:border-onyx-accent/30 transition-colors cursor-pointer"
            >
              <Upload size={14} /> Import
            </button>
            <button
              onClick={handleReset}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-mono
                         text-onyx-text-dim hover:text-white border border-onyx-border/20
                         hover:border-onyx-accent/30 transition-colors cursor-pointer"
            >
              <RotateCcw size={14} /> Reset
            </button>
            <button
              onClick={handleExport}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-mono font-bold
                         bg-onyx-accent/15 text-onyx-accent border border-onyx-accent/30
                         hover:bg-onyx-accent/25 transition-colors cursor-pointer"
            >
              <Download size={14} /> Export
            </button>
          </div>
        </div>
      </header>

      {/* ── Main Layout ── */}
      <main className="pt-16 flex flex-col lg:flex-row h-[calc(100vh)]">
        {/* ── Left: Controls ── */}
        <aside className="lg:w-[420px] xl:w-[480px] border-r border-onyx-border/10 overflow-y-auto">
          {/* Tab bar */}
          <div className="flex border-b border-onyx-border/15 sticky top-0 bg-onyx-bg/95 backdrop-blur z-10">
            {TABS.map((t) => {
              const Icon = t.icon;
              return (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`flex-1 flex items-center justify-center gap-2 py-3.5 text-sm font-mono
                    transition-colors cursor-pointer border-b-2
                    ${tab === t.id
                      ? "text-onyx-accent border-onyx-accent"
                      : "text-onyx-text-dim border-transparent hover:text-white hover:border-onyx-border/30"
                    }`}
                >
                  <Icon size={15} />
                  {t.label}
                </button>
              );
            })}
          </div>

          {/* Tab content */}
          <div className="p-5 space-y-6">
            <AnimatePresence mode="wait">
              {/* ════════════ BODY TAB ════════════ */}
              {tab === "body" && (
                <motion.div key="body" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10 }} className="space-y-6">
                  {/* Body Type — visual style */}
                  <div>
                    <h3 className="text-xs font-mono uppercase tracking-wider text-onyx-text-dim mb-3">
                      Body Type <span className="text-onyx-accent">({BODY_TYPES.length})</span>
                    </h3>
                    <div className="grid grid-cols-4 gap-2">
                      {BODY_TYPES.map((bt) => (
                        <BodyTypeMiniPreview
                          key={bt.id}
                          bodyType={bt}
                          colors={char.body.colors}
                          build={char.body.build}
                          selected={char.body.type === bt.id}
                          onSelect={() => updateBody({ type: bt.id })}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Body Build — proportional modifier */}
                  <div>
                    <h3 className="text-xs font-mono uppercase tracking-wider text-onyx-text-dim mb-3">Body Build</h3>
                    <div className="grid grid-cols-4 gap-2">
                      {BUILD_OPTIONS.map((bs) => (
                        <button
                          key={bs.id}
                          onClick={() => updateBody({ build: bs.id })}
                          className={`px-2 py-2.5 rounded-lg text-xs font-mono text-center transition-all cursor-pointer border
                            ${char.body.build === bs.id
                              ? "bg-onyx-accent/15 border-onyx-accent/50 text-onyx-accent"
                              : "bg-onyx-surface/50 border-onyx-border/20 text-onyx-text-dim hover:border-onyx-accent/30"
                            }`}
                          title={bs.desc}
                        >
                          {bs.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Body Colors */}
                  <div>
                    <h3 className="text-xs font-mono uppercase tracking-wider text-onyx-text-dim mb-3">Body Colors</h3>
                    <div className="space-y-3">
                      <ColorField label="Primary (outlines, bright accents)" value={char.body.colors.primary} onChange={(v) => updateBodyColors({ primary: v })} />
                      <ColorField label="Secondary (panels, mid-tone)" value={char.body.colors.secondary} onChange={(v) => updateBodyColors({ secondary: v })} />
                      <ColorField label="Dark (shadows, recessed)" value={char.body.colors.dark} onChange={(v) => updateBodyColors({ dark: v })} />
                    </div>
                  </div>

                  {/* Theme Presets */}
                  <div>
                    <h3 className="text-xs font-mono uppercase tracking-wider text-onyx-text-dim mb-3">Quick Themes</h3>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(THEME_PRESETS).map(([key, colors]) => (
                        <button
                          key={key}
                          onClick={() => applyTheme(key)}
                          className="group relative w-8 h-8 rounded-lg border border-onyx-border/20 overflow-hidden
                                     hover:border-onyx-accent/50 transition-all cursor-pointer hover:scale-110"
                          title={key}
                        >
                          <div className="absolute inset-0" style={{ background: `linear-gradient(135deg, ${colors.primary} 33%, ${colors.secondary} 66%, ${colors.dark})` }} />
                        </button>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}

              {/* ════════════ FACE TAB ════════════ */}
              {tab === "face" && (
                <motion.div key="face" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10 }} className="space-y-6">
                  {/* Face Style Grid */}
                  <div>
                    <h3 className="text-xs font-mono uppercase tracking-wider text-onyx-text-dim mb-3">
                      Face Style <span className="text-onyx-accent">({FACE_STYLES.length})</span>
                    </h3>
                    <div className="grid grid-cols-4 gap-2">
                      {visibleFaces.map((s) => (
                        <FaceMiniPreview
                          key={s.id}
                          style={s}
                          selected={char.face.style === s.id}
                          onSelect={() => applyFaceStyle(s)}
                        />
                      ))}
                    </div>
                    {!showAllFaces && FACE_STYLES.length > 12 && (
                      <button
                        onClick={() => setShowAllFaces(true)}
                        className="mt-3 w-full py-2 text-xs font-mono text-onyx-accent border border-onyx-accent/20
                                   rounded-lg hover:bg-onyx-accent/10 transition-colors cursor-pointer"
                      >
                        Show all {FACE_STYLES.length} faces
                      </button>
                    )}
                  </div>

                  {/* Face Colors */}
                  <div>
                    <h3 className="text-xs font-mono uppercase tracking-wider text-onyx-text-dim mb-3">Face Colors</h3>
                    <div className="space-y-3">
                      <ColorField label="Accent color" value={char.face.accent} onChange={(v) => updateFace({ accent: v })} />
                      <ColorField label="Background color" value={char.face.bg} onChange={(v) => updateFace({ bg: v })} />
                    </div>
                  </div>

                  {/* Eye & Shape */}
                  <div className="grid grid-cols-2 gap-4">
                    <SelectField label="Eye Style" value={char.traits.eye_style} options={EYE_STYLES} onChange={(v: EyeStyle) => updateTraits({ eye_style: v })} />
                    <SelectField label="Face Shape" value={char.traits.face_shape} options={FACE_SHAPES} onChange={(v: FaceShape) => updateTraits({ face_shape: v })} />
                  </div>
                </motion.div>
              )}

              {/* ════════════ PROFILE TAB ════════════ */}
              {tab === "profile" && (
                <motion.div key="profile" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10 }} className="space-y-6">
                  {/* Name */}
                  <label className="block">
                    <span className="text-xs text-onyx-text-dim font-mono uppercase tracking-wider mb-1 block">Character Name</span>
                    <input
                      type="text"
                      value={char.display_name}
                      onChange={(e) => {
                        const dn = e.target.value;
                        const slug = dn.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
                        setChar((p) => ({ ...p, display_name: dn, name: slug }));
                      }}
                      className="w-full bg-onyx-surface border border-onyx-border/30 rounded-lg px-3 py-2.5
                                 text-sm text-white font-mono placeholder:text-onyx-text-dim/50
                                 hover:border-onyx-accent/40 focus:border-onyx-accent/60 focus:outline-none transition-colors"
                      placeholder="My Bot"
                    />
                  </label>

                  {/* Description */}
                  <label className="block">
                    <span className="text-xs text-onyx-text-dim font-mono uppercase tracking-wider mb-1 block">Description</span>
                    <textarea
                      value={char.description}
                      onChange={(e) => setChar((p) => ({ ...p, description: e.target.value }))}
                      rows={3}
                      className="w-full bg-onyx-surface border border-onyx-border/30 rounded-lg px-3 py-2.5
                                 text-sm text-white font-mono placeholder:text-onyx-text-dim/50 resize-none
                                 hover:border-onyx-accent/40 focus:border-onyx-accent/60 focus:outline-none transition-colors"
                      placeholder="A custom character built with BotKree8r..."
                    />
                  </label>

                  {/* Accessory */}
                  <SelectField label="Accessory" value={char.traits.accessory} options={ACCESSORIES} onChange={(v: Accessory) => updateTraits({ accessory: v })} />

                  {/* Personality */}
                  <SelectField label="Personality" value={char.traits.personality} options={PERSONALITIES} onChange={(v: Personality) => updateTraits({ personality: v })} />

                  {/* Default Pose & Idle */}
                  <div className="grid grid-cols-2 gap-4">
                    <SelectField label="Default Pose" value={char.traits.default_pose} options={DEFAULT_POSES} onChange={(v: DefaultPose) => updateTraits({ default_pose: v })} />
                    <SelectField label="Idle Animation" value={char.traits.idle_animation} options={IDLE_ANIMATIONS} onChange={(v: IdleAnimation) => updateTraits({ idle_animation: v })} />
                  </div>

                  {/* Voice Pitch */}
                  <label className="block">
                    <span className="text-xs text-onyx-text-dim font-mono uppercase tracking-wider mb-1 block">
                      Voice Pitch: {char.traits.voice_pitch.toFixed(2)}
                    </span>
                    <input
                      type="range"
                      min={0.8}
                      max={1.2}
                      step={0.01}
                      value={char.traits.voice_pitch}
                      onChange={(e) => updateTraits({ voice_pitch: parseFloat(e.target.value) })}
                      className="w-full accent-[var(--color-onyx-accent)]"
                    />
                    <div className="flex justify-between text-[10px] text-onyx-text-dim font-mono mt-1">
                      <span>Deep (0.80)</span>
                      <span>Normal (1.00)</span>
                      <span>High (1.20)</span>
                    </div>
                  </label>

                  {/* Export Info */}
                  <div className="mt-6 p-4 rounded-xl bg-onyx-surface/50 border border-onyx-border/15">
                    <h4 className="text-xs font-mono font-bold text-onyx-accent mb-2">Export Instructions</h4>
                    <ol className="text-xs text-onyx-text-dim font-mono space-y-1.5 list-decimal list-inside">
                      <li>Click <span className="text-onyx-accent">Export</span> to download your <code>.botkree8r.json</code> file</li>
                      <li>In <span className="text-white">Animation Studio</span>: File → Import Character</li>
                      <li>Or drop the file in <code>data/characters/</code> to auto-load</li>
                      <li>Use as your main desktop Onyx character in Settings</li>
                    </ol>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </aside>

        {/* ── Right: Live Preview ── */}
        <section className="flex-1 relative bg-gradient-to-b from-onyx-surface/30 to-onyx-bg flex items-center justify-center overflow-hidden">
          {/* Grid background */}
          <div className="absolute inset-0 opacity-5"
            style={{
              backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.3) 1px, transparent 1px)",
              backgroundSize: "24px 24px",
            }}
          />

          {/* Character name badge */}
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10">
            <span className="px-4 py-1.5 rounded-full bg-onyx-surface/80 border border-onyx-border/20
                             text-sm font-mono text-onyx-accent backdrop-blur">
              {char.display_name || "Unnamed Bot"}
            </span>
          </div>

          {/* Preview canvas */}
          <div className="w-full h-full max-w-[600px] max-h-[700px] p-8">
            <LivePreview char={char} />
          </div>

          {/* Current face style badge */}
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2">
            <span className="px-3 py-1 rounded-full bg-onyx-surface/60 border border-onyx-border/15
                             text-xs font-mono text-onyx-text-dim backdrop-blur">
              Face: {FACE_STYLES.find((s) => s.id === char.face.style)?.name ?? "Classic"} •
              Body: {BODY_TYPES.find((b) => b.id === char.body.type)?.name ?? "Mech"} ({BUILD_OPTIONS.find((b) => b.id === char.body.build)?.label ?? "Standard"})
            </span>
          </div>
        </section>
      </main>
    </div>
  );
}
