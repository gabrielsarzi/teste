// Desenho das pedras (DOM + CSS) e da mesa com zoom automático.
import { h } from './dom.js';
import { burstAt } from './fx.js';
import { sfx, haptic } from './audio.js';

const PIPS = {
  0: [],
  1: ['c'],
  2: ['tl', 'br'],
  3: ['tl', 'c', 'br'],
  4: ['tl', 'tr', 'bl', 'br'],
  5: ['tl', 'tr', 'c', 'bl', 'br'],
  6: ['tl', 'tr', 'ml', 'mr', 'bl', 'br'],
};

function half(v, pos) {
  return h('div', { class: `half ${pos} n${v}` }, PIPS[v].map((p) => h('i', { class: `pip ${p}` })));
}

// top = valor de cima, bot = valor de baixo (pedra em pé)
export function tileEl(tile, { top = tile.a, bot = tile.b, u, cls = '' } = {}) {
  const el = h(
    'div',
    { class: `tile ${tile.mod ? 'mod-' + tile.mod : ''} ${tile.a === tile.b ? 'dbl' : ''} ${cls}`, 'data-uid': tile.uid },
    half(top, 'top'),
    half(bot, 'bot'),
    h('span', { class: 'rivet' }),
  );
  if (tile.bonus) el.append(h('span', { class: 'tile-badge' }, `+${tile.bonus}`));
  if (u) el.style.setProperty('--u', u + 'px');
  return el;
}

export function backEl(u, cls = '') {
  const el = h('div', { class: `tile back ${cls}` }, h('span', { class: 'azulejo' }));
  if (u) el.style.setProperty('--u', u + 'px');
  return el;
}

const BASE = 40; // tamanho base da meia-pedra dentro da mesa

export class BoardView {
  constructor({ onPickSide } = {}) {
    this.el = h('div', { class: 'board' });
    this.layer = h('div', { class: 'board-layer' });
    this.el.append(this.layer);
    this.items = new Map(); // uid -> el
    this.targets = [];
    this.onPickSide = onPickSide;
    this.k = 1;
    this.ro = new ResizeObserver(() => this.fit());
    this.ro.observe(this.el);
  }

  destroy() {
    this.ro.disconnect();
  }

  clear() {
    this.layer.innerHTML = '';
    this.items.clear();
    this.targets = [];
  }

  // transforma um registro da mesa em pedra posicionada
  _transform(rec) {
    const cx = (rec.near.x + rec.far.x) / 2;
    const cy = (rec.near.y + rec.far.y) / 2;
    const vx = rec.far.x - rec.near.x;
    const vy = rec.far.y - rec.near.y;
    let ang = 0;
    if (vx > 0.5) ang = -90;
    else if (vx < -0.5) ang = 90;
    else if (vy < -0.5) ang = 180;
    return `translate(${cx * BASE - BASE / 2}px, ${cy * BASE - BASE}px) rotate(${ang}deg)`;
  }

  addRec(rec, { pending = false } = {}) {
    const el = tileEl(rec.tile, { top: rec.nearVal, bot: rec.farVal, u: BASE, cls: pending ? 'pending' : '' });
    el.style.transform = this._transform(rec);
    this.layer.append(el);
    this.items.set(rec.tile.uid, el);
    return el;
  }

  removeTile(tile) {
    const el = this.items.get(tile.uid);
    if (el) el.remove();
    this.items.delete(tile.uid);
  }

  setPending(on) {
    for (const el of this.items.values()) if (!on) el.classList.remove('pending');
  }

  rebuild(board, pendingUids = new Set()) {
    this.clear();
    for (const rec of board.placed) this.addRec(rec, { pending: pendingUids.has(rec.tile.uid) });
    this.board = board;
    this.fit(true);
  }

