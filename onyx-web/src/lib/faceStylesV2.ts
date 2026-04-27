/**
 * AgentFace V2 Styles — 10 NEW original face designs.
 * None of these existed in OnyxKraken. Each is a unique visual identity.
 */
import { FaceRenderer, REF_W, REF_H } from "./faceRenderer";

// ═══════════════════════════════════════════════════════════
// 1. CONSTELLATION — Stars connected by faint lines
// Complexity: geometry 2, effects 2, animation 1 = 5 → Starter ($5)
// ═══════════════════════════════════════════════════════════
export class ConstellationFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, "#020816");
    grad.addColorStop(1, "#0a0e1a");
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Background stars
    const seed = 42;
    for (let i = 0; i < 35; i++) {
      const sx = ((seed * (i + 1) * 7) % 400);
      const sy = ((seed * (i + 1) * 13) % 360);
      const twinkle = 0.3 + 0.7 * Math.abs(Math.sin(t * 0.8 + i * 1.3));
      ctx.fillStyle = `rgba(180,200,255,${0.15 * twinkle})`;
      ctx.beginPath();
      ctx.arc(this._sx(sx), this._sy(sy), this._ss(1 + twinkle * 0.5), 0, Math.PI * 2);
      ctx.fill();
    }

    // Face outline constellation
    const facePoints = [
      [cx, 30], [cx + 80, 60], [cx + 120, 130], [cx + 100, 220],
      [cx + 60, 300], [cx, 330], [cx - 60, 300], [cx - 100, 220],
      [cx - 120, 130], [cx - 80, 60],
    ];
    ctx.strokeStyle = "rgba(100,150,255,0.15)";
    ctx.lineWidth = this._ss(1);
    for (let i = 0; i < facePoints.length; i++) {
      const [x1, y1] = facePoints[i];
      const [x2, y2] = facePoints[(i + 1) % facePoints.length];
      ctx.beginPath();
      ctx.moveTo(this._sx(x1), this._sy(y1));
      ctx.lineTo(this._sx(x2), this._sy(y2));
      ctx.stroke();
    }
    for (const [px, py] of facePoints) {
      const twk = 0.5 + 0.5 * Math.sin(t + px * 0.01);
      ctx.fillStyle = `rgba(150,180,255,${0.4 + twk * 0.3})`;
      ctx.beginPath();
      ctx.arc(this._sx(px), this._sy(py), this._ss(2.5), 0, Math.PI * 2);
      ctx.fill();
    }

    // Eyes — bright star clusters
    const eyeSpacing = 52, eyeY = 135;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 10;
      const py = eyeY + es.gazeY * 8;

      if (blink < 0.15) {
        ctx.fillStyle = "rgba(100,150,255,0.5)";
        ctx.beginPath();
        ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(2), 0, Math.PI * 2);
        ctx.fill();
      } else {
        // Constellation eye shape
        const r = 20 * blink;
        const pts = 5;
        const starPts: [number, number][] = [];
        for (let i = 0; i < pts; i++) {
          const a = (Math.PI * 2 / pts) * i - Math.PI / 2;
          starPts.push([ex + Math.cos(a) * r, eyeY + Math.sin(a) * r * 0.8]);
        }
        ctx.strokeStyle = "rgba(120,170,255,0.3)";
        ctx.lineWidth = this._ss(0.8);
        for (let i = 0; i < pts; i++) {
          for (let j = i + 1; j < pts; j++) {
            ctx.beginPath();
            ctx.moveTo(this._sx(starPts[i][0]), this._sy(starPts[i][1]));
            ctx.lineTo(this._sx(starPts[j][0]), this._sy(starPts[j][1]));
            ctx.stroke();
          }
        }
        for (const [spx, spy] of starPts) {
          ctx.fillStyle = "rgba(160,200,255,0.6)";
          ctx.beginPath();
          ctx.arc(this._sx(spx), this._sy(spy), this._ss(2), 0, Math.PI * 2);
          ctx.fill();
        }

        // Pupil — bright star
        ctx.save();
        ctx.shadowColor = "#6699ff";
        ctx.shadowBlur = this._ss(12);
        ctx.fillStyle = "#aaccff";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(4 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(1.5), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Mouth — arc of stars
    const ms = this.mouth, mouthY = 245;
    const mouthW = 35 * ms.widthFactor;
    const mouthPts = 7;
    for (let i = 0; i < mouthPts; i++) {
      const frac = i / (mouthPts - 1);
      const mx = cx - mouthW + frac * mouthW * 2;
      const curve = Math.sin(frac * Math.PI) * (3 + em.mouth_curve * 8);
      const openOff = ms.openAmount > 0.05 ? Math.sin(frac * Math.PI) * ms.openAmount * 15 : 0;
      const my = mouthY - curve - openOff;
      const bright = 0.3 + 0.4 * Math.sin(t * 2 + i);
      ctx.fillStyle = `rgba(140,180,255,${bright})`;
      ctx.beginPath();
      ctx.arc(this._sx(mx), this._sy(my), this._ss(2), 0, Math.PI * 2);
      ctx.fill();
      if (i > 0) {
        const prevFrac = (i - 1) / (mouthPts - 1);
        const prevX = cx - mouthW + prevFrac * mouthW * 2;
        const prevCurve = Math.sin(prevFrac * Math.PI) * (3 + em.mouth_curve * 8);
        const prevOpen = ms.openAmount > 0.05 ? Math.sin(prevFrac * Math.PI) * ms.openAmount * 15 : 0;
        ctx.strokeStyle = `rgba(100,150,255,${bright * 0.4})`;
        ctx.lineWidth = this._ss(0.6);
        ctx.beginPath();
        ctx.moveTo(this._sx(prevX), this._sy(mouthY - prevCurve - prevOpen));
        ctx.lineTo(this._sx(mx), this._sy(my));
        ctx.stroke();
      }
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 2. CIRCUIT — PCB traces forming face features
// Complexity: geometry 2, effects 1, animation 1 = 4 → Free ($0)
// ═══════════════════════════════════════════════════════════
export class CircuitFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#041208";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    const trace = "#1a6633";
    const bright = "#33cc66";
    const copper = "#cc8833";

    // Grid traces
    ctx.strokeStyle = trace;
    ctx.lineWidth = this._ss(1);
    for (let x = 20; x <= 380; x += 40) {
      ctx.beginPath(); ctx.moveTo(this._sx(x), this._sy(20)); ctx.lineTo(this._sx(x), this._sy(340)); ctx.stroke();
    }
    for (let y = 20; y <= 340; y += 40) {
      ctx.beginPath(); ctx.moveTo(this._sx(20), this._sy(y)); ctx.lineTo(this._sx(380), this._sy(y)); ctx.stroke();
    }

    // Eye chips (IC packages)
    const eyeSpacing = 56, eyeY = 130;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const chipW = 40, chipH = Math.max(4, 32 * blink);

      // Chip body
      ctx.fillStyle = "#0a2a14";
      ctx.fillRect(this._sx(ex - chipW / 2), this._sy(eyeY - chipH / 2), this._ss(chipW), this._ss(chipH));
      ctx.strokeStyle = bright;
      ctx.lineWidth = this._ss(1.5);
      ctx.strokeRect(this._sx(ex - chipW / 2), this._sy(eyeY - chipH / 2), this._ss(chipW), this._ss(chipH));

      // Pins
      if (blink >= 0.15) {
        for (let i = 0; i < 4; i++) {
          const pinX = ex - chipW / 2 + 8 + i * 9;
          ctx.fillStyle = copper;
          ctx.fillRect(this._sx(pinX - 1.5), this._sy(eyeY - chipH / 2 - 6), this._ss(3), this._ss(6));
          ctx.fillRect(this._sx(pinX - 1.5), this._sy(eyeY + chipH / 2), this._ss(3), this._ss(6));
        }

        // Data line (pupil)
        const px = ex + es.gazeX * 12;
        const py = eyeY + es.gazeY * 8;
        const ps = 6 * em.pupil_size;
        ctx.fillStyle = bright;
        ctx.fillRect(this._sx(px - ps / 2), this._sy(py - ps / 2), this._ss(ps), this._ss(ps));
        ctx.fillStyle = "#aaffaa";
        ctx.fillRect(this._sx(px - 1.5), this._sy(py - 1.5), this._ss(3), this._ss(3));
      }
    }

    // Traces connecting eyes to mouth
    ctx.strokeStyle = bright;
    ctx.lineWidth = this._ss(1.5);
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      ctx.beginPath();
      ctx.moveTo(this._sx(ex), this._sy(eyeY + 20));
      ctx.lineTo(this._sx(ex), this._sy(200));
      ctx.lineTo(this._sx(cx + side * 20), this._sy(200));
      ctx.lineTo(this._sx(cx + side * 20), this._sy(240));
      ctx.stroke();
    }

    // Mouth — trace path
    const ms = this.mouth, mouthY = 248;
    const mouthW = 40 * ms.widthFactor;
    ctx.strokeStyle = bright;
    ctx.lineWidth = this._ss(2);
    if (ms.openAmount < 0.05) {
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.lineTo(this._sx(cx - mouthW / 2), this._sy(mouthY - em.mouth_curve * 6));
      ctx.lineTo(this._sx(cx + mouthW / 2), this._sy(mouthY - em.mouth_curve * 6));
      ctx.lineTo(this._sx(cx + mouthW), this._sy(mouthY));
      ctx.stroke();
    } else {
      const openH = ms.openAmount * 16;
      ctx.strokeRect(this._sx(cx - mouthW), this._sy(mouthY - openH / 2), this._ss(mouthW * 2), this._ss(openH));
      ctx.fillStyle = "#041208";
      ctx.fillRect(this._sx(cx - mouthW + 2), this._sy(mouthY - openH / 2 + 2), this._ss(mouthW * 2 - 4), this._ss(openH - 4));
    }

    // Solder dots at junctions
    const dots = [[cx, 200], [cx - 20, 200], [cx + 20, 200], [cx, mouthY]];
    for (const [dx, dy] of dots) {
      ctx.fillStyle = copper;
      ctx.beginPath();
      ctx.arc(this._sx(dx), this._sy(dy), this._ss(3), 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 3. EMOJI — Bright, cartoonish, cheerful
// Complexity: geometry 1, effects 2, animation 1 = 4 → Free ($0)
// ═══════════════════════════════════════════════════════════
export class EmojiFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#1a1520";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, cy = REF_H / 2;
    const es = this.eye, em = this.emotion;
    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Yellow face circle
    const faceR = 140;
    const grad = ctx.createRadialGradient(
      this._sx(cx - 20), this._sy(cy - 30), 0,
      this._sx(cx), this._sy(cy), this._ss(faceR)
    );
    grad.addColorStop(0, "#ffe066");
    grad.addColorStop(0.8, "#ffcc33");
    grad.addColorStop(1, "#e6aa00");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(cy), this._ss(faceR), 0, Math.PI * 2);
    ctx.fill();

    // Eyes
    const eyeSpacing = 42, eyeY = 145;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 6;

      if (blink < 0.15) {
        // Closed — happy arc
        ctx.strokeStyle = "#3a2a0a";
        ctx.lineWidth = this._ss(3);
        ctx.beginPath();
        ctx.arc(this._sx(ex), this._sy(eyeY + 4), this._ss(12), Math.PI, Math.PI * 2);
        ctx.stroke();
      } else {
        // Sclera
        const eyeH = 22 * blink;
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(16), this._ss(eyeH), 0, 0, Math.PI * 2);
        ctx.fill();

        // Iris
        const irisR = 10 * em.pupil_size;
        ctx.fillStyle = "#3a2200";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(irisR), 0, Math.PI * 2);
        ctx.fill();

        // Pupil
        ctx.fillStyle = "#1a0a00";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(5 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();

        // Highlight
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(this._sx(px - 3), this._sy(py - 3), this._ss(3), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Eyebrows
    if (Math.abs(em.brow_raise) > 0.05) {
      ctx.strokeStyle = "#5a3a0a";
      ctx.lineWidth = this._ss(3.5);
      ctx.lineCap = "round";
      for (const side of [-1, 1]) {
        const ex = cx + side * eyeSpacing;
        const by = eyeY - 28 - em.brow_raise * 10;
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 14), this._sy(by + em.brow_raise * 4 * side));
        ctx.quadraticCurveTo(this._sx(ex), this._sy(by - 3), this._sx(ex + 14), this._sy(by - em.brow_raise * 4 * side));
        ctx.stroke();
      }
    }

    // Mouth
    const ms = this.mouth, mouthY = 210;
    const mouthW = 30 * ms.widthFactor;
    if (ms.openAmount < 0.05) {
      ctx.strokeStyle = "#5a3a0a";
      ctx.lineWidth = this._ss(3);
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.arc(this._sx(cx), this._sy(mouthY - 10 - em.mouth_curve * 8), this._ss(mouthW), 0.15 * Math.PI, 0.85 * Math.PI);
      ctx.stroke();
    } else {
      const openH = ms.openAmount * 22;
      ctx.fillStyle = "#5a2a0a";
      ctx.beginPath();
      ctx.ellipse(this._sx(cx), this._sy(mouthY), this._ss(mouthW), this._ss(openH), 0, 0, Math.PI * 2);
      ctx.fill();
      // Tongue hint
      if (openH > 8) {
        ctx.fillStyle = "#ff6666";
        ctx.beginPath();
        ctx.ellipse(this._sx(cx), this._sy(mouthY + openH * 0.3), this._ss(mouthW * 0.5), this._ss(openH * 0.4), 0, 0, Math.PI);
        ctx.fill();
      }
    }

    // Cheek blush
    ctx.fillStyle = "rgba(255,100,80,0.15)";
    ctx.beginPath(); ctx.arc(this._sx(cx - 75), this._sy(195), this._ss(18), 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(this._sx(cx + 75), this._sy(195), this._ss(18), 0, Math.PI * 2); ctx.fill();
  }
}

