export type CardSignal = 'logic' | 'pulse' | 'flux' | 'static' | 'void' | 'neutral';
export type CardType = 'bot' | 'mod' | 'protocol' | 'upgrade' | 'core';
export type CardRarity = 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary' | 'holographic';
export type BodyType = 'mech' | 'sleek' | 'heavy' | 'skeletal' | 'orb' | 'knight' | 'cyber' | 'retro';

export interface Card {
  id: string;            // SG_LG_B01 format
  name: string;
  signal: CardSignal;
  type: CardType;
  rarity: CardRarity;
  cost: number;          // Charge cost
  power: number;         // Attack (bots only, 0 for others)
  defense: number;       // Health (bots only, 0 for others)
  bodyType?: BodyType;   // Bots only
  ability: string;       // Game rules text
  flavor: string;        // Lore/flavor text
  keywords: string[];    // Mechanical tags
  imagePrompt: string;   // Prompt for AI image generation
}

// Keyword glossary — mechanical tags used across all cards
export const KEYWORDS: Record<string, string> = {
  // Combat keywords
  'Rush':       'Can attack the turn it is played.',
  'Guard':      'Must be attacked before other Bots.',
  'Swift':      'Deals combat damage before the defender.',
  'Armored':    'Takes 1 less damage from all sources (min 1).',
  'Piercing':   'Excess combat damage (over Defense) hits opponent Core.',
  'Shield':     'Prevents the next instance of damage to this card.',
  'Volatile':   'When destroyed, deal 2 damage to all adjacent Bots.',
  'Link':       'While an adjacent allied Bot exists, this Bot gains +1 Power.',

  // Utility keywords
  'Chain':      'Draw 1 card when this Bot\'s ability activates.',
  'Recycle':    'When destroyed, return 1 card from Scrap Heap to hand.',
  'Restore':    'Heal 1 Defense to an adjacent ally at end of turn.',
  'Surge':      '+1 max Charge this game (permanent ramp).',
  'Hack':       'Destroy target enemy Core card.',
  'Echo':       'This Protocol resolves twice.',
  'Versatile':  'This Bot can equip 2 Mods instead of 1.',

  // Emotion keywords
  'Angry':      'Triggers when this Bot takes damage but survives.',
  'Confident':  'Triggers when this Bot destroys an enemy Bot.',
  'Sad':        'Triggers when an allied Bot is destroyed.',
  'Excited':    'Triggers when you play 2+ cards this turn.',
  'Focused':    'Triggers when this is the only Bot on your Grid.',

  // Overclock
  'Overclock':  'Triggers a bonus effect when this Bot\'s Defense drops to 3 or below.',
};

// Signal colors and metadata
export const SIGNAL_META: Record<CardSignal, { name: string; color: string; glow: string; icon: string; tagline: string }> = {
  logic:   { name: 'LOGIC',  color: '#2288ff', glow: '#2288ff40', icon: '🔷', tagline: 'Calculate. Defend. Prevail.' },
  pulse:   { name: 'PULSE',  color: '#ff2244', glow: '#ff224440', icon: '🔴', tagline: 'Strike fast. Strike hard.' },
  flux:    { name: 'FLUX',   color: '#22cc66', glow: '#22cc6640', icon: '🟢', tagline: 'Adapt. Grow. Overcome.' },
  static:  { name: 'STATIC', color: '#ffcc00', glow: '#ffcc0040', icon: '🟡', tagline: 'Disrupt. Confuse. Punish.' },
  void:    { name: 'VOID',   color: '#aa44ff', glow: '#aa44ff40', icon: '🟣', tagline: 'Sacrifice. Manipulate. Transcend.' },
  neutral: { name: 'NEUTRAL',color: '#888899', glow: '#88889940', icon: '⚪', tagline: 'Versatile tools for any commander.' },
};

// Rarity display
export const RARITY_COLORS: Record<CardRarity, string> = {
  common:      '#c0c0c0',
  uncommon:    '#ffd700',
  rare:        '#2288ff',
  epic:        '#aa44ff',
  legendary:   '#ff6600',
  holographic: 'linear-gradient(135deg, #2288ff, #ff2244, #22cc66, #ffcc00, #aa44ff)',
};
