/**
 * RobotBody — Canvas renderer for mechanical robot bodies.
 *
 * 8 visually distinct body types, all sharing:
 *   - ThemeColors (primary / secondary / dark)
 *   - BodyBuild proportional modifiers (standard / slim / broad / etc.)
 *   - Same skeleton attachment points (head, shoulders, hips)
 *   - A breathing idle animation
 *
 * Body Types:
 *   mech     — Classic blocky mech robot (original)
 *   sleek    — Smooth aerodynamic curves, tapered limbs
 *   heavy    — Thick armor plating, massive shoulders
 *   skeletal — Exposed frame / wireframe limbs, minimal shell
 *   orb      — Spherical joints and round segments, friendly
 *   knight   — Medieval armor plates, angular pauldrons
 *   cyber    — Transparent panels with glowing circuit traces
 *   retro    — 1950s sci-fi boxy robot with rivets
 */

// ── Types ────────────────────────────────────────────────────
export interface ThemeColors {
  primary: string;    // main outlines, bright accents
  secondary: string;  // panels, mid-tone fills
  dark: string;       // shadows, recessed areas
}

/** Proportional build modifier (applied ON TOP of any body type). */
export type BodyBuild =
  | "standard" | "slim" | "angular" | "elegant"
  | "broad" | "heavy" | "sleek" | "round";

/** Visually distinct body renderer. */
export type BodyType =
  | "mech" | "sleek" | "heavy" | "skeletal"
  | "orb" | "knight" | "cyber" | "retro";

/** Legacy alias — kept for schema compat. */
export type BodyStyle = BodyBuild;

export interface BuildProps {
  tw: number; th: number; sw: number;
  at: number; lt: number; nw: number; cr: number;
}

const BUILD_TABLE: Record<BodyBuild, BuildProps> = {
  standard: { tw: 1.0,  th: 1.0,  sw: 1.0,  at: 1.0,  lt: 1.0,  nw: 1.0,  cr: 15 },
  slim:     { tw: 0.8,  th: 1.12, sw: 0.85, at: 0.8,  lt: 0.8,  nw: 0.85, cr: 12 },
  angular:  { tw: 0.95, th: 0.92, sw: 1.05, at: 0.9,  lt: 0.9,  nw: 0.9,  cr: 4 },
  elegant:  { tw: 0.88, th: 1.08, sw: 0.92, at: 0.85, lt: 0.85, nw: 0.82, cr: 20 },
  broad:    { tw: 1.2,  th: 1.0,  sw: 1.25, at: 1.15, lt: 1.1,  nw: 1.1,  cr: 18 },
  heavy:    { tw: 1.3,  th: 1.05, sw: 1.35, at: 1.3,  lt: 1.25, nw: 1.15, cr: 10 },
  sleek:    { tw: 0.85, th: 1.05, sw: 0.88, at: 0.78, lt: 0.78, nw: 0.8,  cr: 8 },
  round:    { tw: 1.1,  th: 0.95, sw: 1.05, at: 1.1,  lt: 1.1,  nw: 1.05, cr: 25 },
};
/** @deprecated Use BUILD_TABLE */
const BODY_STYLES = BUILD_TABLE;

// 17 built-in theme presets (matches character_library.py THEME_COLORS)
export const THEME_PRESETS: Record<string, ThemeColors> = {
  cyan:         { primary: "#00d4ff", secondary: "#0088aa", dark: "#004455" },
  pink:         { primary: "#ff69b4", secondary: "#aa4477", dark: "#552244" },
  violet:       { primary: "#aa66ff", secondary: "#6633aa", dark: "#331166" },
  amber:        { primary: "#ffaa00", secondary: "#886600", dark: "#3d2a0e" },
  emerald:      { primary: "#00ff88", secondary: "#008844", dark: "#0e3d2a" },
  crimson:      { primary: "#ff3344", secondary: "#882222", dark: "#3d1515" },
  ice:          { primary: "#88ddff", secondary: "#4488aa", dark: "#1a3344" },
  sunset:       { primary: "#ff6633", secondary: "#aa4422", dark: "#3d1a0e" },
  phantom:      { primary: "#ffffff", secondary: "#444444", dark: "#1a1a1a" },
  gray:         { primary: "#aaaaaa", secondary: "#666666", dark: "#333333" },
  alien_green:  { primary: "#44ff88", secondary: "#22aa55", dark: "#0d3d1a" },
  salsa_orange: { primary: "#ff6633", secondary: "#cc4422", dark: "#3d1a0e" },
  spark:        { primary: "#ffee00", secondary: "#ccaa00", dark: "#4d4000" },
  hotpink:      { primary: "#ff44aa", secondary: "#cc2288", dark: "#551144" },
  echo_blue:    { primary: "#44aaff", secondary: "#2266cc", dark: "#112244" },
  glitch_green: { primary: "#33ff66", secondary: "#22aa44", dark: "#0d3d1a" },
  void:         { primary: "#222222", secondary: "#111111", dark: "#050505" },
};

