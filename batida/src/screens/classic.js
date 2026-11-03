import { h, modal, sleep, store } from '../ui/dom.js';
import { BoardView, tileEl, backEl } from '../ui/tileView.js';
import { ClassicMatch, teamOf } from '../classic/engine.js';
import { chooseMove } from '../classic/ai.js';
import { sfx, haptic } from '../ui/audio.js';
import { confetti, chalkDust, shake } from '../ui/fx.js';
import { settings, go } from '../app.js';
import { iconBtn, rulesModal } from './home.js';
import { isDouble, pipSum, BUCHA_NAMES } from '../core/tiles.js';

const NAMES = ['Você', 'Tonhão', 'Parceiro', 'Dona Rosa'];
const SHORT = ['Você', 'Tonhão', 'Parça', 'Rosa'];

function tally(n) {
  const groups = [];
  let left = n;
  while (left > 0) {
    const k = Math.min(5, left);
    left -= k;
    let d = '';
    for (let i = 0; i < Math.min(k, 4); i++) d += `M${4 + i * 7} 3 q1 9 -0.5 18 `;
    if (k === 5) d += 'M0 16 L30 6';
    groups.push(`<svg viewBox="0 0 32 24" aria-hidden="true" style="width:${k === 5 ? 32 : 4 + Math.min(k, 4) * 7}px"><path d="${d}" stroke="#eeece2" stroke-width="2.6" fill="none" stroke-linecap="round"/></svg>`);
  }
  return groups.join('') || '<span style="opacity:.4">–</span>';
}

