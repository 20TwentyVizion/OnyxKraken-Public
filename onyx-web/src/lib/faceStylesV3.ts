/**
 * AgentFace V3 Styles — Batch 3, faces 17-21.
 */
import { FaceRenderer, lerpColor, REF_W, REF_H } from "./faceRenderer";

// ═══════════════════════════════════════════════════════════
// 17. WATERCOLOR — Soft bleeding paint blobs
// Complexity: geometry 2, effects 3, animation 2 = 7 → Premium ($14)
// ═══════════════════════════════════════════════════════════
export class WatercolorFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#f8f4ef";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Paper texture — faint speckles
    ctx.fillStyle = "rgba(180,160,140,0.04)";
    for (let i = 0; i < 60; i++) {
      const sx = ((i * 73 + 17) % REF_W);
      const sy = ((i * 91 + 23) % REF_H);
      ctx.beginPath();
      ctx.arc(this._sx(sx), this._sy(sy), this._ss(1 + Math.sin(i) * 0.5), 0, Math.PI * 2);
      ctx.fill();
    }

    // Face wash — large soft blobs
    const blobs = [
      { x: cx, y: REF_H / 2 - 10, r: 130, color: "rgba(180,140,120,0.08)" },
      { x: cx - 30, y: REF_H / 2 + 20, r: 100, color: "rgba(200,120,100,0.06)" },
      { x: cx + 25, y: REF_H / 2 - 15, r: 110, color: "rgba(160,140,180,0.06)" },
    ];
    for (const b of blobs) {
      const grad = ctx.createRadialGradient(
        this._sx(b.x), this._sy(b.y), 0,
        this._sx(b.x), this._sy(b.y), this._ss(b.r)
      );
      grad.addColorStop(0, b.color);
      grad.addColorStop(0.7, b.color.replace(/[\d.]+\)$/, "0.03)"));
      grad.addColorStop(1, "transparent");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(this._sx(b.x), this._sy(b.y), this._ss(b.r), 0, Math.PI * 2);
      ctx.fill();
    }

    // Cheek blush — soft watercolor circles
    const blushAlpha = 0.08 + 0.03 * Math.sin(t * 0.5);
    for (const side of [-1, 1]) {
      const bx = cx + side * 70;
      const grad = ctx.createRadialGradient(
        this._sx(bx), this._sy(200), 0,
        this._sx(bx), this._sy(200), this._ss(28)
      );
      grad.addColorStop(0, `rgba(220,100,80,${blushAlpha})`);
      grad.addColorStop(1, "transparent");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(this._sx(bx), this._sy(200), this._ss(28), 0, Math.PI * 2);
      ctx.fill();
    }

    // Eyes — soft painted ovals
    const eyeSpacing = 44, eyeY = 140;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 6;

      if (blink < 0.15) {
        ctx.strokeStyle = "rgba(80,60,50,0.4)";
        ctx.lineWidth = this._ss(2);
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 14), this._sy(eyeY + 2));
        ctx.quadraticCurveTo(this._sx(ex), this._sy(eyeY - 2), this._sx(ex + 14), this._sy(eyeY + 2));
        ctx.stroke();
      } else {
        const eyeH = 14 * blink;
        // Watercolor eye wash
        const eyeGrad = ctx.createRadialGradient(
          this._sx(ex), this._sy(eyeY), 0,
          this._sx(ex), this._sy(eyeY), this._ss(eyeH + 6)
        );
        eyeGrad.addColorStop(0, "rgba(240,240,235,0.8)");
        eyeGrad.addColorStop(0.6, "rgba(220,210,200,0.4)");
        eyeGrad.addColorStop(1, "transparent");
        ctx.fillStyle = eyeGrad;
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(16), this._ss(eyeH), 0, 0, Math.PI * 2);
        ctx.fill();

        // Lid stroke
        ctx.strokeStyle = "rgba(80,60,50,0.35)";
        ctx.lineWidth = this._ss(1.5);
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(15), this._ss(eyeH - 1), 0, 0, Math.PI * 2);
        ctx.stroke();

        // Iris — bleeding watercolor ring
        const irisR = 8 * em.pupil_size;
        const iGrad = ctx.createRadialGradient(
          this._sx(px), this._sy(py), this._ss(1),
          this._sx(px), this._sy(py), this._ss(irisR + 3)
        );
        iGrad.addColorStop(0, "rgba(40,80,100,0.7)");
        iGrad.addColorStop(0.5, "rgba(60,120,140,0.5)");
        iGrad.addColorStop(0.8, "rgba(80,140,160,0.2)");
        iGrad.addColorStop(1, "transparent");
        ctx.fillStyle = iGrad;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(irisR + 3), 0, Math.PI * 2);
        ctx.fill();

        // Pupil
        ctx.fillStyle = "rgba(30,20,15,0.75)";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(3.5 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();

        // Highlight
        ctx.fillStyle = "rgba(255,255,255,0.6)";
        ctx.beginPath();
        ctx.arc(this._sx(px - 2), this._sy(py - 2), this._ss(2), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Nose — faint wash
    const noseGrad = ctx.createRadialGradient(
      this._sx(cx + 2), this._sy(190), 0,
      this._sx(cx + 2), this._sy(190), this._ss(12)
    );
    noseGrad.addColorStop(0, "rgba(180,140,120,0.12)");
    noseGrad.addColorStop(1, "transparent");
    ctx.fillStyle = noseGrad;
    ctx.beginPath();
    ctx.arc(this._sx(cx + 2), this._sy(190), this._ss(12), 0, Math.PI * 2);
    ctx.fill();

    // Mouth — soft painted stroke
    const ms = this.mouth, mouthY = 228;
    const mouthW = 26 * ms.widthFactor;
    ctx.strokeStyle = `rgba(160,80,70,${0.3 + ms.openAmount * 0.3})`;
    ctx.lineWidth = this._ss(2);
    ctx.lineCap = "round";
    if (ms.openAmount < 0.05) {
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY - em.mouth_curve * 10), this._sx(cx + mouthW), this._sy(mouthY));
      ctx.stroke();
    } else {
      const openH = ms.openAmount * 14;
      // Open mouth wash
      const mGrad = ctx.createRadialGradient(
        this._sx(cx), this._sy(mouthY), 0,
        this._sx(cx), this._sy(mouthY), this._ss(Math.max(mouthW, openH) + 4)
      );
      mGrad.addColorStop(0, "rgba(140,50,40,0.25)");
      mGrad.addColorStop(0.7, "rgba(160,80,70,0.1)");
      mGrad.addColorStop(1, "transparent");
      ctx.fillStyle = mGrad;
      ctx.beginPath();
      ctx.ellipse(this._sx(cx), this._sy(mouthY), this._ss(mouthW), this._ss(openH), 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }

    // Eyebrows — light strokes
    if (Math.abs(em.brow_raise) > 0.1) {
      ctx.strokeStyle = "rgba(100,70,55,0.25)";
      ctx.lineWidth = this._ss(2.5);
      ctx.lineCap = "round";
      for (const side of [-1, 1]) {
        const ex = cx + side * eyeSpacing;
        const by = eyeY - 24 - em.brow_raise * 8;
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 12), this._sy(by + em.brow_raise * 3 * side));
        ctx.quadraticCurveTo(this._sx(ex), this._sy(by - 2), this._sx(ex + 12), this._sy(by - em.brow_raise * 3 * side));
        ctx.stroke();
      }
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 18. STEAMPUNK — Brass gears, copper pipes, Victorian aesthetic
// Complexity: geometry 3, effects 2, animation 2 = 7 → Premium ($14)
// ═══════════════════════════════════════════════════════════
export class SteampunkFace extends FaceRenderer {
  private _gear(ctx: CanvasRenderingContext2D, gx: number, gy: number, r: number, teeth: number, rot: number) {
    ctx.beginPath();
    for (let i = 0; i < teeth * 2; i++) {
      const a = (Math.PI * 2 / (teeth * 2)) * i + rot;
      const rr = i % 2 === 0 ? r : r * 0.75;
      const x = gx + Math.cos(a) * rr;
      const y = gy + Math.sin(a) * rr;
      if (i === 0) ctx.moveTo(this._sx(x), this._sy(y));
      else ctx.lineTo(this._sx(x), this._sy(y));
    }
    ctx.closePath();
  }

  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    const bgGrad = ctx.createLinearGradient(0, 0, 0, h);
    bgGrad.addColorStop(0, "#1a1008");
    bgGrad.addColorStop(1, "#0e0a04");
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;
    const brass = "#c8a040";
    const copper = "#b86830";
    const dark = "#2a1a08";

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Face plate — riveted oval
    ctx.fillStyle = dark;
    ctx.strokeStyle = brass;
    ctx.lineWidth = this._ss(2.5);
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(REF_H / 2 + 5), this._ss(120), this._ss(150), 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Rivets around plate
    for (let i = 0; i < 16; i++) {
      const a = (Math.PI * 2 / 16) * i;
      const rx = cx + Math.cos(a) * 115;
      const ry = REF_H / 2 + 5 + Math.sin(a) * 145;
      ctx.fillStyle = brass;
      ctx.beginPath();
      ctx.arc(this._sx(rx), this._sy(ry), this._ss(3), 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#e8c860";
      ctx.beginPath();
      ctx.arc(this._sx(rx - 0.5), this._sy(ry - 0.5), this._ss(1.2), 0, Math.PI * 2);
      ctx.fill();
    }

    // Background gears
    const gears = [
      { x: cx - 90, y: 80, r: 25, teeth: 8, speed: 0.3 },
      { x: cx + 95, y: 90, r: 20, teeth: 6, speed: -0.4 },
      { x: cx - 80, y: 280, r: 22, teeth: 7, speed: 0.35 },
      { x: cx + 85, y: 275, r: 18, teeth: 6, speed: -0.45 },
    ];
    for (const g of gears) {
      ctx.strokeStyle = lerpColor("#3a2810", brass, 0.3);
      ctx.lineWidth = this._ss(1.5);
      this._gear(ctx, g.x, g.y, g.r, g.teeth, t * g.speed);
      ctx.stroke();
      // Center axle
      ctx.fillStyle = copper;
      ctx.beginPath();
      ctx.arc(this._sx(g.x), this._sy(g.y), this._ss(4), 0, Math.PI * 2);
      ctx.fill();
    }

    // Eyes — gear-iris porthole design
    const eyeSpacing = 48, eyeY = 135;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 6;
      const eyeR = 22;

      // Porthole ring
      ctx.strokeStyle = brass;
      ctx.lineWidth = this._ss(3);
      ctx.beginPath();
      ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(eyeR), 0, Math.PI * 2);
      ctx.stroke();

