// Música de fundo: modão de viola caipira, em ritmo de toada (3 por 4).
// Viola de dez cordas sintetizada (corda dedilhada Karplus-Strong com o par em oitava),
// violão no baixo e a melodia em terças, como a dupla cantando. Sem chiado.
import { audioCtx } from './audio.js';

const BPM = 92; // semínima
const EIGHTH = 60 / BPM / 2;
// Ré maior. Escala para achar a terça de cima da melodia.
const SCALE = [61, 62, 64, 66, 67, 69, 71, 73, 74, 76, 78, 79, 81, 83, 85, 86];
const third = (m) => {
  const i = SCALE.indexOf(m);
  return i >= 0 && i + 2 < SCALE.length ? SCALE[i + 2] : m + 4;
};
// Acordes: D, G, A7 (baixo, notas do rasqueado)
const CH = {
  D: { bass: [38, 45], notes: [57, 62, 66, 69] },
  G: { bass: [43, 50], notes: [55, 59, 62, 67] },
  A7: { bass: [45, 40], notes: [57, 61, 64, 67] },
};
// 16 compassos: 8 com melodia (ponteado em terças) e 8 só no acompanhamento
const BARS = ['D', 'D', 'G', 'D', 'A7', 'A7', 'D', 'D', 'D', 'G', 'G', 'D', 'A7', 'A7', 'D', 'D'];
// melodia: [colcheia (0..5), nota] por compasso
const MELODY = [
  [[0, 66], [2, 69], [4, 66]],
  [[0, 64], [3, 62], [4, 64]],
  [[0, 67], [2, 71], [4, 69]],
  [[0, 66], [4, 64]],
  [[0, 64], [2, 67], [4, 64]],
  [[0, 61], [3, 64], [4, 62]],
  [[0, 62], [2, 66], [4, 64]],
  [[0, 62]],
];

const cache = new Map();
let playing = false;
let timer = null;
let out = null;
let nextTime = 0;
let step = 0;

function pluck(ctx, midi, dur, bright, decay) {
  const key = `${midi}:${bright}:${decay}`;
  if (cache.has(key)) return cache.get(key);
  const sr = ctx.sampleRate;
  const freq = 440 * Math.pow(2, (midi - 69) / 12);
  const len = Math.floor(sr * dur);
  const buf = ctx.createBuffer(1, len, sr);
  const d = buf.getChannelData(0);
  const period = Math.max(2, Math.round(sr / freq));
  const ring = new Float32Array(period);
  for (let i = 0; i < period; i++) ring[i] = Math.random() * 2 - 1;
  for (let i = 1; i < period; i++) ring[i] = ring[i] * bright + ring[i - 1] * (1 - bright);
  let idx = 0;
  for (let i = 0; i < len; i++) {
    const nxt = (idx + 1) % period;
    const v = ring[idx];
    ring[idx] = decay * 0.5 * (v + ring[nxt]);
    d[i] = v;
    idx = nxt;
  }
  const fade = Math.min(2400, len);
  for (let i = len - fade; i < len; i++) d[i] *= (len - i) / fade;
  cache.set(key, buf);
  return buf;
}

function play(ctx, buf, t, vol, pan = 0) {
  const s = ctx.createBufferSource();
  s.buffer = buf;
  const g = ctx.createGain();
  g.gain.value = vol;
  let node = s.connect(g);
  if (ctx.createStereoPanner) {
    const p = ctx.createStereoPanner();
    p.pan.value = pan;
    node = node.connect(p);
  }
  node.connect(out);
  s.start(t);
}

// viola caipira: cada nota vem com o par da corda em oitava, um tiquinho atrasado
function viola(ctx, midi, t, vol, pan) {
  play(ctx, pluck(ctx, midi, 1.6, 0.82, 0.995), t, vol, pan);
  play(ctx, pluck(ctx, midi + 12, 1.1, 0.85, 0.993), t + 0.009, vol * 0.45, pan);
}

function schedule() {
  const a = audioCtx();
  if (!a || !playing) return;
  const { ctx } = a;
  while (nextTime < ctx.currentTime + 0.5) {
    const barIdx = Math.floor(step / 6) % BARS.length;
    const s8 = step % 6;
    const ch = CH[BARS[barIdx]];
    // violão no baixo: tempo 1 (alterna tônica e quinta a cada compasso)
    if (s8 === 0) play(ctx, pluck(ctx, ch.bass[barIdx % 2], 1.8, 0.3, 0.996), nextTime, 0.55, -0.2);
    // rasqueado da viola nos tempos 2 e 3 (pá-pá da toada)
    if (s8 === 2 || s8 === 4) {
      ch.notes.forEach((n, i) => viola(ctx, n, nextTime + i * 0.014, s8 === 2 ? 0.1 : 0.08, 0.15));
    }
    // ponteado em terças nos 8 primeiros compassos
    if (barIdx < 8) {
      for (const [pos, note] of MELODY[barIdx]) {
        if (pos !== s8) continue;
        viola(ctx, note, nextTime, 0.2, -0.05);
        viola(ctx, third(note), nextTime + 0.006, 0.15, 0.1);
      }
    }
    nextTime += EIGHTH * (s8 % 2 === 0 ? 1.04 : 0.96); // leve balanço
    step++;
  }
}

export function startMusic(level = 1) {
  const a = audioCtx();
  if (!a) return false;
  const { ctx, master } = a;
  if (!out) {
    out = ctx.createGain();
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 5200;
    out.connect(lp).connect(master);
    out.gain.value = 0;
  }
  out.gain.setTargetAtTime(0.42 * level, ctx.currentTime, 0.6);
  if (playing) return true;
  playing = true;
  nextTime = ctx.currentTime + 0.15;
  timer = setInterval(schedule, 120);
  schedule();
  return true;
}

export function stopMusic() {
  const a = audioCtx();
  if (out && a) out.gain.setTargetAtTime(0, a.ctx.currentTime, 0.4);
  playing = false;
  clearInterval(timer);
  timer = null;
}

export const musicPlaying = () => playing;
