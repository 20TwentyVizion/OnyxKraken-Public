/**
 * AgentFace Pricing Model
 *
 * Price is determined by a complexity score across 3 axes (each 1-4):
 *   - geometry:  1 = basic shapes, 2 = curves/compound, 3 = complex paths/mesh, 4 = multi-layer compositing/procedural
 *   - effects:   1 = none/solid fills, 2 = glow/gradients, 3 = particles/distortion, 4 = physics particles/post-processing/procedural noise
 *   - animation: 1 = base engine only, 2 = color cycling/pulse, 3 = heavy per-frame FX, 4 = procedural generation/simulation each frame
 *
 * Total (3-12) maps to tier:
 *   3-4   → Free        ($0)  — Simple starter examples
 *   5     → Starter     ($5)  — Clean styles with a unique twist
 *   6     → Pro         ($9)  — Moderate complexity, polished effects
 *   7-8   → Premium     ($14) — High complexity, multiple layered effects
 *   9     → Signature   ($19) — Maximum standard complexity
 *   10-11 → Masterwork  ($29) — Multi-pass rendering, particle systems, advanced compositing
 *   12    → Legendary   ($39) — Full-scene procedural worlds, every technique combined
 */

export interface ComplexityScore {
  geometry: number;
  effects: number;
  animation: number;
}

export type PriceTier = "free" | "starter" | "pro" | "premium" | "signature" | "masterwork" | "legendary";

export function calculatePrice(c: ComplexityScore): { price: number; tier: PriceTier } {
  const total = c.geometry + c.effects + c.animation;
  if (total <= 4) return { price: 0, tier: "free" };
  if (total === 5) return { price: 5, tier: "starter" };
  if (total === 6) return { price: 9, tier: "pro" };
  if (total <= 8) return { price: 14, tier: "premium" };
  if (total === 9) return { price: 19, tier: "signature" };
  if (total <= 11) return { price: 29, tier: "masterwork" };
  return { price: 39, tier: "legendary" };
}

export const TIER_META: Record<PriceTier, { label: string; color: string; css: string }> = {
  free:        { label: "Free",        color: "#44ff88", css: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30" },
  starter:     { label: "Starter",     color: "#38bdf8", css: "bg-sky-500/15 text-sky-400 border-sky-500/30" },
  pro:         { label: "Pro",         color: "#00d4ff", css: "bg-cyan-500/15 text-cyan-400 border-cyan-500/30" },
  premium:     { label: "Premium",     color: "#a78bfa", css: "bg-purple-500/15 text-purple-400 border-purple-500/30" },
  signature:   { label: "Signature",   color: "#fbbf24", css: "bg-amber-500/15 text-amber-400 border-amber-500/30" },
  masterwork:  { label: "Masterwork",  color: "#f97316", css: "bg-orange-500/15 text-orange-400 border-orange-500/30" },
  legendary:   { label: "Legendary",   color: "#ef4444", css: "bg-red-500/15 text-red-400 border-red-500/30" },
};
