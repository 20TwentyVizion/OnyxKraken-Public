export type { Card, CardSignal, CardType, CardRarity, BodyType } from './types';
export { KEYWORDS, SIGNAL_META, RARITY_COLORS } from './types';
export { LOGIC_CARDS } from './logic';
export { PULSE_CARDS } from './pulse';
export { FLUX_CARDS } from './flux';
export { STATIC_CARDS } from './static';
export { VOID_CARDS } from './void';
export { NEUTRAL_CARDS } from './neutral';
export { HOLOGRAPHIC_CARDS } from './holographic';

import { Card } from './types';
import { LOGIC_CARDS } from './logic';
import { PULSE_CARDS } from './pulse';
import { FLUX_CARDS } from './flux';
import { STATIC_CARDS } from './static';
import { VOID_CARDS } from './void';
import { NEUTRAL_CARDS } from './neutral';
import { HOLOGRAPHIC_CARDS } from './holographic';

export const ALL_CARDS: Card[] = [
  ...LOGIC_CARDS,
  ...PULSE_CARDS,
  ...FLUX_CARDS,
  ...STATIC_CARDS,
  ...VOID_CARDS,
  ...NEUTRAL_CARDS,
  ...HOLOGRAPHIC_CARDS,
];

// Utility helpers
export const getCardsBySignal = (signal: string) => ALL_CARDS.filter(c => c.signal === signal);
export const getCardsByType = (type: string) => ALL_CARDS.filter(c => c.type === type);
export const getCardsByRarity = (rarity: string) => ALL_CARDS.filter(c => c.rarity === rarity);
export const getCardById = (id: string) => ALL_CARDS.find(c => c.id === id);

// Stats
export const CARD_STATS = {
  total: ALL_CARDS.length,
  bySignal: {
    logic: LOGIC_CARDS.length,
    pulse: PULSE_CARDS.length,
    flux: FLUX_CARDS.length,
    static: STATIC_CARDS.length,
    void: VOID_CARDS.length,
    neutral: NEUTRAL_CARDS.length,
    holographic: HOLOGRAPHIC_CARDS.length,
  },
  byRarity: {
    common: ALL_CARDS.filter(c => c.rarity === 'common').length,
    uncommon: ALL_CARDS.filter(c => c.rarity === 'uncommon').length,
    rare: ALL_CARDS.filter(c => c.rarity === 'rare').length,
    epic: ALL_CARDS.filter(c => c.rarity === 'epic').length,
    legendary: ALL_CARDS.filter(c => c.rarity === 'legendary').length,
    holographic: ALL_CARDS.filter(c => c.rarity === 'holographic').length,
  },
  byType: {
    bot: ALL_CARDS.filter(c => c.type === 'bot').length,
    mod: ALL_CARDS.filter(c => c.type === 'mod').length,
    protocol: ALL_CARDS.filter(c => c.type === 'protocol').length,
    upgrade: ALL_CARDS.filter(c => c.type === 'upgrade').length,
    core: ALL_CARDS.filter(c => c.type === 'core').length,
  },
};