// ── Helper drawing ───────────────────────────────────────────

function roundedRect(
  ctx: CanvasRenderingContext2D,
  x: number, y: number, w: number, h: number,
  r: number, fill?: string, stroke?: string, lw = 2,
) {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw; ctx.stroke(); }
}

function limbSegment(
  ctx: CanvasRenderingContext2D,
  x1: number, y1: number, x2: number, y2: number,
  width: number, fill: string, border: string,
) {
  ctx.lineCap = "round";
  // border
  ctx.beginPath();
  ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
  ctx.strokeStyle = border; ctx.lineWidth = width + 4;
  ctx.stroke();
  // fill
  ctx.beginPath();
  ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
  ctx.strokeStyle = fill; ctx.lineWidth = width;
  ctx.stroke();
}

function circle(
  ctx: CanvasRenderingContext2D,
  cx: number, cy: number, r: number,
  fill?: string, stroke?: string, lw = 2,
) {
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw; ctx.stroke(); }
}

// ── Body Type Registry ───────────────────────────────────────

export interface BodyTypeDef {
  id: BodyType;
  name: string;
  desc: string;
  draw: BodyDrawFn;
}

type BodyDrawFn = (
  ctx: CanvasRenderingContext2D,
  cx: number, cy: number,
  s: number, p: BuildProps, c: ThemeColors, breath: number,
) => { x: number; y: number };

/** Registry of all body type renderers. */
export const BODY_TYPES: BodyTypeDef[] = [];

function registerBody(id: BodyType, name: string, desc: string, draw: BodyDrawFn) {
  BODY_TYPES.push({ id, name, desc, draw });
}

// ── Shared helpers ───────────────────────────────────────────

function _arms(
  ctx: CanvasRenderingContext2D, cx: number, sy: number,
  shoulderOff: number, s: number, p: BuildProps, c: ThemeColors,
  armW: number, upperLen: number, lowerLen: number,
  jointFill: string, handStyle: "circle" | "claw" | "mitten" | "box" | "sphere" = "circle",
) {
  for (const side of [-1, 1]) {
    const sx2 = cx + side * shoulderOff;
    const splayRad = (side * 5 * Math.PI) / 180;
    const ex = sx2 + Math.sin(splayRad) * upperLen;
    const ey = sy + Math.cos(splayRad) * upperLen;
    const hx = ex + Math.sin(splayRad) * lowerLen;
    const hy = ey + Math.cos(splayRad) * lowerLen;

    limbSegment(ctx, sx2, sy, ex, ey, armW, c.secondary, c.primary);
    circle(ctx, ex, ey, armW / 2, jointFill, c.primary, 2 * s);
    limbSegment(ctx, ex, ey, hx, hy, armW * 0.9, c.primary, c.primary);

    if (handStyle === "circle" || handStyle === "sphere") {
      circle(ctx, hx, hy, armW * 0.7, c.primary, c.dark, 2 * s);
    } else if (handStyle === "claw") {
      for (let f = -1; f <= 1; f++) {
        ctx.beginPath(); ctx.moveTo(hx + f * 4 * s, hy);
        ctx.lineTo(hx + f * 6 * s, hy + 14 * s);
        ctx.strokeStyle = c.primary; ctx.lineWidth = 2 * s; ctx.stroke();
      }
    } else if (handStyle === "mitten") {
      roundedRect(ctx, hx - 8 * s, hy - 5 * s, 16 * s, 18 * s, 8 * s, c.primary, c.dark, 2 * s);
    } else {
      roundedRect(ctx, hx - 7 * s, hy - 5 * s, 14 * s, 16 * s, 3 * s, c.primary, c.dark, 2 * s);
    }
  }
}

