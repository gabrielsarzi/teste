// Dominó clássico brasileiro.
// 4 jogadores: duplas (0 e 2 contra 1 e 3), 7 pedras cada, sem compra.
// 2 ou 3 jogadores: cada um por si, 7 pedras cada e o resto fica no monte para compra.
// A vez anda para a direita: 0 → 1 → 2 → 3.
import { Board } from '../core/board.js';
import { fullSet, isDouble, pipSum, makeRng } from '../core/tiles.js';

export const DEFAULT_RULES = {
  players: 4,
  buchaVale2: true, // bater com bucha vale 2
  laeloVale2: true, // bater com pedra que entra nos dois lados vale 2
  comecaSena: true, // primeira rodada começa com a maior bucha (a sena, no jogo de 4)
  cincoBuchas: true, // quem recebe 5 buchas ou mais: volta o jogo
  votacao: true, // fechar forçado (a pedra cabia na outra ponta) vai para votação
  metaPontos: 4, // a partida acaba quando alguém completa a cruz
};

export class ClassicMatch {
  constructor(rules = {}, seed) {
    this.rules = { ...DEFAULT_RULES, ...rules };
    this.n = this.rules.players;
    this.teams = this.n === 4 ? 2 : this.n;
    this.rng = makeRng(seed);
    this.score = new Array(this.teams).fill(0);
    this.roundNo = 0;
    this.lastStarter = null;
    this.history = [];
  }

  teamOf(p) {
    return this.n === 4 ? p % 2 : p;
  }

  isOver() {
    return Math.max(...this.score) >= this.rules.metaPontos;
  }

  winnerTeam() {
    let best = 0;
    for (let t = 1; t < this.teams; t++) if (this.score[t] > this.score[best]) best = t;
    return best;
  }

  // Sorteia as mãos. Se alguém tiver 5 buchas ou mais (e a regra estiver ligada),
  // a rodada volta: round.voltou = jogador, e a tela chama redeal().
  newRound() {
    this.roundNo++;
    return this._deal();
  }

  redeal() {
    return this._deal();
  }

  _deal() {
    const n = this.n;
    const tiles = this.rng.shuffle(fullSet());
    const hands = [];
    for (let i = 0; i < n; i++) hands.push(tiles.slice(i * 7, i * 7 + 7));
    const pile = tiles.slice(n * 7);
    if (globalThis.__forceCincoBuchas && n === 4) {
      // só para testes: força 5 buchas na mão de um jogador
      const who = globalThis.__forceCincoBuchas - 1;
      globalThis.__forceCincoBuchas = 0;
      const all = [...hands.flat()];
      const dbl = all.filter(isDouble).slice(0, 5);
      const rest = all.filter((t) => !dbl.includes(t));
      hands[who] = [...dbl, ...rest.splice(0, 2)];
      for (let q = 0, k = 0; q < 4; q++) if (q !== who) (hands[q] = rest.slice(k * 7, k * 7 + 7)), k++;
    }
    if (this.rules.cincoBuchas) {
      const p = hands.findIndex((h) => h.filter(isDouble).length >= 5);
      if (p >= 0) {
        this.round = new ClassicRound(hands, pile, 0, null, this);
        this.round.voltou = p;
        return this.round;
      }
    }
    let starter;
    let mustStartWith = null;
    if (this.roundNo === 1) {
      // sai quem tem a maior bucha (a sena, quando ela está na mão de alguém)
      let best = null;
      hands.forEach((h, p) => {
        for (const t of h) if (isDouble(t) && (!best || t.a > best.t.a)) best = { t, p };
      });
      starter = best ? best.p : 0;
      if (best && this.rules.comecaSena) mustStartWith = best.t;
    } else {
      starter = (this.lastStarter + 1) % n; // rodízio da saída
    }
    this.lastStarter = starter;
    this.round = new ClassicRound(hands, pile, starter, mustStartWith, this);
    return this.round;
  }

  applyResult(res) {
    if (res.team != null) this.score[res.team] += res.points;
    this.history.push(res);
  }
}

export class ClassicRound {
  constructor(hands, pile, starter, mustStartWith, match) {
    this.match = match;
    this.n = hands.length;
    this.hands = hands;
    this.pile = pile || [];
    this.rules = match.rules;
    this.board = new Board();
    this.turn = starter;
    this.starter = starter;
    this.mustStartWith = mustStartWith;
    this.lacks = hands.map(() => new Set()); // números que cada um mostrou não ter
    this.log = [];
    this.result = null;
  }

  teamOf(p) {
    return this.n === 4 ? p % 2 : p;
  }

  legalMoves(p) {
    const hand = this.hands[p];
    if (this.board.empty) {
      if (this.mustStartWith) return hand.includes(this.mustStartWith) ? [{ tile: this.mustStartWith, side: 'C' }] : [];
      return hand.map((tile) => ({ tile, side: 'C' }));
    }
    const out = [];
    for (const tile of hand) for (const side of this.board.sidesFor(tile)) out.push({ tile, side });
    return out;
  }

