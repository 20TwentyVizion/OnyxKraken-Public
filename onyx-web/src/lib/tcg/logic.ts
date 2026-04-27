import { Card } from './types';

export const LOGIC_CARDS: Card[] = [
  // ============================================================
  // BOTS (8) — 3 Common, 2 Uncommon, 1 Rare, 1 Epic, 1 Legendary
  // ============================================================
  {
    id: 'SG_LG_B01', name: 'Signal Drone', signal: 'logic', type: 'bot', rarity: 'common',
    cost: 1, power: 2, defense: 1, bodyType: 'sleek',
    ability: 'Link. +1 Power while an adjacent ally exists.',
    flavor: '"Small. Fast. Always watching."',
    keywords: ['Link'],
    imagePrompt: 'Small sleek blue robot drone with thin aerodynamic limbs, hovering above a data stream, glowing blue sensor eye, circuit board trails in the air behind it, server room background with holographic displays, blue and cyan color palette, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_B02', name: 'Firewall Sentry', signal: 'logic', type: 'bot', rarity: 'common',
    cost: 2, power: 1, defense: 4, bodyType: 'knight',
    ability: 'Guard. Must be attacked before other Bots.',
    flavor: '"Nothing gets through. Nothing."',
    keywords: ['Guard'],
    imagePrompt: 'Sturdy knight-type robot with a large hexagonal shield projecting a blue energy barrier, armored pauldrons with circuit engravings, standing at a digital checkpoint, defensive stance, data walls rising behind it, blue and silver color palette, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_B03', name: 'Data Miner', signal: 'logic', type: 'bot', rarity: 'common',
    cost: 2, power: 2, defense: 2, bodyType: 'retro',
    ability: 'When played, look at the top 2 cards of your deck. Put 1 on top and 1 on bottom.',
    flavor: '"Information is ammunition."',
    keywords: [],
    imagePrompt: 'Boxy retro-style robot with antenna nubs and dial gauges on its chest, mining through streams of blue data crystals with drill hands, underground server cavern with glowing blue veins, 1950s sci-fi meets modern tech, blue and warm amber accents, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_B04', name: 'Protocol Guardian', signal: 'logic', type: 'bot', rarity: 'uncommon',
    cost: 3, power: 2, defense: 4, bodyType: 'mech',
    ability: 'Versatile. Angry: When this Bot takes damage but survives, draw 1 card.',
    flavor: '"Every threat is a data point."',
    keywords: ['Versatile', 'Angry'],
    imagePrompt: 'Medium mech-type robot with blocky panel armor and a glowing blue power core in its chest, standing protectively over a cluster of smaller drones, one arm raised generating a holographic shield, sparks flying from a recent hit, blue and steel gray palette, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_B05', name: 'Mirror Node', signal: 'logic', type: 'bot', rarity: 'uncommon',
    cost: 4, power: 3, defense: 3, bodyType: 'orb',
    ability: 'Shield. Restore. Heals 1 Defense to an adjacent ally at end of turn.',
    flavor: '"Reflect. Restore. Repeat."',
    keywords: ['Shield', 'Restore'],
    imagePrompt: 'Spherical orb-type robot with a mirrored surface reflecting blue light in all directions, gentle glow emanating from its core, floating above a platform of interlocking hexagons, healing energy radiating outward to nearby allies, serene digital garden background, blue and white palette with prismatic reflections, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_B06', name: 'Cipher Knight', signal: 'logic', type: 'bot', rarity: 'rare',
    cost: 5, power: 4, defense: 5, bodyType: 'knight',
    ability: 'Guard. Confident: When this Bot destroys an enemy, gain +2 Defense and Shield.',
    flavor: '"The code is my sword. Logic is my armor."',
    keywords: ['Guard', 'Confident'],
    imagePrompt: 'Imposing knight-type robot with layered blue armor plates and a visor that displays scrolling code, wielding a sword made of compressed data, standing atop a digital fortress wall, cape made of flowing data streams, defeated enemy bot sparking at its feet, royal blue and platinum color palette, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_B07', name: 'Quantum Architect', signal: 'logic', type: 'bot', rarity: 'epic',
    cost: 6, power: 4, defense: 6, bodyType: 'cyber',
    ability: 'Chain. When this Bot\'s ability activates, draw 1. Overclock: When Defense drops to 3 or below, draw 3 cards and all allied Bots gain +1 Power.',
    flavor: '"I don\'t predict the future. I compile it."',
    keywords: ['Chain', 'Overclock'],
    imagePrompt: 'Tall cyber-type robot with a transparent holographic shell revealing intricate circuit pathways beneath, multiple floating holographic screens orbiting its head showing battle calculations, hands weaving quantum data structures in mid-air, futuristic command center background with star maps, brilliant blue and electric cyan with transparent glass effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_B08', name: 'Onyx — Signal Commander', signal: 'logic', type: 'bot', rarity: 'legendary',
    cost: 7, power: 5, defense: 7, bodyType: 'mech',
    ability: 'Versatile. When played, draw 2 cards. Confident: When Onyx destroys an enemy, all allies gain +1 Power. Overclock: When Defense drops to 3 or below, take control of target enemy Bot for 1 turn.',
    flavor: '"Every signal has a frequency. I know them all."',
    keywords: ['Versatile', 'Confident', 'Overclock'],
    imagePrompt: 'Onyx, the iconic cyan mech-type robot commander, standing heroically atop a command platform with arms crossed, glowing cyan power core pulsing in chest, holographic tactical display projected around him showing the entire battlefield, data streams flowing into his body from all directions, massive server towers in the background with the Nexus skyline, dramatic cyan and dark blue palette with white highlights, epic scale, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // MODS (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_LG_M01', name: 'Logic Shield', signal: 'logic', type: 'mod', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Equip to Bot: +2 Defense.',
    flavor: '"A simple calculation: survive."',
    keywords: [],
    imagePrompt: 'Hexagonal blue energy shield module with circuit patterns etched into its surface, glowing softly, floating above an open palm, clean geometric design, blue and silver, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_M02', name: 'Scan Visor', signal: 'logic', type: 'mod', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Power. When equipped Bot attacks, look at the top card of your deck.',
    flavor: '"See everything. Miss nothing."',
    keywords: [],
    imagePrompt: 'Sleek blue visor attachment with holographic targeting reticle projected from the lens, scanning data overlay visible, compact and modular design, floating against a dark background with blue light trails, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_M03', name: 'Overclock Capacitor', signal: 'logic', type: 'mod', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Power, +1 Defense. If equipped Bot has Overclock, its Overclock triggers at 4 Defense instead of 3.',
    flavor: '"Earlier activation. Higher stakes."',
    keywords: [],
    imagePrompt: 'Cylindrical capacitor module crackling with blue electricity, overcharged energy visibly straining the containment field, wires and conduits branching from it, installed on a robot chest plate, blue and white energy arcs, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_M04', name: 'Reflector Plating', signal: 'logic', type: 'mod', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Equip to Bot: +3 Defense. Equipped Bot gains Armored.',
    flavor: '"What doesn\'t kill you makes you a better dataset."',
    keywords: ['Armored'],
    imagePrompt: 'Thick angular armor plating with a mirror-like blue finish, reflecting laser fire in multiple directions, geometric facets catching light, bolted onto a robot torso, defensive and imposing, blue chrome and steel, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_M05', name: 'Neural Uplink', signal: 'logic', type: 'mod', rarity: 'rare',
    cost: 3, power: 0, defense: 0,
    ability: 'Equip to Bot: +2 Power, +2 Defense. Equipped Bot gains Chain (draw 1 on ability trigger).',
    flavor: '"Direct connection to the Nexus mainframe."',
    keywords: ['Chain'],
    imagePrompt: 'Intricate neural interface crown that connects to a robot head via blue fiber optic cables, data flowing visibly through translucent tubes, holographic data readouts floating around it, the Nexus mainframe towering in the background, blue and white with gold connector accents, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // PROTOCOLS (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_LG_P01', name: 'System Scan', signal: 'logic', type: 'protocol', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Draw 2 cards.',
    flavor: '"Scanning... scanning... targets acquired."',
    keywords: [],
    imagePrompt: 'Holographic scanning wave sweeping across a battlefield, revealing hidden data and card outlines in the air, blue gridlines expanding outward from a central point, clean geometric aesthetic, blue and white, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_P02', name: 'Countermeasure', signal: 'logic', type: 'protocol', rarity: 'common',
    cost: 2, power: 0, defense: 0,
    ability: 'Give target Bot +3 Defense this turn. If it has Guard, give it Shield instead.',
    flavor: '"Calculated. Countered. Canceled."',
    keywords: [],
    imagePrompt: 'Blue energy barrier erupting from the ground in a hexagonal pattern, deflecting an incoming red energy blast, sparks and data fragments scattering on impact, defensive matrix visualization, blue versus red energy clash, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_P03', name: 'Memory Wipe', signal: 'logic', type: 'protocol', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Return target enemy Bot with 3 or less Power to its owner\'s hand.',
    flavor: '"Error 404: Bot not found."',
    keywords: [],
    imagePrompt: 'A robot dissolving into fragments of blue data as its memory is wiped, pieces floating upward and dematerializing, corrupted code visible in the dissolving sections, dark background with blue particle effects, eerie and clinical, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_P04', name: 'Recursive Analysis', signal: 'logic', type: 'protocol', rarity: 'uncommon',
    cost: 3, power: 0, defense: 0,
    ability: 'Draw 3 cards, then put 1 card from your hand on the bottom of your deck.',
    flavor: '"Run it again. And again. And again."',
    keywords: [],
    imagePrompt: 'Infinite recursive loop visualization — mirrors reflecting mirrors of holographic data screens, each showing a deeper layer of analysis, fractal patterns in blue light, a robot hand reaching into the recursion, mesmerizing depth effect, blue and white with recursive geometry, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_P05', name: 'Total Lockdown', signal: 'logic', type: 'protocol', rarity: 'rare',
    cost: 4, power: 0, defense: 0,
    ability: 'All enemy Bots lose all keywords and abilities until end of next turn.',
    flavor: '"Access denied. All of it."',
    keywords: [],
    imagePrompt: 'Massive blue firewall grid descending over the entire battlefield, locking all enemy robots in place with energy cages, chains of code wrapping around frozen bots, authoritarian and absolute, blue and steel gray with red warning lights on the trapped bots, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // UPGRADES (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_LG_U01', name: 'Firmware Patch', signal: 'logic', type: 'upgrade', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Give target Bot +1 Power and +1 Defense.',
    flavor: '"Version 2.0.1: minor improvements."',
    keywords: [],
    imagePrompt: 'Software update progress bar projected holographically on a robot, lines of blue code scrolling rapidly, small improvement indicators appearing as checkmarks, simple and clean, blue and white interface aesthetic, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_U02', name: 'Diagnostic Pulse', signal: 'logic', type: 'upgrade', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Restore 3 Defense to target Bot.',
    flavor: '"Damage report: repairable."',
    keywords: [],
    imagePrompt: 'Blue healing pulse wave emanating from a diagnostic tool, repairing cracks and damage on a robot surface, sparks of restoration energy filling wounds, calm and precise repair process, blue and white healing glow, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_U03', name: 'Priority Queue', signal: 'logic', type: 'upgrade', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Give target Bot +2 Power. If it has Guard, give it +3 Power instead.',
    flavor: '"Threat level: elevated. Response: escalated."',
    keywords: [],
    imagePrompt: 'Queue of holographic priority targets arranged by threat level, red warning indicators on highest priority, a robot commander reviewing the tactical display, strategic and organized, blue with red priority highlights, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_U04', name: 'Backup Protocol', signal: 'logic', type: 'upgrade', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Give target Bot Shield. Draw 1 card.',
    flavor: '"Always have a backup. Always."',
    keywords: ['Shield'],
    imagePrompt: 'Blue holographic backup copy of a robot being stored in a data vault, the original and the backup facing each other, protective energy field surrounding the backup, data vault with shelves of stored robot blueprints, blue and silver with golden data accents, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_U05', name: 'Core Synchronization', signal: 'logic', type: 'upgrade', rarity: 'rare',
    cost: 3, power: 0, defense: 0,
    ability: 'All allied Bots gain +1 Power and +1 Defense. Draw 1 card.',
    flavor: '"All systems aligned. All cores synchronized. All threats neutralized."',
    keywords: [],
    imagePrompt: 'Multiple robots connected by beams of synchronized blue energy, their power cores pulsing in unison, harmonic resonance wave visible between them, unified formation, command center background with holographic displays all showing green status, blue and white with pulsing energy accents, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // CORES (2) — 1 Common, 1 Uncommon
  // ============================================================
  {
    id: 'SG_LG_C01', name: 'Logic Sector Relay', signal: 'logic', type: 'core', rarity: 'common',
    cost: 2, power: 0, defense: 0,
    ability: 'All your LOGIC Bots gain +1 Defense.',
    flavor: '"Home field advantage: calculated."',
    keywords: [],
    imagePrompt: 'Massive blue relay tower broadcasting a defensive signal field over a sector of the Grid, hexagonal shield domes covering friendly positions, LOGIC faction banner flying from the spire, imposing digital fortress aesthetic, blue and silver, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_LG_C02', name: 'The Nexus Archive', signal: 'logic', type: 'core', rarity: 'uncommon',
    cost: 3, power: 0, defense: 0,
    ability: 'At the start of your turn, look at the top card of your deck. You may put it on the bottom.',
    flavor: '"Every battle ever fought. Every strategy ever devised. All catalogued."',
    keywords: [],
    imagePrompt: 'Ancient massive digital library with towering shelves of glowing blue data crystals, holographic books floating in organized rows, a central pedestal projecting a map of the entire Nexus, awe-inspiring scale and knowledge, deep blue with golden light from the crystals, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
];
