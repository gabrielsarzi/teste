// Salas do modo online. Lógica pura (sem rede), usada igualzinho no servidor
// de verdade (server/) e no servidor simulado que roda dentro do jogo.
//
// Sala de jogo rápido: 2, 3 ou 4 lugares (4 = duplas: lugares 0+2 contra 1+3).
// Sala de campeonato: 8 lugares em 4 duplas (0+1, 2+3, 4+5, 6+7), mata-mata.

const BOT_NAMES = ['Bot Zé', 'Bot Tião', 'Bot Cida', 'Bot Neném', 'Bot Biu', 'Bot Dora', 'Bot Lelé', 'Bot Quinho'];
const CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

export class RoomError extends Error {}

export class RoomService {
  constructor({ now = () => Date.now(), rand = Math.random } = {}) {
    this.rooms = new Map();
    this.where = new Map(); // uid -> roomId
    this.now = now;
    this.rand = rand;
    this.listeners = new Set();
    this.seq = 1;
  }

  on(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  emit(ev) {
    for (const fn of this.listeners) fn(ev);
  }

  // ---------- consultas ----------
  get(id) {
    return this.rooms.get(id) || null;
  }

  roomOf(uid) {
    const id = this.where.get(uid);
    return id ? this.get(id) : null;
  }

  // Busca: por tipo, por texto (nome ou código) e só salas abertas e públicas.
  // Quem digita o código exato acha a sala privada também.
  list({ kind, q = '', includeFull = false } = {}) {
    const term = q.trim().toLowerCase();
    return [...this.rooms.values()]
      .filter((r) => !kind || r.kind === kind)
      .filter((r) => r.status === 'espera' || includeFull)
      .filter((r) => {
        if (term && r.code.toLowerCase() === term) return true;
        if (r.private) return false;
        return !term || r.name.toLowerCase().includes(term) || hostName(r).toLowerCase().includes(term);
      })
      .map(summary)
      .sort((a, b) => b.humans - a.humans || a.createdAt - b.createdAt);
  }

  // ---------- ações ----------
  create(user, opts = {}) {
    this._leaveIfIn(user.uid);
    const kind = opts.kind === 'campeonato' ? 'campeonato' : 'rapido';
    const capacity = kind === 'campeonato' ? 8 : [2, 3, 4].includes(opts.players) ? opts.players : 4;
    const room = {
      id: `r${this.seq++}`,
      code: this._code(),
      name: (opts.name || `Mesa do ${user.name}`).slice(0, 28),
      kind,
      capacity,
      stake: kind === 'rapido' ? Math.max(0, opts.stake | 0) : 0,
      fee: kind === 'campeonato' ? Math.max(0, opts.fee | 0) : 0,
      private: !!opts.private,
      hostId: user.uid,
      seats: Array.from({ length: capacity }, () => null),
      status: 'espera',
      createdAt: this.now(),
      log: [],
    };
    room.seats[0] = { uid: user.uid, name: user.name, bot: false, ready: false };
    this.rooms.set(room.id, room);
    this.where.set(user.uid, room.id);
    this._log(room, `${user.name} abriu a sala.`);
    this._changed(room);
    return room;
  }

  join(user, idOrCode) {
    const room = this.get(idOrCode) || [...this.rooms.values()].find((r) => r.code === String(idOrCode).toUpperCase());
    if (!room) throw new RoomError('Sala não encontrada.');
    if (room.status !== 'espera') throw new RoomError('Essa sala já está jogando.');
    if (this.where.get(user.uid) === room.id) return room;
    // entra num lugar vazio; se não tiver, toma o lugar de um bot
    let i = room.seats.findIndex((s) => !s);
    if (i < 0) i = room.seats.findIndex((s) => s && s.bot);
    if (i < 0) throw new RoomError('A sala está cheia.');
    this._leaveIfIn(user.uid);
    room.seats[i] = { uid: user.uid, name: user.name, bot: false, ready: false };
    this.where.set(user.uid, room.id);
    this._log(room, `${user.name} sentou na mesa.`);
    this._changed(room);
    return room;
  }

  // Sair: se for o dono, passa para o próximo humano; se não sobrar ninguém, a sala some.
  leave(uid, reason = 'saiu') {
    const room = this.roomOf(uid);
    if (!room) return null;
    const i = room.seats.findIndex((s) => s && s.uid === uid);
    const name = room.seats[i] ? room.seats[i].name : '';
    room.seats[i] = room.status === 'jogando' ? { uid: `bot-${i}-${this.seq++}`, name: this._botName(room), bot: true, ready: true } : null;
    this.where.delete(uid);
    this._log(room, reason === 'expulso' ? `${name} foi tirado da mesa.` : `${name} saiu.`);
    const humans = room.seats.filter((s) => s && !s.bot);
    if (!humans.length) {
      this._close(room, 'Todo mundo saiu.');
      return null;
    }
    if (room.hostId === uid) {
      room.hostId = humans[0].uid;
      this._log(room, `${humans[0].name} agora é o dono da sala.`);
      this.emit({ type: 'host', roomId: room.id, hostId: room.hostId });
    }
    this._changed(room);
    return room;
  }

  kick(hostUid, seat) {
    const room = this._asHost(hostUid);
    const s = room.seats[seat];
    if (!s) return room;
    if (s.uid === hostUid) throw new RoomError('O dono não pode se tirar. Use Sair.');
    if (s.bot) {
      room.seats[seat] = null;
      this._log(room, `${s.name} saiu da mesa.`);
      this._changed(room);
      return room;
    }
    this.leave(s.uid, 'expulso');
    this.emit({ type: 'kicked', roomId: room.id, uid: s.uid });
    return room;
  }

  addBot(hostUid, seat = null) {
    const room = this._asHost(hostUid);
    if (room.status !== 'espera') throw new RoomError('A sala já está jogando.');
    const i = seat != null ? seat : room.seats.findIndex((s) => !s);
    if (i < 0 || room.seats[i]) throw new RoomError('Não tem lugar vazio.');
    room.seats[i] = { uid: `bot-${i}-${this.seq++}`, name: this._botName(room), bot: true, ready: true };
    this._changed(room);
    return room;
  }

  fillBots(hostUid) {
    const room = this._asHost(hostUid);
    room.seats.forEach((s, i) => {
      if (!s) room.seats[i] = { uid: `bot-${i}-${this.seq++}`, name: this._botName(room), bot: true, ready: true };
    });
    this._changed(room);
    return room;
  }

  setReady(uid, ready) {
    const room = this.roomOf(uid);
    if (!room) throw new RoomError('Você não está numa sala.');
    const s = room.seats.find((x) => x && x.uid === uid);
    s.ready = !!ready;
    this._changed(room);
    return room;
  }

  // Trocar de lugar (escolher a dupla no 4 ou no campeonato)
  moveSeat(uid, seat) {
    const room = this.roomOf(uid);
    if (!room || room.status !== 'espera') throw new RoomError('Não dá para trocar de lugar agora.');
    const from = room.seats.findIndex((s) => s && s.uid === uid);
    const target = room.seats[seat];
    if (target && !target.bot) throw new RoomError('Esse lugar já tem gente.');
    room.seats[seat] = room.seats[from];
    room.seats[from] = target || null;
    this._changed(room);
    return room;
  }

  remove(hostUid) {
    const room = this._asHost(hostUid);
    this._close(room, 'O dono fechou a sala.');
  }

  canStart(room) {
    const humans = room.seats.filter((s) => s && !s.bot);
    return humans.every((s) => s.uid === room.hostId || s.ready);
  }

  // Começa: completa o que faltar com bots
  start(hostUid) {
    const room = this._asHost(hostUid);
    if (!this.canStart(room)) throw new RoomError('Ainda tem gente que não marcou "pronto".');
    room.seats.forEach((s, i) => {
      if (!s) room.seats[i] = { uid: `bot-${i}-${this.seq++}`, name: this._botName(room), bot: true, ready: true };
    });
    room.status = 'jogando';
    room.startedAt = this.now();
    this._log(room, 'Começou o jogo!');
    this._changed(room);
    return room;
  }

  // Fim do jogo: a sala volta para a espera, todo mundo desmarca "pronto"
  finish(roomId, summaryText = '') {
    const room = this.get(roomId);
    if (!room) return null;
    room.status = 'espera';
    room.seats.forEach((s) => s && !s.bot && (s.ready = false));
    if (summaryText) this._log(room, summaryText);
    this._changed(room);
    return room;
  }

  // ---------- internos ----------
  _asHost(uid) {
    const room = this.roomOf(uid);
    if (!room) throw new RoomError('Você não está numa sala.');
    if (room.hostId !== uid) throw new RoomError('Só o dono da sala pode fazer isso.');
    return room;
  }

  _leaveIfIn(uid) {
    if (this.where.has(uid)) this.leave(uid);
  }

  _close(room, why) {
    for (const s of room.seats) if (s && !s.bot) this.where.delete(s.uid);
    this.rooms.delete(room.id);
    this.emit({ type: 'closed', roomId: room.id, why });
    this.emit({ type: 'lobby' });
  }

  _changed(room) {
    this.emit({ type: 'room', room });
    this.emit({ type: 'lobby' });
  }

  _log(room, text) {
    room.log.push({ at: this.now(), text });
    if (room.log.length > 30) room.log.shift();
  }

  _code() {
    let c;
    do {
      c = Array.from({ length: 4 }, () => CODE_CHARS[Math.floor(this.rand() * CODE_CHARS.length)]).join('');
    } while ([...this.rooms.values()].some((r) => r.code === c));
    return c;
  }

  _botName(room) {
    const used = new Set(room.seats.filter(Boolean).map((s) => s.name));
    return BOT_NAMES.find((n) => !used.has(n)) || `Bot ${this.seq}`;
  }
}

function hostName(r) {
  const h = r.seats.find((s) => s && s.uid === r.hostId);
  return h ? h.name : '';
}

export function summary(r) {
  return {
    id: r.id,
    code: r.code,
    name: r.name,
    kind: r.kind,
    capacity: r.capacity,
    stake: r.stake,
    fee: r.fee,
    private: r.private,
    status: r.status,
    host: hostName(r),
    humans: r.seats.filter((s) => s && !s.bot).length,
    bots: r.seats.filter((s) => s && s.bot).length,
    free: r.seats.filter((s) => !s).length,
    createdAt: r.createdAt,
  };
}
