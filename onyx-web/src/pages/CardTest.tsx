import { useEffect, useRef, useState } from 'react';
import { renderCard, CARD_W, CARD_H } from '../lib/tcg/CardRenderer';
import { getCardById, getCardsBySignal, SIGNAL_META } from '../lib/tcg';
import type { Card, CardSignal } from '../lib/tcg';
import type { ThemeColors, BodyType, BodyBuild } from '../lib/robotBody';
import { THEME_PRESETS } from '../lib/robotBody';

const SCALE = 1.5; // render at 1.5x for crispy display

// Default card to show
const DEFAULT_CARD_ID = 'SG_LG_B08'; // Onyx — Signal Commander

export default function CardTest() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [selectedId, setSelectedId] = useState(DEFAULT_CARD_ID);
  const [emotion, setEmotion] = useState('neutral');
  const [breathPhase, setBreathPhase] = useState(0.25);
  const [animate, setAnimate] = useState(false);
  const animRef = useRef<number>(0);

  const card = getCardById(selectedId);

  // Draw the card
  useEffect(() => {
    const cvs = canvasRef.current;
    if (!cvs || !card) return;
    const ctx = cvs.getContext('2d');
    if (!ctx) return;

    const draw = (phase: number) => {
      ctx.clearRect(0, 0, cvs.width, cvs.height);
      ctx.save();
      ctx.scale(SCALE, SCALE);
      renderCard(ctx, card, {
        faceEmotion: emotion,
        breathPhase: phase,
      });
      ctx.restore();
    };

    if (animate) {
      let start = performance.now();
      const loop = (ts: number) => {
        const elapsed = (ts - start) / 1000;
        const phase = (elapsed * 0.3) % 1; // slow breathing
        draw(phase);
        animRef.current = requestAnimationFrame(loop);
      };
      animRef.current = requestAnimationFrame(loop);
      return () => cancelAnimationFrame(animRef.current);
    } else {
      draw(breathPhase);
    }
  }, [card, emotion, breathPhase, animate]);

  // Gather all bot cards for the selector
  const signals: CardSignal[] = ['logic', 'pulse', 'flux', 'static', 'void'];
  const allBots = signals.flatMap(s => getCardsBySignal(s).filter(c => c.type === 'bot'));

  if (!card) return <div className="p-8 text-red-400">Card not found: {selectedId}</div>;

  return (
    <div className="min-h-screen bg-[#06060e] text-white flex flex-col items-center py-8 px-4 gap-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-2xl font-bold tracking-wider">
          <span className="text-cyan-400">ONYX:</span>{' '}
          <span className="text-white">OVERCLOCK</span>
        </h1>
        <p className="text-xs text-gray-500 mt-1">Card Renderer Test — Signal Genesis</p>
      </div>

      <div className="flex flex-col lg:flex-row gap-8 items-start">
        {/* Card Canvas */}
        <div className="flex flex-col items-center gap-4">
          <canvas
            ref={canvasRef}
            width={CARD_W * SCALE}
            height={CARD_H * SCALE}
            style={{ width: CARD_W * SCALE, height: CARD_H * SCALE }}
            className="rounded-xl shadow-2xl"
          />
          <p className="text-xs text-gray-600">{card.id}</p>
        </div>

        {/* Controls */}
        <div className="flex flex-col gap-4 min-w-[280px]">
          {/* Card Selector */}
          <div className="bg-[#0e0e1a] rounded-lg p-4 border border-[#222244]">
            <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">Select Card</label>
            <select
              value={selectedId}
              onChange={e => setSelectedId(e.target.value)}
              className="w-full bg-[#14142a] text-white text-sm rounded px-3 py-2 border border-[#333355] focus:outline-none focus:border-cyan-600"
            >
              {signals.map(sig => (
                <optgroup key={sig} label={`${SIGNAL_META[sig].icon} ${SIGNAL_META[sig].name}`}>
                  {getCardsBySignal(sig).filter(c => c.type === 'bot').map(c => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.rarity}) — {c.power}/{c.defense}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          {/* Emotion Selector */}
          <div className="bg-[#0e0e1a] rounded-lg p-4 border border-[#222244]">
            <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">Face Emotion</label>
            <div className="flex flex-wrap gap-2">
              {['neutral', 'happy', 'angry', 'sad', 'surprised', 'thinking', 'determined'].map(e => (
                <button
                  key={e}
                  onClick={() => setEmotion(e)}
                  className={`text-xs px-3 py-1 rounded transition-all ${
                    emotion === e
                      ? 'bg-cyan-600 text-white'
                      : 'bg-[#14142a] text-gray-400 hover:bg-[#1a1a33] border border-[#333355]'
                  }`}
                >
                  {e}
                </button>
              ))}
            </div>
          </div>

          {/* Animation Toggle */}
          <div className="bg-[#0e0e1a] rounded-lg p-4 border border-[#222244]">
            <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">Animation</label>
            <button
              onClick={() => setAnimate(!animate)}
              className={`text-xs px-4 py-2 rounded transition-all ${
                animate
                  ? 'bg-green-600 text-white'
                  : 'bg-[#14142a] text-gray-400 hover:bg-[#1a1a33] border border-[#333355]'
              }`}
            >
              {animate ? '⏸ Stop Breathing' : '▶ Animate Breathing'}
            </button>
            {!animate && (
              <div className="mt-3">
                <label className="text-xs text-gray-600">Breath Phase: {breathPhase.toFixed(2)}</label>
                <input
                  type="range"
                  min={0} max={1} step={0.01}
                  value={breathPhase}
                  onChange={e => setBreathPhase(Number(e.target.value))}
                  className="w-full mt-1 accent-cyan-500"
                />
              </div>
            )}
          </div>

          {/* Card Info */}
          <div className="bg-[#0e0e1a] rounded-lg p-4 border border-[#222244]">
            <label className="text-xs text-gray-500 uppercase tracking-wider mb-2 block">Card Details</label>
            <div className="text-sm space-y-1">
              <p><span className="text-gray-500">Name:</span> <span className="text-white font-bold">{card.name}</span></p>
              <p><span className="text-gray-500">Signal:</span> <span style={{ color: SIGNAL_META[card.signal].color }}>{SIGNAL_META[card.signal].name}</span></p>
              <p><span className="text-gray-500">Type:</span> {card.type} {card.bodyType && `(${card.bodyType})`}</p>
              <p><span className="text-gray-500">Rarity:</span> {card.rarity}</p>
              <p><span className="text-gray-500">Cost:</span> {card.cost} · <span className="text-red-400">{card.power} PWR</span> · <span className="text-blue-400">{card.defense} DEF</span></p>
              <p className="text-gray-400 text-xs mt-2">{card.ability}</p>
              <p className="text-gray-600 text-xs italic mt-1">{card.flavor}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
