import { h, modal, sleep, store, fmt, fmtMult, toast } from '../ui/dom.js';
import { BoardView, tileEl } from '../ui/tileView.js';
import { portrait, bottleIcon, simpatiaIcon, boxIcon } from '../ui/art.js';
import { sfx, haptic } from '../ui/audio.js';
import { confetti, shake, floatAtEl, burstEl, pop } from '../ui/fx.js';
import { go } from '../app.js';
import { iconBtn, rulesModal } from './home.js';
import { bumpUid, makeRng } from '../core/tiles.js';
import {
  JOGOS, JOGO_BY_ID, PARCEIRO_BY_ID, CONSUMIVEL_BY_ID, MESAS, MODS, jogoValues, detectJogo,
} from '../virada/data.js';
import {
  newRun, startMesa, playableSides, anyPlayable, placePending, undoPending, discard, passHand,
  scorePlay, commitPlay, cashOut, advance, makeShop, rerollShop, newParceiro, sellValue,
  caixinhaOptions, useConsumivel, mesaTarget, donoOf, botecoName, MAX_PARCEIROS, MAX_CONSUMIVEIS,
} from '../virada/run.js';

const STATS_DEF = { classicWins: 0, classicPlayed: 0, viradaBest: 0, viradaWins: 0 };

function save(run) {
  const { mesa, ...rest } = run;
  store.set('run', rest);
}

function loadRun() {
  const r = store.get('run', null);
  if (!r || r.v !== 1) return null;
  let max = 0;
  for (const t of r.bag) max = Math.max(max, t.uid);
  bumpUid(max);
  if (r.phase === 'mesa') r.phase = 'map';
  if (r.phase === 'shop' && !r.shop) r.shop = makeShop(r);
  return r;
}

function recordBest(run) {
  const stats = store.get('stats', STATS_DEF);
  stats.viradaBest = Math.max(stats.viradaBest || 0, run.stats.best || 0);
  store.set('stats', stats);
}

// ---------- componentes ----------
function parceiroCard(p, { onClick } = {}) {
  const def = PARCEIRO_BY_ID[p.id];
  const el = h(
    'button',
    { class: `pcard rar-${def.rarity}`, style: { '--pbg': def.face.bg }, 'aria-label': `${def.name}: ${def.desc}`, onClick },
    h('span', { html: portrait(def.face, 52) }),
    h('span', { class: 'pname' }, def.name),
  );
  if (def.label && p.state) el.append(h('span', { class: 'plabel' }, def.label(p).replace(' Mult', '')));
  return el;
}

function consumIcon(c, size = 40) {
  if (c.kind === 'bebida') return bottleIcon(c.color, size);
  return simpatiaIcon(c.id, size);
}

function consumCard(id, { onClick } = {}) {
  const c = CONSUMIVEL_BY_ID[id];
  return h('button', { class: 'ccard', 'aria-label': `${c.name}: ${c.desc}`, onClick, html: consumIcon(c, 40) });
}

function rarLabel(r) {
  return h('span', { class: `rar ${r}` }, r);
}

