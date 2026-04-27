import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ShieldCheck, Cpu, Brain, ArrowRight, Github, Play, Check, X,
  Eye, Zap, Lock, Mic, Workflow, Clock, DollarSign, Quote,
} from "lucide-react";
import SiteNav from "../components/SiteNav";
import { FaceRenderer } from "../lib/faceRenderer";

/* ──────────────────────────────────────────────────────────
   Hero Face — animated Onyx with idle behavior + gaze tracking
   ────────────────────────────────────────────────────────── */
function HeroFace() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrapper = wrapperRef.current;
    if (!canvas || !wrapper) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const renderer = new FaceRenderer();

    const emotions = ["neutral", "thinking", "curious", "happy", "proud"];
    let idx = 0;
    renderer.setEmotion(emotions[0]);
    const emotionLoop = setInterval(() => {
      idx = (idx + 1) % emotions.length;
      renderer.setEmotion(emotions[idx]);
    }, 4500);

    const lines = [
      "I run on your laptop.",
      "I remember your business.",
      "I never send your data to the cloud.",
    ];
    let lineIdx = 0;
    const speakLoop = setInterval(() => {
      renderer.speak(lines[lineIdx % lines.length]);
      lineIdx++;
    }, 6500);
    setTimeout(() => renderer.speak(lines[0]), 800);

    let animId: number;
    let cssW = 0, cssH = 0;
    const frame = () => {
      renderer.update(cssW, cssH);
      renderer.draw(ctx!, cssW, cssH);
      animId = requestAnimationFrame(frame);
    };
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

    // Track gaze using the global pointer position so overlays (border, blur,
    // motion containers) never block the cursor. Gaze stays alive whenever the
    // pointer is over the entire face card, not just the canvas pixels.
    const onMove = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      if (rect.width === 0) return;
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const x = ((e.clientX - cx) / (rect.width / 2));   // -1..1 across canvas
      const y = ((e.clientY - cy) / (rect.height / 2)) * 0.5;
      renderer.setGaze(
        Math.max(-1, Math.min(1, x * 0.85)),
        Math.max(-0.5, Math.min(0.5, y * 0.6)),
      );
    };
    const onLeave = () => renderer.clearGaze();
    window.addEventListener("pointermove", onMove);
    wrapper.addEventListener("pointerleave", onLeave);

    return () => {
      cancelAnimationFrame(animId);
      clearInterval(emotionLoop);
      clearInterval(speakLoop);
      ro.disconnect();
      window.removeEventListener("pointermove", onMove);
      wrapper.removeEventListener("pointerleave", onLeave);
    };
  }, []);

  return (
    <div ref={wrapperRef} className="relative w-full h-full">
      <canvas
        ref={canvasRef}
        className="w-full h-full block rounded-2xl"
        style={{
          background: "radial-gradient(ellipse at 50% 30%, #0a1628 0%, #050810 70%)",
          pointerEvents: "auto",
          cursor: "default",
        }}
      />
      <p className="absolute bottom-3 inset-x-0 text-center text-onyx-text-vdim text-[10px] font-mono pointer-events-none select-none">
        Move your cursor — Onyx tracks
      </p>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────
   Hero Section
   ────────────────────────────────────────────────────────── */
function Hero() {
  return (
    <section className="relative pt-28 sm:pt-32 pb-16 px-4 sm:px-6 lg:px-8 overflow-hidden">
      {/* glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-20 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-onyx-accent/10 blur-3xl" />
      </div>

      <div className="relative max-w-7xl mx-auto grid lg:grid-cols-[1.1fr_1fr] gap-12 items-center">
        {/* Copy */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <div className="inline-flex items-center gap-2 px-3 py-1.5 mb-6 rounded-full border border-onyx-accent/30 bg-onyx-accent/5">
            <ShieldCheck size={14} className="text-onyx-accent" />
            <span className="text-xs font-mono text-onyx-accent">100% local. No cloud APIs.</span>
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold font-mono text-white leading-[1.05] mb-5">
            The AI ops layer for{" "}
            <span className="text-onyx-accent">solo entrepreneurs.</span>
          </h1>

          <p className="text-lg sm:text-xl text-onyx-text-dim leading-relaxed mb-3 max-w-xl">
            Onyx sees your screen, remembers your business, and acts on your
            behalf — entirely on your laptop.
          </p>
          <p className="text-base text-onyx-text-dim/80 leading-relaxed mb-8 max-w-xl">
            Replace your $200/month stack of cloud AI tools with one tool that
            runs locally and never leaks your client data.
          </p>

          <div className="flex flex-wrap gap-3">
            <a
              href="#demo"
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl font-mono text-sm font-bold bg-onyx-accent text-onyx-bg hover:bg-onyx-accent/90 transition-colors"
            >
              <Play size={16} fill="currentColor" /> Watch the 90-second demo
            </a>
            <a
              href="#install"
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl font-mono text-sm font-bold border border-onyx-border/40 text-white hover:bg-onyx-panel transition-colors"
            >
              Install (60s) <ArrowRight size={16} />
            </a>
          </div>

          <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-xs font-mono text-onyx-text-dim">
            <div className="flex items-center gap-1.5"><Cpu size={14} className="text-onyx-accent" /> Powered by local Ollama</div>
            <div className="flex items-center gap-1.5"><Lock size={14} className="text-onyx-accent" /> Zero outbound calls</div>
            <div className="flex items-center gap-1.5"><DollarSign size={14} className="text-onyx-accent" /> $149 once · no subscriptions</div>
          </div>
        </motion.div>

        {/* Face */}
        <motion.div
          className="relative aspect-square w-full max-w-[500px] mx-auto"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, delay: 0.1 }}
        >
          <div className="absolute inset-0 rounded-3xl border border-onyx-border/30 bg-onyx-panel/30 backdrop-blur-sm overflow-hidden">
            <HeroFace />
          </div>
        </motion.div>
      </div>
    </section>
  );
}

