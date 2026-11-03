// IA de dominó de boteco: despeja pedra pesada, segura variedade,
// trava o adversário da vez, ajuda o parceiro e fecha o jogo quando a conta é boa.
import { fullSet, isDouble, pipSum } from '../core/tiles.js';

export function chooseMove(round, p) {
  const moves = round.legalMoves(p);
  if (moves.length <= 1) return moves[0] || null;

  const hand = round.hands[p];
  const seen = new Set(round.board.placed.map((r) => key(r.tile)));
  for (const t of hand) seen.add(key(t));
  const unseen = fullSet().filter((t) => !seen.has(key(t)));
  const avgUnseen = unseen.length ? unseen.reduce((s, t) => s + pipSum(t), 0) / unseen.length : 0;

  const next = (p + 1) % 4;
  const partner = (p + 2) % 4;
  const prevOpp = (p + 3) % 4;

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
      s += Math.min(myFollow, 3) * 2.5;

      // números que eu domino (tenho muitas pedras daquele número)
      for (const v of new Set(e)) {
        const mine = rest.filter((t) => t.a === v || t.b === v).length;
        s += mine >= 3 ? 3 : 0;
      }

      // trava o próximo adversário / não trava o parceiro
      const lackNext = e.filter((v) => round.lacks[next].has(v)).length;
      const lackPrev = e.filter((v) => round.lacks[prevOpp].has(v)).length;
      const lackPartner = e.filter((v) => round.lacks[partner].has(v)).length;
      s += lackNext * 6 + lackPrev * 2 - lackPartner * 5;

      // fechar o jogo de propósito?
      if (round.wouldClose(m.tile, m.side)) {
        const mySum = rest.reduce((a, t) => a + pipSum(t), 0);
        const partnerSum = round.hands[partner].length * avgUnseen;
        const oppSum = (round.hands[next].length + round.hands[prevOpp].length) * avgUnseen;
        const diff = oppSum - (mySum + partnerSum);
        s += diff > 3 ? 400 + diff : -400;
      }
    } else {
      // saída: começa pelo número que mais tem
      const counts = countNums(hand);
      s += (counts[m.tile.a] + counts[m.tile.b]) * 2;
    }

    if (rest.length === 0) s += 10000;
    s += Math.random() * 0.8; // um pouco de personalidade
    if (s > bestScore) {
      bestScore = s;
      best = m;
    }
  }
  return best;
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
