// Pixel art procedural: todos os sprites são desenhados em código com uma paleta fixa.
window.ART = (function () {
  const P = {
    k: '#16120f', d: '#2b2420', b: '#4a3b30', B: '#5e4b3b', r: '#7a4a2c', o: '#b8692e', y: '#e0a640', Y: '#f5d27a',
    s: '#c9b48a', S: '#8f7e5c', g: '#5d6b3a', G: '#8c9a4c', t: '#9be04a', T: '#4f8a2b', c: '#6e7377', C: '#9da3a6',
    w: '#ece6d3', u: '#5ab0d8', U: '#2f6a96', p: '#b04a5a', q: '#6b2a35', v: '#b08af0', V: '#5a3f9a', m: '#33383e', M: '#5c636b'
  };
  const hex = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  const RGB = {}; for (const k in P) RGB[k] = hex(P[k]);
  function rng(seed) { let s = seed % 2147483647; if (s <= 0) s += 2147483646; return () => (s = s * 16807 % 2147483647) / 2147483647; }

  class Pix {
    constructor(w, h) { this.w = w; this.h = h || w; this.a = new Array(this.w * this.h).fill(null); }
    set(x, y, c) { x = Math.floor(x); y = Math.floor(y); if (x >= 0 && y >= 0 && x < this.w && y < this.h) this.a[y * this.w + x] = c; return this; }
    get(x, y) { return (x < 0 || y < 0 || x >= this.w || y >= this.h) ? null : this.a[y * this.w + x]; }
    rect(x, y, w, h, c) { for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) this.set(x + i, y + j, c); return this; }
    circ(cx, cy, r, c) { for (let y = 0; y < this.h; y++) for (let x = 0; x < this.w; x++) { const dx = x + 0.5 - cx, dy = y + 0.5 - cy; if (dx * dx + dy * dy <= r * r) this.set(x, y, c); } return this; }
    ell(cx, cy, rx, ry, c) { for (let y = 0; y < this.h; y++) for (let x = 0; x < this.w; x++) { const dx = (x + 0.5 - cx) / rx, dy = (y + 0.5 - cy) / ry; if (dx * dx + dy * dy <= 1) this.set(x, y, c); } return this; }
    line(x0, y0, x1, y1, c) { const n = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) || 1; for (let i = 0; i <= n; i++) this.set(x0 + (x1 - x0) * i / n + 0.5, y0 + (y1 - y0) * i / n + 0.5, c); return this; }
    // Luz vinda de cima: borda superior clareia, inferior escurece.
    shade(base, hi, lo) { const o = this.a.slice(); for (let y = 0; y < this.h; y++) for (let x = 0; x < this.w; x++) { if (o[y * this.w + x] !== base) continue; const up = y > 0 ? o[(y - 1) * this.w + x] : null; const dn = y < this.h - 1 ? o[(y + 1) * this.w + x] : null; if (hi && up !== base && up !== lo) this.a[y * this.w + x] = hi; else if (lo && dn !== base && dn !== hi) this.a[y * this.w + x] = lo; } return this; }
    outline(c) { c = c || 'k'; const o = this.a.slice(); for (let y = 0; y < this.h; y++) for (let x = 0; x < this.w; x++) { if (o[y * this.w + x]) continue; const n = [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dy]) => { const xx = x + dx, yy = y + dy; return xx >= 0 && yy >= 0 && xx < this.w && yy < this.h && o[yy * this.w + xx]; }); if (n) this.a[y * this.w + x] = c; } return this; }
    canvas() { const cv = document.createElement('canvas'); cv.width = this.w; cv.height = this.h; const x = cv.getContext('2d'); const id = x.createImageData(this.w, this.h); this.a.forEach((c, i) => { if (!c) return; const [r, g, b] = RGB[c]; id.data.set([r, g, b, 255], i * 4); }); x.putImageData(id, 0, 0); return cv; }
  }

  const D = {};
  D.rubble = seed => { const R = rng(seed), p = new Pix(16); p.ell(5.5, 10, 4.5, 3.5, 'c').ell(10.5, 8, 4.5, 4, 'c').ell(9, 12.5, 3.5, 2.5, 'M'); if (R() < 0.6) p.rect(2 + (R() * 4 | 0), 4, 3, 3, 'C'); p.shade('c', 'C', 'M'); p.line(3 + (R() * 3 | 0), 2, 7, 8, 'r').line(12, 3, 11 + (R() * 3 | 0), 7, 'o'); p.set(8, 9, 'm').set(9, 10, 'm'); return p.outline(); };
  D.barrel = f => { const p = new Pix(16); p.ell(8, 10, 4.5, 4, 'r').rect(4, 9, 9, 1, 'o').rect(4, 11, 9, 1, 'o').shade('r', 'o', 'q'); p.ell(8, 7.5, 3.5, 1.5, 'd'); const fl = f ? [[6, 6], [8, 3], [10, 5]] : [[6, 5], [8, 4], [10, 6]]; fl.forEach(([x, h]) => { p.rect(x - 1, 7 - h, 2, h, 'o'); p.rect(x - 1, 7 - h + 1, 1, h - 2, 'y'); p.set(x - 1, 7 - h + 2, 'Y'); }); return p.outline(); };
  D.core = () => { const p = new Pix(16); p.rect(2, 5, 12, 9, 'M').shade('M', 'C', 'm'); p.rect(3, 3, 10, 2, 'C'); p.rect(6, 10, 4, 4, 'm').rect(7, 11, 2, 3, 'k'); p.rect(4, 7, 2, 1, 'y').rect(10, 7, 2, 1, 'y'); p.line(12, 0, 12, 3, 'C').set(12, 0, 't'); for (let x = 1; x < 15; x += 3) p.ell(x + 1, 14.5, 1.6, 1.2, 's'); p.set(5, 3, 'p').set(4, 3, 'w'); return p.outline(); };
  D.base = () => { const p = new Pix(16); for (let i = 0; i < 10; i++) { const a = i / 10 * Math.PI * 2; p.ell(8 + Math.cos(a) * 5.4, 8 + Math.sin(a) * 5.4, 2, 1.6, i % 2 ? 's' : 'S'); } p.circ(8, 8, 4, 'm').circ(8, 8, 2.5, 'M'); return p.outline(); };
  D.gunner = () => { const p = new Pix(16); p.rect(5, 1, 2, 7, 'C').rect(9, 1, 2, 7, 'C').rect(5, 1, 2, 1, 'k').rect(9, 1, 2, 1, 'k'); p.circ(8, 9.5, 3.6, 'M').shade('M', 'C', 'm'); p.rect(6, 10, 4, 1, 'y'); return p.outline(); };
  D.mortar = () => { const p = new Pix(16); p.circ(8, 10, 4.2, 'g').shade('g', 'G', 'T'); p.rect(5, 2, 6, 7, 'G').rect(5, 2, 1, 7, 'g').rect(6, 2, 4, 2, 'k').rect(5, 6, 6, 1, 'y'); return p.outline(); };
  D.cryo = () => { const p = new Pix(16); p.circ(8, 10, 3.8, 'U'); for (let y = 1; y < 9; y++) { const w = y < 5 ? y - 1 : 8 - y; p.rect(8 - w / 2 - 0.5, y, w + 1, 1, 'u'); } p.set(7, 3, 'w').set(7, 4, 'w').set(8, 2, 'w'); p.rect(6, 10, 4, 1, 'u'); return p.outline(); };
  D.tesla = () => { const p = new Pix(16); p.circ(8, 10, 4.2, 'V'); p.rect(6, 5, 4, 7, 'c').rect(5, 7, 6, 1, 'r').rect(5, 9, 6, 1, 'r').rect(5, 11, 6, 1, 'r'); p.circ(8, 4, 2.6, 'v').set(7, 3, 'w').set(8, 3, 'w'); return p.outline(); };
  D.walker = f => { const p = new Pix(16); const a = f ? 1 : -1; p.rect(4, 3 + a, 2, 6, 'G').rect(10, 3 - a, 2, 6, 'G'); p.rect(5, 11, 2, 3 + a, 'd').rect(9, 11, 2, 3 - a, 'd'); p.ell(8, 9, 4.2, 2.6, 'b').rect(6, 8, 1, 2, 'r').rect(9, 9, 2, 1, 'r'); p.circ(8, 6.5, 2.6, 'G').shade('G', 't', 'g'); p.set(7, 5, 'p').set(9, 5, 'p'); return p.outline(); };
  D.runner = f => { const p = new Pix(16); const a = f ? 1 : -1; p.rect(5, 6 + a, 1, 3, 'q').rect(10, 6 - a, 1, 3, 'q').rect(5, 11 - a, 1, 3, 'q').rect(10, 11 + a, 1, 3, 'q'); p.ell(8, 9, 2.6, 4.5, 'r').shade('r', 'o', 'q'); p.circ(8, 4, 2.2, 'o').set(6, 2, 'r').set(10, 2, 'r').set(7, 3, 'y').set(9, 3, 'y'); p.line(8, 13, 8 + a, 15, 'r'); return p.outline(); };
  D.boss = f => { const p = new Pix(24); const a = f ? 1 : -1; p.circ(4, 9 + a * 1.5, 3.4, 'p').circ(20, 9 - a * 1.5, 3.4, 'p'); p.ell(12, 13, 8, 6, 'q').shade('q', 'p', 'k'); p.circ(9, 13, 1.4, 't').circ(15, 15, 1.2, 't').circ(13, 11, 0.9, 't'); p.circ(12, 8, 3.8, 'G').shade('G', 't', 'g'); p.set(10, 7, 'y').set(14, 7, 'y').rect(11, 10, 3, 1, 'k'); p.rect(7, 18, 3, 4 + a, 'd').rect(14, 18, 3, 4 - a, 'd'); return p.outline(); };
  D.bullet = () => new Pix(4).rect(1, 0, 2, 4, 'Y').rect(1, 0, 2, 1, 'w');
  D.shell = () => new Pix(6).circ(3, 3, 2.6, 'm').set(2, 2, 'C').outline();
  D.shard = () => { const p = new Pix(6); p.rect(2, 0, 2, 6, 'u').set(2, 1, 'w').set(2, 2, 'w'); return p; };
  D.select = () => { const p = new Pix(16); [[0, 0], [11, 0], [0, 11], [11, 11]].forEach(([x, y]) => { p.rect(x, y, 5, 5, null); }); const L = (x, y, dx, dy) => { for (let i = 0; i < 4; i++) { p.set(x + dx * i, y, 'Y'); p.set(x, y + dy * i, 'Y'); } }; L(0, 0, 1, 1); L(15, 0, -1, 1); L(0, 15, 1, -1); L(15, 15, -1, -1); return p; };
  D.coin = () => new Pix(8).circ(4, 4, 3, 'y').set(3, 2, 'Y').set(3, 3, 'Y').rect(4, 3, 1, 3, 'o').outline();
  D.heart = () => { const p = new Pix(8); p.circ(2.7, 3, 1.9, 'p').circ(5.3, 3, 1.9, 'p'); for (let y = 3; y < 7; y++) p.rect(1 + (y - 3), y, 6 - 2 * (y - 3), 1, 'p'); p.set(2, 2, 'w'); return p.outline(); };
  D.ess = () => { const p = new Pix(8); for (let y = 0; y < 8; y++) { const w = y < 4 ? y : 7 - y; p.rect(4 - w, y, w * 2, 1, 't'); } p.set(3, 2, 'w'); return p.outline(); };
  D.skull = () => { const p = new Pix(8); p.circ(4, 3.5, 3, 'w').rect(2, 5, 4, 2, 'w').set(3, 3, 'k').set(5, 3, 'k').set(3, 6, 'k').set(5, 6, 'k'); return p.outline(); };

  const cache = {}, texCache = {};
  function canvas(name, arg) { const key = name + (arg !== undefined ? ':' + arg : ''); if (!cache[key]) cache[key] = D[name](arg).canvas(); return cache[key]; }
  function tex(name, arg) {
    const key = name + (arg !== undefined ? ':' + arg : '');
    if (!texCache[key]) { const t = new THREE.CanvasTexture(canvas(name, arg)); t.magFilter = t.minFilter = THREE.NearestFilter; t.generateMipmaps = false; texCache[key] = t; }
    return texCache[key];
  }
  // Ícone de torre (base + cabeça) ampliado para a interface.
  function towerIcon(type, scale) {
    scale = scale || 3; const cv = document.createElement('canvas'); cv.width = cv.height = 16 * scale;
    const x = cv.getContext('2d'); x.imageSmoothingEnabled = false;
    x.drawImage(canvas('base'), 0, 0, cv.width, cv.height); x.drawImage(canvas(type), 0, 0, cv.width, cv.height);
    return cv.toDataURL();
  }
  function icon(name, scale) { const c = canvas(name); const cv = document.createElement('canvas'); cv.width = c.width * scale; cv.height = c.height * scale; const x = cv.getContext('2d'); x.imageSmoothingEnabled = false; x.drawImage(c, 0, 0, cv.width, cv.height); return cv.toDataURL(); }

  // Glow em degraus (estilo pixel) para iluminação aditiva.
  function glowTex() {
    const n = 32, cv = document.createElement('canvas'); cv.width = cv.height = n; const x = cv.getContext('2d'); const id = x.createImageData(n, n);
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) { const d = Math.hypot(i + 0.5 - n / 2, j + 0.5 - n / 2) / (n / 2); const a = d >= 1 ? 0 : Math.ceil((1 - d) * 4) / 4; id.data.set([255, 255, 255, Math.round(a * a * 255)], (j * n + i) * 4); }
    x.putImageData(id, 0, 0); const t = new THREE.CanvasTexture(cv); t.magFilter = t.minFilter = THREE.NearestFilter; t.generateMipmaps = false; return t;
  }

  // Chão inteiro do mapa num único canvas (mapa + margem de 2 tiles).
  function ground(cols, rows, m, spawns, core) {
    const W = (cols + 2 * m) * 16, H = (rows + 2 * m) * 16, R = rng(1337);
    const cv = document.createElement('canvas'); cv.width = W; cv.height = H; const x = cv.getContext('2d'); const id = x.createImageData(W, H);
    const put = (px, py, c, a) => { if (px < 0 || py < 0 || px >= W || py >= H) return; const [r, g, b] = RGB[c]; const i = (py * W + px) * 4; const al = a === undefined ? 1 : a; id.data[i] = id.data[i] * (1 - al) + r * al; id.data[i + 1] = id.data[i + 1] * (1 - al) + g * al; id.data[i + 2] = id.data[i + 2] * (1 - al) + b * al; id.data[i + 3] = 255; };
    for (let py = 0; py < H; py++) for (let px = 0; px < W; px++) {
      const inside = px >= m * 16 && py >= m * 16 && px < (m + cols) * 16 && py < (m + rows) * 16;
      const v = R();
      if (inside) put(px, py, v < 0.04 ? 'd' : v < 0.12 ? 'B' : v < 0.135 ? 'S' : 'b');
      else put(px, py, v < 0.35 ? 'k' : v < 0.95 ? 'd' : 'b');
    }
    // manchas de areia e rachaduras
    for (let i = 0; i < 26; i++) { const cx = R() * W, cy = R() * H, rr = 3 + R() * 7; for (let py = cy - rr; py < cy + rr; py++) for (let px = cx - rr; px < cx + rr; px++) if (Math.hypot(px - cx, py - cy) < rr && R() < 0.7) put(px | 0, py | 0, 'S', 0.35); }
    for (let i = 0; i < 18; i++) { let px = R() * W, py = R() * H; for (let s = 0; s < 14; s++) { put(px | 0, py | 0, 'k', 0.7); px += R() * 2 - 1; py += R() * 2 - 1 + (i % 2 ? 0.6 : -0.6); } }
    // grade sutil para construir
    for (let c = 0; c <= cols; c++) for (let py = m * 16; py < (m + rows) * 16; py++) if (py % 2 === 0) put((m + c) * 16 - (c === cols ? 1 : 0), py, 'k', 0.5);
    for (let r = 0; r <= rows; r++) for (let px = m * 16; px < (m + cols) * 16; px++) if (px % 2 === 0) put(px, (m + r) * 16 - (r === rows ? 1 : 0), 'k', 0.5);
    // estradas de entrada com faixas de perigo
    spawns.forEach(s => {
      let x0, y0, w, h;
      if (s.r === 0) { x0 = (m + s.c) * 16; y0 = 0; w = 16; h = m * 16; } else if (s.c === 0) { x0 = 0; y0 = (m + s.r) * 16; w = m * 16; h = 16; } else { x0 = (m + cols) * 16; y0 = (m + s.r) * 16; w = m * 16; h = 16; }
      for (let py = y0; py < y0 + h; py++) for (let px = x0; px < x0 + w; px++) put(px, py, ((px + py) >> 2) % 2 ? 'y' : 'k', 0.55);
    });
    // base de concreto sob o bunker
    const bx = (m + core.c) * 16, by = (m + core.r) * 16;
    for (let py = by - 2; py < by + 16; py++) for (let px = bx - 2; px < bx + 18; px++) put(px, py, (px + py) % 7 === 0 ? 'M' : 'c', 0.9);
    x.putImageData(id, 0, 0);
    const t = new THREE.CanvasTexture(cv); t.magFilter = t.minFilter = THREE.NearestFilter; t.generateMipmaps = false; return t;
  }

  return { P, tex, canvas, towerIcon, icon, glowTex, ground };
})();
