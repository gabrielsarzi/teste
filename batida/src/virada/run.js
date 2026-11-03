// Estado de uma "Virada": botecos, mesas, saco de pedras, parceiros, dinheiro e loja.
import { Board, isWild } from '../core/board.js';
import { fullSet, makeTile, makeRng, isDouble, hasNum, pipSum } from '../core/tiles.js';
import {
  JOGOS, PARCEIROS, PARCEIRO_BY_ID, BEBIDAS, SIMPATIAS, CONSUMIVEL_BY_ID, DONOS, DONO_FINAL,
  ANTE_BASE, MESAS, BOTECOS, detectJogo, jogoValues, sharedNumber,
} from './data.js';

export const MAX_PARCEIROS = 5;
export const MAX_CONSUMIVEIS = 2;
export const MAX_PER_PLAY = 5;

export function newRun(seed) {
  const rng = makeRng(seed);
  const donos = rng.shuffle([...DONOS]).slice(0, 7);
  donos.push(DONO_FINAL);
  return {
    v: 1,
    seed: rng.seed,
    rngState: 0,
    ante: 1,
    mesaIdx: 0,
    money: 4,
    bag: fullSet(),
    parceiros: [],
    consumiveis: [],
    levels: Object.fromEntries(JOGOS.map((j) => [j.id, 1])),
    played: Object.fromEntries(JOGOS.map((j) => [j.id, 0])),
    donos: donos.map((d) => d.id),
    baseHands: 4,
    baseDiscards: 3,
    baseHandSize: 7,
    stats: { best: 0, mesas: 0 },
    phase: 'map', // map | mesa | shop | over | won
  };
}

export function runRng(run) {
  // RNG derivado do progresso para ser estável entre recarregamentos.
  run.rngState = (run.rngState || 0) + 1;
  return makeRng((run.seed ^ (run.rngState * 2654435761)) >>> 0);
}

export function donoOf(run, ante = run.ante) {
  const id = run.donos[ante - 1];
  return id === 'dono' ? DONO_FINAL : DONOS.find((d) => d.id === id);
}

export function mesaTarget(run, ante = run.ante, idx = run.mesaIdx) {
  const t = ANTE_BASE[ante - 1] * MESAS[idx].mult * (ante === 8 && idx === 2 ? 1.25 : 1);
  return Math.round(t / 10) * 10;
}

export const botecoName = (run) => BOTECOS[run.ante - 1];

export function activeBoss(run) {
  return run.mesaIdx === 2 ? donoOf(run) : null;
}
const bossIs = (mesa, ...ids) => {
  if (!mesa.boss) return false;
  if (mesa.boss.id === 'dono') return ids.some((i) => i === 'pressa' || i === 'fiscal');
  return ids.includes(mesa.boss.id);
};

// ---------- Mesa ----------
export function startMesa(run) {
  const rng = runRng(run);
  const boss = activeBoss(run);
  let hands = run.baseHands;
  let discards = run.baseDiscards;
  let handSize = run.baseHandSize;
  for (const p of run.parceiros) {
    const def = PARCEIRO_BY_ID[p.id];
    hands += def.hands || 0;
    discards += def.discards || 0;
    handSize += def.handSize || 0;
  }
  const mesa = {
    target: mesaTarget(run),
    score: 0,
    handsLeft: hands,
    discardsLeft: discards,
    handSize,
    maxPerPlay: MAX_PER_PLAY,
    boss,
    pile: rng.shuffle(run.bag.map((t) => t)),
    hand: [],
    board: new Board(),
    pending: [],
    jogadas: 0,
  };
  if (boss) {
    if (bossIs(mesa, 'pressa')) mesa.handsLeft = Math.min(mesa.handsLeft, 3);
    if (bossIs(mesa, 'mesquinho')) mesa.discardsLeft = Math.min(mesa.discardsLeft, 1);
    if (bossIs(mesa, 'maocurta')) mesa.handSize -= 2;
    if (bossIs(mesa, 'pontaseca')) mesa.maxPerPlay = 3;
  }
  draw(mesa);
  run.phase = 'mesa';
  run.mesa = mesa;
  return mesa;
}

