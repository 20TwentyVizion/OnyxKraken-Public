/**
 * AgentFace Style Collection — Alternative face renderers.
 * Each extends FaceRenderer and overrides only the draw() method,
 * inheriting all animation logic (blink, gaze, emotion, speech).
 */
import { FaceRenderer, lerpColor, REF_W, REF_H } from "./faceRenderer";

// ═══════════════════════════════════════════════════════════
// 1. MINIMAL — Clean zen-like face, circles + lines
// ═══════════════════════════════════════════════════════════
export class MinimalFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0a0a0f";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2;
    const es = this.eye;
    const em = this.emotion;
    const pulse = 0.5 + 0.5 * Math.sin(this.pulse);

    let blink = 1.0;
    if (es.isBlinking) {
      blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    }
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    const accent = "#e0e0e0";
    const dim = "#444444";

    ctx.strokeStyle = lerpColor("#1a1a22", "#2a2a35", pulse * 0.5);
    ctx.lineWidth = this._ss(1.5);
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(REF_H / 2), this._ss(140), 0, Math.PI * 2);
    ctx.stroke();

    const eyeSpacing = 50;
    const eyeY = 140;
    const eyeR = 18 * Math.max(blink, 0.05) * (1 + em.eye_widen * 0.3);
    const pupilR = 8 * em.pupil_size;

    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 6;

      if (blink < 0.15) {
        ctx.strokeStyle = dim;
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 14), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 14), this._sy(eyeY));
        ctx.stroke();
      } else {
        ctx.strokeStyle = accent;
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(eyeR), 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = accent;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(pupilR), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    if (Math.abs(em.brow_raise) > 0.05) {
      ctx.strokeStyle = lerpColor(dim, accent, 0.3);
      ctx.lineWidth = this._ss(1);
      for (const side of [-1, 1]) {
        const ex = cx + side * eyeSpacing;
        const by = eyeY - 30 - em.brow_raise * 10;
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 16), this._sy(by + em.brow_raise * 3 * side));
        ctx.lineTo(this._sx(ex + 16), this._sy(by - em.brow_raise * 3 * side));
        ctx.stroke();
      }
    }

    const ms = this.mouth;
    const mouthY = 230;
    const mouthW = 35 * ms.widthFactor;

    if (ms.openAmount < 0.05) {
      ctx.strokeStyle = lerpColor(dim, accent, 0.4 + em.mouth_curve * 0.3);
      ctx.lineWidth = this._ss(2);
      ctx.beginPath();
      for (let i = 0; i <= 20; i++) {
        const t = i / 20;
        const x = cx - mouthW + t * mouthW * 2;
        const curve = Math.sin(t * Math.PI) * (2 + em.mouth_curve * 6);
        if (i === 0) ctx.moveTo(this._sx(x), this._sy(mouthY - curve));
        else ctx.lineTo(this._sx(x), this._sy(mouthY - curve));
      }
      ctx.stroke();
    } else {
      const openH = ms.openAmount * 20;
      ctx.strokeStyle = accent;
      ctx.lineWidth = this._ss(2);
      ctx.beginPath();
      ctx.ellipse(this._sx(cx), this._sy(mouthY), this._ss(mouthW), this._ss(openH), 0, 0, Math.PI * 2);
      ctx.stroke();
    }

    ctx.fillStyle = dim;
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(190), this._ss(2), 0, Math.PI * 2);
    ctx.fill();
  }
}

