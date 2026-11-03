import { ClassicMatch } from '../src/classic/engine.js';
import { chooseMove } from '../src/classic/ai.js';
import { setLimit } from '../src/core/board.js';
const AW = +process.argv[2] || 300, AH = +process.argv[3] || 430;
for (const lim of [2.6, 3.6, 4.6, 5.6, 6.6]) {
  setLimit(lim);
  let ks = [], overlaps = 0;
  for (let i = 0; i < 400; i++) {
    const m = new ClassicMatch({}, i + 1); const r = m.newRound(); let g = 0;
    while (!r.result && g++ < 200) { const mv = chooseMove(r, r.turn); mv ? r.play(r.turn, mv.tile, mv.side) : r.pass(r.turn); }
    // overlap check using half cells (rounded to 0.5 grid)
    const cells = new Set();
    for (const p of r.board.placed) for (const h of [p.near, p.far]) { const k = h.x.toFixed(1) + ',' + h.y.toFixed(1); if (cells.has(k)) overlaps++; cells.add(k); }
    // rectangle overlap check
    const rects = r.board.placed.map(p => ({ x0: Math.min(p.near.x, p.far.x) - .5, x1: Math.max(p.near.x, p.far.x) + .5, y0: Math.min(p.near.y, p.far.y) - .5, y1: Math.max(p.near.y, p.far.y) + .5 }));
    for (let a = 0; a < rects.length; a++) for (let b = a + 1; b < rects.length; b++) { const A = rects[a], B = rects[b]; if (A.x0 < B.x1 - 1e-6 && B.x0 < A.x1 - 1e-6 && A.y0 < B.y1 - 1e-6 && B.y0 < A.y1 - 1e-6) overlaps++; }
    const b = r.board.bounds(); const pad = 1.2;
    const k = Math.min(AW / ((b.maxX - b.minX + 2 * pad) * 40), AH / ((b.maxY - b.minY + 2 * pad) * 40));
    ks.push(k);
  }
  ks.sort((a, b) => a - b);
  console.log('limit', lim, 'k p10', ks[40].toFixed(2), 'p50', ks[200].toFixed(2), 'overlaps', overlaps);
}
