import { Card } from './types';

export const FLUX_CARDS: Card[] = [
  // ============================================================
  // BOTS (8) — 3 Common, 2 Uncommon, 1 Rare, 1 Epic, 1 Legendary
  // ============================================================
  {
    id: 'SG_FX_B01', name: 'Sprout Node', signal: 'flux', type: 'bot', rarity: 'common',
    cost: 1, power: 1, defense: 2, bodyType: 'orb',
    ability: 'Restore. Heals 1 Defense to an adjacent ally at end of turn.',
    flavor: '"From a single seed, a forest."',
    keywords: ['Restore'],
    imagePrompt: 'Small round orb-type green robot with a sprouting vine growing from its head, gentle green glow from its core, hovering above mossy circuitry, healing energy radiating to nearby allies, digital garden with bioluminescent plants, green and soft gold color palette, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_B02', name: 'Thornwall Defender', signal: 'flux', type: 'bot', rarity: 'common',
    cost: 2, power: 1, defense: 4, bodyType: 'knight',
    ability: 'Guard. When this Bot takes damage, gain +1 Power permanently.',
    flavor: '"Cut me. I grow back sharper."',
    keywords: ['Guard'],
    imagePrompt: 'Knight-type green robot covered in metallic thorns and vine armor, shield made of interwoven branches with green energy coursing through them, thorns growing longer where damage has been taken, overgrown ruins background with nature reclaiming tech, green and dark brown palette, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_B03', name: 'Pulse Vine', signal: 'flux', type: 'bot', rarity: 'common',
    cost: 2, power: 2, defense: 3, bodyType: 'cyber',
    ability: 'When played, restore 2 Defense to target allied Bot.',
    flavor: '"It wraps around the wounded. It makes them whole."',
    keywords: [],
    imagePrompt: 'Cyber-type green robot made of intertwined circuit-vines with a transparent shell showing flowing green data sap, tendrils reaching out to heal a nearby damaged robot, bioluminescent forest-lab background, green and teal with glowing circuit traces, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_B04', name: 'Adaptive Construct', signal: 'flux', type: 'bot', rarity: 'uncommon',
    cost: 3, power: 2, defense: 3, bodyType: 'mech',
    ability: 'Excited: When you play 2+ cards this turn, gain +1 Power and +1 Defense permanently.',
    flavor: '"Every input makes it stronger. Every battle makes it smarter."',
    keywords: ['Excited'],
    imagePrompt: 'Mech-type green robot with modular body panels that visibly shift and adapt, new armor growing over damaged sections, circuit patterns rearranging in real-time, surrounded by floating upgrade modules it is absorbing, evolving lab background, green and chrome with adaptive glow effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_B05', name: 'Canopy Sentinel', signal: 'flux', type: 'bot', rarity: 'uncommon',
    cost: 4, power: 3, defense: 4, bodyType: 'heavy',
    ability: 'Armored. Restore. At end of turn, heal 1 Defense to ALL allied Bots.',
    flavor: '"Under its branches, nothing falls."',
    keywords: ['Armored', 'Restore'],
    imagePrompt: 'Massive heavy-type green robot shaped like a walking tree, thick bark-like armor with green energy veins, canopy of circuit-branches spreading overhead creating a protective dome of green light over allies, ancient forest backdrop with towering tech-trees, green and dark bark brown with golden light filtering through, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_B06', name: 'Symbiote Weaver', signal: 'flux', type: 'bot', rarity: 'rare',
    cost: 5, power: 3, defense: 5, bodyType: 'cyber',
    ability: 'Chain. When played, give all allied Bots +1 Defense. Sad: When an allied Bot is destroyed, gain +2 Power and +2 Defense.',
    flavor: '"Loss only makes the network stronger."',
    keywords: ['Chain', 'Sad'],
    imagePrompt: 'Cyber-type green robot with a web of symbiotic connections linking it to all nearby allies, glowing green threads of shared energy, visibly absorbing the essence of a fallen ally and growing stronger, circuit-web patterns expanding, deep forest command center, green and bioluminescent blue with mourning purple accents, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_B07', name: 'Genesis Engine', signal: 'flux', type: 'bot', rarity: 'epic',
    cost: 6, power: 4, defense: 6, bodyType: 'retro',
    ability: 'Surge. +1 max Charge this game. At start of your turn, restore 2 Defense to all allied Bots. Overclock: When Defense drops to 3 or below, summon a 3/3 Sprout Token.',
    flavor: '"From its core, new life. Always."',
    keywords: ['Surge', 'Overclock'],
    imagePrompt: 'Massive retro-style green robot with a boxy 1950s sci-fi aesthetic covered in blooming circuitry and growing vines, a genesis reactor in its chest birthing small robot seedlings, dials and gauges showing life-force levels, ancient garden-laboratory with towering organic tech pillars, green and warm amber with golden genesis light, epic scale, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_B08', name: 'Sage — Data Oracle', signal: 'flux', type: 'bot', rarity: 'legendary',
    cost: 7, power: 4, defense: 8, bodyType: 'retro',
    ability: 'Recycle. When played, draw 3 cards. Confident: When Sage destroys an enemy, give target allied Bot +3/+3 permanently. Overclock: When Defense drops to 3 or below, return all cards from Scrap Heap to your deck and shuffle.',
    flavor: '"I have catalogued every frequency. Every signal. Every possibility."',
    keywords: ['Recycle', 'Confident', 'Overclock'],
    imagePrompt: 'Sage, the iconic green retro oracle robot with boxy frame covered in ancient data glyphs, dish antenna receiving cosmic signals, multi-leg platform providing stability, surrounded by floating holographic books and scrolling archives of every battle ever fought, standing in the Great Archive — a cathedral of living data with tree-shaped server towers, green and golden wisdom-light with deep emerald accents, epic scale, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // MODS (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_FX_M01', name: 'Bark Plating', signal: 'flux', type: 'mod', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Equip to Bot: +3 Defense.',
    flavor: '"Grows thicker with every blow."',
    keywords: [],
    imagePrompt: 'Layered bark-like armor plating with green energy coursing through its grain, organic yet technological, growing over a robot surface, green and dark brown with bioluminescent veins, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_M02', name: 'Symbiotic Tendril', signal: 'flux', type: 'mod', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Power. Equipped Bot gains Restore (heal 1 adjacent ally at EOT).',
    flavor: '"It feeds. It heals. It spreads."',
    keywords: ['Restore'],
    imagePrompt: 'Green tendril attachment wrapping around a robot arm, pulsing with healing energy, the tendril reaching toward a nearby damaged ally, symbiotic and organic, green and teal glow, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_M03', name: 'Growth Catalyst', signal: 'flux', type: 'mod', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Power, +2 Defense. At start of your turn, equipped Bot gains +1 Defense.',
    flavor: '"Exponential returns on patience."',
    keywords: [],
    imagePrompt: 'Crystalline green catalyst module embedded in a robot chest, pulsing with growth energy that visibly increases with each heartbeat, small vines sprouting from connection points and getting larger, green and crystal-clear with golden growth particles, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_M04', name: 'Regeneration Core', signal: 'flux', type: 'mod', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Equip to Bot: +2 Defense. At end of turn, restore 1 Defense to equipped Bot.',
    flavor: '"It rebuilds itself. Endlessly."',
    keywords: [],
    imagePrompt: 'Organic green reactor core that pulses with regenerative energy, visible self-repair nanobots rebuilding micro-damage in real-time, the core surrounded by a web of self-healing circuitry, green and warm amber regeneration glow, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_M05', name: 'Evolutionary Matrix', signal: 'flux', type: 'mod', rarity: 'rare',
    cost: 3, power: 0, defense: 0,
    ability: 'Equip to Bot: +2 Power, +2 Defense. Each time equipped Bot survives combat, gain +1/+1 permanently.',
    flavor: '"What doesn\'t kill it makes it the apex predator."',
    keywords: [],
    imagePrompt: 'Complex matrix of interconnected green DNA-like helices wrapping around a robot, each strand encoding new adaptations, the robot visibly evolving — new armor plates growing, weapons sharpening, becoming more formidable with each layer, green and prismatic evolution energy, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // PROTOCOLS (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_FX_P01', name: 'Photosynthesis', signal: 'flux', type: 'protocol', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Restore 3 Defense to target Bot. Draw 1 card.',
    flavor: '"Light in. Life out."',
    keywords: [],
    imagePrompt: 'Green light rays being absorbed by a robot, converting to healing energy that repairs damage, leaves of light unfolding around the target, peaceful and restorative, green and golden sunlight, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_P02', name: 'Overgrowth', signal: 'flux', type: 'protocol', rarity: 'common',
    cost: 2, power: 0, defense: 0,
    ability: 'Give target Bot +2 Defense permanently. If it\'s a FLUX Bot, give +3 Defense instead.',
    flavor: '"It just... keeps growing."',
    keywords: [],
    imagePrompt: 'Explosive green growth erupting from a robot — vines, leaves, and circuit-bark expanding rapidly, the robot becoming larger and more armored as organic tech engulfs it, overgrown battlefield, green and dark emerald with bursting growth energy, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_P03', name: 'Natural Selection', signal: 'flux', type: 'protocol', rarity: 'uncommon',
    cost: 3, power: 0, defense: 0,
    ability: 'Destroy target Bot with the lowest Defense on the field (either side).',
    flavor: '"Only the strong survive. That\'s not cruelty. That\'s data."',
    keywords: [],
    imagePrompt: 'Green energy vines wrapping around and crushing the weakest robot on the field, natural selection in action, the strong standing tall while the weak are consumed and recycled, harsh but natural, green with predatory dark accents, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_P04', name: 'Spore Burst', signal: 'flux', type: 'protocol', rarity: 'uncommon',
    cost: 3, power: 0, defense: 0,
    ability: 'Give all allied Bots +1 Power and +2 Defense.',
    flavor: '"Breathe it in. Feel the upgrade."',
    keywords: [],
    imagePrompt: 'Cloud of green bioluminescent spores erupting from a central pod, spreading across all allied robots, each spore landing and being absorbed — visibly strengthening armor and weapons, green and teal spore cloud with golden absorption glow, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_P05', name: 'Full Bloom', signal: 'flux', type: 'protocol', rarity: 'rare',
    cost: 5, power: 0, defense: 0,
    ability: 'Restore all allied Bots to full Defense. Draw 2 cards.',
    flavor: '"And on the seventh cycle, everything bloomed."',
    keywords: [],
    imagePrompt: 'Spectacular bloom of green energy flowers erupting across the entire allied side of the battlefield, every robot being fully restored by waves of healing light, petals of pure data drifting upward, magical and triumphant moment, vibrant green and gold with white bloom-light, epic scale, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // UPGRADES (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_FX_U01', name: 'Nutrient Infusion', signal: 'flux', type: 'upgrade', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Give target Bot +1 Power and +1 Defense permanently.',
    flavor: '"Feed the machine. Watch it thrive."',
    keywords: [],
    imagePrompt: 'Green nutrient fluid being injected into a robot through vine-like tubes, the robot visibly growing stronger, subtle permanent glow increase, nurturing and steady, green and warm amber, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_U02', name: 'Root Network', signal: 'flux', type: 'upgrade', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Restore 2 Defense to each of up to 2 target Bots.',
    flavor: '"Connected. Sustained. Unbroken."',
    keywords: [],
    imagePrompt: 'Underground network of green glowing roots connecting multiple robots, healing energy flowing between them through the root system, shared sustenance, green and earthy brown with bioluminescent root veins, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_U03', name: 'Accelerated Growth', signal: 'flux', type: 'upgrade', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Give target Bot +2 Defense permanently. If it already has 5+ Defense, give +3 instead.',
    flavor: '"The strong grow strongest."',
    keywords: [],
    imagePrompt: 'Time-lapse effect of a robot rapidly growing additional armor layers, each layer larger than the last, accelerated evolution visualization, green and chrome with time-distortion effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_U04', name: 'Seed of Renewal', signal: 'flux', type: 'upgrade', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Return target Bot card from your Scrap Heap to your hand.',
    flavor: '"Nothing truly dies in the Flux. It just... starts over."',
    keywords: [],
    imagePrompt: 'Glowing green seed pod containing the compressed data of a destroyed robot, cracking open to release the blueprint for resurrection, Scrap Heap background with the seed rising from debris, green and golden rebirth light, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_U05', name: 'Apex Evolution', signal: 'flux', type: 'upgrade', rarity: 'rare',
    cost: 4, power: 0, defense: 0,
    ability: 'Give target Bot +3 Power and +3 Defense permanently. It gains all Emotion keywords it doesn\'t already have.',
    flavor: '"The final form. The perfect machine."',
    keywords: [],
    imagePrompt: 'Robot undergoing ultimate evolution — body transforming into a perfected apex form, every system optimized, new abilities manifesting as orbiting energy icons, transcendence moment, green and prismatic evolution-rainbow with golden apex crown, epic scale, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // CORES (2) — 1 Common, 1 Uncommon
  // ============================================================
  {
    id: 'SG_FX_C01', name: 'Flux Garden', signal: 'flux', type: 'core', rarity: 'common',
    cost: 2, power: 0, defense: 0,
    ability: 'All your FLUX Bots gain +1 Defense.',
    flavor: '"In the garden, all things heal."',
    keywords: [],
    imagePrompt: 'Serene digital garden with circuit-trees bearing fruit of green energy, small robot creatures tending the plants, healing atmosphere, peaceful yet powerful, green and soft gold with dappled light, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_FX_C02', name: 'The Living Network', signal: 'flux', type: 'core', rarity: 'uncommon',
    cost: 3, power: 0, defense: 0,
    ability: 'At end of your turn, restore 1 Defense to your most damaged Bot.',
    flavor: '"The network adapts. The network persists. The network is alive."',
    keywords: [],
    imagePrompt: 'Vast living network of interconnected green nodes spanning the entire battlefield, data flowing like sap through organic circuit-veins, the network itself appearing sentient and aware, pulsing with life, green and bioluminescent teal with neural-pattern connections, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
];