/* ──────────────────────────────────────────────────────────
   Problem — what the operator deals with today
   ────────────────────────────────────────────────────────── */
const PAIN_TOOLS = [
  { name: "ChatGPT Plus",    cost: 20, role: "drafts + general AI" },
  { name: "Perplexity Pro",  cost: 20, role: "research" },
  { name: "Otter.ai",        cost: 30, role: "call transcripts" },
  { name: "Calendly AI",     cost: 15, role: "scheduling" },
  { name: "Notion AI",       cost: 10, role: "notes + docs" },
];
const TOTAL_MONTHLY = PAIN_TOOLS.reduce((s, t) => s + t.cost, 0);

function Problem() {
  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8 border-t border-onyx-border/20">
      <div className="max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-12"
        >
          <span className="text-xs font-mono text-onyx-warm uppercase tracking-wider">The Problem</span>
          <h2 className="text-3xl sm:text-4xl font-bold font-mono text-white mt-3 mb-4">
            You're paying ${TOTAL_MONTHLY}/month for tools<br className="hidden sm:block"/> that don't talk to each other.
          </h2>
          <p className="text-onyx-text-dim max-w-2xl mx-auto leading-relaxed">
            Every solo founder ends up with a Frankenstein stack of cloud AI subscriptions.
            Each one has amnesia. Each one wants your data. None of them know your business.
          </p>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
          {PAIN_TOOLS.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05 }}
              className="rounded-xl border border-onyx-border/30 bg-onyx-panel/50 p-4"
            >
              <div className="text-xs font-mono text-onyx-warm">${t.cost}/mo</div>
              <div className="text-white font-mono text-sm font-bold mt-1">{t.name}</div>
              <div className="text-onyx-text-dim text-xs mt-1">{t.role}</div>
            </motion.div>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-center gap-6 mt-8 p-6 rounded-2xl border border-onyx-warm/30 bg-onyx-warm/5">
          <div className="text-center">
            <div className="text-3xl font-bold font-mono text-onyx-warm">${TOTAL_MONTHLY * 12}</div>
            <div className="text-xs font-mono text-onyx-text-dim mt-1">per year</div>
          </div>
          <div className="hidden sm:block w-px h-12 bg-onyx-border/40" />
          <div className="text-center">
            <div className="text-3xl font-bold font-mono text-onyx-warm">5</div>
            <div className="text-xs font-mono text-onyx-text-dim mt-1">vendors holding your data</div>
          </div>
          <div className="hidden sm:block w-px h-12 bg-onyx-border/40" />
          <div className="text-center">
            <div className="text-3xl font-bold font-mono text-onyx-warm">0</div>
            <div className="text-xs font-mono text-onyx-text-dim mt-1">that remember your business</div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ──────────────────────────────────────────────────────────
   Solution — what Onyx does, the 4 pillars
   ────────────────────────────────────────────────────────── */
