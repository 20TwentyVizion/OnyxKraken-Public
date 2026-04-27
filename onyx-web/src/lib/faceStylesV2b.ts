/**
 * AgentFace V2 Styles — Part 2 (faces 6-10)
 */
import { FaceRenderer, lerpColor, REF_W, REF_H } from "./faceRenderer";

// ═══════════════════════════════════════════════════════════
// 6. HOLOGRAM — Blue-tinted transparent overlay with scan lines
// Complexity: geometry 2, effects 3, animation 2 = 7 → Premium ($14)
// ═══════════════════════════════════════════════════════════
export class HologramFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#020610";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;
    const flicker = Math.sin(t * 30) > 0.92 ? 0.4 : 1.0;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    const holoBlue = `rgba(80,180,255,${0.6 * flicker})`;
    const holoDim = `rgba(40,100,200,${0.3 * flicker})`;
    const holoGlow = `rgba(100,200,255,${0.15 * flicker})`;

    // Holographic face plate — transparent rounded rect
    ctx.fillStyle = `rgba(20,60,120,${0.08 * flicker})`;
    ctx.strokeStyle = holoBlue;
    ctx.lineWidth = this._ss(1.5);
    const rx = 30, ry = 25, rw = 340, rh = 310;
    ctx.beginPath();
    ctx.roundRect(this._sx(rx), this._sy(ry), this._ss(rw), this._ss(rh), this._ss(20));
    ctx.fill();
    ctx.stroke();

    // Inner glow frame
    ctx.strokeStyle = holoDim;
    ctx.lineWidth = this._ss(0.8);
    ctx.beginPath();
    ctx.roundRect(this._sx(rx + 8), this._sy(ry + 8), this._ss(rw - 16), this._ss(rh - 16), this._ss(14));
    ctx.stroke();

    // Eyes
    const eyeSpacing = 52, eyeY = 135;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 10;
      const py = eyeY + es.gazeY * 7;

      if (blink < 0.15) {
        ctx.strokeStyle = holoBlue;
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 18), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 18), this._sy(eyeY));
        ctx.stroke();
      } else {
        const eyeH = 18 * blink;
        // Outer eye glow
        ctx.fillStyle = holoGlow;
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(22), this._ss(eyeH + 4), 0, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = holoBlue;
        ctx.lineWidth = this._ss(1.5);
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(18), this._ss(eyeH), 0, 0, Math.PI * 2);
        ctx.stroke();

        // Iris ring
        ctx.strokeStyle = holoBlue;
        ctx.lineWidth = this._ss(1);
        const irisR = 8 * em.pupil_size;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(irisR), 0, Math.PI * 2);
        ctx.stroke();

        // Pupil
        ctx.fillStyle = holoBlue;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(4 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Nose hint
    ctx.strokeStyle = holoDim;
    ctx.lineWidth = this._ss(0.8);
    ctx.beginPath();
    ctx.moveTo(this._sx(cx), this._sy(165));
    ctx.lineTo(this._sx(cx + 3), this._sy(190));
    ctx.stroke();

    // Mouth
    const ms = this.mouth, mouthY = 240;
    const mouthW = 32 * ms.widthFactor;
    ctx.strokeStyle = holoBlue;
    ctx.lineWidth = this._ss(1.5);
    if (ms.openAmount < 0.05) {
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY - em.mouth_curve * 10), this._sx(cx + mouthW), this._sy(mouthY));
      ctx.stroke();
    } else {
      const openH = ms.openAmount * 16;
      ctx.beginPath();
      ctx.ellipse(this._sx(cx), this._sy(mouthY), this._ss(mouthW), this._ss(openH), 0, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Scan lines
    ctx.fillStyle = `rgba(0,0,0,${0.15 * flicker})`;
    const step = Math.max(2, Math.round(2 / Math.max(this.s, 0.3)));
    for (let y = Math.round(this._sy(ry)); y < this._sy(ry + rh); y += step) {
      ctx.fillRect(this._sx(rx), y, this._ss(rw), 1);
    }

    // Scrolling interference band
    const bandY = (t * 60) % REF_H;
    ctx.fillStyle = `rgba(80,180,255,${0.06 * flicker})`;
    ctx.fillRect(this._sx(rx), this._sy(bandY), this._ss(rw), this._ss(20));
  }
}