function _legs(
  ctx: CanvasRenderingContext2D, cx: number, hipY: number,
  spread: number, s: number, p: BuildProps, c: ThemeColors,
  legW: number, thighLen: number, shinLen: number,
  jointFill: string, footStyle: "rect" | "round" | "boot" | "peg" = "rect",
) {
  for (const side of [-1, 1]) {
    const hx = cx + side * spread;
    const ky = hipY + thighLen;
    const fy = ky + shinLen;

    limbSegment(ctx, hx, hipY, hx, ky, legW, c.secondary, c.primary);
    circle(ctx, hx, ky, legW / 2, jointFill, c.primary, 2 * s);
    limbSegment(ctx, hx, ky, hx, fy, legW * 0.9, c.primary, c.primary);

    if (footStyle === "rect") {
      const fw = 25 * s * p.lt, fh = 12 * s;
      roundedRect(ctx, hx - fw / 2, fy - fh / 2, fw, fh, 5 * s, c.dark, c.primary, 2 * s);
    } else if (footStyle === "round") {
      circle(ctx, hx, fy, 12 * s * p.lt, c.dark, c.primary, 2 * s);
    } else if (footStyle === "boot") {
      const fw = 28 * s * p.lt, fh = 16 * s;
      roundedRect(ctx, hx - fw * 0.35, fy - fh / 2, fw, fh, 4 * s, c.dark, c.primary, 2 * s);
    } else {
      circle(ctx, hx, fy + 2 * s, 5 * s, c.dark, c.primary, 2 * s);
    }
  }
}

function _neck(
  ctx: CanvasRenderingContext2D, cx: number, ny: number,
  s: number, p: BuildProps, c: ThemeColors,
  style: "rect" | "thin" | "rings" | "pipe" = "rect",
) {
  const nw = 30 * s * p.nw, nh = 20 * s;
  if (style === "rect") {
    roundedRect(ctx, cx - nw / 2, ny, nw, nh, 5 * s, c.secondary, c.primary, 2 * s);
    for (const lx of [cx - 8 * s, cx, cx + 8 * s]) {
      ctx.beginPath(); ctx.moveTo(lx, ny + 5 * s); ctx.lineTo(lx, ny + 15 * s);
      ctx.strokeStyle = c.primary; ctx.lineWidth = 1 * s; ctx.stroke();
    }
  } else if (style === "thin") {
    limbSegment(ctx, cx, ny, cx, ny + nh, 8 * s * p.nw, c.secondary, c.primary);
  } else if (style === "rings") {
    for (let i = 0; i < 3; i++) {
      circle(ctx, cx, ny + 5 * s + i * 6 * s, 10 * s * p.nw, undefined, c.primary, 1.5 * s);
    }
    limbSegment(ctx, cx, ny, cx, ny + nh, 6 * s * p.nw, c.secondary, c.primary);
  } else {
    ctx.beginPath();
    ctx.moveTo(cx - 6 * s * p.nw, ny); ctx.lineTo(cx + 6 * s * p.nw, ny);
    ctx.lineTo(cx + 4 * s * p.nw, ny + nh); ctx.lineTo(cx - 4 * s * p.nw, ny + nh);
    ctx.closePath(); ctx.fillStyle = c.secondary; ctx.fill();
    ctx.strokeStyle = c.primary; ctx.lineWidth = 2 * s; ctx.stroke();
  }
}

