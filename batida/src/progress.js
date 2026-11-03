// Estatísticas, missões do dia e conquistas.
// O jogo chama track(evento, dados) e este módulo soma tudo e avisa o que foi cumprido.
import { store, toast } from './ui/dom.js';
import { makeRng } from './core/tiles.js';

// ---------- estatísticas ----------
const STATS0 = {
  partidas: 0, vitorias: 0, rodadas: 0, rodadasGanhas: 0,
  batidas: 0, batidasBucha: 0, batidasLaelo: 0, fechadosGanhos: 0, fechadosPerdidos: 0,
  passes: 0, gatos: 0, compradas: 0, sequencia: 0, melhorSequencia: 0,
  ganhoTotal: 0, desafios: 0,
  porModo: {}, // modo -> { j, v }
};

export function getStats() {
  const s = { ...STATS0, ...store.get('stats3', {}) };
  s.porModo = { ...s.porModo };
  return s;
}
function saveStats(s) {
  store.set('stats3', s);
}

// ---------- missões do dia ----------
// ev: evento que conta; ok(d): filtro; n: quantas vezes; r: prêmio
export const MISSOES = [
  { id: 'bater3', text: 'Bata 3 vezes', ev: 'round', ok: (d) => d.batiEu, n: 3, r: 60 },
  { id: 'bucha1', text: 'Bata com bucha', ev: 'round', ok: (d) => d.batiEu && d.bucha, n: 1, r: 80 },
  { id: 'laelo1', text: 'Bata com lá-e-lô', ev: 'round', ok: (d) => d.batiEu && d.laelo, n: 1, r: 120 },
  { id: 'ganhar2', text: 'Ganhe 2 partidas', ev: 'match', ok: (d) => d.won, n: 2, r: 100 },
  { id: 'fechado1', text: 'Ganhe uma rodada no jogo fechado', ev: 'round', ok: (d) => d.fechado && d.won, n: 1, r: 80 },
  { id: 'rodadas6', text: 'Jogue 6 rodadas', ev: 'round', ok: () => true, n: 6, r: 40 },
  { id: 'mano', text: 'Ganhe uma partida mano a mano (2 jogadores)', ev: 'match', ok: (d) => d.won && d.players === 2, n: 1, r: 70 },
  { id: 'valendo', text: 'Ganhe uma partida valendo dinheiro', ev: 'match', ok: (d) => d.won && d.stake > 0, n: 1, r: 80 },
  { id: 'semgato', text: 'Jogue uma partida inteira sem dar gato', ev: 'match', ok: (d) => d.gatos === 0, n: 1, r: 60 },
  { id: 'dupla', text: 'Ganhe uma partida em dupla', ev: 'match', ok: (d) => d.won && d.players === 4, n: 1, r: 70 },
];

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
};

// 3 missões por dia, sorteadas pela data (iguais o dia todo)
export function dailyMissions() {
  const key = today();
  let m = store.get('missoes', null);
  if (!m || m.day !== key) {
    const rng = makeRng([...key].reduce((a, c) => a * 31 + c.charCodeAt(0), 7) >>> 0);
    const ids = rng.shuffle(MISSOES.map((x) => x.id)).slice(0, 3);
    m = { day: key, list: ids.map((id) => ({ id, prog: 0, done: false, claimed: false })) };
    store.set('missoes', m);
  }
  return m;
}

