import { h, modal } from '../ui/dom.js';
import { tileEl } from '../ui/tileView.js';
import { makeTile } from '../core/tiles.js';
import { tableTexture } from '../ui/art.js';
import { sfx } from '../ui/audio.js';
import { go, settings, saveSettings, owned, addOwned, wallet, setWallet, money } from '../app.js';
import { CAMPEONATOS, MESAS_VISUAL, DOMINOS_VISUAL } from '../classic/cast.js';
import { iconBtn, walletChip } from './home.js';
import { buyRemoveAds, adsRemoved } from '../ads.js';

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

function campOf(kind, id) {
  return CAMPEONATOS.find((x) => x.prize[kind] === id);
}

// Loja: compra mesas e dominós com o dinheiro do jogo; os de campeonato também saem vencendo.
export function lookScreen(stage) {
  const render = () => {
    stage.innerHTML = '';
    stage.append(
      h(
        'div',
        { class: 'topbar' },
        iconBtn('back', 'Voltar', () => go('home')),
        h('div', { class: 'grow' }, h('div', { class: 'eyebrow' }, 'Loja do boteco'), h('div', { class: 'title-sm' }, 'Mesas e dominós')),
        walletChip(),
      ),
    );
    const wrap = h('div', { class: 'look' });
    const noAds = h('button', { class: `no-ads ${adsRemoved() ? 'done' : ''}`, disabled: adsRemoved() },
      h('div', {}, h('b', {}, adsRemoved() ? 'Sem anúncios' : 'Tirar os anúncios'), h('small', {}, adsRemoved() ? 'Obrigado pelo apoio!' : 'Compra única. Os vídeos premiados continuam, se você quiser.')),
      h('span', { class: 'na-price' }, adsRemoved() ? 'Ativo' : 'R$ 9,90'));
    noAds.addEventListener('click', async () => {
      const r = await buyRemoveAds();
      if (r.ok) return render();
      if (r.reason === 'loja') {
        const m = modal([h('h2', {}, 'Na versão da loja'), h('p', {}, 'A compra para tirar os anúncios fica disponível quando o jogo estiver na Play Store.'), h('div', { class: 'actions' }, h('button', { class: 'btn amber', onClick: () => m.close() }, 'Beleza'))]);
      }
    });
    wrap.append(noAds);
    for (const kind of ['mesa', 'domino']) {
      const list = kind === 'mesa' ? MESAS_VISUAL : DOMINOS_VISUAL;
      const have = owned(kind);
      wrap.append(h('h3', { class: 'look-h' }, kind === 'mesa' ? 'Mesa' : 'Dominó'));
      const grid = h('div', { class: 'swatches' });
      for (const it of list) {
        const mine = have.includes(it.id);
        let prev;
        if (kind === 'mesa') {
          const url = texUrl(it.id);
          prev = h('div', { class: 'sw-prev', 'data-mesa': it.id, style: url ? { backgroundImage: `url(${url})` } : {} });
          prev.append(tileEl(makeTile(2, 5), { top: 5, bot: 2, u: 16 }), tileEl(makeTile(4, 4), { u: 16 }));
        } else {
          prev = h('div', { class: 'sw-prev dom', 'data-domino': it.id });
          prev.append(tileEl(makeTile(6, 6), { u: 18 }), tileEl(makeTile(1, 3), { top: 1, bot: 3, u: 18 }), tileEl(makeTile(2, 5), { top: 5, bot: 2, u: 18 }));
        }
        const c = campOf(kind, it.id);
        const using = settings[kind] === it.id;
        let foot;
        if (mine) foot = h('div', { class: 'sw-desc' }, using ? 'Em uso' : it.desc);
        else if (it.price == null) foot = h('div', { class: 'sw-desc' }, c ? `Prêmio do ${c.short}` : 'Bloqueado');
        else foot = h('div', { class: 'sw-price' }, money(it.price), c ? h('small', {}, ` ou vença o ${c.short}`) : null);
        const b = h(
          'button',
          { class: `swatch ${using ? 'on' : ''} ${mine ? '' : 'locked'}`, 'aria-pressed': String(using) },
          prev,
          h('div', { class: 'sw-name' }, it.name),
          foot,
        );
        b.addEventListener('click', () => {
          if (mine) {
            settings[kind] = it.id;
            saveSettings();
            sfx.pick();
            return render();
          }
          if (it.price == null) return sfx.error();
          buy(kind, it);
        });
        grid.append(b);
      }
      wrap.append(grid);
    }
    stage.append(wrap);
  };

  function buy(kind, it) {
    const can = wallet() >= it.price;
    const m = modal([
      h('h2', {}, it.name),
      h('p', {}, it.desc),
      h('div', { class: 'big', style: { color: 'var(--amber-hi)' } }, money(it.price)),
      h('p', {}, `Na carteira: ${money(wallet())}`),
      h(
        'div',
        { class: 'actions' },
        h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Agora não'),
        h('button', {
          class: 'btn amber',
          disabled: !can,
          onClick: () => {
            setWallet(wallet() - it.price);
            addOwned(kind, it.id);
            settings[kind] = it.id;
            saveSettings();
            sfx.coins();
            m.close();
            render();
          },
        }, can ? 'Comprar e usar' : 'Falta dinheiro'),
      ),
    ]);
  }

  render();
  return null;
}
