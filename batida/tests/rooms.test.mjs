// Testes da lógica de salas: node tests/rooms.test.mjs
import assert from 'node:assert/strict';
import { RoomService } from '../src/online/rooms.js';

const s = new RoomService();
const ana = { uid: 'a', name: 'Ana' }, beto = { uid: 'b', name: 'Beto' }, caio = { uid: 'c', name: 'Caio' };
const events = [];
s.on((e) => events.push(e.type));

const r = s.create(ana, { kind: 'rapido', players: 4, stake: 20, name: 'Mesa da Ana' });
assert.equal(r.capacity, 4);
assert.equal(s.list({ kind: 'rapido' }).length, 1);
s.join(beto, r.code.toLowerCase());
s.join(caio, r.id);
assert.equal(s.list({ q: 'ana' })[0].humans, 3);

// só o dono mexe
assert.throws(() => s.addBot(beto.uid), /dono/);
s.addBot(ana.uid);
assert.equal(s.get(r.id).seats.filter((x) => x && x.bot).length, 1);

// não começa sem todo mundo pronto
assert.throws(() => s.start(ana.uid), /pronto/);
s.setReady(beto.uid, true); s.setReady(caio.uid, true);

// dono sai: o próximo humano vira dono
s.leave(ana.uid);
assert.equal(s.get(r.id).hostId, beto.uid);
assert.ok(events.includes('host'));

// expulsar
s.kick(beto.uid, s.get(r.id).seats.findIndex((x) => x && x.uid === 'c'));
assert.equal(s.roomOf('c'), null);

// começar completa com bots
s.start(beto.uid);
assert.equal(s.get(r.id).seats.every(Boolean), true);
assert.equal(s.list({}).length, 0, 'sala jogando some da busca');
s.finish(r.id);
assert.equal(s.list({}).length, 1);

// sala privada só aparece pelo código
const p = s.create(caio, { kind: 'campeonato', private: true, fee: 50 });
assert.equal(p.capacity, 8);
assert.equal(s.list({ kind: 'campeonato' }).length, 0);
assert.equal(s.list({ q: p.code }).length, 1);

// entrar numa sala cheia de bots toma o lugar de um bot
s.fillBots(caio.uid);
s.join(ana, p.code);
assert.equal(s.get(p.id).seats.filter((x) => x && !x.bot).length, 2);

// excluir a sala
s.remove(caio.uid);
assert.equal(s.get(p.id), null);
assert.equal(s.roomOf('a'), null);

// último humano sai: sala some
s.leave(beto.uid);
assert.equal(s.get(r.id), null);
console.log('salas: todos os testes passaram');
