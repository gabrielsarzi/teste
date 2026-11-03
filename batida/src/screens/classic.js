import { h, modal, sleep, speedFactor } from '../ui/dom.js';
import { BoardView, tileEl, backEl } from '../ui/tileView.js';
import { ClassicMatch } from '../classic/engine.js';
import { chooseMove, chooseMoveMaster, voteClose } from '../classic/ai.js';
import { CAST, line } from '../classic/cast.js';
import { say, PLAYER_PHRASES, reactTo } from '../classic/talk.js';
import { sfx, haptic } from '../ui/audio.js';
import { confetti, chalkDust, shake, pop } from '../ui/fx.js';
import { settings, go, stats, saveStats, wallet, setWallet, money, rivals, addRival } from '../app.js';
import { iconBtn, rulesModal } from './home.js';
import { isDouble, pipSum, BUCHA_NAMES } from '../core/tiles.js';
import { track } from '../progress.js';
import { showRewarded, maybeInterstitial } from '../ads.js';

export const QUICK_POOLS = {
  facil: ['zezao', 'naldo', 'marquinhos', 'careca'],
  medio: ['rogerio', 'bia', 'tonhao', 'neide', 'juninho'],
  dificil: ['paulao', 'lurdinha', 'valter', 'edu'],
};

// A cruz da lousa: cada ponto é uma bolinha numa ponta da cruz (4 pontos fecham a partida).
// A bolinha no meio marca quem sai na rodada.
function cruz(n, saida = false) {
  const tips = [[20, 4.5], [35.5, 20], [20, 35.5], [4.5, 20]];
  let dots = '';
  tips.forEach(([x, y], i) => {
    if (i < n) dots += `<circle cx="${x}" cy="${y}" r="4" fill="#eeece2"/>`;
  });
  if (saida) dots += `<circle cx="20" cy="20" r="3.8" fill="#f2c14e" stroke="#23302a" stroke-width="1.2"/>`;
  const extra = n > 4 ? `<text x="40" y="40" fill="#eeece2" font-size="11" font-family="Caveat, cursive" text-anchor="end">+${n - 4}</text>` : '';
  return `<svg viewBox="0 0 40 40" width="40" height="40" role="img" aria-label="${n} ponto${n === 1 ? '' : 's'}${saida ? ', saída desta rodada' : ''}"><path d="M20 6 Q20.6 20 19.6 34 M6 20.4 Q20 19.4 34 20" stroke="#eeece2" stroke-width="2.6" fill="none" stroke-linecap="round"/>${dots}${extra}</svg>`;
}

function shuffled(arr) {
  return [...arr].sort(() => Math.random() - 0.5);
}

const SEATS = { 4: ['me', 'right', 'top', 'left'], 3: ['me', 'right', 'left'], 2: ['me', 'top'] };