// ═══════════════════════════════════════════════════════════
// 2. RETRO TERMINAL — Green-on-black, blocky pixel aesthetic
// ═══════════════════════════════════════════════════════════
export class RetroFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#001200";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2;
    const es = this.eye;
    const em = this.emotion;
    const pulse = 0.5 + 0.5 * Math.sin(this.pulse);

    let blink = 1.0;
    if (es.isBlinking) {
      blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    }
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    const green = "#33ff33";
    const darkGreen = "#115511";
    const px = (v: number) => Math.round(v / 4) * 4;

    const drawPixelRect = (x: number, y: number, w: number, h: number, color: string) => {
      ctx.fillStyle = color;
      ctx.fillRect(this._sx(px(x)), this._sy(px(y)), this._ss(px(w) || 4), this._ss(px(h) || 4));
    };

    drawPixelRect(40, 24, 320, 312, darkGreen);
    ctx.strokeStyle = green;
    ctx.lineWidth = this._ss(2);
    ctx.strokeRect(this._sx(40), this._sy(24), this._ss(320), this._ss(312));

    ctx.fillStyle = green;
    ctx.font = `${Math.max(8, Math.round(this._ss(10)))}px Consolas, monospace`;
    ctx.textAlign = "center";
    ctx.fillText("> AGENT_FACE v1.0", this._sx(cx), this._sy(46));

    const eyeSpacing = 56;
    const eyeY = 130;
    const eyeW = 40;
    const eyeH = Math.max(4, 48 * blink);

    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing - eyeW / 2;
      const ey = eyeY - eyeH / 2;

      drawPixelRect(ex - 4, ey - 4, eyeW + 8, eyeH + 8, "#003300");

      if (blink < 0.15) {
        drawPixelRect(ex, eyeY - 2, eyeW, 4, green);
      } else {
        ctx.strokeStyle = green;
        ctx.lineWidth = this._ss(2);
        ctx.strokeRect(this._sx(px(ex)), this._sy(px(ey)), this._ss(px(eyeW)), this._ss(px(eyeH)));

        const pupilSize = 12 * em.pupil_size;
        const ppx = cx + side * eyeSpacing + es.gazeX * 10 - pupilSize / 2;
        const ppy = eyeY + es.gazeY * 8 - pupilSize / 2;
        drawPixelRect(ppx, ppy, pupilSize, pupilSize, green);

        const glowS = 4;
        drawPixelRect(ppx + pupilSize / 2 - glowS / 2, ppy + pupilSize / 2 - glowS / 2, glowS, glowS, "#aaffaa");
      }
    }

    const ms = this.mouth;
    const mouthY = 250;
    const mouthW = 50 * ms.widthFactor;

    if (ms.openAmount < 0.05) {
      const curveOffset = em.mouth_curve * 4;
      drawPixelRect(cx - mouthW / 2, mouthY - curveOffset, mouthW, 4, green);
    } else {
      const openH = ms.openAmount * 24;
      ctx.strokeStyle = green;
      ctx.lineWidth = this._ss(2);
      ctx.strokeRect(
        this._sx(px(cx - mouthW / 2)), this._sy(px(mouthY - openH / 2)),
        this._ss(px(mouthW)), this._ss(px(openH))
      );
      drawPixelRect(cx - mouthW / 2 + 4, mouthY - openH / 2 + 4, mouthW - 8, openH - 8, "#001200");
    }

    ctx.fillStyle = "rgba(0,0,0,0.12)";
    const step = Math.max(3, Math.round(3 / Math.max(this.s, 0.3)));
    for (let y = Math.round(this._sy(24)); y < this._sy(336); y += step) {
      ctx.fillRect(this._sx(40), y, this._ss(320), 1);
    }

    if (Math.sin(performance.now() / 1000 * 3) > 0) {
      drawPixelRect(cx + 80, 300, 8, 12, green);
    }

    ctx.fillStyle = lerpColor(darkGreen, green, pulse);
    ctx.font = `${Math.max(7, Math.round(this._ss(9)))}px Consolas, monospace`;
    ctx.textAlign = "center";
    ctx.fillText(`[EMO:${this.emotionName.toUpperCase()}] [GAZE:${es.gazeX.toFixed(1)},${es.gazeY.toFixed(1)}]`, this._sx(cx), this._sy(326));
  }
}

