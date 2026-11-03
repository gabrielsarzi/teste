// Utilitários de DOM pequenos e diretos.
export function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on')) el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'html') el.innerHTML = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) {
    if (k == null || k === false) continue;
    el.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
  return el;
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms * speedFactor()));

let speed = 1;
export const setSpeed = (s) => (speed = s);
export const speedFactor = () => speed;

export function fmt(n) {
  n = Math.floor(n);
  if (n >= 1e9) return (n / 1e9).toFixed(n >= 1e10 ? 0 : 1).replace('.', ',') + ' bi';
  return n.toLocaleString('pt-BR');
}
export const fmtMult = (m) => (Number.isInteger(m) ? String(m) : m.toFixed(m >= 100 ? 0 : 1).replace('.', ','));

export const store = {
  get(k, def) {
    try {
      const v = localStorage.getItem('batida:' + k);
      return v == null ? def : JSON.parse(v);
    } catch {
      return def;
    }
  },
  set(k, v) {
    try {
      localStorage.setItem('batida:' + k, JSON.stringify(v));
    } catch {
      /* armazenamento indisponível */
    }
  },
  del(k) {
    try {
      localStorage.removeItem('batida:' + k);
    } catch {
      /* ignore */
    }
  },
};

// Modal simples sobre a tela. Retorna {el, close}.
export function modal(content, { onClose, dismissable = true, cls = '' } = {}) {
  const back = h('div', { class: 'modal-back' });
  const card = h('div', { class: `modal ${cls}`, role: 'dialog', 'aria-modal': 'true' }, content);
  back.append(card);
  const close = () => {
    back.classList.add('out');
    setTimeout(() => back.remove(), 180);
    onClose && onClose();
  };
  if (dismissable) back.addEventListener('click', (e) => e.target === back && close());
  document.getElementById('app').append(back);
  return { el: card, close };
}

export function toast(text, kind = '') {
  const t = h('div', { class: `toast ${kind}` }, text);
  document.getElementById('app').append(t);
  setTimeout(() => t.classList.add('out'), 1800);
  setTimeout(() => t.remove(), 2200);
}
