/**
 * driveClient — Connect a FaceRenderer (and optional body renderer) to the
 * OnyxKraken drive bus over WebSocket.
 *
 * Subscribes to /drive/stream and applies emotion/pose/body_anim/speak
 * events to the local renderer in real time. Reconnects on disconnect.
 *
 * Usage:
 *   const ctl = connectDrive(rendererRef.current, { url: "ws://localhost:8420/drive/stream" });
 *   // ...later
 *   ctl.close();
 */

import type { FaceRenderer } from "./faceRenderer";

export interface DriveEvent {
  kind: "emotion" | "pose" | "body_anim" | "speak" | "stop" | "hello" | "episode_beat";
  character?: string;
  payload: Record<string, unknown>;
  ts: number;
  source?: string;
}

export interface DriveOptions {
  url?: string;
  character?: string;            // only react to this character (default: any)
  reconnectMs?: number;
  onEvent?: (e: DriveEvent) => void;
  onPose?: (pose: string, transitionMs: number) => void;
  onBodyAnim?: (anim: string, loop: boolean) => void;
}

const DEFAULT_URL = (() => {
  if (typeof window === "undefined") return "ws://localhost:8420/drive/stream";
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const host = (import.meta as { env?: Record<string, string> })?.env?.VITE_ONYX_API_HOST
    ?? "localhost:8420";
  return `${proto}://${host}/drive/stream`;
})();

export interface DriveController {
  close: () => void;
  send: (kind: string, payload: Record<string, unknown>) => void;
  isOpen: () => boolean;
}

export const connectDrive = (
  renderer: FaceRenderer | null,
  opts: DriveOptions = {},
): DriveController => {
  const url = opts.url ?? DEFAULT_URL;
  const reconnectMs = opts.reconnectMs ?? 2000;
  let ws: WebSocket | null = null;
  let closed = false;
  let retryTimer: number | null = null;

  const apply = (event: DriveEvent) => {
    if (opts.character && event.character && event.character !== opts.character) {
      return;
    }
    opts.onEvent?.(event);
    if (!renderer) return;

    switch (event.kind) {
      case "emotion": {
        const mix = event.payload.mix as Record<string, number> | undefined;
        if (mix && typeof mix === "object") {
          renderer.setEmotionMix?.(mix);
        } else {
          const emo = String(event.payload.emotion ?? "neutral");
          renderer.setEmotion?.(emo);
        }
        break;
      }
      case "speak": {
        const text = String(event.payload.text ?? "");
        if (text) renderer.speak?.(text);
        break;
      }
      case "pose": {
        opts.onPose?.(
          String(event.payload.pose ?? "neutral"),
          Number(event.payload.transition_ms ?? 300),
        );
        break;
      }
      case "body_anim": {
        opts.onBodyAnim?.(
          String(event.payload.animation ?? ""),
          Boolean(event.payload.loop ?? false),
        );
        break;
      }
      case "stop": {
        renderer.setEmotion?.("neutral");
        break;
      }
      default:
        break;
    }
  };

  const connect = () => {
    if (closed) return;
    try {
      ws = new WebSocket(url);
    } catch {
      retryTimer = window.setTimeout(connect, reconnectMs);
      return;
    }
    ws.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data) as DriveEvent;
        apply(event);
      } catch {
        /* ignore malformed */
      }
    };
    ws.onclose = () => {
      if (!closed) retryTimer = window.setTimeout(connect, reconnectMs);
    };
    ws.onerror = () => {
      ws?.close();
    };
  };

  connect();

  return {
    close: () => {
      closed = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      ws?.close();
    },
    send: (kind, payload) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ kind, payload }));
      }
    },
    isOpen: () => ws?.readyState === WebSocket.OPEN,
  };
};