      // Bolts on porthole
      for (let i = 0; i < 4; i++) {
        const a = (Math.PI / 2) * i;
        ctx.fillStyle = brass;
        ctx.beginPath();
        ctx.arc(this._sx(ex + Math.cos(a) * (eyeR + 1)), this._sy(eyeY + Math.sin(a) * (eyeR + 1)), this._ss(2.5), 0, Math.PI * 2);
        ctx.fill();
      }

      if (blink < 0.15) {
        // Closed — brass shutter
        ctx.fillStyle = lerpColor(dark, brass, 0.4);
        ctx.beginPath();
        ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(eyeR - 2), 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = brass;
        ctx.lineWidth = this._ss(1);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - eyeR + 4), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + eyeR - 4), this._sy(eyeY));
        ctx.stroke();
      } else {
        // Open — dark glass
        ctx.fillStyle = "#0a1520";
        ctx.beginPath();
        ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(eyeR - 3), 0, Math.PI * 2);
        ctx.fill();

        // Gear iris ring
        ctx.strokeStyle = lerpColor(brass, "#e8c860", 0.5 + 0.5 * Math.sin(t * 2));
        ctx.lineWidth = this._ss(1);
        this._gear(ctx, px, py, 10 * em.pupil_size, 6, t * 0.8 * side);
        ctx.stroke();

        // Pupil — glowing amber
        ctx.save();
        ctx.shadowColor = "#ff8800";
        ctx.shadowBlur = this._ss(8);
        ctx.fillStyle = "#ffaa33";
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(3.5 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
    }

    // Pipe connecting eyes
    ctx.strokeStyle = copper;
    ctx.lineWidth = this._ss(3);
    ctx.beginPath();
    ctx.moveTo(this._sx(cx - eyeSpacing + 24), this._sy(eyeY));
    ctx.lineTo(this._sx(cx + eyeSpacing - 24), this._sy(eyeY));
    ctx.stroke();
    // Pipe highlight
    ctx.strokeStyle = lerpColor(copper, "#e8a050", 0.5);
    ctx.lineWidth = this._ss(1);
    ctx.beginPath();
    ctx.moveTo(this._sx(cx - eyeSpacing + 24), this._sy(eyeY - 1));
    ctx.lineTo(this._sx(cx + eyeSpacing - 24), this._sy(eyeY - 1));
    ctx.stroke();

    // Nose — small valve
    ctx.fillStyle = copper;
    ctx.beginPath();
    ctx.arc(this._sx(cx), this._sy(190), this._ss(5), 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = brass;
    ctx.lineWidth = this._ss(1);
    ctx.beginPath();
    ctx.moveTo(this._sx(cx), this._sy(185));
    ctx.lineTo(this._sx(cx), this._sy(178));
    ctx.stroke();

    // Mouth — brass slot with steam vents
    const ms = this.mouth, mouthY = 245;
    const mouthW = 32 * ms.widthFactor;
    ctx.fillStyle = dark;
    ctx.strokeStyle = brass;
    ctx.lineWidth = this._ss(2);
    const openH = Math.max(4, ms.openAmount * 14 + 4);
    ctx.beginPath();
    ctx.roundRect(this._sx(cx - mouthW), this._sy(mouthY - openH / 2), this._ss(mouthW * 2), this._ss(openH), this._ss(3));
    ctx.fill();
    ctx.stroke();

    // Vent slats inside
    const slats = 5;
    ctx.strokeStyle = lerpColor(dark, brass, 0.3);
    ctx.lineWidth = this._ss(1);
    for (let i = 0; i < slats; i++) {
      const sx = cx - mouthW + 6 + i * (mouthW * 2 - 12) / (slats - 1);
      ctx.beginPath();
      ctx.moveTo(this._sx(sx), this._sy(mouthY - openH / 2 + 2));
      ctx.lineTo(this._sx(sx), this._sy(mouthY + openH / 2 - 2));
      ctx.stroke();
    }

    // Steam when speaking
    if (ms.openAmount > 0.2) {
      ctx.fillStyle = "rgba(200,180,150,0.06)";
      for (let i = 0; i < 4; i++) {
        const sx = cx - 15 + i * 10;
        const sy = mouthY + openH / 2 + 5 + Math.sin(t * 3 + i) * 4;
        ctx.beginPath();
        ctx.arc(this._sx(sx), this._sy(sy), this._ss(5 + Math.sin(t * 2 + i * 2) * 3), 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }
}

// ═══════════════════════════════════════════════════════════
// 19. INFRARED — Thermal heat map visualization
// Complexity: geometry 1, effects 3, animation 2 = 6 → Pro ($9)
// ═══════════════════════════════════════════════════════════
export class InfraredFace extends FaceRenderer {
  private _heatColor(v: number): string {
    if (v < 0.25) return lerpColor("#000033", "#0000cc", v / 0.25);
    if (v < 0.5) return lerpColor("#0000cc", "#00cc00", (v - 0.25) / 0.25);
    if (v < 0.75) return lerpColor("#00cc00", "#ffcc00", (v - 0.5) / 0.25);
    return lerpColor("#ffcc00", "#ff0000", (v - 0.75) / 0.25);
  }

  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#000008";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, cy = REF_H / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Thermal body blob — layered heat zones
    const zones = [
      { x: cx, y: cy - 10, r: 140, heat: 0.35 },
      { x: cx, y: cy - 30, r: 100, heat: 0.5 },
      { x: cx, y: cy - 20, r: 70, heat: 0.65 },
      { x: cx - 40, y: 140, r: 35, heat: 0.85 },  // left eye hot
      { x: cx + 40, y: 140, r: 35, heat: 0.85 },  // right eye hot
      { x: cx, y: 245, r: 25, heat: 0.7 },          // mouth warm
    ];
    for (const z of zones) {
      const grad = ctx.createRadialGradient(
        this._sx(z.x), this._sy(z.y), 0,
        this._sx(z.x), this._sy(z.y), this._ss(z.r)
      );
      const pulse = z.heat + Math.sin(t * 0.5) * 0.03;
      grad.addColorStop(0, this._heatColor(pulse) + "60");
      grad.addColorStop(0.5, this._heatColor(pulse * 0.7) + "30");
      grad.addColorStop(1, "transparent");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(this._sx(z.x), this._sy(z.y), this._ss(z.r), 0, Math.PI * 2);
      ctx.fill();
    }

    // Eyes — hot spots
    const eyeSpacing = 42, eyeY = 140;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 6;

      if (blink < 0.15) {
        ctx.strokeStyle = this._heatColor(0.6);
        ctx.lineWidth = this._ss(2);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 14), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 14), this._sy(eyeY));
        ctx.stroke();
      } else {
        const eyeH = 16 * blink;
        // Eye heat zone
        ctx.strokeStyle = this._heatColor(0.75);
        ctx.lineWidth = this._ss(1.5);
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(16), this._ss(eyeH), 0, 0, Math.PI * 2);
        ctx.stroke();

        // Hot pupil
        const pupilHeat = 0.95 + Math.sin(t * 2) * 0.05;
        ctx.save();
        ctx.shadowColor = "#ff3300";
        ctx.shadowBlur = this._ss(10);
        ctx.fillStyle = this._heatColor(pupilHeat);
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

    // Mouth — warm zone
    const ms = this.mouth, mouthY = 245;
    const mouthW = 30 * ms.widthFactor;
    const mouthHeat = 0.6 + ms.openAmount * 0.3;
    ctx.strokeStyle = this._heatColor(mouthHeat);
    ctx.lineWidth = this._ss(2);
    if (ms.openAmount < 0.05) {
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY - em.mouth_curve * 8), this._sx(cx + mouthW), this._sy(mouthY));
      ctx.stroke();
    } else {
      const openH = ms.openAmount * 14;
      ctx.beginPath();
      ctx.ellipse(this._sx(cx), this._sy(mouthY), this._ss(mouthW), this._ss(openH), 0, 0, Math.PI * 2);
      ctx.stroke();
      // Heat inside mouth
      const grad = ctx.createRadialGradient(
        this._sx(cx), this._sy(mouthY), 0,
        this._sx(cx), this._sy(mouthY), this._ss(mouthW)
      );
      grad.addColorStop(0, this._heatColor(0.9) + "30");
      grad.addColorStop(1, "transparent");
      ctx.fillStyle = grad;
      ctx.fill();
    }

    // Temperature scale bar
    const barX = 15, barY = 40, barH = 280, barW = 6;
    for (let i = 0; i < barH; i++) {
      const v = 1 - i / barH;
      ctx.fillStyle = this._heatColor(v);
      ctx.fillRect(this._sx(barX), this._sy(barY + i), this._ss(barW), this._ss(1.5));
    }
    ctx.font = `${Math.max(6, Math.round(this._ss(7)))}px monospace`;
    ctx.fillStyle = "#888888";
    ctx.textAlign = "center";
    ctx.fillText("HOT", this._sx(barX + barW / 2), this._sy(barY - 5));
    ctx.fillText("COLD", this._sx(barX + barW / 2), this._sy(barY + barH + 10));
  }
}

