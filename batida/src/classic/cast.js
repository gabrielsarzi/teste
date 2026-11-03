// Elenco do boteco: rostos, falas e nível de jogo.
// skill: 0..1 (heurística). master: número de simulações da IA mestre (0 = não usa).

const BRONCAS = ['Ó o gato!', 'Isso é gato!', 'Deu gato, hein!', 'Gato! Essa não entra.', 'Opa, gato na mesa!'];

export const CAST = {
  rafa: {
    name: 'Rafa', face: { skin: 1, hair: 'bone', bg: '#2c5f8e', extra: 'barba' }, skill: 0.8,
    lines: { pass: ['Tô sem, parça!', 'Passo, segura aí!'], bucha: ['Bucha na mesa!'], bater: ['Bati, parça!'], bronca: ['Calma, parça, isso é gato.', 'Ó o gato, parça!'] },
  },
  zezao: {
    name: 'Zezão', mania: { buchaTalk: true }, face: { skin: 2, hair: 'careca', stache: 'cheio', bg: '#c4512f', extra: 'palito' }, skill: 0.2,
    lines: { pass: ['Passo!', 'Ih, passei.'], bucha: ['Toma essa bucha!'], bater: ['Bati, rapaziada!'], bronca: ['Ó o gato!', 'Gato! Essa não entra não.'] },
  },
  naldo: {
    name: 'Naldo', face: { skin: 3, hair: 'curto', stache: 'fino', bg: '#3d7a4a', extra: 'copo' }, skill: 0.3,
    lines: { pass: ['Passo, passo.', 'Não tenho.'], bucha: ['Lá vai bucha!'], bater: ['Batidaaa!'], bronca: ['Isso é gato, rapaz!', 'Deu gato!'] },
  },
  rogerio: {
    name: 'Tio Rogério', mania: { slow: 1.6 }, face: { skin: 0, hair: 'chapeu', stache: 'cheio', bg: '#7a4b2a' }, skill: 0.45,
    lines: { pass: ['Passo, sobrinho.', 'Tô fora dessa.'], bucha: ['No meu tempo era assim!'], bater: ['Aprende com o tio!'], bronca: ['Gato, sobrinho! Olha a ponta.', 'No meu tempo isso era gato!'] },
  },
  bia: {
    name: 'Bia', face: { skin: 1, hair: 'longo', bg: '#b23a5a', extra: 'brinco' }, skill: 0.5,
    lines: { pass: ['Passo.', 'Sem jogo.'], bucha: ['Bucha, amor!'], bater: ['Bati!'], bronca: ['Opa, gato!', 'Gato! Não vale.'] },
  },
  tonhao: {
    name: 'Tonhão', mania: { slam: true }, face: { skin: 3, hair: 'bone', bg: '#8a5a2a', extra: 'barba' }, skill: 0.55,
    lines: { pass: ['Passo!'], bucha: ['Pesada essa!'], bater: ['Bati, cambada!'], bronca: ['Gatooo!', 'Tá dando gato, é?'] },
  },
  neide: {
    name: 'Dona Neide', mania: { slow: 1.4 }, face: { skin: 1, hair: 'coque', bg: '#5c5a8a', extra: 'oculos' }, skill: 0.6,
    lines: { pass: ['Passo, meu filho.'], bucha: ['Uma buchinha...'], bater: ['Bati, queridos.'], bronca: ['Isso é gato, meu filho.', 'Gato não, querido.'] },
  },
  juninho: {
    name: 'Juninho', mania: { fast: true }, face: { skin: 2, hair: 'curto', bg: '#2f7f7a' }, skill: 0.6,
    lines: { pass: ['Passo, mano.'], bucha: ['Olha a bucha!'], bater: ['Bati, já era!'], bronca: ['Gato, mano!', 'Ó o gato aí!'] },
  },
  paulao: {
    name: 'Paulão', mania: { slam: true }, face: { skin: 2, hair: 'capacete', bg: '#c9a227', ink: '#2a1d14', stache: 'cheio' }, skill: 0.7,
    lines: { pass: ['Passo.'], bucha: ['Bucha de pedreiro!'], bater: ['Obra entregue!'], bronca: ['Gato! Essa não assenta.', 'Ó o gato!'] },
  },
  lurdinha: {
    name: 'Lurdinha', face: { skin: 3, hair: 'lenco', bg: '#d08a2a', extra: 'brinco' }, skill: 0.75,
    lines: { pass: ['Passei.'], bucha: ['Essa doeu, hein?'], bater: ['Bati, sem dó!'], bronca: ['Gato! Tá distraído?', 'Deu gato!'] },
  },
  valter: {
    name: 'Sargento Válter', face: { skin: 1, hair: 'quepe', stache: 'cheio', bg: '#33465c', ink: '#f3ecdc' }, skill: 0.85, master: 10,
    lines: { pass: ['Passo. Sem alteração.'], bucha: ['Bucha, em frente!'], bater: ['Missão cumprida.'], bronca: ['Negativo! Isso é gato.', 'Gato detectado!'] },
  },
  edu: {
    name: 'Professor Edu', face: { skin: 0, hair: 'curto', bg: '#1f5a46', ink: '#f3ecdc', extra: 'oculos' }, skill: 0.9, master: 18,
    lines: { pass: ['Passo, conforme previsto.'], bucha: ['Elementar.'], bater: ['Fim da aula.'], bronca: ['Gato. Matemática básica.', 'Isso é gato, colega.'] },
  },
  cida: {
    name: 'Dona Cida', face: { skin: 2, hair: 'coque', bg: '#7d8a3a', extra: 'oculos' }, skill: 0.9, master: 24,
    lines: { pass: ['Passo.'], bucha: ['Guarda essa.'], bater: ['Bati. Próxima.'], bronca: ['Gato.', 'Ó o gato!'] },
  },
  bene: {
    name: 'Mestre Bené', mania: { slow: 1.3, slam: true }, face: { skin: 3, hair: 'chapeu', stache: 'cheio', bg: '#151515', ink: '#f2c14e', extra: 'barba' }, skill: 1, master: 40,
    lines: { pass: ['Hum. Passo.'], bucha: ['Bucha de mestre.'], bater: ['Quarenta anos de mesa, menino.'], bronca: ['Gato. Respeita a pedra.', 'Isso é gato, menino.'] },
  },
  marquinhos: {
    name: 'Marquinhos', face: { skin: 1, hair: 'bone', bg: '#6b3e8a' }, skill: 0.35,
    lines: { pass: ['Passo aí.'], bucha: ['Bucha!'], bater: ['Ganhei, ganhei!'], bronca: ['Gato, gato!', 'Ó o gato!'] },
  },
  careca: {
    name: 'Careca', mania: { buchaTalk: true }, face: { skin: 0, hair: 'careca', bg: '#9a3324', blush: true, extra: 'copo' }, skill: 0.4,
    lines: { pass: ['Passo, garçom traz mais uma!'], bucha: ['Bucha gelada!'], bater: ['Bati, saideira!'], bronca: ['Gato! Bebeu, é?', 'Deu gato!'] },
  },
};

