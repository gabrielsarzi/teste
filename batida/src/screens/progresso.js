import { h } from '../ui/dom.js';
import { sfx } from '../ui/audio.js';
import { confetti } from '../ui/fx.js';
import { go, wallet, setWallet, money, rivals } from '../app.js';
import { CAST } from '../classic/cast.js';
import { MISSOES, CONQUISTAS, dailyMissions, achievements, getStats } from '../progress.js';
import { store } from '../ui/dom.js';
import { iconBtn, walletChip, seg } from './home.js';

const MODOS = { quick: 'Jogo rápido', career: 'Carreira', online: 'Online', desafio: 'Desafio do dia' };

export function progressoScreen(stage, params = {}) {
  let tab = params.tab || 'missoes';

  const render = () => {
    stage.innerHTML = '';
    stage.append(
      h('div', { class: 'topbar' }, iconBtn('back', 'Voltar', () => go('home')), h('div', { class: 'grow' }, h('div', { class: 'eyebrow' }, 'Seu boteco'), h('div', { class: 'title-sm' }, 'Missões e números')), walletChip()),
      h('div', { class: 'lobby-tabs' }, seg([['missoes', 'Missões'], ['conquistas', 'Conquistas'], ['numeros', 'Números']], tab, (v) => { tab = v; render(); })),
    );
    const body = h('div', { class: 'prog-body' });
    if (tab === 'missoes') missoes(body);
    else if (tab === 'conquistas') conquistas(body);
    else numeros(body);
    stage.append(body);
  };

  function claim(amount) {
    setWallet(wallet() + amount);
    sfx.coins();
    confetti(40);
  }

  function missoes(body) {
    const m = dailyMissions();
    body.append(h('p', { class: 'rank-help' }, 'Três missões novas todo dia. Cumpriu, recolhe o prêmio.'));
    for (const it of m.list) {
      const def = MISSOES.find((x) => x.id === it.id);
      if (!def) continue;
      const pct = Math.min(100, (it.prog / def.n) * 100);
      const btn = it.claimed
        ? h('span', { class: 'm-state ok' }, 'Recolhido')
        : it.done
          ? h('button', { class: 'btn amber small', onClick: () => { it.claimed = true; store.set('missoes', m); claim(def.r); render(); } }, `Recolher ${money(def.r)}`)
          : h('span', { class: 'm-state' }, money(def.r));
      body.append(
        h('div', { class: `mission ${it.done ? 'done' : ''}` },
          h('div', { class: 'm-main' }, h('b', {}, def.text), h('div', { class: 'm-bar' }, h('i', { style: { width: pct + '%' } })), h('small', {}, `${Math.min(it.prog, def.n)} de ${def.n}`)),
          btn),
      );
    }
  }

  function conquistas(body) {
    const got = achievements();
    const n = Object.keys(got).length;
    body.append(h('p', { class: 'rank-help' }, `${n} de ${CONQUISTAS.length} conquistas.`));
    const grid = h('div', { class: 'ach-grid' });
    for (const c of CONQUISTAS) {
      const g = got[c.id];
      const right = !g
        ? h('span', { class: 'm-state' }, money(c.r))
        : g.claimed
          ? h('span', { class: 'm-state ok' }, 'Feita')
          : h('button', { class: 'btn amber small', onClick: () => { g.claimed = true; store.set('conquistas', got); claim(c.r); render(); } }, `Recolher ${money(c.r)}`);
      grid.append(h('div', { class: `ach ${g ? 'got' : ''}` }, h('div', { class: 'ach-medal', 'aria-hidden': 'true' }, g ? '★' : '☆'), h('div', { class: 'm-main' }, h('b', {}, c.text), h('small', {}, c.desc)), right));
    }
    body.append(grid);
  }

  function numeros(body) {
    const s = getStats();
    const pct = (a, b) => (b ? `${Math.round((a / b) * 100)}%` : '–');
    const rows = [
      ['Partidas', s.partidas],
      ['Vitórias', `${s.vitorias} (${pct(s.vitorias, s.partidas)})`],
      ['Rodadas ganhas', `${s.rodadasGanhas} de ${s.rodadas}`],
      ['Batidas', s.batidas],
      ['Batidas de bucha', s.batidasBucha],
      ['Batidas de lá-e-lô', s.batidasLaelo],
      ['Jogos fechados ganhos', `${s.fechadosGanhos} de ${s.fechadosGanhos + s.fechadosPerdidos}`],
      ['Melhor sequência', `${s.melhorSequencia} vitória${s.melhorSequencia === 1 ? '' : 's'}`],
      ['Passes', s.passes],
      ['Pedras compradas', s.compradas],
      ['Gatos', s.gatos],
      ['Dinheiro ganho', money(s.ganhoTotal)],
    ];
    body.append(h('div', { class: 'stat-grid' }, rows.map(([k, v]) => h('div', { class: 'stat' }, h('small', {}, k), h('b', {}, String(v))))));
    const modos = Object.entries(s.porModo);
    if (modos.length) {
      body.append(h('h3', { class: 'look-h' }, 'Por modo'));
      body.append(h('div', { class: 'rank-list static' }, modos.map(([k, v]) => h('div', { class: 'rank-row' }, h('span', { class: 'pos' }, ''), h('span', { class: 'nm' }, MODOS[k] || k), h('span', { class: 'pts' }, `${v.v} de ${v.j}`)))));
    }
    const rv = Object.entries(rivals()).filter(([id]) => CAST[id] && !id.startsWith('on_')).sort((a, b) => b[1].w + b[1].l - (a[1].w + a[1].l));
    if (rv.length) {
      body.append(h('h3', { class: 'look-h' }, 'Contra cada um'));
      body.append(h('div', { class: 'rank-list static' }, rv.map(([id, r]) => h('div', { class: 'rank-row' }, h('span', { class: 'pos' }, r.w > r.l ? '▲' : r.w < r.l ? '▼' : '='), h('span', { class: 'nm' }, CAST[id].name), h('span', { class: 'pts' }, `${r.w} × ${r.l}`)))));
    }
  }

  render();
  return null;
}
