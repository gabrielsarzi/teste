// Conversa de boteco: provocações, reações e comentários conforme o jogo.
// Cada evento tem falas gerais; um personagem pode ter as próprias (CAST[id].lines[evento]).
import { CAST } from './cast.js';

const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

// Falas gerais por evento
const POOL = {
  start: ['Embaralhou direito isso aí?', 'Hoje eu tô com sorte.', 'Valendo a cerveja, hein!', 'Vamo que vamo.', 'Pedra boa hoje, viu.'],
  start_lead: ['Mais uma pra conta!', 'Já tá no papo.', 'Segue o baile.'],
  start_behind: ['Agora vira!', 'Essa rodada é nossa.', 'Calma que ainda dá.'],
  mock_pass: ['Passou! Ha!', 'Tá sem, é?', 'Trancado, trancado!', 'Ih, travou!', 'Passa, passa, que a vez é nossa.', 'Sem pedra? Que pena...'],
  console_pass: ['Relaxa, eu seguro.', 'Tranquilo, parça.', 'Deixa comigo agora.'],
  self_pass_opp: ['Passo, mas volto.', 'Calma, tô só esperando.'],
  one_left_self: ['Tô com uma, hein!', 'Última pedra!', 'Olha a batida vindo...'],
  one_left_warn: ['Ele tá com uma, cuidado!', 'Segura que ele vai bater!', 'Trava ele, parça!'],
  dump_sena: ['Livrou da sena, né?', 'Pesada essa, hein.', 'Tava com medo dela, né?'],
  bucha_player: ['Bucha na mesa!', 'Lá vai bucha!'],
  close_us: ['Fechei! Conta aí!', 'Fechadinho. Vamo contar.', 'Fecha e conta!'],
  win_round: ['É nós!', 'Mais uma!', 'Anota aí na lousa!', 'Quem manda aqui?'],
  lose_round: ['Foi sorte.', 'Essa passou...', 'Próxima é nossa.', 'Ah, não acredito!'],
  partner_good: ['Boa, parça!', 'Isso, joga assim!', 'É disso que eu tô falando!'],
  lacks_trap: ['Trancou ele bonito!', 'Pegou na ponta, hein!'],
};

export function say(id, event) {
  const own = CAST[id] && CAST[id].lines[event];
  const pool = own && Math.random() < 0.6 ? own : POOL[event];
  return pool ? pick(pool) : null;
}

// Frases que você pode mandar. to: para quem é a mensagem.
export const PLAYER_PHRASES = [
  { id: 'medo', text: 'Tá com medo, é?', to: 'opp', tag: 'provoca' },
  { id: 'bingo', text: 'Isso é dominó ou bingo?', to: 'opp', tag: 'provoca' },
  { id: 'pato', text: 'Hoje tem pato na mesa!', to: 'opp', tag: 'provoca' },
  { id: 'chorar', text: 'Vai chorar?', to: 'opp', tag: 'provoca' },
  { id: 'sorte', text: 'Isso foi sorte!', to: 'opp', tag: 'provoca' },
  { id: 'sono', text: 'Bate logo que eu tô com sono.', to: 'opp', tag: 'provoca' },
  { id: 'boa', text: 'Boa, parça!', to: 'partner', tag: 'elogio' },
  { id: 'segura', text: 'Segura essa ponta aí!', to: 'partner', tag: 'pede' },
  { id: 'confia', text: 'Confia em mim!', to: 'partner', tag: 'pede' },
  { id: 'gg', text: 'Jogaram bem!', to: 'opp', tag: 'respeito' },
  { id: 'garcom', text: 'Garçom, desce mais uma!', to: 'all', tag: 'paz' },
  { id: 'calma', text: 'Calma, gente, é só um jogo.', to: 'all', tag: 'paz' },
];

// Reações: dependem do tipo da frase, de quem responde e do placar (ahead = a dupla de quem responde está na frente)
const REACT = {
  provoca: {
    opp: ['Fala muito e joga pouco!', 'Quero ver no final.', 'Olha quem fala!', 'Tá nervoso? Respira.', 'Conversa é com a pedra.', 'Joga e fica quieto!'],
    opp_ahead: ['Provoca perdendo? Olha a lousa!', 'Fala isso depois de ganhar uma.', 'Kkkk, olha o placar!'],
    opp_behind: ['Tá ganhando agora, depois a gente vê.', 'Aproveita enquanto dura.', 'Calma que o jogo vira.'],
    partner: ['Isso, provoca eles!', 'Kkkk, pegou pesado!', 'Calma que a gente amassa.'],
  },
  elogio: {
    partner: ['Tamo junto!', 'Deixa comigo!', 'É nós!', 'Valeu, parça!'],
    opp: ['Ih, tão se achando.', 'Comemora não que ainda tem jogo.'],
  },
  pede: {
    partner: ['Pode deixar!', 'Tô ligado!', 'Entendi o recado.', 'Segurando!'],
    opp: ['Ih, tão combinando!', 'Sem sinal na mesa, hein!', 'Olha a malandragem!'],
  },
  respeito: {
    opp: ['Valeu. Vocês também.', 'Respeito na mesa.', 'Obrigado, mas não vou aliviar.'],
    opp_ahead: ['Valeu! Mas a vitória é nossa.'],
    partner: ['Educado, hein, parça.'],
  },
  paz: {
    opp: ['Isso mesmo!', 'Desce duas!', 'Paz e dominó.', 'Aí sim!'],
    partner: ['Pede uma pra mim também!', 'Agora sim, falou bonito.'],
  },
};

// Escolhe quem responde e o quê. seats: 1 e 3 adversários, 2 parceiro.
export function reactTo(phrase, { usAhead, usBehind }) {
  const r = REACT[phrase.tag];
  const out = [];
  const opp = Math.random() < 0.5 ? 1 : 3;
  const oppPool = (usAhead && r.opp_behind) || (usBehind && r.opp_ahead) || r.opp;
  if (phrase.to === 'opp') {
    if (oppPool) out.push({ p: opp, text: pick(oppPool) });
    if (r.partner && Math.random() < 0.35) out.push({ p: 2, text: pick(r.partner) });
    if (phrase.tag === 'provoca' && Math.random() < 0.3) out.push({ p: opp === 1 ? 3 : 1, text: pick(r.opp) });
  } else if (phrase.to === 'partner') {
    out.push({ p: 2, text: pick(r.partner) });
    if (r.opp && Math.random() < 0.45) out.push({ p: opp, text: pick(r.opp) });
  } else {
    out.push({ p: Math.random() < 0.5 ? 2 : opp, text: pick(Math.random() < 0.5 && r.partner ? r.partner : r.opp) });
  }
  return out;
}
