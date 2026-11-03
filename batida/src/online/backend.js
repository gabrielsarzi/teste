// Conexão do modo online. Duas implementações com a mesma interface:
//  - LocalBackend: servidor simulado dentro do jogo (gente "de mentira" entrando e saindo),
//    serve para testar todo o fluxo sem internet.
//  - WsBackend: fala com o servidor de verdade (pasta server/) por WebSocket.
import { RoomService, RoomError, summary } from './rooms.js';
import { localRanking } from './ranking.js';

const ROOM_REPLIES = ['Bora!', 'Partiu!', 'Pronto aqui.', 'Só esperando vocês.', 'Boa sorte pra todo mundo.', 'Hoje eu tô com sorte.', 'Pode completar com bot.', 'Valendo a cerveja!'];

const FAKE = ['Marcão', 'Dudu_RJ', 'Tati', 'Seu Lourival', 'NinjaDoDominó', 'Kelly', 'Jorginho', 'Paty', 'Gordão', 'Lucas_SP', 'Vovó Zilda', 'Bigode', 'Raí', 'Fabinho', 'Cris', 'Mineiro'];
const ROOM_NAMES = ['Mesa do fundo', 'Só os bons', 'Valendo a cerveja', 'Treino', 'Bate e volta', 'Galera do bar', 'Sem choro', 'Dupla raiz'];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

export class LocalBackend {
  constructor() {
    this.svc = new RoomService();
    this.me = null;
    this.handlers = new Set();
    this.fakes = FAKE.map((name, i) => ({ uid: `f${i}`, name, busy: false }));
    this.timer = null;
    this.svc.on((ev) => this._relay(ev));
  }

  get label() {
    return 'Servidor de teste (simulado)';
  }

  on(fn) {
    this.handlers.add(fn);
    return () => this.handlers.delete(fn);
  }

  _emit(ev) {
    for (const fn of this.handlers) fn(ev);
  }

  _relay(ev) {
    const mine = this.me && this.svc.roomOf(this.me.uid);
    if (ev.type === 'room' && mine && ev.room.id === mine.id) this._emit({ type: 'room', room: clone(ev.room) });
    else if (ev.type === 'closed' && this.myRoomId === ev.roomId) {
      this.myRoomId = null;
      this._emit({ type: 'closed', why: ev.why });
    } else if (ev.type === 'kicked' && this.me && ev.uid === this.me.uid) {
      this.myRoomId = null;
      this._emit({ type: 'kicked' });
    } else if (ev.type === 'host' && this.myRoomId === ev.roomId) this._emit({ type: 'host', hostId: ev.hostId, me: ev.hostId === this.me.uid });
    else if (ev.type === 'lobby') this._emit({ type: 'lobby' });
    if (mine) this.myRoomId = mine.id;
  }

  async _net(fn) {
    await wait(120 + Math.random() * 220); // latência de rede
    try {
      return { ok: true, data: fn() };
    } catch (e) {
      if (e instanceof RoomError) return { ok: false, error: e.message };
      throw e;
    }
  }

  async connect(nick) {
    await wait(400);
    this.me = { uid: 'me', name: nick };
    if (!this.seeded) this._seed();
    this._tick();
    return { ok: true, data: { uid: 'me', online: 140 + Math.floor(Math.random() * 90) } };
  }

  disconnect() {
    clearTimeout(this.timer);
    this.timer = null;
    if (this.me) this.svc.leave(this.me.uid);
    this.myRoomId = null;
  }

