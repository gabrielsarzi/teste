// Música de fundo: violão de bossa nova sintetizado na hora (corda dedilhada pelo
// método Karplus-Strong), baixo no polegar e um chocalho bem leve. Sem chiado.
import { audioCtx } from './audio.js';

const BPM = 112;
const STEP = 60 / BPM / 4; // semicolcheia
// Progressão: Dm9 – G13 – Cmaj9 – A7(b9), uma por compasso
const CHORDS = [
  { bass: 38, notes: [53, 57, 60, 64] }, // Dm9 (F A C E)
  { bass: 43, notes: [53, 57, 59, 64] }, // G13 (F A B E)
  { bass: 36, notes: [52, 55, 59, 62] }, // Cmaj9 (E G B D)
  { bass: 45, notes: [55, 58, 61, 64] }, // A7b9 (G Bb C# E)
];
// batida de bossa: acordes em contratempo (16 semicolcheias por compasso)
const COMP = [[0, 3, 6, 10, 12], [2, 5, 8, 11, 14]];
const BASS = [0, 6, 8, 14];

const cache = new Map();
let playing = false;
let timer = null;
let out = null;
let nextTime = 0;
let step = 0;

function pluck(ctx, midi, dur = 1.6, bright = 0.5) {
  const key = `${midi}:${bright}`;
  if (cache.has(key)) return cache.get(key);
  const sr = ctx.sampleRate;
  const freq = 440 * Math.pow(2, (midi - 69) / 12);
  const len = Math.floor(sr * dur);
  const buf = ctx.createBuffer(1, len, sr);
  const d = buf.getChannelData(0);
  const period = Math.round(sr / freq);
  const ring = new Float32Array(period);
  for (let i = 0; i < period; i++) ring[i] = Math.random() * 2 - 1;
  // filtra o ruído inicial para o ataque ficar macio (dedo, não palheta)
  for (let k = 0; k < 2; k++) for (let i = 1; i < period; i++) ring[i] = ring[i] * bright + ring[i - 1] * (1 - bright);
  let idx = 0;
  const decay = 0.996;
  for (let i = 0; i < len; i++) {
    const nxt = (idx + 1) % period;
    const v = ring[idx];
    ring[idx] = decay * 0.5 * (v + ring[nxt]);
    d[i] = v;
    idx = nxt;
  }
  // fade-out no fim para não estalar
  for (let i = len - 2000; i < len; i++) d[i] *= (len - i) / 2000;
  cache.set(key, buf);
  return buf;
}

function play(ctx, buf, t, vol) {
  const s = ctx.createBufferSource();
  s.buffer = buf;
  const g = ctx.createGain();
  g.gain.value = vol;
  s.connect(g).connect(out);
  s.start(t);
}

function shaker(ctx, t, vol) {
  const len = Math.floor(ctx.sampleRate * 0.05);
  const buf = ctx.createBuffer(1, len, ctx.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3);
  const s = ctx.createBufferSource();
  s.buffer = buf;
  const f = ctx.createBiquadFilter();
  f.type = 'highpass';
  f.frequency.value = 6000;
  const g = ctx.createGain();
  g.gain.value = vol;
  s.connect(f).connect(g).connect(out);
  s.start(t);
}

function schedule() {
  const a = audioCtx();
  if (!a || !playing) return;
  const { ctx } = a;
  while (nextTime < ctx.currentTime + 0.4) {
    const bar = Math.floor(step / 16) % CHORDS.length;
    const s16 = step % 16;
    const ch = CHORDS[bar];
    const pat = COMP[Math.floor(step / 16) % 2];
    if (BASS.includes(s16)) play(ctx, pluck(ctx, ch.bass + (s16 === 6 || s16 === 14 ? 7 : 0), 1.4, 0.35), nextTime, 0.5);
    if (pat.includes(s16)) {
      // strum: notas do acorde com 12 ms de diferença
      ch.notes.forEach((n, i) => play(ctx, pluck(ctx, n, 1.2, 0.55), nextTime + i * 0.012, 0.16));
    }
    if (s16 % 2 === 0) shaker(ctx, nextTime, s16 % 4 === 0 ? 0.05 : 0.025);
    nextTime += STEP * (s16 % 2 === 0 ? 1.08 : 0.92); // leve balanço
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
    lp.frequency.value = 3800;
    out.connect(lp).connect(master);
    out.gain.value = 0;
  }
  out.gain.setTargetAtTime(0.32 * level, ctx.currentTime, 0.6);
  if (playing) return true;
  playing = true;
  nextTime = ctx.currentTime + 0.1;
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
