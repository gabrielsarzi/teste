// Sons sintetizados na hora (sem arquivos): batida de pedra, contagem, caixa registradora...
let ctx = null;
let master = null;
let noise = null;
let enabled = true;

export function setSound(on) {
  enabled = on;
}
export const soundOn = () => enabled;

export function unlockAudio() {
  try {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      ctx = new AC();
      master = ctx.createGain();
      master.gain.value = 0.55;
      const comp = ctx.createDynamicsCompressor();
      master.connect(comp);
      comp.connect(ctx.destination);
      const len = ctx.sampleRate * 0.5;
      noise = ctx.createBuffer(1, len, ctx.sampleRate);
      const d = noise.getChannelData(0);
      for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    }
    if (ctx.state === 'suspended') ctx.resume();
  } catch {
    ctx = null;
  }
}

function ready() {
  return enabled && ctx && ctx.state === 'running';
}

function env(g, t, a, peak, dur) {
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(peak, t + a);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
}

function tone(freq, dur, { type = 'sine', vol = 0.3, delay = 0, slide = 0 } = {}) {
  if (!ready()) return;
  const t = ctx.currentTime + delay;
  const o = ctx.createOscillator();
  const g = ctx.createGain();
  o.type = type;
  o.frequency.setValueAtTime(freq, t);
  if (slide) o.frequency.exponentialRampToValueAtTime(freq * slide, t + dur);
  env(g, t, 0.005, vol, dur);
  o.connect(g).connect(master);
  o.start(t);
  o.stop(t + dur + 0.02);
}

function burst(dur, freq, q, vol, delay = 0) {
  if (!ready()) return;
  const t = ctx.currentTime + delay;
  const s = ctx.createBufferSource();
  s.buffer = noise;
  const f = ctx.createBiquadFilter();
  f.type = 'bandpass';
  f.frequency.value = freq;
  f.Q.value = q;
  const g = ctx.createGain();
  env(g, t, 0.002, vol, dur);
  s.connect(f).connect(g).connect(master);
  s.start(t, Math.random() * 0.3);
  s.stop(t + dur + 0.02);
}