const PILLARS = [
  {
    icon: Eye,
    title: "Sees your screen",
    body: "Reads any Windows app via UI Automation + vision fallback. No copy-pasting between tabs.",
  },
  {
    icon: Brain,
    title: "Remembers your business",
    body: "Local RAG knowledge engine. Every conversation, doc, and lead is recallable next time.",
  },
  {
    icon: Workflow,
    title: "Acts on your behalf",
    body: "Drafts, types, clicks, navigates apps via voice or text. Workflows you'd otherwise do yourself.",
  },
  {
    icon: ShieldCheck,
    title: "Stays on your laptop",
    body: "Powered by local Ollama models. Zero outbound API calls. Your client data never leaves the machine.",
  },
];

function Solution() {
  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8 border-t border-onyx-border/20">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-14"
        >
          <span className="text-xs font-mono text-onyx-accent uppercase tracking-wider">Meet Onyx</span>
          <h2 className="text-3xl sm:text-4xl font-bold font-mono text-white mt-3 mb-4">
            One tool. On your laptop. <span className="text-onyx-accent">Built for you.</span>
          </h2>
        </motion.div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {PILLARS.map((p, i) => (
            <motion.div
              key={p.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.07 }}
              className="rounded-2xl border border-onyx-border/30 bg-onyx-panel/40 p-6 hover:border-onyx-accent/40 hover:bg-onyx-panel/70 transition-all"
            >
              <div className="w-10 h-10 rounded-lg bg-onyx-accent/10 border border-onyx-accent/30 flex items-center justify-center mb-4">
                <p.icon size={18} className="text-onyx-accent" />
              </div>
              <h3 className="text-white font-mono text-base font-bold mb-2">{p.title}</h3>
              <p className="text-onyx-text-dim text-sm leading-relaxed">{p.body}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ──────────────────────────────────────────────────────────
   Demo — Loom embed placeholder
   ────────────────────────────────────────────────────────── */
function Demo() {
  return (
    <section id="demo" className="py-20 px-4 sm:px-6 lg:px-8 border-t border-onyx-border/20">
      <div className="max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-10"
        >
          <span className="text-xs font-mono text-onyx-accent uppercase tracking-wider">90-second demo</span>
          <h2 className="text-3xl sm:text-4xl font-bold font-mono text-white mt-3 mb-4">
            Watch Onyx do a full lead-followup workflow.
          </h2>
          <p className="text-onyx-text-dim max-w-2xl mx-auto leading-relaxed">
            New email arrives. Onyx reads it, drafts the response, researches the company, books the call.
            <span className="text-onyx-accent"> Zero data leaves your laptop.</span>
          </p>
        </motion.div>

        <div
          className="relative aspect-video rounded-2xl overflow-hidden border border-onyx-border/40 bg-onyx-panel/40"
          style={{ boxShadow: "0 0 80px rgba(0, 212, 255, 0.08)" }}
        >
          {/* TODO: replace with actual Loom embed once recorded:
              <iframe src="https://www.loom.com/embed/YOUR_LOOM_ID" frameBorder="0" allow="autoplay; fullscreen" className="absolute inset-0 w-full h-full" />
          */}
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-[radial-gradient(ellipse_at_center,#0a1628_0%,#050810_80%)]">
            <div className="w-16 h-16 rounded-full bg-onyx-accent/15 border border-onyx-accent/40 flex items-center justify-center">
              <Play size={28} className="text-onyx-accent ml-1" fill="currentColor" />
            </div>
            <div className="text-onyx-text-dim font-mono text-sm">Loom walkthrough · coming May 2026</div>
            <div className="text-onyx-text-vdim font-mono text-xs">Recording the Maya workflow this week</div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ──────────────────────────────────────────────────────────
   Before / After — the Maya workflow
   ────────────────────────────────────────────────────────── */
const BEFORE_STEPS = [
  "Copy lead email into ChatGPT, ask for draft",
  "Open Perplexity, search the company",
  "Paste research back into ChatGPT to weave context",
  "Copy final draft, paste into Gmail, edit, send",
  "Switch to Calendly, manually flag a priority slot",
];

const AFTER_STEPS = [
  "Maya: \"Hey Onyx, draft a followup, research them, prep me a brief.\"",
  "Onyx reads the Gmail thread on her screen",
  "Pulls company name, runs local research, drafts response",
  "Opens her calendar, suggests a slot",
  "Maya skims, edits one sentence, sends",
];

function BeforeAfter() {
  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8 border-t border-onyx-border/20">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-12"
        >
          <span className="text-xs font-mono text-onyx-accent uppercase tracking-wider">Before · After</span>
          <h2 className="text-3xl sm:text-4xl font-bold font-mono text-white mt-3 mb-4">
            Same workflow.<br className="sm:hidden"/> 8× faster. Zero data leaks.
          </h2>
          <p className="text-onyx-text-dim max-w-2xl mx-auto leading-relaxed">
            Maya runs a 2-person consultancy. A new lead arrives at 9:14am.
            By 9:30am she needs a personalized followup, a quick background check, and a booked call.
          </p>
        </motion.div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Before */}
          <div className="rounded-2xl border border-onyx-warm/30 bg-onyx-warm/5 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <X size={20} className="text-onyx-warm" />
                <h3 className="text-white font-mono font-bold">Before — the cloud stack</h3>
              </div>
              <div className="text-onyx-warm font-mono text-sm">8-12 min</div>
            </div>
            <ol className="space-y-3">
              {BEFORE_STEPS.map((step, i) => (
                <li key={i} className="flex gap-3 text-sm text-onyx-text-dim">
                  <span className="font-mono text-onyx-warm w-5 flex-shrink-0">{i + 1}.</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
            <div className="mt-5 pt-4 border-t border-onyx-warm/20 text-xs font-mono text-onyx-text-dim">
              4 cloud tools touched · client email shared with 4 vendors
            </div>
          </div>

          {/* After */}
          <div className="rounded-2xl border border-onyx-accent2/30 bg-onyx-accent2/5 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Check size={20} className="text-onyx-accent2" />
                <h3 className="text-white font-mono font-bold">After — Onyx</h3>
              </div>
              <div className="text-onyx-accent2 font-mono text-sm">~90 sec</div>
            </div>
            <ol className="space-y-3">
              {AFTER_STEPS.map((step, i) => (
                <li key={i} className="flex gap-3 text-sm text-onyx-text-dim">
                  <span className="font-mono text-onyx-accent2 w-5 flex-shrink-0">{i + 1}.</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
            <div className="mt-5 pt-4 border-t border-onyx-accent2/20 text-xs font-mono text-onyx-text-dim">
              1 tool · 0 vendors · this lead is now remembered next time
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ──────────────────────────────────────────────────────────
   Privacy — the proof
   ────────────────────────────────────────────────────────── */
function Privacy() {
  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8 border-t border-onyx-border/20 bg-onyx-bg2/30">
      <div className="max-w-5xl mx-auto grid md:grid-cols-2 gap-10 items-center">
        <div>
          <span className="text-xs font-mono text-onyx-accent uppercase tracking-wider">Privacy by Architecture</span>
          <h2 className="text-3xl sm:text-4xl font-bold font-mono text-white mt-3 mb-5">
            Your data never leaves your laptop.<br />
            <span className="text-onyx-accent">We can prove it.</span>
          </h2>
          <p className="text-onyx-text-dim leading-relaxed mb-4">
            Onyx runs entirely against a local Ollama backend. No cloud APIs.
            No outbound HTTP calls during normal operation. No telemetry.
          </p>
          <p className="text-onyx-text-dim leading-relaxed mb-6">
            Run Wireshark or <code className="font-mono text-onyx-accent text-sm bg-onyx-panel px-1.5 py-0.5 rounded">pktmon</code> alongside the demo.
            Filter by Onyx's process ID. The packet log stays empty.
          </p>
          <div className="flex flex-wrap gap-3">
            {[
              { icon: Lock, label: "No API keys required" },
              { icon: Cpu, label: "Local Ollama backend" },
              { icon: ShieldCheck, label: "Zero telemetry" },
            ].map((b) => (
              <div key={b.label} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-onyx-accent/20 bg-onyx-accent/5">
                <b.icon size={14} className="text-onyx-accent" />
                <span className="text-xs font-mono text-onyx-text">{b.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Mock packet log */}
        <div className="rounded-2xl border border-onyx-border/40 bg-onyx-bg/80 overflow-hidden font-mono text-xs">
          <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-onyx-border/40 bg-onyx-panel/50">
            <span className="w-2.5 h-2.5 rounded-full bg-onyx-warm" />
            <span className="w-2.5 h-2.5 rounded-full bg-onyx-text-vdim" />
            <span className="w-2.5 h-2.5 rounded-full bg-onyx-accent2" />
            <span className="ml-3 text-onyx-text-dim">pktmon ~ filter: process=onyx.exe</span>
          </div>
          <div className="p-4 space-y-1.5 text-onyx-text-dim leading-relaxed">
            <div><span className="text-onyx-text-vdim">[09:14:02]</span> Listening on PID 8432 (onyx.exe)...</div>
            <div><span className="text-onyx-text-vdim">[09:14:12]</span> 127.0.0.1:11434 → POST /api/chat <span className="text-onyx-accent2">[Ollama, local]</span></div>
            <div><span className="text-onyx-text-vdim">[09:14:13]</span> 127.0.0.1:11434 → POST /api/embeddings <span className="text-onyx-accent2">[local]</span></div>
            <div><span className="text-onyx-text-vdim">[09:14:24]</span> 127.0.0.1:11434 → POST /api/chat <span className="text-onyx-accent2">[local]</span></div>
            <div><span className="text-onyx-text-vdim">[09:14:31]</span> <span className="text-onyx-accent2">workflow complete</span></div>
            <div className="pt-3 mt-3 border-t border-onyx-border/40">
              <span className="text-onyx-text-vdim">Outbound (non-localhost):</span>{" "}
              <span className="text-onyx-accent2 font-bold">0 packets</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ──────────────────────────────────────────────────────────
   Pricing
   ────────────────────────────────────────────────────────── */
const TIERS = [
  {
    name: "Onyx Core",
    price: "$149",
    sub: "one-time",
    pitch: "Face + Chat + Memory + Desktop Automation",
    features: ["Conversational AI with memory", "Screen reading + UI automation", "Animated face GUI", "Local RAG knowledge engine", "14-day full-feature trial"],
    highlight: false,
  },
  {
    name: "Starter Pack",
    price: "$199",
    sub: "one-time",
    pitch: "Core + Voice + Agent — most popular",
    features: ["Everything in Core", "Voice I/O (push-to-talk + hands-free)", "Discord remote control", "REST API for integrations", "Self-improvement engine"],
    highlight: true,
  },
  {
    name: "Founder's Edition",
    price: "$499",
    sub: "lifetime",
    pitch: "Everything, forever, with priority access",
    features: ["Every feature, forever", "Lifetime updates", "Priority support", "Founder badge", "Direct line to the builder"],
    highlight: false,
  },
];

function Pricing() {
  return (
    <section id="pricing" className="py-20 px-4 sm:px-6 lg:px-8 border-t border-onyx-border/20">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-12"
        >
          <span className="text-xs font-mono text-onyx-accent uppercase tracking-wider">Pricing</span>
          <h2 className="text-3xl sm:text-4xl font-bold font-mono text-white mt-3 mb-4">
            One-time pricing. <span className="text-onyx-accent">No subscriptions. Ever.</span>
          </h2>
          <p className="text-onyx-text-dim max-w-2xl mx-auto leading-relaxed">
            Pays itself back in 7 weeks vs the cloud stack. After that, every month is profit.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-5">
          {TIERS.map((t) => (
            <div
              key={t.name}
              className={`rounded-2xl border p-6 flex flex-col ${
                t.highlight
                  ? "border-onyx-accent/50 bg-onyx-accent/5 lg:scale-[1.03]"
                  : "border-onyx-border/30 bg-onyx-panel/40"
              }`}
            >
              {t.highlight && (
                <div className="self-start text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-onyx-accent text-onyx-bg mb-3">
                  Most popular
                </div>
              )}
              <h3 className="text-white font-mono font-bold text-lg">{t.name}</h3>
              <div className="flex items-baseline gap-1.5 mt-2 mb-1">
                <span className="text-3xl font-bold font-mono text-white">{t.price}</span>
                <span className="text-xs font-mono text-onyx-text-dim">{t.sub}</span>
              </div>
              <p className="text-onyx-text-dim text-sm mb-5">{t.pitch}</p>
              <ul className="space-y-2 mb-6 flex-1">
                {t.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-onyx-text-dim">
                    <Check size={15} className="text-onyx-accent2 flex-shrink-0 mt-0.5" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <a
                href="#install"
                className={`mt-auto block text-center px-4 py-2.5 rounded-xl font-mono text-sm font-bold transition-colors ${
                  t.highlight
                    ? "bg-onyx-accent text-onyx-bg hover:bg-onyx-accent/90"
                    : "border border-onyx-border/40 text-white hover:bg-onyx-panel"
                }`}
              >
                Start free trial
              </a>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ──────────────────────────────────────────────────────────
   Install / Try it
   ────────────────────────────────────────────────────────── */
function Install() {
  const [copied, setCopied] = useState(false);
  const command = "git clone https://github.com/20TwentyVizion/OnyxKraken-Public\ncd OnyxKraken-Public\npip install -r requirements.txt\npython main.py";
  const copy = () => {
    navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section id="install" className="py-20 px-4 sm:px-6 lg:px-8 border-t border-onyx-border/20 bg-onyx-bg2/30">
      <div className="max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-10"
        >
          <span className="text-xs font-mono text-onyx-accent uppercase tracking-wider">Try it</span>
          <h2 className="text-3xl sm:text-4xl font-bold font-mono text-white mt-3 mb-4">
            60 seconds from clone to running.
          </h2>
          <p className="text-onyx-text-dim max-w-2xl mx-auto leading-relaxed">
            Open source for evaluation. Bring your own Ollama. The onboarding wizard handles the rest.
          </p>
        </motion.div>

        <div className="rounded-2xl border border-onyx-border/40 bg-onyx-bg overflow-hidden font-mono">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-onyx-border/40 bg-onyx-panel/50">
            <span className="text-xs text-onyx-text-dim">terminal</span>
            <button
              onClick={copy}
              className="text-xs text-onyx-accent hover:text-white transition-colors"
            >
              {copied ? "copied!" : "copy"}
            </button>
          </div>
          <pre className="p-5 text-sm text-onyx-text leading-loose overflow-x-auto">
            <span className="text-onyx-text-vdim">$ </span>git clone https://github.com/20TwentyVizion/OnyxKraken-Public{"\n"}
            <span className="text-onyx-text-vdim">$ </span>cd OnyxKraken-Public{"\n"}
            <span className="text-onyx-text-vdim">$ </span>pip install -r requirements.txt{"\n"}
            <span className="text-onyx-text-vdim">$ </span>python main.py
          </pre>
        </div>

        <div className="mt-6 grid sm:grid-cols-3 gap-3">
          <a
            href="https://github.com/20TwentyVizion/OnyxKraken-Public"
            target="_blank" rel="noopener"
            className="flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-onyx-border/40 text-white hover:bg-onyx-panel transition-colors font-mono text-sm"
          >
            <Github size={16} /> View source
          </a>
          <Link
            to="/face"
            className="flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-onyx-accent/30 bg-onyx-accent/5 text-onyx-accent hover:bg-onyx-accent/10 transition-colors font-mono text-sm"
          >
            <Mic size={16} /> Try the live face
          </Link>
          <Link
            to="/ecosystem"
            className="flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-onyx-border/40 text-white hover:bg-onyx-panel transition-colors font-mono text-sm"
          >
            <Zap size={16} /> Explore ecosystem
          </Link>
        </div>

        <div className="mt-6 text-center text-xs font-mono text-onyx-text-vdim">
          Requires Windows 10/11 · Python 3.11+ · 8GB RAM · <a className="underline hover:text-onyx-accent" href="https://ollama.com" target="_blank" rel="noopener">Ollama</a>
        </div>
      </div>
    </section>
  );
}

/* ──────────────────────────────────────────────────────────
   Scale / closing argument
   ────────────────────────────────────────────────────────── */
function Scale() {
  return (
    <section className="py-20 px-4 sm:px-6 lg:px-8 border-t border-onyx-border/20">
      <div className="max-w-4xl mx-auto text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <Quote className="mx-auto text-onyx-accent/40 mb-6" size={36} />
          <p className="text-2xl sm:text-3xl font-mono text-white leading-relaxed mb-6">
            Cursor won the developer market.<br />
            Glean won the enterprise market.<br />
            <span className="text-onyx-accent">Onyx is the operator-first AI ops layer for the 400 million small businesses everyone else forgot.</span>
          </p>
          <div className="grid sm:grid-cols-3 gap-4 mt-12 max-w-2xl mx-auto">
            <div className="p-4 rounded-xl border border-onyx-border/30 bg-onyx-panel/30">
              <div className="text-2xl font-bold font-mono text-onyx-accent">33M</div>
              <div className="text-xs font-mono text-onyx-text-dim mt-1">US small businesses</div>
            </div>
            <div className="p-4 rounded-xl border border-onyx-border/30 bg-onyx-panel/30">
              <div className="text-2xl font-bold font-mono text-onyx-accent">400M</div>
              <div className="text-xs font-mono text-onyx-text-dim mt-1">globally</div>
            </div>
            <div className="p-4 rounded-xl border border-onyx-border/30 bg-onyx-panel/30">
              <div className="text-2xl font-bold font-mono text-onyx-accent">1</div>
              <div className="text-xs font-mono text-onyx-text-dim mt-1">tool that fits them</div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

/* ──────────────────────────────────────────────────────────
   Footer
   ────────────────────────────────────────────────────────── */
function Footer() {
  return (
    <footer className="border-t border-onyx-border/20 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-onyx-accent/15 flex items-center justify-center border border-onyx-accent/30">
            <span className="text-onyx-accent font-bold text-xs">O</span>
          </div>
          <span className="font-mono text-sm text-white">OnyxKraken</span>
          <span className="font-mono text-xs text-onyx-text-vdim">· built by <a href="https://markvizion.com" className="hover:text-onyx-accent">markvizion.com</a></span>
        </div>
        <div className="flex items-center gap-6 text-xs font-mono text-onyx-text-vdim">
          <a href="#demo" className="hover:text-white transition-colors">Demo</a>
          <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
          <a href="#install" className="hover:text-white transition-colors">Install</a>
          <Link to="/ecosystem" className="hover:text-white transition-colors">Ecosystem</Link>
          <a href="https://github.com/20TwentyVizion/OnyxKraken-Public" target="_blank" rel="noopener" className="hover:text-white transition-colors">GitHub</a>
        </div>
      </div>
    </footer>
  );
}

/* ──────────────────────────────────────────────────────────
   Page composition
   ────────────────────────────────────────────────────────── */
export default function LandingPage() {
  return (
    <div className="min-h-screen bg-onyx-bg text-onyx-text">
      <SiteNav />
      <Hero />
      <Problem />
      <Solution />
      <Demo />
      <BeforeAfter />
      <Privacy />
      <Pricing />
      <Install />
      <Scale />
      <Footer />
    </div>
  );
}
