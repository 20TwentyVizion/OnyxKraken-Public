/**
 * AgentFace V3 Styles — Batch 3b, faces 22-26.
 */
import { FaceRenderer, lerpColor, REF_W, REF_H } from "./faceRenderer";

// ═══════════════════════════════════════════════════════════
// 22. SMOKE / NEBULA — Wispy ethereal particles
// Complexity: geometry 1, effects 3, animation 3 = 7 → Premium ($14)
// ═══════════════════════════════════════════════════════════
export class NebulFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#030208";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Nebula clouds — drifting colored blobs
    const clouds = [
      { x: cx - 40, y: 120, r: 80, h1: 260, h2: 300, speed: 0.15 },
      { x: cx + 50, y: 180, r: 90, h1: 320, h2: 350, speed: 0.12 },
      { x: cx - 20, y: 250, r: 70, h1: 200, h2: 240, speed: 0.18 },
      { x: cx + 30, y: 100, r: 60, h1: 280, h2: 310, speed: 0.1 },
      { x: cx, y: REF_H / 2, r: 110, h1: 240, h2: 280, speed: 0.08 },
    ];
    for (const c of clouds) {
      const bx = c.x + Math.sin(t * c.speed) * 15;
      const by = c.y + Math.cos(t * c.speed * 0.7) * 10;
      const hue = c.h1 + (c.h2 - c.h1) * (0.5 + 0.5 * Math.sin(t * 0.2));
      const grad = ctx.createRadialGradient(
        this._sx(bx), this._sy(by), 0,
        this._sx(bx), this._sy(by), this._ss(c.r)
      );
      grad.addColorStop(0, `hsla(${hue},60%,40%,0.12)`);
      grad.addColorStop(0.4, `hsla(${hue},50%,30%,0.06)`);
      grad.addColorStop(1, "transparent");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(this._sx(bx), this._sy(by), this._ss(c.r), 0, Math.PI * 2);
      ctx.fill();
    }

    // Tiny stars
    for (let i = 0; i < 25; i++) {
      const sx = (i * 97 + 13) % REF_W;
      const sy = (i * 67 + 29) % REF_H;
      const twinkle = 0.3 + 0.7 * Math.abs(Math.sin(t * 1.5 + i * 2.1));
      ctx.fillStyle = `rgba(220,200,255,${0.2 * twinkle})`;
      ctx.beginPath();
      ctx.arc(this._sx(sx), this._sy(sy), this._ss(0.8 + twinkle * 0.4), 0, Math.PI * 2);
      ctx.fill();
    }

    // Eyes — glowing nebula orbs
    const eyeSpacing = 48, eyeY = 138;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 10;
      const py = eyeY + es.gazeY * 7;
      const hue = side < 0 ? 270 : 320;

      if (blink < 0.15) {
        ctx.strokeStyle = `hsla(${hue},60%,60%,0.5)`;
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 16), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 16), this._sy(eyeY));
        ctx.stroke();
      } else {
        const eyeR = 18 * blink;
        // Outer nebula glow
        const outerGlow = ctx.createRadialGradient(
          this._sx(ex), this._sy(eyeY), 0,
          this._sx(ex), this._sy(eyeY), this._ss(eyeR + 12)
        );
        outerGlow.addColorStop(0, `hsla(${hue},60%,50%,0.15)`);
        outerGlow.addColorStop(1, "transparent");
        ctx.fillStyle = outerGlow;
        ctx.beginPath();
        ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(eyeR + 12), 0, Math.PI * 2);
        ctx.fill();

        // Eye shape
        ctx.strokeStyle = `hsla(${hue},50%,60%,0.4)`;
        ctx.lineWidth = this._ss(1);
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(16), this._ss(eyeR), 0, 0, Math.PI * 2);
        ctx.stroke();

        // Pupil — bright core
        ctx.save();
        ctx.shadowColor = `hsl(${hue},70%,70%)`;
        ctx.shadowBlur = this._ss(15);
        ctx.fillStyle = `hsl(${hue},60%,75%)`;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(4.5 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        // Particle ring around pupil
        for (let i = 0; i < 8; i++) {
          const a = (Math.PI * 2 / 8) * i + t * 0.8;
          const pr = 8 * em.pupil_size;
          const ppx = px + Math.cos(a) * pr;
          const ppy = py + Math.sin(a) * pr * 0.8;
          ctx.fillStyle = `hsla(${hue + i * 10},60%,70%,${0.15 + 0.1 * Math.sin(t + i)})`;
          ctx.beginPath();
          ctx.arc(this._sx(ppx), this._sy(ppy), this._ss(1.2), 0, Math.PI * 2);
          ctx.fill();
        }

        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(this._sx(px - 1.5), this._sy(py - 1.5), this._ss(1.5), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Mouth — wispy trail
    const ms = this.mouth, mouthY = 248;
    const mouthW = 32 * ms.widthFactor;
    ctx.lineWidth = this._ss(1.5);
    // Multiple wispy passes
    for (let pass = 0; pass < 3; pass++) {
      const alpha = 0.25 - pass * 0.06;
      const hue = 260 + pass * 20;
      ctx.strokeStyle = `hsla(${hue},50%,60%,${alpha})`;
      ctx.beginPath();
      for (let i = 0; i <= 30; i++) {
        const frac = i / 30;
        const x = cx - mouthW + frac * mouthW * 2;
        const wave = Math.sin(frac * Math.PI * 2 + t * 2 + pass) * (2 + ms.openAmount * 8);
        const curve = Math.sin(frac * Math.PI) * (2 + em.mouth_curve * 6);
        const drift = Math.sin(t * 0.5 + pass) * 2;
        const y = mouthY - curve + wave + drift + pass * 2;
        if (i === 0) ctx.moveTo(this._sx(x), this._sy(y));
        else ctx.lineTo(this._sx(x), this._sy(y));
      }
      ctx.stroke();
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 23. ORIGAMI — Flat paper folds, angular minimal
// Complexity: geometry 3, effects: 1, animation: 1 = 5 → Starter ($5)
// ═══════════════════════════════════════════════════════════
export class OrigamiFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#f0ebe0";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const fold = "rgba(180,170,155,0.3)";
    const crease = "rgba(120,110,95,0.5)";
    const paper = "#e8e0d0";
    const shadow = "rgba(150,140,125,0.15)";

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Face — folded diamond shape from triangular panels
    const top: [number, number] = [cx, 40];
    const right: [number, number] = [cx + 110, 175];
    const bottom: [number, number] = [cx, 320];
    const left: [number, number] = [cx - 110, 175];
    const center: [number, number] = [cx, 175];

    // Left panel (slightly darker)
    ctx.fillStyle = shadow;
    ctx.beginPath();
    ctx.moveTo(this._sx(top[0]), this._sy(top[1]));
    ctx.lineTo(this._sx(left[0]), this._sy(left[1]));
    ctx.lineTo(this._sx(center[0]), this._sy(center[1]));
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = shadow;
    ctx.beginPath();
    ctx.moveTo(this._sx(left[0]), this._sy(left[1]));
    ctx.lineTo(this._sx(bottom[0]), this._sy(bottom[1]));
    ctx.lineTo(this._sx(center[0]), this._sy(center[1]));
    ctx.closePath();
    ctx.fill();

    // Right panel
    ctx.fillStyle = paper;
    ctx.beginPath();
    ctx.moveTo(this._sx(top[0]), this._sy(top[1]));
    ctx.lineTo(this._sx(right[0]), this._sy(right[1]));
    ctx.lineTo(this._sx(center[0]), this._sy(center[1]));
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = paper;
    ctx.beginPath();
    ctx.moveTo(this._sx(right[0]), this._sy(right[1]));
    ctx.lineTo(this._sx(bottom[0]), this._sy(bottom[1]));
    ctx.lineTo(this._sx(center[0]), this._sy(center[1]));
    ctx.closePath();
    ctx.fill();

    // Crease lines
    ctx.strokeStyle = crease;
    ctx.lineWidth = this._ss(1.2);
    ctx.beginPath();
    ctx.moveTo(this._sx(top[0]), this._sy(top[1]));
    ctx.lineTo(this._sx(bottom[0]), this._sy(bottom[1]));
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(this._sx(left[0]), this._sy(left[1]));
    ctx.lineTo(this._sx(right[0]), this._sy(right[1]));
    ctx.stroke();

    // Fold lines
    ctx.strokeStyle = fold;
    ctx.lineWidth = this._ss(0.8);
    ctx.setLineDash([this._ss(3), this._ss(3)]);
    ctx.beginPath();
    ctx.moveTo(this._sx(top[0]), this._sy(top[1]));
    ctx.lineTo(this._sx(left[0]), this._sy(left[1]));
    ctx.lineTo(this._sx(bottom[0]), this._sy(bottom[1]));
    ctx.lineTo(this._sx(right[0]), this._sy(right[1]));
    ctx.closePath();
    ctx.stroke();
    ctx.setLineDash([]);

    // Eyes — angular triangular shapes
    const eyeSpacing = 40, eyeY = 145;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 5;

      if (blink < 0.15) {
        ctx.strokeStyle = "#4a4238";
        ctx.lineWidth = this._ss(1.5);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 14), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 14), this._sy(eyeY));
        ctx.stroke();
      } else {
        const eyeH = 12 * blink;
        // Angular eye (diamond)
        ctx.fillStyle = "rgba(255,255,255,0.6)";
        ctx.strokeStyle = "#5a4a38";
        ctx.lineWidth = this._ss(1.2);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 16), this._sy(eyeY));
        ctx.lineTo(this._sx(ex), this._sy(eyeY - eyeH));
        ctx.lineTo(this._sx(ex + 16), this._sy(eyeY));
        ctx.lineTo(this._sx(ex), this._sy(eyeY + eyeH * 0.7));
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        // Inner fold line
        ctx.strokeStyle = fold;
        ctx.lineWidth = this._ss(0.6);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 16), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 16), this._sy(eyeY));
        ctx.stroke();

        // Pupil — small triangle
        ctx.fillStyle = "#3a3028";
        ctx.beginPath();
        const ps = 5 * em.pupil_size;
        ctx.moveTo(this._sx(px), this._sy(py - ps));
        ctx.lineTo(this._sx(px + ps * 0.8), this._sy(py + ps * 0.5));
        ctx.lineTo(this._sx(px - ps * 0.8), this._sy(py + ps * 0.5));
        ctx.closePath();
        ctx.fill();
      }
    }

    // Nose — small fold mark
    ctx.strokeStyle = crease;
    ctx.lineWidth = this._ss(1);
    ctx.beginPath();
    ctx.moveTo(this._sx(cx), this._sy(175));
    ctx.lineTo(this._sx(cx + 5), this._sy(195));
    ctx.lineTo(this._sx(cx - 3), this._sy(195));
    ctx.stroke();

    // Mouth — angular line
    const ms = this.mouth, mouthY = 235;
    const mouthW = 24 * ms.widthFactor;
    ctx.strokeStyle = "#5a4a38";
    ctx.lineWidth = this._ss(1.5);
    if (ms.openAmount < 0.05) {
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.lineTo(this._sx(cx), this._sy(mouthY - em.mouth_curve * 8));
      ctx.lineTo(this._sx(cx + mouthW), this._sy(mouthY));
      ctx.stroke();
    } else {
      const openH = ms.openAmount * 12;
      // Open mouth — diamond
      ctx.fillStyle = "rgba(90,70,50,0.2)";
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.lineTo(this._sx(cx), this._sy(mouthY - openH));
      ctx.lineTo(this._sx(cx + mouthW), this._sy(mouthY));
      ctx.lineTo(this._sx(cx), this._sy(mouthY + openH));
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 24. AURORA — Northern lights ribbons forming face
// Complexity: geometry 1, effects 3, animation 3 = 7 → Premium ($14)
// ═══════════════════════════════════════════════════════════
export class AuroraFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
    bgGrad.addColorStop(0, "#020810");
    bgGrad.addColorStop(1, "#050a18");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Aurora ribbons across the face area
    const ribbons = [
      { baseY: 80, hue: 130, amp: 20, freq: 0.8, speed: 0.4, alpha: 0.12, width: 40 },
      { baseY: 140, hue: 160, amp: 15, freq: 1.0, speed: 0.3, alpha: 0.1, width: 35 },
      { baseY: 200, hue: 100, amp: 25, freq: 0.6, speed: 0.5, alpha: 0.08, width: 45 },
      { baseY: 260, hue: 280, amp: 18, freq: 0.9, speed: 0.35, alpha: 0.1, width: 30 },
    ];
    for (const r of ribbons) {
      const grad = ctx.createLinearGradient(0, this._sy(r.baseY - r.width / 2), 0, this._sy(r.baseY + r.width / 2));
      grad.addColorStop(0, "transparent");
      grad.addColorStop(0.3, `hsla(${r.hue + Math.sin(t * 0.3) * 20},70%,55%,${r.alpha})`);
      grad.addColorStop(0.5, `hsla(${r.hue + Math.sin(t * 0.3) * 20},80%,60%,${r.alpha * 1.5})`);
      grad.addColorStop(0.7, `hsla(${r.hue + Math.sin(t * 0.3) * 20},70%,55%,${r.alpha})`);
      grad.addColorStop(1, "transparent");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.moveTo(this._sx(0), this._sy(r.baseY - r.width / 2));
      for (let x = 0; x <= REF_W; x += 4) {
        const wave = Math.sin(x * 0.01 * r.freq + t * r.speed) * r.amp;
        ctx.lineTo(this._sx(x), this._sy(r.baseY + wave - r.width / 2));
      }
      ctx.lineTo(this._sx(REF_W), this._sy(r.baseY + r.width / 2));
      for (let x = REF_W; x >= 0; x -= 4) {
        const wave = Math.sin(x * 0.01 * r.freq + t * r.speed + 0.5) * r.amp;
        ctx.lineTo(this._sx(x), this._sy(r.baseY + wave + r.width / 2));
      }
      ctx.closePath();
      ctx.fill();
    }

    // Faint stars
    for (let i = 0; i < 20; i++) {
      const sx = (i * 83 + 11) % REF_W;
      const sy = (i * 53 + 31) % REF_H;
      const tw = 0.3 + 0.4 * Math.abs(Math.sin(t * 0.8 + i));
      ctx.fillStyle = `rgba(200,220,255,${tw * 0.15})`;
      ctx.beginPath();
      ctx.arc(this._sx(sx), this._sy(sy), this._ss(0.8), 0, Math.PI * 2);
      ctx.fill();
    }

    // Eyes — bright aurora focus points
    const eyeSpacing = 50, eyeY = 138;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 10;
      const py = eyeY + es.gazeY * 7;
      const hue = side < 0 ? 130 : 280;

      if (blink < 0.15) {
        ctx.strokeStyle = `hsla(${hue},60%,60%,0.5)`;
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 16), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 16), this._sy(eyeY));
        ctx.stroke();
      } else {
        const eyeR = 16 * blink;
        // Glow halo
        const glow = ctx.createRadialGradient(
          this._sx(ex), this._sy(eyeY), 0,
          this._sx(ex), this._sy(eyeY), this._ss(eyeR + 10)
        );
        glow.addColorStop(0, `hsla(${hue},70%,60%,0.15)`);
        glow.addColorStop(1, "transparent");
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(eyeR + 10), 0, Math.PI * 2);
        ctx.fill();

        // Eye ring
        ctx.strokeStyle = `hsla(${hue},60%,65%,0.5)`;
        ctx.lineWidth = this._ss(1.2);
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(15), this._ss(eyeR), 0, 0, Math.PI * 2);
        ctx.stroke();

        // Pupil
        ctx.save();
        ctx.shadowColor = `hsl(${hue},80%,70%)`;
        ctx.shadowBlur = this._ss(12);
        ctx.fillStyle = `hsl(${hue},70%,80%)`;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(4 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(this._sx(px - 1), this._sy(py - 1), this._ss(1.5), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Mouth — aurora wave
    const ms = this.mouth, mouthY = 248;
    const mouthW = 35 * ms.widthFactor;
    for (let pass = 0; pass < 2; pass++) {
      const hue = 130 + pass * 150;
      ctx.strokeStyle = `hsla(${hue},60%,60%,${0.4 - pass * 0.1})`;
      ctx.lineWidth = this._ss(1.5 - pass * 0.3);
      ctx.beginPath();
      for (let i = 0; i <= 25; i++) {
        const frac = i / 25;
        const x = cx - mouthW + frac * mouthW * 2;
        const curve = Math.sin(frac * Math.PI) * (2 + em.mouth_curve * 8);
        const wave = ms.openAmount > 0.05 ? Math.sin(frac * Math.PI * 3 + t * 3 + pass) * ms.openAmount * 8 : 0;
        const y = mouthY - curve + wave + pass * 3;
        if (i === 0) ctx.moveTo(this._sx(x), this._sy(y));
        else ctx.lineTo(this._sx(x), this._sy(y));
      }
      ctx.stroke();
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 25. ART DECO — Golden geometric lines, 1920s aesthetic
// Complexity: geometry 3, effects 2, animation 1 = 6 → Pro ($9)
// ═══════════════════════════════════════════════════════════
export class DecoFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0a0810";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const gold = "#d4aa50";
    const goldDim = "rgba(212,170,80,0.3)";
    const goldBright = "#f0cc70";

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Art deco frame — symmetric geometric border
    ctx.strokeStyle = gold;
    ctx.lineWidth = this._ss(2);
    // Outer frame
    ctx.beginPath();
    ctx.moveTo(this._sx(cx), this._sy(20));
    ctx.lineTo(this._sx(cx + 80), this._sy(50));
    ctx.lineTo(this._sx(cx + 120), this._sy(120));
    ctx.lineTo(this._sx(cx + 120), this._sy(250));
    ctx.lineTo(this._sx(cx + 80), this._sy(320));
    ctx.lineTo(this._sx(cx), this._sy(340));
    ctx.lineTo(this._sx(cx - 80), this._sy(320));
    ctx.lineTo(this._sx(cx - 120), this._sy(250));
    ctx.lineTo(this._sx(cx - 120), this._sy(120));
    ctx.lineTo(this._sx(cx - 80), this._sy(50));
    ctx.closePath();
    ctx.stroke();

    // Inner decorative frame
    ctx.strokeStyle = goldDim;
    ctx.lineWidth = this._ss(1);
    ctx.beginPath();
    ctx.moveTo(this._sx(cx), this._sy(35));
    ctx.lineTo(this._sx(cx + 70), this._sy(60));
    ctx.lineTo(this._sx(cx + 108), this._sy(125));
    ctx.lineTo(this._sx(cx + 108), this._sy(245));
    ctx.lineTo(this._sx(cx + 70), this._sy(310));
    ctx.lineTo(this._sx(cx), this._sy(328));
    ctx.lineTo(this._sx(cx - 70), this._sy(310));
    ctx.lineTo(this._sx(cx - 108), this._sy(245));
    ctx.lineTo(this._sx(cx - 108), this._sy(125));
    ctx.lineTo(this._sx(cx - 70), this._sy(60));
    ctx.closePath();
    ctx.stroke();

    // Decorative fan lines at top
    ctx.strokeStyle = goldDim;
    ctx.lineWidth = this._ss(0.6);
    for (let i = -4; i <= 4; i++) {
      ctx.beginPath();
      ctx.moveTo(this._sx(cx), this._sy(20));
      ctx.lineTo(this._sx(cx + i * 15), this._sy(70));
      ctx.stroke();
    }

    // Horizontal deco bars
    ctx.strokeStyle = goldDim;
    ctx.lineWidth = this._ss(0.8);
    for (const y of [90, 290]) {
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - 100), this._sy(y));
      ctx.lineTo(this._sx(cx + 100), this._sy(y));
      ctx.stroke();
      // Small diamonds at ends
      for (const side of [-1, 1]) {
        const dx = cx + side * 100;
        ctx.fillStyle = gold;
        ctx.beginPath();
        ctx.moveTo(this._sx(dx), this._sy(y - 4));
        ctx.lineTo(this._sx(dx + 4), this._sy(y));
        ctx.lineTo(this._sx(dx), this._sy(y + 4));
        ctx.lineTo(this._sx(dx - 4), this._sy(y));
        ctx.closePath();
        ctx.fill();
      }
    }

    // Eyes — ornate arched shapes
    const eyeSpacing = 48, eyeY = 140;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 5;

      if (blink < 0.15) {
        ctx.strokeStyle = gold;
        ctx.lineWidth = this._ss(1.5);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 18), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 18), this._sy(eyeY));
        ctx.stroke();
        // Decorative dot at center
        ctx.fillStyle = gold;
        ctx.beginPath();
        ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(2), 0, Math.PI * 2);
        ctx.fill();
      } else {
        const eyeH = 16 * blink;
        // Arch top
        ctx.strokeStyle = gold;
        ctx.lineWidth = this._ss(1.5);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 20), this._sy(eyeY));
        ctx.quadraticCurveTo(this._sx(ex), this._sy(eyeY - eyeH), this._sx(ex + 20), this._sy(eyeY));
        ctx.stroke();
        // Flat bottom
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 20), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 20), this._sy(eyeY));
        ctx.stroke();
        // Decorative rays above
        ctx.strokeStyle = goldDim;
        ctx.lineWidth = this._ss(0.5);
        for (let i = -2; i <= 2; i++) {
          ctx.beginPath();
          ctx.moveTo(this._sx(ex + i * 5), this._sy(eyeY - eyeH + 2));
          ctx.lineTo(this._sx(ex + i * 7), this._sy(eyeY - eyeH - 6));
          ctx.stroke();
        }

        // Iris
        ctx.fillStyle = goldDim;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(8 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        // Pupil
        ctx.fillStyle = goldBright;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(4 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(this._sx(px - 1), this._sy(py - 1), this._ss(1.5), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Nose — thin gold line
    ctx.strokeStyle = goldDim;
    ctx.lineWidth = this._ss(0.8);
    ctx.beginPath();
    ctx.moveTo(this._sx(cx), this._sy(170));
    ctx.lineTo(this._sx(cx), this._sy(198));
    ctx.stroke();
    ctx.fillStyle = gold;
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(198), this._ss(1.5), 0, Math.PI * 2);
    ctx.fill();

    // Mouth — art deco curve with ornaments
    const ms = this.mouth, mouthY = 248;
    const mouthW = 32 * ms.widthFactor;
    ctx.strokeStyle = gold;
    ctx.lineWidth = this._ss(1.5);
    if (ms.openAmount < 0.05) {
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY - em.mouth_curve * 10), this._sx(cx + mouthW), this._sy(mouthY));
      ctx.stroke();
      // End ornaments
      for (const side of [-1, 1]) {
        ctx.fillStyle = gold;
        ctx.beginPath();
        ctx.arc(this._sx(cx + side * mouthW), this._sy(mouthY), this._ss(2), 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      const openH = ms.openAmount * 14;
      // Ornate open mouth
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY - openH), this._sx(cx + mouthW), this._sy(mouthY));
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY + openH), this._sx(cx + mouthW), this._sy(mouthY));
      ctx.stroke();
      // Fill
      ctx.fillStyle = "rgba(212,170,80,0.08)";
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY - openH), this._sx(cx + mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY + openH), this._sx(cx - mouthW), this._sy(mouthY));
      ctx.fill();
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 26. TRIBAL — Carved wood mask, bold geometric patterns
// Complexity: geometry 3, effects 1, animation 2 = 6 → Pro ($9)
// ═══════════════════════════════════════════════════════════
export class TribalFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#120a04";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;
    const wood = "#8a5a28";
    const woodLight = "#b87830";
    const woodDark = "#4a2a10";
    const carve = "#2a1808";
    const paint = "#cc3020";

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Mask shape — rounded trapezoid
    const maskGrad = ctx.createLinearGradient(this._sx(cx - 100), 0, this._sx(cx + 100), 0);
    maskGrad.addColorStop(0, woodDark);
    maskGrad.addColorStop(0.3, wood);
    maskGrad.addColorStop(0.5, woodLight);
    maskGrad.addColorStop(0.7, wood);
    maskGrad.addColorStop(1, woodDark);
    ctx.fillStyle = maskGrad;
    ctx.beginPath();
    ctx.moveTo(this._sx(cx - 70), this._sy(40));
    ctx.lineTo(this._sx(cx + 70), this._sy(40));
    ctx.quadraticCurveTo(this._sx(cx + 120), this._sy(80), this._sx(cx + 115), this._sy(160));
    ctx.lineTo(this._sx(cx + 100), this._sy(250));
    ctx.quadraticCurveTo(this._sx(cx + 80), this._sy(320), this._sx(cx), this._sy(335));
    ctx.quadraticCurveTo(this._sx(cx - 80), this._sy(320), this._sx(cx - 100), this._sy(250));
    ctx.lineTo(this._sx(cx - 115), this._sy(160));
    ctx.quadraticCurveTo(this._sx(cx - 120), this._sy(80), this._sx(cx - 70), this._sy(40));
    ctx.fill();

    // Carved border
    ctx.strokeStyle = carve;
    ctx.lineWidth = this._ss(3);
    ctx.stroke();

    // Forehead pattern — zigzag bands
    ctx.strokeStyle = paint;
    ctx.lineWidth = this._ss(2);
    for (const rowY of [60, 75]) {
      ctx.beginPath();
      for (let i = -5; i <= 5; i++) {
        const x = cx + i * 14;
        const y = rowY + (i % 2 === 0 ? 0 : 8);
        if (i === -5) ctx.moveTo(this._sx(x), this._sy(y));
        else ctx.lineTo(this._sx(x), this._sy(y));
      }
      ctx.stroke();
    }

    // Eyes — large concentric shapes
    const eyeSpacing = 45, eyeY = 145;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 5;

      // Carved eye socket — concentric shapes
      ctx.fillStyle = carve;
      ctx.beginPath();
      ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(28), this._ss(22), 0, 0, Math.PI * 2);
      ctx.fill();

      // Paint ring
      ctx.strokeStyle = paint;
      ctx.lineWidth = this._ss(2.5);
      ctx.beginPath();
      ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(26), this._ss(20), 0, 0, Math.PI * 2);
      ctx.stroke();

      if (blink < 0.15) {
        ctx.strokeStyle = woodLight;
        ctx.lineWidth = this._ss(2.5);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 22), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 22), this._sy(eyeY));
        ctx.stroke();
      } else {
        const eyeH = 14 * blink;
        // Inner eye
        ctx.fillStyle = "#1a0a04";
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(18), this._ss(eyeH), 0, 0, Math.PI * 2);
        ctx.fill();

        // Pupil — glowing ember
        const flicker = 0.8 + 0.2 * Math.sin(t * 5 + side * 3);
        ctx.save();
        ctx.shadowColor = "#ff4400";
        ctx.shadowBlur = this._ss(10 * flicker);
        ctx.fillStyle = lerpColor("#cc3300", "#ff6600", flicker);
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(5 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        ctx.fillStyle = "#ffaa44";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(2), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Nose — carved triangular
    ctx.fillStyle = carve;
    ctx.beginPath();
    ctx.moveTo(this._sx(cx), this._sy(175));
    ctx.lineTo(this._sx(cx + 12), this._sy(205));
    ctx.lineTo(this._sx(cx - 12), this._sy(205));
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = paint;
    ctx.lineWidth = this._ss(1.5);
    ctx.stroke();

    // Mouth — wide carved slot
    const ms = this.mouth, mouthY = 260;
    const mouthW = 38 * ms.widthFactor;
    const openH = Math.max(8, ms.openAmount * 20 + 8);
    ctx.fillStyle = carve;
    ctx.beginPath();
    ctx.roundRect(this._sx(cx - mouthW), this._sy(mouthY - openH / 2), this._ss(mouthW * 2), this._ss(openH), this._ss(4));
    ctx.fill();

    // Teeth — carved ridges
    const teethCount = 6;
    ctx.fillStyle = woodLight;
    for (let i = 0; i < teethCount; i++) {
      const tx = cx - mouthW + 8 + i * ((mouthW * 2 - 16) / (teethCount - 1));
      ctx.beginPath();
      ctx.moveTo(this._sx(tx - 4), this._sy(mouthY - openH / 2));
      ctx.lineTo(this._sx(tx), this._sy(mouthY - openH / 2 + 6));
      ctx.lineTo(this._sx(tx + 4), this._sy(mouthY - openH / 2));
      ctx.fill();
    }

    // Paint border around mouth
    ctx.strokeStyle = paint;
    ctx.lineWidth = this._ss(2);
    ctx.beginPath();
    ctx.roundRect(this._sx(cx - mouthW), this._sy(mouthY - openH / 2), this._ss(mouthW * 2), this._ss(openH), this._ss(4));
    ctx.stroke();

    // Cheek patterns — carved parallel lines
    for (const side of [-1, 1]) {
      ctx.strokeStyle = carve;
      ctx.lineWidth = this._ss(1.5);
      for (let i = 0; i < 3; i++) {
        const sx = cx + side * 70;
        ctx.beginPath();
        ctx.moveTo(this._sx(sx), this._sy(180 + i * 10));
        ctx.lineTo(this._sx(sx + side * 25), this._sy(185 + i * 10));
        ctx.stroke();
      }
    }
  }
}