// ═══════════════════════════════════════════════════════════
// 3. NEON WIREFRAME — Outlines only, heavy glow, Tron-like
// ═══════════════════════════════════════════════════════════
export class NeonFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#020008";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2;
    const es = this.eye;
    const em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) {
      blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    }
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    const hue = (t * 20) % 360;
    const accent1 = `hsl(${hue}, 100%, 60%)`;
    const accent2 = `hsl(${(hue + 120) % 360}, 100%, 60%)`;
    const accent3 = `hsl(${(hue + 240) % 360}, 100%, 60%)`;
    const dimAccent = `hsl(${hue}, 60%, 25%)`;

    const glowLine = (color: string, lineW: number, drawFn: () => void) => {
      ctx.save();
      ctx.shadowColor = color;
      ctx.shadowBlur = this._ss(12);
      ctx.strokeStyle = color;
      ctx.lineWidth = this._ss(lineW);
      drawFn();
      ctx.restore();
      ctx.strokeStyle = "#ffffff";
      ctx.globalAlpha = 0.4;
      ctx.lineWidth = this._ss(lineW * 0.5);
      drawFn();
      ctx.globalAlpha = 1;
    };

    const hexR = 150;
    const hexCy = REF_H / 2;
    glowLine(accent1, 2, () => {
      ctx.beginPath();
      for (let i = 0; i <= 6; i++) {
        const angle = (Math.PI / 3) * i - Math.PI / 2;
        const x = cx + hexR * Math.cos(angle);
        const y = hexCy + hexR * 0.9 * Math.sin(angle);
        if (i === 0) ctx.moveTo(this._sx(x), this._sy(y));
        else ctx.lineTo(this._sx(x), this._sy(y));
      }
      ctx.closePath();
      ctx.stroke();
    });

    glowLine(dimAccent, 1, () => {
      ctx.beginPath();
      for (let i = 0; i <= 6; i++) {
        const angle = (Math.PI / 3) * i - Math.PI / 2 + t * 0.1;
        const x = cx + 100 * Math.cos(angle);
        const y = hexCy + 90 * Math.sin(angle);
        if (i === 0) ctx.moveTo(this._sx(x), this._sy(y));
        else ctx.lineTo(this._sx(x), this._sy(y));
      }
      ctx.closePath();
      ctx.stroke();
    });

    const eyeSpacing = 55;
    const eyeY = 135;
    const eyeSize = 28 * Math.max(blink, 0.08);

    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 10;
      const py = eyeY + es.gazeY * 8;
      const col = side < 0 ? accent2 : accent3;

      if (blink < 0.15) {
        glowLine(col, 2, () => {
          ctx.beginPath();
          ctx.moveTo(this._sx(ex - 20), this._sy(eyeY));
          ctx.lineTo(this._sx(ex + 20), this._sy(eyeY));
          ctx.stroke();
        });
      } else {
        glowLine(col, 2, () => {
          ctx.beginPath();
          ctx.moveTo(this._sx(ex), this._sy(eyeY - eyeSize));
          ctx.lineTo(this._sx(ex + eyeSize * 0.8), this._sy(eyeY));
          ctx.lineTo(this._sx(ex), this._sy(eyeY + eyeSize));
          ctx.lineTo(this._sx(ex - eyeSize * 0.8), this._sy(eyeY));
          ctx.closePath();
          ctx.stroke();
        });

        const pr = 6 * em.pupil_size;
        ctx.save();
        ctx.shadowColor = col;
        ctx.shadowBlur = this._ss(15);
        ctx.fillStyle = col;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(pr), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(pr * 0.3), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    const ms = this.mouth;
    const mouthY = 245;
    const mouthW = 40 * ms.widthFactor;

    glowLine(accent1, 2, () => {
      ctx.beginPath();
      for (let i = 0; i <= 30; i++) {
        const frac = i / 30;
        const x = cx - mouthW + frac * mouthW * 2;
        const baseY = mouthY - Math.sin(frac * Math.PI) * (2 + em.mouth_curve * 8);
        const openWave = ms.openAmount > 0.05 ? Math.sin(frac * Math.PI * 4 + t * 8) * ms.openAmount * 10 : 0;
        const y = baseY - openWave;
        if (i === 0) ctx.moveTo(this._sx(x), this._sy(y));
        else ctx.lineTo(this._sx(x), this._sy(y));
      }
      ctx.stroke();
    });

    ctx.strokeStyle = dimAccent;
    ctx.lineWidth = this._ss(0.5);
    ctx.setLineDash([this._ss(3), this._ss(6)]);
    for (const side of [-1, 1]) {
      ctx.beginPath();
      ctx.moveTo(this._sx(cx + side * eyeSpacing), this._sy(eyeY + 30));
      ctx.lineTo(this._sx(cx), this._sy(mouthY - 15));
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }
}