export function draw(mesa) {
  const drawn = [];
  while (mesa.hand.length < mesa.handSize && mesa.pile.length) {
    const t = mesa.pile.pop();
    mesa.hand.push(t);
    drawn.push(t);
  }
  return drawn;
}

export function playableSides(mesa, tile) {
  if (mesa.pending.length >= mesa.maxPerPlay) return [];
  return mesa.board.sidesFor(tile);
}

export function anyPlayable(mesa) {
  return mesa.hand.some((t) => playableSides(mesa, t).length);
}

export function placePending(mesa, tile, side) {
  const rec = mesa.board.place(tile, side);
  mesa.hand = mesa.hand.filter((t) => t !== tile);
  mesa.pending.push({ tile, rec });
  return rec;
}

export function undoPending(mesa) {
  const last = mesa.pending.pop();
  if (!last) return null;
  mesa.board.undo();
  mesa.hand.push(last.tile);
  return last;
}

export function discard(mesa, tiles) {
  mesa.hand = mesa.hand.filter((t) => !tiles.includes(t));
  mesa.discardsLeft--;
  return draw(mesa);
}

// "Passar": sem jogada e sem troca — gasta uma jogada e troca a mão toda.
export function passHand(mesa) {
  const old = mesa.hand;
  mesa.hand = [];
  mesa.handsLeft--;
  mesa.pile.unshift(...old);
  return draw(mesa);
}

// ---------- Pontuação ----------
// Monta a sequência de passos para animar e o total final.
export function scorePlay(run, mesa, rng, { preview = false } = {}) {
  const played = mesa.pending.map((p) => p.tile);
  const jogoId = detectJogo(played);
  if (!jogoId) return null;
  const level = run.levels[jogoId];
  let [chips, mult] = jogoValues(jogoId, level);
  if (bossIs(mesa, 'ressaca')) mult = 1;
  const steps = [];
  const ctx = {
    played,
    boardCount: mesa.board.placed.length,
    discardsLeft: mesa.discardsLeft,
    handsLeft: mesa.handsLeft,
    rng: preview ? () => 1 : rng,
  };
  let money = 0;
  const broken = [];

  const apply = (eff, src) => {
    if (!eff) return;
    if (eff.chips) chips += eff.chips;
    if (eff.mult) mult += eff.mult;
    if (eff.xmult) mult *= eff.xmult;
    if (eff.money) money += eff.money;
    steps.push({ ...eff, src, chipsNow: chips, multNow: mult });
  };

  played.forEach((t, i) => {
    const debuff =
      (bossIs(mesa, 'fiscal') && isDouble(t)) || (bossIs(mesa, 'apagao') && hasNum(t, 0));
    if (debuff) {
      steps.push({ src: { kind: 'tile', i }, msg: 'Não vale!', debuff: true, chipsNow: chips, multNow: mult });
      return;
    }
    apply({ chips: pipSum(t) + (t.bonus || 0) }, { kind: 'tile', i });
    if (t.mod === 'marfim') apply({ chips: 30 }, { kind: 'tile', i });
    if (t.mod === 'brasa') apply({ mult: 4 }, { kind: 'tile', i });
    if (t.mod === 'vidro') apply({ xmult: 2 }, { kind: 'tile', i });
    if (t.mod === 'ouro') apply({ money: 3 }, { kind: 'tile', i });
    run.parceiros.forEach((p, pi) => {
      const def = PARCEIRO_BY_ID[p.id];
      if (def.onTile && !preview) apply(def.onTile(ctx, t, p), { kind: 'parceiro', i: pi, tile: i });
      else if (def.onTile && preview && def.id !== 'pedreiro') apply(def.onTile(ctx, t, p), { kind: 'parceiro', i: pi, tile: i });
    });
    if (t.mod === 'vidro' && !preview && rng() < 0.25) broken.push(t);
  });

  // Lá e Lô: as duas pontas ficam iguais depois da jogada
  const ends = mesa.board.ends;
  const laelo = mesa.board.placed.length > 1 && ends && ends.L === ends.R;
  if (laelo) {
    const x = run.parceiros.some((p) => PARCEIRO_BY_ID[p.id].passive === 'laelo3') ? 3 : 1.5;
    apply({ xmult: x, tag: 'Lá e Lô!' }, { kind: 'laelo' });
  }

  run.parceiros.forEach((p, pi) => {
    const def = PARCEIRO_BY_ID[p.id];
    if (!def.onPlay) return;
    if (preview && (def.id === 'pequente' || def.id === 'bebum')) {
      if (def.id === 'bebum') apply({ mult: p.state.left }, { kind: 'parceiro', i: pi });
      return;
    }
    if (preview) {
      apply(def.onPlay(ctx, { ...p, state: { ...p.state } }), { kind: 'parceiro', i: pi });
      return;
    }
    apply(def.onPlay(ctx, p), { kind: 'parceiro', i: pi });
  });

  const total = Math.floor(chips * mult);
  return { jogoId, level, played, steps, chips, mult, total, money, broken, laelo, naipe: sharedNumber(played) };
}

