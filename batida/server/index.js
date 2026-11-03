// Servidor online do Batida.
// Rode com:  cd server && npm install && npm start   (porta 8787, ou PORT=...)
// No jogo: Online > toque no nome do servidor > ws://SEU_IP:8787
//
// O que já faz: apelido, salas de jogo rápido e campeonato, busca por nome/dono/código,
// sala privada por código, entrar/sair, dono que sai passa a sala para outro, expulsar,
// bots, pronto, trocar de lugar, excluir sala, começar e terminar.
// Próximo passo (ver PROTOCOLO.md): a partida em si rodando aqui, com as jogadas de cada
// pessoa chegando pela rede (o motor do jogo em src/classic/engine.js já serve no servidor).
import { WebSocketServer } from 'ws';
import { RoomService, RoomError } from '../src/online/rooms.js';

const PORT = Number(process.env.PORT) || 8787;
const svc = new RoomService();
const clients = new Map(); // uid -> { ws, user }
let seq = 1;

const send = (ws, msg) => ws.readyState === 1 && ws.send(JSON.stringify(msg));

// avisa cada pessoa da sala quando a sala muda
svc.on((ev) => {
  if (ev.type === 'room') {
    for (const s of ev.room.seats) if (s && !s.bot && clients.has(s.uid)) send(clients.get(s.uid).ws, { type: 'room', room: ev.room });
  } else if (ev.type === 'closed') {
    for (const [uid, c] of clients) if (c.roomId === ev.roomId) {
      c.roomId = null;
      send(c.ws, { type: 'closed', why: ev.why });
    }
  } else if (ev.type === 'kicked') {
    const c = clients.get(ev.uid);
    if (c) send(c.ws, { type: 'kicked' });
  } else if (ev.type === 'host') {
    const c = clients.get(ev.hostId);
    if (c) send(c.ws, { type: 'host', hostId: ev.hostId, me: true });
  } else if (ev.type === 'lobby') {
    lobbyDirty = true;
  }
});

// avisa o saguão no máximo 2 vezes por segundo
let lobbyDirty = false;
setInterval(() => {
  if (!lobbyDirty) return;
  lobbyDirty = false;
  for (const c of clients.values()) if (!c.roomId) send(c.ws, { type: 'lobby' });
}, 500);

const ops = {
  hello(c, { nick }) {
    const name = String(nick || '').trim().slice(0, 16);
    if (name.length < 2) throw new RoomError('Apelido muito curto.');
    c.user.name = name;
    return { uid: c.user.uid, online: clients.size };
  },
  list(c, q) {
    return svc.list({ kind: q.kind, q: q.q || '' });
  },
  create(c, { opts }) {
    const r = svc.create(c.user, opts || {});
    c.roomId = r.id;
    return r;
  },
  join(c, { code }) {
    const r = svc.join(c.user, code);
    c.roomId = r.id;
    return r;
  },
  leave(c) {
    svc.leave(c.user.uid);
    c.roomId = null;
    return null;
  },
  kick(c, { seat }) {
    return svc.kick(c.user.uid, seat);
  },
  addBot(c, { seat }) {
    return svc.addBot(c.user.uid, seat ?? null);
  },
  fillBots(c) {
    return svc.fillBots(c.user.uid);
  },
  ready(c, { v }) {
    return svc.setReady(c.user.uid, v);
  },
  moveSeat(c, { seat }) {
    return svc.moveSeat(c.user.uid, seat);
  },
  remove(c) {
    svc.remove(c.user.uid);
    c.roomId = null;
    return null;
  },
  start(c) {
    const r = svc.start(c.user.uid);
    for (const s of r.seats) if (s && !s.bot && clients.has(s.uid)) send(clients.get(s.uid).ws, { type: 'start', room: r });
    return r;
  },
  finish(c, { text }) {
    const r = svc.roomOf(c.user.uid);
    if (!r) return null;
    if (r.hostId !== c.user.uid) return r; // só o dono encerra
    return svc.finish(r.id, text || '');
  },
};

const wss = new WebSocketServer({ port: PORT });
wss.on('connection', (ws) => {
  const c = { ws, user: { uid: `u${seq++}`, name: 'Anônimo' }, roomId: null };
  clients.set(c.user.uid, c);
  ws.on('message', (raw) => {
    let msg;
    try {
      msg = JSON.parse(raw);
    } catch {
      return;
    }
    const fn = ops[msg.op];
    if (!fn) return send(ws, { re: msg.id, ok: false, error: 'Comando desconhecido.' });
    try {
      const data = fn(c, msg);
      send(ws, { re: msg.id, ok: true, data });
    } catch (e) {
      send(ws, { re: msg.id, ok: false, error: e instanceof RoomError ? e.message : 'Erro no servidor.' });
      if (!(e instanceof RoomError)) console.error(e);
    }
  });
  ws.on('close', () => {
    // quem cai da conexão sai da sala (e o dono passa para outro)
    svc.leave(c.user.uid, 'caiu');
    clients.delete(c.user.uid);
  });
});

console.log(`Batida online rodando na porta ${PORT}`);
