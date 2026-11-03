// Visual "D": campo de grama seca, sprites em visão 3/4 com sombra e trilha pisoteada.
window.ART3 = (function () {
  const hx = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  function rng(seed) { let s = seed % 2147483647; if (s <= 0) s += 2147483646; return () => (s = s * 16807 % 2147483647) / 2147483647; }
  function cv(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d'); x.imageSmoothingEnabled = false; return [c, x]; }
  const OUT = '#1b1626';

  class Px {
    constructor(w, h) { this.w = w; this.h = h || w; this.a = new Array(this.w * this.h).fill(null); }
    set(x, y, c) { x = Math.floor(x); y = Math.floor(y); if (x >= 0 && y >= 0 && x < this.w && y < this.h) this.a[y * this.w + x] = c; return this; }
    rect(x, y, w, h, c) { for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) this.set(x + i, y + j, c); return this; }
    ell(cx, cy, rx, ry, c) { for (let y = 0; y < this.h; y++) for (let x = 0; x < this.w; x++) { const dx = (x + 0.5 - cx) / rx, dy = (y + 0.5 - cy) / ry; if (dx * dx + dy * dy <= 1) this.set(x, y, c); } return this; }
    line(x0, y0, x1, y1, c) { const n = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) || 1; for (let i = 0; i <= n; i++) this.set(x0 + (x1 - x0) * i / n + 0.5, y0 + (y1 - y0) * i / n + 0.5, c); return this; }
    outline(c) { c = c || OUT; const o = this.a.slice(); for (let y = 0; y < this.h; y++) for (let x = 0; x < this.w; x++) { if (o[y * this.w + x]) continue; if ([[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dy]) => { const X = x + dx, Y = y + dy; return X >= 0 && Y >= 0 && X < this.w && Y < this.h && o[Y * this.w + X]; })) this.a[y * this.w + x] = c; } return this; }
    canvas() { const [c, x] = cv(this.w, this.h); const id = x.createImageData(this.w, this.h); this.a.forEach((col, i) => { if (col) id.data.set([...hx(col), 255], i * 4); }); x.putImageData(id, 0, 0); return c; }
  }

  // ---------- Zumbis (olhando para a direita; o jogo espelha) ----------
  const ZV = [
    { skin: '#8fbf6a', skinD: '#6f9a52', shirt: '#c9b458', shirtD: '#a38f3e', pants: '#3b3a52', hair: '#2a2233', blood: 1 },
    { skin: '#8fbf6a', skinD: '#6f9a52', shirt: '#b5473f', shirtD: '#8a3330', pants: '#3b3a52', hair: '#6b4a2e', blood: 0 },
    { skin: '#9cc77a', skinD: '#7aa25c', shirt: '#4f78a8', shirtD: '#3a5a82', pants: '#4a3b30', hair: '#2a2233', blood: 1 }
  ];
  function walker(v, f) {
    const o = ZV[v % ZV.length], p = new Px(16, 20), a = f ? 1 : 0;
    p.rect(6, 14, 2, 5 - a, o.pants).rect(9, 14, 2, 4 + a, o.pants).rect(6, 18 - a, 2, 1, '#2a2233').rect(9, 17 + a, 2, 1, '#2a2233');
    p.rect(9, 10, 5, 2, o.skinD);
    p.rect(5, 8, 6, 7, o.shirt).rect(5, 8, 1, 7, o.shirtD).rect(5, 13, 6, 1, o.shirtD);
    if (o.blood) p.set(8, 10, '#8f2f3c').set(9, 12, '#8f2f3c');
    p.rect(9, 9 + a, 6, 2, o.skin);
    p.rect(5, 2, 6, 6, o.skin).rect(5, 2, 6, 2, o.hair).rect(5, 2, 2, 5, o.hair);
    p.set(9, 4, '#ffffff').set(10, 4, '#c0392b').set(9, 6, '#4a2a2a').set(10, 6, '#4a2a2a');
    return p.outline();
  }
  function runner(f) {
    const p = new Px(16, 18), a = f ? 1 : 0;
    p.line(6, 12, 3 + a * 2, 17, '#3d3550').line(9, 12, 11 - a * 2, 17, '#3d3550');
    p.ell(8, 10, 3.6, 2.6, '#5d7fb5').rect(5, 9, 2, 3, '#45659a');
    p.line(10, 9, 15, 11 - a, '#8fbf6a');
    p.rect(9, 4, 5, 5, '#a3cf7a').rect(9, 4, 5, 1, '#2a2233').set(12, 6, '#e74c3c').set(13, 8, '#4a2a2a');
    return p.outline();
  }
  function boss(f) {
    const p = new Px(28, 28), a = f ? 1 : 0;
    p.rect(8, 21, 4, 6 - a, '#3b3a52').rect(16, 21, 4, 5 + a, '#3b3a52');
    p.ell(14, 15, 11, 9, '#6f9a52').ell(14, 14, 10, 8, '#8fbf6a');
    [[9, 12, 2], [18, 17, 1.6], [15, 10, 1.2], [11, 19, 1.3]].forEach(([x, y, r]) => p.ell(x, y, r, r, '#c6f06b'));
    p.line(6, 15, 12, 20, '#3d3550').line(17, 9, 21, 13, '#3d3550');
    p.ell(24, 13 + a, 3.5, 3, '#8fbf6a').ell(4, 14 - a, 3.5, 3, '#6f9a52');
    p.rect(10, 2, 8, 7, '#a3cf7a').rect(10, 2, 8, 2, '#2a2233').set(15, 5, '#ffffff').set(16, 5, '#e74c3c').rect(14, 7, 4, 1, '#4a2a2a');
    return p.outline();
  }
  // ---------- Torres (olhando para a direita) ----------
  function tower(type) {
    const p = new Px(16, 22);
    p.ell(8, 17, 7.5, 4.2, '#c8b07a').ell(8, 16.4, 7, 3.4, '#ddc792').ell(8, 16.6, 4.4, 2, '#8a7650');
    for (let i = 1; i < 15; i += 4) p.set(i, 17, '#a8915e');
    p.rect(7, 11, 2, 6, '#56566a');
    if (type === 'gunner') { p.rect(4, 6, 8, 6, '#6c6f80').rect(4, 6, 8, 1, '#9da0b2').rect(11, 7, 5, 2, '#2f2f3d').rect(11, 10, 5, 1, '#2f2f3d').rect(5, 9, 3, 1, '#f1c40f'); }
    if (type === 'mortar') { p.rect(4, 8, 8, 5, '#6b7d3a').rect(4, 8, 8, 1, '#8ea04c'); p.line(7, 8, 12, 2, '#55663a').line(8, 8, 13, 2, '#55663a').line(9, 8, 14, 3, '#55663a'); p.rect(12, 1, 3, 2, '#2a2233'); }
    if (type === 'cryo') { p.rect(5, 9, 6, 3, '#3f6f9a'); for (let y = 1; y < 10; y++) { const w = y < 5 ? y : 10 - y; p.rect(8 - w / 2, y, w + 1, 1, '#7fd3f5'); } p.set(7, 3, '#ffffff').set(7, 4, '#ffffff'); }
    if (type === 'tesla') { p.rect(6, 5, 4, 7, '#6c6f80').rect(5, 6, 6, 1, '#c27c3a').rect(5, 8, 6, 1, '#c27c3a').rect(5, 10, 6, 1, '#c27c3a'); p.ell(8, 3.5, 3, 2.6, '#b48cff').set(7, 2, '#ffffff'); }
    return p.outline();
  }
  function bunker() {
    const p = new Px(32, 28);
    p.rect(3, 8, 26, 16, '#8d8a99').rect(3, 8, 26, 2, '#b4b1c2').rect(3, 22, 26, 2, '#6e6b7c');
    p.rect(1, 5, 30, 4, '#6e6b7c').rect(1, 5, 30, 1, '#9b98ab');
    p.rect(13, 14, 6, 10, '#3b3a52').rect(14, 15, 4, 9, '#2a2233').rect(15, 19, 1, 1, '#f1c40f');
    p.rect(6, 12, 4, 2, '#f1c40f').rect(22, 12, 4, 2, '#f1c40f');
    p.rect(24, 0, 1, 5, '#b4b1c2').set(24, 0, '#7bed6b');
    for (let x = 0; x < 32; x += 5) p.ell(x + 2.5, 25.5, 2.6, 1.8, '#ddc792');
    p.rect(9, 6, 14, 2, '#c0392b').rect(10, 6, 2, 2, '#ece6d3');
    return p.outline();
  }
  // ---------- Obstáculos do campo ----------
  const OB = {
    rock: s => { const r = rng(s * 31 + 7), p = new Px(16, 14); p.ell(8, 9, 6.5, 4.5, '#8f8a96').ell(7, 7.5, 5, 3.5, '#aaa5b0').ell(6, 6.5, 2, 1.2, '#c6c1cc'); if (r() > 0.5) p.ell(12.5, 10.5, 2.5, 2, '#8f8a96'); return p.outline(); },
    bush: () => { const p = new Px(16, 14); p.ell(5, 9, 4.5, 4, '#4f7a3a').ell(11, 9, 4.5, 4, '#4f7a3a').ell(8, 6, 5, 4.5, '#5f9142').ell(7, 4.5, 2, 1.4, '#79ad55').set(5, 9, '#e85a71').set(11, 7, '#e85a71'); return p.outline(); },
    crate: () => { const p = new Px(14, 14); p.rect(1, 1, 12, 12, '#b07a3c').rect(1, 1, 12, 1, '#d19a52').line(2, 2, 12, 12, '#8b5a2b').line(12, 2, 2, 12, '#8b5a2b').rect(1, 6, 12, 1, '#8b5a2b'); return p.outline(); },
    tires: () => { const p = new Px(14, 14); [[7, 10], [7, 6]].forEach(([x, y]) => { p.ell(x, y, 6, 2.8, '#2f2f3d').ell(x, y, 2.6, 1.2, '#55556a'); }); return p.outline(); },
    barrel: f => { const p = new Px(12, 20); p.rect(1, 8, 10, 11, '#c0392b').rect(1, 8, 2, 11, '#e74c3c').rect(1, 11, 10, 1, '#8e2a20').rect(1, 15, 10, 1, '#8e2a20').rect(4, 12, 3, 2, '#f1c40f').ell(6, 8, 5, 1.4, '#3a2a20');
      const fl = f ? [[3, 5], [6, 7], [9, 4]] : [[3, 4], [6, 6], [9, 5]]; fl.forEach(([x, h]) => { p.rect(x - 1, 8 - h, 2, h, '#ff8c2a'); p.rect(x - 1, 9 - h, 1, h - 2, '#ffd23f'); }); return p.outline(); }
  };
  const OB_KINDS = ['rock', 'bush', 'crate', 'rock', 'tires', 'bush'];

  function shadowCanvas() { const [c, x] = cv(16, 8); x.fillStyle = 'rgba(20,16,30,0.32)'; x.beginPath(); x.ellipse(8, 4, 7.5, 3.5, 0, 0, 7); x.fill(); return c; }
  function selectCanvas() { const [c, x] = cv(16, 16); x.fillStyle = 'rgba(255,248,214,0.28)'; x.fillRect(1, 1, 14, 14); x.fillStyle = '#fff6c8'; [[0, 0], [12, 0], [0, 12], [12, 12]].forEach(([a, b]) => { x.fillRect(a, b, 4, 1); x.fillRect(a, b + 3, 4, 1); x.fillRect(a, b, 1, 4); x.fillRect(a + 3, b, 1, 4); }); x.clearRect(1, 1, 2, 2); x.clearRect(13, 1, 2, 2); x.clearRect(1, 13, 2, 2); x.clearRect(13, 13, 2, 2); return c; }

  // ---------- Chão: campo de grama seca (mapa + margem) ----------
  function ground(cols, rows, m, spawns, core) {
    const S = 16, W = (cols + 2 * m) * S, H = (rows + 2 * m) * S, R = rng(4242);
    const [c, x] = cv(W, H); const id = x.createImageData(W, H);
    const put = (px, py, col, al) => { px |= 0; py |= 0; if (px < 0 || py < 0 || px >= W || py >= H) return; const [r, g, b] = hx(col); const i = (py * W + px) * 4; al = al === undefined ? 1 : al; id.data[i] = id.data[i] * (1 - al) + r * al; id.data[i + 1] = id.data[i + 1] * (1 - al) + g * al; id.data[i + 2] = id.data[i + 2] * (1 - al) + b * al; id.data[i + 3] = 255; };
    const X0 = m * S, Y0 = m * S, X1 = (m + cols) * S, Y1 = (m + rows) * S;
    const inside = (px, py) => px >= X0 && py >= Y0 && px < X1 && py < Y1;
    for (let py = 0; py < H; py++) for (let px = 0; px < W; px++) { const v = R(); if (inside(px, py)) put(px, py, v < 0.12 ? '#979c5d' : v < 0.24 ? '#b6bb77' : '#a7ac69'); else put(px, py, v < 0.3 ? '#5f6a37' : '#7a8448'); }
    // árvores na margem
    for (let i = 0; i < 40; i++) { const side = i % 4; let cx, cy; if (side === 0) { cx = R() * X0; cy = R() * H; } else if (side === 1) { cx = X1 + R() * (W - X1); cy = R() * H; } else if (side === 2) { cx = R() * W; cy = R() * Y0; } else { cx = R() * W; cy = Y1 + R() * (H - Y1); } const rr = 5 + R() * 6;
      if (spawns.some(s => Math.abs(cx - (m + s.c + 0.5) * S) < 14 && (s.r === 0 ? cy < Y0 : Math.abs(cy - (m + s.r + 0.5) * S) < 14))) continue;
      for (let py = cy - rr; py < cy + rr; py++) for (let px = cx - rr; px < cx + rr; px++) { const d = Math.hypot(px - cx, py - cy); if (d < rr && !inside(px, py)) put(px, py, d < rr * 0.5 && py < cy ? '#5f9142' : '#4a6b33'); } }
    for (let i = 0; i < 170; i++) { const px = X0 + R() * cols * S, py = Y0 + R() * rows * S; ['#7d8547'].forEach(col => { put(px, py, col); put(px + 1, py - 1, col); put(px + 2, py, col); put(px + 1, py, col); }); }
    const flowers = ['#f4eec8', '#f2b84b', '#e88aa6'];
    for (let i = 0; i < 46; i++) put(X0 + R() * cols * S, Y0 + R() * rows * S, flowers[i % 3]);
    for (let i = 0; i < 6; i++) { const cx = X0 + R() * cols * S, cy = Y0 + R() * rows * S, rr = 3 + R() * 4; for (let py = cy - rr; py < cy + rr; py++) for (let px = cx - rr; px < cx + rr; px++) if (Math.hypot(px - cx, py - cy) < rr && R() < 0.75) put(px, py, '#b99e6c', 0.8); }
    for (let py = Y0; py < Y1; py++) { put(X0 - 1, py, '#5f6a37'); put(X1, py, '#5f6a37'); }
    for (let px = X0; px < X1; px++) { put(px, Y0 - 1, '#5f6a37'); put(px, Y1, '#5f6a37'); }
    for (let r = 1; r < rows; r++) for (let px = X0; px < X1; px += 2) put(px, Y0 + r * S, '#000000', 0.07);
    for (let k = 1; k < cols; k++) for (let py = Y0; py < Y1; py += 2) put(X0 + k * S, py, '#000000', 0.07);
    // estradinhas de terra nas entradas
    spawns.forEach(s => { const cx = (m + s.c + 0.5) * S, cy = (m + s.r + 0.5) * S; if (s.r === 0) { for (let py = 0; py < Y0; py++) for (let px = cx - 6; px < cx + 6; px++) put(px, py, Math.abs(px - cx) > 4 ? '#b39563' : '#c4a676'); } else { const a = s.c === 0 ? 0 : X1, b = s.c === 0 ? X0 : W; for (let px = a; px < b; px++) for (let py = cy - 6; py < cy + 6; py++) put(px, py, Math.abs(py - cy) > 4 ? '#b39563' : '#c4a676'); } });
    x.putImageData(id, 0, 0);
    return c;
  }
  // Trilha pisoteada: desenha o caminho atual dos zumbis num canvas transparente do tamanho do mapa
  function trail(canvas, cols, rows, paths) {
    const S = 16, x = canvas.getContext('2d'); x.clearRect(0, 0, canvas.width, canvas.height);
    const R = rng(77);
    paths.forEach(path => {
      for (let i = 0; i < path.length - 1; i++) {
        const [ax, ay] = path[i], [bx, by] = path[i + 1], L = Math.max(1, Math.hypot(bx - ax, by - ay) * S);
        for (let k = 0; k <= L; k += 1) {
          const cx = (ax + (bx - ax) * k / L) * S, cy = (ay + (by - ay) * k / L) * S;
          for (let j = -5; j <= 5; j++) for (let mm = -5; mm <= 5; mm++) { const d = Math.hypot(j, mm); if (d < 4.2 || (d < 5.6 && R() < 0.3)) { x.fillStyle = d < 3 ? '#c4a676' : '#b39563'; x.fillRect(Math.round(cx + j), Math.round(cy + mm), 1, 1); } }
        }
      }
      x.fillStyle = '#a3865a';
      for (let i = 0; i < path.length * 3; i++) { const p = path[(R() * path.length) | 0]; x.fillRect(Math.round(p[0] * S + (R() - 0.5) * 7), Math.round(p[1] * S + (R() - 0.5) * 7), 1, 1); }
    });
  }

  // ---------- Cache de texturas ----------
  const cache = {}, texCache = {};
  const MAKERS = {
    walker: a => walker(a >> 1, a & 1).canvas(), runner: a => runner(a).canvas(), boss: a => boss(a).canvas(),
    tower: t => tower(t).canvas(), bunker: () => bunker().canvas(), barrel: f => OB.barrel(f).canvas(),
    obstacle: i => OB[OB_KINDS[i % OB_KINDS.length]](i).canvas(), shadow: () => shadowCanvas(), select: () => selectCanvas()
  };
  function canvas(name, arg) { const k = name + ':' + arg; if (!cache[k]) cache[k] = MAKERS[name](arg); return cache[k]; }
  function tex(name, arg) { const k = name + ':' + arg; if (!texCache[k]) { const t = new THREE.CanvasTexture(canvas(name, arg)); t.magFilter = t.minFilter = THREE.NearestFilter; t.generateMipmaps = false; texCache[k] = t; } return texCache[k]; }
  function icon(name, arg, scale) { const s = canvas(name, arg); const [c, x] = cv(s.width * scale, s.height * scale); x.drawImage(s, 0, 0, c.width, c.height); return c.toDataURL(); }
  function groundTex(cols, rows, m, spawns, core) { const t = new THREE.CanvasTexture(ground(cols, rows, m, spawns, core)); t.magFilter = t.minFilter = THREE.NearestFilter; t.generateMipmaps = false; return t; }
  return { canvas, tex, icon, groundTex, trail, ZV_COUNT: ZV.length, OB_COUNT: OB_KINDS.length };
})();
