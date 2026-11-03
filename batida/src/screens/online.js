import { h, modal, store, toast } from '../ui/dom.js';
import { sfx } from '../ui/audio.js';
import { confetti } from '../ui/fx.js';
import { go, settings, saveSettings, wallet, setWallet, money } from '../app.js';
import { guest } from '../classic/cast.js';
import { LocalBackend, WsBackend } from '../online/backend.js';
import { iconBtn, walletChip, seg } from './home.js';

// Estado que sobrevive enquanto você entra e sai da mesa de jogo.
const S = { backend: null, me: null, room: null, tab: 'rapido', online: 0, torneio: null };

const ICON = {
  lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>',
  crown: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 8l4.5 4L12 5l4.5 7L21 8l-2 11H5z"/></svg>',
  bot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="5" y="8" width="14" height="11" rx="3"/><path d="M12 4v4M9 13h.01M15 13h.01"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>',
  wifi: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M3 9a13 13 0 0 1 18 0M6.5 12.5a8 8 0 0 1 11 0M10 16a3 3 0 0 1 4 0"/><circle cx="12" cy="19" r="1" fill="currentColor"/></svg>',
};

function makeBackend() {
  const url = (settings.servidor || '').trim();
  return url ? new WsBackend(url) : new LocalBackend();
}