export const sfx = {
  // pedra batendo na mesa de madeira
  clack(power = 1) {
    burst(0.05, 2400 + Math.random() * 600, 1.4, 0.5 * power);
    burst(0.09, 900, 0.9, 0.35 * power);
    tone(150 + Math.random() * 30, 0.09, { type: 'sine', vol: 0.35 * power, slide: 0.6 });
  },
  slam() {
    burst(0.08, 1800, 1, 0.9);
    burst(0.18, 500, 0.7, 0.6);
    tone(95, 0.22, { vol: 0.6, slide: 0.5 });
  },
  pick() {
    tone(880, 0.05, { type: 'triangle', vol: 0.12 });
  },
  drop() {
    tone(520, 0.06, { type: 'triangle', vol: 0.12, slide: 0.8 });
  },
  chip(step = 0) {
    const f = 440 * Math.pow(2, Math.min(step, 18) / 12);
    tone(f, 0.09, { type: 'triangle', vol: 0.22 });
    tone(f * 2, 0.05, { type: 'sine', vol: 0.06 });
  },
  mult(step = 0) {
    const f = 220 * Math.pow(2, Math.min(step, 14) / 12);
    tone(f, 0.14, { type: 'sawtooth', vol: 0.1 });
    tone(f * 1.5, 0.12, { type: 'square', vol: 0.05 });
  },
  xmult() {
    tone(330, 0.2, { type: 'sawtooth', vol: 0.12, slide: 2 });
    burst(0.2, 3000, 0.6, 0.15);
  },
  coin() {
    tone(1568, 0.08, { type: 'square', vol: 0.06 });
    tone(2093, 0.18, { type: 'square', vol: 0.06, delay: 0.07 });
  },
  register() {
    burst(0.05, 3500, 2, 0.3);
    tone(1318, 0.3, { type: 'triangle', vol: 0.18, delay: 0.04 });
    tone(1760, 0.4, { type: 'triangle', vol: 0.14, delay: 0.1 });
  },
  shuffle() {
    for (let i = 0; i < 9; i++) burst(0.04, 1800 + Math.random() * 1500, 1.2, 0.18, i * 0.035 + Math.random() * 0.02);
  },
  pass() {
    tone(196, 0.12, { type: 'triangle', vol: 0.18 });
    tone(165, 0.16, { type: 'triangle', vol: 0.16, delay: 0.1 });
  },
  win() {
    [523, 659, 784, 1046].forEach((f, i) => tone(f, 0.28, { type: 'triangle', vol: 0.2, delay: i * 0.09 }));
    tone(1318, 0.6, { type: 'sine', vol: 0.12, delay: 0.38 });
  },
  lose() {
    [392, 330, 262, 196].forEach((f, i) => tone(f, 0.3, { type: 'triangle', vol: 0.18, delay: i * 0.13 }));
  },
  total() {
    burst(0.35, 600, 0.5, 0.35);
    tone(110, 0.45, { vol: 0.5, slide: 0.5 });
    tone(880, 0.4, { type: 'triangle', vol: 0.12 });
  },
  // toc-toc: quem passa bate na mesa
  knock() {
    for (const d of [0, 0.16]) {
      tone(110, 0.09, { vol: 0.55, delay: d, slide: 0.7 });
      burst(0.05, 700, 1.2, 0.5, d);
    }
  },
  tick(urgent = false) {
    tone(urgent ? 1400 : 1000, 0.035, { type: 'square', vol: 0.05 });
  },
  // pedra arrastada do monte
  drawTile() {
    burst(0.12, 2600, 0.8, 0.18);
    tone(300, 0.06, { type: 'triangle', vol: 0.08, delay: 0.08 });
  },
  vote() {
    tone(660, 0.08, { type: 'triangle', vol: 0.12 });
    tone(880, 0.1, { type: 'triangle', vol: 0.1, delay: 0.08 });
  },
  coins() {
    for (let i = 0; i < 5; i++) tone(1800 + Math.random() * 900, 0.06, { type: 'square', vol: 0.04, delay: i * 0.05 });
  },
  error() {
    tone(140, 0.12, { type: 'square', vol: 0.08 });
  },
};

export function haptic(ms = 12) {
  try {
    if (enabled && navigator.vibrate) navigator.vibrate(ms);
  } catch {
    /* sem vibração */
  }
}

// ---------- barulho de bar ao fundo ----------
let amb = null;
export function setAmbient(on) {
  try {
    if (!on || !enabled) {
      if (amb) {
        amb.gain.gain.setTargetAtTime(0, ctx.currentTime, 0.4);
        const a = amb;
        setTimeout(() => a.src.stop(), 1500);
        clearInterval(a.timer);
        amb = null;
      }
      return;
    }
    if (amb || !ctx) return;
    // conversa abafada: ruído marrom filtrado com volume que sobe e desce
    const len = ctx.sampleRate * 4;
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const d = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < len; i++) {
      last = (last + 0.02 * (Math.random() * 2 - 1)) / 1.02;
      d[i] = last * 3.5;
    }
    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.loop = true;
    const f = ctx.createBiquadFilter();
    f.type = 'bandpass';
    f.frequency.value = 500;
    f.Q.value = 0.6;
    const gain = ctx.createGain();
    gain.gain.value = 0;
    gain.gain.setTargetAtTime(0.09, ctx.currentTime, 1.5);
    const lfo = ctx.createOscillator();
    const lfoG = ctx.createGain();
    lfo.frequency.value = 0.13;
    lfoG.gain.value = 0.03;
    lfo.connect(lfoG).connect(gain.gain);
    lfo.start();
    src.connect(f).connect(gain).connect(master);
    src.start();
    // copo tilintando de vez em quando
    const timer = setInterval(() => {
      if (!ready() || Math.random() < 0.5) return;
      const base = 2400 + Math.random() * 1600;
      tone(base, 0.25, { type: 'sine', vol: 0.025 });
      tone(base * 1.5, 0.2, { type: 'sine', vol: 0.015, delay: 0.02 });
    }, 3500);
    amb = { src, gain, timer };
  } catch {
    amb = null;
  }
}