// ═══════════════════════════════════════════════════════════
// 4. ORGANIC — Soft, rounded, warm tones, human-like
// ═══════════════════════════════════════════════════════════
export class OrganicFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0f0a08";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2;
    const es = this.eye;
    const em = this.emotion;
    const pulse = 0.5 + 0.5 * Math.sin(this.pulse);

    let blink = 1.0;
    if (es.isBlinking) {
      blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    }
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    const warm = "#e8a060";
    const warmDim = "#5a3020";
    const warmBright = "#ffe0c0";

    const faceRx = 135;
    const faceRy = 155;
    const faceCy = REF_H / 2 + 5;

    const grad = ctx.createRadialGradient(
      this._sx(cx), this._sy(faceCy - 20), 0,
      this._sx(cx), this._sy(faceCy), this._ss(faceRy)
    );
    grad.addColorStop(0, "#1c1210");
    grad.addColorStop(0.7, "#140c08");
    grad.addColorStop(1, "#0f0a08");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(faceCy), this._ss(faceRx), this._ss(faceRy), 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = lerpColor(warmDim, warm, pulse * 0.3);
    ctx.lineWidth = this._ss(2);
    ctx.stroke();

    const eyeSpacing = 48;
    const eyeY = 135;
    const eyeW = 28;
    const eyeH = 18 * Math.max(blink, 0.05);

    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 10;
      const py = eyeY + es.gazeY * 6;

      if (blink < 0.15) {
        ctx.strokeStyle = warm;
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - eyeW), this._sy(eyeY));
        ctx.quadraticCurveTo(this._sx(ex), this._sy(eyeY + 3), this._sx(ex + eyeW), this._sy(eyeY));
        ctx.stroke();
      } else {
        ctx.fillStyle = "#201510";
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - eyeW), this._sy(eyeY));
        ctx.quadraticCurveTo(this._sx(ex), this._sy(eyeY - eyeH), this._sx(ex + eyeW), this._sy(eyeY));
        ctx.quadraticCurveTo(this._sx(ex), this._sy(eyeY + eyeH), this._sx(ex - eyeW), this._sy(eyeY));
        ctx.fill();
        ctx.strokeStyle = warm;
        ctx.lineWidth = this._ss(1.5);
        ctx.stroke();

        const irisR = 10 * em.pupil_size;
        const irisGrad = ctx.createRadialGradient(
          this._sx(px), this._sy(py), 0,
          this._sx(px), this._sy(py), this._ss(irisR)
        );
        irisGrad.addColorStop(0, warmBright);
        irisGrad.addColorStop(0.4, warm);
        irisGrad.addColorStop(1, warmDim);
        ctx.fillStyle = irisGrad;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(irisR), 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "#0a0604";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(4 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = warmBright;
        ctx.beginPath();
        ctx.arc(this._sx(px - 3), this._sy(py - 3), this._ss(2), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    if (Math.abs(em.brow_raise) > 0.03) {
      ctx.strokeStyle = lerpColor(warmDim, warm, 0.5);
      ctx.lineWidth = this._ss(2.5);
      for (const side of [-1, 1]) {
        const ex = cx + side * eyeSpacing;
        const by = eyeY - 28 - em.brow_raise * 12;
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 22), this._sy(by + 4 + em.brow_raise * 4 * side));
        ctx.quadraticCurveTo(this._sx(ex), this._sy(by - 4), this._sx(ex + 22), this._sy(by + 4 - em.brow_raise * 4 * side));
        ctx.stroke();
      }
    }

    ctx.fillStyle = warmDim;
    ctx.beginPath();
    ctx.moveTo(this._sx(cx - 5), this._sy(192));
    ctx.quadraticCurveTo(this._sx(cx), this._sy(204), this._sx(cx + 5), this._sy(192));
    ctx.fill();

    const ms = this.mouth;
    const mouthY = 240;
    const mouthW = 30 * ms.widthFactor;

    if (ms.openAmount < 0.05) {
      ctx.strokeStyle = lerpColor(warmDim, warm, 0.6);
      ctx.lineWidth = this._ss(2);
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY - em.mouth_curve * 10), this._sx(cx + mouthW), this._sy(mouthY));
      ctx.stroke();
      ctx.strokeStyle = lerpColor(warmDim, warm, 0.3);
      ctx.lineWidth = this._ss(1.5);
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW * 0.7), this._sy(mouthY + 2));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY + 6 + em.mouth_curve * 3), this._sx(cx + mouthW * 0.7), this._sy(mouthY + 2));
      ctx.stroke();
    } else {
      const openH = ms.openAmount * 18;
      const mGrad = ctx.createRadialGradient(
        this._sx(cx), this._sy(mouthY), 0,
        this._sx(cx), this._sy(mouthY), this._ss(mouthW)
      );
      mGrad.addColorStop(0, "#0a0604");
      mGrad.addColorStop(1, "#150c08");
      ctx.fillStyle = mGrad;
      ctx.beginPath();
      ctx.ellipse(this._sx(cx), this._sy(mouthY), this._ss(mouthW), this._ss(openH), 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = warm;
      ctx.lineWidth = this._ss(2);
      ctx.stroke();
    }

    ctx.fillStyle = "rgba(200,100,50,0.04)";
    ctx.beginPath();
    ctx.arc(this._sx(cx - 80), this._sy(200), this._ss(30), 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(this._sx(cx + 80), this._sy(200), this._ss(30), 0, Math.PI * 2);
    ctx.fill();
  }
}