export function onlineScreen(stage, params = {}) {
  let dead = false;
  let off = null;
  let lobbyTimer = null;
  let q = '';

  const show = (fn) => {
    if (dead) return;
    clearInterval(lobbyTimer);
    stage.innerHTML = '';
    fn();
  };

  // ---------- entrada: apelido e conexão ----------
  async function enter() {
    const nick = store.get('nick', '');
    if (!nick) return askNick(enter);
    if (S.backend && S.me) return afterConnect();
    show(() => stage.append(top('Conectando...'), h('div', { class: 'online-wait' }, h('div', { class: 'spinner' }), h('p', {}, 'Procurando mesas abertas...'))));
    S.backend = makeBackend();
    const r = await S.backend.connect(nick);
    if (dead) return;
    if (!r.ok) {
      show(() => stage.append(top('Online'), h('div', { class: 'online-wait' }, h('p', {}, r.error), h('button', { class: 'btn amber', onClick: () => { S.backend = null; enter(); } }, 'Tentar de novo'), h('button', { class: 'btn ghost', onClick: serverModal }, 'Trocar servidor'))));
      S.backend = null;
      return;
    }
    S.me = { uid: r.data.uid, name: nick };
    S.online = r.data.online || 0;
    afterConnect();
  }

  function afterConnect() {
    off && off();
    off = S.backend.on(onEvent);
    if (S.room) roomView();
    else lobby();
  }

  function onEvent(ev) {
    if (dead) return;
    if (ev.type === 'room') {
      S.room = ev.room;
      if (current === 'room') roomView();
    } else if (ev.type === 'lobby' && current === 'lobby') refreshList();
    else if (ev.type === 'closed') {
      S.room = null;
      toast(ev.why || 'A sala fechou.');
      lobby();
    } else if (ev.type === 'kicked') {
      S.room = null;
      toast('Você foi tirado da sala.');
      lobby();
    } else if (ev.type === 'host' && ev.me) {
      sfx.vote();
      toast('Agora você é o dono da sala.');
    } else if (ev.type === 'start') {
      S.room = ev.room;
      launch(ev.room);
    }
  }

  function askNick(then) {
    const input = h('input', { id: 'nick', class: 'text-in', maxlength: '16', placeholder: 'Seu apelido na mesa', value: store.get('nick', '') });
    const m = modal(
      [
        h('h2', {}, 'Como te chamam no boteco?'),
        h('p', {}, 'É o nome que os outros vão ver na mesa.'),
        input,
        h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: () => { m.close(); go('home'); } }, 'Voltar'), h('button', {
          class: 'btn amber',
          onClick: () => {
            const v = input.value.trim().replace(/\s+/g, ' ');
            if (v.length < 2) return input.focus();
            store.set('nick', v);
            m.close();
            then();
          },
        }, 'Entrar')),
      ],
      { dismissable: false },
    );
    setTimeout(() => input.focus(), 50);
  }

  function serverModal() {
    const input = h('input', { id: 'srv', class: 'text-in', placeholder: 'wss://seu-servidor.com', value: settings.servidor || '' });
    const m = modal([
      h('h2', {}, 'Servidor online'),
      h('p', {}, 'Deixe vazio para usar o servidor de teste, com gente simulada. Quando o servidor de verdade estiver no ar, coloque o endereço aqui.'),
      input,
      h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Cancelar'), h('button', {
        class: 'btn amber',
        onClick: () => {
          settings.servidor = input.value.trim();
          saveSettings();
          if (S.backend && S.backend.disconnect) S.backend.disconnect();
          Object.assign(S, { backend: null, me: null, room: null });
          m.close();
          enter();
        },
      }, 'Salvar')),
    ]);
  }

  let current = '';
  function top(title, sub) {
    return h(
      'div',
      { class: 'topbar' },
      iconBtn('back', 'Voltar', () => (current === 'room' ? confirmLeave() : exitOnline())),
      h('div', { class: 'grow' }, h('div', { class: 'eyebrow' }, sub || 'Online'), h('div', { class: 'title-sm' }, title)),
      walletChip(),
    );
  }

  function exitOnline() {
    go('home');
  }

  // ---------- saguão ----------
  const listEl = h('div', { class: 'room-list' });
  async function refreshList() {
    if (!S.backend) return;
    const r = await S.backend.list({ kind: S.tab, q });
    if (dead || current !== 'lobby' || !r.ok) return;
    listEl.innerHTML = '';
    if (!r.data.length) {
      listEl.append(h('div', { class: 'empty-state' }, h('b', {}, q ? 'Nenhuma sala com esse nome.' : 'Nenhuma sala aberta agora.'), h('span', {}, 'Crie a sua e chame a galera, ou complete com bots.')));
      return;
    }
    for (const s of r.data) listEl.append(roomCard(s));
  }

  function roomCard(s) {
    const dots = h('div', { class: 'seat-dots', 'aria-label': `${s.humans} pessoas, ${s.bots} bots, ${s.free} lugares vazios` });
    for (let i = 0; i < s.humans; i++) dots.append(h('i', { class: 'h' }));
    for (let i = 0; i < s.bots; i++) dots.append(h('i', { class: 'b' }));
    for (let i = 0; i < s.free; i++) dots.append(h('i'));
    const price = s.kind === 'rapido' ? (s.stake ? `Valendo ${money(s.stake)}` : 'Sem aposta') : `Inscrição ${money(s.fee)}`;
    const b = h(
      'button',
      { class: 'room-card' },
      h('div', { class: 'rc-main' }, h('div', { class: 'rc-name' }, s.private ? h('span', { class: 'lock', html: ICON.lock }) : null, s.name), h('div', { class: 'rc-sub' }, `${s.host} · ${s.kind === 'rapido' ? (s.capacity === 4 ? 'dupla' : `${s.capacity} jogadores`) : 'campeonato, 4 duplas'}`)),
      h('div', { class: 'rc-side' }, dots, h('div', { class: 'rc-price' }, price)),
    );
    b.addEventListener('click', () => joinRoom(s.code, s));
    return b;
  }

  function lobby() {
    current = 'lobby';
    S.room = null;
    show(() => {
      const search = h('input', { id: 'room-q', class: 'text-in search', placeholder: 'Buscar sala, dono ou código', value: q });
      let t;
      search.addEventListener('input', () => {
        clearTimeout(t);
        t = setTimeout(() => {
          q = search.value;
          refreshList();
        }, 250);
      });
      const tabs = seg([['rapido', 'Jogo rápido'], ['campeonato', 'Campeonato']], S.tab, (v) => {
        S.tab = v;
        refreshList();
      });
      stage.append(
        top('Salão online'),
        h('div', { class: 'online-status' }, h('span', { class: 'live', html: ICON.wifi }), `${S.online} jogando agora`, h('button', { class: 'link-btn', onClick: serverModal }, S.backend.label)),
        h('div', { class: 'lobby-tabs' }, tabs),
        h('div', { class: 'search-row' }, h('span', { class: 'search-ico', html: ICON.search }), search, h('button', { class: 'btn ghost small', onClick: codeModal }, 'Código')),
        listEl,
        h('div', { class: 'lobby-actions' }, h('button', { class: 'btn amber wide', onClick: createModal }, S.tab === 'rapido' ? 'Criar sala de jogo rápido' : 'Criar campeonato')),
      );
      refreshList();
      lobbyTimer = setInterval(refreshList, 4000);
    });
  }

  function codeModal() {
    const input = h('input', { id: 'code', class: 'text-in code', maxlength: '4', placeholder: 'ABCD' });
    const m = modal([
      h('h2', {}, 'Entrar com código'),
      h('p', {}, 'Salas privadas só aparecem pelo código. Peça para o dono da sala.'),
      input,
      h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Cancelar'), h('button', { class: 'btn amber', onClick: () => { m.close(); joinRoom(input.value.trim().toUpperCase()); } }, 'Entrar')),
    ]);
    setTimeout(() => input.focus(), 50);
  }

  async function joinRoom(code, s) {
    if (s && s.kind === 'rapido' && s.stake > wallet()) return toast(`Essa mesa vale ${money(s.stake)}. Falta dinheiro.`);
    if (s && s.kind === 'campeonato' && s.fee > wallet()) return toast(`A inscrição é ${money(s.fee)}. Falta dinheiro.`);
    const r = await S.backend.join(code);
    if (dead) return;
    if (!r.ok) return toast(r.error);
    sfx.pick();
    S.room = r.data;
    roomView();
  }

  function createModal() {
    const isCamp = S.tab === 'campeonato';
    const o = { kind: S.tab, players: 4, stake: 0, fee: 50, private: false, name: `Mesa do ${S.me.name}` };
    const name = h('input', { id: 'room-name', class: 'text-in', maxlength: '28', value: o.name });
    const priv = h('input', { type: 'checkbox', id: 'room-priv', role: 'switch' });
    const w = wallet();
    const m = modal([
      h('h2', {}, isCamp ? 'Novo campeonato' : 'Nova sala'),
      h('label', { class: 'field' }, h('span', {}, 'Nome da sala'), name),
      isCamp
        ? h('div', { class: 'toggle-row' }, h('div', {}, h('div', { class: 't' }, 'Inscrição'), h('div', { class: 'd' }, 'A dupla campeã leva tudo')), seg([20, 50, 100, 200].map((v) => [v, `R$${v}`, v > w]), o.fee, (v) => (o.fee = v)))
        : h('div', { class: 'toggle-row' }, h('div', {}, h('div', { class: 't' }, 'Na mesa')), seg([[2, '2'], [3, '3'], [4, '4 (dupla)']], o.players, (v) => (o.players = v))),
      isCamp ? null : h('div', { class: 'toggle-row' }, h('div', {}, h('div', { class: 't' }, 'Aposta')), seg([0, 10, 20, 50, 100].map((v) => [v, v ? `R$${v}` : 'Sem', v > w]), o.stake, (v) => (o.stake = v))),
      h('div', { class: 'toggle-row' }, h('label', { for: 'room-priv' }, h('div', { class: 't' }, 'Sala privada'), h('div', { class: 'd' }, 'Só entra quem tiver o código')), h('span', { class: 'switch' }, priv, h('span'))),
      h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Cancelar'), h('button', {
        class: 'btn amber',
        onClick: async () => {
          o.name = name.value.trim() || o.name;
          o.private = priv.checked;
          m.close();
          const r = await S.backend.create(o);
          if (!r.ok) return toast(r.error);
          S.room = r.data;
          roomView();
        },
      }, 'Abrir sala')),
    ]);
  }

  // ---------- dentro da sala ----------
  function roomView() {
    current = 'room';
    const room = S.room;
    if (!room) return lobby();
    const me = S.me.uid;
    const isHost = room.hostId === me;
    const mySeat = room.seats.findIndex((s) => s && s.uid === me);
    const mine = room.seats[mySeat];
    show(() => {
      const seatEl = (s, i) => {
        const cls = ['seat-card', s ? (s.bot ? 'bot' : 'human') : 'empty', s && s.uid === me ? 'me' : '', s && s.uid === room.hostId ? 'host' : ''].join(' ');
        const badges = [];
        if (s && s.uid === room.hostId) badges.push(h('span', { class: 'badge host', html: ICON.crown + 'Dono' }));
        if (s && s.bot) badges.push(h('span', { class: 'badge', html: ICON.bot + 'Bot' }));
        if (s && !s.bot && s.uid !== room.hostId) badges.push(h('span', { class: `badge ${s.ready ? 'ok' : ''}` }, s.ready ? 'Pronto' : 'Esperando'));
        const el = h('button', { class: cls }, h('div', { class: 'sc-name' }, s ? (s.uid === me ? `${s.name} (você)` : s.name) : 'Lugar vazio'), h('div', { class: 'sc-badges' }, badges));
        el.addEventListener('click', () => seatMenu(s, i));
        return el;
      };
      let seatsBox;
      if (room.kind === 'campeonato') {
        seatsBox = h('div', { class: 'duplas' });
        for (let d = 0; d < 4; d++) seatsBox.append(h('div', { class: `dupla ${Math.floor(mySeat / 2) === d ? 'mine' : ''}` }, h('div', { class: 'dupla-n' }, `Dupla ${d + 1}`), seatEl(room.seats[2 * d], 2 * d), seatEl(room.seats[2 * d + 1], 2 * d + 1)));
      } else if (room.capacity === 4) {
        seatsBox = h('div', { class: 'duplas two' });
        for (const d of [0, 1]) seatsBox.append(h('div', { class: `dupla ${mySeat % 2 === d ? 'mine' : ''}` }, h('div', { class: 'dupla-n' }, d === 0 ? 'Dupla A' : 'Dupla B'), seatEl(room.seats[d], d), seatEl(room.seats[d + 2], d + 2)));
      } else {
        seatsBox = h('div', { class: 'seat-grid' }, room.seats.map(seatEl));
      }
      const info = room.kind === 'rapido' ? (room.stake ? `Valendo ${money(room.stake)} · até 4 pontos` : 'Sem aposta · até 4 pontos') : `Inscrição ${money(room.fee)} · prêmio ${money(room.fee * 8)} para a dupla campeã`;
      const codeChip = h('button', { class: 'code-chip', 'aria-label': `Código da sala ${room.code}`, onClick: () => copyCode(room.code) }, h('small', {}, room.private ? 'Privada · código' : 'Código'), room.code);
      const log = h('div', { class: 'room-log' }, room.log.slice(-4).map((l) => h('div', {}, l.text)));
      const canStart = room.seats.filter((s) => s && !s.bot).every((s) => s.uid === room.hostId || s.ready);
      const actions = h('div', { class: 'room-actions' });
      if (isHost) {
        actions.append(
          h('div', { class: 'row2' }, h('button', { class: 'btn ghost small', onClick: () => call('fillBots') }, 'Completar com bots'), h('button', { class: 'btn ghost small danger', onClick: confirmDelete }, 'Excluir sala')),
          h('button', { class: 'btn amber wide', disabled: !canStart, onClick: () => startGame() }, canStart ? 'Começar' : 'Esperando todos ficarem prontos'),
        );
      } else {
        actions.append(h('button', { class: `btn wide ${mine && mine.ready ? 'ghost' : 'amber'}`, onClick: () => call('ready', !(mine && mine.ready)) }, mine && mine.ready ? 'Não estou pronto' : 'Estou pronto'));
      }
      stage.append(
        top(room.name, room.kind === 'rapido' ? 'Sala de jogo rápido' : 'Campeonato online'),
        h('div', { class: 'room-head' }, h('div', { class: 'room-info' }, info), codeChip),
        seatsBox,
        log,
        actions,
      );
    });
  }

  function seatMenu(s, i) {
    const room = S.room;
    const me = S.me.uid;
    const isHost = room.hostId === me;
    const opts = [];
    if (!s || s.bot) opts.push(['Sentar aqui', () => call('moveSeat', i)]);
    if (isHost && !s) opts.push(['Colocar um bot', () => call('addBot', i)]);
    if (isHost && s && s.uid !== me) opts.push([s.bot ? 'Tirar o bot' : `Tirar ${s.name} da mesa`, () => call('kick', i)]);
    if (!opts.length) return;
    const m = modal([h('h2', {}, s ? s.name : 'Lugar vazio'), h('div', { class: 'phrases' }, opts.map(([label, fn]) => h('button', { class: 'phrase', onClick: () => { m.close(); fn(); } }, label)))], { cls: 'chat-sheet' });
  }

  async function call(op, arg) {
    const r = await S.backend[op](arg);
    if (dead) return;
    if (!r.ok) return toast(r.error);
    if (r.data && r.data.seats) {
      S.room = r.data;
      roomView();
    }
  }

  function copyCode(code) {
    try {
      navigator.clipboard.writeText(code).then(() => toast(`Código ${code} copiado`), () => toast(`Código: ${code}`));
    } catch {
      toast(`Código: ${code}`);
    }
  }

  function confirmLeave() {
    const isHost = S.room && S.room.hostId === S.me.uid;
    const m = modal([
      h('h2', {}, 'Sair da sala?'),
      h('p', {}, isHost ? 'Você é o dono. Se sair, outra pessoa da sala vira dona. Se não tiver ninguém, a sala fecha.' : 'Você volta para o salão.'),
      h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Ficar'), h('button', { class: 'btn chili', onClick: async () => { m.close(); await S.backend.leave(); S.room = null; lobby(); } }, 'Sair')),
    ]);
  }

  function confirmDelete() {
    const m = modal([
      h('h2', {}, 'Excluir a sala?'),
      h('p', {}, 'Todo mundo volta para o salão.'),
      h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Cancelar'), h('button', { class: 'btn chili', onClick: async () => { m.close(); await S.backend.remove(); S.room = null; lobby(); } }, 'Excluir')),
    ]);
  }

  async function startGame() {
    const r = await S.backend.start();
    if (!r.ok) return toast(r.error);
  }

  // ---------- partida ----------
  function seatIds(room) {
    return room.seats.map((s) => (s.uid === S.me.uid ? 'voce' : guest(`on_${s.uid}`, s.name, s.bot ? 0.55 : 0.6 + Math.random() * 0.25)));
  }

  function launch(room) {
    if (room.kind === 'campeonato') return startTorneio(room);
    const n = room.capacity;
    const ids = seatIds(room);
    const k = room.seats.findIndex((s) => s.uid === S.me.uid);
    const order = [...Array(n).keys()].map((i) => ids[(k + i) % n]);
    if (room.stake > wallet()) {
      toast('Falta dinheiro para a aposta dessa mesa.');
      return S.backend.leave().then(() => lobby());
    }
    go('classic', {
      mode: 'online',
      players: n,
      opps: n === 4 ? [order[1], order[3]] : order.slice(1),
      partner: n === 4 ? order[2] : undefined,
      stake: room.stake,
      rules: { players: n, buchaVale2: true, laeloVale2: true, comecaSena: true, cincoBuchas: true, votacao: true, metaPontos: 4 },
      onEnd: (won, match, quit) => {
        const payers = n === 4 ? 1 : n - 1;
        const delta = room.stake ? (won ? room.stake * payers : -room.stake) : 0;
        if (delta) setWallet(wallet() + delta);
        S.backend.finish(quit ? 'Alguém levantou no meio do jogo.' : `Fim de jogo: ${match.score.join(' × ')}`).then((r) => {
          if (r && r.ok && r.data) S.room = r.data;
          go('online', { back: { won, delta, quit } });
        });
      },
    });
  }

  // Campeonato online: 4 duplas, semifinais e final
  function startTorneio(room) {
    if (room.fee > wallet()) {
      toast('Falta dinheiro para a inscrição.');
      return S.backend.leave().then(() => lobby());
    }
    setWallet(wallet() - room.fee);
    const ids = seatIds(room);
    const duplas = [0, 1, 2, 3].map((d) => ({ ids: [ids[2 * d], ids[2 * d + 1]], names: [room.seats[2 * d].name, room.seats[2 * d + 1].name] }));
    const myD = Math.floor(room.seats.findIndex((s) => s.uid === S.me.uid) / 2);
    S.torneio = { room, duplas, myD, fase: 'semi', semis: [[0, 1], [2, 3]], winners: [], out: false };
    torneioView();
  }

  function torneioView(msg) {
    current = 'torneio';
    const T = S.torneio;
    show(() => {
      const nm = (d) => (d === T.myD ? `Você e ${T.duplas[d].names.find((x) => x !== S.me.name) || 'parceiro'}` : T.duplas[d].names.join(' e '));
      const line = (a, b, w, label) => h('div', { class: `match-row ${w == null ? 'next' : 'done'}` }, h('div', { class: 'fase' }, label), h('div', { class: 'opp' }, h('div', { class: 'opp-names' }, h('b', {}, `${nm(a)}  ×  ${nm(b)}`)), h('div', { class: 'state' }, w == null ? '' : `${nm(w)} venceu`)));
      const box = h('div', { class: 'bracket' });
      box.append(line(T.semis[0][0], T.semis[0][1], T.winners[0], 'Semifinal 1'), line(T.semis[1][0], T.semis[1][1], T.winners[1], 'Semifinal 2'));
      if (T.final) box.append(line(T.final[0], T.final[1], T.champion, 'Final'));
      if (msg) box.append(h('p', { class: 'quote' }, msg));
      const act = h('div', { class: 'career-actions' });
      if (T.champion != null || T.out) act.append(h('button', { class: 'btn amber wide', onClick: () => { S.torneio = null; S.backend.finish(T.champion != null ? `Campeões: ${nm(T.champion)}` : ''); go('online'); } }, 'Voltar para a sala'));
      else act.append(h('button', { class: 'btn amber wide', onClick: playTorneio }, T.fase === 'final' ? 'Jogar a final' : 'Jogar a semifinal'));
      stage.append(top(T.room.name, 'Campeonato online'), box, act);
    });
  }

  function playTorneio() {
    const T = S.torneio;
    const pair = T.fase === 'final' ? T.final : T.semis.find((p) => p.includes(T.myD));
    const opp = pair[0] === T.myD ? pair[1] : pair[0];
    const mine = T.duplas[T.myD].ids;
    const partner = mine[0] === 'voce' ? mine[1] : mine[0];
    go('classic', {
      mode: 'online',
      players: 4,
      opps: T.duplas[opp].ids,
      partner,
      rules: { players: 4, buchaVale2: true, laeloVale2: true, comecaSena: true, cincoBuchas: true, votacao: true, metaPontos: 4 },
      onEnd: (won) => {
        if (T.fase === 'semi') {
          const mineIdx = T.semis.findIndex((p) => p.includes(T.myD));
          T.winners[mineIdx] = won ? T.myD : opp;
          const other = T.semis[1 - mineIdx];
          T.winners[1 - mineIdx] = other[Math.random() < 0.5 ? 0 : 1]; // a outra semi é simulada
          T.final = [T.winners[0], T.winners[1]];
          if (won) T.fase = 'final';
          else {
            T.out = true;
            T.champion = T.final[Math.random() < 0.5 ? 0 : 1];
          }
        } else {
          T.champion = won ? T.myD : opp;
          if (won) setWallet(wallet() + T.room.fee * 4);
        }
        go('online', { torneio: true, won });
      },
    });
  }

  // ---------- boot ----------
  if (params.torneio && S.torneio) {
    const T = S.torneio;
    current = 'torneio';
    off = S.backend.on(onEvent);
    if (T.champion === T.myD) {
      confetti(160);
      sfx.coins();
      torneioView(`Campeões! +${money(T.room.fee * 4)} pra cada um da dupla.`);
    } else torneioView(T.out || T.champion != null ? 'Fim do campeonato pra gente.' : 'Passamos! Agora é a final.');
  } else if (params.back && S.backend) {
    off = S.backend.on(onEvent);
    const b = params.back;
    roomView();
    if (b.delta) toast(`${b.won ? 'Ganhou' : 'Perdeu'} ${money(Math.abs(b.delta))}`);
  } else enter();

  return {
    destroy() {
      dead = true;
      clearInterval(lobbyTimer);
      off && off();
    },
  };
}
