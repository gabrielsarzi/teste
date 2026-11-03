// Dominó clássico brasileiro: 4 jogadores em duplas, 7 pedras cada.
// Assentos: 0 = você (baixo), 1 = direita, 2 = parceiro (cima), 3 = esquerda.
// A vez anda para a direita: 0 → 1 → 2 → 3.
import { Board } from '../core/board.js';
import { fullSet, isDouble, pipSum, makeRng } from '../core/tiles.js';

export const teamOf = (p) => p % 2; // 0 = Nós (0 e 2), 1 = Eles (1 e 3)

export const DEFAULT_RULES = {
  buchaVale2: true, // bater com bucha vale 2
  laeloVale2: false, // bater lá-e-lô (pedra que serve nas duas pontas) vale 2
  comecaSena: true, // primeira rodada começa com a bucha de sena
  formato: 'rodadas', // 'rodadas' (4, um início de cada) | 'pontos' (até 6)
  metaPontos: 6,
};

export class ClassicMatch {
  constructor(rules = {}, seed) {
    this.rules = { ...DEFAULT_RULES, ...rules };
    this.rng = makeRng(seed);
    this.score = [0, 0];
    this.roundNo = 0;
    this.firstStarter = null;
    this.lastStarter = null;
    this.history = []; // resultados de cada rodada
  }

  get totalRounds() {
    return 4;
  }

  isOver() {
    if (this.rules.formato === 'pontos') return Math.max(...this.score) >= this.rules.metaPontos;
    // 4 rodadas; se empatar, segue rodada de desempate
    return this.roundNo >= 4 && this.score[0] !== this.score[1];
  }

  winnerTeam() {
    return this.score[0] > this.score[1] ? 0 : 1;
  }

  newRound() {
    this.roundNo++;
    const tiles = this.rng.shuffle(fullSet());
    const hands = [0, 1, 2, 3].map((i) => tiles.slice(i * 7, i * 7 + 7));
    let starter;
    let mustStartWith = null;
    if (this.roundNo === 1) {
      const holder = hands.findIndex((h) => h.some((t) => t.a === 6 && t.b === 6));
      starter = holder;
      this.firstStarter = holder;
      if (this.rules.comecaSena) mustStartWith = hands[holder].find((t) => t.a === 6 && t.b === 6);
    } else {
      starter = (this.lastStarter + 1) % 4; // rodízio: cada um começa uma
    }
    this.lastStarter = starter;
    this.round = new ClassicRound(hands, starter, mustStartWith, this.rules);
    return this.round;
  }

  applyResult(res) {
    if (res.team != null) this.score[res.team] += res.points;
    this.history.push(res);
  }
}

export class ClassicRound {
  constructor(hands, starter, mustStartWith, rules) {
    this.hands = hands;
    this.rules = rules;
    this.board = new Board();
    this.turn = starter;
    this.starter = starter;
    this.mustStartWith = mustStartWith;
    this.lacks = [new Set(), new Set(), new Set(), new Set()]; // números que cada um mostrou não ter
    this.passesInRow = 0;
    this.log = [];
    this.result = null;
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

  // Esta jogada fecharia o jogo? (ninguém mais consegue jogar)
  wouldClose(tile, side) {
    if (this.board.empty) return false;
    const ends = { ...this.board.ends };
    const far = this.board.resultEnd(tile, side);
    ends[side] = far;
    for (let p = 0; p < 4; p++) {
      for (const t of this.hands[p]) {
        if (t === tile) continue;
        if (t.a === ends.L || t.b === ends.L || t.a === ends.R || t.b === ends.R) return false;
      }
    }
    return this.hands.reduce((n, h) => n + h.length, 0) > 1;
  }

  play(p, tile, side) {
    if (p !== this.turn || this.result) throw new Error('fora da vez');
    const ok = this.legalMoves(p).some((m) => m.tile === tile && m.side === side);
    if (!ok) throw new Error('jogada inválida');
    const endsBefore = this.board.empty ? null : { ...this.board.ends };
    const rec = this.board.place(tile, side);
    this.mustStartWith = null;
    this.hands[p] = this.hands[p].filter((t) => t !== tile);
    this.passesInRow = 0;
    this.log.push({ p, type: 'play', tile, side });

    if (this.hands[p].length === 0) {
      // batida
      let points = 1;
      const kinds = [];
      const laelo =
        endsBefore &&
        endsBefore.L !== endsBefore.R &&
        [endsBefore.L, endsBefore.R].every((v) => tile.a === v || tile.b === v);
      if (isDouble(tile) && this.rules.buchaVale2) {
        points = 2;
        kinds.push('bucha');
      }
      if (laelo && this.rules.laeloVale2) {
        points = Math.max(points, 2) + (kinds.length ? 1 : 0);
        kinds.push('laelo');
      }
      this.result = { type: 'batida', winner: p, team: p % 2, points, kinds, tile };
      return { rec, result: this.result };
    }
    if (this.isBlocked()) {
      const sums = [0, 1, 2, 3].map((i) => this.hands[i].reduce((s, t) => s + pipSum(t), 0));
      const teamSums = [sums[0] + sums[2], sums[1] + sums[3]];
      let team = null;
      if (teamSums[0] < teamSums[1]) team = 0;
      else if (teamSums[1] < teamSums[0]) team = 1;
      this.result = { type: 'fechado', closer: p, team, points: team == null ? 0 : 1, sums, teamSums };
      return { rec, result: this.result };
    }
    this.turn = (p + 1) % 4;
    return { rec, result: null };
  }

  isBlocked() {
    if (this.board.empty) return false;
    for (let p = 0; p < 4; p++) for (const t of this.hands[p]) if (this.board.canPlay(t)) return false;
    return true;
  }

  pass(p) {
    if (this.legalMoves(p).length) throw new Error('não pode passar com pedra na mão');
    const { L, R } = this.board.ends;
    this.lacks[p].add(L);
    this.lacks[p].add(R);
    this.passesInRow++;
    this.log.push({ p, type: 'pass' });
    this.turn = (p + 1) % 4;
  }
}