// ═══════════════════════════════════════════════════════════
// 4. VAPOR — 80s retrowave sunset, chrome bars
// Complexity: geometry 2, effects 2, animation 2 = 6 → Pro ($9)
// ═══════════════════════════════════════════════════════════
export class VaporFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    // Sunset gradient
    const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
    bgGrad.addColorStop(0, "#1a0030");
    bgGrad.addColorStop(0.4, "#4a0060");
    bgGrad.addColorStop(0.6, "#ff4488");
    bgGrad.addColorStop(0.8, "#ff8844");
    bgGrad.addColorStop(1, "#ffcc44");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Sun circle
    ctx.fillStyle = "#ff6644";
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(200), this._ss(80), 0, Math.PI * 2);
    ctx.fill();
    // Sun stripes
    ctx.fillStyle = "#4a0060";
    for (let i = 0; i < 5; i++) {
      const sy = 170 + i * 12;
      ctx.fillRect(this._sx(cx - 80), this._sy(sy), this._ss(160), this._ss(3));
    }

    // Perspective grid
    ctx.strokeStyle = "rgba(255,100,255,0.3)";
    ctx.lineWidth = this._ss(1);
    const horizon = 230;
    for (let i = -8; i <= 8; i++) {
      ctx.beginPath();
      ctx.moveTo(this._sx(cx + i * 25), this._sy(horizon));
      ctx.lineTo(this._sx(cx + i * 80), this._sy(REF_H));
      ctx.stroke();
    }
    for (let i = 0; i < 8; i++) {
      const y = horizon + (i * i * 2.5);
      if (y > REF_H) break;
      ctx.beginPath();
      ctx.moveTo(this._sx(0), this._sy(y));
      ctx.lineTo(this._sx(REF_W), this._sy(y));
      ctx.stroke();
    }

    // Eyes — chrome horizontal bars
    const eyeSpacing = 55, eyeY = 125;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const barW = 36, barH = Math.max(2, 14 * blink);

      // Chrome gradient
      const chromeGrad = ctx.createLinearGradient(
        this._sx(ex - barW / 2), this._sy(eyeY - barH / 2),
        this._sx(ex - barW / 2), this._sy(eyeY + barH / 2)
      );
      chromeGrad.addColorStop(0, "#ffffff");
      chromeGrad.addColorStop(0.3, "#aabbcc");
      chromeGrad.addColorStop(0.5, "#445566");
      chromeGrad.addColorStop(0.7, "#aabbcc");
      chromeGrad.addColorStop(1, "#ffffff");
      ctx.fillStyle = chromeGrad;
      ctx.fillRect(this._sx(ex - barW / 2), this._sy(eyeY - barH / 2), this._ss(barW), this._ss(barH));

      if (blink >= 0.15) {
        const px = ex + es.gazeX * 10;
        const py = eyeY + es.gazeY * 5;
        ctx.fillStyle = "#ff44ff";
        ctx.shadowColor = "#ff44ff";
        ctx.shadowBlur = this._ss(8);
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(4 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    }

    // Mouth — neon line
    const ms = this.mouth, mouthY = 200;
    const mouthW = 35 * ms.widthFactor;
    ctx.strokeStyle = "#ff44ff";
    ctx.shadowColor = "#ff44ff";
    ctx.shadowBlur = this._ss(10);
    ctx.lineWidth = this._ss(2.5);
    ctx.beginPath();
    for (let i = 0; i <= 20; i++) {
      const frac = i / 20;
      const x = cx - mouthW + frac * mouthW * 2;
      const wave = Math.sin(frac * Math.PI * 3 + t * 4) * ms.openAmount * 8;
      const curve = Math.sin(frac * Math.PI) * (2 + em.mouth_curve * 8);
      const y = mouthY - curve + wave;
      if (i === 0) ctx.moveTo(this._sx(x), this._sy(y));
      else ctx.lineTo(this._sx(x), this._sy(y));
    }
    ctx.stroke();
    ctx.shadowBlur = 0;
  }
}