export function classicScreen(stage) {
  let dead = false;
  const match = new ClassicMatch({
    buchaVale2: settings.buchaVale2,
    laeloVale2: settings.laeloVale2,
    comecaSena: settings.comecaSena,
    formato: settings.formato,
  });
  let round = null;
  let waiting = null; // resolve da jogada humana
  let selected = null;

  // ---------- montagem ----------
  const tallyUs = h('div', { class: 'tally' });
  const tallyThem = h('div', { class: 'tally' });
  const roundLbl = h('div', { class: 'round' });
  const lousa = h(
    'div',
    { class: 'lousa', role: 'status', 'aria-live': 'polite' },
    h('div', { class: 'team' }, h('div', { class: 'lbl' }, 'Nós'), tallyUs),
    roundLbl,
    h('div', { class: 'team' }, h('div', { class: 'lbl' }, 'Eles'), tallyThem),
  );
  const top = h(
    'div',
    { class: 'topbar' },
    iconBtn('back', 'Sair da mesa', () => confirmExit()),
    lousa,
    iconBtn('help', 'Regras', () => rulesModal('classico')),
  );

  const seats = [null];
  const mkSeat = (p, cls) => {
    const backs = h('div', { class: 'backs' });
    const who = h('div', { class: 'who' }, NAMES[p]);
    const el = h('div', { class: `seat ${cls} ${p === 2 ? 'partner' : ''}` }, cls === 'top' ? [who, backs] : [backs, who]);
    seats[p] = { el, backs, who };
    return el;
  };
  const boardView = new BoardView();
  const tableEl = h('div', { class: 'table-classic' }, mkSeat(2, 'top'), mkSeat(3, 'side left'), boardView.el, mkSeat(1, 'side right'));
  const myWho = h('div', { class: 'who' }, 'Você');
  const hint = h('div', { class: 'hint' });
  const meBar = h('div', { class: 'me-bar' }, myWho, hint);
  const handEl = h('div', { class: 'hand locked' });
  stage.append(top, tableEl, meBar, handEl, h('div', { class: 'bottom-pad' }));

  boardView.el.addEventListener('click', () => {
    if (selected) deselect();
  });

  function updateScore() {
    tallyUs.innerHTML = tally(match.score[0]);
    tallyThem.innerHTML = tally(match.score[1]);
    const fmtLbl = match.rules.formato === 'pontos' ? `até ${match.rules.metaPontos}` : match.roundNo > 4 ? 'desempate' : `de 4`;
    roundLbl.innerHTML = '';
    roundLbl.append('Rodada', h('b', {}, String(Math.max(1, match.roundNo))), fmtLbl);
  }

  function renderSeats() {
    for (const p of [1, 2, 3]) {
      const s = seats[p];
      s.backs.innerHTML = '';
      const n = round.hands[p].length;
      const u = p === 2 ? 15 : 13;
      for (let i = 0; i < n; i++) s.backs.append(backEl(u));
    }
  }

  function setTurn(p) {
    for (const q of [1, 2, 3]) seats[q].el.classList.toggle('turn', q === p);
    myWho.classList.toggle('turn', p === 0);
  }

  function handU(n) {
    const w = handEl.clientWidth || stage.clientWidth - 24;
    return Math.max(28, Math.min(46, Math.floor((w - 6 * (n - 1)) / n)));
  }

  function renderHand({ enter = false } = {}) {
    handEl.innerHTML = '';
    const hand = round.hands[0];
    const legal = round.turn === 0 && !round.result ? round.legalMoves(0) : [];
    const u = handU(Math.max(hand.length, 5));
    hand.forEach((t, i) => {
      const el = tileEl(t, { u });
      el.setAttribute('role', 'button');
      el.setAttribute('tabindex', '0');
      el.setAttribute('aria-label', `Pedra ${t.a} e ${t.b}`);
      const can = legal.some((m) => m.tile === t);
      if (round.turn === 0) el.classList.add(can ? 'can' : 'cannot');
      if (selected === t) el.classList.add('sel');
      if (enter) {
        el.classList.add('enter');
        el.style.animationDelay = `${i * 45}ms`;
      }
      const act = () => onTileTap(t, el);
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        act();
      });
      el.addEventListener('keydown', (e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), act()));
      handEl.append(el);
    });
    handEl.classList.toggle('locked', round.turn !== 0 || !!round.result);
  }

  function bubble(p, text) {
    const s = p === 0 ? { el: meBar } : seats[p];
    const b = h('div', { class: 'bubble' }, text);
    if (p === 0) Object.assign(b.style, { left: '0', bottom: '100%' });
    s.el.append(b);
    setTimeout(() => b.remove(), 1500);
  }

  // ---------- jogada humana ----------
  function onTileTap(t, el) {
    if (!waiting || round.turn !== 0) return;
    const moves = round.legalMoves(0).filter((m) => m.tile === t);
    if (!moves.length) {
      sfx.error();
      haptic(30);
      el.animate([{ transform: 'translateX(0)' }, { transform: 'translateX(-5px)' }, { transform: 'translateX(5px)' }, { transform: 'translateX(0)' }], { duration: 220 });
      setHint('Essa não encaixa.', true);
      return;
    }
    const closes = moves.some((m) => round.wouldClose(m.tile, m.side));
    if (selected === t) {
      if (moves.length === 1) return commit(moves[0], el);
      return;
    }
    if (moves.length === 1 && !closes) return commit(moves[0], el);
    selected = t;
    sfx.pick();
    renderHand();
    if (closes) setHint('Essa pedra fecha o jogo! Ganha a dupla com menos pontos na mão.', true);
    else setHint('Escolha a ponta.');
    boardView.showTargets(round.board, moves.map((m) => m.side), (side) => {
      const mv = moves.find((m) => m.side === side);
      const tEl = handEl.querySelector(`[data-uid="${t.uid}"]`);
      commit(mv, tEl);
    });
  }

  function deselect() {
    selected = null;
    boardView.hideTargets();
    boardView.fit();
    renderHand();
    setHint(defaultHint());
  }

  function commit(mv, el) {
    const rect = el ? el.getBoundingClientRect() : null;
    selected = null;
    boardView.hideTargets();
    const w = waiting;
    waiting = null;
    w({ mv, rect });
  }

  function setHint(text, warn = false) {
    hint.textContent = text;
    hint.classList.toggle('warn', warn);
  }
  function defaultHint() {
    if (round.board.empty) return round.mustStartWith ? 'Você sai com a bucha de sena.' : 'Sua saída. Jogue qualquer pedra.';
    const { L, R } = round.board.ends;
    return `Pontas: ${L} e ${R}`;
  }

  // ---------- fluxo ----------
  async function playMove(p, mv, fromRect) {
    const res = round.play(p, mv.tile, mv.side);
    if (p !== 0) renderSeats();
    else renderHand();
    boardView.board = round.board;
    const power = res.result ? 1.4 : isDouble(mv.tile) ? 1.15 : 1;
    await boardView.flyIn(res.rec, fromRect, { power });
    if (res.result) {
      shake(1.2);
      sfx.slam();
    }
    return res;
  }

  async function humanTurn() {
    const legal = round.legalMoves(0);
    if (!legal.length) {
      setHint('Sem jogo. Você passa.', true);
      renderHand();
      await sleep(700);
      if (dead) return;
      round.pass(0);
      bubble(0, 'Passo!');
      sfx.pass();
      haptic(20);
      return;
    }
    setHint(defaultHint());
    renderHand();
    const { mv, rect } = await new Promise((r) => (waiting = r));
    if (dead) return;
    await playMove(0, mv, rect);
  }

  async function aiTurn(p) {
    await sleep(520 + Math.random() * 420);
    if (dead) return;
    const mv = chooseMove(round, p);
    if (!mv) {
      round.pass(p);
      bubble(p, p === 2 ? 'Tô sem, parça!' : 'Passo!');
      sfx.pass();
      await sleep(450);
      return;
    }
    const rect = seats[p].backs.lastElementChild?.getBoundingClientRect() || seats[p].el.getBoundingClientRect();
    await playMove(p, mv, rect);
    if (round.board.placed.length > 1 && mv.tile.a === mv.tile.b && Math.random() < 0.35 && !round.result) {
      bubble(p, ['Toma essa bucha!', 'Bucha na mesa!', 'Lá vai!'][Math.floor(Math.random() * 3)]);
    }
  }

  async function playRound() {
    round = match.newRound();
    boardView.clear();
    boardView.rebuild(round.board);
    updateScore();
    round.hands[0].sort((x, y) => x.a - y.a || x.b - y.b);
    renderSeats();
    sfx.shuffle();
    setTurn(-1);
    renderHand({ enter: true });
    const starterName = round.starter === 0 ? 'Você começa' : `${NAMES[round.starter]} começa`;
    setHint(starterName + (round.mustStartWith ? ' com a bucha de sena.' : '.'));
    await sleep(900);
    while (!round.result && !dead) {
      setTurn(round.turn);
      if (round.turn === 0) await humanTurn();
      else await aiTurn(round.turn);
      if (dead) return;
    }
    setTurn(-1);
    renderHand();
    await sleep(500);
    match.applyResult(round.result);
    updateScore();
    chalkDust(round.result.team === 1 ? tallyThem : tallyUs);
    await showResult(round.result);
  }

  function showResult(res) {
    return new Promise((resolve) => {
      const us = res.team === 0;
      const parts = [];
      if (res.type === 'batida') {
        const kind = res.kinds.includes('bucha') ? 'Batida de bucha!' : res.kinds.includes('laelo') ? 'Lá e lô!' : 'Batida!';
        const who = res.winner === 0 ? 'Você bateu' : res.winner === 2 ? 'Seu parceiro bateu' : `${NAMES[res.winner]} bateu`;
        parts.push(h('div', { class: 'eyebrow' }, who), h('h2', {}, kind));
        const tw = tileEl(res.tile, { u: 34 });
        tw.style.margin = '12px auto';
        parts.push(tw);
        if (isDouble(res.tile)) parts.push(h('p', {}, `Bateu com a ${BUCHA_NAMES[res.tile.a]}.`));
      } else {
        parts.push(h('div', { class: 'eyebrow' }, res.closer === 0 ? 'Você fechou o jogo' : `${NAMES[res.closer]} fechou o jogo`), h('h2', {}, 'Jogo fechado'));
        parts.push(
          h(
            'div',
            { class: 'res-team' },
            h('div', {}, h('small', {}, 'Nós'), String(res.teamSums[0])),
            h('div', {}, h('small', {}, 'Eles'), String(res.teamSums[1])),
          ),
        );
        const rows = h('div', { class: 'res-hands' });
        for (const p of [0, 2, 1, 3]) {
          const tiles = h('div', { class: 'tiles' }, round.hands[p].map((t) => tileEl(t, { u: 13 })));
          rows.append(h('div', { class: 'res-row' }, h('span', { class: 'nm' }, SHORT[p]), tiles, h('span', { class: 'sum' }, String(round.hands[p].reduce((s, t) => s + pipSum(t), 0)))));
        }
        parts.push(rows);
        if (res.team == null) parts.push(h('p', {}, 'Empatou na contagem. Ninguém marca.'));
        else parts.push(h('p', {}, us ? 'Menos pontos na mão: a rodada é nossa.' : 'Eles tinham menos pontos na mão.'));
      }
      if (res.team != null) {
        parts.push(h('div', { class: 'big', style: { color: us ? 'var(--amber-hi)' : 'var(--chili-hi)' } }, `${us ? '+' : ''}${res.points} ${us ? 'pra nós' : 'pra eles'}`));
        if (us) {
          sfx.win();
          confetti(50);
        } else sfx.lose();
      }
      const over = match.isOver();
      const btn = h('button', { class: 'btn amber wide' }, over ? 'Ver resultado' : 'Próxima rodada');
      parts.push(h('div', { class: 'actions' }, btn));
      const m = modal(parts, { dismissable: false, cls: 'result' });
      btn.addEventListener('click', () => {
        m.close();
        resolve();
      });
    });
  }

  function showMatchEnd() {
    const won = match.winnerTeam() === 0;
    const stats = store.get('stats', { classicWins: 0, classicPlayed: 0, viradaBest: 0, viradaWins: 0 });
    stats.classicPlayed++;
    if (won) stats.classicWins++;
    store.set('stats', stats);
    if (won) {
      confetti(140);
      sfx.win();
    } else sfx.lose();
    const m = modal(
      [
        h('div', { class: 'eyebrow' }, 'Fim da partida'),
        h('h2', {}, won ? 'A mesa é nossa!' : 'Hoje deu eles.'),
        h('div', { class: 'big' }, `${match.score[0]} × ${match.score[1]}`),
        h('p', {}, won ? 'Você e o parceiro levaram a partida. Pede mais uma?' : 'Revanche? A próxima rodada é por nossa conta.'),
        h(
          'div',
          { class: 'actions' },
          h('button', { class: 'btn ghost', onClick: () => { m.close(); go('home'); } }, 'Sair'),
          h('button', { class: 'btn amber', onClick: () => { m.close(); go('classic'); } }, 'Jogar de novo'),
        ),
      ],
      { dismissable: false, cls: 'result' },
    );
  }

  function confirmExit() {
    const m = modal([
      h('h2', {}, 'Levantar da mesa?'),
      h('p', {}, 'A partida em andamento vai ser perdida.'),
      h(
        'div',
        { class: 'actions' },
        h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Ficar'),
        h('button', { class: 'btn chili', onClick: () => { m.close(); go('home'); } }, 'Sair'),
      ),
    ]);
  }

  (async () => {
    while (!dead && !match.isOver()) {
      await playRound();
    }
    if (!dead) showMatchEnd();
  })();

  return {
    destroy() {
      dead = true;
      boardView.destroy();
      if (waiting) waiting({ mv: null });
    },
  };
}