  fit(instant = false) {
    const board = this.board;
    if (!board) return;
    const b = board.bounds();
    // inclui os alvos na conta para não ficarem fora da tela
    for (const t of this.targets) {
      for (const hpos of [t.g.near, t.g.far]) {
        b.minX = Math.min(b.minX, hpos.x - 0.5);
        b.maxX = Math.max(b.maxX, hpos.x + 0.5);
        b.minY = Math.min(b.minY, hpos.y - 0.5);
        b.maxY = Math.max(b.maxY, hpos.y + 0.5);
      }
    }
    const pad = 1.2;
    const w = (b.maxX - b.minX + pad * 2) * BASE;
    const hh = (b.maxY - b.minY + pad * 2) * BASE;
    const aw = this.el.clientWidth || 300;
    const ah = this.el.clientHeight || 300;
    const k = Math.min(aw / w, ah / hh, 1.25);
    const mx = ((b.minX + b.maxX) / 2) * BASE;
    const my = ((b.minY + b.maxY) / 2) * BASE;
    this.k = k;
    if (instant) this.layer.style.transition = 'none';
    this.layer.style.transform = `translate(${-mx * k}px, ${-my * k}px) scale(${k})`;
    if (instant) {
      void this.layer.offsetWidth;
      this.layer.style.transition = '';
    }
  }

  // anima uma pedra vinda de um retângulo de origem (mão ou assento) até a mesa
  async flyIn(rec, fromRect, { pending = false, power = 1, faceDown = false } = {}) {
    const el = this.addRec(rec, { pending });
    this.board = this.board || null;
    el.style.visibility = 'hidden';
    this.fit();
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    const target = el.getBoundingClientRect();
    const tcx = target.left + target.width / 2;
    const tcy = target.top + target.height / 2;
    const size = BASE * this.k;
    const vx = rec.far.x - rec.near.x;
    const vy = rec.far.y - rec.near.y;
    const ang = vx > 0.5 ? -90 : vx < -0.5 ? 90 : vy < -0.5 ? 180 : 0;
    const clone = tileEl(rec.tile, { top: rec.nearVal, bot: rec.farVal, u: size, cls: 'flying' });
    if (faceDown) clone.classList.add('reveal');
    Object.assign(clone.style, {
      position: 'fixed', left: tcx - size / 2 + 'px', top: tcy - size + 'px', zIndex: 60, margin: 0,
    });
    document.getElementById('app').append(clone);
    const fcx = fromRect ? fromRect.left + fromRect.width / 2 : tcx;
    const fcy = fromRect ? fromRect.top + fromRect.height / 2 : tcy - 80;
    const s0 = fromRect ? Math.max(0.35, fromRect.width / size) : 1;
    const anim = clone.animate(
      [
        { transform: `translate(${fcx - tcx}px, ${fcy - tcy}px) scale(${s0}) rotate(0deg)`, offset: 0 },
        { transform: `translate(${(fcx - tcx) * 0.25}px, ${(fcy - tcy) * 0.25 - 26}px) scale(${1.25}) rotate(${ang * 0.8}deg)`, offset: 0.62 },
        { transform: `translate(0,0) scale(1) rotate(${ang}deg)`, offset: 1 },
      ],
      { duration: 340, easing: 'cubic-bezier(.3,.7,.4,1)' },
    );
    await anim.finished.catch(() => {});
    clone.remove();
    el.style.visibility = '';
    el.classList.add('landed');
    sfx.clack(power);
    haptic(10);
    burstAt(tcx, tcy, { n: 8, colors: ['#f6e7c3', '#c99a5b'], speed: 2.2, size: 1.8, life: 380, g: 0.05, shape: 'dot' });
    return el;
  }

  showTargets(board, sides, onPick) {
    this.hideTargets();
    this.board = board;
    for (const side of sides) {
      const g = side === 'C' ? { near: { x: -0.5, y: 0 }, far: { x: 0.5, y: 0 } } : board.ghost(side);
      const el = h('button', { class: 'target', 'aria-label': side === 'L' ? 'Ponta esquerda' : 'Ponta direita' });
      el.style.transform = this._transform({ near: g.near, far: g.far });
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        onPick(side);
      });
      this.layer.append(el);
      this.targets.push({ el, g, side });
    }
    this.fit();
  }

  hideTargets() {
    for (const t of this.targets) t.el.remove();
    this.targets = [];
  }
}
