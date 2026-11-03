// Conteúdo do modo Virada: jogos (combinações), parceiros, simpatias, bebidas e donos de boteco.
import { isDouble, hasNum } from '../core/tiles.js';

// ---------- Jogos ----------
// base: pontos e mult no nível 1; up: quanto sobe por nível
export const JOGOS = [
  { id: 'encaixe', name: 'Encaixe', desc: '1 pedra', base: [5, 1], up: [10, 1] },
  { id: 'par', name: 'Parelha', desc: '2 pedras', base: [10, 1], up: [15, 1] },
  { id: 'corrente', name: 'Corrente', desc: '3 pedras', base: [15, 2], up: [20, 1] },
  { id: 'buchada', name: 'Buchada', desc: '2 buchas ou mais', base: [25, 2], up: [20, 2] },
  { id: 'trem', name: 'Trem', desc: '4 pedras', base: [25, 3], up: [25, 1] },
  { id: 'naipe', name: 'Naipe', desc: '3+ pedras com o mesmo número', base: [35, 3], up: [25, 2] },
  { id: 'expresso', name: 'Expresso', desc: '5 pedras', base: [40, 4], up: [30, 2] },
  { id: 'naipereal', name: 'Naipe Real', desc: '4+ pedras com o mesmo número', base: [80, 6], up: [40, 3] },
];
export const JOGO_BY_ID = Object.fromEntries(JOGOS.map((j) => [j.id, j]));

export function sharedNumber(tiles) {
  for (let n = 0; n <= 6; n++) if (tiles.every((t) => t.mod === 'coringa' || hasNum(t, n))) return n;
  return null;
}

export function detectJogo(tiles) {
  const n = tiles.length;
  if (!n) return null;
  const doubles = tiles.filter(isDouble).length;
  const naipe = n >= 3 ? sharedNumber(tiles) : null;
  if (naipe != null && n >= 4) return 'naipereal';
  if (n >= 5) return 'expresso';
  if (naipe != null) return 'naipe';
  if (n >= 4) return 'trem';
  if (doubles >= 2) return 'buchada';
  if (n >= 3) return 'corrente';
  if (n === 2) return 'par';
  return 'encaixe';
}

export function jogoValues(id, level) {
  const j = JOGO_BY_ID[id];
  return [j.base[0] + j.up[0] * (level - 1), j.base[1] + j.up[1] * (level - 1)];
}

// ---------- Modificadores de pedra ----------
export const MODS = {
  ouro: { name: 'Dourada', desc: '+$3 quando joga' },
  vidro: { name: 'Vidro', desc: '×2 Mult · 1 em 4 de quebrar' },
  brasa: { name: 'Brasa', desc: '+4 Mult' },
  coringa: { name: 'Coringa', desc: 'Encaixa em qualquer ponta' },
  marfim: { name: 'Marfim', desc: '+30 pontos' },
};

