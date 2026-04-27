/**
 * AgentFace V4b Styles — Masterwork & Legendary tier faces (30-31).
 */
import { FaceRenderer, REF_W, REF_H } from "./faceRenderer";

// ── Shared particle helper ──────────────────────────────
interface Particle {
  x: number; y: number; vx: number; vy: number;
  life: number; maxLife: number; size: number;
  hue: number; alpha: number;
}

function spawnParticle(x: number, y: number, opts: Partial<Particle> = {}): Particle {
  return {
    x, y,
    vx: opts.vx ?? (Math.random() - 0.5) * 2,
    vy: opts.vy ?? -Math.random() * 2 - 0.5,
    life: 0,
    maxLife: opts.maxLife ?? 60 + Math.random() * 60,
    size: opts.size ?? 1.5 + Math.random() * 2,
    hue: opts.hue ?? 20,
    alpha: opts.alpha ?? 1,
  };
}

function tickParticles(particles: Particle[], gravity = 0): Particle[] {
  for (const p of particles) {
    p.x += p.vx;
    p.y += p.vy;
    p.vy += gravity;
    p.life++;
    p.alpha = Math.max(0, 1 - p.life / p.maxLife);
  }
  return particles.filter(p => p.life < p.maxLife);
}

// ── Simple 2D value noise ───────────────────────────────
const _noiseP: number[] = [];
for (let i = 0; i < 256; i++) _noiseP.push(i);
for (let i = 255; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [_noiseP[i], _noiseP[j]] = [_noiseP[j], _noiseP[i]]; }
const _nP = [..._noiseP, ..._noiseP];

function fade(t: number) { return t * t * t * (t * (t * 6 - 15) + 10); }
function lerp(a: number, b: number, t: number) { return a + t * (b - a); }
function grad2(hash: number, x: number, y: number) {
  const h = hash & 3;
  const u = h < 2 ? x : y;
  const v = h < 2 ? y : x;
  return ((h & 1) === 0 ? u : -u) + ((h & 2) === 0 ? v : -v);
}
function noise2D(x: number, y: number): number {
  const X = Math.floor(x) & 255, Y = Math.floor(y) & 255;
  const xf = x - Math.floor(x), yf = y - Math.floor(y);
  const u = fade(xf), v = fade(yf);
  const aa = _nP[_nP[X] + Y], ab = _nP[_nP[X] + Y + 1];
  const ba = _nP[_nP[X + 1] + Y], bb = _nP[_nP[X + 1] + Y + 1];
  return lerp(
    lerp(grad2(aa, xf, yf), grad2(ba, xf - 1, yf), u),
    lerp(grad2(ab, xf, yf - 1), grad2(bb, xf - 1, yf - 1), u),
    v
  );
}

// ═══════════════════════════════════════════════════════════
// 30. DEEP SEA — Bioluminescent deep-ocean creature face
// Complexity: geometry 3, effects 4, animation 4 = 11 → Masterwork ($29)
// ═══════════════════════════════════════════════════════════
export class DeepSeaFace extends FaceRenderer {
  private plankton: Particle[] = [];
  private bubbles: Particle[] = [];

  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
    bgGrad.addColorStop(0, "#000810");
    bgGrad.addColorStop(0.5, "#000612");
    bgGrad.addColorStop(1, "#000408");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Drifting bioluminescent plankton
    if (Math.random() < 0.3) {
      this.plankton.push(spawnParticle(
        Math.random() * REF_W,
        REF_H + 10,
        {
          vx: (Math.random() - 0.5) * 0.5,
          vy: -0.3 - Math.random() * 0.5,
          hue: 160 + Math.random() * 60,
          maxLife: 120 + Math.random() * 100,
          size: 0.5 + Math.random() * 1.5,
        }
      ));
    }
    // Bubbles from mouth area
    if (Math.random() < 0.08) {
      this.bubbles.push(spawnParticle(
        cx + (Math.random() - 0.5) * 40,
        240,
        {
          vx: (Math.random() - 0.5) * 0.8,
          vy: -0.8 - Math.random() * 1.2,
          hue: 190,
          maxLife: 80 + Math.random() * 60,
          size: 1 + Math.random() * 3,
        }
      ));
    }

