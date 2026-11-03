// A mesa: corrente de pedras com duas pontas e o layout em "cobrinha".
// Coordenadas em unidades: meia-pedra = 1 x 1. Uma pedra = 2 x 1.
import { isDouble } from './tiles.js';

const LIMIT = 6.6; // meia-largura máxima de uma fileira antes de dobrar

export const isWild = (t) => t.mod === 'coringa';

export class Board {
  constructor() {
    this.placed = []; // {tile, side, near:{x,y}, far:{x,y}, nearVal, farVal}
    this.arms = null; // {L, R}
    this.history = [];
  }

  get empty() {
    return this.placed.length === 0;
  }

  get ends() {
    if (!this.arms) return null;
    return { L: this.arms.L.end, R: this.arms.R.end };
  }

  // Lados onde a pedra pode entrar. Se as duas pontas forem iguais, só oferece um.
  sidesFor(tile) {
    if (this.empty) return ['C'];
    const { L, R } = this.ends;
    const fits = (v) => isWild(tile) || tile.a === v || tile.b === v;
    const out = [];
    if (fits(L)) out.push('L');
    if (fits(R) && !(L === R && out.length)) out.push('R');
    return out;
  }

  canPlay(tile) {
    return this.sidesFor(tile).length > 0;
  }

  // Valor que fica exposto se a pedra entrar naquele lado.
  resultEnd(tile, side) {
    if (side === 'C') return null;
    const v = this.ends[side];
    return orient(tile, v).far;
  }

  place(tile, side) {
    this.history.push(JSON.stringify(this.arms));
    let rec;
    if (side === 'C' || this.empty) {
      rec = this._placeFirst(tile);
    } else {
      const arm = this.arms[side];
      const { near, far } = orient(tile, arm.end);
      rec = placeOnArm(arm, tile, near, far);
      rec.side = side;
      arm.end = far;
    }
    this.placed.push(rec);
    return rec;
  }

  undo() {
    if (!this.placed.length) return null;
    const rec = this.placed.pop();
    const prev = this.history.pop();
    this.arms = prev === 'null' || prev === undefined ? null : JSON.parse(prev);
    return rec;
  }

  _placeFirst(tile) {
    const dbl = isDouble(tile);
    let rec;
    if (dbl) {
      rec = { tile, side: 'C', near: { x: 0, y: -0.5 }, far: { x: 0, y: 0.5 }, nearVal: tile.a, farVal: tile.b };
      this.arms = {
        L: mkArm(-0.5, -1, tile.a),
        R: mkArm(0.5, 1, tile.b),
      };
    } else {
      rec = { tile, side: 'C', near: { x: -0.5, y: 0 }, far: { x: 0.5, y: 0 }, nearVal: tile.a, farVal: tile.b };
      this.arms = {
        L: mkArm(-1, -1, tile.a),
        R: mkArm(1, 1, tile.b),
      };
    }
    return rec;
  }

  // Onde a próxima pedra (não-bucha) apareceria — usado para desenhar os alvos.
  ghost(side) {
    if (this.empty) return { near: { x: -0.5, y: 0 }, far: { x: 0.5, y: 0 } };
    const arm = { ...this.arms[side] };
    const rec = placeOnArm(arm, { a: 0, b: 1 }, 0, 1);
    return { near: rec.near, far: rec.far };
  }

  bounds() {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const p of this.placed) {
      for (const h of [p.near, p.far]) {
        minX = Math.min(minX, h.x - 0.5);
        maxX = Math.max(maxX, h.x + 0.5);
        minY = Math.min(minY, h.y - 0.5);
        maxY = Math.max(maxY, h.y + 0.5);
      }
    }
    if (minX === Infinity) return { minX: -1, maxX: 1, minY: -0.5, maxY: 0.5 };
    return { minX, maxX, minY, maxY };
  }
}

function mkArm(cx, dir, end) {
  // dx: direção da fileira; ty: para onde dobra (direita desce, esquerda sobe)
  return { cx, cy: 0, dx: dir, ty: dir, mode: 'row', end };
}

export function orient(tile, endVal) {
  if (tile.a === endVal) return { near: tile.a, far: tile.b };
  if (tile.b === endVal) return { near: tile.b, far: tile.a };
  // coringa: encaixa em qualquer ponta e expõe o maior número
  return { near: endVal, far: Math.max(tile.a, tile.b) };
}

function placeOnArm(arm, tile, nearVal, farVal) {
  const d = arm.dx;
  const t = arm.ty;
  const c = { x: arm.cx, y: arm.cy };
  let near, far;
  if (arm.mode === 'hook') {
    near = { x: c.x + d * 0.5, y: c.y + t * 2 };
    far = { x: near.x - d, y: near.y };
    arm.cx = near.x - d * 1.5;
    arm.cy = near.y;
    arm.dx = -d;
    arm.mode = 'row';
  } else if (isDouble(tile)) {
    const cx = c.x + d * 0.5;
    near = { x: cx, y: c.y - 0.5 };
    far = { x: cx, y: c.y + 0.5 };
    arm.cx = c.x + d;
  } else if (Math.abs(c.x + d * 2) > LIMIT) {
    near = { x: c.x + d * 0.5, y: c.y };
    far = { x: near.x, y: c.y + t };
    arm.mode = 'hook';
  } else {
    near = { x: c.x + d * 0.5, y: c.y };
    far = { x: c.x + d * 1.5, y: c.y };
    arm.cx = c.x + d * 2;
  }
  return { tile, near, far, nearVal, farVal };
}
