// Ranking semanal do online.
// Pontos: vitória vale 10 (15 se tinha aposta), derrota vale 2 por ter jogado,
// título de campeonato online vale 40, chegar na final vale 15.
// A semana vira na segunda-feira 00:00; quem terminou bem colocado ganha prêmio.
import { store } from '../ui/dom.js';
import { makeRng } from '../core/tiles.js';

export const PONTOS = { vitoria: 10, vitoriaAposta: 15, derrota: 2, titulo: 40, final: 15 };

export const PREMIOS = [
  { ate: 1, valor: 1000, label: '1º lugar' },
  { ate: 2, valor: 600, label: '2º lugar' },
  { ate: 3, valor: 400, label: '3º lugar' },
  { ate: 10, valor: 200, label: '4º ao 10º' },
  { ate: 50, valor: 100, label: '11º ao 50º' },
  { ate: 100, valor: 50, label: '51º ao 100º' },
];

export function premioDe(pos) {
  const p = PREMIOS.find((x) => pos <= x.ate);
  return p ? p.valor : 0;
}

// Semana começa na segunda 00:00 (horário do aparelho)
export function weekStart(now = new Date()) {
  const d = new Date(now);
  d.setHours(0, 0, 0, 0);
  const dow = (d.getDay() + 6) % 7; // segunda = 0
  d.setDate(d.getDate() - dow);
  return d;
}
export const weekKey = (now = new Date()) => weekStart(now).toISOString().slice(0, 10);

export function timeLeft(now = new Date()) {
  const end = weekStart(now);
  end.setDate(end.getDate() + 7);
  const ms = end - now;
  const d = Math.floor(ms / 86400000);
  const hh = Math.floor((ms % 86400000) / 3600000);
  return d > 0 ? `${d}d ${hh}h` : `${hh}h ${Math.floor((ms % 3600000) / 60000)}min`;
}

const NOMES = ['Marcão', 'Dudu_RJ', 'Tati', 'Seu Lourival', 'NinjaDoDominó', 'Kelly', 'Jorginho', 'Paty', 'Gordão', 'Lucas_SP', 'Vovó Zilda', 'Bigode', 'Raí', 'Fabinho', 'Cris', 'Mineiro', 'Baiano', 'Leleco', 'Sandrinha', 'Toninho', 'Rei da Sena', 'Buchudo', 'Dona Fátima', 'Nego Véio', 'Carioca', 'Pernambuco', 'Juca', 'Valdir', 'Zeca', 'Neusa', 'Rogerinho', 'Peixe', 'Tico', 'Malu', 'Bruninho', 'Cabeça', 'Xandão', 'Marquinho BH', 'Lu', 'Dentinho'];

// Ranking local (servidor de teste): uns 120 jogadores fictícios que vão somando pontos durante a semana.
export function localRanking(me, now = new Date()) {
  const key = weekKey(now);
  const rng = makeRng(hash(key));
  const frac = Math.min(1, (now - weekStart(now)) / (7 * 86400000));
  const rows = [];
  const SUF = ['', '_BH', ' do Bar', '_RJ', '77', ' Jr', '_SP', ' da Vila'];
  for (let i = 0; i < 160; i++) {
    const base = NOMES[i % NOMES.length] + SUF[Math.floor(i / NOMES.length) % SUF.length];
    const top = Math.pow(rng(), 2.2) * 900 + 20; // poucos com muitos pontos
    // quem ainda não jogou na semana fica de fora
    const pts = Math.round(top * (0.15 + 0.85 * frac) * (rng() < 0.25 ? 0 : 1));
    if (pts > 0) rows.push({ name: base, pts, you: false });
  }
  rows.push({ name: me, pts: myPoints(key), you: true });
  rows.sort((a, b) => b.pts - a.pts || (a.you ? -1 : 1));
  rows.forEach((r, i) => (r.pos = i + 1));
  return { week: key, left: timeLeft(now), rows };
}

export function myPoints(key = weekKey()) {
  const s = store.get('rank', {});
  return s.week === key ? s.pts || 0 : 0;
}

export function addPoints(n) {
  const key = weekKey();
  const s = store.get('rank', {});
  if (s.week !== key) {
    // semana virou: guarda como ficou a anterior para pagar o prêmio
    if (s.week) store.set('rankPrev', { week: s.week, pts: s.pts || 0, paid: false });
    s.week = key;
    s.pts = 0;
  }
  s.pts += n;
  store.set('rank', s);
  return s.pts;
}

// Quando a semana vira, calcula a posição final e devolve o prêmio (uma vez só).
export function settlePrevWeek(me) {
  const cur = store.get('rank', {});
  const key = weekKey();
  if (cur.week && cur.week !== key) {
    store.set('rankPrev', { week: cur.week, pts: cur.pts || 0, paid: false });
    store.set('rank', { week: key, pts: 0 });
  }
  const prev = store.get('rankPrev', null);
  if (!prev || prev.paid) return null;
  const end = new Date(prev.week + 'T12:00:00');
  end.setDate(end.getDate() + 6);
  end.setHours(23, 59);
  const table = localRanking(me, end);
  const row = table.rows.find((r) => r.you);
  row.pts = prev.pts;
  table.rows.sort((a, b) => b.pts - a.pts);
  const pos = table.rows.indexOf(row) + 1;
  prev.paid = true;
  prev.pos = pos;
  store.set('rankPrev', prev);
  return { pos, pts: prev.pts, premio: prev.pts > 0 ? premioDe(pos) : 0 };
}

function hash(s) {
  let h = 2166136261;
  for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return h >>> 0;
}