// ═══════════════════════════════════════════════════════════
// 5. GLITCH — RGB split, digital artifacts, distortion
// ═══════════════════════════════════════════════════════════
export class GlitchFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#080808";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2;
    const es = this.eye;
    const em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) {
      blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    }
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    const glitchActive = Math.sin(t * 7) > 0.85;
    const gOx = glitchActive ? (Math.random() - 0.5) * 8 : 0;
    const gOy = glitchActive ? (Math.random() - 0.5) * 4 : 0;

    const rOx = 3 + Math.sin(t * 2) * 2;
    const bOx = -3 - Math.sin(t * 2) * 2;

    const passes = [
      { color: "#ff0000", ox: rOx, oy: 0, alpha: 0.4 },
      { color: "#00ff00", ox: 0, oy: 0, alpha: 0.5 },
      { color: "#0000ff", ox: bOx, oy: 0, alpha: 0.4 },
    ];

    for (const pass of passes) {
      ctx.save();
      ctx.globalAlpha = pass.alpha;

      const oox = pass.ox + gOx;
      const ooy = pass.oy + gOy;

      ctx.strokeStyle = pass.color;
      ctx.lineWidth = this._ss(2);
      ctx.strokeRect(this._sx(50 + oox), this._sy(30 + ooy), this._ss(300), this._ss(300));

      const eyeSpacing = 56;
      const eyeY = 130;
      const eyeW = 44;
      const eyeH = Math.max(4, 44 * blink);

      for (const side of [-1, 1]) {
        const ex = cx + side * eyeSpacing - eyeW / 2 + oox;
        const ey = eyeY - eyeH / 2 + ooy;

        if (blink < 0.15) {
          ctx.fillStyle = pass.color;
          ctx.fillRect(this._sx(ex), this._sy(eyeY - 2 + ooy), this._ss(eyeW), this._ss(4));
        } else {
          ctx.strokeStyle = pass.color;
          ctx.strokeRect(this._sx(ex), this._sy(ey), this._ss(eyeW), this._ss(eyeH));

          const ppx = cx + side * eyeSpacing + es.gazeX * 12 + oox;
          const ppy = eyeY + es.gazeY * 8 + ooy;
          const ps = 8 * em.pupil_size;

          ctx.beginPath();
          ctx.moveTo(this._sx(ppx - ps), this._sy(ppy));
          ctx.lineTo(this._sx(ppx + ps), this._sy(ppy));
          ctx.moveTo(this._sx(ppx), this._sy(ppy - ps));
          ctx.lineTo(this._sx(ppx), this._sy(ppy + ps));
          ctx.stroke();
        }
      }

      const ms = this.mouth;
      const mouthY = 250 + ooy;
      const mouthW = 50 * ms.widthFactor;
      const segments = 12;

      ctx.beginPath();
      for (let i = 0; i <= segments; i++) {
        const frac = i / segments;
        const x = cx - mouthW + frac * mouthW * 2 + oox;
        const jitter = glitchActive ? (Math.random() - 0.5) * 6 : 0;
        const curve = Math.sin(frac * Math.PI) * (3 + em.mouth_curve * 8);
        const openOffset = ms.openAmount > 0.05 ? Math.sin(frac * Math.PI) * ms.openAmount * 20 : 0;
        const y = mouthY - curve - openOffset + jitter;
        if (i === 0) ctx.moveTo(this._sx(x), this._sy(y));
        else ctx.lineTo(this._sx(x), this._sy(y));
      }
      ctx.stroke();

      ctx.restore();
    }

    if (glitchActive) {
      for (let i = 0; i < 3; i++) {
        const barY = Math.random() * h;
        const barH = 2 + Math.random() * 4;
        const barX = Math.random() * w * 0.3;
        ctx.fillStyle = `rgba(${Math.random() > 0.5 ? 255 : 0},${Math.random() > 0.5 ? 255 : 0},${Math.random() > 0.5 ? 255 : 0},0.15)`;
        ctx.fillRect(barX, barY, w - barX * 2, barH);
      }
    }

    ctx.fillStyle = "rgba(255,255,255,0.02)";
    for (let i = 0; i < 40; i++) {
      const nx = Math.random() * w;
      const ny = Math.random() * h;
      ctx.fillRect(nx, ny, 2, 1);
    }

    ctx.fillStyle = "rgba(0,0,0,0.08)";
    for (let y = 0; y < h; y += 3) {
      ctx.fillRect(0, y, w, 1);
    }
  }
}

