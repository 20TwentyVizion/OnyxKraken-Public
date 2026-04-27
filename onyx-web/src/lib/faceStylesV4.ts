/**
 * AgentFace V4 Styles — Masterwork & Legendary tier faces (27-31).
 *
 * These push Canvas 2D to its limits with:
 *   - Off-screen canvas compositing (multi-pass)
 *   - Particle systems with physics (gravity, drift, fade)
 *   - Procedural noise textures generated per-frame
 *   - Complex state machines driving animation
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
// 27. PHOENIX — Fire & ember face with particle flames
// Complexity: geometry 3, effects 4, animation 3 = 10 → Masterwork ($29)
// ═══════════════════════════════════════════════════════════
export class PhoenixFace extends FaceRenderer {
  private particles: Particle[] = [];
  private embers: Particle[] = [];

  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
    bgGrad.addColorStop(0, "#0a0204");
    bgGrad.addColorStop(1, "#050102");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Spawn flame particles rising from face edges
    if (Math.random() < 0.4) {
      const sx = cx + (Math.random() - 0.5) * 160;
      this.particles.push(spawnParticle(sx, 300 + Math.random() * 30, {
        vx: (Math.random() - 0.5) * 1.5,
        vy: -1.5 - Math.random() * 2,
        hue: 10 + Math.random() * 30,
        maxLife: 50 + Math.random() * 40,
        size: 2 + Math.random() * 3,
      }));
    }
    // Ember sparks
    if (Math.random() < 0.15) {
      this.embers.push(spawnParticle(cx + (Math.random() - 0.5) * 120, 250 + Math.random() * 50, {
        vx: (Math.random() - 0.5) * 3,
        vy: -2 - Math.random() * 3,
        hue: 30 + Math.random() * 20,
        maxLife: 30 + Math.random() * 30,
        size: 0.8 + Math.random() * 1.5,
      }));
    }

    this.particles = tickParticles(this.particles, -0.02);
    this.embers = tickParticles(this.embers, -0.01);

    // Draw flame particles (behind face)
    for (const p of this.particles) {
      const grad = ctx.createRadialGradient(
        this._sx(p.x), this._sy(p.y), 0,
        this._sx(p.x), this._sy(p.y), this._ss(p.size * 2)
      );
      grad.addColorStop(0, `hsla(${p.hue},100%,60%,${p.alpha * 0.4})`);
      grad.addColorStop(0.5, `hsla(${p.hue - 10},90%,40%,${p.alpha * 0.2})`);
      grad.addColorStop(1, "transparent");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(this._sx(p.x), this._sy(p.y), this._ss(p.size * 2), 0, Math.PI * 2);
      ctx.fill();
    }

    // Magma-cracked face plate
    const faceGrad = ctx.createRadialGradient(
      this._sx(cx), this._sy(REF_H / 2), 0,
      this._sx(cx), this._sy(REF_H / 2), this._ss(140)
    );
    faceGrad.addColorStop(0, "rgba(40,10,5,0.85)");
    faceGrad.addColorStop(0.6, "rgba(25,5,2,0.7)");
    faceGrad.addColorStop(1, "transparent");
    ctx.fillStyle = faceGrad;
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(REF_H / 2 + 5), this._ss(115), this._ss(145), 0, 0, Math.PI * 2);
    ctx.fill();

    // Magma cracks — procedural noise-based glowing lines
    ctx.strokeStyle = "rgba(255,80,20,0.3)";
    ctx.lineWidth = this._ss(1.2);
    const crackSeeds = [
      { sx: cx - 60, sy: 80, len: 8 },
      { sx: cx + 40, sy: 100, len: 7 },
      { sx: cx - 30, sy: 200, len: 6 },
      { sx: cx + 50, sy: 220, len: 5 },
      { sx: cx - 10, sy: 280, len: 7 },
    ];
    for (const seed of crackSeeds) {
      ctx.beginPath();
      let px = seed.sx, py = seed.sy;
      ctx.moveTo(this._sx(px), this._sy(py));
      for (let i = 0; i < seed.len; i++) {
        const n = noise2D(px * 0.02 + t * 0.2, py * 0.02);
        px += Math.cos(n * Math.PI * 2) * 12;
        py += Math.sin(n * Math.PI * 2) * 12 + 5;
        ctx.lineTo(this._sx(px), this._sy(py));
      }
      const glow = 0.2 + 0.15 * Math.sin(t * 3 + seed.sx);
      ctx.strokeStyle = `rgba(255,80,20,${glow})`;
      ctx.stroke();
      // Glow along crack
      ctx.save();
      ctx.shadowColor = "#ff4400";
      ctx.shadowBlur = this._ss(6);
      ctx.strokeStyle = `rgba(255,120,40,${glow * 0.5})`;
      ctx.stroke();
      ctx.restore();
    }

    // Eyes — molten orbs
    const eyeSpacing = 48, eyeY = 135;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 6;

      // Outer heat halo
      const halo = ctx.createRadialGradient(
        this._sx(ex), this._sy(eyeY), this._ss(5),
        this._sx(ex), this._sy(eyeY), this._ss(28)
      );
      halo.addColorStop(0, "rgba(255,60,10,0.2)");
      halo.addColorStop(1, "transparent");
      ctx.fillStyle = halo;
      ctx.beginPath();
      ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(28), 0, Math.PI * 2);
      ctx.fill();

      if (blink < 0.15) {
        ctx.save();
        ctx.shadowColor = "#ff4400";
        ctx.shadowBlur = this._ss(8);
        ctx.strokeStyle = "#ff6620";
        ctx.lineWidth = this._ss(2.5);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 16), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 16), this._sy(eyeY));
        ctx.stroke();
        ctx.restore();
      } else {
        const eyeH = 15 * blink;
        // Dark socket
        ctx.fillStyle = "#0a0202";
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(18), this._ss(eyeH), 0, 0, Math.PI * 2);
        ctx.fill();

        // Molten iris ring
        ctx.save();
        ctx.shadowColor = "#ff6600";
        ctx.shadowBlur = this._ss(12);
        const irisGrad = ctx.createRadialGradient(
          this._sx(px), this._sy(py), this._ss(2),
          this._sx(px), this._sy(py), this._ss(10 * em.pupil_size)
        );
        const flicker = 0.8 + 0.2 * Math.sin(t * 6 + side * 4);
        irisGrad.addColorStop(0, `rgba(255,200,50,${flicker})`);
        irisGrad.addColorStop(0.4, `rgba(255,100,20,${flicker * 0.8})`);
        irisGrad.addColorStop(0.7, `rgba(200,40,10,${flicker * 0.5})`);
        irisGrad.addColorStop(1, "transparent");
        ctx.fillStyle = irisGrad;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(10 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        // Bright core
        ctx.fillStyle = "#ffe880";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(2.5), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Mouth — magma rift
    const ms = this.mouth, mouthY = 248;
    const mouthW = 30 * ms.widthFactor;
    const openH = Math.max(3, ms.openAmount * 16 + 3);
    ctx.save();
    ctx.shadowColor = "#ff4400";
    ctx.shadowBlur = this._ss(10);
    const mGrad = ctx.createLinearGradient(
      this._sx(cx - mouthW), this._sy(mouthY),
      this._sx(cx + mouthW), this._sy(mouthY)
    );
    const mFlicker = 0.6 + 0.4 * Math.sin(t * 4);
    mGrad.addColorStop(0, `rgba(200,40,10,${mFlicker * 0.3})`);
    mGrad.addColorStop(0.3, `rgba(255,100,20,${mFlicker * 0.6})`);
    mGrad.addColorStop(0.5, `rgba(255,200,50,${mFlicker * 0.8})`);
    mGrad.addColorStop(0.7, `rgba(255,100,20,${mFlicker * 0.6})`);
    mGrad.addColorStop(1, `rgba(200,40,10,${mFlicker * 0.3})`);
    ctx.fillStyle = mGrad;
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(mouthY), this._ss(mouthW), this._ss(openH), 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // Ember particles (on top)
    for (const p of this.embers) {
      ctx.save();
      ctx.shadowColor = `hsl(${p.hue},100%,60%)`;
      ctx.shadowBlur = this._ss(4);
      ctx.fillStyle = `hsla(${p.hue},100%,70%,${p.alpha})`;
      ctx.beginPath();
      ctx.arc(this._sx(p.x), this._sy(p.y), this._ss(p.size), 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    // Heat shimmer overlay — subtle noise distortion
    ctx.fillStyle = `rgba(255,60,10,${0.01 + 0.01 * Math.sin(t * 2)})`;
    for (let y = 0; y < h; y += 6) {
      const offset = Math.sin(y * 0.05 + t * 3) * 2;
      ctx.fillRect(offset, y, w, 1);
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 28. LIQUID CHROME — Metallic morphing face with reflections
// Complexity: geometry 4, effects 3, animation 3 = 10 → Masterwork ($29)
// ═══════════════════════════════════════════════════════════
export class ChromeFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#060608";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, cy = REF_H / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Chrome face mesh — procedural noise-warped grid
    const gridCols = 20, gridRows = 24;
    const cellW = 230 / gridCols, cellH = 290 / gridRows;
    const startX = cx - 115, startY = 35;

    for (let row = 0; row < gridRows; row++) {
      for (let col = 0; col < gridCols; col++) {
        const bx = startX + col * cellW;
        const by = startY + row * cellH;
        const bcx = bx + cellW / 2;
        const bcy = by + cellH / 2;

        // Check if inside face ellipse
        const dx = (bcx - cx) / 115;
        const dy = (bcy - (cy + 5)) / 145;
        if (dx * dx + dy * dy > 1) continue;

        // Noise-based warping
        const n = noise2D(bcx * 0.015 + t * 0.3, bcy * 0.015 + t * 0.2);
        const wx = bcx + n * 3;
        const wy = bcy + noise2D(bcx * 0.015 + 100, bcy * 0.015 + t * 0.25) * 3;

        // Chrome lighting — based on surface normal approximation
        const nx2 = noise2D(wx * 0.02 + t * 0.4, wy * 0.02);
        const ny2 = noise2D(wx * 0.02, wy * 0.02 + t * 0.4);
        const lightAngle = Math.atan2(ny2, nx2);
        const lightIntensity = 0.3 + 0.7 * Math.abs(Math.sin(lightAngle + t * 0.5));

        // Chrome color — blue-silver gradient
        const r = Math.round(140 + lightIntensity * 115);
        const g = Math.round(145 + lightIntensity * 110);
        const b2 = Math.round(160 + lightIntensity * 95);

        ctx.fillStyle = `rgb(${r},${g},${b2})`;
        ctx.fillRect(this._sx(wx - cellW / 2), this._sy(wy - cellH / 2), this._ss(cellW + 0.5), this._ss(cellH + 0.5));
      }
    }

    // Chrome edge highlight
    ctx.strokeStyle = "rgba(200,210,230,0.3)";
    ctx.lineWidth = this._ss(1.5);
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(cy + 5), this._ss(115), this._ss(145), 0, 0, Math.PI * 2);
    ctx.stroke();

    // Specular highlights — bright spots that move
    const specs = [
      { x: cx - 30 + Math.sin(t * 0.7) * 15, y: 90 + Math.cos(t * 0.5) * 10, r: 25 },
      { x: cx + 40 + Math.cos(t * 0.6) * 10, y: 130 + Math.sin(t * 0.8) * 8, r: 18 },
      { x: cx + Math.sin(t * 0.4) * 20, y: 260 + Math.cos(t * 0.7) * 5, r: 20 },
    ];
    for (const sp of specs) {
      const sGrad = ctx.createRadialGradient(
        this._sx(sp.x), this._sy(sp.y), 0,
        this._sx(sp.x), this._sy(sp.y), this._ss(sp.r)
      );
      sGrad.addColorStop(0, "rgba(255,255,255,0.25)");
      sGrad.addColorStop(0.3, "rgba(220,225,240,0.1)");
      sGrad.addColorStop(1, "transparent");
      ctx.fillStyle = sGrad;
      ctx.beginPath();
      ctx.arc(this._sx(sp.x), this._sy(sp.y), this._ss(sp.r), 0, Math.PI * 2);
      ctx.fill();
    }

    // Eyes — dark recessed sockets with bright pupils
    const eyeSpacing = 46, eyeY = 138;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 6;

      // Dark recess
      ctx.fillStyle = "rgba(10,10,15,0.9)";
      ctx.beginPath();
      ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(18), this._ss(14), 0, 0, Math.PI * 2);
      ctx.fill();

      if (blink < 0.15) {
        // Chrome lid closes
        const lidGrad = ctx.createLinearGradient(
          this._sx(ex - 18), this._sy(eyeY),
          this._sx(ex + 18), this._sy(eyeY)
        );
        lidGrad.addColorStop(0, "#888");
        lidGrad.addColorStop(0.5, "#ddd");
        lidGrad.addColorStop(1, "#999");
        ctx.fillStyle = lidGrad;
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(18), this._ss(14), 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "rgba(60,60,70,0.5)";
        ctx.lineWidth = this._ss(1);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 18), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 18), this._sy(eyeY));
        ctx.stroke();
      } else {
        const eyeH = 14 * blink;
        ctx.fillStyle = "#050508";
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(16), this._ss(eyeH), 0, 0, Math.PI * 2);
        ctx.fill();

        // Metallic iris ring
        ctx.strokeStyle = `rgba(180,190,210,${0.5 + 0.3 * Math.sin(t * 2 + side)})`;
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(7 * em.pupil_size), 0, Math.PI * 2);
        ctx.stroke();

        // Bright white pupil
        ctx.save();
        ctx.shadowColor = "#ffffff";
        ctx.shadowBlur = this._ss(10);
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(3 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
    }

    // Nose — subtle chrome ridge
    ctx.strokeStyle = "rgba(180,185,200,0.2)";
    ctx.lineWidth = this._ss(1);
    ctx.beginPath();
    ctx.moveTo(this._sx(cx), this._sy(165));
    ctx.quadraticCurveTo(this._sx(cx + 4), this._sy(185), this._sx(cx + 2), this._sy(200));
    ctx.stroke();

    // Mouth
    const ms = this.mouth, mouthY = 248;
    const mouthW = 28 * ms.widthFactor;
    ctx.fillStyle = "#050508";
    if (ms.openAmount < 0.05) {
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY - em.mouth_curve * 6 - 3), this._sx(cx + mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY + 2), this._sx(cx - mouthW), this._sy(mouthY));
      ctx.fill();
      // Chrome lip highlight
      ctx.strokeStyle = "rgba(200,205,220,0.3)";
      ctx.lineWidth = this._ss(1);
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY - em.mouth_curve * 6 - 3), this._sx(cx + mouthW), this._sy(mouthY));
      ctx.stroke();
    } else {
      const openH = ms.openAmount * 14;
      ctx.beginPath();
      ctx.ellipse(this._sx(cx), this._sy(mouthY), this._ss(mouthW), this._ss(openH), 0, 0, Math.PI * 2);
      ctx.fill();
      // Chrome lip ring
      ctx.strokeStyle = "rgba(200,205,220,0.3)";
      ctx.lineWidth = this._ss(1.5);
      ctx.stroke();
    }

    // Environment reflection band
    const refY = 100 + Math.sin(t * 0.3) * 40;
    const refGrad = ctx.createLinearGradient(0, this._sy(refY - 15), 0, this._sy(refY + 15));
    refGrad.addColorStop(0, "transparent");
    refGrad.addColorStop(0.3, "rgba(180,200,240,0.06)");
    refGrad.addColorStop(0.5, "rgba(200,220,255,0.08)");
    refGrad.addColorStop(0.7, "rgba(180,200,240,0.06)");
    refGrad.addColorStop(1, "transparent");
    ctx.fillStyle = refGrad;
    // Clip to face
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(cy + 5), this._ss(114), this._ss(144), 0, 0, Math.PI * 2);
    ctx.clip();
    ctx.fillRect(0, this._sy(refY - 15), w, this._ss(30));
    ctx.restore();
  }
}

// ═══════════════════════════════════════════════════════════
// 29. CYBERNETIC — Multi-layered circuit overlay with holographic scan
// Complexity: geometry 3, effects 4, animation 4 = 11 → Masterwork ($29)
// ═══════════════════════════════════════════════════════════
export class CyberneticFace extends FaceRenderer {
  private sparks: Particle[] = [];
  private scanY = 0;

  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#020308";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Moving scan line
    this.scanY = (this.scanY + 1.2) % REF_H;

    // Base face — dark metallic
    const baseGrad = ctx.createLinearGradient(this._sx(cx - 110), 0, this._sx(cx + 110), 0);
    baseGrad.addColorStop(0, "#0a0c14");
    baseGrad.addColorStop(0.3, "#0f1220");
    baseGrad.addColorStop(0.5, "#121828");
    baseGrad.addColorStop(0.7, "#0f1220");
    baseGrad.addColorStop(1, "#0a0c14");
    ctx.fillStyle = baseGrad;
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(REF_H / 2 + 5), this._ss(115), this._ss(145), 0, 0, Math.PI * 2);
    ctx.fill();

    // Circuit overlay — dense network of tiny lines
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(REF_H / 2 + 5), this._ss(113), this._ss(143), 0, 0, Math.PI * 2);
    ctx.clip();

    ctx.strokeStyle = "rgba(0,180,255,0.08)";
    ctx.lineWidth = this._ss(0.5);
    for (let i = 0; i < 30; i++) {
      const x1 = cx - 100 + (i * 47 + 13) % 200;
      const y1 = 40 + (i * 67 + 29) % 280;
      const angle = noise2D(x1 * 0.01 + t * 0.1, y1 * 0.01) * Math.PI * 2;
      const len = 15 + Math.abs(noise2D(x1 * 0.02, y1 * 0.02)) * 25;
      ctx.beginPath();
      ctx.moveTo(this._sx(x1), this._sy(y1));
      // Right-angle path segments
      const mx = x1 + Math.cos(angle) * len;
      ctx.lineTo(this._sx(mx), this._sy(y1));
      ctx.lineTo(this._sx(mx), this._sy(y1 + Math.sin(angle) * len));
      ctx.stroke();
      // Node dots
      ctx.fillStyle = "rgba(0,180,255,0.15)";
      ctx.beginPath();
      ctx.arc(this._sx(x1), this._sy(y1), this._ss(1), 0, Math.PI * 2);
      ctx.fill();
    }

    // Scanning line effect
    const scanGrad = ctx.createLinearGradient(0, this._sy(this.scanY - 10), 0, this._sy(this.scanY + 10));
    scanGrad.addColorStop(0, "transparent");
    scanGrad.addColorStop(0.5, "rgba(0,200,255,0.12)");
    scanGrad.addColorStop(1, "transparent");
    ctx.fillStyle = scanGrad;
    ctx.fillRect(0, this._sy(this.scanY - 10), w, this._ss(20));

    ctx.restore();

    // Face panel border — glowing segments
    const segments = 12;
    for (let i = 0; i < segments; i++) {
      const a1 = (Math.PI * 2 / segments) * i;
      const a2 = (Math.PI * 2 / segments) * (i + 1);
      const pulse = 0.3 + 0.7 * Math.abs(Math.sin(t * 2 + i * 0.8));
      ctx.strokeStyle = `rgba(0,180,255,${0.15 * pulse})`;
      ctx.lineWidth = this._ss(1.5);
      ctx.beginPath();
      ctx.ellipse(this._sx(cx), this._sy(REF_H / 2 + 5), this._ss(115), this._ss(145), 0, a1, a2);
      ctx.stroke();
    }

    // HUD data overlays
    ctx.font = `${Math.max(5, Math.round(this._ss(6)))}px monospace`;
    ctx.fillStyle = "rgba(0,180,255,0.2)";
    ctx.textAlign = "left";
    ctx.fillText(`SYS: ${(Math.sin(t * 0.5) * 50 + 50).toFixed(0)}%`, this._sx(cx - 95), this._sy(55));
    ctx.fillText(`NET: ACTIVE`, this._sx(cx - 95), this._sy(65));
    ctx.textAlign = "right";
    ctx.fillText(`${(t % 100).toFixed(2)}s`, this._sx(cx + 95), this._sy(55));
    ctx.fillText(`FACE.v4`, this._sx(cx + 95), this._sy(65));

    // Eyes — tech-enhanced with targeting reticle
    const eyeSpacing = 48, eyeY = 135;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 6;

      // Outer targeting bracket
      ctx.strokeStyle = "rgba(0,180,255,0.3)";
      ctx.lineWidth = this._ss(1);
      const brkSize = 20;
      for (const [dx, dy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
        ctx.beginPath();
        ctx.moveTo(this._sx(ex + dx * brkSize), this._sy(eyeY + dy * (brkSize - 5)));
        ctx.lineTo(this._sx(ex + dx * brkSize), this._sy(eyeY + dy * brkSize));
        ctx.lineTo(this._sx(ex + dx * (brkSize - 5)), this._sy(eyeY + dy * brkSize));
        ctx.stroke();
      }

      if (blink < 0.15) {
        ctx.strokeStyle = "rgba(0,200,255,0.6)";
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 16), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 16), this._sy(eyeY));
        ctx.stroke();
      } else {
        const eyeH = 16 * blink;
        // Socket
        ctx.fillStyle = "#020408";
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(17), this._ss(eyeH), 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "rgba(0,180,255,0.3)";
        ctx.lineWidth = this._ss(1);
        ctx.stroke();

        // Rotating targeting ring
        ctx.strokeStyle = "rgba(0,200,255,0.25)";
        ctx.lineWidth = this._ss(0.8);
        const ringR = 9 * em.pupil_size;
        for (let i = 0; i < 4; i++) {
          const a = (Math.PI / 2) * i + t * 1.5 * side;
          ctx.beginPath();
          ctx.arc(this._sx(px), this._sy(py), this._ss(ringR), a, a + 0.8);
          ctx.stroke();
        }

        // Pupil
        ctx.save();
        ctx.shadowColor = "#00ccff";
        ctx.shadowBlur = this._ss(12);
        ctx.fillStyle = "#00ddff";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(3.5 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        // Crosshair
        ctx.strokeStyle = "rgba(0,200,255,0.15)";
        ctx.lineWidth = this._ss(0.5);
        ctx.beginPath();
        ctx.moveTo(this._sx(px - ringR - 3), this._sy(py));
        ctx.lineTo(this._sx(px + ringR + 3), this._sy(py));
        ctx.moveTo(this._sx(px), this._sy(py - ringR - 3));
        ctx.lineTo(this._sx(px), this._sy(py + ringR + 3));
        ctx.stroke();
      }
    }

    // Nose — tech line
    ctx.strokeStyle = "rgba(0,180,255,0.15)";
    ctx.lineWidth = this._ss(0.8);
    ctx.beginPath();
    ctx.moveTo(this._sx(cx), this._sy(165));
    ctx.lineTo(this._sx(cx), this._sy(200));
    ctx.stroke();

    // Mouth — segmented bar
    const ms = this.mouth, mouthY = 248;
    const mouthW = 32 * ms.widthFactor;
    const openH = Math.max(4, ms.openAmount * 12 + 4);
    const mouthSegs = 8;
    for (let i = 0; i < mouthSegs; i++) {
      const sx = cx - mouthW + i * (mouthW * 2 / mouthSegs);
      const segW = (mouthW * 2 / mouthSegs) - 1;
      const pulse = 0.3 + 0.7 * Math.abs(Math.sin(t * 3 + i * 0.5));
      const speaking = ms.openAmount > 0.05 ? pulse : 0.3;
      ctx.fillStyle = `rgba(0,180,255,${speaking * 0.5})`;
      ctx.fillRect(this._sx(sx), this._sy(mouthY - openH / 2), this._ss(segW), this._ss(openH));
    }

    // Spark particles at random circuit nodes
    if (Math.random() < 0.1) {
      const sx = cx + (Math.random() - 0.5) * 180;
      const sy = 50 + Math.random() * 260;
      this.sparks.push(spawnParticle(sx, sy, {
        vx: (Math.random() - 0.5) * 4,
        vy: (Math.random() - 0.5) * 4,
        hue: 190 + Math.random() * 20,
        maxLife: 15 + Math.random() * 15,
        size: 0.5 + Math.random() * 1,
      }));
    }
    this.sparks = tickParticles(this.sparks);
    for (const p of this.sparks) {
      ctx.fillStyle = `hsla(${p.hue},100%,70%,${p.alpha})`;
      ctx.beginPath();
      ctx.arc(this._sx(p.x), this._sy(p.y), this._ss(p.size), 0, Math.PI * 2);
      ctx.fill();
    }
  }
}
