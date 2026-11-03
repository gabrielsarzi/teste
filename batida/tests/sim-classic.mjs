import { ClassicMatch } from '../src/classic/engine.js';
import { chooseMove, chooseMoveMaster } from '../src/classic/ai.js';
for (const players of [4, 3, 2]) {
  const stats = { batida: 0, fechado: 0, empate: 0, rounds: 0, draws: 0, wins: new Array(players === 4 ? 2 : players).fill(0) };
  for (let i = 0; i < 1500; i++) {
    const m = new ClassicMatch({ players }, i + 1);
    while (!m.isOver()) {
      let r = m.newRound();
      while (r.voltou != null) r = m.redeal();
      let g = 0;
      while (!r.result && g++ < 400) {
        const p = r.turn;
        const mv = i % 5 === 0 && players === 4 ? chooseMoveMaster(r, p, 6) : chooseMove(r, p, 0.7);
        if (mv) r.play(p, mv.tile, mv.side);
        else if (r.canDraw(p)) { r.draw(p); stats.draws++; }
        else r.pass(p);
      }
      if (!r.result) throw new Error('round never ended ' + players + ' seed ' + (i + 1));
      const total = r.hands.flat().length + r.pile.length + r.board.placed.length;
      if (total !== 28) throw new Error('perdeu pedra');
      stats.rounds++;
      if (r.result.type === 'batida') stats.batida++; else if (r.result.team == null) stats.empate++; else stats.fechado++;
      m.applyResult(r.result);
    }
    stats.wins[m.winnerTeam()]++;
  }
  console.log(players, 'jogadores', JSON.stringify(stats));
}
