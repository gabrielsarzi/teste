// Marcas de uso na mesa: anéis de copo e riscos finos, por baixo das pedras.
import { h } from './dom.js';

function marksSvg(seed) {
  const r = mulberry(seed);
  let out = '';
  // anéis de copo: círculos que não fecham, com borda irregular
  for (let i = 0; i < 3; i++) {
    const cx = 15 + r() * 70;
    const cy = 12 + r() * 76;
    const rad = 5.2 + r() * 1.2;
    const op = 0.12 + r() * 0.1;
    const start = r() * 360;
    const len = 250 + r() * 100;
    out += `<circle cx="${cx}%" cy="${cy}%" r="${rad}%" fill="none" stroke="rgb(40,20,8)" stroke-opacity="${op}" stroke-width="${2 + r() * 2}" stroke-dasharray="${len} 1000" stroke-dashoffset="${start}" transform-origin="${cx}% ${cy}%" style="filter:blur(.6px)"/>`;
    out += `<circle cx="${cx}%" cy="${cy}%" r="${rad - 0.6}%" fill="rgb(60,30,10)" fill-opacity="${op * 0.25}"/>`;
  }
  // riscos finos e claros
  for (let i = 0; i < 7; i++) {
    const x = r() * 100;
    const y = r() * 100;
    const ang = r() * Math.PI;
    const l = 4 + r() * 12;
    out += `<line x1="${x}%" y1="${y}%" x2="${x + Math.cos(ang) * l}%" y2="${y + Math.sin(ang) * l}%" stroke="rgb(255,235,200)" stroke-opacity="${0.06 + r() * 0.08}" stroke-width="${0.6 + r() * 0.8}" stroke-linecap="round"/>`;
  }
  return `<svg class="marks" aria-hidden="true">${out}</svg>`;
}

function mulberry(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function tableDecor() {
  const el = h('div', { class: 'decor', 'aria-hidden': 'true' });
  el.innerHTML = marksSvg(Math.floor(Math.random() * 1e9));
  return { el };
}