// ─── V2 Styles (new originals) ───────────────────────────
import { ConstellationFace, CircuitFace, EmojiFace, VaporFace, SketchFace } from "./faceStylesV2";
import { HologramFace, PixelFace, PlasmaFace, GeometricFace, AsciiFace } from "./faceStylesV2b";
// ─── V3 Styles (batch 3) ────────────────────────────────
import { WatercolorFace, SteampunkFace, InfraredFace, BlueprintFace, StainedGlassFace } from "./faceStylesV3";
import { NebulFace, OrigamiFace, AuroraFace, DecoFace, TribalFace } from "./faceStylesV3b";
// ─── V4 Styles (Masterwork & Legendary) ─────────────────
import { PhoenixFace, ChromeFace, CyberneticFace } from "./faceStylesV4";
import { DeepSeaFace, SynthwaveFace, EtherealFace } from "./faceStylesV4b";
import { type ComplexityScore, type PriceTier, calculatePrice } from "./pricing";

// ═══════════════════════════════════════════════════════════
// FACE STYLE CATALOG
//
// Pricing is driven by complexity scoring:
//   geometry  (1-3): basic shapes → curves → complex mesh/paths
//   effects   (1-3): solid fills → glow/gradients → particles/distortion/multi-pass
//   animation (1-3): base engine only → color cycling/pulse → heavy per-frame FX
//
// Total maps to tier: 3-4 Free, 5 Starter($5), 6 Pro($9), 7-8 Premium($14), 9 Signature($19)
// ═══════════════════════════════════════════════════════════
export interface FaceStyleDef {
  id: string;
  name: string;
  description: string;
  renderer: typeof FaceRenderer;
  accent: string;
  bg: string;
  price: number;
  tier: PriceTier;
  tags: string[];
  complexity: ComplexityScore;
}

function def(
  id: string, name: string, description: string, renderer: typeof FaceRenderer,
  accent: string, bg: string, tags: string[], complexity: ComplexityScore,
): FaceStyleDef {
  const { price, tier } = calculatePrice(complexity);
  return { id, name, description, renderer, accent, bg, price, tier, tags, complexity };
}

