// Música de fundo: gravação de viola caipira de verdade, em loop.
// "Pagode de Viola No 1", Projeto Música Artesanal (Gabriel Fedel), licença CC BY-SA 3.0.
import violaUrl from '../assets/viola.mp3';

let el = null;
let playing = false;
let target = 0;
let fadeTimer = null;

function fadeTo(v, ms = 900) {
  clearInterval(fadeTimer);
  const start = el.volume;
  const t0 = performance.now();
  fadeTimer = setInterval(() => {
    const k = Math.min(1, (performance.now() - t0) / ms);
    el.volume = Math.max(0, Math.min(1, start + (v - start) * k));
    if (k >= 1) {
      clearInterval(fadeTimer);
      if (v === 0) el.pause();
    }
  }, 40);
}

export function startMusic(level = 1) {
  try {
    if (!el) {
      el = new Audio(violaUrl);
      el.loop = true;
      el.preload = 'auto';
      el.volume = 0;
    }
    target = 0.5 * level;
    if (!playing || el.paused) {
      playing = true;
      const p = el.play();
      if (p && p.catch) p.catch(() => (playing = false));
    }
    fadeTo(target);
    return true;
  } catch {
    return false;
  }
}

export function stopMusic() {
  if (!el) return;
  playing = false;
  fadeTo(0, 500);
}

export const musicPlaying = () => playing;
