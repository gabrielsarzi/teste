import { h } from '../ui/dom.js';
import { tileEl } from '../ui/tileView.js';
import { makeTile } from '../core/tiles.js';
import { tableTexture } from '../ui/art.js';
import { sfx } from '../ui/audio.js';
import { go, career, settings, saveSettings } from '../app.js';
import { CAMPEONATOS, MESAS_VISUAL, DOMINOS_VISUAL } from '../classic/cast.js';
import { iconBtn } from './home.js';

const tex = {};
function texUrl(id) {
  if (!(id in tex)) {
    try {
      tex[id] = tableTexture(id);
    } catch {
      tex[id] = null;
    }
  }
  return tex[id];
}

function unlockHint(kind, id) {
  const c = CAMPEONATOS.find((x) => x.prize[kind] === id);
  return c ? `Vença o ${c.short}` : '';
}

export function lookScreen(stage) {
  const car = career();
  const render = () => {
    stage.innerHTML = '';
    stage.append(
      h(
        'div',
        { class: 'topbar' },
        iconBtn('back', 'Voltar', () => go('home')),
        h('div', { class: 'grow' }, h('div', { class: 'eyebrow' }, 'Visual'), h('div', { class: 'title-sm' }, 'Mesas e dominós')),
      ),
    );
    const wrap = h('div', { class: 'look' });

    wrap.append(h('h3', { class: 'look-h' }, 'Mesa'));
    const mesas = h('div', { class: 'swatches' });
    for (const m of MESAS_VISUAL) {
      const open = car.unlocked.mesa.includes(m.id);
      const url = texUrl(m.id);
      const prev = h('div', { class: 'sw-prev', 'data-mesa': m.id, style: url ? { backgroundImage: `url(${url})` } : {} });
      prev.append(tileEl(makeTile(2, 5), { top: 5, bot: 2, u: 16 }), tileEl(makeTile(4, 4), { u: 16 }));
      const b = h(
        'button',
        { class: `swatch ${settings.mesa === m.id ? 'on' : ''} ${open ? '' : 'locked'}`, 'aria-pressed': String(settings.mesa === m.id), disabled: !open },
        prev,
        h('div', { class: 'sw-name' }, m.name),
        h('div', { class: 'sw-desc' }, open ? m.desc : `Bloqueada: ${unlockHint('mesa', m.id)}`),
      );
      b.addEventListener('click', () => {
        settings.mesa = m.id;
        saveSettings();
        sfx.pick();
        render();
      });
      mesas.append(b);
    }
    wrap.append(mesas);

    wrap.append(h('h3', { class: 'look-h' }, 'Dominó'));
    const doms = h('div', { class: 'swatches' });
    for (const d of DOMINOS_VISUAL) {
      const open = car.unlocked.domino.includes(d.id);
      const prev = h('div', { class: 'sw-prev dom', 'data-domino': d.id });
      prev.append(tileEl(makeTile(6, 6), { u: 18 }), tileEl(makeTile(1, 3), { top: 1, bot: 3, u: 18 }), tileEl(makeTile(2, 5), { top: 5, bot: 2, u: 18 }));
      const b = h(
        'button',
        { class: `swatch ${settings.domino === d.id ? 'on' : ''} ${open ? '' : 'locked'}`, 'aria-pressed': String(settings.domino === d.id), disabled: !open },
        prev,
        h('div', { class: 'sw-name' }, d.name),
        h('div', { class: 'sw-desc' }, open ? d.desc : `Bloqueado: ${unlockHint('domino', d.id)}`),
      );
      b.addEventListener('click', () => {
        settings.domino = d.id;
        saveSettings();
        sfx.pick();
        render();
      });
      doms.append(b);
    }
    wrap.append(doms);
    stage.append(wrap);
  };
  render();
  return null;
}