// Confirma a jogada: soma placar, aplica dinheiro, quebra vidros, repõe a mão.
export function commitPlay(run, mesa, result) {
  mesa.score += result.total;
  mesa.handsLeft--;
  mesa.jogadas++;
  run.money += result.money;
  if (bossIs(mesa, 'paoduro')) run.money = Math.max(0, run.money - 1);
  run.played[result.jogoId]++;
  run.stats.best = Math.max(run.stats.best, result.total);
  if (result.broken.length) {
    run.bag = run.bag.filter((t) => !result.broken.includes(t));
  }
  // parceiros que acabam (Bebum)
  run.parceiros = run.parceiros.filter((p) => {
    const def = PARCEIRO_BY_ID[p.id];
    return !(def.expired && def.expired(p));
  });
  mesa.pending = [];
  const drawn = draw(mesa);
  const won = mesa.score >= mesa.target;
  const lost = !won && (mesa.handsLeft <= 0 || (mesa.hand.length === 0 && mesa.pile.length === 0));
  return { drawn, won, lost };
}

export function cashOut(run) {
  const mesa = run.mesa;
  const lines = [];
  lines.push({ label: MESAS[run.mesaIdx].name, value: MESAS[run.mesaIdx].reward });
  if (mesa.handsLeft > 0) lines.push({ label: `${mesa.handsLeft} jogada${mesa.handsLeft > 1 ? 's' : ''} sobrando`, value: mesa.handsLeft });
  const interest = Math.min(5, Math.floor(run.money / 5));
  if (interest > 0) lines.push({ label: 'Juros ($1 a cada $5)', value: interest });
  for (const p of run.parceiros) {
    const def = PARCEIRO_BY_ID[p.id];
    if (def.onMesaEnd) lines.push({ label: def.name, value: def.onMesaEnd(run) });
  }
  const total = lines.reduce((s, l) => s + l.value, 0);
  return { lines, total };
}

export function advance(run, cash) {
  run.money += cash.total;
  run.stats.mesas++;
  run.mesa = null;
  if (run.mesaIdx === 2) {
    if (run.ante === 8) {
      run.phase = 'won';
      return;
    }
    run.ante++;
    run.mesaIdx = 0;
  } else {
    run.mesaIdx++;
  }
  run.phase = 'shop';
  run.shop = makeShop(run);
}

