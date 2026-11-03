// Node: simula mesas com bot guloso, sem parceiros, para calibrar metas.
globalThis.window = {}; 
const { newRun, startMesa, playableSides, placePending, scorePlay, commitPlay, discard, anyPlayable, passHand } = await import('../src/virada/run.js');
const { makeRng } = await import('../src/core/tiles.js');
const rng = makeRng(7);
function playMesa(run) {
  const mesa = startMesa(run);
  let guard = 0;
  while (guard++ < 50) {
    // gulosa: coloca até 5 pedras escolhendo a de mais pontos
    for (let k = 0; k < 5; k++) {
      let best = null;
      for (const t of mesa.hand) for (const s of playableSides(mesa, t)) { const v = t.a + t.b; if (!best || v > best.v) best = { t, s, v }; }
      if (!best) break;
      placePending(mesa, best.t, best.s);
    }
    if (!mesa.pending.length) {
      if (mesa.discardsLeft > 0) { discard(mesa, mesa.hand.slice(0, 4)); continue; }
      passHand(mesa); if (mesa.handsLeft <= 0) return mesa.score; continue;
    }
    const r = scorePlay(run, mesa, rng);
    const res = commitPlay(run, mesa, r);
    if (res.lost || mesa.handsLeft <= 0 || res.won && false) return mesa.score;
  }
  return mesa.score;
}
const scores = [];
for (let i = 0; i < 400; i++) { const run = newRun(i + 1); run.mesaIdx = 0; scores.push(playMesa(run)); }
scores.sort((a, b) => a - b);
console.log('4 jogadas sem parceiros: p10', scores[40], 'p50', scores[200], 'p90', scores[360]);
