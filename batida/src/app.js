// Estado global do app: configurações e navegação entre telas.
import { h, store, setSpeed } from './ui/dom.js';
import { setSound } from './ui/audio.js';

export const settings = Object.assign(
  { sound: true, speed: 'normal', buchaVale2: true, laeloVale2: false, comecaSena: true, formato: 'rodadas' },
  store.get('settings', {}),
);

export function applySettings() {
  setSound(settings.sound);
  setSpeed(settings.speed === 'rapido' ? 0.55 : 1);
}

export function saveSettings() {
  store.set('settings', settings);
  applySettings();
}

const screens = {};
let current = null;
export const registerScreen = (name, fn) => (screens[name] = fn);

export function go(name, params = {}) {
  if (current && current.destroy) current.destroy();
  const app = document.getElementById('app');
  app.querySelector('#stage')?.remove();
  app.querySelectorAll('.modal-back, .float-text, .toast').forEach((e) => e.remove());
  const stage = h('div', { id: 'stage' });
  app.prepend(stage);
  current = screens[name](stage, params) || null;
}