// ---------- conquistas ----------
export const CONQUISTAS = [
  { id: 'primeira', text: 'Primeira batida', desc: 'Bata pela primeira vez', r: 50, test: (s) => s.batidas >= 1 },
  { id: 'bate10', text: 'Batedor', desc: 'Bata 10 vezes', r: 100, test: (s) => s.batidas >= 10 },
  { id: 'bate50', text: 'Mão de ferro', desc: 'Bata 50 vezes', r: 300, test: (s) => s.batidas >= 50 },
  { id: 'bucha10', text: 'Bucha de ouro', desc: 'Bata 10 vezes com bucha', r: 250, test: (s) => s.batidasBucha >= 10 },
  { id: 'laelo', text: 'Lá e lô', desc: 'Bata com pedra que entra nos dois lados', r: 100, test: (s) => s.batidasLaelo >= 1 },
  { id: 'fecha5', text: 'Fecha e conta', desc: 'Ganhe 5 rodadas no jogo fechado', r: 150, test: (s) => s.fechadosGanhos >= 5 },
  { id: 'seq3', text: 'Embalado', desc: 'Ganhe 3 partidas seguidas', r: 150, test: (s) => s.melhorSequencia >= 3 },
  { id: 'seq7', text: 'Ninguém segura', desc: 'Ganhe 7 partidas seguidas', r: 500, test: (s) => s.melhorSequencia >= 7 },
  { id: 'partidas50', text: 'Freguês da casa', desc: 'Jogue 50 partidas', r: 200, test: (s) => s.partidas >= 50 },
  { id: 'desafio7', text: 'Desafiante', desc: 'Vença 7 desafios do dia', r: 300, test: (s) => s.desafios >= 7 },
  { id: 'rico', text: 'Bolso cheio', desc: 'Ganhe R$ 2.000 no total', r: 200, test: (s) => s.ganhoTotal >= 2000 },
  { id: 'rival5', text: 'Freguês meu', desc: 'Ganhe 5 vezes do mesmo adversário', r: 150, test: (s, x) => Object.values(x.rivals || {}).some((r) => r.w >= 5) },
  { id: 'titulo1', text: 'Campeão do bairro', desc: 'Vença o Torneio do Boteco do Zezão', r: 100, test: (s, x) => (x.titles || []).includes('boteco') },
  { id: 'titulo6', text: 'Rei do Brasileirão', desc: 'Vença o Brasileirão de Dominó', r: 1000, test: (s, x) => (x.titles || []).includes('brasileirao') },
];

export function achievements() {
  return store.get('conquistas', {}); // id -> { at, claimed }
}

// ---------- registro ----------
let matchGatos = 0;

export function track(ev, d = {}, extra = {}) {
  const s = getStats();
  if (ev === 'gato') {
    s.gatos++;
    matchGatos++;
  } else if (ev === 'pass') s.passes++;
  else if (ev === 'draw') s.compradas++;
  else if (ev === 'matchStart') matchGatos = 0;
  else if (ev === 'round') {
    s.rodadas++;
    if (d.won) s.rodadasGanhas++;
    if (d.batiEu) {
      s.batidas++;
      if (d.bucha) s.batidasBucha++;
      if (d.laelo) s.batidasLaelo++;
    }
    if (d.fechado && d.won) s.fechadosGanhos++;
    if (d.fechado && d.lost) s.fechadosPerdidos++;
  } else if (ev === 'match') {
    d.gatos = matchGatos;
    s.partidas++;
    const m = (s.porModo[d.mode] = s.porModo[d.mode] || { j: 0, v: 0 });
    m.j++;
    if (d.won) {
      s.vitorias++;
      m.v++;
      s.sequencia++;
      s.melhorSequencia = Math.max(s.melhorSequencia, s.sequencia);
    } else s.sequencia = 0;
  } else if (ev === 'money') s.ganhoTotal += Math.max(0, d.amount || 0);
  else if (ev === 'desafio' && d.won) s.desafios++;
  saveStats(s);

  // missões do dia
  const m = dailyMissions();
  let changed = false;
  for (const it of m.list) {
    const def = MISSOES.find((x) => x.id === it.id);
    if (!def || it.done || def.ev !== ev || !def.ok(d)) continue;
    it.prog++;
    changed = true;
    if (it.prog >= def.n) {
      it.done = true;
      toast(`Missão cumprida: ${def.text}`);
    }
  }
  if (changed) store.set('missoes', m);

  // conquistas
  const got = achievements();
  const ctx = { rivals: store.get('rivals', {}), titles: (store.get('career', {}) || {}).titles || [], ...extra };
  for (const c of CONQUISTAS) {
    if (got[c.id] || !c.test(s, ctx)) continue;
    got[c.id] = { at: Date.now(), claimed: false };
    toast(`Conquista: ${c.text}!`);
  }
  store.set('conquistas', got);
}

// Quantos prêmios esperando para recolher (para a bolinha no botão)
export function pendingRewards() {
  const m = dailyMissions();
  const a = achievements();
  return m.list.filter((x) => x.done && !x.claimed).length + Object.values(a).filter((x) => !x.claimed).length;
}