    this.plankton = tickParticles(this.plankton);
    this.bubbles = tickParticles(this.bubbles, -0.005);

    // Draw plankton
    for (const p of this.plankton) {
      const drift = Math.sin(t * 0.5 + p.x * 0.05) * 3;
      ctx.save();
      ctx.shadowColor = `hsl(${p.hue},100%,60%)`;
      ctx.shadowBlur = this._ss(4);
      ctx.fillStyle = `hsla(${p.hue},80%,60%,${p.alpha * 0.6})`;
      ctx.beginPath();
      ctx.arc(this._sx(p.x + drift), this._sy(p.y), this._ss(p.size), 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    // Deep-sea face — translucent jellyfish-like form
    const faceGrad = ctx.createRadialGradient(
      this._sx(cx), this._sy(REF_H / 2), 0,
      this._sx(cx), this._sy(REF_H / 2), this._ss(140)
    );
    const facePulse = 0.06 + 0.02 * Math.sin(t * 0.8);
    faceGrad.addColorStop(0, `rgba(20,60,100,${facePulse * 2})`);
    faceGrad.addColorStop(0.5, `rgba(10,40,80,${facePulse})`);
    faceGrad.addColorStop(1, "transparent");
    ctx.fillStyle = faceGrad;
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(REF_H / 2 + 5), this._ss(115), this._ss(145), 0, 0, Math.PI * 2);
    ctx.fill();

    // Bioluminescent veins — procedural branching
    const veins = [
      { sx: cx - 70, sy: 80, angle: Math.PI * 0.3, hue: 180 },
      { sx: cx + 70, sy: 90, angle: Math.PI * 0.7, hue: 200 },
      { sx: cx - 50, sy: 240, angle: Math.PI * 0.4, hue: 170 },
      { sx: cx + 55, sy: 250, angle: Math.PI * 0.6, hue: 190 },
      { sx: cx - 80, sy: 160, angle: Math.PI * 0.25, hue: 160 },
      { sx: cx + 80, sy: 170, angle: Math.PI * 0.75, hue: 210 },
    ];
    for (const v of veins) {
      const glow = 0.15 + 0.1 * Math.sin(t * 1.5 + v.sx * 0.01);
      ctx.strokeStyle = `hsla(${v.hue},80%,50%,${glow})`;
      ctx.lineWidth = this._ss(1);
      ctx.beginPath();
      let px = v.sx, py = v.sy;
      ctx.moveTo(this._sx(px), this._sy(py));
      for (let i = 0; i < 8; i++) {
        const n = noise2D(px * 0.02 + t * 0.1, py * 0.02);
        const a = v.angle + n * 0.8;
        px += Math.cos(a) * 10;
        py += Math.sin(a) * 10;
        ctx.lineTo(this._sx(px), this._sy(py));
      }
      ctx.stroke();
      // Glow
      ctx.save();
      ctx.shadowColor = `hsl(${v.hue},100%,60%)`;
      ctx.shadowBlur = this._ss(5);
      ctx.strokeStyle = `hsla(${v.hue},80%,60%,${glow * 0.5})`;
      ctx.stroke();
      ctx.restore();
    }

    // Bioluminescent edge outline
    ctx.save();
    const edgePulse = 0.1 + 0.05 * Math.sin(t * 0.6);
    ctx.shadowColor = "#00aaff";
    ctx.shadowBlur = this._ss(8);
    ctx.strokeStyle = `rgba(0,150,255,${edgePulse})`;
    ctx.lineWidth = this._ss(1.5);
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(REF_H / 2 + 5), this._ss(115), this._ss(145), 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();

    // Eyes — large anglerfish-like glowing orbs
    const eyeSpacing = 50, eyeY = 135;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 10;
      const py = eyeY + es.gazeY * 7;
      const eyeHue = side < 0 ? 170 : 200;

      // Outer glow halo
      const halo = ctx.createRadialGradient(
        this._sx(ex), this._sy(eyeY), 0,
        this._sx(ex), this._sy(eyeY), this._ss(30)
      );
      const haloAlpha = 0.06 + 0.04 * Math.sin(t * 1.2 + side);
      halo.addColorStop(0, `hsla(${eyeHue},80%,50%,${haloAlpha})`);
      halo.addColorStop(1, "transparent");
      ctx.fillStyle = halo;
      ctx.beginPath();
      ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(30), 0, Math.PI * 2);
      ctx.fill();