// ═══════════════════════════════════════════════════════════════
// Body Type 1: MECH — Classic blocky mech robot (original)
// ═══════════════════════════════════════════════════════════════
registerBody("mech", "Mech", "Classic blocky mech robot with panel details", (ctx, cx, cy, s, p, c, breath) => {
  const tw = 100 * s * p.tw, th = 140 * s * p.th;
  const shOff = 65 * s * p.sw, legSp = 20 * s * p.lt;
  const cr = p.cr * s;

  // Legs
  _legs(ctx, cx, cy + th - 20 * s, legSp, s, p, c, 16 * s * p.lt, 50 * s, 50 * s, c.dark, "rect");

  // Torso
  const ty = cy + breath;
  roundedRect(ctx, cx - tw / 2, ty, tw, th, cr, c.secondary, c.primary, 3 * s);
  // Chest panel
  const pw = 60 * s * p.tw, ph = 80 * s * p.th;
  roundedRect(ctx, cx - pw / 2, ty + 20 * s, pw, ph, Math.max(4, cr * 0.5), c.dark, c.primary, 2 * s);
  // Power core
  const coreR = 12 * s, coreY = ty + 50 * s;
  for (let i = 3; i >= 1; i--) circle(ctx, cx, coreY, coreR * i, undefined, c.primary, 1 * s);
  circle(ctx, cx, coreY, coreR, c.primary);
  // Panel detail lines
  for (const ly of [ty + 30 * s, ty + 70 * s, ty + 110 * s]) {
    ctx.beginPath(); ctx.moveTo(cx - tw / 2 + 10 * s, ly); ctx.lineTo(cx + tw / 2 - 10 * s, ly);
    ctx.strokeStyle = c.primary; ctx.lineWidth = 1 * s; ctx.stroke();
  }
  // Shoulder plates
  for (const side of [-1, 1]) {
    const sx = cx + side * tw / 2, capW = 30 * s * p.sw, capH = 25 * s * p.at;
    ctx.beginPath(); ctx.moveTo(sx, ty + 10 * s); ctx.lineTo(sx + side * capW, ty + 5 * s);
    ctx.lineTo(sx + side * capW, ty + 10 * s + capH); ctx.lineTo(sx, ty + 10 * s + capH - 5 * s);
    ctx.closePath(); ctx.fillStyle = c.secondary; ctx.fill();
    ctx.strokeStyle = c.primary; ctx.lineWidth = 2 * s; ctx.stroke();
  }

  // Arms
  _arms(ctx, cx, ty + 20 * s, shOff, s, p, c, 14 * s * p.at, 45 * s, 40 * s, c.dark, "circle");

  // Neck
  _neck(ctx, cx, cy - 10 * s + breath, s, p, c, "rect");
  return { x: cx, y: cy - 20 * s + breath };
});

// ═══════════════════════════════════════════════════════════════
// Body Type 2: SLEEK — Smooth aerodynamic curves
// ═══════════════════════════════════════════════════════════════
registerBody("sleek", "Sleek", "Smooth aerodynamic curves, tapered limbs", (ctx, cx, cy, s, p, c, breath) => {
  const tw = 80 * s * p.tw, th = 150 * s * p.th;
  const shOff = 50 * s * p.sw, legSp = 16 * s * p.lt;

  _legs(ctx, cx, cy + th - 20 * s, legSp, s, p, c, 10 * s * p.lt, 55 * s, 55 * s, c.dark, "round");

  const ty = cy + breath;
  // Tapered torso — wider at top, narrow at waist
  ctx.beginPath();
  ctx.moveTo(cx - tw * 0.35, ty + th);           // bottom left
  ctx.quadraticCurveTo(cx - tw * 0.3, ty + th * 0.5, cx - tw / 2, ty); // left curve
  ctx.lineTo(cx + tw / 2, ty);                   // top
  ctx.quadraticCurveTo(cx + tw * 0.3, ty + th * 0.5, cx + tw * 0.35, ty + th); // right curve
  ctx.closePath();
  ctx.fillStyle = c.secondary; ctx.fill();
  ctx.strokeStyle = c.primary; ctx.lineWidth = 2 * s; ctx.stroke();
  // Center seam
  ctx.beginPath(); ctx.moveTo(cx, ty + 10 * s); ctx.lineTo(cx, ty + th - 10 * s);
  ctx.strokeStyle = c.primary; ctx.lineWidth = 1 * s; ctx.stroke();
  // Core: diamond
  const dy = ty + 45 * s;
  ctx.beginPath(); ctx.moveTo(cx, dy - 12 * s); ctx.lineTo(cx + 8 * s, dy);
  ctx.lineTo(cx, dy + 12 * s); ctx.lineTo(cx - 8 * s, dy); ctx.closePath();
  ctx.fillStyle = c.primary; ctx.fill();

  _arms(ctx, cx, ty + 15 * s, shOff, s, p, c, 10 * s * p.at, 50 * s, 45 * s, c.dark, "circle");
  _neck(ctx, cx, cy - 10 * s + breath, s, p, c, "thin");
  return { x: cx, y: cy - 20 * s + breath };
});