export const FACE_STYLES: FaceStyleDef[] = [
  // ── Free (complexity 3-4) ──────────────────────────────
  def("classic", "Classic", "The original cyberpunk face — tech panels, glowing pupils, detailed HUD elements and CRT scanlines.",
    FaceRenderer, "#00d4ff", "#050810", ["cyberpunk", "tech", "HUD"],
    { geometry: 2, effects: 1, animation: 1 }),

  def("minimal", "Minimal", "Clean zen aesthetic — circle eyes, simple lines, no face plate. Quiet elegance for modern interfaces.",
    MinimalFace, "#e0e0e0", "#0a0a0f", ["clean", "modern", "zen"],
    { geometry: 1, effects: 1, animation: 1 }),

  def("circuit", "Circuit", "PCB green traces forming face features — IC chip eyes, copper solder dots, right-angle data paths.",
    CircuitFace, "#33cc66", "#041208", ["PCB", "hardware", "tech"],
    { geometry: 2, effects: 1, animation: 1 }),

  def("emoji", "Emoji", "Bright and cheerful cartoon face — glossy eyes, yellow skin, rosy cheeks. Pure friendliness.",
    EmojiFace, "#ffcc33", "#1a1520", ["cartoon", "cute", "friendly"],
    { geometry: 1, effects: 2, animation: 1 }),

  def("pixel", "Pixel Art", "Chunky 8-bit blocks on a grid — retro game aesthetic with visible pixel boundaries.",
    PixelFace, "#4a6ea0", "#16161d", ["8-bit", "retro", "game"],
    { geometry: 1, effects: 1, animation: 2 }),

  // ── Starter $5 (complexity 5) ──────────────────────────
  def("constellation", "Constellation", "Dark sky dotted with stars — face outlined by connected constellations, eyes are bright star clusters.",
    ConstellationFace, "#aaccff", "#020816", ["stars", "space", "ethereal"],
    { geometry: 2, effects: 2, animation: 1 }),

  def("sketch", "Sketch", "Hand-drawn pencil on cream paper — wobbly strokes, cross-hatching shadows, notebook aesthetic.",
    SketchFace, "#3a3530", "#f5f0e8", ["pencil", "hand-drawn", "paper"],
    { geometry: 3, effects: 1, animation: 1 }),

  def("ascii", "ASCII", "Monospace character matrix — face formed from punctuation and symbols on a terminal grid.",
    AsciiFace, "#66ff66", "#0c0c0c", ["text", "terminal", "matrix"],
    { geometry: 2, effects: 1, animation: 2 }),

  // ── Pro $9 (complexity 6) ──────────────────────────────
  def("retro", "Retro Terminal", "Green-on-black terminal aesthetic — blocky pixels, CRT scanlines, blinking cursor. Pure nostalgia.",
    RetroFace, "#33ff33", "#001200", ["retro", "CRT", "terminal"],
    { geometry: 2, effects: 2, animation: 2 }),

  def("organic", "Organic", "Warm and human-like — almond eyes, soft iris gradients, subtle cheek warmth. Natural and approachable.",
    OrganicFace, "#e8a060", "#0f0a08", ["warm", "human", "organic"],
    { geometry: 2, effects: 2, animation: 2 }),

  def("vapor", "Vaporwave", "80s retrowave sunset — chrome bar eyes, perspective grid, neon mouth line. Pure aesthetic.",
    VaporFace, "#ff44ff", "#1a0030", ["80s", "retro", "sunset"],
    { geometry: 2, effects: 2, animation: 2 }),

  // ── Premium $14 (complexity 7-8) ───────────────────────
  def("neon", "Neon Wireframe", "Tron-like wireframe — hexagonal frame, diamond eyes, color-cycling glow. No fills, all vibes.",
    NeonFace, "#ff44ff", "#020008", ["neon", "wireframe", "Tron"],
    { geometry: 2, effects: 3, animation: 2 }),

  def("hologram", "Hologram", "Blue-tinted transparent projection — scan lines, flicker, interference bands. Sci-fi briefing aesthetic.",
    HologramFace, "#50b4ff", "#020610", ["hologram", "sci-fi", "projection"],
    { geometry: 2, effects: 3, animation: 2 }),

  def("geometric", "Geometric", "Low-poly triangulated mesh — flat-shaded polygons, wireframe edges, vertex dots. Mathematical precision.",
    GeometricFace, "#5599dd", "#0a0c14", ["low-poly", "mesh", "math"],
    { geometry: 3, effects: 2, animation: 2 }),

  def("plasma", "Plasma", "Flowing energy gradients — shifting hues, glowing orb eyes, pulsing energy arcs. Lava lamp meets AI.",
    PlasmaFace, "#ff66ff", "#08050a", ["energy", "plasma", "flowing"],
    { geometry: 1, effects: 3, animation: 3 }),

  // ── V3 Free (complexity 3-4) ────────────────────────────
  def("blueprint", "Blueprint", "Technical drawing on blue paper — dimension lines, dashed construction, title block. Engineer aesthetic.",
    BlueprintFace, "#c0d8ff", "#0a2040", ["technical", "engineering", "CAD"],
    { geometry: 2, effects: 1, animation: 1 }),

  // ── V3 Starter $5 (complexity 5) ──────────────────────
  def("origami", "Origami", "Flat paper folds forming a diamond face — angular creases, shadow panels, triangular eyes. Paper art.",
    OrigamiFace, "#5a4a38", "#f0ebe0", ["paper", "minimal", "angular"],
    { geometry: 3, effects: 1, animation: 1 }),

  // ── V3 Pro $9 (complexity 6) ──────────────────────────
  def("infrared", "Infrared", "Thermal heat map visualization — layered heat zones, hot-spot pupils, temperature scale bar.",
    InfraredFace, "#ff4400", "#000008", ["thermal", "heat", "sci-fi"],
    { geometry: 1, effects: 3, animation: 2 }),

  def("stained", "Stained Glass", "Medieval cathedral window — colored triangular panes with lead borders, jewel eyes, arched mouth.",
    StainedGlassFace, "#4488ff", "#0a0808", ["glass", "cathedral", "art"],
    { geometry: 3, effects: 2, animation: 1 }),

  def("deco", "Art Deco", "1920s golden geometric lines — symmetric frame, ornate arched eyes, fan motifs, brass and gold.",
    DecoFace, "#d4aa50", "#0a0810", ["gold", "1920s", "luxury"],
    { geometry: 3, effects: 2, animation: 1 }),

  def("tribal", "Tribal", "Carved wood mask — bold geometric patterns, ember-glow pupils, zigzag forehead bands, teeth ridges.",
    TribalFace, "#cc3020", "#120a04", ["mask", "wood", "primal"],
    { geometry: 3, effects: 1, animation: 2 }),

  // ── V3 Premium $14 (complexity 7-8) ───────────────────
  def("watercolor", "Watercolor", "Soft bleeding paint on cream paper — radial wash blobs, watercolor iris rings, rosy cheek blush.",
    WatercolorFace, "#6090a0", "#f8f4ef", ["paint", "soft", "artistic"],
    { geometry: 2, effects: 3, animation: 2 }),

  def("steampunk", "Steampunk", "Brass gears and copper pipes — porthole eyes with gear iris, riveted oval face, steam vents.",
    SteampunkFace, "#c8a040", "#1a1008", ["brass", "Victorian", "gears"],
    { geometry: 3, effects: 2, animation: 2 }),

  def("nebula", "Nebula", "Cosmic gas clouds forming a face — drifting purple-blue nebula wisps, particle rings, star field.",
    NebulFace, "#bb88ff", "#030208", ["space", "cosmic", "wispy"],
    { geometry: 1, effects: 3, animation: 3 }),

  def("aurora", "Aurora", "Northern lights ribbons flowing across the face — green-purple curtains, halo eyes, wave mouth.",
    AuroraFace, "#66dd88", "#020810", ["lights", "nature", "flowing"],
    { geometry: 1, effects: 3, animation: 3 }),

  // ── Signature $19 (complexity 9) ───────────────────────
  def("glitch", "Glitch", "Digital chaos — RGB channel split, random distortion, static noise, scanlines. Corrupted data aesthetic.",
    GlitchFace, "#00ff00", "#080808", ["glitch", "chaos", "RGB"],
    { geometry: 3, effects: 3, animation: 3 }),

  // ── Masterwork $29 (complexity 10-11) ─────────────────
  def("phoenix", "Phoenix", "Fire & ember face with particle flames rising from cracks — molten iris, heat shimmer, procedural magma veins.",
    PhoenixFace, "#ff6620", "#0a0204", ["fire", "ember", "particles"],
    { geometry: 3, effects: 4, animation: 3 }),

  def("chrome", "Liquid Chrome", "Metallic morphing face — procedural noise mesh, specular highlights, environment reflection band. T-1000 vibes.",
    ChromeFace, "#c0c8e0", "#060608", ["metal", "chrome", "reflective"],
    { geometry: 4, effects: 3, animation: 3 }),

  def("cybernetic", "Cybernetic", "Multi-layered circuit overlay with holographic scan — targeting reticles, HUD data, spark particles, segmented mouth.",
    CyberneticFace, "#00ccff", "#020308", ["cyber", "HUD", "targeting"],
    { geometry: 3, effects: 4, animation: 4 }),

  def("deepsea", "Deep Sea", "Bioluminescent deep-ocean creature — anglerfish lure, glowing veins, plankton particles, bubble physics, caustic light.",
    DeepSeaFace, "#00aaff", "#000810", ["ocean", "bioluminescent", "creature"],
    { geometry: 3, effects: 4, animation: 4 }),

  // ── Legendary $39 (complexity 12) ─────────────────────
  def("synthwave", "Synthwave", "Full retrowave world — striped sunset, perspective grid, star field, chrome face, neon triangle eyes, equalizer mouth.",
    SynthwaveFace, "#ff00aa", "#0a001a", ["80s", "retrowave", "world"],
    { geometry: 4, effects: 4, animation: 4 }),

  def("ethereal", "Ethereal", "Transcendent light being — sacred geometry patterns, flower of life, light-beam crown, third eye chakra, golden motes.",
    EtherealFace, "#ffe888", "#080410", ["divine", "sacred", "light"],
    { geometry: 4, effects: 4, animation: 4 }),
];
