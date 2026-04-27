import { useRef, useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FaceRenderer } from "../lib/faceRenderer";

export default function FloatingOnyx() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<FaceRenderer | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const renderer = new FaceRenderer();
    rendererRef.current = renderer;
    renderer.setEmotion("curious");

    const emotions = ["curious", "happy", "listening", "amused", "thinking"];
    let idx = 0;
    const emotionLoop = setInterval(() => {
      idx = (idx + 1) % emotions.length;
      renderer.setEmotion(emotions[idx]);
    }, 5000);

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
      clearInterval(emotionLoop);
      ro.disconnect();
    };
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const r = rendererRef.current;
    const canvas = canvasRef.current;
    if (!r || !canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const y = ((e.clientY - rect.top) / rect.height) - 0.5;
    r.setGaze(x * 0.8, y * 0.6);
  }, []);

  return (
    <motion.div
      className="fixed bottom-5 right-5 z-[100] cursor-pointer"
      initial={{ opacity: 0, scale: 0 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 1.5, type: "spring", stiffness: 200 }}
    >
      <div
        onClick={() => setExpanded(!expanded)}
        onMouseMove={handleMouseMove}
        className={`rounded-full overflow-hidden border-2 border-onyx-accent/40 shadow-[0_0_30px_rgba(0,212,255,0.15)] transition-all duration-300 ${
          expanded ? "w-28 h-28" : "w-14 h-14"
        }`}
        style={{ background: "#050810" }}
      >
        <canvas ref={canvasRef} className="w-full h-full" />
      </div>
    </motion.div>
  );
}
