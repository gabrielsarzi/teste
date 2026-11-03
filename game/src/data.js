// Balanceamento: torres, inimigos e talentos.
window.TOWERS = {
  gunner: { cost: 50, dmg: 7, rate: 2.6, range: 2.4, proj: 'bullet', light: 0xffc060,
    a: s => { s.rate *= 2.1; s.dmg *= 0.8; },
    b: s => { s.dmg *= 3; s.rate *= 0.5; s.range += 1.8; } },
  mortar: { cost: 90, dmg: 16, rate: 0.55, range: 3.2, splash: 0.9, proj: 'shell', light: 0xff9040,
    a: s => { s.burn = 0.35; },
    b: s => { s.splash *= 1.6; s.dmg *= 1.4; } },
  cryo: { cost: 70, dmg: 2, rate: 1.1, range: 2.1, slow: 0.4, slowT: 1.6, proj: 'shard', light: 0x70c8ff,
    a: s => { s.freeze = 0.18; },
    b: s => { s.pulse = true; s.rate *= 0.8; s.dmg *= 2; } },
  tesla: { cost: 120, dmg: 9, rate: 0.8, range: 2.2, chain: 3, proj: 'zap', light: 0xb890ff,
    a: s => { s.chain += 3; },
    b: s => { s.dmg *= 2.1; } }
};
window.TOWER_ORDER = ['gunner', 'mortar', 'cryo', 'tesla'];
window.MAX_LVL = 5;

window.ENEMIES = {
  walker: { hp: 18, spd: 1.0, gold: 1, core: 1, size: 0.95 },
  runner: { hp: 10, spd: 1.85, gold: 1, core: 1, size: 0.8 },
  boss:   { hp: 18 * 18, spd: 0.5, gold: 25, core: 5, size: 1.6 }
};

// Árvore de talentos: cada ramo é uma cadeia; "req" precisa estar no nível 1+.
window.TALENTS = [
  { id: 'dmg',      br: 'atk', max: 25, base: 2,  g: 1.45 },
  { id: 'rate',     br: 'atk', req: 'dmg',      max: 15, base: 5,  g: 1.5 },
  { id: 'range',    br: 'atk', req: 'rate',     max: 6,  base: 12, g: 1.8 },
  { id: 'crit',     br: 'atk', req: 'range',    max: 10, base: 20, g: 1.6 },
  { id: 'gold0',    br: 'eco', max: 20, base: 2,  g: 1.45 },
  { id: 'bounty',   br: 'eco', req: 'gold0',    max: 15, base: 4,  g: 1.5 },
  { id: 'interest', br: 'eco', req: 'bounty',   max: 5,  base: 15, g: 1.9 },
  { id: 'essence',  br: 'eco', req: 'interest', max: 10, base: 25, g: 1.7 },
  { id: 'hp',       br: 'tec', max: 10, base: 3,  g: 1.5 },
  { id: 'autowave', br: 'tec', req: 'hp',       max: 1,  base: 20, g: 1 },
  { id: 'speed4',   br: 'tec', req: 'autowave', max: 1,  base: 45, g: 1 },
  { id: 'rubble',   br: 'tec', req: 'hp',       max: 5,  base: 8,  g: 1.7 },
  { id: 'offhours', br: 'tec', req: 'rubble',   max: 6,  base: 15, g: 1.8 },
  { id: 'offrate',  br: 'tec', req: 'offhours', max: 10, base: 20, g: 1.6 }
];
window.talentCost = (t, lvl) => Math.ceil(t.base * Math.pow(t.g, lvl));

window.fmt = function (n) {
  n = Math.floor(n);
  if (n < 10000) return String(n);
  const u = ['K', 'M', 'B', 'T'];
  let i = -1;
  while (n >= 1000 && i < u.length - 1) { n /= 1000; i++; }
  return (n >= 100 ? n.toFixed(0) : n.toFixed(1)) + u[i];
};

// ---------- Mina ----------
// Cada andar: minério, multiplicador de valor e vida base dos zumbis do andar
window.FLOORS = [
  { ore: 'coal', v: 1 }, { ore: 'copper', v: 5 }, { ore: 'iron', v: 25 }, { ore: 'silver', v: 125 },
  { ore: 'gold', v: 625 }, { ore: 'crystal', v: 3125 }, { ore: 'ruby', v: 15625 }, { ore: 'uranium', v: 78125 }
];
window.MINE = {
  minerCost: (f, n) => Math.ceil(10 * Math.pow(5, f) * Math.pow(1.15, n)),
  minerRate: 1,                                   // ouro/s por mineiro (x valor do andar)
  floorCost: f => Math.ceil(400 * Math.pow(6, f - 1)), // custo para cavar o andar f (f >= 1)
  zombieHp: f => 10 * Math.pow(3.5, f),
  slots: [4, 5, 6, 7]                             // colunas das vagas de torre em cada andar
};
// Melhorias permanentes compradas com ouro
window.UPGRADES = [
  { id: 'pick',    base: 25,  g: 2.2, max: 50 },  // +1 ouro por toque (x valor do andar)
  { id: 'tools',   base: 150, g: 3,   max: 30 },  // mineiros +25%
  { id: 'silence', base: 300, g: 3.5, max: 8 },   // -8% de barulho
  { id: 'range',   base: 500, g: 4,   max: 6 },   // torres +6% de alcance
  { id: 'store',   base: 200, g: 4,   max: 10 }   // +1h de armazém offline (base 2h)
];
window.upgradeCost = (u, lvl) => Math.ceil(u.base * Math.pow(u.g, lvl));