// ═══════════════════════════════════════════════════════════════
// Body Type 3: HEAVY — Thick armor plating, massive shoulders
// ═══════════════════════════════════════════════════════════════
registerBody("heavy", "Heavy", "Thick armor plating, massive shoulders", (ctx, cx, cy, s, p, c, breath) => {
  const tw = 120 * s * p.tw, th = 135 * s * p.th;
  const shOff = 78 * s * p.sw, legSp = 26 * s * p.lt;

  _legs(ctx, cx, cy + th - 15 * s, legSp, s, p, c, 22 * s * p.lt, 48 * s, 45 * s, c.dark, "boot");

  const ty = cy + breath;
  // Wide, thick torso
  roundedRect(ctx, cx - tw / 2, ty, tw, th, 8 * s, c.secondary, c.primary, 4 * s);
  // Chest armor plate
  const apW = tw * 0.7, apH = th * 0.5;
  roundedRect(ctx, cx - apW / 2, ty + 15 * s, apW, apH, 6 * s, c.dark, c.primary, 3 * s);
  // Horizontal rivet lines
  for (let i = 0; i < 3; i++) {
    const ry = ty + 25 * s + i * 22 * s;
    for (let j = -2; j <= 2; j++) {
      circle(ctx, cx + j * 18 * s, ry, 3 * s, c.primary);
    }
  }
  // Core: heavy-duty hexagonal
  const cY = ty + 55 * s, cR = 16 * s;
  ctx.beginPath();
  for (let a = 0; a < 6; a++) {
    const ang = (a * 60 - 90) * Math.PI / 180;
    const px = cx + Math.cos(ang) * cR, py = cY + Math.sin(ang) * cR;
    a === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
  }
  ctx.closePath(); ctx.fillStyle = c.primary; ctx.fill();
  ctx.strokeStyle = c.dark; ctx.lineWidth = 2 * s; ctx.stroke();

  // Massive shoulder plates
  for (const side of [-1, 1]) {
    const sx = cx + side * tw / 2;
    roundedRect(ctx, sx - (side > 0 ? 5 * s : 40 * s), ty, 45 * s, 35 * s * p.at, 6 * s, c.secondary, c.primary, 3 * s);
  }

  _arms(ctx, cx, ty + 20 * s, shOff, s, p, c, 20 * s * p.at, 42 * s, 38 * s, c.dark, "box");
  _neck(ctx, cx, cy - 8 * s + breath, s, p, c, "pipe");
  return { x: cx, y: cy - 18 * s + breath };
});

// ═══════════════════════════════════════════════════════════════
// Body Type 4: SKELETAL — Exposed frame, minimal shell
// ═══════════════════════════════════════════════════════════════
registerBody("skeletal", "Skeletal", "Exposed wireframe, minimal covering", (ctx, cx, cy, s, p, c, breath) => {
  const tw = 70 * s * p.tw, th = 130 * s * p.th;
  const shOff = 48 * s * p.sw, legSp = 18 * s * p.lt;

  _legs(ctx, cx, cy + th - 20 * s, legSp, s, p, c, 8 * s * p.lt, 52 * s, 50 * s, c.dark, "peg");

  const ty = cy + breath;
  // Spine line
  ctx.beginPath(); ctx.moveTo(cx, ty); ctx.lineTo(cx, ty + th);
  ctx.strokeStyle = c.primary; ctx.lineWidth = 4 * s; ctx.stroke();
  // Rib cage: 4 curved rib pairs
  for (let i = 0; i < 4; i++) {
    const ry = ty + 20 * s + i * 22 * s;
    for (const side of [-1, 1]) {
      ctx.beginPath();
      ctx.moveTo(cx, ry);
      ctx.quadraticCurveTo(cx + side * tw * 0.4, ry - 8 * s, cx + side * tw / 2, ry + 5 * s);
      ctx.strokeStyle = c.secondary; ctx.lineWidth = 2 * s; ctx.stroke();
    }
  }
  // Hip plate (small)
  roundedRect(ctx, cx - tw * 0.3, ty + th - 20 * s, tw * 0.6, 18 * s, 4 * s, c.dark, c.primary, 2 * s);
  // Core: small exposed sphere
  circle(ctx, cx, ty + 40 * s, 8 * s, c.primary, c.dark, 2 * s);

  _arms(ctx, cx, ty + 12 * s, shOff, s, p, c, 8 * s * p.at, 48 * s, 44 * s, c.secondary, "claw");
  _neck(ctx, cx, cy - 10 * s + breath, s, p, c, "thin");
  return { x: cx, y: cy - 20 * s + breath };
});