// ═══════════════════════════════════════════════════════════
// 7. PIXEL ART — Chunky 8-bit blocks
// Complexity: geometry 1, effects 1, animation 2 = 4 → Free ($0)
// ═══════════════════════════════════════════════════════════
export class PixelFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#16161d";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const P = 8; // pixel size

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    const snap = (v: number) => Math.round(v / P) * P;
    const pxRect = (x: number, y: number, pw: number, ph: number, color: string) => {
      ctx.fillStyle = color;
      ctx.fillRect(this._sx(snap(x)), this._sy(snap(y)), this._ss(pw * P), this._ss(ph * P));
    };

    // Face plate — pixel border
    const skin = "#4a6ea0";
    const skinDark = "#2a3e60";
    const skinLight = "#6a8ec0";

    // Face shape (rounded pixel box)
    for (let px = 6; px <= 44; px++) {
      for (let py = 4; py <= 40; py++) {
        const dx = Math.abs(px - 25);
        const dy = Math.abs(py - 22);
        const edge = dx > 18 || dy > 17 || (dx > 16 && dy > 14);
        if (!edge) {
          const isBorder = dx > 15 || dy > 15 || (dx > 13 && dy > 12);
          pxRect(px * P, py * P, 1, 1, isBorder ? skinDark : skin);
        }
      }
    }

    // Eyes
    const eyeSpacing = snap(56);
    const eyeY = snap(135);
    for (const side of [-1, 1]) {
      const ex = snap(cx + side * eyeSpacing);
      const gx = snap(es.gazeX * 8);
      const gy = snap(es.gazeY * 6);

      if (blink < 0.15) {
        pxRect(ex - P * 2, eyeY, 4, 1, "#ffffff");
      } else {
        const eh = Math.max(1, Math.round(4 * blink));
        // White of eye
        for (let py = 0; py < eh; py++) {
          pxRect(ex - P * 2, eyeY - P * Math.floor(eh / 2) + py * P, 4, 1, "#ffffff");
        }
        // Pupil
        pxRect(ex + gx - P, eyeY + gy - P, 2, 2, "#1a1a2a");
        // Highlight
        pxRect(ex + gx - P, eyeY + gy - P, 1, 1, skinLight);
      }
    }

    // Eyebrows
    if (Math.abs(em.brow_raise) > 0.1) {
      const browY = snap(eyeY - 28 - em.brow_raise * 10);
      for (const side of [-1, 1]) {
        const ex = snap(cx + side * eyeSpacing);
        pxRect(ex - P * 2, browY, 4, 1, skinDark);
      }
    }

    // Mouth
    const ms = this.mouth, mouthY = snap(240);
    const mouthW = Math.max(2, Math.round(5 * ms.widthFactor));

    if (ms.openAmount < 0.05) {
      const curveOff = snap(em.mouth_curve * 6);
      pxRect(cx - mouthW * P / 2, mouthY - curveOff, mouthW, 1, "#1a1a2a");
    } else {
      const openH = Math.max(1, Math.round(ms.openAmount * 3));
      for (let py = 0; py < openH; py++) {
        pxRect(cx - mouthW * P / 2, mouthY + py * P, mouthW, 1, "#1a1a2a");
      }
      // Teeth top row
      if (openH > 1) {
        pxRect(cx - (mouthW - 1) * P / 2, mouthY, mouthW - 1, 1, "#dddddd");
      }
    }

    // Pixel grid overlay
    ctx.strokeStyle = "rgba(255,255,255,0.03)";
    ctx.lineWidth = 1;
    for (let x = 0; x < REF_W; x += P) {
      ctx.beginPath(); ctx.moveTo(this._sx(x), 0); ctx.lineTo(this._sx(x), h); ctx.stroke();
    }
    for (let y = 0; y < REF_H; y += P) {
      ctx.beginPath(); ctx.moveTo(0, this._sy(y)); ctx.lineTo(w, this._sy(y)); ctx.stroke();
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 8. PLASMA — Flowing energy gradients, shifting hues
// Complexity: geometry 1, effects 3, animation 3 = 7 → Premium ($14)
// ═══════════════════════════════════════════════════════════
export class PlasmaFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#08050a";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    const hue1 = (t * 25) % 360;
    const hue2 = (hue1 + 120) % 360;

    // Plasma background blobs
    for (let i = 0; i < 4; i++) {
      const bx = cx + Math.sin(t * 0.4 + i * 1.8) * 80;
      const by = REF_H / 2 + Math.cos(t * 0.3 + i * 2.2) * 60;
      const br = 60 + Math.sin(t * 0.5 + i) * 20;
      const grad = ctx.createRadialGradient(
        this._sx(bx), this._sy(by), 0,
        this._sx(bx), this._sy(by), this._ss(br)
      );
      const h = (hue1 + i * 90) % 360;
      grad.addColorStop(0, `hsla(${h},80%,50%,0.12)`);
      grad.addColorStop(1, `hsla(${h},80%,50%,0)`);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(this._sx(bx), this._sy(by), this._ss(br), 0, Math.PI * 2);
      ctx.fill();
    }

    // Face container glow
    const faceGrad = ctx.createRadialGradient(
      this._sx(cx), this._sy(REF_H / 2), 0,
      this._sx(cx), this._sy(REF_H / 2), this._ss(150)
    );
    faceGrad.addColorStop(0, `hsla(${hue1},60%,30%,0.1)`);
    faceGrad.addColorStop(1, "transparent");
    ctx.fillStyle = faceGrad;
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(REF_H / 2), this._ss(150), 0, Math.PI * 2);
    ctx.fill();

    // Eyes — glowing energy orbs
    const eyeSpacing = 50, eyeY = 135;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 10;
      const py = eyeY + es.gazeY * 7;
      const h = side < 0 ? hue1 : hue2;

      if (blink < 0.15) {
        ctx.strokeStyle = `hsla(${h},70%,60%,0.6)`;
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 16), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 16), this._sy(eyeY));
        ctx.stroke();
      } else {
        const eyeR = 16 * blink;
        // Outer glow
        const eyeGrad = ctx.createRadialGradient(
          this._sx(ex), this._sy(eyeY), 0,
          this._sx(ex), this._sy(eyeY), this._ss(eyeR + 8)
        );
        eyeGrad.addColorStop(0, `hsla(${h},80%,60%,0.2)`);
        eyeGrad.addColorStop(1, "transparent");
        ctx.fillStyle = eyeGrad;
        ctx.beginPath();
        ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(eyeR + 8), 0, Math.PI * 2);
        ctx.fill();

        // Eye ring
        ctx.strokeStyle = `hsla(${h},80%,65%,0.7)`;
        ctx.lineWidth = this._ss(1.5);
        ctx.beginPath();
        ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(eyeR), 0, Math.PI * 2);
        ctx.stroke();

        // Pupil
        ctx.save();
        ctx.shadowColor = `hsl(${h},90%,70%)`;
        ctx.shadowBlur = this._ss(15);
        ctx.fillStyle = `hsl(${h},90%,75%)`;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(5 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(2), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Mouth — energy arc
    const ms = this.mouth, mouthY = 245;
    const mouthW = 35 * ms.widthFactor;
    ctx.strokeStyle = `hsla(${hue1},70%,60%,0.6)`;
    ctx.lineWidth = this._ss(2);
    ctx.beginPath();
    for (let i = 0; i <= 24; i++) {
      const frac = i / 24;
      const x = cx - mouthW + frac * mouthW * 2;
      const curve = Math.sin(frac * Math.PI) * (3 + em.mouth_curve * 8);
      const energy = ms.openAmount > 0.05 ? Math.sin(frac * Math.PI * 5 + t * 6) * ms.openAmount * 10 : 0;
      const y = mouthY - curve + energy;
      if (i === 0) ctx.moveTo(this._sx(x), this._sy(y));
      else ctx.lineTo(this._sx(x), this._sy(y));
    }
    ctx.stroke();
  }
}