const DEFAULT_LINES = {
  pass: ['Passo!', 'Passo.', 'Tô sem.'],
  bucha: ['Bucha!', 'Lá vai bucha!'],
  bater: ['Bati!', 'Batida!'],
};

// Jogador online (ou convidado) que não é do elenco: ganha um lugar no CAST com falas padrão.
export function guest(id, name, skill = 0.6) {
  if (!CAST[id]) CAST[id] = { name, skill, face: {}, lines: {} };
  CAST[id].name = name;
  return id;
}

export function line(id, kind) {
  const c = CAST[id];
  const pool = (c && c.lines[kind]) || (kind === 'bronca' ? BRONCAS : DEFAULT_LINES[kind] || ['...']);
  return pool[Math.floor(Math.random() * pool.length)];
}

// ---------- Carreira: campeonatos ----------
// Cada campeonato: quartas, semi e final contra duplas cada vez melhores.
export const CAMPEONATOS = [
  {
    id: 'boteco', fee: 20, cash: 100, name: 'Torneio do Boteco do Zezão', short: 'Boteco do Zezão', place: 'Bairro',
    format: { formato: 'pontos', metaPontos: 4 },
    duplas: [['zezao', 'naldo'], ['marquinhos', 'careca'], ['rogerio', 'bia']],
    prize: { mesa: 'plastico' },
  },
  {
    id: 'praca', fee: 50, cash: 250, name: 'Copa da Praça', short: 'Copa da Praça', place: 'Praça da Matriz',
    format: { formato: 'pontos', metaPontos: 4 },
    duplas: [['naldo', 'marquinhos'], ['bia', 'tonhao'], ['rogerio', 'neide']],
    prize: { domino: 'colorido' },
  },
  {
    id: 'clube', fee: 100, cash: 500, name: 'Campeonato do Clube', short: 'Clube Recreativo', place: 'Clube Recreativo',
    format: { formato: 'pontos', metaPontos: 4 },
    duplas: [['tonhao', 'juninho'], ['neide', 'paulao'], ['lurdinha', 'paulao']],
    prize: { mesa: 'feltro' },
  },
  {
    id: 'cidade', fee: 200, cash: 1000, name: 'Copa da Cidade', short: 'Copa da Cidade', place: 'Ginásio Municipal',
    format: { formato: 'pontos', metaPontos: 4 },
    duplas: [['juninho', 'lurdinha'], ['paulao', 'valter'], ['valter', 'edu']],
    prize: { domino: 'preto' },
  },
  {
    id: 'estadual', fee: 400, cash: 2000, name: 'Estadual de Dominó', short: 'Estadual', place: 'Centro de Convenções',
    format: { formato: 'pontos', metaPontos: 4 },
    duplas: [['lurdinha', 'valter'], ['edu', 'cida'], ['cida', 'valter']],
    prize: { mesa: 'marmore' },
  },
  {
    id: 'brasileirao', fee: 800, cash: 5000, name: 'Brasileirão de Dominó', short: 'Brasileirão', place: 'Final nacional',
    format: { formato: 'pontos', metaPontos: 4 },
    duplas: [['edu', 'valter'], ['cida', 'edu'], ['bene', 'cida']],
    prize: { domino: 'dourado', mesa: 'toalha' },
  },
];
export const FASES = ['Quartas de final', 'Semifinal', 'Final'];