// ═══════════════════════════════════════════════════════════════
// Body Type 5: ORB — Round segments, spherical joints, friendly
// ═══════════════════════════════════════════════════════════════
registerBody("orb", "Orb", "Spherical segments, round joints, friendly look", (ctx, cx, cy, s, p, c, breath) => {
  const torsoR = 65 * s * p.tw;
  const shOff = 55 * s * p.sw, legSp = 20 * s * p.lt;
  const th = torsoR * 2 * p.th;

  _legs(ctx, cx, cy + th - 20 * s, legSp, s, p, c, 14 * s * p.lt, 45 * s, 42 * s, c.dark, "round");

  const ty = cy + breath;
  // Main body: big oval
  ctx.beginPath();
  ctx.ellipse(cx, ty + torsoR * p.th, torsoR, torsoR * p.th, 0, 0, Math.PI * 2);
  ctx.fillStyle = c.secondary; ctx.fill();
  ctx.strokeStyle = c.primary; ctx.lineWidth = 3 * s; ctx.stroke();
  // Belly circle
  circle(ctx, cx, ty + torsoR * p.th, torsoR * 0.5, c.dark, c.primary, 2 * s);
  // Core: happy glow
  circle(ctx, cx, ty + torsoR * p.th * 0.9, 10 * s, c.primary);
  // Belly button detail
  circle(ctx, cx, ty + torsoR * p.th * 1.2, 5 * s, undefined, c.primary, 1.5 * s);

  // Shoulder spheres
  for (const side of [-1, 1]) {
    circle(ctx, cx + side * shOff, ty + 20 * s, 14 * s * p.sw, c.secondary, c.primary, 2 * s);
  }

  _arms(ctx, cx, ty + 20 * s, shOff, s, p, c, 12 * s * p.at, 42 * s, 38 * s, c.dark, "mitten");
  _neck(ctx, cx, cy - 8 * s + breath, s, p, c, "rings");
  return { x: cx, y: cy - 18 * s + breath };
});

// ═══════════════════════════════════════════════════════════════
// Body Type 6: KNIGHT — Medieval armor plates, angular pauldrons
// ═══════════════════════════════════════════════════════════════
registerBody("knight", "Knight", "Medieval armor plates, angular pauldrons", (ctx, cx, cy, s, p, c, breath) => {
  const tw = 100 * s * p.tw, th = 145 * s * p.th;
  const shOff = 68 * s * p.sw, legSp = 22 * s * p.lt;

  _legs(ctx, cx, cy + th - 18 * s, legSp, s, p, c, 18 * s * p.lt, 50 * s, 48 * s, c.dark, "boot");

  const ty = cy + breath;
  // Torso: tapers at waist, wider at chest
  ctx.beginPath();
  ctx.moveTo(cx - tw * 0.35, ty + th);
  ctx.lineTo(cx - tw / 2, ty + 20 * s);
  ctx.lineTo(cx - tw * 0.4, ty);
  ctx.lineTo(cx + tw * 0.4, ty);
  ctx.lineTo(cx + tw / 2, ty + 20 * s);
  ctx.lineTo(cx + tw * 0.35, ty + th);
  ctx.closePath();
  ctx.fillStyle = c.secondary; ctx.fill();
  ctx.strokeStyle = c.primary; ctx.lineWidth = 3 * s; ctx.stroke();
  // Center plate
  ctx.beginPath();
  ctx.moveTo(cx, ty + 10 * s); ctx.lineTo(cx + 25 * s, ty + 45 * s);
  ctx.lineTo(cx, ty + 80 * s); ctx.lineTo(cx - 25 * s, ty + 45 * s);
  ctx.closePath(); ctx.fillStyle = c.dark; ctx.fill();
  ctx.strokeStyle = c.primary; ctx.lineWidth = 2 * s; ctx.stroke();
  // Core: cross emblem
  const ey = ty + 45 * s;
  roundedRect(ctx, cx - 3 * s, ey - 12 * s, 6 * s, 24 * s, 2 * s, c.primary);
  roundedRect(ctx, cx - 10 * s, ey - 3 * s, 20 * s, 6 * s, 2 * s, c.primary);
  // Belt line
  roundedRect(ctx, cx - tw * 0.37, ty + th * 0.65, tw * 0.74, 10 * s, 3 * s, c.dark, c.primary, 2 * s);

  // Pointed pauldrons
  for (const side of [-1, 1]) {
    const px = cx + side * tw / 2;
    ctx.beginPath();
    ctx.moveTo(px, ty + 5 * s);
    ctx.lineTo(px + side * 35 * s * p.sw, ty - 5 * s);
    ctx.lineTo(px + side * 30 * s * p.sw, ty + 30 * s);
    ctx.lineTo(px, ty + 25 * s);
    ctx.closePath(); ctx.fillStyle = c.secondary; ctx.fill();
    ctx.strokeStyle = c.primary; ctx.lineWidth = 2 * s; ctx.stroke();
  }

  _arms(ctx, cx, ty + 20 * s, shOff, s, p, c, 16 * s * p.at, 44 * s, 40 * s, c.dark, "box");
  _neck(ctx, cx, cy - 10 * s + breath, s, p, c, "pipe");
  return { x: cx, y: cy - 20 * s + breath };
});

