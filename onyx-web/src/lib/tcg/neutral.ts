import { Card } from './types';

export const NEUTRAL_CARDS: Card[] = [
  // ============================================================
  // UPGRADES (3) — 2 Common, 1 Uncommon
  // ============================================================
  {
    id: 'SG_NT_U01', name: 'Quick Fix', signal: 'neutral', type: 'upgrade', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Restore 2 Defense to target Bot.',
    flavor: '"Duct tape of the digital age."',
    keywords: [],
    imagePrompt: 'Simple repair tool applying a quick fix to a damaged robot, sparks and healing energy, functional and no-frills, silver and warm white repair glow on neutral background, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_U02', name: 'Power Surge', signal: 'neutral', type: 'upgrade', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Give target Bot +2 Power this turn.',
    flavor: '"Temporary. Explosive. Effective."',
    keywords: [],
    imagePrompt: 'Generic power surge hitting a robot, temporary boost visualized as white energy aura, simple and universal, silver and electric white on neutral dark background, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_U03', name: 'Signal Boost', signal: 'neutral', type: 'upgrade', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Give target Bot +1 Power and +1 Defense permanently. Draw 1 card.',
    flavor: '"Amplify. Strengthen. Persist."',
    keywords: [],
    imagePrompt: 'Universal signal boost wave enhancing a robot, permanent stat increase visualized as a settled glow, drawing new data from the boost, silver and warm gold boost energy, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // MODS (3) — 2 Common, 1 Uncommon
  // ============================================================
  {
    id: 'SG_NT_M01', name: 'Basic Plating', signal: 'neutral', type: 'mod', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Equip to Bot: +2 Defense.',
    flavor: '"Standard issue. Gets the job done."',
    keywords: [],
    imagePrompt: 'Simple gray armor plating, functional and unadorned, bolted onto a robot surface, silver and steel gray on neutral background, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_M02', name: 'Combat Booster', signal: 'neutral', type: 'mod', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Power, +1 Defense.',
    flavor: '"A little of everything."',
    keywords: [],
    imagePrompt: 'Balanced combat enhancement module with both offensive and defensive indicators, modest but reliable, silver and warm white balanced glow, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_M03', name: 'Adaptive Armor', signal: 'neutral', type: 'mod', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Power, +2 Defense. Equipped Bot gains the Signal advantage bonus against ALL Signals.',
    flavor: '"It learns what hurts you. Then it becomes that."',
    keywords: [],
    imagePrompt: 'Adaptive armor that shifts colors to match any Signal advantage, chameleon-like surface cycling through blue red green yellow purple, versatile and dangerous, all Signal colors cycling on silver base, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // PROTOCOLS (8) — 4 Common, 4 Uncommon
  // ============================================================
  {
    id: 'SG_NT_P01', name: 'Reboot', signal: 'neutral', type: 'protocol', rarity: 'common',
    cost: 0, power: 0, defense: 0,
    ability: 'Restore 1 Defense to target Bot.',
    flavor: '"Have you tried turning it off and on again?"',
    keywords: [],
    imagePrompt: 'Robot rebooting with a loading screen on its visor, simple restart animation, functional and universal, silver and white reboot glow with progress bar, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_P02', name: 'Scrap Salvage', signal: 'neutral', type: 'protocol', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Return 1 card from your Scrap Heap to your hand.',
    flavor: '"One bot\'s trash..."',
    keywords: [],
    imagePrompt: 'Hand reaching into a pile of scrapped robot parts and pulling out a glowing card, salvage operation, resourceful, silver and warm amber salvage glow among gray debris, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_P03', name: 'Emergency Shutdown', signal: 'neutral', type: 'protocol', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Target Bot cannot attack or be attacked until end of next turn.',
    flavor: '"Safe mode engaged. Stand by."',
    keywords: [],
    imagePrompt: 'Robot entering emergency safe mode, amber warning lights, protective energy bubble forming around it, frozen and protected, silver and amber safe-mode glow with warning indicators, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_P04', name: 'EMP Blast', signal: 'neutral', type: 'protocol', rarity: 'common',
    cost: 2, power: 0, defense: 0,
    ability: 'Deal 1 damage to ALL Bots (both sides).',
    flavor: '"Indiscriminate. Effective."',
    keywords: [],
    imagePrompt: 'Electromagnetic pulse blast expanding outward in a ring, hitting all robots on both sides of the field, universal disruption, silver and electric white EMP wave with interference patterns, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_P05', name: 'Field Repair', signal: 'neutral', type: 'protocol', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Restore 2 Defense to all your Bots.',
    flavor: '"Patch everyone up. We go again."',
    keywords: [],
    imagePrompt: 'Repair wave sweeping across all allied robots, fixing minor damage on each one, field medic energy, silver and green healing wave across multiple targets, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_P06', name: 'Swap Parts', signal: 'neutral', type: 'protocol', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Swap the Power and Defense of 2 target Bots (can be on different sides).',
    flavor: '"What was yours is mine. What was mine is... also mine."',
    keywords: [],
    imagePrompt: 'Two robots having their stats visually swapped, power and defense numbers trading places through silver energy beams, strategic manipulation, silver and shifting multicolor stat-swap beams, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_P07', name: 'Tactical Retreat', signal: 'neutral', type: 'protocol', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Return target Bot you control to your hand. Draw 1 card.',
    flavor: '"Fall back. Regroup. Return stronger."',
    keywords: [],
    imagePrompt: 'Robot teleporting back to the hand zone in a flash of silver energy, tactical withdrawal, retreating to fight another day, silver and blue retreat-teleport effect, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_P08', name: 'Hijack', signal: 'neutral', type: 'protocol', rarity: 'uncommon',
    cost: 4, power: 0, defense: 0,
    ability: 'Take control of target enemy Bot with 3 or less Power until end of turn. It gains Rush.',
    flavor: '"Nice bot. Think I\'ll borrow it."',
    keywords: ['Rush'],
    imagePrompt: 'Purple-silver hacking beam overriding an enemy robot control system, the robot eye color changing from red to silver as control is seized, digital hijacking visualization, silver and shifting colors with override code overlay, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // CORE (1) — 1 Uncommon
  // ============================================================
  {
    id: 'SG_NT_C01', name: 'Neutral Ground', signal: 'neutral', type: 'core', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'All Bots (both sides) gain +1 Power. Signal advantages do not apply.',
    flavor: '"No faction. No advantage. Just skill."',
    keywords: [],
    imagePrompt: 'Neutral battlefield where all Signal colors are equalized, a flat gray arena where no faction has advantage, balanced and fair, all Signal colors muted to silver-gray equality, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // ADDITIONAL NEUTRAL (5 more to reach 150 total)
  // ============================================================
  {
    id: 'SG_NT_U04', name: 'Overhaul', signal: 'neutral', type: 'upgrade', rarity: 'uncommon',
    cost: 3, power: 0, defense: 0,
    ability: 'Fully restore target Bot\'s Defense. Give it +1 Power.',
    flavor: '"Good as new. Better, actually."',
    keywords: [],
    imagePrompt: 'Robot undergoing a full systems overhaul, panels open with repair drones working inside, emerging fully restored and improved, silver and clean white restoration glow, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_P09', name: 'Signal Flare', signal: 'neutral', type: 'protocol', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Draw 1 card. If you have no Bots on the Grid, draw 2 instead.',
    flavor: '"Is anyone out there?"',
    keywords: [],
    imagePrompt: 'Bright silver signal flare shooting into the dark sky, illuminating the battlefield, calling for reinforcements, hope in desperation, silver and bright white flare against dark background, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_P10', name: 'Dismantle', signal: 'neutral', type: 'protocol', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Destroy target Mod or Core card.',
    flavor: '"Nice upgrade. Was nice, anyway."',
    keywords: [],
    imagePrompt: 'Wrench-like energy tool deconstructing an equipped mod, pieces scattering as it is dismantled, targeted removal, silver and orange deconstruction sparks, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_M04', name: 'Salvaged Shield', signal: 'neutral', type: 'mod', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Defense. Equipped Bot gains Shield.',
    flavor: '"Found it in the Scrap Heap. Still works."',
    keywords: ['Shield'],
    imagePrompt: 'Dented but functional shield module salvaged from scrap, scratched surface with faint energy still glowing, resourceful and scrappy, silver and faded blue shield energy on worn metal, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_NT_U05', name: 'Recalibrate', signal: 'neutral', type: 'upgrade', rarity: 'common',
    cost: 0, power: 0, defense: 0,
    ability: 'Give target Bot +1 Power this turn.',
    flavor: '"Minor adjustment. Major difference."',
    keywords: [],
    imagePrompt: 'Small calibration tool making a precise adjustment to a robot, tiny tweak with visible improvement, simple and efficient, silver and minimal white precision glow, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
];
