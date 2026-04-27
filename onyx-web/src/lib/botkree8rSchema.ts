/**
 * BotKree8r Character Definition Schema.
 * This is the portable JSON format that bridges web ↔ desktop.
 */

import type { BodyStyle, BodyType, BodyBuild, ThemeColors } from "./robotBody";

export interface BotKree8rCharacter {
  version: "1.0";
  name: string;
  display_name: string;
  description: string;

  body: {
    type: BodyType;     // visual body renderer (mech, sleek, cyber, etc.)
    build: BodyBuild;   // proportional modifier (standard, slim, broad, etc.)
    colors: ThemeColors;
  };

  face: {
    style: string;       // one of 31 AgentFace style IDs
    accent: string;      // face accent color
    bg: string;          // face background color
  };

  traits: {
    eye_style: EyeStyle;
    face_shape: FaceShape;
    accessory: Accessory;
    personality: Personality;
    voice_pitch: number;       // 0.8 – 1.2
    default_pose: DefaultPose;
    idle_animation: IdleAnimation;
  };

  metadata: {
    created: string;     // ISO 8601
    creator: string;
  };
}

// ── Enum-like unions ─────────────────────────────────────────
export type EyeStyle = "default" | "round" | "angular" | "narrow" | "wide";
export type FaceShape = "default" | "circle" | "hexagon" | "diamond" | "shield";
export type Accessory = "none" | "antenna" | "headphones" | "visor" | "halo" | "horns";
export type Personality = "casual" | "professional" | "creative" | "technical";
export type DefaultPose = "neutral" | "confident" | "excited" | "thinking" | "relaxed";
export type IdleAnimation = "breathing" | "swaying" | "nodding";

export const EYE_STYLES: EyeStyle[] = ["default", "round", "angular", "narrow", "wide"];
export const FACE_SHAPES: FaceShape[] = ["default", "circle", "hexagon", "diamond", "shield"];
export const ACCESSORIES: Accessory[] = ["none", "antenna", "headphones", "visor", "halo", "horns"];
export const PERSONALITIES: Personality[] = ["casual", "professional", "creative", "technical"];
export const DEFAULT_POSES: DefaultPose[] = ["neutral", "confident", "excited", "thinking", "relaxed"];
export const IDLE_ANIMATIONS: IdleAnimation[] = ["breathing", "swaying", "nodding"];

export const BUILD_OPTIONS: { id: BodyBuild; label: string; desc: string }[] = [
  { id: "standard", label: "Standard", desc: "Balanced proportions" },
  { id: "slim",     label: "Slim",     desc: "Tall and lean" },
  { id: "angular",  label: "Angular",  desc: "Sharp edges, geometric" },
  { id: "elegant",  label: "Elegant",  desc: "Graceful and refined" },
  { id: "broad",    label: "Broad",    desc: "Wide shoulders, powerful" },
  { id: "heavy",    label: "Heavy",    desc: "Thick and imposing" },
  { id: "sleek",    label: "Sleek",    desc: "Streamlined and fast" },
  { id: "round",    label: "Round",    desc: "Soft and friendly" },
];

/** @deprecated Alias for BUILD_OPTIONS */
export const BODY_STYLE_OPTIONS = BUILD_OPTIONS;

/** Create a default character definition. */
export function defaultCharacter(): BotKree8rCharacter {
  return {
    version: "1.0",
    name: "my_bot",
    display_name: "My Bot",
    description: "A custom character built with BotKree8r.",
    body: {
      type: "mech",
      build: "standard",
      colors: { primary: "#00d4ff", secondary: "#0088aa", dark: "#004455" },
    },
    face: {
      style: "minimal",
      accent: "#e0e0e0",
      bg: "#0a0a0f",
    },
    traits: {
      eye_style: "default",
      face_shape: "default",
      accessory: "none",
      personality: "casual",
      voice_pitch: 1.0,
      default_pose: "neutral",
      idle_animation: "breathing",
    },
    metadata: {
      created: new Date().toISOString(),
      creator: "BotKree8r",
    },
  };
}
