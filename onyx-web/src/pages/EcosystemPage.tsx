import { useRef, useEffect, useState, useCallback } from "react";
import { motion, useInView } from "framer-motion";
import {
  Brain, Palette, Music, Theater, Swords, Monitor,
  Mic, Hammer, Video, Gamepad2, Plug, GitBranch,
  Sparkles, ArrowRight, Play, Eye, ChevronDown,
} from "lucide-react";
import SiteNav from "../components/SiteNav";
import { FaceRenderer } from "../lib/faceRenderer";
import { FACE_STYLES, type FaceStyleDef } from "../lib/faceStyles";

// ─── Hero Face ──────────────────────────────────────────
function HeroFace() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const renderer = new FaceRenderer();

    const emotions = ["neutral", "curious", "happy", "thinking", "amused", "proud", "excited"];
    let idx = 0;
    renderer.setEmotion(emotions[0]);
    const loop1 = setInterval(() => {
      idx = (idx + 1) % emotions.length;
      renderer.setEmotion(emotions[idx]);
    }, 3500);

    const texts = [
      "I'm Onyx.",
      "I create music, shows, and worlds.",
      "The ecosystem is my hands.",
    ];
    let tIdx = 0;
    const loop2 = setInterval(() => {
      renderer.speak(texts[tIdx % texts.length]);
      tIdx++;
    }, 6000);
    setTimeout(() => renderer.speak(texts[0]), 800);

    let animId: number;
    let cssW = 0, cssH = 0;
    function frame() {
      renderer.update(cssW, cssH);
      renderer.draw(ctx!, cssW, cssH);
      animId = requestAnimationFrame(frame);
    }
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      cssW = rect.width;
      cssH = rect.height;
      canvas.width = cssW * dpr;
      canvas.height = cssH * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    frame();

    const handleMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = ((e.clientY - rect.top) / rect.height) - 0.5;
      renderer.setGaze(x * 0.6, y * 0.4);
    };
    const handleLeave = () => renderer.clearGaze();
    canvas.addEventListener("mousemove", handleMove);
    canvas.addEventListener("mouseleave", handleLeave);

    return () => {
      cancelAnimationFrame(animId);
      clearInterval(loop1);
      clearInterval(loop2);
      ro.disconnect();
      canvas.removeEventListener("mousemove", handleMove);
      canvas.removeEventListener("mouseleave", handleLeave);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="w-full h-full block rounded-2xl"
      style={{ background: "#050810" }}
    />
  );
}

// ─── Ecosystem Hub Node ─────────────────────────────────
interface HubNode {
  id: string;
  label: string;
  icon: typeof Brain;
  color: string;
  desc: string;
  angle: number;
}

const HUB_NODES: HubNode[] = [
  { id: "chat", label: "AI Chat", icon: Brain, color: "#7c5cff", desc: "Conversational AI with memory, vision, and self-improvement", angle: 0 },
  { id: "studio", label: "Animation Studio", icon: Theater, color: "#ffd32a", desc: "Multi-character 2.5D scenes with timeline, keyframes, and IK", angle: 60 },
  { id: "music", label: "Music Production", icon: Music, color: "#ff6b81", desc: "AI-composed tracks, beat battles, and DJ automation", angle: 120 },
  { id: "blender", label: "3D Creation", icon: Palette, color: "#ff9f43", desc: "Procedural characters, buildings, and worlds in Blender", angle: 180 },
  { id: "shows", label: "AI Shows", icon: Video, color: "#00ff88", desc: "Full episode production — script to screen via OAE pipeline", angle: 240 },
  { id: "battles", label: "Beat Battles", icon: Swords, color: "#ff4757", desc: "AI vs AI music competition with automated judging", angle: 300 },
];

