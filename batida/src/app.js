// Estado global do app: configurações, visual escolhido, carreira e navegação.
import { h, store, setSpeed } from './ui/dom.js';
import { setSound } from './ui/audio.js';
import { tableTexture } from './ui/art.js';

export const settings = Object.assign(
  {
    sound: true,
    speed: 'normal', // normal | rapido | lento
    ajuda: false, // destacar as pedras que encaixam
    contagem: false, // mostrar quantas pedras de cada número já saíram
    conversa: true, // provocações e frases na mesa
    buchaVale2: true,
    laeloVale2: true,
    comecaSena: true,
    cincoBuchas: true,
    nivel: 'medio', // jogo rápido: facil | medio | dificil
    mesa: 'madeira',
    domino: 'osso',
  },
  store.get('settings', {}),
);
// migração: lá-e-lô passou a vir ligado
if (!settings.rv) {
  settings.laeloVale2 = true;
  settings.rv = 2;
}
if (settings.rv < 3) {
  delete settings.formato; // agora é sempre até 4 pontos
  settings.rv = 3;
}
store.set('settings', settings);

export function applySettings() {
  setSound(settings.sound);
  setSpeed(settings.speed === 'rapido' ? 0.6 : settings.speed === 'lento' ? 1.5 : 1);
  applyLook();
}

export function saveSettings() {
  store.set('settings', settings);
  applySettings();
}

const texCache = {};
export function applyLook() {
  const app = document.getElementById('app');
  if (!app) return;
  app.dataset.mesa = settings.mesa;
  app.dataset.domino = settings.domino;
  try {
    if (!texCache[settings.mesa]) texCache[settings.mesa] = tableTexture(settings.mesa);
    const url = texCache[settings.mesa];
    app.style.setProperty('--table-img', url ? `url(${url})` : 'none');
  } catch {
    app.style.setProperty('--table-img', 'none');
  }
}

// ---------- carreira ----------
export function career() {
  return Object.assign(
    { level: 0, fase: 0, wins: 0, titles: [], unlocked: { mesa: ['madeira'], domino: ['osso'] } },
    store.get('career', {}),
  );
}
export function saveCareer(c) {
  store.set('career', c);
}

export function stats() {
  return Object.assign({ quickWins: 0, quickPlayed: 0, rounds: 0, batidas: 0, buchas: 0 }, store.get('stats2', {}));
}
export function saveStats(s) {
  store.set('stats2', s);
}

// ---------- navegação ----------
const screens = {};
let current = null;
export const registerScreen = (name, fn) => (screens[name] = fn);

export function go(name, params = {}) {
  if (current && current.destroy) current.destroy();
  const app = document.getElementById('app');
  app.querySelector('#stage')?.remove();
  app.querySelectorAll('.modal-back, .float-text, .toast, .tile.flying').forEach((e) => e.remove());
  const stage = h('div', { id: 'stage' });
  app.prepend(stage);
  current = screens[name](stage, params) || null;
}
