import { ClassicMatch } from '../src/classic/engine.js';
import { chooseMove, chooseMoveMaster } from '../src/classic/ai.js';
let w = 0, N = +process.argv[2] || 200; const t0 = Date.now(); let moves = 0;
for (let i = 0; i < N; i++) {
  const m = new ClassicMatch({}, 1000 + i);
  while (!m.isOver()) { const r = m.newRound(); let g = 0;
    while (!r.result && g++ < 200) { const q = r.turn; const mv = q % 2 === 0 ? (moves++, chooseMoveMaster(r, q)) : chooseMove(r, q, 0.7); mv ? r.play(q, mv.tile, mv.side) : r.pass(q); }
    m.applyResult(r.result); }
  if (m.winnerTeam() === 0) w++;
}
console.log(`mestre vs 0.7: ${(100 * w / N).toFixed(1)}%  ms/jogada ${((Date.now() - t0) / moves).toFixed(1)}`);