// ---------- Parceiros ----------
// Ganchos: onTile(ctx, tile) por pedra pontuada; onPlay(ctx) depois das pedras;
// onMesaEnd(run) -> dinheiro; mods de regra: hands, discards, handSize.
// Retornam efeitos: { chips, mult, xmult, money, msg }
export const PARCEIROS = [
  {
    id: 'seuze', name: 'Seu Zé', rarity: 'comum', cost: 3,
    desc: '+4 Mult',
    face: { skin: 2, hair: 'careca', stache: 'cheio', bg: '#c4512f', extra: 'palito' },
    onPlay: () => ({ mult: 4 }),
  },
  {
    id: 'donacida', name: 'Dona Cida', rarity: 'comum', cost: 4,
    desc: 'Cada bucha jogada dá +3 Mult',
    face: { skin: 1, hair: 'coque', bg: '#2b6b8f', extra: 'brinco' },
    onTile: (ctx, t) => (isDouble(t) ? { mult: 3 } : null),
  },
  {
    id: 'carroca', name: 'Tio Carroça', rarity: 'comum', cost: 4,
    desc: 'Cada bucha jogada dá +25 pontos',
    face: { skin: 3, hair: 'chapeu', stache: 'fino', bg: '#7a4b2a' },
    onTile: (ctx, t) => (isDouble(t) ? { chips: 25 } : null),
  },
  {
    id: 'sena', name: 'Sena Braba', rarity: 'comum', cost: 4,
    desc: 'Pedra com sena (6) dá +3 Mult',
    face: { skin: 2, hair: 'bone', bg: '#3d7a4a', extra: 'barba' },
    onTile: (ctx, t) => (hasNum(t, 6) ? { mult: 3 } : null),
  },
  {
    id: 'branquinha', name: 'Branquinha', rarity: 'raro', cost: 6,
    desc: 'Pedra com branco (0) dá ×1,5 Mult',
    face: { skin: 0, hair: 'longo', bg: '#e6dfcf', ink: '#2a1d14', extra: 'oculos' },
    onTile: (ctx, t) => (hasNum(t, 0) ? { xmult: 1.5 } : null),
  },
  {
    id: 'contador', name: 'O Contador', rarity: 'comum', cost: 5,
    desc: '+1 Mult a cada 2 pedras na mesa',
    face: { skin: 1, hair: 'curto', bg: '#5c5a8a', extra: 'oculos' },
    onPlay: (ctx) => ({ mult: Math.floor(ctx.boardCount / 2) }),
  },
  {
    id: 'lourdes', name: 'Dona Lourdes', rarity: 'raro', cost: 6,
    desc: 'Lá e Lô vale ×3 em vez de ×1,5',
    face: { skin: 3, hair: 'lenco', bg: '#b23a5a', extra: 'brinco' },
    passive: 'laelo3',
  },
  {
    id: 'fominha', name: 'Fominha', rarity: 'comum', cost: 5,
    desc: '+1 jogada por mesa',
    face: { skin: 2, hair: 'bone', bg: '#d08a2a', extra: 'copo' },
    hands: 1,
  },
  {
    id: 'maoleve', name: 'Mão Leve', rarity: 'comum', cost: 4,
    desc: '+1 troca por mesa',
    face: { skin: 1, hair: 'curto', stache: 'fino', bg: '#3a3a3a', ink: '#f3ecdc' },
    discards: 1,
  },
  {
    id: 'bolso', name: 'Bolso Fundo', rarity: 'raro', cost: 6,
    desc: '+1 pedra na mão',
    face: { skin: 0, hair: 'chapeu', bg: '#6b3e8a', extra: 'barba' },
    handSize: 1,
  },
  {
    id: 'agiota', name: 'O Agiota', rarity: 'comum', cost: 5,
    desc: 'Ganha $3 no fim de cada mesa',
    face: { skin: 1, hair: 'careca', stache: 'fino', bg: '#1f5a46', ink: '#f3ecdc', extra: 'oculos' },
    onMesaEnd: () => 3,
  },
  {
    id: 'bebum', name: 'Bebum', rarity: 'comum', cost: 5,
    desc: '+20 Mult, perde 2 a cada jogada',
    face: { skin: 3, hair: 'curto', stache: 'cheio', bg: '#9a3324', extra: 'copo', blush: true },
    init: () => ({ left: 20 }),
    onPlay: (ctx, p) => {
      const v = p.state.left;
      p.state.left -= 2;
      return { mult: v };
    },
    label: (p) => `+${p.state.left} Mult`,
    expired: (p) => p.state.left <= 0,
  },
  {
    id: 'pequente', name: 'Pé-Quente', rarity: 'raro', cost: 6,
    desc: '1 chance em 3 de ×3 Mult',
    face: { skin: 2, hair: 'longo', bg: '#2f7f7a', extra: 'brinco' },
    onPlay: (ctx) => (ctx.rng() < 1 / 3 ? { xmult: 3 } : { msg: 'Nada!' }),
  },
  {
    id: 'pedreiro', name: 'Pedreiro', rarity: 'raro', cost: 6,
    desc: 'Cada pedra jogada ganha +3 pontos para sempre',
    face: { skin: 3, hair: 'capacete', bg: '#c9a227', ink: '#2a1d14' },
    onTile: (ctx, t) => {
      t.bonus = (t.bonus || 0) + 3;
      return { msg: '+3 pra sempre' };
    },
  },
  {
    id: 'vodita', name: 'Vó Dita', rarity: 'comum', cost: 4,
    desc: '+4 Mult por troca sobrando',
    face: { skin: 1, hair: 'coque', bg: '#7d8a3a', extra: 'oculos' },
    onPlay: (ctx) => ({ mult: 4 * ctx.discardsLeft }),
  },
  {
    id: 'maquinista', name: 'Maquinista', rarity: 'raro', cost: 7,
    desc: '×2 Mult se jogar 4 pedras ou mais',
    face: { skin: 2, hair: 'quepe', stache: 'cheio', bg: '#33465c', ink: '#f3ecdc' },
    onPlay: (ctx) => (ctx.played.length >= 4 ? { xmult: 2 } : null),
  },
  {
    id: 'zetres', name: 'Zé Três', rarity: 'comum', cost: 5,
    desc: '×2 Mult se jogar exatamente 3 pedras',
    face: { skin: 0, hair: 'curto', bg: '#a8562b', extra: 'barba' },
    onPlay: (ctx) => (ctx.played.length === 3 ? { xmult: 2 } : null),
  },
  {
    id: 'sortudo', name: 'Sortudo', rarity: 'raro', cost: 6,
    desc: 'Pedra Dourada dá +$2 e +6 Mult a mais',
    face: { skin: 1, hair: 'chapeu', bg: '#d9a43a', ink: '#2a1d14', stache: 'fino' },
    onTile: (ctx, t) => (t.mod === 'ouro' ? { mult: 6, money: 2 } : null),
  },
  {
    id: 'garcom', name: 'Garçom', rarity: 'comum', cost: 4,
    desc: '+$1 por jogada com bucha',
    face: { skin: 2, hair: 'curto', stache: 'fino', bg: '#e9e1cf', ink: '#2a1d14', extra: 'gravata' },
    onPlay: (ctx) => (ctx.played.some(isDouble) ? { money: 1 } : null),
  },
  {
    id: 'mestre', name: 'Mestre do Boteco', rarity: 'lendário', cost: 9,
    desc: 'Cada pedra jogada dá ×1,2 Mult',
    face: { skin: 3, hair: 'chapeu', stache: 'cheio', bg: '#151515', ink: '#f2c14e', extra: 'barba' },
    onTile: () => ({ xmult: 1.2 }),
  },
];
export const PARCEIRO_BY_ID = Object.fromEntries(PARCEIROS.map((p) => [p.id, p]));

