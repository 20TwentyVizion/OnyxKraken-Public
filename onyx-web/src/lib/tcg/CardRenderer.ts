/**
 * TCG Card Renderer — Draws a complete Onyx: Overclock card on a canvas.
 *
 * Composites:
 *   1. Card frame (colored by Signal faction)
 *   2. Character art (robotBody + faceRenderer from the Onyx engine)
 *   3. Name banner, stats (cost/power/defense), ability text, flavor text
 *   4. Rarity badge, type/signal indicators, body type tag
 *
 * Card dimensions: 400×560 (4:5.6 ratio, close to standard TCG 2.5×3.5)
 */

import type { Card, CardSignal, CardRarity } from './types';
import { SIGNAL_META, RARITY_COLORS } from './types';
import { drawRobotBody, THEME_PRESETS } from '../robotBody';
import type { ThemeColors, BodyType, BodyBuild } from '../robotBody';
import { FaceRenderer } from '../faceRenderer';

// ── Card Layout Constants ───────────────────────────────────
export const CARD_W = 400;
export const CARD_H = 560;
const BORDER = 8;
const INNER_PAD = 12;
const ART_TOP = 70;
const ART_H = 220;
const NAME_H = 34;
const STATS_H = 30;
const TEXT_TOP = ART_TOP + ART_H + NAME_H + STATS_H + 8;

// ── Signal → character color mapping ────────────────────────
const SIGNAL_BODY_COLORS: Record<CardSignal, ThemeColors> = {
  logic:   THEME_PRESETS.cyan,
  pulse:   THEME_PRESETS.crimson,
  flux:    THEME_PRESETS.emerald,
  static:  THEME_PRESETS.spark,
  void:    THEME_PRESETS.violet,
  neutral: THEME_PRESETS.gray,
};

// ── Rarity → frame accent ───────────────────────────────────
function rarityBorderColor(r: CardRarity): string {
  const m: Record<CardRarity, string> = {
    common: '#888899',
    uncommon: '#ddaa22',
    rare: '#2288ff',
    epic: '#aa44ff',
    legendary: '#ff6600',
    holographic: '#ff44cc',
  };
  return m[r] ?? '#888899';
}

// ── Helper: rounded rect path ───────────────────────────────
function rrect(
  ctx: CanvasRenderingContext2D,
  x: number, y: number, w: number, h: number, r: number,
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
}

// ── Helper: wrap text ───────────────────────────────────────
function wrapText(
  ctx: CanvasRenderingContext2D, text: string,
  x: number, y: number, maxW: number, lineH: number, maxLines: number,
): number {
  const words = text.split(' ');
  let line = '';
  let linesDrawn = 0;
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxW && line) {
      ctx.fillText(line, x, y);
      y += lineH;
      linesDrawn++;
      if (linesDrawn >= maxLines) return y;
      line = word;
    } else {
      line = test;
    }
  }
  if (line) {
    ctx.fillText(line, x, y);
    linesDrawn++;
    y += lineH;
  }
  return y;
}

// ── Card character config ───────────────────────────────────
export interface CardCharacterConfig {
  bodyType?: BodyType;
  bodyBuild?: BodyBuild;
  colors?: ThemeColors;
  faceEmotion?: string;
  /** 0-1 breathing phase for static pose */
  breathPhase?: number;
}

// ── Shared face renderer (reused across draws) ──────────────
let _face: FaceRenderer | null = null;
function getFace(): FaceRenderer {
  if (!_face) _face = new FaceRenderer();
  return _face;
}