  list(q) {
    return this._net(() => this.svc.list(q));
  }
  create(opts) {
    return this._net(() => clone(this.svc.create(this.me, opts)));
  }
  join(code) {
    return this._net(() => clone(this.svc.join(this.me, code)));
  }
  leave() {
    return this._net(() => {
      this.svc.leave(this.me.uid);
      this.myRoomId = null;
    });
  }
  kick(seat) {
    return this._net(() => clone(this.svc.kick(this.me.uid, seat)));
  }
  addBot(seat) {
    return this._net(() => clone(this.svc.addBot(this.me.uid, seat)));
  }
  fillBots() {
    return this._net(() => clone(this.svc.fillBots(this.me.uid)));
  }
  ready(v) {
    return this._net(() => clone(this.svc.setReady(this.me.uid, v)));
  }
  moveSeat(i) {
    return this._net(() => clone(this.svc.moveSeat(this.me.uid, i)));
  }
  remove() {
    return this._net(() => this.svc.remove(this.me.uid));
  }
  say(text) {
    return this._net(() => {
      const r = this.svc.say(this.me.uid, text);
      // alguém da sala responde
      const others = r.seats.filter((s) => s && !s.bot && s.uid !== this.me.uid);
      if (others.length && Math.random() < 0.8) {
        const o = others[Math.floor(Math.random() * others.length)];
        setTimeout(() => this.svc.roomOf(o.uid) && this.svc.say(o.uid, ROOM_REPLIES[Math.floor(Math.random() * ROOM_REPLIES.length)]), 900 + Math.random() * 1500);
      }
      return clone(r);
    });
  }
  ranking() {
    return this._net(() => localRanking(this.me.name));
  }
  score() {
    return Promise.resolve({ ok: true });
  }
  start() {
    return this._net(() => {
      const r = this.svc.start(this.me.uid);
      setTimeout(() => this._emit({ type: 'start', room: clone(r) }), 50);
      return clone(r);
    });
  }
  finish(text) {
    return this._net(() => {
      const r = this.svc.roomOf(this.me.uid);
      return r ? clone(this.svc.finish(r.id, text)) : null;
    });
  }

  // ---------- gente de mentira ----------
  _seed() {
    this.seeded = true;
    for (let i = 0; i < 7; i++) {
      const host = this._freeFake();
      if (!host) break;
      const kind = i < 5 ? 'rapido' : 'campeonato';
      const r = this.svc.create(host, {
        kind,
        players: [2, 3, 4, 4][i % 4],
        stake: [0, 10, 20, 50, 100][i % 5],
        fee: [20, 50][i % 2],
        name: ROOM_NAMES[i],
      });
      const extra = Math.floor(Math.random() * (r.capacity - 1));
      for (let k = 0; k < extra; k++) {
        const f = this._freeFake();
        if (f) this.svc.join(f, r.id);
      }
    }
  }

  _freeFake() {
    const free = this.fakes.filter((f) => !this.svc.roomOf(f.uid));
    return free.length ? free[Math.floor(Math.random() * free.length)] : null;
  }

  _tick() {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      try {
        this._simulate();
      } catch {
        /* simulação não pode derrubar o jogo */
      }
      this._tick();
    }, 2200 + Math.random() * 1800);
  }

  _simulate() {
    const mine = this.me && this.svc.roomOf(this.me.uid);
    if (mine && mine.status === 'espera') {
      const fakesHere = mine.seats.filter((s) => s && !s.bot && s.uid !== this.me.uid);
      // alguém entra na sua sala
      if (mine.seats.some((s) => !s) && Math.random() < 0.35) {
        const f = this._freeFake();
        if (f) {
          this.svc.join(f, mine.id);
          // quem chega marca "pronto" logo depois
          setTimeout(() => this.svc.roomOf(f.uid) && this.svc.setReady(f.uid, true), 1200 + Math.random() * 1500);
        }
      }
      for (const s of fakesHere) if (!s.ready && Math.random() < 0.8) this.svc.setReady(s.uid, true);
      // às vezes alguém desiste
      if (fakesHere.length && Math.random() < 0.06) this.svc.leave(fakesHere[Math.floor(Math.random() * fakesHere.length)].uid);
      // dono de mentira: começa quando você está pronto, ou às vezes vai embora
      const host = mine.seats.find((s) => s && s.uid === mine.hostId);
      if (host && host.uid !== this.me.uid) {
        if (Math.random() < 0.07) this.svc.leave(host.uid);
        else if (this.svc.canStart(mine) && mine.seats.find((s) => s && s.uid === this.me.uid).ready && Math.random() < 0.6) {
          const r = this.svc.start(host.uid);
          this._emit({ type: 'start', room: clone(r) });
        }
      }
    }
    // movimento no saguão
    const rooms = [...this.svc.rooms.values()].filter((r) => !mine || r.id !== mine.id);
    for (const r of rooms) {
      if (r.status === 'espera' && Math.random() < 0.2) {
        const f = this._freeFake();
        if (f && r.seats.some((s) => !s)) this.svc.join(f, r.id);
      }
      if (r.status === 'espera' && !r.seats.some((s) => !s) && Math.random() < 0.3) this.svc.start(r.hostId);
      else if (r.status === 'jogando' && Math.random() < 0.15) this.svc.remove(r.hostId);
    }
    if (this.svc.rooms.size < 6 && Math.random() < 0.4) {
      const f = this._freeFake();
      if (f) this.svc.create(f, { kind: Math.random() < 0.7 ? 'rapido' : 'campeonato', players: [2, 3, 4][Math.floor(Math.random() * 3)], stake: [0, 10, 20, 50][Math.floor(Math.random() * 4)], fee: 20, name: ROOM_NAMES[Math.floor(Math.random() * ROOM_NAMES.length)] });
    }
  }
}

