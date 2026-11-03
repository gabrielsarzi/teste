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
  // ---- sons de menu ----
  // toque leve: uma pedrinha encostando na outra
  uiTap() {
    burst(0.025, 3200, 1.6, 0.16);
    tone(720, 0.04, { type: 'triangle', vol: 0.07, slide: 0.85 });
  },
  // botão principal: pedra batendo na mesa, mais encorpado
  uiPrimary() {
    burst(0.04, 2400, 1.3, 0.3);
    burst(0.07, 800, 0.9, 0.18);
    tone(190, 0.08, { vol: 0.22, slide: 0.6 });
    tone(880, 0.06, { type: 'triangle', vol: 0.06, delay: 0.03 });
  },
  // voltar: dois toques descendo
  uiBack() {
    tone(560, 0.05, { type: 'triangle', vol: 0.09 });
    tone(420, 0.07, { type: 'triangle', vol: 0.08, delay: 0.05 });
  },
  // troca de tela: varrida curtinha
  uiSwipe() {
    burst(0.12, 1400, 0.7, 0.06);
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
  if (!enabled) return;
  try {
    // no app (Capacitor) usa o motor de vibração nativo; no navegador, a API web
    const native = window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Haptics;
    if (native) native.vibrate({ duration: ms });
    else if (navigator.vibrate) navigator.vibrate(ms);
  } catch {
    /* sem vibração */
  }
}

// ---------- sons do bar ao fundo ----------
// Nada de chiado: só copos tilintando e pedras batendo em outras mesas, de vez em quando.
let amb = null;
export function setAmbient(on) {
  if (!on || !enabled) {
    if (amb) clearTimeout(amb);
    amb = null;
    return;
  }
  if (amb || !ctx) return;
  const next = () => {
    amb = setTimeout(() => {
      if (ready()) {
        const r = Math.random();
        if (r < 0.45) {
          // copo de vidro
          const base = 2600 + Math.random() * 1400;
          tone(base, 0.4, { type: 'sine', vol: 0.02 });
          tone(base * 2.76, 0.25, { type: 'sine', vol: 0.008, delay: 0.005 });
        } else if (r < 0.85) {
          // pedra batendo numa mesa longe
          const n = 1 + Math.floor(Math.random() * 2);
          for (let i = 0; i < n; i++) {
            burst(0.04, 2200, 1.4, 0.06, i * 0.22);
            tone(160, 0.06, { vol: 0.05, delay: i * 0.22, slide: 0.6 });
          }
        } else {
          // dois copos brindando
          tone(3100, 0.35, { type: 'sine', vol: 0.018 });
          tone(3350, 0.3, { type: 'sine', vol: 0.016, delay: 0.03 });
        }
      }
      if (amb) next();
    }, 3500 + Math.random() * 6000);
  };
  next();
}