// ---------- Consumíveis ----------
// Bebidas sobem o nível de um jogo. Simpatias mexem nas pedras do saco.
export const BEBIDAS = [
  { id: 'cafe', name: 'Cafezinho', jogo: 'encaixe', color: '#5a3a24' },
  { id: 'guarana', name: 'Guaraná', jogo: 'par', color: '#2f8a3b' },
  { id: 'caldo', name: 'Caldo de Cana', jogo: 'corrente', color: '#a7b33a' },
  { id: 'quentao', name: 'Quentão', jogo: 'buchada', color: '#a9442b' },
  { id: 'rabo', name: 'Rabo de Galo', jogo: 'trem', color: '#8a2a2a' },
  { id: 'caipi', name: 'Caipirinha', jogo: 'naipe', color: '#6fae3a' },
  { id: 'batida', name: 'Batida de Coco', jogo: 'expresso', color: '#d8cdb5' },
  { id: 'envelhecida', name: 'Cachaça Envelhecida', jogo: 'naipereal', color: '#c08a2a' },
].map((b) => ({ ...b, kind: 'bebida', cost: 3, desc: `Sobe o nível de ${JOGO_BY_ID[b.jogo].name}` }));

export const SIMPATIAS = [
  { id: 'ferradura', name: 'Ferradura', pick: 2, mod: 'ouro', desc: 'Até 2 pedras viram Douradas (+$3 ao jogar)' },
  { id: 'arruda', name: 'Arruda', pick: 2, mod: 'brasa', desc: 'Até 2 pedras viram Brasa (+4 Mult)' },
  { id: 'olhogrego', name: 'Olho Grego', pick: 1, mod: 'vidro', desc: '1 pedra vira Vidro (×2 Mult, pode quebrar)' },
  { id: 'coelho', name: 'Pé de Coelho', pick: 1, mod: 'coringa', desc: '1 pedra vira Coringa (encaixa em qualquer ponta)' },
  { id: 'fitinha', name: 'Fitinha', pick: 2, mod: 'marfim', desc: 'Até 2 pedras viram Marfim (+30 pontos)' },
  { id: 'sal', name: 'Sal Grosso', pick: 2, action: 'destroy', desc: 'Joga fora até 2 pedras do saco' },
  { id: 'espelho', name: 'Espelho', pick: 1, action: 'mirror', desc: '1 pedra vira a bucha do seu maior número' },
  { id: 'trevo', name: 'Trevo', pick: 0, action: 'money', desc: 'Dobra seu dinheiro (até +$20)' },
].map((s) => ({ ...s, kind: 'simpatia', cost: 4 }));

export const CONSUMIVEL_BY_ID = Object.fromEntries([...BEBIDAS, ...SIMPATIAS].map((c) => [c.id, c]));

// ---------- Donos de boteco (chefes) ----------
export const DONOS = [
  { id: 'fiscal', name: 'O Fiscal', desc: 'Buchas não pontuam', color: '#3b5a7a' },
  { id: 'mesquinho', name: 'Seu Mesquinho', desc: 'Só 1 troca', color: '#6a5a2a' },
  { id: 'pressa', name: 'Dona Pressa', desc: 'Só 3 jogadas', color: '#9a3a3a' },
  { id: 'apagao', name: 'O Apagão', desc: 'Pedras com branco não pontuam', color: '#2a2a3a' },
  { id: 'maocurta', name: 'Mão Curta', desc: '2 pedras a menos na mão', color: '#5a3a6a' },
  { id: 'paoduro', name: 'O Pão-Duro', desc: 'Cada jogada custa $1', color: '#4a6a3a' },
  { id: 'pontaseca', name: 'Ponta Seca', desc: 'No máximo 3 pedras por jogada', color: '#8a5a2a' },
  { id: 'ressaca', name: 'A Ressaca', desc: 'Todo jogo começa com Mult 1', color: '#6a2a4a' },
];
export const DONO_FINAL = { id: 'dono', name: 'O Dono do Boteco', desc: 'Só 3 jogadas e buchas não pontuam', color: '#1a1a1a' };

export const ANTE_BASE = [300, 800, 2000, 4500, 9000, 17000, 30000, 50000];
export const MESAS = [
  { name: 'Mesa do Canto', mult: 1, reward: 3 },
  { name: 'Mesa do Meio', mult: 1.5, reward: 4 },
  { name: 'Mesa do Dono', mult: 2, reward: 5 },
];
export const BOTECOS = [
  'Bar do Zé', 'Boteco da Esquina', 'Bar da Praça', 'Armazém Bom Gosto',
  'Bar Estrela', 'Boteco do Porto', 'Bar Saudade', 'Bar Final Feliz',
];