// ---------- servidor de verdade ----------
export class WsBackend {
  constructor(url) {
    this.url = url;
    this.handlers = new Set();
    this.pending = new Map();
    this.seq = 1;
  }

  get label() {
    return this.url;
  }

  on(fn) {
    this.handlers.add(fn);
    return () => this.handlers.delete(fn);
  }

  connect(nick) {
    return new Promise((resolve) => {
      let done = false;
      try {
        this.ws = new WebSocket(this.url);
      } catch {
        return resolve({ ok: false, error: 'Endereço do servidor inválido.' });
      }
      const fail = () => !done && ((done = true), resolve({ ok: false, error: 'Não deu para conectar no servidor.' }));
      setTimeout(fail, 6000);
      this.ws.onerror = fail;
      this.ws.onclose = () => {
        if (done) for (const fn of this.handlers) fn({ type: 'closed', why: 'A conexão caiu.' });
      };
      this.ws.onmessage = (m) => {
        const msg = JSON.parse(m.data);
        if (msg.re && this.pending.has(msg.re)) {
          this.pending.get(msg.re)(msg.ok ? { ok: true, data: msg.data } : { ok: false, error: msg.error });
          this.pending.delete(msg.re);
          return;
        }
        for (const fn of this.handlers) fn(msg);
      };
      this.ws.onopen = async () => {
        const r = await this._call('hello', { nick });
        done = true;
        resolve(r);
      };
    });
  }

  disconnect() {
    try {
      this.ws && this.ws.close();
    } catch {
      /* ignore */
    }
  }

  _call(op, args = {}) {
    return new Promise((resolve) => {
      const id = this.seq++;
      this.pending.set(id, resolve);
      this.ws.send(JSON.stringify({ id, op, ...args }));
      setTimeout(() => this.pending.has(id) && (this.pending.delete(id), resolve({ ok: false, error: 'O servidor não respondeu.' })), 8000);
    });
  }

  list(q) { return this._call('list', q); }
  create(opts) { return this._call('create', { opts }); }
  join(code) { return this._call('join', { code }); }
  leave() { return this._call('leave'); }
  kick(seat) { return this._call('kick', { seat }); }
  addBot(seat) { return this._call('addBot', { seat }); }
  fillBots() { return this._call('fillBots'); }
  ready(v) { return this._call('ready', { v }); }
  moveSeat(i) { return this._call('moveSeat', { seat: i }); }
  remove() { return this._call('remove'); }
  say(text) { return this._call('say', { text }); }
  ranking() { return this._call('ranking'); }
  score(pts) { return this._call('score', { pts }); }
  start() { return this._call('start'); }
  finish(text) { return this._call('finish', { text }); }
}

function clone(r) {
  return r ? JSON.parse(JSON.stringify(r)) : r;
}

export { summary };