// ═══════════════════════════════════════════════════════════
// 20. BLUEPRINT — Technical drawing on blue paper
// Complexity: geometry 2, effects 1, animation 1 = 4 → Free ($0)
// ═══════════════════════════════════════════════════════════
export class BlueprintFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0a2040";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const white = "rgba(200,220,255,0.6)";
    const dim = "rgba(200,220,255,0.2)";
    const bright = "rgba(220,240,255,0.85)";

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Grid
    ctx.strokeStyle = "rgba(100,150,200,0.1)";
    ctx.lineWidth = this._ss(0.5);
    for (let x = 0; x < REF_W; x += 20) {
      ctx.beginPath(); ctx.moveTo(this._sx(x), 0); ctx.lineTo(this._sx(x), h); ctx.stroke();
    }
    for (let y = 0; y < REF_H; y += 20) {
      ctx.beginPath(); ctx.moveTo(0, this._sy(y)); ctx.lineTo(w, this._sy(y)); ctx.stroke();
    }

    // Face outline — technical oval with dimension lines
    ctx.strokeStyle = white;
    ctx.lineWidth = this._ss(1.2);
    ctx.setLineDash([this._ss(4), this._ss(3)]);
    ctx.beginPath();
    ctx.ellipse(this._sx(cx), this._sy(REF_H / 2 + 5), this._ss(110), this._ss(145), 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Dimension lines
    ctx.strokeStyle = dim;
    ctx.lineWidth = this._ss(0.6);
    // Horizontal
    ctx.beginPath();
    ctx.moveTo(this._sx(cx - 110), this._sy(15)); ctx.lineTo(this._sx(cx + 110), this._sy(15));
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(this._sx(cx - 110), this._sy(12)); ctx.lineTo(this._sx(cx - 110), this._sy(18));
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(this._sx(cx + 110), this._sy(12)); ctx.lineTo(this._sx(cx + 110), this._sy(18));
    ctx.stroke();
    ctx.font = `${Math.max(6, Math.round(this._ss(8)))}px monospace`;
    ctx.fillStyle = dim;
    ctx.textAlign = "center";
    ctx.fillText("220", this._sx(cx), this._sy(12));

    // Eyes
    const eyeSpacing = 48, eyeY = 138;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 6;

      ctx.strokeStyle = white;
      ctx.lineWidth = this._ss(1.2);

      if (blink < 0.15) {
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 16), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 16), this._sy(eyeY));
        ctx.stroke();
      } else {
        const eyeH = 15 * blink;
        ctx.beginPath();
        ctx.ellipse(this._sx(ex), this._sy(eyeY), this._ss(16), this._ss(eyeH), 0, 0, Math.PI * 2);
        ctx.stroke();

        // Center mark crosshair
        ctx.strokeStyle = dim;
        ctx.lineWidth = this._ss(0.5);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 4), this._sy(eyeY)); ctx.lineTo(this._sx(ex + 4), this._sy(eyeY));
        ctx.moveTo(this._sx(ex), this._sy(eyeY - 4)); ctx.lineTo(this._sx(ex), this._sy(eyeY + 4));
        ctx.stroke();

        // Pupil
        ctx.fillStyle = bright;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(4.5 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();

        // Dimension — eye radius
        ctx.fillStyle = dim;
        ctx.font = `${Math.max(5, Math.round(this._ss(6)))}px monospace`;
        ctx.textAlign = "left";
        ctx.fillText(`R${Math.round(eyeH)}`, this._sx(ex + 18), this._sy(eyeY - eyeH + 2));
      }
    }

    // Label between eyes
    ctx.fillStyle = dim;
    ctx.font = `${Math.max(5, Math.round(this._ss(6)))}px monospace`;
    ctx.textAlign = "center";
    ctx.fillText(`${eyeSpacing * 2}px`, this._sx(cx), this._sy(eyeY - 22));
    ctx.strokeStyle = dim;
    ctx.lineWidth = this._ss(0.5);
    ctx.beginPath();
    ctx.moveTo(this._sx(cx - eyeSpacing), this._sy(eyeY - 18));
    ctx.lineTo(this._sx(cx + eyeSpacing), this._sy(eyeY - 18));
    ctx.stroke();

    // Nose — center mark
    ctx.strokeStyle = dim;
    ctx.lineWidth = this._ss(0.8);
    ctx.beginPath();
    ctx.moveTo(this._sx(cx), this._sy(170));
    ctx.lineTo(this._sx(cx), this._sy(195));
    ctx.lineTo(this._sx(cx + 6), this._sy(195));
    ctx.stroke();

    // Mouth
    const ms = this.mouth, mouthY = 245;
    const mouthW = 30 * ms.widthFactor;
    ctx.strokeStyle = white;
    ctx.lineWidth = this._ss(1.2);
    if (ms.openAmount < 0.05) {
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY - em.mouth_curve * 8), this._sx(cx + mouthW), this._sy(mouthY));
      ctx.stroke();
    } else {
      const openH = ms.openAmount * 14;
      ctx.beginPath();
      ctx.ellipse(this._sx(cx), this._sy(mouthY), this._ss(mouthW), this._ss(openH), 0, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Title block
    ctx.strokeStyle = dim;
    ctx.lineWidth = this._ss(0.8);
    ctx.strokeRect(this._sx(280), this._sy(310), this._ss(110), this._ss(35));
    ctx.fillStyle = dim;
    ctx.font = `${Math.max(5, Math.round(this._ss(6)))}px monospace`;
    ctx.textAlign = "left";
    ctx.fillText("AgentFace Blueprint", this._sx(284), this._sy(322));
    ctx.fillText(`Scale: ${this.s.toFixed(2)}x`, this._sx(284), this._sy(334));
    ctx.fillText("REV: A", this._sx(355), this._sy(334));
  }
}

