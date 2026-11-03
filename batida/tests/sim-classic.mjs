import { ClassicMatch } from '../src/classic/engine.js';
import { chooseMove } from '../src/classic/ai.js';
let stats = { batida: 0, fechado: 0, empate: 0, rounds: 0, matches: 0, wins: [0, 0], maxTiles: 0, bounds: 0 };
for (let i = 0; i < 2000; i++) {
  const m = new ClassicMatch({}, i + 1);
  while (!m.isOver()) {
    const r = m.newRound();
    let guard = 0;
    while (!r.result && guard++ < 200) {
      const p = r.turn;
      const mv = chooseMove(r, p);
      if (mv) r.play(p, mv.tile, mv.side); else r.pass(p);
    }
    if (!r.result) throw new Error('round never ended');
    // overlap check of layout
    const cells = new Set();
    for (const pl of r.board.placed) for (const h of [pl.near, pl.far]) {
      const k = h.x + ',' + h.y; if (cells.has(k)) throw new Error('overlap ' + k + ' seed ' + (i+1)); cells.add(k);
    }
    const b = r.board.bounds(); stats.bounds = Math.max(stats.bounds, b.maxY - b.minY);
    stats.maxTiles = Math.max(stats.maxTiles, r.board.placed.length);
    stats.rounds++;
    if (r.result.type === 'batida') stats.batida++; else if (r.result.team == null) stats.empate++; else stats.fechado++;
    m.applyResult(r.result);
  }
  stats.matches++; stats.wins[m.winnerTeam()]++;
}
console.log(stats);
