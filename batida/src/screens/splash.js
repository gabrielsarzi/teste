// Abertura: a luminária acende e o "Batida!" cai na mesa como uma pedra.
// Só na primeira vez que o jogo abre no dia, e um toque pula.
import { h, store } from '../ui/dom.js';
import { sfx, haptic } from '../ui/audio.js';

const today = () => new Date().toDateString();

export function splash() {
  if (store.get('splashDay', '') === today()) return;
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  store.set('splashDay', today());
  const el = h(
    'div',
    { class: 'splash', 'aria-hidden': 'true' },
    h('div', { class: 'sp-lamp' }),
    h('div', { class: 'sp-glow' }),
    h('div', { class: 'sp-title' }, 'Batida', h('span', {}, '!')),
    h('div', { class: 'sp-sub' }, 'dominó de boteco'),
  );
  document.getElementById('app').append(el);
  let gone = false;
  const close = () => {
    if (gone) return;
    gone = true;
    el.classList.add('out');
    setTimeout(() => el.remove(), 400);
  };
  // o título bate na mesa
  setTimeout(() => {
    sfx.slam();
    haptic(30);
  }, 1050);
  setTimeout(close, 2300);
  el.addEventListener('pointerdown', close);
}
