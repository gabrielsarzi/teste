// Rádio do boteco: gravações de verdade, uma por estação, tocando em loop.
// Créditos e licenças em store/CREDITOS.md (todas permitem uso comercial com crédito).
import violaUrl from '../assets/viola.mp3';
import sambaUrl from '../assets/samba.mp3';
import choroUrl from '../assets/choro.mp3';
import bossaUrl from '../assets/bossa.mp3';

export const STATIONS = [
  { id: 'viola', name: 'Viola caipira', url: violaUrl },
  { id: 'samba', name: 'Samba', url: sambaUrl },
  { id: 'choro', name: 'Choro', url: choroUrl },
  { id: 'bossa', name: 'Bossa nova', url: bossaUrl },
];

const BASE_VOL = 0.28; // volume nos menus; na partida fica mais baixo ainda
let current = null; // { id, el }
let playing = false;
let level = 1;

function fade(el, to, ms, after) {
  const from = el.volume;
  const t0 = performance.now();
  const step = () => {
    const k = Math.min(1, (performance.now() - t0) / ms);
    el.volume = Math.max(0, Math.min(1, from + (to - from) * k));
    if (k < 1) requestAnimationFrame(step);
    else if (after) after();
  };
  requestAnimationFrame(step);
}

function station(id) {
  return STATIONS.find((s) => s.id === id) || STATIONS[0];
}

// Liga (ou troca) a estação. lvl: 1 nos menus, menor durante o jogo.
export function startMusic(lvl = 1, id) {
  level = lvl;
  const st = station(id || (current && current.id) || 'viola');
  try {
    if (!current || current.id !== st.id) {
      const old = current;
      if (old) fade(old.el, 0, 700, () => old.el.pause());
      const el = new Audio(st.url);
      el.loop = true;
      el.volume = 0;
      current = { id: st.id, el };
    }
    const p = current.el.play();
    if (p && p.catch) p.catch(() => (playing = false));
    playing = true;
    fade(current.el, BASE_VOL * level, 900);
    return true;
  } catch {
    return false;
  }
}

export function stopMusic() {
  if (!current) return;
  playing = false;
  const el = current.el;
  fade(el, 0, 500, () => el.pause());
}

export const musicPlaying = () => playing;