// ═══════════════════════════════════════════════════════════
// 5. SKETCH — Hand-drawn pencil on paper
// Complexity: geometry 3, effects 1, animation 1 = 5 → Starter ($5)
// ═══════════════════════════════════════════════════════════
export class SketchFace extends FaceRenderer {
  private _jitter(v: number, amt = 1.5): number {
    return v + (Math.sin(v * 7.3 + performance.now() / 1000 * 0.5) * amt);
  }

  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#f5f0e8";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    const pencil = "#3a3530";
    const light = "#8a8070";

    // Face oval — multiple wobbly strokes
    ctx.strokeStyle = pencil;
    ctx.lineWidth = this._ss(1.5);
    for (let pass = 0; pass < 2; pass++) {
      ctx.beginPath();
      for (let i = 0; i <= 40; i++) {
        const a = (Math.PI * 2 / 40) * i;
        const rx = 110 + pass * 2;
        const ry = 140 + pass * 2;
        const x = cx + Math.cos(a) * rx + (Math.sin(a * 7 + pass) * 2);
        const y = REF_H / 2 + 5 + Math.sin(a) * ry + (Math.cos(a * 5 + pass) * 2);
        if (i === 0) ctx.moveTo(this._sx(this._jitter(x)), this._sy(this._jitter(y)));
        else ctx.lineTo(this._sx(this._jitter(x)), this._sy(this._jitter(y)));
      }
      ctx.stroke();
    }

