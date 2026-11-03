// Efeitos chiptune e música simples gerados com WebAudio.
window.SFX = (function () {
  let ctx = null, master, sfxG, musG, noiseBuf;
  const on = { sfx: true, music: true };
  const last = {};
  const mf = m => 440 * Math.pow(2, (m - 69) / 12);

  function unlock() {
    if (!ctx) {
      try { ctx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { return; }
      master = ctx.createGain(); master.gain.value = 0.55; master.connect(ctx.destination);
      sfxG = ctx.createGain(); sfxG.connect(master);
      musG = ctx.createGain(); musG.gain.value = on.music ? 0.18 : 0; musG.connect(master);
      noiseBuf = ctx.createBuffer(1, ctx.sampleRate * 0.6, ctx.sampleRate);
      const d = noiseBuf.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
      startMusic();
    }
    if (ctx.state === 'suspended') ctx.resume();
  }

  function tone(type, f0, f1, dur, vol, dest, when) {
    const t = when || ctx.currentTime;
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type; o.frequency.setValueAtTime(f0, t);
    if (f1) o.frequency.exponentialRampToValueAtTime(f1, t + dur);
    g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(dest || sfxG); o.start(t); o.stop(t + dur + 0.02);
  }
  function noise(dur, vol, freq) {
    const t = ctx.currentTime;
    const s = ctx.createBufferSource(); s.buffer = noiseBuf;
    const f = ctx.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = freq;
    const g = ctx.createGain(); g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    s.connect(f); f.connect(g); g.connect(sfxG); s.start(t); s.stop(t + dur);
  }
  const defs = {
    shoot: () => tone('square', 900, 420, 0.05, 0.035),
    boom: () => { noise(0.35, 0.25, 700); tone('triangle', 130, 40, 0.3, 0.22); },
    zap: () => tone('sawtooth', 1400, 180, 0.12, 0.04),
    ice: () => tone('triangle', 1600, 900, 0.09, 0.06),
    die: () => noise(0.1, 0.09, 1800),
    coin: () => { tone('square', 988, 0, 0.05, 0.03); tone('square', 1319, 0, 0.08, 0.03, null, ctx.currentTime + 0.05); },
    build: () => tone('square', 220, 440, 0.12, 0.07),
    up: () => { tone('square', 523, 0, 0.07, 0.05); tone('square', 784, 0, 0.07, 0.05, null, ctx.currentTime + 0.07); tone('square', 1046, 0, 0.12, 0.05, null, ctx.currentTime + 0.14); },
    error: () => tone('square', 180, 120, 0.15, 0.07),
    wave: () => { tone('sawtooth', 196, 0, 0.25, 0.06); tone('sawtooth', 294, 0, 0.45, 0.06, null, ctx.currentTime + 0.22); },
    boss: () => { tone('sawtooth', 90, 55, 0.9, 0.13); noise(0.6, 0.12, 300); },
    hurt: () => { tone('square', 300, 90, 0.25, 0.09); noise(0.2, 0.1, 900); },
    click: () => tone('square', 660, 0, 0.03, 0.035),
    over: () => { [392, 330, 262, 196].forEach((f, i) => tone('triangle', f, 0, 0.35, 0.08, null, ctx.currentTime + i * 0.22)); }
  };
  function play(n) {
    if (!ctx || !on.sfx) return;
    const now = performance.now();
    if (last[n] && now - last[n] < 45) return;
    last[n] = now;
    if (defs[n]) defs[n]();
  }

  // Música: Lá menor, progressão Am F C G, 100 bpm, semicolcheias.
  const BASS = [45, 41, 48, 43];
  const ARP = [[69, 72, 76, 72], [65, 69, 72, 69], [67, 72, 76, 72], [67, 71, 74, 71]];
  const MEL = [76, 0, 0, 74, 72, 0, 74, 0, 72, 0, 69, 0, 0, 0, 67, 0, 69, 0, 0, 72, 74, 0, 76, 0, 79, 0, 76, 0, 74, 0, 0, 0];
  let step = 0, nextT = 0;
  function startMusic() {
    nextT = ctx.currentTime + 0.1;
    setInterval(() => {
      if (!ctx || ctx.state !== 'running') return;
      const spb = 60 / 100 / 4;
      while (nextT < ctx.currentTime + 0.15) {
        const bar = Math.floor(step / 16) % 4, s = step % 16;
        if (s % 4 === 0) tone('triangle', mf(BASS[bar]), 0, spb * 3.5, 0.5, musG, nextT);
        if (s % 2 === 0) tone('square', mf(ARP[bar][(s / 2) % 4]), 0, spb * 0.9, 0.08, musG, nextT);
        const m = MEL[(step % 64) >> 1];
        if (step % 2 === 0 && m && Math.floor(step / 64) % 2 === 1) tone('square', mf(m), 0, spb * 1.8, 0.12, musG, nextT);
        if (s === 4 || s === 12) { /* caixa */ }
        nextT += spb; step++;
      }
    }, 30);
  }
  function set(k, v) {
    on[k] = v;
    if (k === 'music' && musG) musG.gain.value = v ? 0.18 : 0;
  }
  return { unlock, play, set, on };
})();
