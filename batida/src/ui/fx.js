// Efeitos: partículas num canvas por cima de tudo, textos flutuantes e tremida de tela.
import { h } from './dom.js';

let canvas, c2d, parts = [], running = false, dpr = 1;
const reduce = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export function initFx(root) {
  canvas = h('canvas', { class: 'fx-canvas', 'aria-hidden': 'true' });
  root.append(canvas);
  c2d = canvas.getContext('2d');
  const resize = () => {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = innerWidth * dpr;
    canvas.height = innerHeight * dpr;
  };
  resize();
  addEventListener('resize', resize);
}

function loop() {
  if (!parts.length) {
    running = false;
    c2d.clearRect(0, 0, canvas.width, canvas.height);
    return;
  }
  running = true;
  c2d.setTransform(dpr, 0, 0, dpr, 0, 0);
  c2d.clearRect(0, 0, innerWidth, innerHeight);
  const now = performance.now();
  parts = parts.filter((p) => now - p.t0 < p.life);
  for (const p of parts) {
    const k = (now - p.t0) / p.life;
    p.vy += p.g;
    p.vx *= p.drag;
    p.vy *= p.drag;
    p.x += p.vx;
    p.y += p.vy;
    p.rot += p.vr;
    c2d.save();
    c2d.globalAlpha = Math.max(0, 1 - k * k);
    c2d.translate(p.x, p.y);
    c2d.rotate(p.rot);
    c2d.fillStyle = p.color;
    if (p.shape === 'rect') c2d.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
    else if (p.shape === 'spark') {
      c2d.globalCompositeOperation = 'lighter';
      c2d.beginPath();
      c2d.arc(0, 0, p.size * (1 - k * 0.6), 0, Math.PI * 2);
      c2d.fill();
    } else {
      c2d.beginPath();
      c2d.arc(0, 0, p.size, 0, Math.PI * 2);
      c2d.fill();
    }
    c2d.restore();
  }
  requestAnimationFrame(loop);
}

function add(p) {
  parts.push({ vr: 0, rot: 0, g: 0, drag: 0.98, shape: 'dot', t0: performance.now(), ...p });
  if (!running) requestAnimationFrame(loop);
}

export function burstAt(x, y, { n = 14, colors = ['#f2b33d', '#fff1c9'], speed = 4, size = 2.4, life = 600, g = 0.08, shape = 'spark' } = {}) {
  if (reduce()) n = Math.min(n, 4);
  for (let i = 0; i < n; i++) {
    const a = Math.random() * Math.PI * 2;
    const s = speed * (0.4 + Math.random());
    add({
      x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s - 1, g, size: size * (0.6 + Math.random() * 0.8),
      color: colors[i % colors.length], life: life * (0.6 + Math.random() * 0.6), shape,
    });
  }
}

export function burstEl(el, opts) {
  if (!el) return;
  const r = el.getBoundingClientRect();
  burstAt(r.left + r.width / 2, r.top + r.height / 2, opts);
}

export function confetti(n = 90) {
  if (reduce()) n = 20;
  const colors = ['#f2b33d', '#e2483b', '#2f6f9f', '#f3ecdc', '#4f9a5a'];
  for (let i = 0; i < n; i++) {
    add({
      x: innerWidth * Math.random(), y: -20 - Math.random() * 120,
      vx: (Math.random() - 0.5) * 3, vy: 1.5 + Math.random() * 3, g: 0.05, drag: 0.995,
      vr: (Math.random() - 0.5) * 0.3, size: 9 + Math.random() * 6, color: colors[i % colors.length],
      life: 2600 + Math.random() * 1200, shape: 'rect',
    });
  }
}

// poeira de giz para o placar
export function chalkDust(el) {
  burstEl(el, { n: 10, colors: ['rgba(240,238,228,.9)', 'rgba(240,238,228,.5)'], speed: 1.6, size: 1.6, life: 700, g: 0.03, shape: 'dot' });
}

export function floatText(text, x, y, cls = '') {
  const el = h('div', { class: `float-text ${cls}`, style: { left: x + 'px', top: y + 'px' } }, text);
  document.getElementById('app').append(el);
  setTimeout(() => el.remove(), 1100);
  return el;
}

export function floatAtEl(el, text, cls = '', dy = -10) {
  if (!el) return;
  const r = el.getBoundingClientRect();
  floatText(text, r.left + r.width / 2, r.top + dy, cls);
}

export function shake(power = 1) {
  if (reduce()) return;
  const app = document.getElementById('stage') || document.getElementById('app');
  app.style.setProperty('--shake', `${Math.min(10, 2 + power * 3)}px`);
  app.classList.remove('shaking');
  void app.offsetWidth;
  app.classList.add('shaking');
  setTimeout(() => app.classList.remove('shaking'), 420);
}

export function pop(el, cls = 'pop') {
  if (!el) return;
  el.classList.remove(cls);
  void el.offsetWidth;
  el.classList.add(cls);
}