// ═══════════════════════════════════════════════════════════════
// Body Type 7: CYBER — Transparent panels with glowing circuits
// ═══════════════════════════════════════════════════════════════
registerBody("cyber", "Cyber", "Transparent panels with glowing circuit lines", (ctx, cx, cy, s, p, c, breath) => {
  const tw = 90 * s * p.tw, th = 140 * s * p.th;
  const shOff = 58 * s * p.sw, legSp = 18 * s * p.lt;

  _legs(ctx, cx, cy + th - 20 * s, legSp, s, p, c, 12 * s * p.lt, 52 * s, 50 * s, c.dark, "rect");

  const ty = cy + breath;
  // Transparent torso shell
  ctx.save();
  ctx.globalAlpha = 0.35;
  roundedRect(ctx, cx - tw / 2, ty, tw, th, 12 * s, c.secondary, undefined, 0);
  ctx.restore();
  // Outline
  roundedRect(ctx, cx - tw / 2, ty, tw, th, 12 * s, undefined, c.primary, 2 * s);

  // Circuit traces inside torso
  ctx.save(); ctx.globalAlpha = 0.9;
  ctx.strokeStyle = c.primary; ctx.lineWidth = 1.5 * s;
  // Vertical main bus
  ctx.beginPath(); ctx.moveTo(cx, ty + 10 * s); ctx.lineTo(cx, ty + th - 10 * s); ctx.stroke();
  // Horizontal branches
  for (let i = 0; i < 5; i++) {
    const by = ty + 20 * s + i * 24 * s;
    const bw = (tw / 2 - 15 * s) * (0.5 + Math.random() * 0.5);
    const side = i % 2 === 0 ? -1 : 1;
    ctx.beginPath(); ctx.moveTo(cx, by); ctx.lineTo(cx + side * bw, by);
    ctx.lineTo(cx + side * bw, by + 8 * s); ctx.stroke();
    // Node dot at end
    circle(ctx, cx + side * bw, by + 8 * s, 3 * s, c.primary);
  }
  ctx.restore();
  // Core: glowing data node
  circle(ctx, cx, ty + 50 * s, 14 * s, undefined, c.primary, 2 * s);
  circle(ctx, cx, ty + 50 * s, 8 * s, c.primary);
  // Hex overlay
  for (const offset of [-20, 20]) {
    const hx = cx + offset * s, hy = ty + 90 * s;
    ctx.beginPath();
    for (let a = 0; a < 6; a++) {
      const ang = (a * 60 - 90) * Math.PI / 180;
      const px = hx + Math.cos(ang) * 10 * s, py = hy + Math.sin(ang) * 10 * s;
      a === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    }
    ctx.closePath(); ctx.strokeStyle = c.primary; ctx.lineWidth = 1 * s; ctx.stroke();
  }

  _arms(ctx, cx, ty + 15 * s, shOff, s, p, c, 11 * s * p.at, 48 * s, 44 * s, c.dark, "circle");
  _neck(ctx, cx, cy - 10 * s + breath, s, p, c, "rings");
  return { x: cx, y: cy - 20 * s + breath };
});

