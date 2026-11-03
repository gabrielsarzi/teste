// Estado global do app: configurações, visual escolhido, carreira e navegação.
import { h, store, setSpeed } from './ui/dom.js';
import { setSound, setAmbient, sfx } from './ui/audio.js';
import { tableTexture, grainTexture } from './ui/art.js';

export const settings = Object.assign(
  {
    sound: true,
    speed: 'normal', // normal | rapido | lento
    ajuda: false, // destacar as pedras que encaixam
    contagem: false, // mostrar quantas pedras de cada número já saíram
    conversa: true, // provocações e frases na mesa
    telaLimpa: false, // esconde os textos de ajuda da mesa
    tempo: 30, // segundos para jogar (0 = sem limite)
    somBar: false, // sons do bar ao fundo (copos e pedras)
    jogadores: 4, // jogo rápido: 2, 3 ou 4
    aposta: 20,
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
if (settings.rv < 4) {
  settings.somBar = false; // o ruído antigo saiu; o novo começa desligado
  settings.rv = 4;
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
  setAmbient(settings.sound && settings.somBar);
}

const texCache = {};
export function applyLook() {
  const app = document.getElementById('app');
  if (!app) return;
  app.dataset.mesa = settings.mesa;
  if (!texCache.grain) {
    try {
      texCache.grain = grainTexture();
      app.style.setProperty('--grain', `url(${texCache.grain})`);
    } catch {
      /* sem canvas */
    }
  }
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

// ---------- dinheiro ----------
export function wallet() {
  return store.get('wallet', 200);
}
export function setWallet(v) {
  store.set('wallet', Math.max(0, Math.round(v)));
  document.querySelectorAll('[data-wallet]').forEach((el) => (el.textContent = money(wallet())));
}
export const money = (v) => 'R$ ' + Math.round(v).toLocaleString('pt-BR');

// ---------- rivalidade: vitórias e derrotas contra cada personagem ----------
export function rivals() {
  return store.get('rivals', {});
}
export function addRival(id, won) {
  const r = rivals();
  const cur = r[id] || { w: 0, l: 0 };
  if (won) cur.w++;
  else cur.l++;
  r[id] = cur;
  store.set('rivals', r);
}

// visual que você tem: ganho na carreira ou comprado na loja
export function owned(kind) {
  const base = kind === 'mesa' ? ['madeira'] : ['osso'];
  const bought = store.get('bought', {})[kind] || [];
  return [...new Set([...base, ...career().unlocked[kind], ...bought])];
}
export function addOwned(kind, id) {
  const b = store.get('bought', {});
  b[kind] = [...new Set([...(b[kind] || []), id])];
  store.set('bought', b);
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
  const stage = h('div', { id: 'stage', class: 'enter' });
  app.prepend(stage);
  sfx.uiSwipe();
  current = screens[name](stage, params) || null;
}
