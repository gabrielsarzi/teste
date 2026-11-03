// Teste rápido do servidor: sobe o servidor e simula duas pessoas.
// Uso: node test-client.mjs
import { spawn } from 'node:child_process';
import WebSocket from 'ws';
import assert from 'node:assert/strict';

const PORT = 8799;
const srv = spawn(process.execPath, ['index.js'], { env: { ...process.env, PORT: String(PORT) }, stdio: ['ignore', 'pipe', 'inherit'] });
await new Promise((r) => srv.stdout.once('data', r));

function client() {
  const ws = new WebSocket(`ws://localhost:${PORT}`);
  const pending = new Map();
  const events = [];
  let id = 1;
  ws.on('message', (raw) => {
    const m = JSON.parse(raw);
    if (m.re) {
      pending.get(m.re)(m);
      pending.delete(m.re);
    } else events.push(m);
  });
  const call = (op, args = {}) =>
    new Promise((resolve) => {
      const i = id++;
      pending.set(i, resolve);
      ws.send(JSON.stringify({ id: i, op, ...args }));
    });
  return new Promise((r) => ws.on('open', () => r({ ws, call, events })));
}

const ana = await client();
const beto = await client();
assert.equal((await ana.call('hello', { nick: 'Ana' })).ok, true);
assert.equal((await beto.call('hello', { nick: 'Beto' })).ok, true);

const created = await ana.call('create', { opts: { kind: 'rapido', players: 4, name: 'Mesa da Ana' } });
assert.equal(created.ok, true);
const code = created.data.code;
const listed = await beto.call('list', { kind: 'rapido', q: 'ana' });
assert.equal(listed.data.length, 1);
assert.equal((await beto.call('join', { code })).ok, true);
assert.equal((await beto.call('fillBots')).ok, false, 'só o dono completa com bots');
await beto.call('ready', { v: true });
assert.equal((await ana.call('fillBots')).ok, true);

// dono cai: Beto vira dono
ana.ws.close();
await new Promise((r) => setTimeout(r, 200));
assert.ok(beto.events.some((e) => e.type === 'host' && e.me), 'Beto virou dono');
const st = await beto.call('start');
assert.equal(st.ok, true);
assert.ok(beto.events.some((e) => e.type === 'start'));

beto.ws.close();
srv.kill();
console.log('servidor: todos os testes passaram');