  canDraw(p) {
    return this.pile.length > 0 && this.legalMoves(p).length === 0 && !this.board.empty;
  }

  // Compra uma pedra do monte (só quando não tem jogo).
  draw(p) {
    if (!this.canDraw(p)) throw new Error('não pode comprar');
    const { L, R } = this.board.ends;
    this.lacks[p].add(L);
    this.lacks[p].add(R);
    const t = this.pile.pop();
    this.hands[p].push(t);
    this.log.push({ p, type: 'draw' });
    return t;
  }

  // Esta jogada fecharia o jogo? (ninguém mais consegue jogar e não há monte)
  wouldClose(tile, side) {
    if (this.board.empty || this.pile.length) return false;
    const ends = { ...this.board.ends };
    ends[side] = this.board.resultEnd(tile, side);
    for (const h of this.hands) {
      for (const t of h) {
        if (t === tile) continue;
        if (t.a === ends.L || t.b === ends.L || t.a === ends.R || t.b === ends.R) return false;
      }
    }
    return this.hands.reduce((n, h) => n + h.length, 0) > 1;
  }

  // Fechou forçado: a pedra fecha deste lado, mas no outro lado o jogo seguiria aberto.
  forcedClose(tile, side) {
    if (!this.wouldClose(tile, side)) return null;
    const other = this.board.sidesFor(tile).find((s) => s !== side);
    if (other && !this.wouldClose(tile, other)) return other;
    // pontas iguais: sidesFor devolve só uma; testa a outra ponta explicitamente
    if (!other && this.board.ends.L === this.board.ends.R) {
      const alt = side === 'L' ? 'R' : 'L';
      if (!this.wouldClose(tile, alt)) return alt;
    }
    return null;
  }

  play(p, tile, side) {
    if (p !== this.turn || this.result) throw new Error('fora da vez');
    const ok = this.legalMoves(p).some((m) => m.tile === tile && (m.side === side || (this.board.ends && this.board.ends.L === this.board.ends.R)));
    if (!ok) throw new Error('jogada inválida');
    const endsBefore = this.board.empty ? null : { ...this.board.ends };
    const rec = this.board.place(tile, side);
    this.mustStartWith = null;
    this.hands[p] = this.hands[p].filter((t) => t !== tile);
    this.log.push({ p, type: 'play', tile, side });

    if (this.hands[p].length === 0) {
      let points = 1;
      const kinds = [];
      const laelo = endsBefore && endsBefore.L !== endsBefore.R && [endsBefore.L, endsBefore.R].every((v) => tile.a === v || tile.b === v);
      if (isDouble(tile) && this.rules.buchaVale2) {
        points = 2;
        kinds.push('bucha');
      }
      if (laelo && this.rules.laeloVale2) {
        points = 2;
        kinds.push('laelo');
      }
      this.result = { type: 'batida', winner: p, team: this.teamOf(p), points, kinds, tile };
      return { rec, result: this.result };
    }
    if (this.isBlocked()) return { rec, result: this._closeResult(p) };
    this.turn = (p + 1) % this.n;
    return { rec, result: null };
  }

  _closeResult(closer) {
    const sums = this.hands.map((h) => h.reduce((s, t) => s + pipSum(t), 0));
    const nT = this.n === 4 ? 2 : this.n;
    const teamSums = new Array(nT).fill(0);
    sums.forEach((v, q) => (teamSums[this.teamOf(q)] += v));
    const min = Math.min(...teamSums);
    const winners = teamSums.map((v, t) => (v === min ? t : -1)).filter((t) => t >= 0);
    const team = winners.length === 1 ? winners[0] : null;
    this.result = { type: 'fechado', closer, team, points: team == null ? 0 : 1, sums, teamSums };
    return this.result;
  }

  isBlocked() {
    if (this.board.empty || this.pile.length) return false;
    for (const h of this.hands) for (const t of h) if (this.board.canPlay(t)) return false;
    return true;
  }

  pass(p) {
    if (this.legalMoves(p).length) throw new Error('não pode passar com pedra na mão');
    if (this.pile.length && !this.board.empty) throw new Error('tem que comprar');
    if (!this.board.empty) {
      const { L, R } = this.board.ends;
      this.lacks[p].add(L);
      this.lacks[p].add(R);
    }
    this.log.push({ p, type: 'pass' });
    this.turn = (p + 1) % this.n;
    // com compra, o monte pode acabar sem ninguém conseguir jogar: fecha aqui
    if (this.isBlocked()) {
      const last = [...this.log].reverse().find((e) => e.type === 'play');
      this._closeResult(last ? last.p : p);
    }
  }
}