export function viradaScreen(stage, params = {}) {
  let run = (params.resume && loadRun()) || null;
  let dead = false;
  let view = null; // limpeza da sub-tela

  if (!run) {
    run = newRun();
    save(run);
  }

  const rng = makeRng((run.seed ^ 0x9e3779b9) >>> 0);

  function show(phase) {
    if (view && view.destroy) view.destroy();
    stage.innerHTML = '';
    run.phase = phase;
    if (phase !== 'mesa') save(run);
    if (phase === 'map') view = mapView();
    else if (phase === 'mesa') view = mesaView();
    else if (phase === 'shop') view = shopView();
    else if (phase === 'won') view = endView(true);
    else if (phase === 'over') view = endView(false);
  }

  // ---------- barra de parceiros/consumíveis ----------
  function crewBar(onChange) {
    const wrap = h('div', { class: 'crew' });
    const render = () => {
      wrap.innerHTML = '';
      const slots = h('div', { class: 'slots' });
      run.parceiros.forEach((p, i) => slots.append(parceiroCard(p, { onClick: () => parceiroDetail(i, render) })));
      for (let i = run.parceiros.length; i < MAX_PARCEIROS; i++) slots.append(h('div', { class: 'pcard empty', 'aria-hidden': 'true' }));
      const cons = h('div', { class: 'cons' });
      run.consumiveis.forEach((id, i) => cons.append(consumCard(id, { onClick: () => consumDetail(i, render) })));
      for (let i = run.consumiveis.length; i < MAX_CONSUMIVEIS; i++) cons.append(h('div', { class: 'ccard empty', 'aria-hidden': 'true' }));
      wrap.append(slots, cons);
      onChange && onChange();
    };
    render();
    wrap.render = render;
    return wrap;
  }

  function parceiroDetail(i, rerender) {
    const p = run.parceiros[i];
    const def = PARCEIRO_BY_ID[p.id];
    const m = modal([
      h(
        'div',
        { class: 'detail-head' },
        parceiroCard(p),
        h('div', {}, rarLabel(def.rarity), h('h2', { style: { marginTop: '6px' } }, def.name)),
      ),
      h('p', { style: { fontSize: '17px' } }, def.desc),
      def.label ? h('p', { style: { color: 'var(--amber-hi)' } }, `Agora: ${def.label(p)}`) : null,
      h(
        'div',
        { class: 'actions' },
        h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Fechar'),
        h(
          'button',
          {
            class: 'btn chili',
            disabled: run.phase === 'mesa' && run.mesa && run.mesa.busy,
            onClick: () => {
              run.money += sellValue(p);
              run.parceiros.splice(i, 1);
              sfx.coin();
              m.close();
              rerender();
              refreshMoney();
              if (run.phase !== 'mesa') save(run);
            },
          },
          `Vender por $${sellValue(p)}`,
        ),
      ),
    ]);
  }

  function consumDetail(i, rerender) {
    const id = run.consumiveis[i];
    const c = CONSUMIVEL_BY_ID[id];
    const busy = run.mesa && run.mesa.busy;
    const useIt = () => {
      if (c.pick > 0) {
        m.close();
        bagPicker(c.pick, c.name, (picked) => {
          if (!picked.length) return;
          const r = useConsumivel(run, i, picked);
          sfx.register();
          toast(r.msg || c.name);
          rerender();
          afterBagChange();
        });
        return;
      }
      const r = useConsumivel(run, i);
      sfx.register();
      toast(r.msg);
      m.close();
      rerender();
      refreshMoney();
      afterBagChange();
    };
    const m = modal([
      h('div', { class: 'detail-head' }, h('div', { class: 'ccard', html: consumIcon(c, 44) }), h('div', {}, h('span', { class: 'rar' }, c.kind === 'bebida' ? 'bebida' : 'simpatia'), h('h2', { style: { marginTop: '6px' } }, c.name))),
      h('p', { style: { fontSize: '17px' } }, c.desc),
      c.kind === 'bebida' ? h('p', { style: { color: 'var(--muted)' } }, levelLine(c.jogo)) : null,
      h(
        'div',
        { class: 'actions' },
        h('button', { class: 'btn ghost', onClick: () => { run.money += Math.floor(c.cost / 2); run.consumiveis.splice(i, 1); sfx.coin(); m.close(); rerender(); refreshMoney(); } }, `Vender $${Math.floor(c.cost / 2)}`),
        h('button', { class: 'btn amber', disabled: busy, onClick: useIt }, 'Usar'),
      ),
    ]);
  }

  function levelLine(jogoId) {
    const lv = run.levels[jogoId];
    const [c0, m0] = jogoValues(jogoId, lv);
    const [c1, m1] = jogoValues(jogoId, lv + 1);
    return `Nível ${lv}: ${c0} × ${m0}  →  Nível ${lv + 1}: ${c1} × ${m1}`;
  }

  let afterBagChange = () => {};
  let refreshMoney = () => {};

  function bagPicker(max, title, onDone) {
    const sel = new Set();
    const tiles = [...run.bag].sort((a, b) => a.a - b.a || a.b - b.b);
    const grid = h('div', { class: 'bag-grid' });
    const okBtn = h('button', { class: 'btn amber', disabled: true }, 'Escolher');
    tiles.forEach((t) => {
      const el = tileEl(t, { u: 22 });
      el.setAttribute('role', 'button');
      el.setAttribute('tabindex', '0');
      const toggle = () => {
        if (sel.has(t)) sel.delete(t);
        else if (sel.size < max) sel.add(t);
        else return sfx.error();
        el.classList.toggle('sel', sel.has(t));
        okBtn.disabled = sel.size === 0;
        okBtn.textContent = sel.size ? `Escolher ${sel.size}` : 'Escolher';
        sfx.pick();
      };
      el.addEventListener('click', toggle);
      el.addEventListener('keydown', (e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggle()));
      grid.append(el);
    });
    const m = modal([
      h('h2', {}, title),
      h('p', {}, `Escolha até ${max} pedra${max > 1 ? 's' : ''} do seu saco (${run.bag.length} pedras).`),
      grid,
      h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Cancelar'), okBtn),
    ]);
    okBtn.addEventListener('click', () => {
      m.close();
      onDone([...sel]);
    });
  }

  function bagModal() {
    const tiles = [...run.bag].sort((a, b) => a.a - b.a || a.b - b.b);
    const special = tiles.filter((t) => t.mod);
    modal([
      h('h2', {}, 'Seu saco'),
      h('p', {}, `${run.bag.length} pedras${special.length ? `, ${special.length} benzidas` : ''}.`),
      h('div', { class: 'bag-grid' }, tiles.map((t) => tileEl(t, { u: 20 }))),
      h('h3', {}, 'Pedras benzidas'),
      h('ul', {}, Object.entries(MODS).map(([, m]) => h('li', {}, h('b', {}, m.name), ': ', m.desc))),
      h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: (e) => e.target.closest('.modal-back').click() }, 'Fechar')),
    ]);
  }

  function levelsModal() {
    const grid = h('div', { class: 'levels' });
    for (const j of JOGOS) {
      const [c, m] = jogoValues(j.id, run.levels[j.id]);
      grid.append(
        h('div', {}, h('b', {}, j.name), h('div', { style: { fontSize: '12px', color: 'var(--muted)' } }, j.desc)),
        h('span', { class: 'lv' }, `nv ${run.levels[j.id]}`),
        h('span', { class: 'vals' }, `${c} × ${m}`),
      );
    }
    modal([
      h('h2', {}, 'Jogos'),
      h('p', {}, 'Pontos-base × Mult de cada jogo. As pedras jogadas somam seus pontos por cima.'),
      grid,
      h('p', { style: { marginTop: '12px' } }, h('b', {}, 'Lá e Lô: '), 'se as duas pontas ficarem com o mesmo número depois da jogada, ×1,5 Mult.'),
      h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: (e) => e.target.closest('.modal-back').click() }, 'Fechar')),
    ]);
  }

  function topBar(title, sub) {
    const money = h('div', { class: 'money', 'aria-label': 'Dinheiro' }, `$${run.money}`);
    refreshMoney = () => {
      money.textContent = `$${run.money}`;
    };
    return h(
      'div',
      { class: 'topbar v-top' },
      iconBtn('back', 'Voltar ao início', () => {
        if (run.phase !== 'mesa') {
          save(run);
          go('home');
          return;
        }
        const m = modal([
          h('h2', {}, 'Sair da mesa?'),
          h('p', {}, 'Sua Virada fica salva no começo desta mesa.'),
          h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Ficar'), h('button', { class: 'btn chili', onClick: () => { m.close(); run.phase = 'map'; run.mesa = null; save(run); go('home'); } }, 'Sair')),
        ]);
      }),
      h('div', { class: 'grow' }, h('div', { class: 'eyebrow' }, sub), h('div', { class: 'title-sm' }, title)),
      money,
    );
  }

  // ---------- mapa ----------
  function mapView() {
    const dono = donoOf(run);
    stage.append(topBar(botecoName(run), `Boteco ${run.ante} de 8`));
    const list = h('div', { class: 'map' });
    list.append(h('div', { class: 'map-head' }, h('div', { class: 'ante' }, `BOTECO ${run.ante} DE 8`), h('h2', {}, botecoName(run))));
    MESAS.forEach((ms, i) => {
      const isBoss = i === 2;
      const cls = `mesa-card ${isBoss ? 'boss' : ''} ${i < run.mesaIdx ? 'done' : ''} ${i === run.mesaIdx ? 'now' : ''}`;
      list.append(
        h(
          'div',
          { class: cls },
          h('div', { class: 'num' }, i < run.mesaIdx ? '✓' : String(i + 1)),
          h('div', {}, h('div', { class: 'nm' }, isBoss ? dono.name : ms.name), h('div', { class: 'ds' }, isBoss ? dono.desc : i === 0 ? 'Mesa tranquila para esquentar.' : 'A meta sobe pela metade.')),
          h('div', { class: 'meta' }, h('b', {}, fmt(mesaTarget(run, run.ante, i))), h('small', {}, `+$${ms.reward}`)),
        ),
      );
    });
    const crew = crewBar();
    const actions = h(
      'div',
      { style: { display: 'grid', gridTemplateColumns: 'auto auto 1fr', gap: '8px', paddingBottom: 'max(12px, env(safe-area-inset-bottom, 0px))' } },
      h('button', { class: 'btn ghost', onClick: bagModal }, 'Saco'),
      h('button', { class: 'btn ghost', onClick: levelsModal }, 'Jogos'),
      h('button', { class: 'btn amber', onClick: () => { sfx.shuffle(); startMesa(run); show('mesa'); } }, run.mesaIdx === 2 ? 'Enfrentar o dono' : 'Sentar à mesa'),
    );
    stage.append(list, crew, actions);
    return null;
  }

  // ---------- mesa ----------
  function mesaView() {
    const mesa = run.mesa;
    let mode = 'play'; // play | trocar | scoring
    let selected = null;
    const marked = new Set();
    mesa.busy = false;

    const title = mesa.boss ? mesa.boss.name : MESAS[run.mesaIdx].name;
    stage.append(topBar(title, `Boteco ${run.ante} · ${botecoName(run)}`));

    const scoreEl = h('div', { class: 'score' }, fmt(mesa.score));
    const barFill = h('i');
    const goal = h(
      'div',
      { class: 'goal' },
      h('div', {}, h('span', { class: 'lbl' }, 'Placar'), scoreEl),
      h('div', { class: 'meta-t' }, h('small', {}, 'Meta'), fmt(mesa.target)),
      h('div', { class: 'bar' }, barFill),
    );
    const handsB = h('b', {}, String(mesa.handsLeft));
    const discB = h('b', {}, String(mesa.discardsLeft));
    const counters = h('div', { class: 'counters' }, h('div', { class: 'counter jog' }, h('span', {}, 'Jogadas'), handsB), h('div', { class: 'counter tro' }, h('span', {}, 'Trocas'), discB));
    stage.append(h('div', { class: 'v-hud' }, goal, counters));
    if (mesa.boss) stage.append(h('div', { class: 'boss-chip' }, h('b', {}, mesa.boss.name), mesa.boss.desc));

    const crew = crewBar();
    stage.append(crew);

    const boardView = new BoardView();
    boardView.board = mesa.board;
    const table = h('div', { class: 'v-table' }, boardView.el);
    stage.append(table);
    boardView.el.addEventListener('click', () => selected && deselect());

    const jogoB = h('b', {}, 'Escolha suas pedras');
    const jogoS = h('span', {}, `Até ${mesa.maxPerPlay} pedras por jogada`);
    const chipsBox = h('div', { class: 'pbox chips' }, '0');
    const multBox = h('div', { class: 'pbox mult' }, '0');
    const preview = h('div', { class: 'preview' }, h('div', { class: 'jogo' }, jogoB, jogoS), chipsBox, h('span', { class: 'x' }, '×'), multBox);
    stage.append(preview);

    const note = h('div', { class: 'stuck-note', role: 'status', 'aria-live': 'polite' });
    const handEl = h('div', { class: 'hand' });
    stage.append(note, handEl);

    const btnLeft = h('button', { class: 'btn chili' }, 'Trocar');
    const btnMid = h('button', { class: 'btn ghost', 'aria-label': 'Desfazer', html: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/></svg>' });
    const btnRight = h('button', { class: 'btn amber' }, 'Jogar');
    stage.append(h('div', { class: 'v-actions' }, btnLeft, btnMid, btnRight), h('div', { class: 'bottom-pad' }));

    btnLeft.addEventListener('click', onLeft);
    btnMid.addEventListener('click', onUndo);
    btnRight.addEventListener('click', onRight);

    afterBagChange = () => {
      renderHand();
      boardView.rebuild(mesa.board, new Set(mesa.pending.map((p) => p.tile.uid)));
      updatePreview();
    };

    function handU(n) {
      const w = handEl.clientWidth || 340;
      return Math.max(26, Math.min(44, Math.floor((w - 6 * (n - 1)) / n)));
    }

    function renderHand({ enterUids = null } = {}) {
      handEl.innerHTML = '';
      const u = handU(Math.max(mesa.hand.length, 6));
      mesa.hand.forEach((t, i) => {
        const el = tileEl(t, { u });
        el.setAttribute('role', 'button');
        el.setAttribute('tabindex', '0');
        el.setAttribute('aria-label', `Pedra ${t.a} e ${t.b}${t.mod ? ', ' + MODS[t.mod].name : ''}`);
        if (mode === 'play') {
          const can = playableSides(mesa, t).length > 0;
          el.classList.add(can ? 'can' : 'cannot');
          if (selected === t) el.classList.add('sel');
        } else if (mode === 'trocar' && marked.has(t)) el.classList.add('mark');
        if (enterUids && enterUids.has(t.uid)) {
          el.classList.add('enter');
          el.style.animationDelay = `${i * 40}ms`;
        }
        const act = () => onTile(t, el);
        el.addEventListener('click', (e) => {
          e.stopPropagation();
          act();
        });
        el.addEventListener('keydown', (e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), act()));
        handEl.append(el);
      });
      handEl.classList.toggle('locked', mode === 'scoring');
      updateButtons();
    }

    function updateButtons() {
      const stuck = mode === 'play' && !mesa.pending.length && !anyPlayable(mesa);
      if (mode === 'trocar') {
        btnLeft.textContent = 'Cancelar';
        btnLeft.className = 'btn ghost';
        btnRight.textContent = marked.size ? `Trocar ${marked.size}` : 'Trocar';
        btnRight.className = 'btn chili';
        btnRight.disabled = !marked.size;
        btnMid.disabled = true;
        btnLeft.disabled = false;
        note.textContent = 'Marque até 5 pedras para trocar.';
        return;
      }
      btnLeft.textContent = 'Trocar';
      btnLeft.className = 'btn chili';
      btnLeft.disabled = mode !== 'play' || mesa.discardsLeft <= 0 || !mesa.hand.length;
      btnMid.disabled = mode !== 'play' || !mesa.pending.length;
      if (stuck && mesa.discardsLeft <= 0) {
        btnRight.textContent = 'Passar a vez';
        btnRight.className = 'btn blue';
        btnRight.disabled = mode !== 'play';
        note.textContent = 'Nenhuma pedra encaixa. Passar gasta 1 jogada e troca a mão.';
      } else {
        btnRight.textContent = 'Jogar';
        btnRight.className = 'btn amber';
        btnRight.disabled = mode !== 'play' || !mesa.pending.length;
        if (stuck) note.textContent = 'Nenhuma pedra encaixa. Troque algumas.';
        else if (mesa.pending.length >= mesa.maxPerPlay) note.textContent = `Máximo de ${mesa.maxPerPlay} pedras. Toque em Jogar.`;
        else note.textContent = '';
      }
    }

    function updatePreview() {
      if (!mesa.pending.length) {
        jogoB.textContent = mesa.board.empty ? 'Sua saída' : 'Escolha suas pedras';
        jogoS.textContent = mesa.board.empty ? 'A primeira pedra entra em qualquer lugar' : `Pontas ${mesa.board.ends.L} e ${mesa.board.ends.R} · até ${mesa.maxPerPlay} pedras`;
        chipsBox.textContent = '0';
        multBox.textContent = '0';
        preview.classList.remove('hot');
        return;
      }
      const r = scorePlay(run, mesa, null, { preview: true });
      const j = JOGO_BY_ID[r.jogoId];
      jogoB.textContent = `${j.name}`;
      jogoS.innerHTML = '';
      jogoS.append(`nível ${r.level}`);
      if (r.laelo) jogoS.append(h('span', { class: 'tag' }, 'Lá e Lô'));
      const [c, m] = jogoValues(r.jogoId, r.level);
      chipsBox.textContent = fmt(c);
      multBox.textContent = fmtMult(mesa.boss && (mesa.boss.id === 'ressaca') ? 1 : m);
      preview.classList.toggle('hot', mesa.score + r.total >= mesa.target);
      pop(chipsBox);
      pop(multBox);
    }

    function setCounters() {
      handsB.textContent = String(mesa.handsLeft);
      discB.textContent = String(mesa.discardsLeft);
      scoreEl.textContent = fmt(mesa.score);
      barFill.style.width = `${Math.min(100, (mesa.score / mesa.target) * 100)}%`;
      refreshMoney();
    }

    async function onTile(t, el) {
      if (mode === 'scoring' || mesa.busy) return;
      if (mode === 'trocar') {
        if (marked.has(t)) marked.delete(t);
        else if (marked.size < 5) marked.add(t);
        else return sfx.error();
        sfx.pick();
        renderHand();
        return;
      }
      const sides = playableSides(mesa, t);
      if (!sides.length) {
        sfx.error();
        haptic(30);
        el.animate([{ transform: 'translateX(0)' }, { transform: 'translateX(-5px)' }, { transform: 'translateX(5px)' }, { transform: 'translateX(0)' }], { duration: 220 });
        note.textContent = mesa.pending.length >= mesa.maxPerPlay ? `Máximo de ${mesa.maxPerPlay} pedras por jogada.` : 'Essa não encaixa em nenhuma ponta.';
        return;
      }
      if (sides.length === 1) return place(t, sides[0], el);
      selected = t;
      sfx.pick();
      renderHand();
      note.textContent = 'Escolha a ponta.';
      boardView.showTargets(mesa.board, sides, (side) => {
        const tEl = handEl.querySelector(`[data-uid="${t.uid}"]`);
        place(t, side, tEl);
      });
    }

    function deselect() {
      selected = null;
      boardView.hideTargets();
      boardView.fit();
      renderHand();
    }

    async function place(t, side, el) {
      const rect = el ? el.getBoundingClientRect() : null;
      selected = null;
      boardView.hideTargets();
      mesa.busy = true;
      const rec = placePending(mesa, t, side);
      renderHand();
      await boardView.flyIn(rec, rect, { pending: true });
      mesa.busy = false;
      updatePreview();
      updateButtons();
    }

    function onUndo() {
      if (mode !== 'play' || mesa.busy) return;
      const last = undoPending(mesa);
      if (!last) return;
      boardView.removeTile(last.tile);
      boardView.fit();
      sfx.drop();
      renderHand();
      updatePreview();
    }

    function onLeft() {
      if (mesa.busy) return;
      if (mode === 'trocar') {
        mode = 'play';
        marked.clear();
        renderHand();
        return;
      }
      if (mesa.discardsLeft <= 0) return;
      while (mesa.pending.length) {
        const l = undoPending(mesa);
        boardView.removeTile(l.tile);
      }
      boardView.fit();
      updatePreview();
      mode = 'trocar';
      selected = null;
      boardView.hideTargets();
      renderHand();
    }

    async function onRight() {
      if (mesa.busy) return;
      if (mode === 'trocar') {
        if (!marked.size) return;
        const els = [...marked].map((t) => handEl.querySelector(`[data-uid="${t.uid}"]`));
        mesa.busy = true;
        await Promise.all(els.map((el, i) => el && el.animate([{ transform: el.style.transform || 'none', opacity: 1 }, { transform: 'translateY(-90px) rotate(20deg)', opacity: 0 }], { duration: 260, delay: i * 40, easing: 'ease-in', fill: 'forwards' }).finished));
        const drawn = discard(mesa, [...marked]);
        marked.clear();
        mode = 'play';
        sfx.shuffle();
        setCounters();
        renderHand({ enterUids: new Set(drawn.map((t) => t.uid)) });
        mesa.busy = false;
        updatePreview();
        return;
      }
      if (!mesa.pending.length) {
        if (!anyPlayable(mesa) && mesa.discardsLeft <= 0) {
          const drawn = passHand(mesa);
          sfx.pass();
          setCounters();
          renderHand({ enterUids: new Set(drawn.map((t) => t.uid)) });
          if (mesa.handsLeft <= 0) return endMesa(false);
        }
        return;
      }
      await scoreSequence();
    }

    async function scoreSequence() {
      mode = 'scoring';
      mesa.busy = true;
      renderHand();
      const result = scorePlay(run, mesa, rng);
      const j = JOGO_BY_ID[result.jogoId];
      jogoB.textContent = j.name;
      let [c0, m0] = jogoValues(result.jogoId, result.level);
      if (mesa.boss && mesa.boss.id === 'ressaca') m0 = 1;
      chipsBox.textContent = fmt(c0);
      multBox.textContent = fmtMult(m0);
      pop(chipsBox);
      pop(multBox);
      sfx.mult(0);
      await sleep(320);

      const tileEls = result.played.map((t) => boardView.items.get(t.uid));
      const crewCards = crew.querySelectorAll('.slots .pcard:not(.empty)');
      let step = 0;
      let delay = 300;
      for (const s of result.steps) {
        if (dead) return;
        const target = s.src.kind === 'tile' ? tileEls[s.src.i] : s.src.kind === 'parceiro' ? crewCards[s.src.i] : preview;
        if (s.src.kind === 'parceiro') pop(crewCards[s.src.i], 'fire');
        if (s.src.kind === 'tile' && target) pop(target, 'landed');
        if (s.debuff) {
          floatAtEl(target, s.msg, 'bad');
          sfx.error();
        } else if (s.chips) {
          floatAtEl(target, `+${fmt(s.chips)}`, '');
          sfx.chip(step);
          chipsBox.textContent = fmt(s.chipsNow);
          pop(chipsBox);
        } else if (s.mult) {
          floatAtEl(target, `+${fmtMult(s.mult)} Mult`, 'mult');
          sfx.mult(step);
          multBox.textContent = fmtMult(s.multNow);
          pop(multBox);
        } else if (s.xmult) {
          floatAtEl(target, s.tag ? `${s.tag} ×${fmtMult(s.xmult)}` : `×${fmtMult(s.xmult)} Mult`, 'xmult');
          sfx.xmult();
          multBox.textContent = fmtMult(s.multNow);
          pop(multBox);
          shake(0.4);
        } else if (s.money) {
          floatAtEl(target, `+$${s.money}`, 'money');
          sfx.coin();
        } else if (s.msg) {
          floatAtEl(target, s.msg, 'bad');
        }
        if (s.money && (s.chips || s.mult)) sfx.coin();
        step++;
        await sleep(delay);
        delay = Math.max(130, delay * 0.9);
      }
      await sleep(180);
      // total
      const burst = h('div', { class: `total-burst ${result.total >= mesa.target - mesa.score ? 'fire' : ''}` }, fmt(result.total));
      table.append(burst);
      setTimeout(() => burst.remove(), 1300);
      sfx.total();
      haptic(25);
      const ratio = result.total / Math.max(1, mesa.target);
      shake(Math.min(2.5, 0.5 + ratio * 2));
      burstEl(burst, { n: 22 + Math.min(40, Math.floor(ratio * 40)), colors: ['#ffd27a', '#f2a93b', '#fff1c9', '#e2483b'], speed: 5, size: 3, life: 800 });

      const from = mesa.score;
      const res = commitPlay(run, mesa, result);
      animateNumber(scoreEl, from, mesa.score, 600);
      barFill.style.width = `${Math.min(100, (mesa.score / mesa.target) * 100)}%`;
      handsB.textContent = String(mesa.handsLeft);
      refreshMoney();
      crew.render();
      await sleep(750);
      if (dead) return;

      for (const t of result.broken) {
        const el = boardView.items.get(t.uid);
        burstEl(el, { n: 18, colors: ['#cfe8f5', '#ffffff', '#8fc3de'], speed: 4, size: 2.2, life: 600, shape: 'dot' });
        if (el) el.style.opacity = '0.25';
        toast('O vidro quebrou!');
      }
      boardView.setPending(false);
      mode = 'play';
      mesa.busy = false;
      chipsBox.textContent = '0';
      multBox.textContent = '0';
      if (res.won) return endMesa(true);
      if (res.lost) return endMesa(false);
      renderHand({ enterUids: new Set(res.drawn.map((t) => t.uid)) });
      updatePreview();
      if (res.drawn.length) sfx.shuffle();
    }

    function endMesa(won) {
      mode = 'scoring';
      renderHand();
      if (!won) {
        recordBest(run);
        sfx.lose();
        setTimeout(() => show('over'), 700);
        return;
      }
      sfx.win();
      confetti(70);
      const cash = cashOut(run);
      const lines = h('div', { class: 'cash-lines' }, cash.lines.map((l) => h('div', {}, h('span', {}, l.label), h('b', {}, `+$${l.value}`))));
      const m = modal(
        [
          h('div', { class: 'eyebrow' }, `${fmt(mesa.score)} de ${fmt(mesa.target)}`),
          h('h2', {}, mesa.boss ? `${mesa.boss.name} pagou a conta!` : 'Mesa virada!'),
          lines,
          h('div', { class: 'big', style: { color: 'var(--amber-hi)' } }, `$${cash.total}`),
          h('div', { class: 'actions' }, h('button', { class: 'btn amber wide', onClick: () => { m.close(); sfx.register(); advance(run, cash); recordBest(run); show(run.phase); } }, 'Recolher e ir ao balcão')),
        ],
        { dismissable: false, cls: 'result' },
      );
    }

    boardView.rebuild(mesa.board);
    setCounters();
    renderHand({ enterUids: new Set(mesa.hand.map((t) => t.uid)) });
    updatePreview();

    return {
      destroy() {
        boardView.destroy();
      },
    };
  }

  function animateNumber(el, from, to, ms) {
    const t0 = performance.now();
    const tick = (now) => {
      const k = Math.min(1, (now - t0) / ms);
      const e = 1 - Math.pow(1 - k, 3);
      el.textContent = fmt(from + (to - from) * e);
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  // ---------- balcão ----------
  function shopView() {
    stage.append(topBar(botecoName(run), run.mesaIdx === 2 ? 'Balcão · antes do dono' : `Balcão · antes da ${MESAS[run.mesaIdx].name}`));
    const wrap = h('div', { class: 'shop' });
    let renderShop = () => {};
    const crew = crewBar(() => renderShop());
    const rerollBtn = h('button', { class: 'btn ghost small' });
    const grid = h('div', { class: 'shop-grid' });

    renderShop = () => {
      grid.innerHTML = '';
      rerollBtn.textContent = `Trocar itens $${run.shop.rerollCost}`;
      rerollBtn.disabled = run.money < run.shop.rerollCost;
      run.shop.items.forEach((it) => grid.append(shopItem(it)));
      refreshMoney();
    };

    function shopItem(it) {
      let art, name, desc, kind;
      if (it.type === 'parceiro') {
        const def = PARCEIRO_BY_ID[it.id];
        art = parceiroCard({ id: it.id, state: def.init ? def.init() : {} });
        name = def.name;
        desc = def.desc;
        kind = h('span', { class: `rar ${def.rarity}` }, `parceiro ${def.rarity !== 'comum' ? '· ' + def.rarity : ''}`);
      } else if (it.type === 'consumivel') {
        const c = CONSUMIVEL_BY_ID[it.id];
        art = h('div', { class: 'ccard', html: consumIcon(c, 44) });
        name = c.name;
        desc = c.desc;
        kind = h('span', { class: 'ikind' }, c.kind);
      } else {
        art = h('div', { html: boxIcon(58) });
        name = 'Caixinha de Pedras';
        desc = 'Escolha 1 de 3 pedras benzidas para pôr no saco.';
        kind = h('span', { class: 'ikind' }, 'pacote');
      }
      const full =
        (it.type === 'parceiro' && run.parceiros.length >= MAX_PARCEIROS) ||
        (it.type === 'consumivel' && run.consumiveis.length >= MAX_CONSUMIVEIS);
      const buy = h('button', { class: 'btn amber small wide buy', disabled: it.sold || run.money < it.cost || full }, it.sold ? 'Vendido' : full ? 'Sem espaço' : `Comprar $${it.cost}`);
      buy.addEventListener('click', () => doBuy(it));
      return h('div', { class: `item ${it.sold ? 'sold' : ''}` }, h('div', { class: 'art' }, art), kind, h('div', {}, h('div', { class: 'iname' }, name), h('div', { class: 'idesc' }, desc)), buy);
    }

    function doBuy(it) {
      if (run.money < it.cost || it.sold) return;
      if (it.type === 'caixinha') {
        const opts = caixinhaOptions(run);
        const row = h('div', { class: 'bag-grid' });
        const m = modal([h('h2', {}, 'Caixinha de Pedras'), h('p', {}, 'Escolha uma para o seu saco.'), row, h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Deixar pra lá'))]);
        opts.forEach((t) => {
          const card = h('button', { class: 'item', style: { justifyItems: 'center', textAlign: 'center' } }, tileEl(t, { u: 30 }), h('div', { class: 'iname' }, `${t.a}·${t.b}`), h('div', { class: 'idesc' }, `${MODS[t.mod].name}: ${MODS[t.mod].desc}`));
          card.addEventListener('click', () => {
            run.money -= it.cost;
            it.sold = true;
            run.bag.push(t);
            sfx.register();
            toast(`${t.a}·${t.b} ${MODS[t.mod].name} foi pro saco`);
            m.close();
            renderShop();
            save(run);
          });
          row.append(card);
        });
        return;
      }
      run.money -= it.cost;
      it.sold = true;
      if (it.type === 'parceiro') run.parceiros.push(newParceiro(it.id));
      else run.consumiveis.push(it.id);
      sfx.register();
      haptic(15);
      crew.render();
      renderShop();
      save(run);
    }

    rerollBtn.addEventListener('click', () => {
      if (rerollShop(run)) {
        sfx.shuffle();
        renderShop();
        save(run);
      }
    });
    afterBagChange = () => save(run);

    wrap.append(
      h('div', { class: 'shop-head' }, h('div', {}, h('h2', {}, 'Balcão'), h('p', {}, 'Pegue parceiros, bebidas e simpatias.')), rerollBtn),
      grid,
    );
    const nextLbl = run.mesaIdx === 2 ? `Enfrentar ${donoOf(run).name}` : `Ir para ${MESAS[run.mesaIdx].name}`;
    const actions = h(
      'div',
      { style: { display: 'grid', gridTemplateColumns: 'auto auto 1fr', gap: '8px', paddingBottom: 'max(12px, env(safe-area-inset-bottom, 0px))' } },
      h('button', { class: 'btn ghost', onClick: bagModal }, 'Saco'),
      h('button', { class: 'btn ghost', onClick: levelsModal }, 'Jogos'),
      h('button', { class: 'btn amber', onClick: () => { run.shop = null; show('map'); } }, nextLbl),
    );
    stage.append(wrap, crew, actions);
    renderShop();
    return null;
  }

  // ---------- fim ----------
  function endView(won) {
    store.del('run');
    recordBest(run);
    if (won) {
      const stats = store.get('stats', STATS_DEF);
      stats.viradaWins = (stats.viradaWins || 0) + 1;
      store.set('stats', stats);
      confetti(160);
      sfx.win();
    }
    const box = h(
      'div',
      { class: 'map', style: { justifyContent: 'center', textAlign: 'center' } },
      h('div', { class: 'map-head' }, h('div', { class: 'ante' }, won ? 'VIRADA COMPLETA' : `PAROU NO BOTECO ${run.ante} DE 8`), h('h2', { style: { fontSize: '40px' } }, won ? 'Rei do Boteco!' : 'Fechou a conta.')),
      h('p', { style: { color: 'var(--muted)', lineHeight: 1.5 } }, won ? 'Você virou os 8 botecos. O dono te deve uma rodada.' : `${botecoName(run)}, ${run.mesaIdx === 2 ? donoOf(run).name : MESAS[run.mesaIdx].name}.`),
      h(
        'div',
        { class: 'levels', style: { margin: '10px auto', maxWidth: '300px', width: '100%' } },
        h('span', {}, 'Melhor jogada'), h('span'), h('b', { class: 'lv' }, fmt(run.stats.best)),
        h('span', {}, 'Mesas viradas'), h('span'), h('b', { class: 'lv' }, String(run.stats.mesas)),
        h('span', {}, 'Parceiros'), h('span'), h('b', { class: 'lv' }, String(run.parceiros.length)),
      ),
      h('div', { style: { display: 'flex', gap: '8px', justifyContent: 'center', flexWrap: 'wrap', minHeight: '76px' } }, run.parceiros.map((p) => parceiroCard(p))),
    );
    const actions = h(
      'div',
      { style: { display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: '8px', paddingBottom: 'max(12px, env(safe-area-inset-bottom, 0px))' } },
      h('button', { class: 'btn ghost', onClick: () => go('home') }, 'Início'),
      h('button', { class: 'btn amber', onClick: () => go('virada') }, 'Nova Virada'),
    );
    stage.append(topBar(won ? 'Vitória' : 'Fim da Virada', 'Virada'), box, actions);
    return null;
  }

  // primeira vez? mostra as regras
  if (!store.get('seenViradaRules', false)) {
    store.set('seenViradaRules', true);
    setTimeout(() => rulesModal('virada'), 400);
  }

  show(run.phase === 'shop' ? 'shop' : run.phase === 'won' || run.phase === 'over' ? run.phase : 'map');

  return {
    destroy() {
      dead = true;
      if (view && view.destroy) view.destroy();
      if (run && run.phase !== 'over' && run.phase !== 'won') {
        if (run.phase === 'mesa') run.phase = 'map';
        run.mesa = null;
        save(run);
      }
    },
  };
}