// ---------- Visual: mesas e dominós ----------
export const MESAS_VISUAL = [
  { id: 'madeira', name: 'Madeira de boteco', desc: 'A mesa de sempre.', price: 0 },
  { id: 'plastico', name: 'Mesa de plástico', desc: 'Amarela, de bar de calçada.', price: 150 },
  { id: 'feltro', name: 'Feltro verde', desc: 'Mesa de clube, pano novo.', price: 400 },
  { id: 'marmore', name: 'Mármore de padaria', desc: 'Fria, lisa e chique.', price: 900 },
  { id: 'toalha', name: 'Toalha xadrez', desc: 'Domingo na casa da vó.', price: 1500 },
  { id: 'carvalho', name: 'Carvalho claro', desc: 'Madeira clara de mesa nova.', price: 300 },
  { id: 'sinuca', name: 'Pano vinho', desc: 'Pano de mesa de sinuca, cor de vinho.', price: 600 },
  { id: 'noite', name: 'Feltro azul-noite', desc: 'Pano azul-escuro de cassino.', price: 750 },
  { id: 'concreto', name: 'Mesa da praça', desc: 'Concreto com tabuleiro pintado, igual da praça.', price: 1100 },
  { id: 'azulejo', name: 'Azulejo português', desc: 'Azul e branco, de bar antigo.', price: 2000 },
];
export const DOMINOS_VISUAL = [
  { id: 'osso', name: 'Osso clássico', desc: 'Pedra branca com pinta preta.', price: 0 },
  { id: 'colorido', name: 'Pintas coloridas', desc: 'Cada número com sua cor.', price: 250 },
  { id: 'preto', name: 'Pedra preta', desc: 'Preta com pinta branca.', price: 700 },
  { id: 'dourado', name: 'Dourado de campeão', desc: 'Só para quem ganhou o Brasileirão.', price: null },
  { id: 'marfim', name: 'Marfim antigo', desc: 'Amarelado de tanto jogo.', price: 200 },
  { id: 'madeira', name: 'Pedra de madeira', desc: 'Madeira lixada com pinta queimada.', price: 450 },
  { id: 'azul', name: 'Azul royal', desc: 'Azul forte com pinta branca.', price: 600 },
  { id: 'vermelho', name: 'Vermelho cereja', desc: 'Vermelha e brilhante.', price: 600 },
  { id: 'jade', name: 'Verde jade', desc: 'Verde de pedra polida.', price: 1200 },
  { id: 'acrilico', name: 'Acrílico', desc: 'Transparente, de jogo novo.', price: 1800 },
];

// Parceiros que você pode contratar na carreira (pagando uma vez).
export const PARCEIROS = [
  { id: 'rafa', price: 0, skill: 0.6, pitch: 'Seu parceiro de sempre. Joga direitinho.' },
  { id: 'bia', price: 150, skill: 0.7, pitch: 'Esperta e boa de conversa.' },
  { id: 'juninho', price: 300, skill: 0.78, pitch: 'Rápido no gatilho, joga sem medo.' },
  { id: 'lurdinha', price: 800, skill: 0.86, pitch: 'Conta pedra como ninguém.' },
  { id: 'edu', price: 2500, skill: 0.92, master: 18, pitch: 'Professor de matemática. Quase não erra.' },
];

// Desafio do dia: adversário muda conforme o dia da semana.
export const DESAFIO_OPPS = ['zezao', 'naldo', 'rogerio', 'bia', 'tonhao', 'neide', 'paulao'];
