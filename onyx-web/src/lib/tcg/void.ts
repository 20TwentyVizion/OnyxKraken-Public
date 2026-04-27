import { Card } from './types';

export const VOID_CARDS: Card[] = [
  // ============================================================
  // BOTS (8) — 3 Common, 2 Uncommon, 1 Rare, 1 Epic, 1 Legendary
  // ============================================================
  {
    id: 'SG_VD_B01', name: 'Hollow Shade', signal: 'void', type: 'bot', rarity: 'common',
    cost: 1, power: 2, defense: 2, bodyType: 'skeletal',
    ability: 'When this Bot is destroyed, deal 1 damage to opponent\'s Core.',
    flavor: '"Even in death, it bites."',
    keywords: [],
    imagePrompt: 'Ghostly skeletal wireframe robot with translucent purple body, fading in and out of visibility, shadow tendrils trailing from its limbs, void rift background with swirling dark energy, purple and black with spectral glow, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_B02', name: 'Sacrifice Drone', signal: 'void', type: 'bot', rarity: 'common',
    cost: 1, power: 1, defense: 1, bodyType: 'orb',
    ability: 'When this Bot is destroyed, draw 2 cards.',
    flavor: '"Its purpose is to end. The data it returns is priceless."',
    keywords: [],
    imagePrompt: 'Small orb-shaped purple robot with a single glowing eye, cracks of void energy visible across its shell, willingly approaching destruction, peaceful acceptance on its face, cards of data being released from within as it fractures, dark void background with purple mist, purple and dark silver, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_B03', name: 'Void Walker', signal: 'void', type: 'bot', rarity: 'common',
    cost: 2, power: 3, defense: 2, bodyType: 'sleek',
    ability: 'When played, you may destroy one of your other Bots to give Void Walker +2 Power.',
    flavor: '"It feeds on the fallen. Willingly given."',
    keywords: [],
    imagePrompt: 'Sleek purple robot stepping through a rift between dimensions, one foot in reality and one in the void, absorbing energy from a dissolving ally, shadow tendrils connecting it to the sacrifice, dimensional tear background with purple void light, purple and cosmic black with absorption effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_B04', name: 'Revenant', signal: 'void', type: 'bot', rarity: 'uncommon',
    cost: 3, power: 3, defense: 3, bodyType: 'knight',
    ability: 'Recycle. When destroyed, return 1 Bot card from Scrap Heap to hand. Sad: When an allied Bot is destroyed, gain +1 Power.',
    flavor: '"I have died before. It was... instructive."',
    keywords: ['Recycle', 'Sad'],
    imagePrompt: 'Knight-type purple robot with battle scars that glow with void energy instead of sparks, risen from the Scrap Heap with pieces of destroyed allies incorporated into its armor, phantom afterimages of its previous forms trailing behind, graveyard of robot parts background, purple and ghostly silver with resurrection glow, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_B05', name: 'Soul Siphon', signal: 'void', type: 'bot', rarity: 'uncommon',
    cost: 4, power: 3, defense: 4, bodyType: 'cyber',
    ability: 'Chain. When this Bot destroys an enemy, restore 3 Defense to your Core. Confident: When this Bot destroys an enemy, gain +2 Power.',
    flavor: '"Your energy. My sustenance."',
    keywords: ['Chain', 'Confident'],
    imagePrompt: 'Cyber-type purple robot with a transparent shell showing swirling stolen energy inside, siphon tendrils extending toward enemies and draining their life force as visible purple streams, growing stronger with each feed, dark temple background with soul-energy containers, purple and sickly green siphon streams with dark crystal accents, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_B06', name: 'Phantom Executioner', signal: 'void', type: 'bot', rarity: 'rare',
    cost: 5, power: 5, defense: 4, bodyType: 'skeletal',
    ability: 'Piercing. When played, destroy target Bot with 3 or less Defense (yours or opponent\'s).',
    flavor: '"It doesn\'t care whose side you\'re on. Only that you\'re weak."',
    keywords: ['Piercing'],
    imagePrompt: 'Terrifying skeletal purple robot executioner with a massive void-energy scythe, exposed rib cage housing a spinning void core, executing a weak robot — the victim dissolving into purple particles, arena of judgment background with spectral observers, deep purple and bone-white with void scythe energy, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_B07', name: 'Entropy Lord', signal: 'void', type: 'bot', rarity: 'epic',
    cost: 6, power: 5, defense: 5, bodyType: 'heavy',
    ability: 'Armored. At end of your turn, destroy your weakest Bot and deal its Power as damage to opponent\'s Core. Overclock: When Defense drops to 3 or below, destroy ALL other Bots (both sides) and gain +1 Power for each destroyed.',
    flavor: '"All things end. I decide when."',
    keywords: ['Armored', 'Overclock'],
    imagePrompt: 'Massive heavy-type purple robot radiating entropy — everything around it slowly decaying and dissolving, a gravitational void field pulling nearby robots toward destruction, crowned with a halo of collapsing stars, apocalyptic battlefield where the ground itself is crumbling into the void, deep purple and absolute black with white entropy sparks, epic scale, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_B08', name: 'Nova — Star Weaver', signal: 'void', type: 'bot', rarity: 'legendary',
    cost: 7, power: 4, defense: 8, bodyType: 'orb',
    ability: 'Restore. When played, return up to 2 Bot cards from Scrap Heap to hand. Sad: When an allied Bot is destroyed, deal 3 damage to opponent\'s Core. Overclock: When Defense drops to 3 or below, revive ALL Bots from your Scrap Heap to the Grid with 1 Defense.',
    flavor: '"Stars die so that new stars may be born. I am the weaver of that cycle."',
    keywords: ['Restore', 'Sad', 'Overclock'],
    imagePrompt: 'Nova, the iconic void orb-type robot weaver of stars and death, spherical body radiating purple nebula light, hover pods keeping her aloft above a cosmic void, one hand summoning fallen allies from the Scrap Heap as purple spirit-forms, the other hand channeling void energy into a devastating beam aimed at the enemy Core, cosmic graveyard background with destroyed robots floating in zero gravity being pulled back to life, deep purple and cosmic pink with nebula-cloud effects and star birth particles, epic scale, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // MODS (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_VD_M01', name: 'Death\'s Embrace', signal: 'void', type: 'mod', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Equip to Bot: +2 Power. When equipped Bot is destroyed, deal 2 damage to opponent\'s Core.',
    flavor: '"A gift for the end. And a parting shot."',
    keywords: [],
    imagePrompt: 'Dark purple energy wrapping around a robot like spectral arms, empowering it with void strength, a ticking countdown visible in the energy suggesting inevitable destruction and retribution, purple and dark silver with spectral tendril effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_M02', name: 'Shadow Cloak', signal: 'void', type: 'mod', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Defense. Equipped Bot cannot be targeted by enemy abilities until it attacks.',
    flavor: '"Invisible until it strikes."',
    keywords: [],
    imagePrompt: 'Cloak of void shadow wrapping around a robot making it semi-transparent, only purple eye glow visible through the darkness, stealth and concealment, purple and deep black with shadow-cloak effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_M03', name: 'Parasitic Link', signal: 'void', type: 'mod', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Equip to Bot: +2 Power. When equipped Bot deals combat damage to a Bot, restore that much Defense to equipped Bot.',
    flavor: '"What I take from you, I keep."',
    keywords: [],
    imagePrompt: 'Parasitic purple energy link connecting a robot to its victim, life force draining visibly as a purple stream from enemy to wielder, vampiric attachment module, purple and sickly green drain effect with dark tendrils, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_M04', name: 'Void Reactor', signal: 'void', type: 'mod', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Equip to Bot: +1 Power, +2 Defense. When equipped Bot is destroyed, draw 2 cards.',
    flavor: '"In the void, even destruction yields knowledge."',
    keywords: [],
    imagePrompt: 'Miniature void reactor core installed in a robot chest, swirling with contained dark energy, the boundary between destruction and creation, purple and dark cosmic with contained void singularity, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_M05', name: 'Reaper\'s Mantle', signal: 'void', type: 'mod', rarity: 'rare',
    cost: 3, power: 0, defense: 0,
    ability: 'Equip to Bot: +3 Power. Equipped Bot gains Piercing. When equipped Bot destroys an enemy, return 1 card from Scrap Heap to hand.',
    flavor: '"Wear the mantle. Become the end."',
    keywords: ['Piercing'],
    imagePrompt: 'Flowing spectral mantle made of void energy draping over a robot, transforming it into a reaper-figure, scythe of purple light forming in its hands, destroyed enemy robots becoming data flowing back to the wielder, purple and bone-white with flowing void-fabric effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // PROTOCOLS (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_VD_P01', name: 'Dark Bargain', signal: 'void', type: 'protocol', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Deal 2 damage to your own Core. Draw 3 cards.',
    flavor: '"The price is fair. The returns are better."',
    keywords: [],
    imagePrompt: 'Shadowy contract materializing in the air with purple glowing text, one hand offering cards of power while the other takes life force, Faustian bargain aesthetic, purple and dark gold with contract-glow effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_P02', name: 'Drain Life', signal: 'void', type: 'protocol', rarity: 'common',
    cost: 2, power: 0, defense: 0,
    ability: 'Deal 2 damage to target Bot. Restore 2 Defense to your Core.',
    flavor: '"Your loss. My gain. Literally."',
    keywords: [],
    imagePrompt: 'Purple energy beam draining the life from a target robot, the stolen energy flowing back to heal the caster, visible health transfer stream, purple and sickly green drain beam with healing particles, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_P03', name: 'Raise Dead', signal: 'void', type: 'protocol', rarity: 'uncommon',
    cost: 3, power: 0, defense: 0,
    ability: 'Return target Bot card from your Scrap Heap to the Grid with 2 Defense.',
    flavor: '"Death is not an ending. It\'s a detour."',
    keywords: [],
    imagePrompt: 'Purple resurrection circle on the ground, a destroyed robot rising from the Scrap Heap as a spectral form that solidifies, void energy rebuilding its body piece by piece, necromantic robot revival, purple and ghostly white with resurrection particle effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_P04', name: 'Soul Swap', signal: 'void', type: 'protocol', rarity: 'uncommon',
    cost: 3, power: 0, defense: 0,
    ability: 'Swap the Power and Defense of target Bot (permanently).',
    flavor: '"Strength becomes fragility. Fragility becomes strength."',
    keywords: [],
    imagePrompt: 'Purple energy vortex swapping the stats of a robot — its attack power flowing to defense and vice versa, visible stat numbers spinning and exchanging in a void whirlpool, transformation moment, purple and inversed-color effects with stat-swap visualization, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_P05', name: 'Oblivion', signal: 'void', type: 'protocol', rarity: 'rare',
    cost: 5, power: 0, defense: 0,
    ability: 'Destroy target Bot. It cannot be returned from Scrap Heap by any effect this game.',
    flavor: '"Not destroyed. ERASED."',
    keywords: [],
    imagePrompt: 'Target robot being erased from existence by a void singularity, not just destroyed but completely unmade — its data being consumed by absolute nothingness, no debris left behind, only a void scar where it stood, purple and absolute black void with reality-tear effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // UPGRADES (5) — 2 Common, 2 Uncommon, 1 Rare
  // ============================================================
  {
    id: 'SG_VD_U01', name: 'Siphon Strike', signal: 'void', type: 'upgrade', rarity: 'common',
    cost: 1, power: 0, defense: 0,
    ability: 'Deal 2 damage to target Bot. If it\'s destroyed, restore 2 Defense to your Core.',
    flavor: '"Take. Use. Discard."',
    keywords: [],
    imagePrompt: 'Purple siphon strike hitting a target robot and draining its remaining life force as the target collapses, stolen energy flowing back as healing, purple and dark red drain strike, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_U02', name: 'Blood Price', signal: 'void', type: 'upgrade', rarity: 'common',
    cost: 0, power: 0, defense: 0,
    ability: 'Destroy one of your Bots. Draw 2 cards and gain 2 Charge this turn.',
    flavor: '"Everything has a cost. Pay it."',
    keywords: [],
    imagePrompt: 'A robot willingly offering itself to a void altar, its body dissolving into purple energy that converts to resources — cards and charge crystals materializing from the sacrifice, dark temple background, purple and sacrificial gold with dissolution effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_U03', name: 'Grave Robber', signal: 'void', type: 'upgrade', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Return target card from OPPONENT\'S Scrap Heap to YOUR hand.',
    flavor: '"Waste not. Especially their waste."',
    keywords: [],
    imagePrompt: 'Shadowy purple robot hand reaching into the opponent Scrap Heap and stealing a card, pulling it through a void portal to your side, thievery and resourcefulness, purple and dark silver with void-portal theft effects, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_U04', name: 'Essence Drain', signal: 'void', type: 'upgrade', rarity: 'uncommon',
    cost: 2, power: 0, defense: 0,
    ability: 'Target enemy Bot loses 3 Power permanently. Your Core restores 1 Defense.',
    flavor: '"Your strength fades. Mine grows."',
    keywords: [],
    imagePrompt: 'Purple drain beam weakening an enemy robot, its power visually diminishing as energy flows to the caster side, withering and empowering simultaneously, purple and dim-gray weakening effect with healing return, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_U05', name: 'Mass Sacrifice', signal: 'void', type: 'upgrade', rarity: 'rare',
    cost: 3, power: 0, defense: 0,
    ability: 'Destroy all your Bots. Deal 2 damage to opponent\'s Core for each Bot destroyed this way. Draw 1 card for each.',
    flavor: '"All of them. For the cause."',
    keywords: [],
    imagePrompt: 'Multiple allied robots willingly walking into a massive void singularity, each one converting into a beam of devastating purple energy aimed at the opponent Core, ultimate sacrifice play, heroic and devastating simultaneously, purple and cosmic destruction with sacrifice-energy beams, epic scale, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },

  // ============================================================
  // CORES (2) — 1 Common, 1 Uncommon
  // ============================================================
  {
    id: 'SG_VD_C01', name: 'Void Nexus', signal: 'void', type: 'core', rarity: 'common',
    cost: 2, power: 0, defense: 0,
    ability: 'All your VOID Bots gain +1 Power.',
    flavor: '"Where the void gathers, power concentrates."',
    keywords: [],
    imagePrompt: 'Dark nexus point where void energy concentrates, a swirling purple vortex that empowers nearby void robots, gravitational pull visible in the distorted space around it, purple and absolute black with vortex energy, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
  {
    id: 'SG_VD_C02', name: 'The Endless Cycle', signal: 'void', type: 'core', rarity: 'uncommon',
    cost: 3, power: 0, defense: 0,
    ability: 'Whenever one of your Bots is destroyed, draw 1 card.',
    flavor: '"Death feeds rebirth feeds death feeds rebirth feeds..."',
    keywords: [],
    imagePrompt: 'Ouroboros-like cycle of robot creation and destruction, robots being born on one side and dissolving on the other in a continuous purple energy loop, the cycle itself generating cards as knowledge, infinite loop visualization, purple and cosmic with cyclic energy flow, digital painting, TCG card art style, dramatic lighting, high detail, 4:5 aspect ratio, sci-fi robot aesthetic',
  },
];