// ═══════════════════════════════════════════════════════════
// 9. GEOMETRIC — Low-poly triangulated mesh
// Complexity: geometry 3, effects 2, animation 2 = 7 → Premium ($14)
// ═══════════════════════════════════════════════════════════
export class GeometricFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0a0c14";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Face mesh — triangulated hexagonal shape
    const facePoints: [number, number][] = [
      [cx, 28], // top
      [cx + 55, 55], [cx + 90, 100], [cx + 110, 150], [cx + 105, 200],
      [cx + 85, 250], [cx + 55, 290], [cx + 20, 318], [cx, 330], // right
      [cx - 20, 318], [cx - 55, 290], [cx - 85, 250], [cx - 105, 200],
      [cx - 110, 150], [cx - 90, 100], [cx - 55, 55], // left
    ];

    // Triangulate to center
    const fcx = cx, fcy = REF_H / 2;
    for (let i = 0; i < facePoints.length; i++) {
      const [x1, y1] = facePoints[i];
      const [x2, y2] = facePoints[(i + 1) % facePoints.length];
      const midBright = 0.08 + 0.04 * Math.sin(t * 0.5 + i * 0.7);
      ctx.fillStyle = `rgba(60,100,180,${midBright})`;
      ctx.beginPath();
      ctx.moveTo(this._sx(x1), this._sy(y1));
      ctx.lineTo(this._sx(x2), this._sy(y2));
      ctx.lineTo(this._sx(fcx), this._sy(fcy));
      ctx.closePath();
      ctx.fill();
    }

    // Wireframe edges
    ctx.strokeStyle = lerpColor("#1a2a50", "#3366aa", 0.5 + 0.5 * Math.sin(t));
    ctx.lineWidth = this._ss(1);
    ctx.beginPath();
    for (let i = 0; i < facePoints.length; i++) {
      const [x, y] = facePoints[i];
      if (i === 0) ctx.moveTo(this._sx(x), this._sy(y));
      else ctx.lineTo(this._sx(x), this._sy(y));
      // Radial line to center
      ctx.moveTo(this._sx(x), this._sy(y));
      ctx.lineTo(this._sx(fcx), this._sy(fcy));
      ctx.moveTo(this._sx(x), this._sy(y));
    }
    ctx.closePath();
    ctx.stroke();

    // Vertices
    for (const [px, py] of facePoints) {
      ctx.fillStyle = "#4477cc";
      ctx.beginPath();
      ctx.arc(this._sx(px), this._sy(py), this._ss(2.5), 0, Math.PI * 2);
      ctx.fill();
    }

    // Eyes — diamond shapes
    const eyeSpacing = 50, eyeY = 135;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 10;
      const py = eyeY + es.gazeY * 7;
      const dSize = 20 * Math.max(blink, 0.08);

      if (blink < 0.15) {
        ctx.strokeStyle = "#4488cc";
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 16), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 16), this._sy(eyeY));
        ctx.stroke();
      } else {
        // Diamond eye
        ctx.fillStyle = "rgba(30,60,120,0.4)";
        ctx.strokeStyle = "#5599dd";
        ctx.lineWidth = this._ss(1.5);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex), this._sy(eyeY - dSize));
        ctx.lineTo(this._sx(ex + dSize * 0.7), this._sy(eyeY));
        ctx.lineTo(this._sx(ex), this._sy(eyeY + dSize));
        ctx.lineTo(this._sx(ex - dSize * 0.7), this._sy(eyeY));
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        // Subdivide — inner triangle
        ctx.strokeStyle = "rgba(80,150,220,0.3)";
        ctx.lineWidth = this._ss(0.8);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex), this._sy(eyeY - dSize * 0.5));
        ctx.lineTo(this._sx(ex + dSize * 0.35), this._sy(eyeY + dSize * 0.25));
        ctx.lineTo(this._sx(ex - dSize * 0.35), this._sy(eyeY + dSize * 0.25));
        ctx.closePath();
        ctx.stroke();

        // Pupil
        ctx.fillStyle = "#66aaff";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(5 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(2), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Mouth — segmented line
    const ms = this.mouth, mouthY = 245;
    const mouthW = 35 * ms.widthFactor;
    const segments = 6;
    ctx.strokeStyle = "#5599dd";
    ctx.lineWidth = this._ss(1.5);
    ctx.beginPath();
    for (let i = 0; i <= segments; i++) {
      const frac = i / segments;
      const x = cx - mouthW + frac * mouthW * 2;
      const curve = Math.sin(frac * Math.PI) * (3 + em.mouth_curve * 8);
      const openOff = ms.openAmount > 0.05 ? Math.sin(frac * Math.PI) * ms.openAmount * 14 : 0;
      const y = mouthY - curve - openOff;
      if (i === 0) ctx.moveTo(this._sx(x), this._sy(y));
      else ctx.lineTo(this._sx(x), this._sy(y));
    }
    ctx.stroke();
    // Vertex dots on mouth
    for (let i = 0; i <= segments; i++) {
      const frac = i / segments;
      const x = cx - mouthW + frac * mouthW * 2;
      const curve = Math.sin(frac * Math.PI) * (3 + em.mouth_curve * 8);
      const openOff = ms.openAmount > 0.05 ? Math.sin(frac * Math.PI) * ms.openAmount * 14 : 0;
      ctx.fillStyle = "#4488cc";
      ctx.beginPath();
      ctx.arc(this._sx(x), this._sy(mouthY - curve - openOff), this._ss(2), 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 10. ASCII — Character matrix forming face
// Complexity: geometry 2, effects 1, animation 2 = 5 → Starter ($5)
// ═══════════════════════════════════════════════════════════
export class AsciiFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0c0c0c";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    const charW = 8, charH = 12;
    const cols = Math.floor(REF_W / charW);
    const rows = Math.floor(REF_H / charH);
    const fontSize = Math.max(6, Math.round(this._ss(10)));
    ctx.font = `${fontSize}px Consolas, monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    // Background noise characters
    const noiseChars = ".,:;'`~-+*";
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const x = c * charW + charW / 2;
        const y = r * charH + charH / 2;
        const dist = Math.sqrt((x - cx) ** 2 + ((y - REF_H / 2) * 0.85) ** 2);
        if (dist < 145 && dist > 120) {
          // Face outline
          ctx.fillStyle = `rgba(100,255,100,${0.15 + 0.05 * Math.sin(t + r + c)})`;
          ctx.fillText("|/-\\|/-\\"[Math.floor(Math.atan2(y - REF_H / 2, x - cx) / (Math.PI / 4) + 4) % 8], this._sx(x), this._sy(y));
        } else if (dist < 120) {
          // Inside face — sparse dots
          if (Math.sin(r * 3.7 + c * 5.3) > 0.7) {
            ctx.fillStyle = "rgba(100,255,100,0.06)";
            ctx.fillText(noiseChars[Math.floor(Math.abs(Math.sin(r * c + t * 0.2)) * noiseChars.length)], this._sx(x), this._sy(y));
          }
        }
      }
    }

    // Eyes
    const eyeSpacing = 52, eyeY = 135;
    const green = "rgb(100,255,100)";
    const dimGreen = "rgba(100,255,100,0.5)";

    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const gx = Math.round(es.gazeX * 1.5);
      const gy = Math.round(es.gazeY * 1);

      if (blink < 0.15) {
        ctx.fillStyle = green;
        ctx.fillText("---", this._sx(ex), this._sy(eyeY));
      } else {
        // Eye frame
        const eyeChars = blink > 0.6 ? [
          " .--.  ",
          "| @@ | ",
          " '--'  ",
        ] : [
          " .--. ",
          "| -- |",
          " '--' ",
        ];

        const pupilRow = 1;
        const pupilCol = 3 + gx;

        for (let r = 0; r < eyeChars.length; r++) {
          for (let c = 0; c < eyeChars[r].length; c++) {
            const ch = eyeChars[r][c];
            if (ch === ' ') continue;
            const px = ex - (eyeChars[r].length / 2) * charW + c * charW;
            const py = eyeY - charH + r * charH + gy * charH;

            if (r === pupilRow && Math.abs(c - pupilCol) < 1 && ch === '@') {
              ctx.fillStyle = green;
              ctx.shadowColor = green;
              ctx.shadowBlur = this._ss(6);
              ctx.fillText("@", this._sx(px), this._sy(py));
              ctx.shadowBlur = 0;
            } else {
              ctx.fillStyle = dimGreen;
              ctx.fillText(ch, this._sx(px), this._sy(py));
            }
          }
        }
      }
    }

    // Mouth
    const ms = this.mouth, mouthY = 250;
    ctx.fillStyle = green;

    if (ms.openAmount < 0.05) {
      const mouthStr = em.mouth_curve > 0.3 ? " \\___/ " : em.mouth_curve < -0.3 ? " /---\\ " : " ----- ";
      for (let c = 0; c < mouthStr.length; c++) {
        if (mouthStr[c] === ' ') continue;
        ctx.fillText(mouthStr[c], this._sx(cx - (mouthStr.length / 2) * charW + c * charW), this._sy(mouthY));
      }
    } else {
      const openRows = Math.max(1, Math.round(ms.openAmount * 3));
      const mouthOpen = [" .----. ", "|      |", " '----' "];
      const displayRows = openRows >= 2 ? mouthOpen : [mouthOpen[0], mouthOpen[2]];
      for (let r = 0; r < displayRows.length; r++) {
        const row = displayRows[r];
        for (let c = 0; c < row.length; c++) {
          if (row[c] === ' ') continue;
          ctx.fillStyle = r === 0 || r === displayRows.length - 1 ? dimGreen : green;
          ctx.fillText(row[c], this._sx(cx - (row.length / 2) * charW + c * charW), this._sy(mouthY + r * charH - charH / 2));
        }
      }
    }

    // Status line
    ctx.fillStyle = dimGreen;
    ctx.font = `${Math.max(6, Math.round(this._ss(8)))}px Consolas, monospace`;
    ctx.textAlign = "center";
    const statusLine = `> ${this.emotionName} | gaze(${es.gazeX.toFixed(1)},${es.gazeY.toFixed(1)})`;
    ctx.fillText(statusLine, this._sx(cx), this._sy(330));
    // Blinking cursor
    if (Math.sin(t * 4) > 0) {
      const cursorX = cx + statusLine.length * 2.5;
      ctx.fillStyle = green;
      ctx.fillText("_", this._sx(cursorX), this._sy(330));
    }
  }
}