// ═════════════════════════════════════════════════════════════
// Main render function
// ═════════════════════════════════════════════════════════════
export function renderCard(
  ctx: CanvasRenderingContext2D,
  card: Card,
  charConfig: CardCharacterConfig = {},
) {
  const signalColor = SIGNAL_META[card.signal]?.color ?? '#888899';
  const signalGlow = SIGNAL_META[card.signal]?.glow ?? '#88889940';
  const rarityColor = rarityBorderColor(card.rarity);
  const bodyColors = charConfig.colors ?? SIGNAL_BODY_COLORS[card.signal] ?? THEME_PRESETS.cyan;
  const bodyType = charConfig.bodyType ?? card.bodyType ?? 'mech';
  const bodyBuild = charConfig.bodyBuild ?? 'standard';
  const breathPhase = charConfig.breathPhase ?? 0.25;

  ctx.save();

  // ── 1. Card background ────────────────────────────────────
  // Outer glow
  ctx.shadowColor = signalColor;
  ctx.shadowBlur = 16;
  rrect(ctx, 0, 0, CARD_W, CARD_H, 16);
  ctx.fillStyle = '#0a0a14';
  ctx.fill();
  ctx.shadowBlur = 0;

  // Frame border
  rrect(ctx, 2, 2, CARD_W - 4, CARD_H - 4, 14);
  ctx.strokeStyle = rarityColor;
  ctx.lineWidth = 3;
  ctx.stroke();

  // Inner border
  rrect(ctx, BORDER, BORDER, CARD_W - BORDER * 2, CARD_H - BORDER * 2, 10);
  ctx.strokeStyle = signalColor + '60';
  ctx.lineWidth = 1;
  ctx.stroke();

  // ── 2. Cost badge (top-left) ──────────────────────────────
  const costX = 24, costY = 24, costR = 20;
  ctx.beginPath();
  ctx.arc(costX, costY, costR, 0, Math.PI * 2);
  ctx.fillStyle = signalColor;
  ctx.fill();
  ctx.strokeStyle = '#000';
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.font = 'bold 22px "JetBrains Mono", monospace';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = '#fff';
  ctx.fillText(String(card.cost), costX, costY + 1);

  // ── 3. Card type badge (top-right) ────────────────────────
  const typeLabel = card.type.toUpperCase();
  ctx.font = 'bold 10px "JetBrains Mono", monospace';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'top';
  ctx.fillStyle = signalColor;
  const typeBgW = ctx.measureText(typeLabel).width + 12;
  rrect(ctx, CARD_W - BORDER - typeBgW - 8, BORDER + 4, typeBgW + 4, 18, 4);
  ctx.fillStyle = signalColor + '30';
  ctx.fill();
  ctx.fillStyle = signalColor;
  ctx.fillText(typeLabel, CARD_W - BORDER - 10, BORDER + 7);

  // ── 4. Art region ─────────────────────────────────────────
  const artX = INNER_PAD + BORDER;
  const artW = CARD_W - (INNER_PAD + BORDER) * 2;

  // Art background
  rrect(ctx, artX, ART_TOP, artW, ART_H, 8);
  ctx.fillStyle = '#080812';
  ctx.fill();
  ctx.strokeStyle = signalColor + '40';
  ctx.lineWidth = 1;
  ctx.stroke();

  // Signal glow behind character
  const glowGrad = ctx.createRadialGradient(
    CARD_W / 2, ART_TOP + ART_H / 2, 10,
    CARD_W / 2, ART_TOP + ART_H / 2, ART_H * 0.6,
  );
  glowGrad.addColorStop(0, signalColor + '30');
  glowGrad.addColorStop(1, 'transparent');
  ctx.fillStyle = glowGrad;
  ctx.fillRect(artX, ART_TOP, artW, ART_H);

  // Clip to art region for character rendering
  ctx.save();
  rrect(ctx, artX, ART_TOP, artW, ART_H, 8);
  ctx.clip();

  // Draw robot body
  const charScale = 0.65;
  const bodyCx = CARD_W / 2;
  const bodyCy = ART_TOP + 50;
  const headPos = drawRobotBody(
    ctx, bodyCx, bodyCy, charScale,
    bodyColors, bodyType, bodyBuild, breathPhase,
  );

  // Draw face on the head attachment point
  const faceSize = 60;
  const face = getFace();
  if (charConfig.faceEmotion) face.setEmotion(charConfig.faceEmotion);
  face.update(faceSize, faceSize);
  ctx.save();
  ctx.translate(headPos.x - faceSize / 2, headPos.y - faceSize / 2 - 8);
  face.draw(ctx, faceSize, faceSize);
  ctx.restore();

  ctx.restore(); // un-clip

  // ── 5. Body type tag (bottom-right of art) ────────────────
  if (card.bodyType) {
    const btLabel = card.bodyType.toUpperCase();
    ctx.font = 'bold 9px "JetBrains Mono", monospace';
    const btW = ctx.measureText(btLabel).width + 10;
    const btX = artX + artW - btW - 4;
    const btY = ART_TOP + ART_H - 18;
    rrect(ctx, btX, btY, btW, 14, 3);
    ctx.fillStyle = '#0a0a14cc';
    ctx.fill();
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillStyle = bodyColors.primary;
    ctx.fillText(btLabel, btX + 5, btY + 2);
  }

  // ── 6. Name banner ────────────────────────────────────────
  const nameY = ART_TOP + ART_H + 2;
  rrect(ctx, artX, nameY, artW, NAME_H, 0);
  const nameGrad = ctx.createLinearGradient(artX, nameY, artX + artW, nameY);
  nameGrad.addColorStop(0, signalColor + '25');
  nameGrad.addColorStop(0.5, signalColor + '10');
  nameGrad.addColorStop(1, signalColor + '25');
  ctx.fillStyle = nameGrad;
  ctx.fill();

  // Name text
  ctx.font = 'bold 16px "Inter", "Segoe UI", sans-serif';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = '#eeeeff';
  const maxNameW = artW - 80;
  let nameText = card.name;
  while (ctx.measureText(nameText).width > maxNameW && nameText.length > 5) {
    nameText = nameText.slice(0, -1);
  }
  ctx.fillText(nameText, artX + 8, nameY + NAME_H / 2);

  // Signal icon
  ctx.font = '14px sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText(SIGNAL_META[card.signal]?.icon ?? '', artX + artW - 8, nameY + NAME_H / 2);

  // ── 7. Stats bar (bots only) ──────────────────────────────
  const statsY = nameY + NAME_H;
  if (card.type === 'bot') {
    // Power badge (left)
    const pwX = artX + 30, pwY = statsY + STATS_H / 2;
    ctx.beginPath();
    ctx.arc(pwX, pwY, 14, 0, Math.PI * 2);
    ctx.fillStyle = '#ff4444';
    ctx.fill();
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.font = 'bold 16px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#fff';
    ctx.fillText(String(card.power), pwX, pwY + 1);

    // Power label
    ctx.font = '10px "Inter", sans-serif';
    ctx.textAlign = 'left';
    ctx.fillStyle = '#ff666688';
    ctx.fillText('PWR', pwX + 18, pwY + 1);

    // Defense badge (right)
    const dfX = artX + artW - 30, dfY = statsY + STATS_H / 2;
    ctx.beginPath();
    ctx.arc(dfX, dfY, 14, 0, Math.PI * 2);
    ctx.fillStyle = '#4488ff';
    ctx.fill();
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.font = 'bold 16px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#fff';
    ctx.fillText(String(card.defense), dfX, dfY + 1);

    // Defense label
    ctx.font = '10px "Inter", sans-serif';
    ctx.textAlign = 'right';
    ctx.fillStyle = '#4488ff88';
    ctx.fillText('DEF', dfX - 18, dfY + 1);

    // Keywords (center)
    if (card.keywords.length > 0) {
      ctx.font = 'bold 9px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.fillStyle = signalColor;
      const kwText = card.keywords.join(' · ');
      ctx.fillText(kwText, CARD_W / 2, statsY + STATS_H / 2 + 1);
    }
  } else {
    // Non-bot: keywords centered
    if (card.keywords.length > 0) {
      ctx.font = 'bold 10px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.fillStyle = signalColor;
      ctx.fillText(card.keywords.join(' · '), CARD_W / 2, statsY + STATS_H / 2);
    }
  }

  // Divider line
  ctx.beginPath();
  ctx.moveTo(artX + 10, statsY + STATS_H);
  ctx.lineTo(artX + artW - 10, statsY + STATS_H);
  ctx.strokeStyle = signalColor + '30';
  ctx.lineWidth = 1;
  ctx.stroke();

  // ── 8. Ability text ───────────────────────────────────────
  const textX = artX + 8;
  const textW = artW - 16;
  let textY = TEXT_TOP + 4;

  ctx.font = '12px "Inter", "Segoe UI", sans-serif';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'top';
  ctx.fillStyle = '#ccccdd';
  textY = wrapText(ctx, card.ability, textX, textY, textW, 16, 5);

  // ── 9. Flavor text ────────────────────────────────────────
  textY += 6;
  ctx.font = 'italic 11px "Inter", "Segoe UI", sans-serif';
  ctx.fillStyle = '#666688';
  wrapText(ctx, card.flavor, textX, textY, textW, 14, 3);

  // ── 10. Rarity bar (bottom) ───────────────────────────────
  const barY = CARD_H - BORDER - 24;
  rrect(ctx, artX, barY, artW, 18, 4);
  ctx.fillStyle = '#0a0a1488';
  ctx.fill();

  // Rarity text
  ctx.font = 'bold 9px "JetBrains Mono", monospace';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = rarityColor;
  ctx.fillText(card.rarity.toUpperCase(), artX + 6, barY + 9);

  // Set name
  ctx.font = '9px "JetBrains Mono", monospace';
  ctx.textAlign = 'center';
  ctx.fillStyle = '#555566';
  ctx.fillText('SIGNAL GENESIS', CARD_W / 2, barY + 9);

  // Card ID
  ctx.textAlign = 'right';
  ctx.fillStyle = '#333344';
  ctx.fillText(card.id, artX + artW - 6, barY + 9);

  // ── 11. Holographic shimmer (for holographic rarity) ──────
  if (card.rarity === 'holographic') {
    const shimmer = ctx.createLinearGradient(0, 0, CARD_W, CARD_H);
    shimmer.addColorStop(0, 'rgba(255,34,68,0.08)');
    shimmer.addColorStop(0.2, 'rgba(34,136,255,0.08)');
    shimmer.addColorStop(0.4, 'rgba(34,204,102,0.08)');
    shimmer.addColorStop(0.6, 'rgba(255,204,0,0.08)');
    shimmer.addColorStop(0.8, 'rgba(170,68,255,0.08)');
    shimmer.addColorStop(1, 'rgba(255,68,204,0.08)');
    rrect(ctx, 0, 0, CARD_W, CARD_H, 16);
    ctx.fillStyle = shimmer;
    ctx.fill();
  }

  ctx.restore();
}
