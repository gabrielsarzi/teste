// IA de dominó de boteco: despeja pedra pesada, segura variedade,
// trava o adversário da vez, ajuda o parceiro e fecha o jogo quando a conta é boa.
import { fullSet, isDouble, pipSum } from '../core/tiles.js';

// skill: 0 (iniciante) a 1 (mestre)
export function chooseMove(round, p, skill = 0.7) {
  const moves = round.legalMoves(p);
  if (moves.length <= 1) return moves[0] || null;

  const hand = round.hands[p];
  const seen = new Set(round.board.placed.map((r) => key(r.tile)));
  for (const t of hand) seen.add(key(t));
  const unseen = fullSet().filter((t) => !seen.has(key(t)));
  const avgUnseen = unseen.length ? unseen.reduce((s, t) => s + pipSum(t), 0) / unseen.length : 0;

  const n = round.n || 4;
  const next = (p + 1) % n;
  const partner = n === 4 ? (p + 2) % 4 : -1;
  const prevOpp = (p + n - 1) % n;

  let best = null;
  let bestScore = -Infinity;
  for (const m of moves) {
    let s = 0;
    const rest = hand.filter((t) => t !== m.tile);
    s += pipSum(m.tile) * 1.6;
    if (isDouble(m.tile)) s += 5;

    if (!round.board.empty) {
      const ends = { ...round.board.ends };
      ends[m.side] = round.board.resultEnd(m.tile, m.side);
      const e = [ends.L, ends.R];

      // continuo tendo jogo depois?
      const myFollow = rest.filter((t) => e.includes(t.a) || e.includes(t.b)).length;
      s += Math.min(myFollow, 3) * 2.5 * (0.4 + skill);

      // números que eu domino (tenho muitas pedras daquele número)
      for (const v of new Set(e)) {
        const mine = rest.filter((t) => t.a === v || t.b === v).length;
        s += mine >= 3 ? 3 : 0;
      }

      // trava o próximo adversário / não trava o parceiro
      const lackNext = e.filter((v) => round.lacks[next].has(v)).length;
      const lackPrev = e.filter((v) => round.lacks[prevOpp].has(v)).length;
      const lackPartner = partner >= 0 ? e.filter((v) => round.lacks[partner].has(v)).length : 0;
      s += (lackNext * 6 + lackPrev * 2 - lackPartner * 5) * skill;

      // fechar o jogo de propósito?
      if (skill > 0.35 && round.wouldClose(m.tile, m.side)) {
        const diff = closeAdvantage(round, p, rest, avgUnseen);
        s += diff > 3 ? 400 + diff : -400;
      }
    } else {
      // saída: começa pelo número que mais tem
      const counts = countNums(hand);
      s += (counts[m.tile.a] + counts[m.tile.b]) * 2;
    }

    if (rest.length === 0) s += 10000;
    s += Math.random() * (0.8 + (1 - skill) * 22); // iniciante erra mais
    if (s > bestScore) {
      bestScore = s;
      best = m;
    }
  }
  return best;
}

// Quanto a dupla de p ganha na contagem se o jogo fechar agora (positivo = bom).
export function closeAdvantage(round, p, myHand, avgUnseen) {
  const n = round.n || 4;
  const team = (q) => (n === 4 ? q % 2 : q);
  const sums = {};
  for (let q = 0; q < n; q++) {
    const v = q === p ? myHand.reduce((a, t) => a + pipSum(t), 0) : round.hands[q].length * avgUnseen;
    sums[team(q)] = (sums[team(q)] || 0) + v;
  }
  const mine = sums[team(p)];
  let bestOther = Infinity;
  for (const [t, v] of Object.entries(sums)) if (+t !== team(p)) bestOther = Math.min(bestOther, v);
  return bestOther - mine;
}

// Estimativa de p sobre a média das pedras que ele não vê.
export function unseenAvg(round, p) {
  const seen = new Set(round.board.placed.map((r) => key(r.tile)));
  for (const t of round.hands[p]) seen.add(key(t));
  const unseen = fullSet().filter((t) => !seen.has(key(t)));
  return unseen.length ? unseen.reduce((s, t) => s + pipSum(t), 0) / unseen.length : 0;
}

