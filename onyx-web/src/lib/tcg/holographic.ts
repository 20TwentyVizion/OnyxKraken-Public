import { Card } from './types';

// Holographic cards are alternate-art, boosted versions of each faction's Legendary Bot.
// One per Signal = 5 total. These are the rarest cards in the game.
export const HOLOGRAPHIC_CARDS: Card[] = [
  {
    id: 'SG_LG_H01', name: 'Onyx — Nexus Ascendant', signal: 'logic', type: 'bot', rarity: 'holographic',
    cost: 8, power: 6, defense: 8, bodyType: 'mech',
    ability: 'Versatile. When played, draw 3 cards. Confident: When Onyx destroys an enemy, all allies gain +2 Power. Overclock: When Defense drops to 3 or below, take control of ALL enemy Bots with 4 or less Power for 1 turn.',
    flavor: '"I am the signal and the silence. The question and the answer. The Nexus speaks through me."',
    keywords: ['Versatile', 'Confident', 'Overclock'],
    imagePrompt: 'Onyx ascended to godlike form — body made of pure crystallized logic energy, the entire Nexus visible as a holographic galaxy within his transparent chest, commanding all data streams with outstretched hands, enemy robots bowing to his control, floating above a nexus convergence point where all five Signal colors meet and are dominated by blue, holographic prismatic shimmer across the entire image, ultimate cyan and cosmic blue with holographic rainbow reflections, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_H01', name: 'Volt — Gigavolt Storm', signal: 'pulse', type: 'bot', rarity: 'holographic',
    cost: 8, power: 8, defense: 6, bodyType: 'sleek',
    ability: 'Rush. Swift. When Volt attacks, deal 3 damage to ALL other enemy Bots. Overclock: When Defense drops to 3 or below, Volt attacks three times this turn with +4 Power.',
    flavor: '"I am the storm that ends all storms. Count the lightning. Count the bodies."',
    keywords: ['Rush', 'Swift', 'Overclock'],
    imagePrompt: 'Volt transcended into a living lightning storm — body dissolved into pure electrical energy shaped like a robot, three afterimage copies attacking simultaneously, chain lightning connecting all enemy targets in a web of destruction, the arena itself electrified and crumbling, holographic prismatic shimmer overlay, ultimate red and amber-lightning with holographic rainbow fire, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_H01', name: 'Sage — Infinite Archive', signal: 'flux', type: 'bot', rarity: 'holographic',
    cost: 8, power: 5, defense: 10, bodyType: 'retro',
    ability: 'Recycle. When played, draw 4 cards. At start of your turn, all allies gain +1/+1. Overclock: When Defense drops to 3 or below, shuffle your entire Scrap Heap into your deck, draw 5 cards, and all allies gain +3/+3.',
    flavor: '"I have archived infinity. Every outcome. Every possibility. And in all of them — I win."',
    keywords: ['Recycle', 'Overclock'],
    imagePrompt: 'Sage transformed into the living embodiment of all knowledge — a colossal retro-style robot made of stacked infinite library shelves, every book a different battle strategy, the Great Archive extending into infinity in all directions, allies growing stronger in the light of pure wisdom, holographic prismatic shimmer overlay, ultimate green and golden-wisdom with holographic rainbow knowledge-light, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_H01', name: 'Xyno — Entropy Singularity', signal: 'static', type: 'bot', rarity: 'holographic',
    cost: 8, power: 6, defense: 7, bodyType: 'cyber',
    ability: 'When played, opponent discards 3 cards. When Xyno attacks, deal 2 damage to ALL enemies and opponent discards 1 card. Overclock: When Defense drops to 3 or below, destroy ALL Mods and Cores on the field. Opponent discards their entire hand. Deal 1 damage per card discarded to opponent Core.',
    flavor: '"I am the noise at the end of all signals. The static after the last broadcast. The chaos that was always inevitable."',
    keywords: ['Overclock'],
    imagePrompt: 'Xyno achieved singularity of chaos — a being of pure entropic static that warps reality around it, the entire battlefield glitching and corrupting, opponent cards dissolving into noise, a black hole of chaos at the center consuming order itself, everything distorting toward Xyno gravity, holographic prismatic shimmer overlay, ultimate yellow and void-purple with holographic glitch-art distortion across the cosmos, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_H01', name: 'Nova — Event Horizon', signal: 'void', type: 'bot', rarity: 'holographic',
    cost: 8, power: 5, defense: 9, bodyType: 'orb',
    ability: 'Restore. When played, return ALL Bot cards from your Scrap Heap to hand. Sad: When an allied Bot is destroyed, deal 4 damage to opponent Core and draw 1. Overclock: When Defense drops to 3 or below, revive ALL Bots from your Scrap Heap to Grid with full Defense. All allies gain Shield.',
    flavor: '"Beyond the event horizon, death and birth are the same moment. I live in that moment. Forever."',
    keywords: ['Restore', 'Sad', 'Overclock'],
    imagePrompt: 'Nova transformed into a cosmic event horizon — an orb of pure void energy the size of a planet, all destroyed robots orbiting her as spectral forms being reborn, a massive beam of resurrection energy pouring from her core reviving everything, the boundary between life and death made visible as a shimmering purple-pink membrane, holographic prismatic shimmer overlay, ultimate purple and cosmic-pink with holographic nebula effects across the entire image, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
];
