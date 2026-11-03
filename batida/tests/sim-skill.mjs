import { ClassicMatch } from '../src/classic/engine.js';
import { chooseMove } from '../src/classic/ai.js';
for (const [a, b] of [[0.7, 0.1], [0.7, 0.4], [0.7, 0.7], [0.7, 1]]) {
  let w = 0, N = 1500;
  for (let i = 0; i < N; i++) {
    const m = new ClassicMatch({}, i + 1);
    while (!m.isOver()) { const r = m.newRound(); let g = 0;
      while (!r.result && g++ < 200) { const sk = r.turn % 2 === 0 ? a : b; const mv = chooseMove(r, r.turn, sk); mv ? r.play(r.turn, mv.tile, mv.side) : r.pass(r.turn); }
      m.applyResult(r.result); }
    if (m.winnerTeam() === 0) w++;
  }
  console.log(`nós ${a} vs eles ${b}: vitória ${(100 * w / N).toFixed(1)}%`);
}
