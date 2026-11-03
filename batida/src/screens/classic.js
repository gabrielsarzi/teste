import { h, modal, sleep, speedFactor } from '../ui/dom.js';
import { BoardView, tileEl, backEl } from '../ui/tileView.js';
import { ClassicMatch } from '../classic/engine.js';
import { chooseMove, chooseMoveMaster } from '../classic/ai.js';
import { CAST, line } from '../classic/cast.js';
import { say, PLAYER_PHRASES, reactTo } from '../classic/talk.js';
import { sfx, haptic } from '../ui/audio.js';
import { confetti, chalkDust, shake } from '../ui/fx.js';
import { settings, go, stats, saveStats } from '../app.js';
import { iconBtn, rulesModal } from './home.js';
import { isDouble, pipSum, BUCHA_NAMES } from '../core/tiles.js';

const QUICK_POOLS = {
  facil: ['zezao', 'naldo', 'marquinhos', 'careca'],
  medio: ['rogerio', 'bia', 'tonhao', 'neide', 'juninho'],
  dificil: ['paulao', 'lurdinha', 'valter', 'edu'],
};

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

function pickTwo(arr) {
  const a = [...arr].sort(() => Math.random() - 0.5);
  return [a[0], a[1]];
}

// params: { mode: 'quick'|'career', opps: [direita, esquerda], partner, rules, title, onEnd(won, match) }
export function classicScreen(stage, params = {}) {
  let dead = false;
  const mode = params.mode || 'quick';
  const opps = params.opps || pickTwo(QUICK_POOLS[settings.nivel] || QUICK_POOLS.medio);
  const partner = params.partner || 'rafa';
  const ids = ['voce', opps[0], partner, opps[1]];
  const rules = params.rules || {
    buchaVale2: settings.buchaVale2,
    laeloVale2: settings.laeloVale2,
    comecaSena: settings.comecaSena,
    formato: settings.formato,
  };
  const match = new ClassicMatch(rules);
  const nameOf = (p) => (p === 0 ? 'Você' : CAST[ids[p]].name);
  let round = null;
  let waiting = null;
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
  const top = h('div', { class: 'topbar' }, iconBtn('back', 'Sair da mesa', () => confirmExit()), lousa, iconBtn('help', 'Regras', () => rulesModal()));

  const seats = [null];
  const mkSeat = (p, cls) => {
    const c = CAST[ids[p]];
    const backs = h('div', { class: 'backs' });
    const think = h('span', { class: 'think', 'aria-hidden': 'true' }, h('i'), h('i'), h('i'));
    const who = h('div', { class: 'nameplate' }, h('span', { class: 'nm' }, c.name), think);
    const lacks = h('div', { class: 'lacks' });
    const id = h('div', { class: 'ident' }, who, lacks);
    const el = h('div', { class: `seat ${cls} ${p === 2 ? 'partner' : ''}` }, id, backs);
    seats[p] = { el, backs, who, avatar: who, lacks };
    return el;
  };
  const boardView = new BoardView();
  const tableEl = h('div', { class: 'table-classic' }, mkSeat(2, 'top'), mkSeat(3, 'side left'), h('div', { class: 'felt' }, boardView.el), mkSeat(1, 'side right'));
  const myWho = h('div', { class: 'who' }, 'Você');
  const hint = h('div', { class: 'hint' });
  const chatBtn = h('button', { class: 'chat-btn', 'aria-label': 'Mandar uma frase', html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M4 5h16v11H9l-5 4z"/><path d="M8 10h8M8 13h5" stroke-linecap="round"/></svg>' });
  chatBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    openChat();
  });
  if (!settings.conversa) chatBtn.hidden = true;
  const meBar = h('div', { class: 'me-bar' }, h('div', { class: 'me-left' }, myWho, chatBtn), hint);
  const countStrip = h('div', { class: 'count-strip', 'aria-label': 'Contagem da mesa' });
  if (!settings.contagem) countStrip.hidden = true;
  const handEl = h('div', { class: 'hand locked' });
  stage.append(top, tableEl, countStrip, meBar, h('div', { class: 'rack' }, handEl), h('div', { class: 'bottom-pad' }));

  boardView.el.addEventListener('click', () => selected && deselect());

  function updateScore() {
    tallyUs.innerHTML = tally(match.score[0]);
    tallyThem.innerHTML = tally(match.score[1]);
    const lbl = match.rules.formato === 'pontos' ? `até ${match.rules.metaPontos}` : match.roundNo > 4 ? 'desempate' : 'de 4';
    roundLbl.innerHTML = '';
    roundLbl.append('Rodada', h('b', {}, String(Math.max(1, match.roundNo))), lbl);
  }

  function renderSeats() {
    for (const p of [1, 2, 3]) {
      const s = seats[p];
      const n = round.hands[p].length;
      while (s.backs.children.length > n) s.backs.lastElementChild.remove();
      while (s.backs.children.length < n) s.backs.append(backEl(p === 2 ? 14 : 12));
    }
  }

  // contagem: quantas pedras de cada número já estão na mesa, e onde cada um passou
  function updateCount() {
    if (!settings.contagem || !round) return;
    const c = [0, 0, 0, 0, 0, 0, 0];
    for (const r of round.board.placed) {
      c[r.tile.a]++;
      if (r.tile.b !== r.tile.a) c[r.tile.b]++;
    }
    const mine = [0, 0, 0, 0, 0, 0, 0];
    for (const t of round.hands[0]) {
      mine[t.a]++;
      if (t.b !== t.a) mine[t.b]++;
    }
    countStrip.innerHTML = '';
    const ends = round.board.empty ? [] : [round.board.ends.L, round.board.ends.R];
    for (let n = 0; n <= 6; n++) {
      const out = 7 - c[n] - mine[n];
      const cell = h(
        'div',
        { class: `cnt ${c[n] === 7 ? 'gone' : ''} ${ends.includes(n) ? 'end' : ''}`, title: `${n}: ${c[n]} na mesa, ${mine[n]} com você, ${out} com os outros`, 'aria-label': `Número ${n}: ${c[n]} de 7 na mesa, ${out} com os outros` },
        h('span', { class: 'cnt-n' }, String(n)),
        h('span', { class: 'cnt-v' }, `${c[n]}/7`),
        h('span', { class: 'cnt-o' }, c[n] === 7 ? 'acabou' : out > 0 ? `resta ${out}` : 'só você'),
      );
      countStrip.append(cell);
    }
    for (const p of [1, 2, 3]) {
      const l = [...round.lacks[p]].sort();
      seats[p].lacks.textContent = l.length ? `sem ${l.join(' ')}` : '';
    }
  }

  function setTurn(p, thinking = false) {
    for (const q of [1, 2, 3]) {
      seats[q].el.classList.toggle('turn', q === p);
      seats[q].el.classList.toggle('thinking', q === p && thinking);
    }
    myWho.classList.toggle('turn', p === 0);
  }

  // ---------- mão (atualizada no lugar, sem recriar as pedras) ----------
  const handEls = new Map();
  function handU(n) {
    const w = handEl.clientWidth || stage.clientWidth - 24;
    return Math.max(28, Math.min(48, Math.floor((w - 6 * (n - 1)) / n)));
  }

  function buildHand() {
    handEl.innerHTML = '';
    handEls.clear();
    const u = handU(7);
    round.hands[0].forEach((t, i) => {
      const el = tileEl(t, { u });
      el.setAttribute('role', 'button');
      el.setAttribute('tabindex', '0');
      el.setAttribute('aria-label', `Pedra ${t.a} e ${t.b}`);
      el.classList.add('enter');
      el.style.animationDelay = `${i * 70}ms`;
      const act = () => onTileTap(t, el);
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        act();
      });
      el.addEventListener('keydown', (e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), act()));
      handEl.append(el);
      handEls.set(t.uid, el);
    });
  }

  function refreshHand() {
    const hand = round.hands[0];
    for (const [uid, el] of handEls) {
      if (!hand.some((t) => t.uid === uid)) {
        el.remove();
        handEls.delete(uid);
      }
    }
    const myTurn = round.turn === 0 && !round.result && waiting;
    const legal = myTurn ? round.legalMoves(0) : [];
    for (const t of hand) {
      const el = handEls.get(t.uid);
      if (!el) continue;
      const can = legal.some((m) => m.tile === t);
      el.classList.toggle('can', !!(myTurn && settings.ajuda && can));
      el.classList.toggle('cannot', !!(myTurn && settings.ajuda && !can));
      el.classList.toggle('sel', selected === t);
    }
    handEl.classList.toggle('locked', !myTurn);
    handEl.classList.toggle('my-turn', !!myTurn);
  }

  let lastChat = 0;
  function bubble(p, text, kind = '', chatter = false) {
    if (chatter) {
      if (!settings.conversa || Date.now() - lastChat < 2200) return;
      lastChat = Date.now();
    }
    if (!text) return;
    const s = p === 0 ? { el: meBar } : seats[p];
    s.el.querySelectorAll('.bubble').forEach((b) => b.remove());
    const b = h('div', { class: `bubble ${kind}` }, text);
    if (p === 0) Object.assign(b.style, { left: '0', bottom: '100%' });
    s.el.append(b);
    setTimeout(() => b.remove(), 1900 * Math.max(0.8, speedFactor()));
  }

  // ---------- jogada humana ----------
  let lastBronca = 0;
  function onTileTap(t, el) {
    if (!waiting || round.turn !== 0) return;
    const moves = round.legalMoves(0).filter((m) => m.tile === t);
    if (!moves.length) {
      sfx.error();
      haptic(40);
      el.animate([{ transform: 'translateX(0)' }, { transform: 'translateX(-6px)' }, { transform: 'translateX(6px)' }, { transform: 'translateX(0)' }], { duration: 240 });
      // bronca de um adversário
      const now = Date.now();
      if (now - lastBronca > 900) {
        lastBronca = now;
        const who = Math.random() < 0.5 ? 1 : 3;
        bubble(who, line(ids[who], 'bronca'), 'bronca');
      }
      setHint(round.board.empty && round.mustStartWith ? 'Tem que sair com a bucha de sena.' : 'Essa não encaixa.', true);
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
    refreshHand();
    if (closes) setHint('Essa fecha o jogo! Toque na ponta para confirmar.', true);
    else setHint('Escolha a ponta.');
    boardView.showTargets(round.board, moves.map((m) => m.side), (side) => {
      const mv = moves.find((m) => m.side === side);
      commit(mv, handEls.get(t.uid));
    });
  }

  function deselect() {
    selected = null;
    boardView.hideTargets();
    boardView.fit();
    refreshHand();
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
    if (round.board.empty) return round.mustStartWith ? 'Você sai com a bucha de sena.' : 'Sua saída: qualquer pedra.';
    const { L, R } = round.board.ends;
    return `Sua vez · pontas ${L} e ${R}`;
  }

  // ---------- fluxo ----------
  async function playMove(p, mv, fromRect) {
    const res = round.play(p, mv.tile, mv.side);
    if (p !== 0) renderSeats();
    else refreshHand();
    boardView.board = round.board;
    const power = res.result ? 1.4 : isDouble(mv.tile) ? 1.15 : 1;
    await boardView.flyIn(res.rec, fromRect, { power });
    updateCount();
    if (!res.result) afterPlayChatter(p, mv.tile);
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
      await sleep(900);
      if (dead) return;
      round.pass(0);
      updateCount();
      bubble(0, 'Passo!');
      passChatter(0);
      sfx.pass();
      haptic(20);
      await sleep(500);
      return;
    }
    setHint(defaultHint());
    const p = new Promise((r) => (waiting = r));
    refreshHand();
    const { mv, rect } = await p;
    if (dead || !mv) return;
    await playMove(0, mv, rect);
    await sleep(450);
  }

  function aiChoose(p) {
    const c = CAST[ids[p]];
    if (c.master) return chooseMoveMaster(round, p, c.master);
    return chooseMove(round, p, c.skill);
  }

  async function aiTurn(p) {
    setTurn(p, true);
    const t0 = performance.now();
    const mv = aiChoose(p);
    const nMoves = round.legalMoves(p).length;
    // pensa mais quando tem escolha de verdade
    const think = nMoves <= 1 ? 850 : 1150 + Math.random() * 650;
    const spent = performance.now() - t0;
    await sleep(Math.max(0, think - spent / speedFactor()));
    if (dead) return;
    setTurn(p, false);
    if (!mv) {
      round.pass(p);
      updateCount();
      bubble(p, line(ids[p], 'pass'));
      passChatter(p);
      sfx.pass();
      await sleep(800);
      return;
    }
    const rect = seats[p].backs.lastElementChild?.getBoundingClientRect() || seats[p].avatar.getBoundingClientRect();
    await playMove(p, mv, rect);
    if (round.result) bubble(p, line(ids[p], 'bater'));
    else if (round.board.placed.length > 1 && isDouble(mv.tile) && Math.random() < 0.4) bubble(p, line(ids[p], 'bucha'), '', true);
    await sleep(380);
  }

  // ---------- conversa de mesa ----------
  const chance = (x) => settings.conversa && Math.random() < x;
  const usAhead = () => match.score[0] > match.score[1];
  const usBehind = () => match.score[0] < match.score[1];

  function roundStartChatter() {
    if (!chance(0.6) || match.roundNo < 1) return;
    const p = [1, 2, 3][Math.floor(Math.random() * 3)];
    const team = p % 2;
    const ahead = team === 0 ? usAhead() : usBehind();
    const behind = team === 0 ? usBehind() : usAhead();
    const ev = match.roundNo > 1 && ahead ? 'start_lead' : match.roundNo > 1 && behind ? 'start_behind' : 'start';
    setTimeout(() => !dead && bubble(p, say(ids[p], ev), '', true), 700);
  }

  function passChatter(p) {
    if (!chance(0.55)) return;
    const mocker = p % 2 === 0 ? (Math.random() < 0.5 ? 1 : 3) : null;
    setTimeout(() => {
      if (dead) return;
      if (p === 0 && Math.random() < 0.4) bubble(2, say(ids[2], 'console_pass'), '', true);
      else if (mocker) bubble(mocker, say(ids[mocker], 'mock_pass'), '', true);
      else if (Math.random() < 0.5) bubble(2, say(ids[2], 'mock_pass'), '', true);
    }, 650);
  }

  function afterPlayChatter(p, tile) {
    if (!settings.conversa) return;
    const left = round.hands[p].length;
    if (left === 1) {
      if (p !== 0 && Math.random() < 0.6) return void setTimeout(() => !dead && bubble(p, say(ids[p], 'one_left_self'), '', true), 300);
      if (p % 2 === 1 && Math.random() < 0.6) return void setTimeout(() => !dead && bubble(2, say(ids[2], 'one_left_warn'), '', true), 400);
    }
    if (p === 0 && tile.a === 6 && tile.b === 6 && chance(0.5)) {
      const q = Math.random() < 0.5 ? 1 : 3;
      return void setTimeout(() => !dead && bubble(q, say(ids[q], 'dump_sena'), '', true), 450);
    }
  }

  function openChat() {
    if (!settings.conversa) return;
    const list = h('div', { class: 'phrases' });
    const groups = [['opp', 'Pra eles'], ['partner', `Pro ${CAST[partner].name}`], ['all', 'Pra mesa']];
    for (const [to, label] of groups) {
      list.append(h('div', { class: 'ph-group' }, label));
      for (const ph of PLAYER_PHRASES.filter((x) => x.to === to)) {
        list.append(
          h('button', { class: 'phrase', onClick: () => { m.close(); sendPhrase(ph); } }, ph.text),
        );
      }
    }
    const m = modal([h('h2', {}, 'Falar na mesa'), list], { cls: 'chat-sheet' });
  }

  let lastSent = 0;
  function sendPhrase(ph) {
    if (Date.now() - lastSent < 1500) return;
    lastSent = Date.now();
    sfx.pick();
    bubble(0, ph.text);
    const replies = reactTo(ph, { usAhead: usAhead(), usBehind: usBehind() });
    replies.forEach((r, i) => setTimeout(() => !dead && bubble(r.p, r.text), 1100 + i * 1300));
  }

  async function playRound() {
    round = match.newRound();
    boardView.clear();
    boardView.prepareRound();
    boardView.rebuild(round.board);
    updateScore();
    round.hands[0].sort((x, y) => x.a - y.a || x.b - y.b);
    renderSeats();
    sfx.shuffle();
    setTurn(-1);
    buildHand();
    refreshHand();
    countStrip.innerHTML = '';
    for (const q of [1, 2, 3]) seats[q].lacks.textContent = '';
    updateCount();
    roundStartChatter();
    const starter = round.starter === 0 ? 'Você começa' : `${nameOf(round.starter)} começa`;
    setHint(starter + (round.mustStartWith ? ' com a bucha de sena.' : '.'));
    // tempo para olhar as próprias pedras antes da primeira jogada
    await sleep(round.starter === 0 ? 900 : 2200);
    while (!round.result && !dead) {
      setTurn(round.turn);
      if (round.turn === 0) await humanTurn();
      else await aiTurn(round.turn);
      if (dead) return;
    }
    setTurn(-1);
    refreshHand();
    if (round.result.type === 'fechado' && round.result.team != null && chance(0.8)) {
      const q = round.result.closer;
      if (q !== 0) bubble(q, say(ids[q], round.result.team === q % 2 ? 'close_us' : 'lose_round'));
    } else if (round.result.team != null && chance(0.6)) {
      const winners = round.result.team === 0 ? [2] : [1, 3];
      const losers = round.result.team === 0 ? [1, 3] : [2];
      const w = winners[Math.floor(Math.random() * winners.length)];
      const l = losers[Math.floor(Math.random() * losers.length)];
      if (round.result.winner !== w) setTimeout(() => !dead && bubble(w, say(ids[w], 'win_round')), 500);
      setTimeout(() => !dead && bubble(l, say(ids[l], 'lose_round')), 1300);
    }
    await sleep(1700);
    match.applyResult(round.result);
    const st = stats();
    st.rounds++;
    if (round.result.type === 'batida' && round.result.winner === 0) {
      st.batidas++;
      if (isDouble(round.result.tile)) st.buchas++;
    }
    saveStats(st);
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
        const who = res.winner === 0 ? 'Você bateu' : res.winner === 2 ? `${nameOf(2)} bateu` : `${nameOf(res.winner)} bateu`;
        parts.push(h('div', { class: 'eyebrow' }, who), h('h2', {}, kind));
        const row = h('div', { class: 'res-batida' }, tileEl(res.tile, { u: 34 }));
        parts.push(row);
        if (isDouble(res.tile)) parts.push(h('p', {}, `Bateu com a ${BUCHA_NAMES[res.tile.a]}.`));
      } else {
        parts.push(h('div', { class: 'eyebrow' }, res.closer === 0 ? 'Você fechou o jogo' : `${nameOf(res.closer)} fechou o jogo`), h('h2', {}, 'Jogo fechado'));
        parts.push(h('div', { class: 'res-team' }, h('div', {}, h('small', {}, 'Nós'), String(res.teamSums[0])), h('div', {}, h('small', {}, 'Eles'), String(res.teamSums[1]))));
        const rows = h('div', { class: 'res-hands' });
        for (const p of [0, 2, 1, 3]) {
          const tiles = h('div', { class: 'tiles' }, round.hands[p].map((t) => tileEl(t, { u: 13 })));
          rows.append(h('div', { class: 'res-row' }, h('span', { class: 'nm' }, nameOf(p)), tiles, h('span', { class: 'sum' }, String(round.hands[p].reduce((s, t) => s + pipSum(t), 0)))));
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
      parts.push(h('div', { class: 'score-line' }, `Nós ${match.score[0]} × ${match.score[1]} Eles`));
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

  function showQuickEnd() {
    const won = match.winnerTeam() === 0;
    const st = stats();
    st.quickPlayed++;
    if (won) st.quickWins++;
    saveStats(st);
    if (won) {
      confetti(140);
      sfx.win();
    } else sfx.lose();
    const m = modal(
      [
        h('div', { class: 'eyebrow' }, 'Fim da partida'),
        h('h2', {}, won ? 'A mesa é nossa!' : 'Hoje deu eles.'),
        h('div', { class: 'big' }, `${match.score[0]} × ${match.score[1]}`),
        h('p', {}, won ? `Você e ${nameOf(2)} levaram a partida.` : 'Bora pra revanche?'),
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
      h('p', {}, mode === 'career' ? 'Se sair agora, conta como derrota neste jogo do campeonato.' : 'A partida em andamento vai ser perdida.'),
      h(
        'div',
        { class: 'actions' },
        h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Ficar'),
        h('button', { class: 'btn chili', onClick: () => { m.close(); if (mode === 'career' && params.onEnd) { dead = true; params.onEnd(false, match, true); } else go('home'); } }, 'Sair'),
      ),
    ]);
  }

  (async () => {
    await sleep(200);
    while (!dead && !match.isOver()) await playRound();
    if (dead) return;
    if (mode === 'career' && params.onEnd) params.onEnd(match.winnerTeam() === 0, match);
    else showQuickEnd();
  })();

  return {
    destroy() {
      dead = true;
      boardView.destroy();
      if (waiting) waiting({ mv: null });
    },
  };
}