// ═══════════════════════════════════════════════════════════
// 21. STAINED GLASS — Colored segments with lead lines
// Complexity: geometry 3, effects 2, animation 1 = 6 → Pro ($9)
// ═══════════════════════════════════════════════════════════
export class StainedGlassFace extends FaceRenderer {
  draw(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#0a0808";
    ctx.fillRect(0, 0, w, h);
    if (this.s < 0.01) return;

    const cx = REF_W / 2, es = this.eye, em = this.emotion;
    const t = performance.now() / 1000;
    const lead = "#1a1a1a";

    let blink = 1.0;
    if (es.isBlinking) blink = es.blinkProgress < 1 ? (1 - es.blinkProgress) : (es.blinkProgress - 1);
    blink = Math.max(0, blink - es.squint * 0.5);
    blink = Math.min(1, blink * (1 + em.eye_widen));

    // Glass colors
    const glassColors = [
      "rgba(40,60,140,0.6)", "rgba(140,40,50,0.5)", "rgba(40,120,60,0.5)",
      "rgba(140,120,40,0.5)", "rgba(100,40,120,0.5)", "rgba(40,100,120,0.5)",
      "rgba(120,80,40,0.5)", "rgba(60,40,130,0.5)",
    ];

    // Face divided into glass segments — triangulated regions
    const facePoints: [number, number][] = [
      [cx, 30], [cx + 60, 55], [cx + 100, 110], [cx + 110, 170],
      [cx + 95, 240], [cx + 55, 300], [cx, 330],
      [cx - 55, 300], [cx - 95, 240], [cx - 110, 170],
      [cx - 100, 110], [cx - 60, 55],
    ];
    const innerPts: [number, number][] = [
      [cx, 100], [cx + 50, 130], [cx + 40, 200], [cx, 270],
      [cx - 40, 200], [cx - 50, 130],
    ];

    // Outer segments
    for (let i = 0; i < facePoints.length; i++) {
      const [x1, y1] = facePoints[i];
      const [x2, y2] = facePoints[(i + 1) % facePoints.length];
      const near = innerPts.reduce((best, p) => {
        const d1 = Math.hypot(p[0] - (x1 + x2) / 2, p[1] - (y1 + y2) / 2);
        const d2 = Math.hypot(best[0] - (x1 + x2) / 2, best[1] - (y1 + y2) / 2);
        return d1 < d2 ? p : best;
      }, innerPts[0]);

      const glow = 0.8 + 0.2 * Math.sin(t * 0.3 + i * 0.7);
      ctx.globalAlpha = glow;
      ctx.fillStyle = glassColors[i % glassColors.length];
      ctx.beginPath();
      ctx.moveTo(this._sx(x1), this._sy(y1));
      ctx.lineTo(this._sx(x2), this._sy(y2));
      ctx.lineTo(this._sx(near[0]), this._sy(near[1]));
      ctx.closePath();
      ctx.fill();
      ctx.globalAlpha = 1;

      // Lead lines
      ctx.strokeStyle = lead;
      ctx.lineWidth = this._ss(2);
      ctx.beginPath();
      ctx.moveTo(this._sx(x1), this._sy(y1));
      ctx.lineTo(this._sx(x2), this._sy(y2));
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(this._sx(x2), this._sy(y2));
      ctx.lineTo(this._sx(near[0]), this._sy(near[1]));
      ctx.stroke();
    }

    // Inner segments
    for (let i = 0; i < innerPts.length; i++) {
      const [x1, y1] = innerPts[i];
      const [x2, y2] = innerPts[(i + 1) % innerPts.length];
      ctx.strokeStyle = lead;
      ctx.lineWidth = this._ss(1.5);
      ctx.beginPath();
      ctx.moveTo(this._sx(x1), this._sy(y1));
      ctx.lineTo(this._sx(x2), this._sy(y2));
      ctx.stroke();
    }

    // Eyes — round glass jewels
    const eyeSpacing = 50, eyeY = 138;
    for (const side of [-1, 1]) {
      const ex = cx + side * eyeSpacing;
      const px = ex + es.gazeX * 8;
      const py = eyeY + es.gazeY * 5;

      if (blink < 0.15) {
        ctx.strokeStyle = lead;
        ctx.lineWidth = this._ss(2.5);
        ctx.beginPath();
        ctx.moveTo(this._sx(ex - 14), this._sy(eyeY));
        ctx.lineTo(this._sx(ex + 14), this._sy(eyeY));
        ctx.stroke();
      } else {
        const eyeR = 16 * blink;
        // Glass fill
        const eyeGrad = ctx.createRadialGradient(
          this._sx(ex - 3), this._sy(eyeY - 3), 0,
          this._sx(ex), this._sy(eyeY), this._ss(eyeR)
        );
        eyeGrad.addColorStop(0, "rgba(200,220,255,0.4)");
        eyeGrad.addColorStop(0.5, "rgba(100,140,200,0.3)");
        eyeGrad.addColorStop(1, "rgba(40,60,120,0.5)");
        ctx.fillStyle = eyeGrad;
        ctx.beginPath();
        ctx.arc(this._sx(ex), this._sy(eyeY), this._ss(eyeR), 0, Math.PI * 2);
        ctx.fill();

        // Lead border
        ctx.strokeStyle = lead;
        ctx.lineWidth = this._ss(2.5);
        ctx.stroke();

        // Pupil jewel
        ctx.save();
        ctx.shadowColor = "#4488ff";
        ctx.shadowBlur = this._ss(6);
        const pGrad = ctx.createRadialGradient(
          this._sx(px - 1), this._sy(py - 1), 0,
          this._sx(px), this._sy(py), this._ss(6 * em.pupil_size)
        );
        pGrad.addColorStop(0, "#aaccff");
        pGrad.addColorStop(0.4, "#4466cc");
        pGrad.addColorStop(1, "#1a2244");
        ctx.fillStyle = pGrad;
        ctx.beginPath();
        ctx.arc(this._sx(px), this._sy(py), this._ss(6 * em.pupil_size), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        // Light reflection
        ctx.fillStyle = "rgba(255,255,255,0.5)";
        ctx.beginPath();
        ctx.arc(this._sx(px - 2), this._sy(py - 2), this._ss(2), 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Mouth — arched glass panel
    const ms = this.mouth, mouthY = 260;
    const mouthW = 30 * ms.widthFactor;
    ctx.strokeStyle = lead;
    ctx.lineWidth = this._ss(2);
    if (ms.openAmount < 0.05) {
      ctx.fillStyle = "rgba(140,40,50,0.3)";
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY - em.mouth_curve * 10 - 6), this._sx(cx + mouthW), this._sy(mouthY));
      ctx.quadraticCurveTo(this._sx(cx), this._sy(mouthY + 3), this._sx(cx - mouthW), this._sy(mouthY));
      ctx.fill();
      ctx.stroke();
    } else {
      const openH = ms.openAmount * 16;
      ctx.fillStyle = "rgba(140,40,50,0.4)";
      ctx.beginPath();
      ctx.ellipse(this._sx(cx), this._sy(mouthY), this._ss(mouthW), this._ss(openH), 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      // Inner division
      ctx.strokeStyle = lead;
      ctx.lineWidth = this._ss(1);
      ctx.beginPath();
      ctx.moveTo(this._sx(cx - mouthW), this._sy(mouthY));
      ctx.lineTo(this._sx(cx + mouthW), this._sy(mouthY));
      ctx.stroke();
    }
  }
}