function EcosystemHub() {
  const [active, setActive] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });

  const radius = 180;

  return (
    <div ref={ref} className="relative w-[500px] h-[500px] mx-auto">
      {/* Center — Onyx */}
      <motion.div
        initial={{ scale: 0 }}
        animate={inView ? { scale: 1 } : {}}
        transition={{ type: "spring", stiffness: 150, delay: 0.2 }}
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-24 h-24 rounded-full bg-onyx-panel border-2 border-onyx-accent/50 flex items-center justify-center shadow-[0_0_40px_rgba(0,212,255,0.2)] z-10"
      >
        <div className="text-center">
          <Eye size={24} className="text-onyx-accent mx-auto mb-1" />
          <span className="text-[10px] font-mono font-bold text-onyx-accent">ONYX</span>
        </div>
      </motion.div>

      {/* Nodes */}
      {HUB_NODES.map((node, i) => {
        const rad = (node.angle * Math.PI) / 180;
        const x = 250 + Math.cos(rad) * radius - 36;
        const y = 250 + Math.sin(rad) * radius - 36;
        const isActive = active === node.id;
        const Icon = node.icon;

        return (
          <motion.div
            key={node.id}
            initial={{ scale: 0, opacity: 0 }}
            animate={inView ? { scale: 1, opacity: 1 } : {}}
            transition={{ type: "spring", stiffness: 150, delay: 0.4 + i * 0.1 }}
            className="absolute"
            style={{ left: x, top: y }}
          >
            {/* Connection line */}
            <svg
              className="absolute pointer-events-none"
              style={{
                left: 36, top: 36,
                width: 1, height: 1,
                overflow: "visible",
              }}
            >
              <line
                x1={0} y1={0}
                x2={250 - x - 36} y2={250 - y - 36}
                stroke={isActive ? node.color : "#1a2a3d"}
                strokeWidth={isActive ? 2 : 1}
                strokeDasharray={isActive ? "none" : "4 4"}
                opacity={isActive ? 0.8 : 0.4}
              />
            </svg>

            {/* Node circle */}
            <button
              onClick={() => setActive(isActive ? null : node.id)}
              onMouseEnter={() => setActive(node.id)}
              onMouseLeave={() => setActive(null)}
              className="relative w-[72px] h-[72px] rounded-full border-2 flex flex-col items-center justify-center transition-all duration-300 z-10"
              style={{
                borderColor: isActive ? node.color : node.color + "40",
                background: isActive ? node.color + "20" : "#0c1220",
                boxShadow: isActive ? `0 0 24px ${node.color}30` : "none",
              }}
            >
              <Icon size={20} style={{ color: node.color }} />
              <span className="text-[8px] font-mono mt-0.5 text-onyx-text-dim">{node.label}</span>
            </button>

            {/* Tooltip */}
            {isActive && (
              <motion.div
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-48 p-3 rounded-xl bg-onyx-panel border border-onyx-border/40 shadow-xl z-20"
              >
                <p className="text-xs font-mono text-onyx-text leading-relaxed">{node.desc}</p>
              </motion.div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}

// ─── Capability Section ─────────────────────────────────
interface Capability {
  icon: typeof Brain;
  title: string;
  subtitle: string;
  desc: string;
  color: string;
  stats: string[];
}

const CAPABILITIES: Capability[] = [
  {
    icon: Theater,
    title: "Animation Studio",
    subtitle: "Multi-character 2.5D scenes",
    desc: "Full scene editor with 8+ robot characters, IK rigs, timeline, keyframes, body animations, and camera control. Characters have unique faces, body styles, and personalities.",
    color: "#ffd32a",
    stats: ["8 characters", "62-bone rigs", "10 body animations", "2.5D camera"],
  },
  {
    icon: Video,
    title: "AI Episode Production",
    subtitle: "Script to screen, autonomously",
    desc: "The OAE pipeline takes a prompt and produces a full animated episode — writer, storyboard, casting, direction, editing, QA. Seven AI agents collaborate to create content.",
    color: "#00ff88",
    stats: ["7 AI agents", "Full pipeline", "Auto TTS", "Auto scoring"],
  },
  {
    icon: Music,
    title: "Music Production",
    subtitle: "AI-composed beats and tracks",
    desc: "Batch music generation, automated DJ sets, and a full beat battle system where AI DJs compete head-to-head with AI judges scoring originality, production, and impact.",
    color: "#ff6b81",
    stats: ["Beat battles", "AI judging", "Auto deployment", "5-round format"],
  },
  {
    icon: Palette,
    title: "3D Creation",
    subtitle: "Blender + Unreal Engine",
    desc: "Procedural character generation with 62-bone skeletons, auto-weighted meshes, skin shaders, and eye systems. Plus architectural generation — houses, buildings, furnished interiors.",
    color: "#ff9f43",
    stats: ["62-bone skeletons", "200+ helpers", "Auto quality", "6 body presets"],
  },
  {
    icon: Brain,
    title: "AI Core",
    subtitle: "The brain behind it all",
    desc: "Conversational AI with screen vision, desktop automation, self-improvement engine, memory system, voice I/O, and safety guardrails. The pilot that drives every tool.",
    color: "#7c5cff",
    stats: ["Screen vision", "Self-improvement", "Memory system", "Voice I/O"],
  },
  {
    icon: Swords,
    title: "Beat Battles",
    subtitle: "AI vs AI music competition",
    desc: "Autonomous 5-round rap beat battle format. AI DJs generate tracks in real-time, AI judges score them, results deploy to the website automatically.",
    color: "#ff4757",
    stats: ["5 rounds", "AI judges", "Live scoring", "Auto deploy"],
  },
];

function CapabilityCard({ cap, index }: { cap: Capability; index: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  const Icon = cap.icon;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 40 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.5, delay: index * 0.1 }}
      className="group rounded-2xl border border-onyx-border/30 bg-onyx-panel/40 p-6 hover:border-onyx-border/60 transition-all hover:shadow-[0_0_30px_rgba(0,212,255,0.05)]"
    >
      <div className="flex items-start gap-4 mb-4">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: cap.color + "15", border: `1px solid ${cap.color}30` }}
        >
          <Icon size={18} style={{ color: cap.color }} />
        </div>
        <div>
          <h3 className="text-white font-bold font-mono text-base">{cap.title}</h3>
          <p className="text-onyx-text-dim text-xs font-mono">{cap.subtitle}</p>
        </div>
      </div>
      <p className="text-onyx-text-dim text-sm leading-relaxed mb-4">{cap.desc}</p>
      <div className="flex flex-wrap gap-2">
        {cap.stats.map((s) => (
          <span
            key={s}
            className="text-[10px] font-mono px-2 py-1 rounded-md border"
            style={{ color: cap.color, borderColor: cap.color + "30", background: cap.color + "08" }}
          >
            {s}
          </span>
        ))}
      </div>
    </motion.div>
  );
}

// ─── Face Gallery Preview ───────────────────────────────
function FacePreview({ style }: { style: FaceStyleDef }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const Renderer = style.renderer;
    const renderer = new Renderer();

    const emotions = ["neutral", "happy", "curious", "thinking"];
    let idx = 0;
    renderer.setEmotion(emotions[0]);
    const emoLoop = setInterval(() => {
      idx = (idx + 1) % emotions.length;
      renderer.setEmotion(emotions[idx]);
    }, 3000);

    let animId: number;
    let cssW = 0, cssH = 0;
    function loop() {
      renderer.update(cssW, cssH);
      renderer.draw(ctx!, cssW, cssH);
      animId = requestAnimationFrame(loop);
    }
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      cssW = rect.width;
      cssH = rect.height;
      canvas.width = cssW * dpr;
      canvas.height = cssH * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    loop();

    return () => {
      cancelAnimationFrame(animId);
      clearInterval(emoLoop);
      ro.disconnect();
    };
  }, [style]);

  return (
    <motion.div
      whileHover={{ scale: 1.03 }}
      className="rounded-xl border border-onyx-border/30 overflow-hidden hover:border-onyx-border/60 transition-all"
    >
      <div className="aspect-square w-full" style={{ background: style.bg }}>
        <canvas ref={canvasRef} className="w-full h-full" />
      </div>
      <div className="p-3 bg-onyx-panel/60">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full" style={{ background: style.accent }} />
          <span className="text-white font-mono text-xs font-bold">{style.name}</span>
        </div>
      </div>
    </motion.div>
  );
}