// ---------- Loja (Balcão) ----------
export function makeShop(run, rerolls = 0) {
  const rng = runRng(run);
  const owned = new Set(run.parceiros.map((p) => p.id));
  const pool = PARCEIROS.filter((p) => !owned.has(p.id));
  const weighted = [];
  for (const p of pool) {
    const w = p.rarity === 'comum' ? 6 : p.rarity === 'raro' ? 3 : 1;
    for (let i = 0; i < w; i++) weighted.push(p);
  }
  const parceiros = [];
  while (parceiros.length < 2 && weighted.length) {
    const p = rng.pick(weighted);
    if (!parceiros.includes(p)) parceiros.push(p);
    if (parceiros.length >= pool.length) break;
  }
  const consum = [];
  for (let i = 0; i < 2; i++) {
    const c = rng() < 0.5 ? rng.pick(BEBIDAS) : rng.pick(SIMPATIAS);
    consum.push(c);
  }
  return {
    items: [
      ...parceiros.map((p) => ({ type: 'parceiro', id: p.id, cost: p.cost, sold: false })),
      ...consum.map((c) => ({ type: 'consumivel', id: c.id, cost: c.cost, sold: false })),
      { type: 'caixinha', id: 'caixinha', cost: 4, sold: false },
    ],
    rerollCost: 3 + rerolls,
    rerolls,
  };
}

export function rerollShop(run) {
  const s = run.shop;
  if (run.money < s.rerollCost) return false;
  run.money -= s.rerollCost;
  const caix = s.items.find((i) => i.type === 'caixinha');
  run.shop = makeShop(run, s.rerolls + 1);
  if (caix && caix.sold) run.shop.items.find((i) => i.type === 'caixinha').sold = true;
  return true;
}

export function newParceiro(id) {
  const def = PARCEIRO_BY_ID[id];
  return { id, state: def.init ? def.init() : {} };
}

export function sellValue(p) {
  return Math.max(1, Math.floor(PARCEIRO_BY_ID[p.id].cost / 2));
}

// Caixinha: 3 pedras especiais para escolher uma
export function caixinhaOptions(run) {
  const rng = runRng(run);
  const mods = ['ouro', 'vidro', 'brasa', 'coringa', 'marfim'];
  const out = [];
  for (let i = 0; i < 3; i++) {
    const a = rng.int(7);
    const b = rng.int(7);
    out.push(makeTile(a, b, { mod: rng.pick(mods) }));
  }
  return out;
}

// ---------- Consumíveis ----------
export function useConsumivel(run, idx, picked = []) {
  const c = CONSUMIVEL_BY_ID[run.consumiveis[idx]];
  if (!c) return null;
  let msg = '';
  if (c.kind === 'bebida') {
    run.levels[c.jogo]++;
    msg = `${JOGOS.find((j) => j.id === c.jogo).name} subiu para o nível ${run.levels[c.jogo]}`;
  } else if (c.mod) {
    for (const t of picked) t.mod = c.mod;
    msg = picked.length ? `${picked.length} pedra${picked.length > 1 ? 's' : ''} benzida${picked.length > 1 ? 's' : ''}` : '';
  } else if (c.action === 'destroy') {
    run.bag = run.bag.filter((t) => !picked.includes(t));
    if (run.mesa) {
      run.mesa.hand = run.mesa.hand.filter((t) => !picked.includes(t));
      run.mesa.pile = run.mesa.pile.filter((t) => !picked.includes(t));
    }
    msg = 'Sal grosso jogado';
  } else if (c.action === 'mirror') {
    for (const t of picked) {
      const m = Math.max(t.a, t.b);
      t.a = m;
      t.b = m;
    }
    msg = 'Virou bucha';
  } else if (c.action === 'money') {
    const gain = Math.min(20, run.money);
    run.money += gain;
    msg = `+$${gain}`;
  }
  run.consumiveis.splice(idx, 1);
  return { c, msg };
}

export { isWild };
