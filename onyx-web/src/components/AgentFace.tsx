/**
 * AgentFace — Reusable React component that renders an animated face.
 *
 * Usage:
 *   import AgentFace from "./components/AgentFace";
 *   import { FaceRenderer } from "./lib/faceRenderer";
 *
 *   const ref = useRef<FaceRenderer>(null);
 *   <AgentFace rendererRef={ref} />
 *
 *   // Control:
 *   ref.current?.speak("Hello!");
 *   ref.current?.setEmotion("happy");
 */
import { useRef, useEffect, useCallback, type MutableRefObject } from "react";
import { FaceRenderer } from "../lib/faceRenderer";
import { connectDrive, type DriveOptions } from "../lib/driveClient";

interface AgentFaceProps {
  rendererRef?: MutableRefObject<FaceRenderer | null>;
  RendererClass?: typeof FaceRenderer;
  className?: string;
  bg?: string;
  /** Connect to /drive/stream for live face/body events. */
  drive?: boolean | DriveOptions;
}

export default function AgentFace({
  rendererRef,
  RendererClass = FaceRenderer,
  className = "",
  bg = "#050810",
  drive,
}: AgentFaceProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const internalRef = useRef<FaceRenderer | null>(null);
  const animRef = useRef<number>(0);

  useEffect(() => {
    const renderer = new RendererClass();
    internalRef.current = renderer;
    if (rendererRef) rendererRef.current = renderer;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    let cssW = 0, cssH = 0;

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas!.getBoundingClientRect();
      cssW = rect.width;
      cssH = rect.height;
      canvas!.width = cssW * dpr;
      canvas!.height = cssH * dpr;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    function loop() {
      renderer.update(cssW, cssH);
      renderer.draw(ctx!, cssW, cssH);
      animRef.current = requestAnimationFrame(loop);
    }
    animRef.current = requestAnimationFrame(loop);

    const driveOpts: DriveOptions | null = drive === true ? {} : (drive || null);
    const driveCtl = driveOpts ? connectDrive(renderer, driveOpts) : null;

    return () => {
      ro.disconnect();
      if (animRef.current) cancelAnimationFrame(animRef.current);
      driveCtl?.close();
    };
  }, [rendererRef, RendererClass, drive]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const r = internalRef.current;
    if (!r || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    const y = ((e.clientY - rect.top) / rect.height) - 0.5;
    r.setGaze(x * 0.8, y * 0.6);
  }, []);

  const handleMouseLeave = useCallback(() => {
    if (internalRef.current) internalRef.current.clearGaze();
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className={`w-full h-full block ${className}`}
      style={{ background: bg }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    />
  );
}