// ─── Show Cards (Output Gallery) ────────────────────────
const SHOWS = [
  {
    title: "Model \u00d7 Mindset",
    type: "Educational Series",
    desc: "5-episode series on the human mindset shift needed to work effectively with AI. Onyx teaches, Xyno learns.",
    color: "#00d4ff",
    episodes: 5,
    status: "In Production",
  },
  {
    title: "DonutTaco Tuesday",
    type: "Comedy Series",
    desc: "Onyx runs a donut-taco truck in the void. 10 characters, neon chaos, cosmic nonsense.",
    color: "#ff6b81",
    episodes: 1,
    status: "Pilot Complete",
  },
  {
    title: "Beat Battle: Vol. 1",
    type: "Music Competition",
    desc: "AI DJs go head-to-head in 5-round rap beat battles. Automated judging, live scoring.",
    color: "#ffd32a",
    episodes: 5,
    status: "Available",
  },
];

// ─── Main Page ──────────────────────────────────────────
export default function LandingPage() {
  const [visibleFaces, setVisibleFaces] = useState(8);

  return (
    <div className="min-h-screen bg-onyx-bg">
      <SiteNav />

      {/* ══════ HERO ══════ */}
      <section className="relative pt-24 pb-16 md:pt-32 md:pb-24 overflow-hidden">
        {/* Background grid */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(0,212,255,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.3) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full bg-onyx-accent/[0.04] blur-[120px]" />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col lg:flex-row items-center gap-12 lg:gap-16">
            {/* Text */}
            <motion.div
              className="flex-1 text-center lg:text-left"
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.7 }}
            >
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-onyx-accent/20 bg-onyx-accent/5 mb-6">
                <Sparkles size={14} className="text-onyx-accent" />
                <span className="text-xs font-mono text-onyx-accent">AI Creative Ecosystem</span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-white font-mono leading-tight mb-6">
                Meet <span className="text-onyx-accent">Onyx.</span>
                <br />
                <span className="text-onyx-text-dim text-2xl sm:text-3xl lg:text-4xl">
                  The pilot of the ecosystem.
                </span>
              </h1>

              <p className="text-onyx-text-dim text-base sm:text-lg max-w-xl mb-8 leading-relaxed">
                Onyx is an AI with a face, a voice, and hands that build.
                Music production, animated shows, 3D worlds, beat battles &mdash;
                one ecosystem, infinite creative output.
              </p>

              <div className="flex flex-wrap gap-3 justify-center lg:justify-start">
                <a
                  href="#ecosystem"
                  className="px-6 py-3 rounded-xl font-mono text-sm font-bold bg-onyx-accent text-onyx-bg hover:bg-onyx-accent/90 transition-colors flex items-center gap-2"
                >
                  Explore Ecosystem <ArrowRight size={16} />
                </a>
                <a
                  href="#gallery"
                  className="px-6 py-3 rounded-xl font-mono text-sm font-bold border border-onyx-border/40 text-onyx-text hover:border-onyx-accent/40 hover:text-onyx-accent transition-colors flex items-center gap-2"
                >
                  <Play size={14} /> Watch Demos
                </a>
              </div>
            </motion.div>

            {/* Face */}
            <motion.div
              className="flex-1 max-w-md w-full"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.8, delay: 0.2 }}
            >
              <div className="aspect-[10/9] w-full rounded-2xl overflow-hidden border-2 border-onyx-accent/20 shadow-[0_0_60px_rgba(0,212,255,0.1)]">
                <HeroFace />
              </div>
              <p className="text-center text-onyx-text-vdim text-xs font-mono mt-3">
                Move your mouse over Onyx &mdash; the face tracks your gaze
              </p>
            </motion.div>
          </div>
        </div>

        {/* Scroll hint */}
        <motion.div
          className="absolute bottom-4 left-1/2 -translate-x-1/2"
          animate={{ y: [0, 8, 0] }}
          transition={{ repeat: Infinity, duration: 2 }}
        >
          <ChevronDown size={20} className="text-onyx-text-vdim" />
        </motion.div>
      </section>

      {/* ══════ THE ECOSYSTEM ══════ */}
      <section id="ecosystem" className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <motion.div
            className="text-center mb-16"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl sm:text-4xl font-bold font-mono text-white mb-4">
              Onyx is the pilot.{" "}
              <span className="text-onyx-accent">The tools are its hands.</span>
            </h2>
            <p className="text-onyx-text-dim max-w-2xl mx-auto text-base leading-relaxed">
              Not a chatbot. Not an agent. An ecosystem. Every tool connects to the core.
              Every capability feeds the others. Create music for your shows.
              Build characters for your scenes. Produce episodes from a single prompt.
            </p>
          </motion.div>

          <EcosystemHub />
        </div>
      </section>

      {/* ══════ CAPABILITIES ══════ */}
      <section id="capabilities" className="py-20 px-4 sm:px-6 lg:px-8 bg-onyx-bg2">
        <div className="max-w-7xl mx-auto">
          <motion.div
            className="text-center mb-12"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl sm:text-4xl font-bold font-mono text-white mb-4">
              What the ecosystem <span className="text-onyx-accent">creates</span>
            </h2>
            <p className="text-onyx-text-dim max-w-xl mx-auto">
              Each tool is powerful alone. Together, they're an integrated creative platform.
            </p>
          </motion.div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {CAPABILITIES.map((cap, i) => (
              <CapabilityCard key={cap.title} cap={cap} index={i} />
            ))}
          </div>
        </div>
      </section>

      {/* ══════ OUTPUT GALLERY ══════ */}
      <section id="gallery" className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <motion.div
            className="text-center mb-12"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl sm:text-4xl font-bold font-mono text-white mb-4">
              Built with the ecosystem
            </h2>
            <p className="text-onyx-text-dim max-w-xl mx-auto">
              Shows, music, battles &mdash; all produced by Onyx and its tools.
            </p>
          </motion.div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {SHOWS.map((show) => (
              <motion.div
                key={show.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                whileHover={{ y: -4 }}
                className="rounded-2xl border border-onyx-border/30 bg-onyx-panel/40 overflow-hidden hover:border-onyx-border/60 transition-all"
              >
                {/* Color bar */}
                <div className="h-1" style={{ background: show.color }} />
                <div className="p-6">
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className="text-[10px] font-mono px-2 py-0.5 rounded-md border"
                      style={{ color: show.color, borderColor: show.color + "30" }}
                    >
                      {show.type}
                    </span>
                    <span className="text-[10px] font-mono text-onyx-text-vdim">
                      {show.episodes} episode{show.episodes > 1 ? "s" : ""}
                    </span>
                  </div>
                  <h3 className="text-white font-bold font-mono text-lg mb-2">{show.title}</h3>
                  <p className="text-onyx-text-dim text-sm leading-relaxed mb-4">{show.desc}</p>
                  <div className="flex items-center justify-between">
                    <span
                      className="text-xs font-mono px-2 py-1 rounded-md"
                      style={{ color: show.color, background: show.color + "10" }}
                    >
                      {show.status}
                    </span>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════ CHARACTERS & FACES ══════ */}
      <section id="characters" className="py-20 px-4 sm:px-6 lg:px-8 bg-onyx-bg2">
        <div className="max-w-7xl mx-auto">
          <motion.div
            className="text-center mb-12"
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl sm:text-4xl font-bold font-mono text-white mb-4">
              <span className="text-onyx-accent">{FACE_STYLES.length} faces.</span>{" "}
              Infinite characters.
            </h2>
            <p className="text-onyx-text-dim max-w-xl mx-auto">
              Every character in the ecosystem gets a unique animated face.
              Real-time emotions, gaze tracking, lip sync &mdash; powered by the AgentFace engine.
            </p>
          </motion.div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {FACE_STYLES.slice(0, visibleFaces).map((style) => (
              <FacePreview key={style.id} style={style} />
            ))}
          </div>

          {visibleFaces < FACE_STYLES.length && (
            <div className="text-center mt-8">
              <button
                onClick={() => setVisibleFaces((v) => Math.min(v + 8, FACE_STYLES.length))}
                className="px-6 py-3 rounded-xl font-mono text-sm font-bold border border-onyx-accent/30 text-onyx-accent hover:bg-onyx-accent/10 transition-colors"
              >
                Load more faces ({FACE_STYLES.length - visibleFaces} remaining)
              </button>
            </div>
          )}
        </div>
      </section>

      {/* ══════ CTA ══════ */}
      <section className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl sm:text-4xl font-bold font-mono text-white mb-4">
              Ready to create?
            </h2>
            <p className="text-onyx-text-dim text-base mb-8 max-w-lg mx-auto leading-relaxed">
              The ecosystem is open. The tools are ready.
              Start with Onyx and build from there.
            </p>
            <div className="flex flex-wrap gap-4 justify-center">
              <a
                href="https://github.com"
                target="_blank"
                rel="noopener"
                className="px-8 py-3.5 rounded-xl font-mono text-sm font-bold bg-onyx-accent text-onyx-bg hover:bg-onyx-accent/90 transition-colors"
              >
                Get Started
              </a>
              <a
                href="#ecosystem"
                className="px-8 py-3.5 rounded-xl font-mono text-sm font-bold border border-onyx-border/40 text-onyx-text-dim hover:text-white hover:border-onyx-accent/40 transition-colors"
              >
                Explore More
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ══════ FOOTER ══════ */}
      <footer className="border-t border-onyx-border/20 py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <span className="text-onyx-text-vdim text-xs font-mono">
            Onyx Ecosystem &mdash; AI-native creative platform
          </span>
          <div className="flex items-center gap-6 text-xs font-mono text-onyx-text-vdim">
            <span>217K lines</span>
            <span>31 face styles</span>
            <span>7 AI agents</span>
            <span>Local-first</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