// Voto de p sobre aceitar um fechamento forçado: true = fecha e conta.
// Cada um olha a própria conta; os mais experientes erram menos.
export function voteClose(round, p, skill = 0.6) {
  const adv = closeAdvantage(round, p, round.hands[p], unseenAvg(round, p));
  const noise = (Math.random() - 0.5) * (1 - skill) * 30;
  return adv + noise > 0;
}

function key(t) {
  return t.a * 10 + t.b;
}

function countNums(hand) {
  const c = [0, 0, 0, 0, 0, 0, 0];
  for (const t of hand) {
    c[t.a]++;
    if (t.b !== t.a) c[t.b]++;
  }
  return c;
}

// ---------- Mestre: simulação de Monte Carlo ----------
// Sorteia mãos possíveis para os outros (respeitando quem já passou em cada número),
// joga o resto da rodada várias vezes e escolhe a jogada com melhor resultado médio.
import { Board } from '../core/board.js';
import { ClassicRound } from './engine.js';

export function chooseMoveMaster(round, p, samples = 28) {
  if ((round.n || 4) !== 4 || (round.pile && round.pile.length)) return chooseMove(round, p, 0.95);
  const moves = round.legalMoves(p);
  if (moves.length <= 1) return moves[0] || null;
  if (round.hands[p].length === 1) return moves[0];
  const hand = round.hands[p];
  const seen = new Set(round.board.placed.map((r) => key(r.tile)));
  for (const t of hand) seen.add(key(t));
  const unseen = fullSet().filter((t) => !seen.has(key(t)));
  const others = [1, 2, 3].map((d) => (p + d) % 4);

  const totals = moves.map(() => 0);
  for (let s = 0; s < samples; s++) {
    const deal = sampleHands(round, others, unseen);
    moves.forEach((m, i) => {
      const sim = cloneRound(round, p, deal);
      const tile = sim.hands[p].find((t) => t.a === m.tile.a && t.b === m.tile.b);
      sim.play(p, tile, m.side);
      totals[i] += playout(sim, p % 2);
    });
  }
  let best = 0;
  for (let i = 1; i < moves.length; i++) if (totals[i] > totals[best]) best = i;
  return moves[best];
}

function sampleHands(round, others, unseen) {
  for (let attempt = 0; attempt < 40; attempt++) {
    const pool = shuffle([...unseen]);
    const out = {};
    let ok = true;
    // quem tem mais restrição escolhe primeiro
    const order = [...others].sort((a, b) => round.lacks[b].size - round.lacks[a].size);
    for (const q of order) {
      const need = round.hands[q].length;
      const lacks = round.lacks[q];
      const pick = [];
      for (let i = 0; i < pool.length && pick.length < need; i++) {
        const t = pool[i];
        if (attempt < 30 && (lacks.has(t.a) || lacks.has(t.b))) continue;
        pick.push(t);
      }
      if (pick.length < need) {
        ok = false;
        break;
      }
      for (const t of pick) pool.splice(pool.indexOf(t), 1);
      out[q] = pick;
    }
    if (ok) return out;
  }
  // sem solução consistente: distribui sem restrição
  const pool = shuffle([...unseen]);
  const out = {};
  for (const q of others) out[q] = pool.splice(0, round.hands[q].length);
  return out;
}

function cloneRound(round, p, deal) {
  const hands = [0, 1, 2, 3].map((q) => (q === p ? round.hands[p].map((t) => ({ ...t })) : deal[q].map((t) => ({ ...t }))));
  const r = new ClassicRound(hands, [], p, null, round.match);
  const b = new Board();
  b.placed = round.board.placed.slice();
  b.arms = round.board.arms ? JSON.parse(JSON.stringify(round.board.arms)) : null;
  r.board = b;
  r.turn = p;
  r.lacks = round.lacks.map((s) => new Set(s));
  return r;
}

function playout(r, team) {
  let g = 0;
  while (!r.result && g++ < 120) {
    const q = r.turn;
    const mv = chooseMove(r, q, 0.75);
    if (mv) r.play(q, mv.tile, mv.side);
    else r.pass(q);
  }
  const res = r.result;
  if (!res || res.team == null) return 0;
  // ganhar vale os pontos; e um pouco pela margem na contagem
  return res.team === team ? res.points : -res.points;
}

function shuffle(a) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