      if (blink < 0.15) {
        ctx.save();
        ctx.shadowColor = `hsl(${eyeHue},100%,60%)`;
        ctx.shadowBlur = this._ss(6);
        ctx.strokeStyle = `hsla(${eyeHue},80%,60%,0.5)`;
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 18), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 18), this._sy(eyeY));
        ctx.stroke();
        ctx.restore();
      } else {
        const eyeH = 18 * blink;
        // Dark socket
        ctx.fillStyle = "#000408";
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(20), this._ss(eyeH), 0, 0, Math.PI * 2);
        ctx.fill();

        // Bioluminescent iris rings
        for (let ring = 0; ring < 3; ring++) {
          const ringR = (6 + ring * 3) * em.pupil_size;
          const ringAlpha = 0.3 - ring * 0.08;
          const ringHue = eyeHue + ring * 15;
          ctx.strokeStyle = `hsla(${ringHue},80%,55%,${ringAlpha + 0.1 * Math.sin(t * 2 + ring)})`;
          ctx.lineWidth = this._ss(0.8);
          ctx.beginPath();
          ctx.arc(this._sx(px), this._sy(py), this._ss(ringR), 0, Math.PI * 2);
          ctx.stroke();
        }

        // Bright core
        ctx.save();
        ctx.shadowColor = `hsl(${eyeHue},100%,70%)`;
        ctx.shadowBlur = this._ss(15);
        ctx.fillStyle = `hsl(${eyeHue},80%,75%)`;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(4 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(this._sx(px - 1.5), this._sy(py - 1.5), this._ss(1.8), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Anglerfish lure — small light above the face
    const lureX = cx + Math.sin(t * 0.4) * 10;
    const lureY = 30 + Math.cos(t * 0.3) * 5;
    ctx.strokeStyle = "rgba(0,150,255,0.15)";
    ctx.lineWidth = this._ss(0.8);
    ctx.beginPath();
    ctx.moveTo(this._sx(cx), this._sy(50));
    ctx.quadraticCurveTo(this._sx(lureX - 5), this._sy(40), this._sx(lureX), this._sy(lureY));
    ctx.stroke();
    ctx.save();
    ctx.shadowColor = "#00ccff";
    ctx.shadowBlur = this._ss(10);
    ctx.fillStyle = `rgba(100,200,255,${0.4 + 0.3 * Math.sin(t * 3)})`;
    ctx.beginPath();
    ctx.arc(this._sx(lureX), this._sy(lureY), this._ss(3), 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // Mouth — bioluminescent band
    const ms = this.mouth, mouthY = 258;
    const mouthW = 30 * ms.widthFactor;
    for (let pass = 0; pass < 3; pass++) {
      const hue = 170 + pass * 20;
      const alpha = 0.25 - pass * 0.05;
      ctx.strokeStyle = `hsla(${hue},60%,55%,${alpha + ms.openAmount * 0.15})`;
      ctx.lineWidth = this._ss(1.5 - pass * 0.3);
      ctx.beginPath();
      for (let i = 0; i <= 25; i++) {
        const frac = i / 25;
        const x = cx - mouthW + frac * mouthW * 2;
        const wave = ms.openAmount > 0.05 ? Math.sin(frac * Math.PI * 2 + t * 2 + pass) * ms.openAmount * 6 : 0;
        const curve = Math.sin(frac * Math.PI) * (2 + em.mouth_curve * 6);
        const y = mouthY - curve + wave + pass * 2;
        if (i === 0) ctx.moveTo(this._sx(x), this._sy(y));
        else ctx.lineTo(this._sx(x), this._sy(y));
      }
      ctx.stroke();
    }

    // Bubbles on top
    for (const b of this.bubbles) {
      const drift = Math.sin(t * 0.8 + b.x * 0.1) * 2;
      ctx.strokeStyle = `rgba(100,180,255,${b.alpha * 0.3})`;
      ctx.lineWidth = this._ss(0.5);
      ctx.beginPath();
      ctx.arc(this._sx(b.x + drift), this._sy(b.y), this._ss(b.size), 0, Math.PI * 2);
      ctx.stroke();
      // Highlight
      ctx.fillStyle = `rgba(180,220,255,${b.alpha * 0.15})`;
      ctx.beginPath();
      ctx.arc(this._sx(b.x + drift - b.size * 0.3), this._sy(b.y - b.size * 0.3), this._ss(b.size * 0.3), 0, Math.PI * 2);
      ctx.fill();
    }

    // Caustic light overlay
    ctx.fillStyle = `rgba(0,100,200,${0.01 + 0.005 * Math.sin(t * 0.5)})`;
    for (let i = 0; i < 8; i++) {
      const cx2 = REF_W * 0.5 + Math.sin(t * 0.2 + i * 0.8) * 100;
      const cy2 = REF_H * 0.5 + Math.cos(t * 0.3 + i * 1.1) * 80;
      ctx.beginPath();
      ctx.arc(this._sx(cx2), this._sy(cy2), this._ss(40 + Math.sin(t + i) * 15), 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 31. SYNTHWAVE — Full retrowave world: sunset, grid, chrome face
// Complexity: geometry 4, effects 4, animation 4 = 12 → Legendary ($39)
// ═══════════════════════════════════════════════════════════
export class SynthwaveFace extends FaceRenderer {
  private stars: { x: number; y: number; s: number; b: number }[] = [];
  private initStars = false;

  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // ── Sky gradient ──
    const skyGrad = ctx.createLinearGradient(0, 0, 0, this._sy(200));
    skyGrad.addColorStop(0, "#0a001a");
    skyGrad.addColorStop(0.3, "#1a0040");
    skyGrad.addColorStop(0.55, "#4a0060");
    skyGrad.addColorStop(0.75, "#cc2060");
    skyGrad.addColorStop(0.9, "#ff6040");
    skyGrad.addColorStop(1, "#ffaa40");
    ctx.fillStyle = skyGrad;
    ctx.fillRect(0, 0, w, this._sy(200));

    // Below horizon — dark grid area
    ctx.fillStyle = "#0a000e";
    ctx.fillRect(0, this._sy(200), w, h - this._sy(200));

    // ── Stars ──
    if (!this.initStars) {
      this.initStars = true;
      for (let i = 0; i < 40; i++) {
        this.stars.push({
          x: Math.random() * REF_W,
          y: Math.random() * 150,
          s: 0.3 + Math.random() * 1,
          b: Math.random() * Math.PI * 2,
        });
      }
    }
    for (const star of this.stars) {
      const twinkle = 0.3 + 0.7 * Math.abs(Math.sin(t * 1.5 + star.b));
      ctx.fillStyle = `rgba(255,220,255,${twinkle * 0.6})`;
      ctx.beginPath();
      ctx.arc(this._sx(star.x), this._sy(star.y), this._ss(star.s), 0, Math.PI * 2);
      ctx.fill();
    }

    // ── Sun (behind face) ──
    const sunY = 160;
    const sunR = 50;
    // Sun body — striped
    for (let i = 0; i < 10; i++) {
      const stripeY = sunY - sunR + i * (sunR * 2 / 10);
      const stripeH = sunR * 2 / 10;
      const r = Math.sqrt(Math.max(0, sunR * sunR - (stripeY - sunY) * (stripeY - sunY)));
      if (i % 2 === 0) {
        const sGrad = ctx.createLinearGradient(0, this._sy(stripeY), 0, this._sy(stripeY + stripeH));
        sGrad.addColorStop(0, "#ff6080");
        sGrad.addColorStop(1, "#ffaa60");
        ctx.fillStyle = sGrad;
      } else {
        ctx.fillStyle = "transparent";
        continue;
      }
      ctx.save();
      ctx.beginPath();
      ctx.arc(this._sx(cx), this._sy(sunY), this._ss(sunR), 0, Math.PI * 2);
      ctx.clip();
      ctx.fillRect(this._sx(cx - r), this._sy(stripeY), this._ss(r * 2), this._ss(stripeH));
      ctx.restore();
    }
    // Sun glow
    const sunGlow = ctx.createRadialGradient(
      this._sx(cx), this._sy(sunY), this._ss(sunR),
      this._sx(cx), this._sy(sunY), this._ss(sunR + 40)
    );
    sunGlow.addColorStop(0, "rgba(255,100,80,0.3)");
    sunGlow.addColorStop(0.5, "rgba(255,60,100,0.1)");
    sunGlow.addColorStop(1, "transparent");
    ctx.fillStyle = sunGlow;
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(sunY), this._ss(sunR + 40), 0, Math.PI * 2);
    ctx.fill();

    // ── Perspective Grid ──
    const horizonY = 200;
    const gridBottom = REF_H;
    // Vertical grid lines
    ctx.strokeStyle = "rgba(255,0,100,0.2)";
    ctx.lineWidth = this._ss(0.8);
    const gridCols = 16;
    for (let i = -gridCols / 2; i <= gridCols / 2; i++) {
      const topX = cx + i * 3;
      const bottomX = cx + i * (w / (gridCols * 0.4));
      ctx.beginPath();
      ctx.moveTo(this._sx(topX), this._sy(horizonY));
      ctx.lineTo(this._sx(bottomX), this._sy(gridBottom));
      ctx.stroke();
    }
    // Horizontal grid lines — perspective spacing
    for (let i = 1; i <= 12; i++) {
      const frac = i / 12;
      const gy = horizonY + frac * frac * (gridBottom - horizonY);
      const scrollOffset = (t * 20 * frac) % ((gridBottom - horizonY) / 12 * frac * 2);
      const finalY = gy + scrollOffset;
      if (finalY > gridBottom) continue;
      ctx.strokeStyle = `rgba(255,0,100,${0.15 * (1 - frac * 0.5)})`;
      ctx.beginPath();
      ctx.moveTo(0, this._sy(finalY));
      ctx.lineTo(w, this._sy(finalY));
      ctx.stroke();
    }

    // ── Chrome face (foreground) ──
    // Face shape
    const faceGrad = ctx.createLinearGradient(this._sx(cx - 80), 0, this._sx(cx + 80), 0);
    faceGrad.addColorStop(0, "#1a0030");
    faceGrad.addColorStop(0.3, "#2a0050");
    faceGrad.addColorStop(0.5, "#3a0070");
    faceGrad.addColorStop(0.7, "#2a0050");
    faceGrad.addColorStop(1, "#1a0030");
    ctx.fillStyle = faceGrad;
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(REF_H / 2 + 10), this._ss(90), this._ss(120), 0, 0, Math.PI * 2);
    ctx.fill();

    // Neon face outline
    ctx.save();
    ctx.shadowColor = "#ff00aa";
    ctx.shadowBlur = this._ss(10);
    const neonPulse = 0.5 + 0.5 * Math.sin(t * 2);
    ctx.strokeStyle = `rgba(255,0,170,${0.4 + neonPulse * 0.3})`;
    ctx.lineWidth = this._ss(2);
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(REF_H / 2 + 10), this._ss(90), this._ss(120), 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();

    // Chrome reflection band across face
    const refBand = ctx.createLinearGradient(0, this._sy(130), 0, this._sy(160));
    refBand.addColorStop(0, "transparent");
    refBand.addColorStop(0.3, "rgba(255,100,200,0.08)");
    refBand.addColorStop(0.5, "rgba(255,150,220,0.12)");
    refBand.addColorStop(0.7, "rgba(255,100,200,0.08)");
    refBand.addColorStop(1, "transparent");
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(REF_H / 2 + 10), this._ss(89), this._ss(119), 0, 0, Math.PI * 2);
    ctx.clip();
    ctx.fillStyle = refBand;
    ctx.fillRect(0, this._sy(130), w, this._ss(30));
    ctx.restore();

    // ── Eyes — neon triangle shapes ──
    const eyeSpacing = 38, eyeY = 150;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 5;

      if (blink < 0.15) {
        ctx.save();
        ctx.shadowColor = "#00ffff";
        ctx.shadowBlur = this._ss(6);
        ctx.strokeStyle = "rgba(0,255,255,0.6)";
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 14), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 14), this._sy(eyeY));
        ctx.stroke();
        ctx.restore();
      } else {
        const eyeH = 14 * blink;
        // Neon eye triangle
        ctx.save();
        ctx.shadowColor = "#00ffff";
        ctx.shadowBlur = this._ss(8);
        ctx.strokeStyle = "rgba(0,255,255,0.6)";
        ctx.lineWidth = this._ss(1.5);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 18), this._sy(eyeY + eyeH * 0.4));
        ctx.lineTo(this._sx(ex), this._sy(eyeY - eyeH));
        ctx.lineTo(this._sx(ex + 18), this._sy(eyeY + eyeH * 0.4));
        ctx.closePath();
        ctx.stroke();

        // Fill dark
        ctx.fillStyle = "rgba(0,0,10,0.7)";
        ctx.fill();
        ctx.restore();

        // Pupil — hot pink glow
        ctx.save();
        ctx.shadowColor = "#ff00ff";
        ctx.shadowBlur = this._ss(12);
        ctx.fillStyle = "#ff44ff";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(3.5 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(this._sx(px - 1), this._sy(py - 1), this._ss(1.2), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // ── Mouth — neon equalizer bars ──
    const ms = this.mouth, mouthY = 260;
    const mouthW = 28 * ms.widthFactor;
    const bars = 10;
    for (let i = 0; i < bars; i++) {
      const bx = cx - mouthW + i * (mouthW * 2 / bars);
      const barW = (mouthW * 2 / bars) - 1.5;
      const barPhase = Math.sin(t * 4 + i * 0.6);
      const barH = ms.openAmount > 0.05
        ? 3 + ms.openAmount * 10 * Math.abs(barPhase)
        : 2 + Math.abs(barPhase) * 1;
      const hue = 300 - i * 12;

      ctx.save();
      ctx.shadowColor = `hsl(${hue},100%,60%)`;
      ctx.shadowBlur = this._ss(4);
      ctx.fillStyle = `hsla(${hue},100%,55%,0.7)`;
      ctx.fillRect(this._sx(bx), this._sy(mouthY - barH / 2), this._ss(barW), this._ss(barH));
      ctx.restore();
    }

    // ── Decorative neon lines ──
    // Cheek accents
    for (const side of [-1, 1]) {
      ctx.save();
      ctx.shadowColor = "#ff0066";
      ctx.shadowBlur = this._ss(4);
      ctx.strokeStyle = "rgba(255,0,100,0.2)";
      ctx.lineWidth = this._ss(1);
      ctx.beginPath();
      ctx.moveTo(this._sx(cx + side * 55), this._sy(190));
      ctx.lineTo(this._sx(cx + side * 75), this._sy(200));
      ctx.lineTo(this._sx(cx + side * 70), this._sy(215));
      ctx.stroke();
      ctx.restore();
    }

    // Horizontal glow line at horizon
    ctx.save();
    ctx.shadowColor = "#ff6600";
    ctx.shadowBlur = this._ss(6);
    ctx.strokeStyle = "rgba(255,100,50,0.3)";
    ctx.lineWidth = this._ss(1);
    ctx.beginPath();
    ctx.moveTo(0, this._sy(horizonY));
    ctx.lineTo(w, this._sy(horizonY));
    ctx.stroke();
    ctx.restore();

    // Scanlines over everything
    ctx.fillStyle = "rgba(0,0,0,0.06)";
    for (let y = 0; y < h; y += 3) {
      ctx.fillRect(0, y, w, 1);
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 32. ETHEREAL — Transcendent light being with sacred geometry
// Complexity: geometry 4, effects 4, animation 4 = 12 → Legendary ($39)
// ═══════════════════════════════════════════════════════════
export class EtherealFace extends FaceRenderer {
  private motes: Particle[] = [];

  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    const bgGrad = ctx.createRadialGradient(
      this._sx(REF_W / 2), this._sy(REF_H / 2), 0,
      this._sx(REF_W / 2), this._sy(REF_H / 2), this._ss(250)
    );
    bgGrad.addColorStop(0, "#080410");
    bgGrad.addColorStop(1, "#020108");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, cy = REF_H / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Spawn light motes
    if (Math.random() < 0.3) {
      const angle = Math.random() * Math.PI * 2;
      const dist = 100 + Math.random() * 80;
      this.motes.push(spawnParticle(
        cx + Math.cos(angle) * dist,
        cy + Math.sin(angle) * dist,
        {
          vx: -Math.cos(angle) * 0.3,
          vy: -Math.sin(angle) * 0.3,
          hue: 40 + Math.random() * 30,
          maxLife: 100 + Math.random() * 80,
          size: 0.5 + Math.random() * 1.5,
        }
      ));
    }
    this.motes = tickParticles(this.motes);

    // Draw motes (behind geometry)
    for (const m of this.motes) {
      ctx.save();
      ctx.shadowColor = `hsl(${m.hue},60%,70%)`;
      ctx.shadowBlur = this._ss(5);
      ctx.fillStyle = `hsla(${m.hue},60%,70%,${m.alpha * 0.5})`;
      ctx.beginPath();
      ctx.arc(this._sx(m.x), this._sy(m.y), this._ss(m.size), 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    // ── Sacred geometry — rotating nested shapes ──
    // Outer hexagon
    ctx.save();
    ctx.globalAlpha = 0.08 + 0.04 * Math.sin(t * 0.3);
    ctx.strokeStyle = "#eedd88";
    ctx.lineWidth = this._ss(0.6);
    const hexR = 150;
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 3) * i + t * 0.05;
      const hx = cx + Math.cos(a) * hexR;
      const hy = cy + Math.sin(a) * hexR;
      if (i === 0) ctx.moveTo(this._sx(hx), this._sy(hy));
      else ctx.lineTo(this._sx(hx), this._sy(hy));
    }
    ctx.closePath();
    ctx.stroke();

    // Inner circle
    ctx.strokeStyle = "#eedd88";
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(cy), this._ss(105), 0, Math.PI * 2);
    ctx.stroke();

    // Flower of life pattern — overlapping circles
    const flowerR = 40;
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 3) * i - t * 0.08;
      const fx = cx + Math.cos(a) * flowerR;
      const fy = cy + Math.sin(a) * flowerR;
      ctx.beginPath();
      ctx.arc(this._sx(fx), this._sy(fy), this._ss(flowerR), 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(cy), this._ss(flowerR), 0, Math.PI * 2);
    ctx.stroke();

    // Inner triangle
    ctx.strokeStyle = "#ffcc44";
    ctx.lineWidth = this._ss(0.8);
    ctx.beginPath();
    for (let i = 0; i < 3; i++) {
      const a = (Math.PI * 2 / 3) * i + t * 0.1 - Math.PI / 2;
      const tx = cx + Math.cos(a) * 80;
      const ty = cy + Math.sin(a) * 80;
      if (i === 0) ctx.moveTo(this._sx(tx), this._sy(ty));
      else ctx.lineTo(this._sx(tx), this._sy(ty));
    }
    ctx.closePath();
    ctx.stroke();

    ctx.globalAlpha = 1;
    ctx.restore();

    // ── Radiant face — pure light ──
    const faceGlow = ctx.createRadialGradient(
      this._sx(cx), this._sy(cy + 5), 0,
      this._sx(cx), this._sy(cy + 5), this._ss(100)
    );
    const breathe = 0.1 + 0.03 * Math.sin(t * 0.5);
    faceGlow.addColorStop(0, `rgba(255,240,200,${breathe})`);
    faceGlow.addColorStop(0.4, `rgba(255,220,150,${breathe * 0.5})`);
    faceGlow.addColorStop(0.7, `rgba(200,180,100,${breathe * 0.2})`);
    faceGlow.addColorStop(1, "transparent");
    ctx.fillStyle = faceGlow;
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(cy + 5), this._ss(100), 0, Math.PI * 2);
    ctx.fill();

    // Light-beam crown
    for (let i = 0; i < 7; i++) {
      const a = Math.PI + (Math.PI / 8) * (i - 3);
      const beamLen = 50 + 20 * Math.sin(t * 1.5 + i);
      const beamAlpha = 0.04 + 0.03 * Math.sin(t * 2 + i * 0.7);
      ctx.strokeStyle = `rgba(255,240,180,${beamAlpha})`;
      ctx.lineWidth = this._ss(3 + Math.sin(t + i) * 1);
      ctx.beginPath();
      ctx.moveTo(this._sx(cx + Math.cos(a) * 60), this._sy(cy + 5 + Math.sin(a) * 75));
      ctx.lineTo(this._sx(cx + Math.cos(a) * (60 + beamLen)), this._sy(cy + 5 + Math.sin(a) * (75 + beamLen)));
      ctx.stroke();
    }

    // ── Eyes — pure light orbs ──
    const eyeSpacing = 40, eyeY = cy - 20;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 5;

      if (blink < 0.15) {
        ctx.save();
        ctx.shadowColor = "#ffdd88";
        ctx.shadowBlur = this._ss(8);
        ctx.strokeStyle = "rgba(255,230,160,0.4)";
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 16), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 16), this._sy(eyeY));
        ctx.stroke();
        ctx.restore();
      } else {
        const eyeR = 14 * blink;
        // Soft glow halo
        const eyeGlow = ctx.createRadialGradient(
          this._sx(ex), this._sy(eyeY), 0,
          this._sx(ex), this._sy(eyeY), this._ss(eyeR + 15)
        );
        eyeGlow.addColorStop(0, "rgba(255,240,180,0.1)");
        eyeGlow.addColorStop(1, "transparent");
        ctx.fillStyle = eyeGlow;
        ctx.beginPath();
        ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(eyeR + 15), 0, Math.PI * 2);
        ctx.fill();

        // Eye shape — gentle almond
        ctx.strokeStyle = "rgba(255,230,160,0.25)";
        ctx.lineWidth = this._ss(1);
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(16), this._ss(eyeR), 0, 0, Math.PI * 2);
        ctx.stroke();

        // Iris — golden light rings
        for (let ring = 0; ring < 3; ring++) {
          const rr = (4 + ring * 2.5) * em.pupil_size;
          const alpha = 0.2 - ring * 0.05;
          ctx.strokeStyle = `rgba(255,${200 + ring * 20},${100 + ring * 30},${alpha + 0.05 * Math.sin(t * 2 + ring)})`;
          ctx.lineWidth = this._ss(0.6);
          ctx.beginPath();
          ctx.arc(this._sx(px), this._sy(py), this._ss(rr), 0, Math.PI * 2);
          ctx.stroke();
        }

        // Core
        ctx.save();
        ctx.shadowColor = "#ffe888";
        ctx.shadowBlur = this._ss(15);
        ctx.fillStyle = "#fffae0";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(3 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
    }

    // Third eye — forehead chakra
    const thirdEyeY = eyeY - 40;
    const tePulse = 0.15 + 0.1 * Math.sin(t * 1.2);
    const teGlow = ctx.createRadialGradient(
      this._sx(cx), this._sy(thirdEyeY), 0,
      this._sx(cx), this._sy(thirdEyeY), this._ss(12)
    );
    teGlow.addColorStop(0, `rgba(200,150,255,${tePulse})`);
    teGlow.addColorStop(1, "transparent");
    ctx.fillStyle = teGlow;
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(thirdEyeY), this._ss(12), 0, Math.PI * 2);
    ctx.fill();
    ctx.save();
    ctx.shadowColor = "#cc88ff";
    ctx.shadowBlur = this._ss(8);
    ctx.fillStyle = `rgba(200,150,255,${tePulse * 2})`;
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(thirdEyeY), this._ss(3), 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // Mouth — soft light curve
    const ms = this.mouth, mouthY = cy + 65;
    const mouthW = 25 * ms.widthFactor;
    ctx.strokeStyle = `rgba(255,230,160,${0.15 + ms.openAmount * 0.2})`;
    ctx.lineWidth = this._ss(1.5);
    if (ms.openAmount < 0.05) {
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY - em.mouth_curve * 8), this._sx(cx + mouthW), this._sy(mouthY));
      ctx.stroke();
    } else {
      const openH = ms.openAmount * 12;
      // Light emanating from mouth
      const mGlow = ctx.createRadialGradient(
        this._sx(cx), this._sy(mouthY), 0,
        this._sx(cx), this._sy(mouthY), this._ss(Math.max(mouthW, openH) + 8)
      );
      mGlow.addColorStop(0, `rgba(255,240,180,${0.08 + ms.openAmount * 0.1})`);
      mGlow.addColorStop(1, "transparent");
      ctx.fillStyle = mGlow;
      ctx.beginPath();
      ctx.arc(this._sx(cx), this._sy(mouthY), this._ss(Math.max(mouthW, openH) + 8), 0, Math.PI * 2);
      ctx.fill();

      ctx.beginPath();
      ctx.ellipse(this._sx(cx), this._sy(mouthY), this._ss(mouthW), this._ss(openH), 0, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
}
