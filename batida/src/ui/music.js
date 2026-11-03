// Rádio do boteco: gravações de verdade, uma por estação, tocando em loop.
// Um único tocador para tudo (troca só a faixa): é o que funciona em todos os
// navegadores e celulares, que às vezes só liberam o primeiro tocador criado.
// Créditos e licenças em store/CREDITOS.md.
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
let el = null;
let currentId = null;
let playing = false;
let fadeTimer = null;
let switching = null;

function player() {
  if (!el) {
    el = new Audio();
    el.loop = true;
    el.preload = 'auto';
    el.volume = 0;
  }
  return el;
}

function fadeTo(to, ms) {
  clearInterval(fadeTimer);
  const a = player();
  const from = a.volume;
  const t0 = Date.now();
  return new Promise((resolve) => {
    fadeTimer = setInterval(() => {
      const k = Math.min(1, (Date.now() - t0) / ms);
      a.volume = Math.max(0, Math.min(1, from + (to - from) * k));
      if (k >= 1) {
        clearInterval(fadeTimer);
        resolve();
      }
    }, 30);
  });
}

function tryPlay() {
  const a = player();
  try {
    const p = a.play();
    if (p && p.catch) {
      p.catch(() => {
        // o navegador barrou: tenta de novo no próximo toque na tela
        const retry = () => {
          removeEventListener('pointerdown', retry);
          if (playing) a.play().catch(() => {});
        };
        addEventListener('pointerdown', retry);
      });
    }
  } catch {
    /* sem áudio */
  }
}

// Liga ou troca a estação. lvl: 1 nos menus, menor durante o jogo.
export function startMusic(lvl = 1, id) {
  const st = STATIONS.find((s) => s.id === id) || STATIONS.find((s) => s.id === currentId) || STATIONS[0];
  const a = player();
  const vol = BASE_VOL * lvl;
  playing = true;
  if (currentId !== st.id) {
    const token = {};
    switching = token;
    const change = () => {
      if (switching !== token) return;
      currentId = st.id;
      a.src = st.url;
      a.currentTime = 0;
      tryPlay();
      fadeTo(vol, 900);
    };
    // troca a faixa já, dentro do toque (o celular exige), e só depois faz o fade-in
    if (a.src && !a.paused) {
      a.volume = Math.min(a.volume, 0.05);
    }
    change();
    return true;
  }
  if (a.paused) tryPlay();
  fadeTo(vol, 900);
  return true;
}

export function stopMusic() {
  if (!el) return;
  playing = false;
  fadeTo(0, 500).then(() => {
    if (!playing) el.pause();
  });
}

export const musicPlaying = () => playing;