// params: { mode: 'quick'|'career', players, opps: [...], partner, rules, stake, onEnd(won, match, quit) }
export function classicScreen(stage, params = {}) {
  let dead = false;
  const mode = params.mode || 'quick';
  const n = params.players || (mode === 'career' ? 4 : settings.jogadores || 4);
  const nOpp = n === 4 ? 2 : n - 1;
  const opps = params.opps || shuffled(QUICK_POOLS[settings.nivel] || QUICK_POOLS.medio).slice(0, nOpp);
  const partner = params.partner || 'rafa';
  const ids = n === 4 ? ['voce', opps[0], partner, opps[1]] : ['voce', ...opps];
  const stake = mode === 'quick' ? params.stake ?? Math.min(settings.aposta, wallet()) : mode === 'online' ? params.stake || 0 : 0;
  const rules = params.rules || {
    players: n,
    buchaVale2: settings.buchaVale2,
    laeloVale2: settings.laeloVale2,
    comecaSena: settings.comecaSena,
    cincoBuchas: settings.cincoBuchas,
    votacao: true,
  };
  rules.players = n;
  const match = new ClassicMatch(rules, params.seed);
  track('matchStart');
  const teamOf = (p) => match.teamOf(p);
  const nameOf = (p) => (p === 0 ? 'Você' : CAST[ids[p]].name);
  const partnerName = n === 4 ? CAST[ids[2]].name : '';
  const teamName = (t) => (n === 4 ? (t === 0 ? 'Nós' : 'Eles') : t === 0 ? 'Você' : CAST[ids[t]].name.split(' ').pop());
  const isMate = (p) => n === 4 && p === 2;
  const opponents = () => [...Array(n).keys()].filter((q) => q !== 0 && !isMate(q));
  let round = null;
  let waiting = null;
  let drawWait = null;
  let selected = null;

  // ---------- conversa: timers que somem quando a rodada acaba ----------
  const timers = new Set();
  const later = (fn, ms) => {
    const id = setTimeout(() => {
      timers.delete(id);
      if (!dead) fn();
    }, ms);
    timers.add(id);
  };
  const clearChatter = () => {
    for (const id of timers) clearTimeout(id);
    timers.clear();
  };

  // ---------- montagem ----------
  const crosses = [];
  const lousa = h('div', { class: `lousa teams-${match.teams}`, role: 'status', 'aria-live': 'polite' });
  for (let t = 0; t < match.teams; t++) {
    const c = h('div', { class: 'tally' });
    crosses.push(c);
    lousa.append(h('div', { class: 'team' }, h('div', { class: 'lbl' }, teamName(t)), c));
    if (t === 0 && match.teams === 2) lousa.append(h('div', { class: 'round' }));
  }
  if (match.teams !== 2) lousa.append(h('div', { class: 'round' }));
  const roundLbl = lousa.querySelector('.round');
  const top = h('div', { class: 'topbar' }, iconBtn('back', 'Sair da mesa', () => confirmExit()), lousa, iconBtn('help', 'Regras', () => rulesModal()));

  const seats = [];
  const mkSeat = (p) => {
    const pos = SEATS[n][p];
    const c = CAST[ids[p]];
    const backs = h('div', { class: 'backs' });
    const think = h('span', { class: 'think', 'aria-hidden': 'true' }, h('i'), h('i'), h('i'));
    const who = h('div', { class: 'nameplate' }, h('span', { class: 'nm' }, c.name), think);
    const lacks = h('div', { class: 'lacks' });
    const el = h('div', { class: `seat ${pos === 'top' ? 'top' : `side ${pos}`} ${isMate(p) ? 'partner' : ''}` }, h('div', { class: 'ident' }, who, lacks), backs);
    seats[p] = { el, backs, who, lacks, pos };
    return el;
  };
  for (let p = 1; p < n; p++) mkSeat(p);
  const seatAt = (pos) => seats.find((s) => s && s.pos === pos)?.el || h('div', { class: `seat ${pos === 'top' ? 'top' : `side ${pos}`} empty`, 'aria-hidden': 'true' });
  const boardView = new BoardView();
  const monte = h('div', { class: 'monte', hidden: true }, h('div', { class: 'monte-stack' }), h('div', { class: 'monte-n' }));
  const felt = h('div', { class: 'felt' }, boardView.el, monte);
  const tableEl = h('div', { class: `table-classic n${n}` }, seatAt('top'), seatAt('left'), felt, seatAt('right'));

  const myWho = h('div', { class: 'who' }, 'Você');
  const timerBar = h('div', { class: 'turn-timer', hidden: true }, h('i'));
  const hint = h('div', { class: 'hint' });
  const chatBtn = h('button', { class: 'chat-btn', 'aria-label': 'Mandar uma frase', html: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M4 5h16v11H9l-5 4z"/><path d="M8 10h8M8 13h5" stroke-linecap="round"/></svg>' });
  chatBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    openChat();
  });
  if (!settings.conversa) chatBtn.hidden = true;
  const drawBtn = h('button', { class: 'btn amber small draw-btn', hidden: true }, 'Comprar');
  drawBtn.addEventListener('click', () => drawWait && drawWait());
  const meBar = h('div', { class: 'me-bar' }, h('div', { class: 'me-left' }, myWho, chatBtn, timerBar), drawBtn, hint);
  if (settings.telaLimpa) stage.classList.add('clean');
  const countStrip = h('div', { class: 'count-strip', 'aria-label': 'Contagem da mesa' });
  if (!settings.contagem) countStrip.hidden = true;
  const handEl = h('div', { class: 'hand locked' });
  const stakeChip = stake ? h('div', { class: 'stake-chip' }, `Valendo ${money(stake)}`) : null;
  stage.append(top, tableEl, countStrip, meBar, h('div', { class: 'rack' }, handEl), h('div', { class: 'bottom-pad' }));
  if (stakeChip) felt.append(stakeChip);

  boardView.el.addEventListener('click', () => selected && deselect());

  function updateScore() {
    const saidaTeam = round && round.voltou == null && !round.result ? teamOf(round.starter) : -1;
    crosses.forEach((c, t) => (c.innerHTML = cruz(match.score[t], saidaTeam === t)));
    roundLbl.innerHTML = '';
    roundLbl.append('Rodada', h('b', {}, String(Math.max(1, match.roundNo))), `até ${match.rules.metaPontos}`);
  }

  function renderSeats() {
    for (let p = 1; p < n; p++) {
      const s = seats[p];
      const k = round.hands[p].length;
      const u = s.pos === 'top' ? 14 : 12;
      while (s.backs.children.length > k) s.backs.lastElementChild.remove();
      while (s.backs.children.length < k) s.backs.append(backEl(u));
      s.backs.classList.toggle('many', k > 9);
    }
    const pk = round.pile.length;
    monte.hidden = n === 4;
    monte.querySelector('.monte-n').textContent = pk ? `Monte ${pk}` : 'Monte vazio';
    const st = monte.querySelector('.monte-stack');
    st.innerHTML = '';
    for (let i = 0; i < Math.min(pk, 6); i++) {
      const b = backEl(11);
      b.style.transform = `translate(${i * 2}px, ${-i * 2}px) rotate(${(i % 2 ? 4 : -3)}deg)`;
      st.append(b);
    }
  }

  // contagem: quantas pedras de cada número já estão na mesa, e onde cada um passou
  function updateCount() {
    if (!round) return;
    for (let p = 1; p < n; p++) {
      const l = [...round.lacks[p]].sort();
      seats[p].lacks.textContent = settings.contagem && l.length ? `sem ${l.join(' ')}` : '';
    }
    if (!settings.contagem) return;
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
    for (let k = 0; k <= 6; k++) {
      const out = 7 - c[k] - mine[k];
      countStrip.append(
        h(
          'div',
          { class: `cnt ${c[k] === 7 ? 'gone' : ''} ${ends.includes(k) ? 'end' : ''}`, 'aria-label': `Número ${k}: ${c[k]} de 7 na mesa, ${out} com os outros` },
          h('span', { class: 'cnt-n' }, String(k)),
          h('span', { class: 'cnt-v' }, `${c[k]}/7`),
          h('span', { class: 'cnt-o' }, c[k] === 7 ? 'acabou' : out > 0 ? `resta ${out}` : 'só você'),
        ),
      );
    }
  }

  function setTurn(p, thinking = false) {
    for (let q = 1; q < n; q++) {
      seats[q].el.classList.toggle('turn', q === p);
      seats[q].el.classList.toggle('thinking', q === p && thinking);
    }
    myWho.classList.toggle('turn', p === 0);
    updateHint();
  }

  // ---------- texto de status: pontas e de quem é a vez, sempre atualizado ----------
  let hintLock = 0;
  function setHint(text, warn = false, holdMs = 0) {
    hint.textContent = text;
    hint.classList.toggle('warn', warn);
    if (holdMs) hintLock = Date.now() + holdMs;
  }
  function updateHint() {
    if (!round || Date.now() < hintLock) return;
    if (round.result) return setHint('');
    const pontas = round.board.empty ? '' : `pontas ${round.board.ends.L} e ${round.board.ends.R}`;
    if (round.turn === 0) {
      if (round.board.empty) return setHint(round.mustStartWith ? `Você sai com a ${BUCHA_NAMES[round.mustStartWith.a]}.` : 'Sua saída: qualquer pedra.');
      return setHint(`Sua vez · ${pontas}`);
    }
    if (round.board.empty) return setHint(`${nameOf(round.turn)} vai sair.`);
    setHint(`Vez de ${nameOf(round.turn)} · ${pontas}`);
  }

  // ---------- mão: atualizada no lugar, e dá para arrastar para reorganizar ----------
  const handEls = new Map();
  function handU(k) {
    const w = handEl.clientWidth || stage.clientWidth - 24;
    const big = settings.pedras === 'grande';
    const gap = big ? 4 : 6;
    handEl.style.gap = gap + 'px';
    return Math.max(24, Math.min(big ? 58 : 48, Math.floor((w - gap * (k - 1)) / k)));
  }

  function addHandTile(t, i, enter = true) {
    const el = tileEl(t, { u: handU(Math.max(7, round.hands[0].length)) });
    el.setAttribute('role', 'button');
    el.setAttribute('tabindex', '0');
    el.setAttribute('aria-label', `Pedra ${t.a} e ${t.b}`);
    if (enter) {
      el.classList.add('enter');
      el.style.animationDelay = `${i * 70}ms`;
    }
    let dragged = false;
    el.addEventListener('click', (e) => {
      e.stopPropagation();
      if (dragged) return void (dragged = false);
      onTileTap(t, el);
    });
    el.addEventListener('keydown', (e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onTileTap(t, el)));
    // arrastar para os lados troca a pedra de lugar
    el.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      const startX = e.clientX;
      const startY = e.clientY;
      let active = false;
      let base = startX;
      const move = (ev) => {
        const dx = ev.clientX - base;
        if (!active) {
          if (Math.abs(ev.clientX - startX) < 10 || Math.abs(ev.clientY - startY) > 30) return;
          active = true;
          el.classList.add('dragging');
          try {
            el.setPointerCapture(e.pointerId);
          } catch {
            /* ignore */
          }
        }
        el.style.translate = `${dx}px -10px`;
        // troca com a vizinha quando passa do meio dela
        const sib = dx > 0 ? el.nextElementSibling : el.previousElementSibling;
        if (sib) {
          const r = sib.getBoundingClientRect();
          const mid = r.left + r.width / 2;
          if ((dx > 0 && ev.clientX > mid) || (dx < 0 && ev.clientX < mid)) {
            const before = el.getBoundingClientRect().left;
            if (dx > 0) sib.after(el);
            else sib.before(el);
            const after = el.getBoundingClientRect().left;
            base += after - before;
            el.style.translate = `${ev.clientX - base}px -10px`;
            sfx.pick();
          }
        }
      };
      const up = () => {
        removeEventListener('pointermove', move);
        removeEventListener('pointerup', up);
        removeEventListener('pointercancel', up);
        if (!active) return;
        dragged = true;
        setTimeout(() => (dragged = false), 0);
        el.classList.remove('dragging');
        el.style.translate = '';
        const order = [...handEl.children].map((c) => +c.dataset.uid);
        round.hands[0].sort((a, b) => order.indexOf(a.uid) - order.indexOf(b.uid));
      };
      addEventListener('pointermove', move);
      addEventListener('pointerup', up);
      addEventListener('pointercancel', up);
    });
    handEls.set(t.uid, el);
    return el;
  }

  function buildHand() {
    handEl.innerHTML = '';
    handEls.clear();
    round.hands[0].forEach((t, i) => handEl.append(addHandTile(t, i)));
  }

  function refreshHand() {
    const hand = round.hands[0];
    for (const [uid, el] of handEls) {
      if (!hand.some((t) => t.uid === uid)) {
        el.remove();
        handEls.delete(uid);
      }
    }
    const u = handU(Math.max(7, hand.length));
    const myTurn = round.turn === 0 && !round.result && waiting;
    const legal = myTurn ? round.legalMoves(0) : [];
    for (const t of hand) {
      let el = handEls.get(t.uid);
      if (!el) {
        el = addHandTile(t, 0);
        handEl.append(el);
      }
      el.style.setProperty('--u', u + 'px');
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
    if (!text || dead) return;
    const s = p === 0 ? { el: meBar } : seats[p];
    s.el.querySelectorAll('.bubble').forEach((b) => b.remove());
    const b = h('div', { class: `bubble ${kind}` }, text);
    if (p === 0) Object.assign(b.style, { left: '0', bottom: '100%' });
    s.el.append(b);
    setTimeout(() => b.remove(), 2100 * Math.max(0.8, speedFactor()));
  }

  // ---------- relógio de jogada ----------
  let timer = null;
  function startTimer(onTimeout) {
    stopTimer();
    if (!settings.tempo) return;
    const total = settings.tempo * 1000;
    const t0 = Date.now();
    let cobrou = false;
    let lastTick = -1;
    timerBar.hidden = false;
    const fill = timerBar.firstElementChild;
    timer = setInterval(() => {
      if (dead) return stopTimer();
      const left = total - (Date.now() - t0);
      fill.style.width = `${Math.max(0, (left / total) * 100)}%`;
      timerBar.classList.toggle('low', left < 10000);
      if (!cobrou && left <= total / 2) {
        cobrou = true;
        const q = opponents()[Math.floor(Math.random() * opponents().length)];
        bubble(q, say(ids[q], 'cobra'));
      }
      const sec = Math.ceil(left / 1000);
      if (sec <= 5 && sec !== lastTick && sec > 0) {
        lastTick = sec;
        sfx.tick(sec <= 3);
      }
      if (left <= 0) {
        stopTimer();
        onTimeout();
      }
    }, 100);
  }
  function stopTimer() {
    if (timer) clearInterval(timer);
    timer = null;
    timerBar.hidden = true;
  }

  // ---------- jogada humana ----------
  let lastBronca = 0;
  function onTileTap(t, el) {
    if (!waiting || round.turn !== 0) return;
    const moves = round.legalMoves(0).filter((m) => m.tile === t);
    if (!moves.length) {
      sfx.error();
      haptic(40);
      track('gato');
      el.animate([{ transform: 'translateX(0)' }, { transform: 'translateX(-6px)' }, { transform: 'translateX(6px)' }, { transform: 'translateX(0)' }], { duration: 240 });
      const now = Date.now();
      if (now - lastBronca > 900) {
        lastBronca = now;
        const opp = opponents();
        const who = opp[Math.floor(Math.random() * opp.length)];
        bubble(who, line(ids[who], 'bronca'), 'bronca');
      }
      setHint(round.board.empty && round.mustStartWith ? `Tem que sair com a ${BUCHA_NAMES[round.mustStartWith.a]}.` : 'Essa não encaixa.', true, 1500);
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
    const forced = moves.some((m) => round.forcedClose(m.tile, m.side));
    if (forced) setHint('Numa ponta essa fecha o jogo: a mesa vota.', true, 4000);
    else if (closes) setHint('Essa fecha o jogo! Toque na ponta.', true, 4000);
    else setHint('Escolha a ponta.', false, 4000);
    boardView.showTargets(round.board, moves.map((m) => m.side), (side) => {
      const mv = moves.find((m) => m.side === side);
      commit(mv, handEls.get(t.uid));
    });
  }

  function deselect() {
    selected = null;
    hintLock = 0;
    boardView.hideTargets();
    boardView.fit();
    refreshHand();
    updateHint();
  }

  function commit(mv, el) {
    const rect = el ? el.getBoundingClientRect() : null;
    selected = null;
    hintLock = 0;
    boardView.hideTargets();
    const w = waiting;
    waiting = null;
    w && w({ mv, rect });
  }

  // ---------- votação do fechamento forçado ----------
  async function runVote(p, mv, alt) {
    sfx.vote();
    bubble(p, say(ids[p], 'vote_ask') || 'Vou fechar!');
    const votes = [];
    const rows = [];
    for (let q = 0; q < n; q++) {
      const st = h('span', { class: 'vote-st' }, q === p ? 'Fecha' : '...');
      rows.push(st);
      votes.push(q === p ? true : null);
    }
    const list = h(
      'div',
      { class: 'vote-list' },
      [...Array(n).keys()].map((q) => h('div', { class: `vote-row ${q === p ? 'closer' : ''}` }, h('span', {}, nameOf(q)), rows[q])),
    );
    const yesBtn = h('button', { class: 'btn ghost' }, 'Fecha e conta');
    const noBtn = h('button', { class: 'btn amber' }, 'Abre o jogo');
    const needMe = p !== 0;
    const m = modal(
      [
        h('div', { class: 'eyebrow' }, `${nameOf(p)} quer fechar`),
        h('h2', {}, 'Fecha ou abre?'),
        h('div', { class: 'res-batida' }, tileEl(mv.tile, { u: 26 })),
        h('p', {}, 'Essa pedra também cabia na outra ponta, onde o jogo seguiria aberto. A mesa decide.'),
        list,
        needMe ? h('div', { class: 'actions' }, yesBtn, noBtn) : h('p', { class: 'vote-wait' }, 'Votando...'),
      ],
      { dismissable: false, cls: 'result' },
    );
    const setVote = (q, v) => {
      votes[q] = v;
      rows[q].textContent = v ? 'Fecha' : 'Abre';
      rows[q].className = `vote-st ${v ? 'yes' : 'no'}`;
      sfx.pick();
    };
    // os outros votam um a um
    for (let q = 1; q < n; q++) {
      if (q === p) continue;
      await sleep(650);
      const c = CAST[ids[q]];
      const v = voteClose(round, q, c.skill);
      setVote(q, v);
      later(() => bubble(q, say(ids[q], v ? 'vote_yes' : 'vote_no')), 0);
    }
    if (needMe) {
      const mine = await new Promise((r) => {
        yesBtn.onclick = () => r(true);
        noBtn.onclick = () => r(false);
      });
      setVote(0, mine);
    }
    const yes = votes.filter(Boolean).length;
    const closed = yes > n / 2; // empate: o jogo continua aberto
    await sleep(500);
    m.el.append(h('div', { class: 'big', style: { fontSize: '30px', color: closed ? 'var(--chili-hi)' : 'var(--amber-hi)' } }, closed ? 'Fechou!' : 'Abriu!'));
    await sleep(1100);
    m.close();
    if (!closed) later(() => bubble(p, say(ids[p], 'vote_open')), 300);
    return closed ? mv : { ...mv, side: alt };
  }

  // ---------- fluxo ----------
  async function playMove(p, mv, fromRect) {
    if (match.rules.votacao) {
      const alt = round.forcedClose(mv.tile, mv.side);
      if (alt) mv = await runVote(p, mv, alt);
      if (dead) return null;
    }
    const res = round.play(p, mv.tile, mv.side);
    if (res.result) clearChatter();
    if (p !== 0) renderSeats();
    else refreshHand();
    boardView.board = round.board;
    const mania = p !== 0 && CAST[ids[p]].mania;
    const power = res.result ? 1.5 : mania && mania.slam ? 1.4 : isDouble(mv.tile) ? 1.15 : 1;
    await boardView.flyIn(res.rec, fromRect, { power });
    if (mania && mania.slam && !res.result) {
      shake(0.5);
      if (Math.random() < 0.3) bubble(p, say(ids[p], 'slam'), '', true);
    }
    updateCount();
    updateHint();
    if (!res.result) afterPlayChatter(p, mv.tile);
    if (res.result) {
      shake(res.result.type === 'batida' ? 1.6 : 1);
      sfx.slam();
      haptic(res.result.type === 'batida' ? 60 : 30);
    }
    return res;
  }

  async function animateDraw(p) {
    const from = monte.getBoundingClientRect();
    const target = p === 0 ? handEl.getBoundingClientRect() : seats[p].backs.getBoundingClientRect();
    const fly = backEl(14, 'flying');
    Object.assign(fly.style, { position: 'fixed', left: from.left + 'px', top: from.top + 'px', zIndex: 60 });
    document.getElementById('app').append(fly);
    sfx.drawTile();
    await fly
      .animate(
        [{ transform: 'translate(0,0) scale(1)' }, { transform: `translate(${target.left + target.width / 2 - from.left}px, ${target.top + target.height / 2 - from.top}px) scale(1.2)`, opacity: 0.4 }],
        { duration: 300 * speedFactor(), easing: 'ease-in' },
      )
      .finished.catch(() => {});
    fly.remove();
  }

  async function humanTurn() {
    let timedOut = false;
    let onTimeout = () => {};
    startTimer(() => {
      timedOut = true;
      const q = opponents()[0];
      later(() => bubble(q, say(ids[q], 'timeout')), 400);
      onTimeout();
    });
    try {
      // sem jogo: compra até achar (ou passa se o monte acabou)
      while (!round.legalMoves(0).length) {
        if (round.canDraw(0)) {
          setHint('Sem jogo: compre do monte.', true, 600);
          drawBtn.hidden = false;
          if (!timedOut) await new Promise((r) => ((drawWait = r), (onTimeout = r)));
          drawWait = null;
          drawBtn.hidden = true;
          if (dead) return;
          await animateDraw(0);
          round.draw(0);
          track('draw');
          refreshHand();
          renderSeats();
          updateCount();
          continue;
        }
        setHint('Sem jogo. Você passa.', true, 900);
        await sleep(900);
        if (dead) return;
        round.pass(0);
        track('pass');
        updateCount();
        bubble(0, 'Passo!');
        sfx.knock();
        haptic(20);
        passChatter(0);
        await sleep(500);
        return;
      }
      updateHint();
      const p = new Promise((r) => (waiting = r));
      onTimeout = () => {
        if (!waiting) return;
        const mv = chooseMove(round, 0, 0.5);
        commit(mv, handEls.get(mv.tile.uid));
      };
      if (timedOut) onTimeout();
      refreshHand();
      const { mv, rect } = await p;
      if (dead || !mv) return;
      stopTimer();
      await playMove(0, mv, rect);
      await sleep(450);
    } finally {
      stopTimer();
      drawBtn.hidden = true;
    }
  }

  function aiChoose(p) {
    const c = isMate(p) && params.partnerLevel ? params.partnerLevel : CAST[ids[p]];
    if (c.master) return chooseMoveMaster(round, p, c.master);
    return chooseMove(round, p, c.skill);
  }

  async function aiTurn(p) {
    setTurn(p, true);
    const mania = CAST[ids[p]].mania || {};
    // compra do monte até achar uma pedra que encaixa
    if (!round.legalMoves(p).length && round.canDraw(p)) {
      await sleep(600);
      if (Math.random() < 0.4) bubble(p, say(ids[p], 'draw_self'), '', true);
      while (!round.legalMoves(p).length && round.canDraw(p) && !dead) {
        await animateDraw(p);
        round.draw(p);
        renderSeats();
        updateCount();
        await sleep(260);
      }
      if (round.hands[p].length > 9 && Math.random() < 0.5) {
        const q = opponents().find((x) => x !== p) ?? 0;
        if (q) bubble(q, say(ids[q], 'draw_mock'), '', true);
      }
    }
    const t0 = performance.now();
    const mv = aiChoose(p);
    const nMoves = round.legalMoves(p).length;
    const slow = mania.slow || (mania.fast ? 0.6 : 1);
    const think = (nMoves <= 1 ? 850 : 1150 + Math.random() * 650) * slow;
    const spent = performance.now() - t0;
    await sleep(Math.max(0, think - spent / speedFactor()));
    if (dead) return;
    setTurn(p, false);
    if (!mv) {
      round.pass(p);
      updateCount();
      bubble(p, line(ids[p], 'pass'));
      sfx.knock();
      passChatter(p);
      await sleep(800);
      return;
    }
    const rect = seats[p].backs.lastElementChild?.getBoundingClientRect() || seats[p].who.getBoundingClientRect();
    await playMove(p, mv, rect);
    if (round.result) bubble(p, line(ids[p], 'bater'));
    else if (round.board.placed.length > 1 && isDouble(mv.tile) && Math.random() < (mania.buchaTalk ? 0.9 : 0.4)) bubble(p, line(ids[p], 'bucha'), '', true);
    await sleep(380);
  }

  // ---------- conversa de mesa ----------
  const chance = (x) => settings.conversa && Math.random() < x;
  const aheadOf = (t) => match.score[t] > Math.max(...match.score.filter((_, i) => i !== t));
  const behindOf = (t) => match.score[t] < Math.max(...match.score.filter((_, i) => i !== t));

  function roundStartChatter() {
    if (!settings.conversa) return;
    // rivalidade: quem já cruzou com você lembra
    if (match.roundNo === 1) {
      const rv = rivals();
      const opp = opponents().find((q) => rv[ids[q]] && rv[ids[q]].w + rv[ids[q]].l >= 2);
      if (opp) {
        const r = rv[ids[opp]];
        if (r.w !== r.l) return later(() => bubble(opp, say(ids[opp], r.w > r.l ? 'rival_owes' : 'rival_leads')), 900);
      }
      if (params.revanche) {
        const q = opponents()[0];
        return later(() => bubble(q, say(ids[q], 'revanche')), 900);
      }
    }
    if (!chance(0.6)) return;
    const others = [...Array(n).keys()].slice(1);
    const p = others[Math.floor(Math.random() * others.length)];
    const t = teamOf(p);
    const ev = match.roundNo > 1 && aheadOf(t) ? 'start_lead' : match.roundNo > 1 && behindOf(t) ? 'start_behind' : 'start';
    later(() => bubble(p, say(ids[p], ev), '', true), 700);
  }

  function passChatter(p) {
    if (!chance(0.55)) return;
    later(() => {
      if (p === 0 && n === 4 && Math.random() < 0.4) return bubble(2, say(ids[2], 'console_pass'), '', true);
      const mockers = [...Array(n).keys()].filter((q) => q !== 0 && teamOf(q) !== teamOf(p));
      if (mockers.length) {
        const q = mockers[Math.floor(Math.random() * mockers.length)];
        bubble(q, say(ids[q], 'mock_pass'), '', true);
      }
    }, 650);
  }

  function afterPlayChatter(p, tile) {
    if (!settings.conversa) return;
    const left = round.hands[p].length;
    if (left === 1) {
      if (p !== 0 && Math.random() < 0.6) return later(() => bubble(p, say(ids[p], 'one_left_self'), '', true), 300);
      if (n === 4 && teamOf(p) === 1 && Math.random() < 0.6) return later(() => bubble(2, say(ids[2], 'one_left_warn'), '', true), 400);
    }
    if (p === 0 && tile.a === 6 && tile.b === 6 && chance(0.5)) {
      const opp = opponents();
      const q = opp[Math.floor(Math.random() * opp.length)];
      later(() => bubble(q, say(ids[q], 'dump_sena'), '', true), 450);
    }
  }

  function openChat() {
    if (!settings.conversa) return;
    const list = h('div', { class: 'phrases' });
    const groups = n === 4 ? [['opp', 'Pra eles'], ['partner', `Pro ${partnerName}`], ['all', 'Pra mesa']] : [['opp', 'Pros adversários'], ['all', 'Pra mesa']];
    for (const [to, label] of groups) {
      list.append(h('div', { class: 'ph-group' }, label));
      for (const ph of PLAYER_PHRASES.filter((x) => x.to === to)) {
        list.append(h('button', { class: 'phrase', onClick: () => { m.close(); sendPhrase(ph); } }, ph.text));
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
    const replies = reactTo(ph, { usAhead: aheadOf(0), usBehind: behindOf(0) });
    const opp = opponents();
    replies.forEach((r, i) => {
      let q = r.p;
      if (n !== 4) q = q === 2 ? opp[0] : opp[(i + (q === 3 ? 1 : 0)) % opp.length];
      if (q >= n || q === 0) q = opp[0];
      setTimeout(() => !dead && bubble(q, r.text), 1100 + i * 1300);
    });
  }

  // Fim da rodada: as pedras dos outros viram na mesa, rapidinho (uma onda só, sem demora)
  async function revealHands() {
    let any = false;
    for (let p = 1; p < n; p++) {
      const s = seats[p];
      const hand = round.hands[p];
      if (!hand.length) continue;
      any = true;
      const u = s.pos === 'top' ? 15 : 13;
      const delay = (p - 1) * 90;
      s.backs.innerHTML = '';
      hand.forEach((t, i) => {
        const el = tileEl(t, { u, cls: 'reveal-flip' });
        el.style.animationDelay = `${(delay + i * 35) * speedFactor()}ms`;
        s.backs.append(el);
      });
    }
    if (any) {
      sfx.shuffle();
      await sleep(650);
    }
  }

  // ---------- embaralhar e distribuir ----------
  async function shuffleAndDeal() {
    for (let q = 1; q < n; q++) seats[q].backs.innerHTML = '';
    monte.hidden = true;
    handEl.innerHTML = '';
    handEls.clear();
    const area = boardView.el.getBoundingClientRect();
    const layer = h('div', { class: 'shuffle-layer' });
    Object.assign(layer.style, { left: area.left + 'px', top: area.top + 'px', width: area.width + 'px', height: area.height + 'px' });
    document.getElementById('app').append(layer);
    const u = 16;
    const cx = area.width / 2;
    const cy = area.height / 2;
    const tiles = [];
    for (let i = 0; i < 28; i++) {
      const t = backEl(u);
      const x = cx + ((i % 7) - 3) * (u + 4) - u / 2;
      const y = cy + (Math.floor(i / 7) - 2) * (u * 2 + 4);
      t.style.transform = `translate(${x}px, ${y}px)`;
      Object.assign(t.dataset, { x, y, r: 0 });
      layer.append(t);
      tiles.push(t);
    }
    const rnd = (a) => (Math.random() - 0.5) * a;
    const R = Math.min(area.width, area.height) * 0.32;
    for (let pass = 0; pass < 3 && !dead; pass++) {
      sfx.shuffle();
      const anims = tiles.map((t) => {
        const a = Math.random() * Math.PI * 2;
        const rr = R * (0.2 + Math.random() * 0.8);
        const x = cx + Math.cos(a) * rr - u / 2;
        const y = cy + Math.sin(a) * rr * 0.8 - u;
        const r = rnd(360);
        const from = `translate(${t.dataset.x}px, ${t.dataset.y}px) rotate(${t.dataset.r}deg)`;
        const to = `translate(${x}px, ${y}px) rotate(${r}deg)`;
        Object.assign(t.dataset, { x, y, r });
        t.style.transform = to;
        return t.animate([{ transform: from }, { transform: to }], { duration: 420 * speedFactor(), easing: 'cubic-bezier(.4,.1,.3,1)' }).finished;
      });
      await Promise.all(anims).catch(() => {});
    }
    const targets = [...Array(n).keys()].map((p) => {
      const el = p === 0 ? handEl : seats[p].backs;
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2 - area.left - u / 2, y: r.top + r.height / 2 - area.top - u };
    });
    sfx.shuffle();
    const deals = tiles.map((t, i) => {
      const from = t.style.transform;
      if (i >= n * 7) {
        // sobra: vira o monte no canto
        const mr = monte.getBoundingClientRect();
        const to = `translate(${mr.left - area.left + 10 + rnd(6)}px, ${mr.top - area.top + rnd(6)}px) rotate(${rnd(20)}deg)`;
        return t.animate([{ transform: from }, { transform: to, opacity: 0.6 }], { duration: 300 * speedFactor(), delay: i * 22 * speedFactor(), fill: 'forwards' }).finished;
      }
      const p = (round.starter + i) % n;
      const tg = targets[p];
      const to = `translate(${tg.x + rnd(30)}px, ${tg.y + rnd(10)}px) rotate(${seats[p] && seats[p].pos !== 'top' ? 90 : 0}deg) scale(.8)`;
      return t.animate([{ transform: from, opacity: 1 }, { transform: to, opacity: 0.2 }], { duration: 300 * speedFactor(), delay: i * 26 * speedFactor(), easing: 'ease-in', fill: 'forwards' }).finished;
    });
    await Promise.all(deals).catch(() => {});
    layer.remove();
  }

  async function voltaOJogo(p) {
    const doubles = round.hands[p].filter(isDouble);
    sfx.slam();
    shake(0.8);
    if (p !== 0) bubble(p, say(ids[p], 'voltou_owner'));
    const others = [...Array(n).keys()].filter((q) => q !== 0 && q !== p);
    others.forEach((q, i) => {
      const mate = teamOf(q) === teamOf(p);
      if (!mate) later(() => bubble(q, say(ids[q], 'voltou_angry')), 900 + i * 900);
      else if (Math.random() < 0.6) later(() => bubble(q, say(ids[q], 'voltou_relief')), 2400);
    });
    await new Promise((resolve) => {
      const m = modal(
        [
          h('div', { class: 'eyebrow' }, p === 0 ? 'Você pegou' : `${nameOf(p)} pegou`),
          h('h2', {}, `${doubles.length} buchas! Volta o jogo.`),
          h('div', { class: 'res-batida' }, round.hands[p].map((t) => tileEl(t, { u: 22 }))),
          h('p', {}, 'Com 5 buchas ou mais na mão, as pedras voltam pra mesa e embaralha de novo.'),
          h('div', { class: 'actions' }, h('button', { class: 'btn amber wide', onClick: () => { m.close(); resolve(); } }, 'Embaralhar de novo')),
        ],
        { dismissable: false, cls: 'result' },
      );
    });
  }

  async function playRound() {
    round = match.newRound();
    boardView.clear();
    boardView.prepareRound();
    boardView.rebuild(round.board);
    updateScore();
    setTurn(-1);
    setHint('Embaralhando...');
    await shuffleAndDeal();
    while (round.voltou != null && !dead) {
      await voltaOJogo(round.voltou);
      round = match.redeal();
      setHint('Embaralhando de novo...');
      await shuffleAndDeal();
    }
    if (dead) return;
    updateScore();
    round.hands[0].sort((x, y) => x.a - y.a || x.b - y.b);
    renderSeats();
    buildHand();
    refreshHand();
    countStrip.innerHTML = '';
    updateCount();
    roundStartChatter();
    const starter = round.starter === 0 ? 'Você começa' : `${nameOf(round.starter)} começa`;
    setHint(starter + (round.mustStartWith ? ` com a ${BUCHA_NAMES[round.mustStartWith.a]}.` : '.'), false, 2000);
    await sleep(round.starter === 0 ? 900 : 2200);
    while (!round.result && !dead) {
      setTurn(round.turn);
      if (round.turn === 0) await humanTurn();
      else await aiTurn(round.turn);
      if (dead) return;
    }
    setTurn(-1);
    refreshHand();
    const res = round.result;
    await revealHands();
    // a reação vem depois que a pedra assentou
    if (res.type === 'fechado') {
      const q = res.closer;
      if (q !== 0) bubble(q, say(ids[q], 'close_us'));
      setHint('Jogo fechado. Contando...', true, 3000);
    }
    await sleep(1200);
    match.applyResult(res);
    track('round', { won: res.team === 0, lost: res.team != null && res.team !== 0, batiEu: res.type === 'batida' && res.winner === 0, bucha: res.type === 'batida' && isDouble(res.tile), laelo: res.type === 'batida' && res.kinds.includes('laelo'), fechado: res.type === 'fechado' });
    const st = stats();
    st.rounds++;
    if (res.type === 'batida' && res.winner === 0) {
      st.batidas++;
      if (isDouble(res.tile)) st.buchas++;
    }
    saveStats(st);
    updateScore();
    if (res.team != null) {
      chalkDust(crosses[res.team]);
      pop(crosses[res.team], 'pop');
    }
    await showResult(res);
  }

  function quoteFor(res) {
    if (res.team == null || !settings.conversa) return null;
    const winners = [...Array(n).keys()].filter((q) => q !== 0 && teamOf(q) === res.team);
    const losers = [...Array(n).keys()].filter((q) => q !== 0 && teamOf(q) !== res.team);
    const pool = winners.length && Math.random() < 0.6 ? winners : losers;
    if (!pool.length) return null;
    const q = pool[Math.floor(Math.random() * pool.length)];
    const text = say(ids[q], teamOf(q) === res.team ? 'win_round' : 'lose_round');
    return h('p', { class: 'quote' }, `“${text}”`, h('span', {}, ` · ${nameOf(q)}`));
  }

  function showResult(res) {
    return new Promise((resolve) => {
      const us = res.team === 0;
      const parts = [];
      if (res.type === 'batida') {
        const kind = res.kinds.includes('bucha') ? 'Batida de bucha!' : res.kinds.includes('laelo') ? 'Lá e lô!' : 'Batida!';
        parts.push(h('div', { class: 'eyebrow' }, res.winner === 0 ? 'Você bateu' : `${nameOf(res.winner)} bateu`), h('h2', {}, kind));
        parts.push(h('div', { class: 'res-batida' }, tileEl(res.tile, { u: 34 })));
        if (isDouble(res.tile)) parts.push(h('p', {}, `Bateu com a ${BUCHA_NAMES[res.tile.a]}.`));
        if (res.kinds.includes('laelo')) parts.push(h('p', {}, 'A pedra entrava nos dois lados.'));
      } else {
        parts.push(h('div', { class: 'eyebrow' }, res.closer === 0 ? 'Você fechou o jogo' : `${nameOf(res.closer)} fechou o jogo`), h('h2', {}, 'Jogo fechado'));
        parts.push(h('div', { class: 'res-team' }, res.teamSums.map((v, t) => h('div', {}, h('small', {}, teamName(t)), String(v)))));
        const rows = h('div', { class: 'res-hands' });
        const order = n === 4 ? [0, 2, 1, 3] : [...Array(n).keys()];
        for (const p of order) {
          const tiles = h('div', { class: 'tiles' }, round.hands[p].map((t) => tileEl(t, { u: 13 })));
          rows.append(h('div', { class: 'res-row' }, h('span', { class: 'nm' }, nameOf(p)), tiles, h('span', { class: 'sum' }, String(round.hands[p].reduce((s, t) => s + pipSum(t), 0)))));
        }
        parts.push(rows);
        if (res.team == null) parts.push(h('p', {}, 'Empatou na contagem. Ninguém marca.'));
        else parts.push(h('p', {}, `Menos pontos na mão: ${n === 4 ? (us ? 'a rodada é nossa.' : 'deu eles.') : `ponto pr${res.team === 0 ? 'a você' : `o ${teamName(res.team)}`}.`}`));
      }
      if (res.team != null) {
        const who = n === 4 ? (us ? 'pra nós' : 'pra eles') : us ? 'pra você' : `pro ${teamName(res.team)}`;
        parts.push(h('div', { class: 'big', style: { color: us ? 'var(--amber-hi)' : 'var(--chili-hi)' } }, `+${res.points} ${who}`));
        if (us) {
          sfx.win();
          confetti(50);
        } else sfx.lose();
      }
      const q = quoteFor(res);
      if (q) parts.push(q);
      parts.push(h('div', { class: 'score-line' }, match.score.map((v, t) => `${teamName(t)} ${v}`).join(' · ')));
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
    for (const q of opponents()) addRival(ids[q], won);
    // aposta: cada adversário paga (ou recebe) o valor
    const payers = n === 4 ? 1 : n - 1;
    const delta = stake ? (won ? stake * payers : -stake) : 0;
    if (delta) setWallet(wallet() + delta);
    if (won) {
      confetti(140);
      sfx.win();
      if (delta) sfx.coins();
    } else sfx.lose();
    const canDouble = stake && wallet() >= stake * 2;
    const leave = async (fn) => {
      m.close();
      await maybeInterstitial();
      fn();
    };
    const dobra = won && delta > 0
      ? h('button', { class: 'btn blue wide' }, `Ver um vídeo e dobrar: +${money(delta)}`)
      : null;
    if (dobra) {
      dobra.addEventListener('click', async () => {
        dobra.disabled = true;
        if (await showRewarded()) {
          setWallet(wallet() + delta);
          sfx.coins();
          dobra.textContent = `Prêmio dobrado! +${money(delta)}`;
        } else dobra.disabled = false;
      });
    }
    const again = () => go('classic', { ...params, players: n, opps, stake: canDouble ? stake * 2 : Math.min(stake, wallet()), revanche: true });
    const m = modal(
      [
        h('div', { class: 'eyebrow' }, 'Fim da partida'),
        h('h2', {}, won ? (n === 4 ? 'A mesa é nossa!' : 'Você ganhou!') : n === 4 ? 'Hoje deu eles.' : `Deu ${teamName(match.winnerTeam())}.`),
        h('div', { class: 'big' }, match.score.join(' × ')),
        delta ? h('div', { class: `money-delta ${won ? 'up' : 'down'}` }, `${won ? '+' : '−'}${money(Math.abs(delta))}`) : null,
        h('p', {}, `Carteira: ${money(wallet())}`),
        dobra,
        h(
          'div',
          { class: 'actions col' },
          stake
            ? h('button', { class: 'btn chili wide', disabled: !wallet(), onClick: () => leave(again) }, canDouble ? `Revanche valendo ${money(stake * 2)}` : 'Revanche')
            : null,
          h('div', { class: 'actions' },
            h('button', { class: 'btn ghost', onClick: () => leave(() => go('home')) }, 'Sair'),
            h('button', { class: 'btn amber', onClick: () => leave(() => go('classic', { players: n, stake: Math.min(stake, wallet()) })) }, 'Nova mesa'),
          ),
        ),
      ],
      { dismissable: false, cls: 'result' },
    );
  }

  function confirmExit() {
    const m = modal([
      h('h2', {}, 'Levantar da mesa?'),
      h('p', {}, mode === 'career' ? 'Se sair agora, conta como derrota neste jogo do campeonato.' : mode === 'desafio' ? 'Sair agora conta como desafio perdido hoje.' : mode === 'online' ? (stake ? `Quem levanta perde o valor da mesa (${money(stake)}) e fica 5 minutos sem entrar em mesa valendo dinheiro.` : 'Sair no meio conta como derrota.') : stake ? `Quem levanta perde o valor da mesa (${money(stake)}).` : 'A partida em andamento vai ser perdida.'),
      h(
        'div',
        { class: 'actions' },
        h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Ficar'),
        h('button', {
          class: 'btn chili',
          onClick: () => {
            m.close();
            if (mode !== 'quick' && params.onEnd) {
              dead = true;
              params.onEnd(false, match, true);
            } else {
              if (stake) setWallet(wallet() - stake);
              go('home');
            }
          },
        }, 'Sair'),
      ),
    ]);
  }

  (async () => {
    await sleep(200);
    while (!dead && !match.isOver()) await playRound();
    if (dead) return;
    track('match', { won: match.winnerTeam() === 0, mode, players: n, stake });
    if (mode !== 'quick' && params.onEnd) {
      for (const q of opponents()) addRival(ids[q], match.winnerTeam() === 0);
      params.onEnd(match.winnerTeam() === 0, match);
    } else showQuickEnd();
  })();

  return {
    destroy() {
      dead = true;
      stopTimer();
      clearChatter();
      boardView.destroy();
      if (waiting) waiting({ mv: null });
      if (drawWait) drawWait();
    },
  };
}
