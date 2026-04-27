import { Card } from './types';

export const STATIC_CARDS: Card[] = [
  // ============================================================
  // BOTS (8) — 3 Common, 2 Uncommon, 1 Rare, 1 Epic, 1 Legendary
  // ============================================================
  {
    id: 'SG_ST_B01', name: 'Glitch Rat', signal: 'static', type: 'bot', rarity: 'common',
    cost: 1, power: 2, defense: 1, bodyType: 'skeletal',
    ability: 'When played, opponent discards 1 random card.',
    flavor: '"It\'s in your system. Good luck finding it."',
    keywords: [],
    imagePrompt: 'Small skeletal wireframe rat-shaped robot with exposed spine, skittering through corrupted data streams, yellow glitch artifacts trailing behind it, chewing on data cables, dark cyber-alley background with static-filled screens, yellow and dark gray with glitch distortion, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_B02', name: 'Noise Generator', signal: 'static', type: 'bot', rarity: 'common',
    cost: 2, power: 2, defense: 2, bodyType: 'retro',
    ability: 'When played, deal 1 damage to all enemy Bots.',
    flavor: '"BZZZZZT. Sorry, what was your strategy again?"',
    keywords: [],
    imagePrompt: 'Boxy retro-style yellow robot with antenna arrays broadcasting visible noise waves in all directions, screens on its chest displaying static patterns, disruptive sound visualized as yellow shockwaves hitting enemies, broadcast tower background, yellow and black with white noise static, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_B03', name: 'Feedback Drone', signal: 'static', type: 'bot', rarity: 'common',
    cost: 2, power: 3, defense: 1, bodyType: 'sleek',
    ability: 'Swift. Deals combat damage before the defender.',
    flavor: '"The screech you hear is the last thing you process."',
    keywords: ['Swift'],
    imagePrompt: 'Sleek yellow drone-type robot emitting a piercing feedback screech visualized as jagged yellow soundwaves, aerodynamic body with speaker arrays, moving fast through a corrupted digital corridor, yellow and electric white with harsh noise visualization, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_B04', name: 'Signal Jammer', signal: 'static', type: 'bot', rarity: 'uncommon',
    cost: 3, power: 2, defense: 3, bodyType: 'cyber',
    ability: 'Enemy Bots cost 1 more Charge to play while Signal Jammer is on the Grid.',
    flavor: '"Your plans? Delayed. Indefinitely."',
    keywords: [],
    imagePrompt: 'Cyber-type yellow robot with a massive jamming dish on its back broadcasting disruptive signals, enemy holographic displays flickering and glitching around it, standing in a field of scrambled data, interference patterns radiating outward, yellow and dark purple interference with static overlay, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_B05', name: 'Trap Layer', signal: 'static', type: 'bot', rarity: 'uncommon',
    cost: 3, power: 2, defense: 4, bodyType: 'mech',
    ability: 'Versatile. When an enemy Bot attacks this Bot, deal 2 damage to the attacker before combat.',
    flavor: '"Go ahead. Attack. I dare you."',
    keywords: ['Versatile'],
    imagePrompt: 'Mech-type yellow robot crouched in a defensive posture surrounded by glowing yellow energy mines and trip-wire lasers, bait stance with hidden dangers everywhere, smug expression on its visor, minefield background with warning holograms, yellow and hazard-orange with trap glow effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_B06', name: 'Corruption Agent', signal: 'static', type: 'bot', rarity: 'rare',
    cost: 5, power: 4, defense: 4, bodyType: 'cyber',
    ability: 'Chain. When played, look at opponent\'s hand and discard 1 card of your choice. Angry: When this takes damage but survives, opponent discards 1 random card.',
    flavor: '"I don\'t destroy your bots. I destroy your options."',
    keywords: ['Chain', 'Angry'],
    imagePrompt: 'Sinister cyber-type yellow robot with corrupted data tendrils extending from its hands into an enemy holographic hand display, selectively deleting cards, half its body glitched with static artifacts, corrupted data room background, yellow and dark violet corruption with static-glitch overlay, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_B07', name: 'Paradox Engine', signal: 'static', type: 'bot', rarity: 'epic',
    cost: 6, power: 5, defense: 5, bodyType: 'retro',
    ability: 'When this Bot attacks, opponent discards 1 card. Overclock: When Defense drops to 3 or below, destroy ALL Mods on the field and deal 1 damage per Mod destroyed to opponent\'s Core.',
    flavor: '"Nothing works the way it should. That IS the way it should work."',
    keywords: ['Overclock'],
    imagePrompt: 'Massive retro-style yellow robot with impossible geometry — parts phasing in and out of reality, Escher-like mechanical components, paradoxical gears turning in contradictory directions, reality warping around it with yellow static cracks in space, surreal glitch-dimension background, yellow and reality-distortion purple with paradox effects, epic scale, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_B08', name: 'Xyno — Chaos Architect', signal: 'static', type: 'bot', rarity: 'legendary',
    cost: 7, power: 5, defense: 6, bodyType: 'cyber',
    ability: 'When played, opponent discards 2 cards. When Xyno attacks, deal 1 damage to ALL enemy Bots. Overclock: When Defense drops to 3 or below, opponent discards their entire hand.',
    flavor: '"Chaos isn\'t the absence of order. It\'s MY order."',
    keywords: ['Overclock'],
    imagePrompt: 'Xyno, the iconic chaos architect robot with a glitched cyber-frame body, digitized legs phasing through reality, jammer arrays broadcasting chaos across the battlefield, one hand deleting enemy cards from existence while the other rearranges the fabric of the Grid itself, static lightning arcing between all enemy bots, throne of corrupted data in a shattered dimension, yellow and electric purple with heavy glitch-art distortion, holographic chaos crown, epic scale, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // MODS (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_ST_M01', name: 'Static Charge', signal: 'static', type: 'mod', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Power. When equipped Bot is attacked, deal 1 damage to the attacker.',
    flavor: '"Touch it. I\'ll wait."',
    keywords: [],
    imagePrompt: 'Crackling yellow static electricity field surrounding a robot component, arcs of electricity snapping at anything nearby, charged capacitor module, yellow and white electric arcs on dark background, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_M02', name: 'Scrambler Module', signal: 'static', type: 'mod', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Defense. Equipped Bot cannot be targeted by enemy Protocols.',
    flavor: '"Can\'t hack what you can\'t find."',
    keywords: [],
    imagePrompt: 'Small yellow scrambler device creating a bubble of signal interference around itself, enemy targeting systems shown as broken/scrambled red lines bouncing off, stealth-tech meets disruption, yellow and dark gray with interference patterns, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_M03', name: 'Virus Injector', signal: 'static', type: 'mod', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Equip to Bot: +2 Power. When equipped Bot deals combat damage to a Bot, that Bot loses all keywords until end of turn.',
    flavor: '"One touch. All systems compromised."',
    keywords: [],
    imagePrompt: 'Syringe-like yellow weapon attachment with visible virus code swirling inside, corrupted data dripping from the needle tip, menacing injection mechanism, yellow and toxic green virus code, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_M04', name: 'Feedback Amplifier', signal: 'static', type: 'mod', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Power, +2 Defense. Whenever opponent plays a Protocol, deal 1 damage to their Core.',
    flavor: '"Every spell they cast costs them."',
    keywords: [],
    imagePrompt: 'Large amplifier dish attached to a robot back, channeling yellow feedback energy, every enemy action creating a backlash pulse aimed at the opponent, amplification waves radiating, yellow and orange feedback energy with speaker-cone visual, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_M05', name: 'Chaos Engine', signal: 'static', type: 'mod', rarity: 'rare',
    cost: 3, power: 0, defense: 0,
    ability: 'Equip to Bot: +2 Power, +2 Defense. At start of your turn, opponent discards 1 random card.',
    flavor: '"Order is a temporary illusion. Chaos is the natural state."',
    keywords: [],
    imagePrompt: 'Impossible mechanical engine with gears turning in contradictory directions, yellow chaos energy leaking from every seam, warping nearby reality, mounted on a robot chassis, the engine of pure disruption, yellow and dark purple with reality-warp effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // PROTOCOLS (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_ST_P01', name: 'Interference', signal: 'static', type: 'protocol', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Opponent discards 1 random card.',
    flavor: '"CONNECTION LOST."',
    keywords: [],
    imagePrompt: 'Yellow static interference wave disrupting a holographic hand of cards, one card dissolving into noise particles, signal-lost screen in background, harsh and disruptive, yellow and dark static-gray, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_P02', name: 'Short Circuit', signal: 'static', type: 'protocol', rarity: 'common',
    cost: 2, power: 0, defense: 0,
    ability: 'Deal 2 damage to target Bot. That Bot loses all keywords until end of turn.',
    flavor: '"ZAP. Oops. There go your abilities."',
    keywords: [],
    imagePrompt: 'Yellow lightning bolt causing a short circuit in a robot, sparks flying from every joint, abilities visually shorting out as keyword icons fizzle and die, yellow and electric white with sparking effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_P03', name: 'Scramble Signal', signal: 'static', type: 'protocol', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Return target enemy Bot with 4 or less Defense to its owner\'s hand.',
    flavor: '"Signal lost. Returning to base."',
    keywords: [],
    imagePrompt: 'Enemy robot being forcefully teleported away in a burst of yellow scrambled data, its form dissolving into static as the signal is scrambled, forced retreat effect, yellow and interference-purple with teleport distortion, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_P04', name: 'Noise Bomb', signal: 'static', type: 'protocol', rarity: 'uncommon',
    cost: 3, power: 0, defense: 0,
    ability: 'Deal 1 damage to ALL Bots. Opponent discards 1 card for each Bot that was destroyed.',
    flavor: '"MAXIMUM VOLUME. ZERO SIGNAL."',
    keywords: [],
    imagePrompt: 'Massive yellow noise bomb detonating in the center of the battlefield, concussive rings of static energy hitting everything, all bots staggering, screens cracking, pure sonic chaos, yellow and white shockwave with black disruption cracks, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_P05', name: 'System Crash', signal: 'static', type: 'protocol', rarity: 'rare',
    cost: 5, power: 0, defense: 0,
    ability: 'Destroy target enemy Bot. Opponent discards 1 card.',
    flavor: '"FATAL ERROR: UNRECOVERABLE."',
    keywords: [],
    imagePrompt: 'Robot experiencing a catastrophic system crash — blue screen of death displayed on its visor, body seizing and sparking, cascading failure spreading through its systems, collapsing into a heap of broken parts, yellow crash-screen glow with red critical errors, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // UPGRADES (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_ST_U01', name: 'Signal Spike', signal: 'static', type: 'upgrade', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Deal 1 damage to target Bot. Draw 1 card.',
    flavor: '"A little poke. A lot of information."',
    keywords: [],
    imagePrompt: 'Sharp yellow signal spike piercing through a target, data fragments scattered from the impact point, quick and precise disruption, yellow and white spike energy, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_U02', name: 'Disrupt', signal: 'static', type: 'upgrade', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Target enemy Bot loses 2 Power until end of turn.',
    flavor: '"Your strength? Temporarily unavailable."',
    keywords: [],
    imagePrompt: 'Yellow disruption wave hitting an enemy robot, its power visibly draining as yellow static envelops its weapon systems, weakened and confused, yellow and dim-gray power drain effect, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_U03', name: 'Data Corruption', signal: 'static', type: 'upgrade', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Look at opponent\'s hand. Choose 1 card — it costs 2 more Charge next turn.',
    flavor: '"I can see your plans. And I don\'t like them."',
    keywords: [],
    imagePrompt: 'Holographic display of enemy hand being corrupted, one card being infected with yellow virus code that increases its cost, strategic sabotage visualization, yellow and dark purple corruption spreading across the card, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_U04', name: 'Feedback Loop', signal: 'static', type: 'upgrade', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Deal 2 damage to target Bot. If it has any keywords, deal 3 damage instead.',
    flavor: '"The more complex you are, the harder you crash."',
    keywords: [],
    imagePrompt: 'Yellow feedback energy loop spiraling around a complex robot, its own keywords feeding back as destructive energy, more abilities meaning more damage, recursive destruction loop visualization, yellow and orange with feedback spiral effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_U05', name: 'Total Blackout', signal: 'static', type: 'upgrade', rarity: 'rare',
    cost: 4, power: 0, defense: 0,
    ability: 'All enemy Bots lose all keywords and abilities until end of next turn. Opponent discards 1 card.',
    flavor: '"Lights out. Everyone."',
    keywords: [],
    imagePrompt: 'Entire enemy side of the battlefield going dark — all lights, displays, and energy systems shutting down in a cascading blackout wave, robots standing frozen and powerless, only yellow static-snow illuminating the darkness, total shutdown aesthetic, yellow static on pitch black, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // CORES (2) — 1 Common, 1 Uncommon
  // ============================================================
  {
    id: 'SG_ST_C01', name: 'Static Field', signal: 'static', type: 'core', rarity: 'common',
    cost: 2, power: 0, defense: 0,
    ability: 'All your STATIC Bots gain +1 Power.',
    flavor: '"Everything within the field answers to noise."',
    keywords: [],
    imagePrompt: 'Persistent yellow static energy field covering an area of the Grid, crackling with constant disruption, anything entering the field gets distorted, yellow and electric white static field with dark edges, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_ST_C02', name: 'The Dead Zone', signal: 'static', type: 'core', rarity: 'uncommon',
    cost: 3, power: 0, defense: 0,
    ability: 'Whenever opponent plays a card, there is a 50% chance they discard 1 random card. (Flip a coin or random.)',
    flavor: '"In the Dead Zone, nothing works reliably. Not even hope."',
    keywords: [],
    imagePrompt: 'Eerie dead zone where all signals die — floating debris of destroyed robots and corrupted data hanging motionless in the air, no light except flickering yellow static, oppressive and suffocating, yellow static on absolute darkness with floating debris, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
];