// ═══════════════════════════════════════════════════════════════
// Body Type 8: RETRO — 1950s sci-fi boxy robot with rivets
// ═══════════════════════════════════════════════════════════════
registerBody("retro", "Retro", "1950s sci-fi boxy robot with rivets and dials", (ctx, cx, cy, s, p, c, breath) => {
  const tw = 110 * s * p.tw, th = 130 * s * p.th;
  const shOff = 68 * s * p.sw, legSp = 24 * s * p.lt;

  _legs(ctx, cx, cy + th - 15 * s, legSp, s, p, c, 18 * s * p.lt, 46 * s, 44 * s, c.dark, "rect");

  const ty = cy + breath;
  // Boxy torso — zero radius
  roundedRect(ctx, cx - tw / 2, ty, tw, th, 3 * s, c.secondary, c.primary, 3 * s);
  // Rivets: corners + edges
  const rivetR = 3 * s;
  const margin = 8 * s;
  for (const rx of [cx - tw / 2 + margin, cx + tw / 2 - margin]) {
    for (const ry of [ty + margin, ty + th / 2, ty + th - margin]) {
      circle(ctx, rx, ry, rivetR, c.dark, c.primary, 1 * s);
    }
  }
  // Chest panel: recessed rectangle
  const pw = tw * 0.6, ph = th * 0.4;
  roundedRect(ctx, cx - pw / 2, ty + 20 * s, pw, ph, 2 * s, c.dark, c.primary, 2 * s);
  // Dial gauges
  for (const dx of [-18, 0, 18]) {
    const dy = ty + 35 * s;
    circle(ctx, cx + dx * s, dy, 8 * s, c.dark, c.primary, 1.5 * s);
    // Needle
    const angle = (dx + 20) * 3 * Math.PI / 180;
    ctx.beginPath(); ctx.moveTo(cx + dx * s, dy);
    ctx.lineTo(cx + dx * s + Math.cos(angle) * 6 * s, dy + Math.sin(angle) * 6 * s);
    ctx.strokeStyle = c.primary; ctx.lineWidth = 1.5 * s; ctx.stroke();
  }
  // Vent slats at bottom
  for (let i = 0; i < 4; i++) {
    const vy = ty + th * 0.65 + i * 8 * s;
    ctx.beginPath(); ctx.moveTo(cx - pw / 2 + 5 * s, vy); ctx.lineTo(cx + pw / 2 - 5 * s, vy);
    ctx.strokeStyle = c.primary; ctx.lineWidth = 1.5 * s; ctx.stroke();
  }
  // Antenna nubs on top
  for (const side of [-1, 1]) {
    const ax = cx + side * tw * 0.35;
    ctx.beginPath(); ctx.moveTo(ax, ty); ctx.lineTo(ax, ty - 10 * s);
    ctx.strokeStyle = c.primary; ctx.lineWidth = 2 * s; ctx.stroke();
    circle(ctx, ax, ty - 12 * s, 3 * s, c.primary);
  }

  _arms(ctx, cx, ty + 18 * s, shOff, s, p, c, 16 * s * p.at, 44 * s, 40 * s, c.dark, "box");
  _neck(ctx, cx, cy - 8 * s + breath, s, p, c, "rect");
  return { x: cx, y: cy - 18 * s + breath };
});

// ═══════════════════════════════════════════════════════════════
// Public API
// ═══════════════════════════════════════════════════════════════

/**
 * Draw a robot body using the specified body type and build.
 *
 * @param ctx         Canvas 2D context
 * @param cx          Center X
 * @param cy          Torso top Y
 * @param scale       Scale multiplier (1.0 ≈ 280px body)
 * @param colors      ThemeColors
 * @param bodyType    Visual body type (mech, sleek, cyber, etc.)
 * @param build       Proportional build modifier (standard, slim, broad, etc.)
 * @param breathPhase 0–1 breathing cycle phase
 * @returns Head attachment point {x, y}
 */
export function drawRobotBody(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  scale: number,
  colors: ThemeColors,
  bodyType: BodyType = "mech",
  build: BodyBuild = "standard",
  breathPhase = 0,
): { x: number; y: number } {
  const p = BUILD_TABLE[build] ?? BUILD_TABLE.standard;
  const breath = Math.sin(breathPhase * Math.PI * 2) * 2 * scale;
  const def = BODY_TYPES.find((b) => b.id === bodyType) ?? BODY_TYPES[0];
  return def.draw(ctx, cx, cy, scale, p, colors, breath);
}

/** @deprecated Legacy 6-arg overload — maps style→build, bodyType defaults to "mech". */
export function drawRobotBodyLegacy(
  ctx: CanvasRenderingContext2D,
  cx: number, cy: number,
  scale: number, colors: ThemeColors,
  style: BodyStyle = "standard",
  breathPhase = 0,
): { x: number; y: number } {
  return drawRobotBody(ctx, cx, cy, scale, colors, "mech", style, breathPhase);
}

// ── Exports ──────────────────────────────────────────────────
export { BODY_STYLES, BUILD_TABLE };
