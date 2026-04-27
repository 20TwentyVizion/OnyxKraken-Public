import { Card } from './types';

export const PULSE_CARDS: Card[] = [
  // ============================================================
  // BOTS (8) — 3 Common, 2 Uncommon, 1 Rare, 1 Epic, 1 Legendary
  // ============================================================
  {
    id: 'SG_PL_B01', name: 'Spark Runner', signal: 'pulse', type: 'bot', rarity: 'common',
    cost: 1, power: 2, defense: 1, bodyType: 'sleek',
    ability: 'Rush. Can attack the turn it is played.',
    flavor: '"First in, first strike, first blood."',
    keywords: ['Rush'],
    imagePrompt: 'Small sleek red robot sprinting at incredible speed, leaving red lightning trails behind it, aerodynamic limbs with speed-line effects, arena corridor with sparking walls, red and orange color palette, motion blur, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_B02', name: 'Shockwave Bruiser', signal: 'pulse', type: 'bot', rarity: 'common',
    cost: 2, power: 3, defense: 2, bodyType: 'heavy',
    ability: 'When played, deal 1 damage to a random enemy Bot.',
    flavor: '"Subtlety is for bots with time to waste."',
    keywords: [],
    imagePrompt: 'Bulky heavy-type red robot with massive shoulder plates and riveted armor, slamming a fist into the ground creating a shockwave of red energy, arena dust cloud rising, aggressive stance, red and gunmetal gray palette, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_B03', name: 'Arc Welder', signal: 'pulse', type: 'bot', rarity: 'common',
    cost: 2, power: 3, defense: 1, bodyType: 'skeletal',
    ability: 'Piercing. Excess combat damage hits opponent\'s Core.',
    flavor: '"Cuts through armor. Cuts through everything."',
    keywords: ['Piercing'],
    imagePrompt: 'Skeletal wireframe robot with exposed spine and rib cage structure, wielding crackling red arc welding beams from both claw hands, molten sparks flying everywhere, industrial forge background with red-hot metal, red and dark steel palette, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_B04', name: 'Blitz Striker', signal: 'pulse', type: 'bot', rarity: 'uncommon',
    cost: 3, power: 4, defense: 2, bodyType: 'sleek',
    ability: 'Rush. Swift. Deals combat damage before the defender.',
    flavor: '"You won\'t see me. You\'ll only feel the impact."',
    keywords: ['Rush', 'Swift'],
    imagePrompt: 'Ultra-aerodynamic sleek red robot mid-leap with blade arms extended, afterimage effect showing its speed, targeting reticle on an enemy, arena with cheering crowd silhouettes, red and white speed lines, dynamic action pose, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_B05', name: 'Demolition Core', signal: 'pulse', type: 'bot', rarity: 'uncommon',
    cost: 3, power: 3, defense: 3, bodyType: 'heavy',
    ability: 'Volatile. When destroyed, deal 2 damage to all adjacent Bots. Angry: When this takes damage but survives, gain +1 Power.',
    flavor: '"The closer you get, the worse it gets."',
    keywords: ['Volatile', 'Angry'],
    imagePrompt: 'Heavily armored red robot with a visibly unstable glowing reactor core in its chest, warning symbols on its hull, cracks leaking red energy, standing in a blast crater from a previous explosion, ready to detonate again, red and hazard-yellow accents, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_B06', name: 'Railgun Sentinel', signal: 'pulse', type: 'bot', rarity: 'rare',
    cost: 5, power: 6, defense: 3, bodyType: 'mech',
    ability: 'When played, deal 3 damage to target enemy Bot. Piercing.',
    flavor: '"One shot. One kill. One signal."',
    keywords: ['Piercing'],
    imagePrompt: 'Mech-type red robot with a massive electromagnetic railgun arm, the barrel glowing white-hot with charged energy, standing on a firing platform overlooking a battlefield, shell casings and smoke around its feet, sniper scope visor glowing red, red and chrome palette with white energy, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_B07', name: 'Inferno Engine', signal: 'pulse', type: 'bot', rarity: 'epic',
    cost: 6, power: 5, defense: 5, bodyType: 'heavy',
    ability: 'Armored. When this Bot attacks, deal 1 damage to ALL enemy Bots. Overclock: When Defense drops to 3 or below, gain +4 Power and Rush.',
    flavor: '"The engine doesn\'t stop. The engine doesn\'t slow. The engine BURNS."',
    keywords: ['Armored', 'Overclock'],
    imagePrompt: 'Massive heavy-type red robot shaped like a walking engine block, exhaust pipes belching fire, molten metal dripping from joints, treads for feet crushing the ground, engine roar visualized as red shockwaves, volcanic industrial wasteland background, deep red and molten orange with black smoke, epic scale, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_B08', name: 'Volt — Thunderstrike', signal: 'pulse', type: 'bot', rarity: 'legendary',
    cost: 7, power: 7, defense: 5, bodyType: 'sleek',
    ability: 'Rush. Swift. When Volt attacks, deal 2 damage to all other enemy Bots. Overclock: When Defense drops to 3 or below, Volt attacks twice this turn and gains +3 Power.',
    flavor: '"Lightning never strikes twice? Watch me."',
    keywords: ['Rush', 'Swift', 'Overclock'],
    imagePrompt: 'Volt, the iconic amber-lightning sleek robot, in a dynamic mid-strike pose with both blade arms crackling with red and amber electricity, chain lightning arcing from Volt to multiple enemy targets simultaneously, speed lines and afterimages showing impossible velocity, arena of champions with electrified walls, dramatic red and electric amber palette with white lightning, epic scale, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // MODS (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_PL_M01', name: 'Power Cell', signal: 'pulse', type: 'mod', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Equip to Bot: +2 Power.',
    flavor: '"Raw energy. No safety features."',
    keywords: [],
    imagePrompt: 'Glowing red cylindrical power cell with crackling energy visible through its casing, arcs of electricity connecting its terminals, simple but powerful, red and amber glow on dark background, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_M02', name: 'Targeting Array', signal: 'pulse', type: 'mod', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Power. Equipped Bot gains Piercing.',
    flavor: '"Aim for the Core. Always the Core."',
    keywords: ['Piercing'],
    imagePrompt: 'Red holographic targeting array with multiple laser sights converging on a point, crosshair display, heat-seeking indicators, attached to a robot shoulder mount, red and orange targeting lasers, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_M03', name: 'Berserker Chip', signal: 'pulse', type: 'mod', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Equip to Bot: +2 Power. Equipped Bot gains Rush but loses 1 Defense.',
    flavor: '"Override all safety protocols. ATTACK."',
    keywords: ['Rush'],
    imagePrompt: 'Small menacing red microchip with aggressive circuit patterns, emitting a red haze of rage energy, warning labels scratched off, installed in a robot brain casing with red override glow, aggressive and dangerous, red and black, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_M04', name: 'Afterburner', signal: 'pulse', type: 'mod', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Power, +1 Defense. Equipped Bot gains Swift.',
    flavor: '"Activate. Accelerate. Annihilate."',
    keywords: ['Swift'],
    imagePrompt: 'Twin jet afterburner pack attached to a robot back, red flame exhausts roaring with power, heat shimmer distortion around the engines, rocket fuel lines glowing, speed and aggression incarnate, red and orange fire with chrome hardware, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_M05', name: 'Unstable Reactor', signal: 'pulse', type: 'mod', rarity: 'rare',
    cost: 3, power: 0, defense: 0,
    ability: 'Equip to Bot: +3 Power. When equipped Bot is destroyed, deal 4 damage to opponent\'s Core.',
    flavor: '"It\'s not a flaw. It\'s a feature."',
    keywords: [],
    imagePrompt: 'Dangerously glowing red reactor core with visible cracks and containment warnings, energy leaking from fractures, installed in a robot chest with exposed wiring, ticking time bomb aesthetic, red and hazard-orange with white-hot core center, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // PROTOCOLS (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_PL_P01', name: 'Pulse Strike', signal: 'pulse', type: 'protocol', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Deal 2 damage to target Bot.',
    flavor: '"Fast. Clean. Effective."',
    keywords: [],
    imagePrompt: 'Concentrated beam of red pulse energy striking a robot target, impact crater and sparks on the hit point, clean surgical strike, red energy beam cutting through the air, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_P02', name: 'Overcharge', signal: 'pulse', type: 'protocol', rarity: 'common',
    cost: 2, power: 0, defense: 0,
    ability: 'Give target Bot +3 Power this turn. That Bot takes 1 damage at end of turn.',
    flavor: '"More power. MORE. Worry about the bill later."',
    keywords: [],
    imagePrompt: 'Robot being supercharged with red electricity, power levels visibly exceeding safe limits, sparks and arcs flying from every joint, eyes glowing bright red, power gauge shattering its maximum, red and white overcharge energy, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_P03', name: 'Chain Lightning', signal: 'pulse', type: 'protocol', rarity: 'uncommon',
    cost: 3, power: 0, defense: 0,
    ability: 'Deal 2 damage to target Bot. If it survives, deal 2 damage to another random enemy Bot.',
    flavor: '"It jumps. It always jumps."',
    keywords: [],
    imagePrompt: 'Red lightning bolt chaining between multiple robot targets, each hit creating a new arc to the next victim, chain reaction of electrical destruction, robots recoiling from sequential impacts, arena background, red and white lightning on dark background, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_P04', name: 'Reckless Charge', signal: 'pulse', type: 'protocol', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Give all your Bots +2 Power and Rush this turn. They each take 1 damage at end of turn.',
    flavor: '"EVERYONE. CHARGE. NOW."',
    keywords: ['Rush'],
    imagePrompt: 'Army of red robots all charging forward simultaneously in a reckless all-out assault, red energy auras blazing around each one, dust clouds and destruction in their wake, war cry energy, chaotic and aggressive, red and amber battle-charge with motion blur, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_P05', name: 'Meltdown', signal: 'pulse', type: 'protocol', rarity: 'rare',
    cost: 5, power: 0, defense: 0,
    ability: 'Deal 4 damage to ALL Bots (yours and opponent\'s). Your PULSE Bots take 1 less.',
    flavor: '"Everything burns. Some things burn better."',
    keywords: [],
    imagePrompt: 'Cataclysmic explosion of red energy engulfing the entire battlefield, all robots caught in the blast wave, the ground cracking and melting, nuclear meltdown aesthetic with mushroom cloud of red data particles, total devastation, deep red and white-hot center with black scorched edges, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // UPGRADES (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_PL_U01', name: 'Adrenaline Surge', signal: 'pulse', type: 'upgrade', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Give target Bot +2 Power this turn.',
    flavor: '"SYSTEMS OVERCLOCKED. ENGAGING."',
    keywords: [],
    imagePrompt: 'Red adrenaline energy spike surging through a robot, power meters spiking, eyes flaring red, temporary but explosive boost, red and amber surge effect, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_U02', name: 'Quick Repair', signal: 'pulse', type: 'upgrade', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Give target Bot +1 Power and restore 1 Defense.',
    flavor: '"Patch it up. Get back in."',
    keywords: [],
    imagePrompt: 'Quick field repair on a battle-damaged robot, sparks from a welding tool, hasty but functional patching, red emergency repair lights, battlefield triage aesthetic, red and orange repair glow, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_U03', name: 'Battle Frenzy', signal: 'pulse', type: 'upgrade', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Give target Bot +2 Power. If it has Rush, give it +3 Power instead.',
    flavor: '"The first hit is free. Everything after costs extra."',
    keywords: [],
    imagePrompt: 'Robot in a battle frenzy state with red rage aura, claws extended, eyes blazing, berserker energy radiating, multiple afterimages showing rapid attacks, arena combat, red and dark crimson frenzy effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_U04', name: 'Ignition Sequence', signal: 'pulse', type: 'upgrade', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Deal 3 damage to target Bot. If it\'s destroyed, gain 1 Charge this turn.',
    flavor: '"Ignition confirmed. Target eliminated."',
    keywords: [],
    imagePrompt: 'Ignition countdown display reaching zero, massive red energy blast launching from a cannon at a target, explosion on impact, countdown numbers floating in the air, military precision meets raw power, red and white ignition energy, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_U05', name: 'Total Assault', signal: 'pulse', type: 'upgrade', rarity: 'rare',
    cost: 4, power: 0, defense: 0,
    ability: 'All your Bots gain +2 Power permanently.',
    flavor: '"No retreat. No mercy. No survivors."',
    keywords: [],
    imagePrompt: 'Entire army of red robots powering up simultaneously, red energy pillars rising from each one, permanent power boost wave spreading across the formation, war drums of energy, unified assault force, deep red and crimson with golden power-up glow, epic scale, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // CORES (2) — 1 Common, 1 Uncommon
  // ============================================================
  {
    id: 'SG_PL_C01', name: 'Pulse Arena', signal: 'pulse', type: 'core', rarity: 'common',
    cost: 2, power: 0, defense: 0,
    ability: 'All your PULSE Bots gain +1 Power.',
    flavor: '"Welcome to the arena. There are no rules."',
    keywords: [],
    imagePrompt: 'Gladiatorial arena with red energy walls, combat platforms hovering over lava, cheering holographic crowd, weapons racks on the walls, aggressive combat venue, red and orange arena with molten light, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_PL_C02', name: 'The Crucible', signal: 'pulse', type: 'core', rarity: 'uncommon',
    cost: 3, power: 0, defense: 0,
    ability: 'When a Bot is destroyed (either side), deal 1 damage to both players\' Cores.',
    flavor: '"In the Crucible, everyone bleeds."',
    keywords: [],
    imagePrompt: 'Massive forge-arena where destroyed robots melt into a central crucible of molten red energy, the energy lashing out at both sides, dangerous and chaotic battlefield where destruction feeds more destruction, red and molten orange with black iron, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
];