    // Eyes
    const eyeSpacing = 45, eyeY = 140;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 10;
      const py = eyeY + es.gazeY * 7;

      if (blink < 0.15) {
        ctx.strokeStyle = pencil;
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.moveTo(this._sx(this._jitter(ex - 15)), this._sy(this._jitter(eyeY)));
        ctx.lineTo(this._sx(this._jitter(ex + 15)), this._sy(this._jitter(eyeY)));
        ctx.stroke();
      } else {
        const eyeH = 14 * blink;
        ctx.strokeStyle = pencil;
        ctx.lineWidth = this._ss(1.8);
        // Upper lid
        ctx.beginPath();
        ctx.moveTo(this._sx(this._jitter(ex - 18)), this._sy(this._jitter(eyeY)));
        ctx.quadraticCurveTo(this._sx(this._jitter(ex)), this._sy(this._jitter(eyeY - eyeH)), this._sx(this._jitter(ex + 18)), this._sy(this._jitter(eyeY)));
        ctx.stroke();
        // Lower lid
        ctx.beginPath();
        ctx.moveTo(this._sx(this._jitter(ex - 18)), this._sy(this._jitter(eyeY)));
        ctx.quadraticCurveTo(this._sx(this._jitter(ex)), this._sy(this._jitter(eyeY + eyeH * 0.7)), this._sx(this._jitter(ex + 18)), this._sy(this._jitter(eyeY)));
        ctx.stroke();

        // Iris
        ctx.fillStyle = pencil;
        ctx.beginPath();
        ctx.arc(this._sx(this._jitter(px)), this._sy(this._jitter(py)), this._ss(7 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        // Highlight
        ctx.fillStyle = "#f5f0e8";
        ctx.beginPath();
        ctx.arc(this._sx(this._jitter(px - 2)), this._sy(this._jitter(py - 2)), this._ss(2.5), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Nose — simple L
    ctx.strokeStyle = light;
    ctx.lineWidth = this._ss(1.2);
    ctx.beginPath();
    ctx.moveTo(this._sx(this._jitter(cx)), this._sy(this._jitter(175)));
    ctx.lineTo(this._sx(this._jitter(cx)), this._sy(this._jitter(195)));
    ctx.lineTo(this._sx(this._jitter(cx + 8)), this._sy(this._jitter(195)));
    ctx.stroke();

    // Mouth
    const ms = this.mouth, mouthY = 230;
    const mouthW = 28 * ms.widthFactor;
    ctx.strokeStyle = pencil;
    ctx.lineWidth = this._ss(2);
    if (ms.openAmount < 0.05) {
      ctx.beginPath();
      ctx.moveTo(this._sx(this._jitter(cx - mouthW)), this._sy(this._jitter(mouthY)));
      ctx.quadraticCurveTo(
        this._sx(this._jitter(cx)), this._sy(this._jitter(mouthY - em.mouth_curve * 10)),
        this._sx(this._jitter(cx + mouthW)), this._sy(this._jitter(mouthY))
      );
      ctx.stroke();
    } else {
      const openH = ms.openAmount * 16;
      ctx.beginPath();
      ctx.ellipse(this._sx(this._jitter(cx)), this._sy(this._jitter(mouthY)), this._ss(mouthW), this._ss(openH), 0, 0, Math.PI * 2);
      ctx.stroke();
      // Cross-hatch inside
      ctx.strokeStyle = light;
      ctx.lineWidth = this._ss(0.6);
      for (let i = -2; i <= 2; i++) {
        ctx.beginPath();
        ctx.moveTo(this._sx(cx - mouthW + 4 + i * 3), this._sy(mouthY - openH + 2));
        ctx.lineTo(this._sx(cx + mouthW - 4 + i * 3), this._sy(mouthY + openH - 2));
        ctx.stroke();
      }
    }

    // Cross-hatching shadow under chin
    ctx.strokeStyle = "rgba(60,50,40,0.12)";
    ctx.lineWidth = this._ss(0.5);
    for (let i = 0; i < 15; i++) {
      const x1 = cx - 40 + i * 6;
      ctx.beginPath();
      ctx.moveTo(this._sx(x1), this._sy(290));
      ctx.lineTo(this._sx(x1 + 15), this._sy(310));
      ctx.stroke();
    }
  }
}
