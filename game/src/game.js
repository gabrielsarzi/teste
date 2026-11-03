// Último Bunker: simulação, render (three.js) e interface.
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
  const COLS = 9, ROWS = 16, MARGIN = 2, CORE = { c: 4, r: 15 };
  const SPAWNS = [
    { c: 4, r: 0, ex: 4.5, ey: 0.9, from: 1 },
    { c: 0, r: 5, ex: -0.9, ey: -5.5, from: 6 },
    { c: 8, r: 5, ex: COLS + 0.9, ey: -5.5, from: 6 }
  ];
  const DIRS = [[0, 1], [-1, 0], [1, 0], [0, -1]];
  const idx = (c, r) => r * COLS + c;
  const wx = c => c + 0.5, wy = r => -(r + 0.5);
  const EMPTY = 0, RUBBLE = 1, TOWER = 2, COREC = 3;

  // ---------- Save / meta ----------
  const SAVE_KEY = 'ultimo-bunker-v1';
  const meta = { essence: 0, talents: {}, best: 0, lang: null, sfx: true, music: true, last: Date.now(), runs: 0 };
  try { const o = JSON.parse(localStorage.getItem(SAVE_KEY)); if (o) Object.assign(meta, o); } catch (e) { }
  function saveMeta() { meta.last = Date.now(); try { localStorage.setItem(SAVE_KEY, JSON.stringify(meta)); } catch (e) { } }
  const tl = id => meta.talents[id] || 0;
  if (!meta.lang) meta.lang = (navigator.language || 'pt').toLowerCase().startsWith('pt') ? 'pt' : 'en';
  window.LANG = meta.lang;
  SFX.set('sfx', meta.sfx); SFX.set('music', meta.music);

  // ---------- Three.js ----------
  const stage = $('stage'), glc = $('gl'), fx = $('fx'), fxc = fx.getContext('2d');
  const renderer = new THREE.WebGLRenderer({ canvas: glc, antialias: false });
  renderer.setClearColor(0x0d0b0a);
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -10, 10);
  const cam = { x: COLS / 2, y: -ROWS / 2, zoom: 1, scale: 40, w: 1, h: 1, shake: 0 };
  const geo = new THREE.PlaneGeometry(1, 1);
  const matOf = (map, o) => new THREE.MeshBasicMaterial(Object.assign({ map: map || null, transparent: true, depthTest: false, depthWrite: false, side: THREE.DoubleSide }, o || {}));
  function mesh(map, w, h, order, o) { const m = new THREE.Mesh(geo, matOf(map, o)); m.scale.set(w, h, 1); m.renderOrder = order; scene.add(m); return m; }
  const L = { ground: 0, trail: 1, shadow: 2, sel: 3, rubble: 100, base: 100, enemy: 100, head: 100, proj: 900, dark: 1000, glow: 1001, part: 1002, bar: 1003, ui: 1004 };
  // Profundidade 3/4: quem está mais embaixo na tela é desenhado por cima
  const depth = (m, feetY) => { m.renderOrder = 100 + Math.round(-feetY * 24); };
  const PX = 1 / 16; // um pixel da arte em unidades do mundo
  function sprite(tex, wpx, hpx, x, feetY) { const m = mesh(tex, wpx * PX, hpx * PX, 100); m.position.set(x, feetY + hpx * PX / 2, 0); depth(m, feetY); return m; }
  function shadowAt(x, y, w) { const m = mesh(ART3.tex('shadow', 0), w, w * 0.5, L.shadow); m.position.set(x, y, 0); return m; }

  const groundM = mesh(ART3.groundTex(COLS, ROWS, MARGIN, SPAWNS, CORE), COLS + 2 * MARGIN, ROWS + 2 * MARGIN, L.ground, { transparent: false });
  groundM.position.set(COLS / 2, -ROWS / 2, 0);
  shadowAt(wx(CORE.c), wy(CORE.r) - 0.4, 2.1);
  const coreM = sprite(ART3.tex('bunker', 0), 32, 28, wx(CORE.c), wy(CORE.r) - 0.45);
  // Trilha pisoteada: canvas do tamanho do mapa, redesenhado quando o caminho muda
  const trailCv = document.createElement('canvas'); trailCv.width = COLS * 16; trailCv.height = ROWS * 16;
  const trailTex = new THREE.CanvasTexture(trailCv); trailTex.magFilter = trailTex.minFilter = THREE.NearestFilter; trailTex.generateMipmaps = false;
  const trailM = mesh(trailTex, COLS, ROWS, L.trail); trailM.position.set(COLS / 2, -ROWS / 2, 0);
  const darkM = mesh(null, 60, 60, L.dark, { color: 0x0e102e, opacity: 0 }); darkM.position.set(COLS / 2, -ROWS / 2, 0);
  const selM = mesh(ART3.tex('select', 0), 1, 1, L.sel); selM.visible = false;
  const rangeM = new THREE.Mesh(new THREE.CircleGeometry(1, 48), matOf(null, { color: 0xfff0b4, opacity: 0.16 })); rangeM.renderOrder = L.ui; scene.add(rangeM); rangeM.visible = false;
  const rangeRing = new THREE.Mesh(new THREE.RingGeometry(0.97, 1, 48), matOf(null, { color: 0xfff0b4, opacity: 0.85 })); rangeRing.renderOrder = L.ui; scene.add(rangeRing); rangeRing.visible = false;

  // Luzes (glow aditivo em cima da camada de escuridão)
  const GLOW = ART.glowTex();
  const glowPool = [];
  function glow(x, y, size, color, life, intensity) {
    let g = glowPool.find(o => !o.on);
    if (!g) { g = { m: mesh(GLOW, 1, 1, L.glow, { blending: THREE.AdditiveBlending }), on: false }; glowPool.push(g); }
    g.on = true; g.m.visible = true; g.m.position.set(x, y, 0); g.m.scale.set(size, size, 1); g.m.material.color.setHex(color);
    g.life = life; g.max = life; g.i = intensity || 1; g.follow = null; g.flicker = 0; return g;
  }
  const coreGlow = glow(wx(CORE.c), wy(CORE.r), 3, 0x9be04a, Infinity, 0.6);

  // Partículas
  const partPool = [];
  function particle(x, y, color, n, spd, life, size) {
    for (let i = 0; i < n; i++) {
      let p = partPool.find(o => !o.on);
      if (!p) { if (partPool.length > 400) return; p = { m: mesh(null, 1, 1, L.part), on: false }; partPool.push(p); }
      const a = Math.random() * Math.PI * 2, v = spd * (0.3 + Math.random() * 0.7);
      p.on = true; p.m.visible = true; p.x = x; p.y = y; p.vx = Math.cos(a) * v; p.vy = Math.sin(a) * v;
      p.life = p.max = life * (0.6 + Math.random() * 0.6); p.s = size || 0.1; p.m.material.color.setHex(color); p.m.material.opacity = 1;
    }
  }

  // Raios da tesla
  const boltPool = [];
  function bolt(x0, y0, x1, y1, color) {
    const pts = [[x0, y0]]; const n = 4;
    for (let i = 1; i < n; i++) { const t = i / n; pts.push([x0 + (x1 - x0) * t + (Math.random() - 0.5) * 0.35, y0 + (y1 - y0) * t + (Math.random() - 0.5) * 0.35]); }
    pts.push([x1, y1]);
    for (let i = 0; i < pts.length - 1; i++) {
      let b = boltPool.find(o => !o.on);
      if (!b) { b = { m: mesh(null, 1, 1, L.part, { blending: THREE.AdditiveBlending }), on: false }; boltPool.push(b); }
      const [ax, ay] = pts[i], [bx, by] = pts[i + 1];
      b.on = true; b.m.visible = true; b.life = 0.12; b.m.material.color.setHex(color); b.m.material.opacity = 1;
      b.m.position.set((ax + bx) / 2, (ay + by) / 2, 0); b.m.scale.set(Math.hypot(bx - ax, by - ay) + 0.04, 0.07, 1); b.m.rotation.z = Math.atan2(by - ay, bx - ax);
    }
  }

  // Anéis (nevasca, explosões)
  const ringPool = [];
  const ringGeo = new THREE.RingGeometry(0.85, 1, 32);
  function ring(x, y, r, color, life) {
    let o = ringPool.find(q => !q.on);
    if (!o) { o = { m: new THREE.Mesh(ringGeo, matOf(null, { blending: THREE.AdditiveBlending })), on: false }; o.m.renderOrder = L.part; scene.add(o.m); ringPool.push(o); }
    o.on = true; o.m.visible = true; o.m.position.set(x, y, 0); o.r = r; o.life = o.max = life; o.m.material.color.setHex(color); return o;
  }

  // Textos flutuantes (desenhados num canvas 2D por cima)
  const texts = [];
  function floatText(x, y, s, color, big) { if (texts.length > 80) texts.shift(); texts.push({ x, y, s, color, t: 0, big: !!big, dx: (Math.random() - 0.5) * 0.3 }); }

  // ---------- Câmera ----------
  const BOT = 64; // faixa embaixo para os botões de onda/velocidade
  function resize() {
    const r = stage.getBoundingClientRect(); cam.w = Math.max(1, r.width); cam.h = Math.max(1, r.height);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(dpr); renderer.setSize(cam.w, cam.h, false);
    fx.width = Math.round(cam.w * dpr); fx.height = Math.round(cam.h * dpr); fxc.setTransform(dpr, 0, 0, dpr, 0, 0);
    // Escala inteira por pixel da arte (16 px por tile) para manter os pixels nítidos
    let s = Math.min(cam.w / (COLS + 0.3), (cam.h - BOT) / (ROWS + 0.3));
    const snapped = Math.floor(s * dpr / 16) * 16 / dpr;
    cam.scale = snapped >= s * 0.8 ? snapped : s;
    clampCam();
  }
  function clampCam() {
    cam.zoom = clamp(cam.zoom, 1, 3);
    const s = cam.scale * cam.zoom, hw = cam.w / 2 / s, hh = cam.h / 2 / s;
    cam.x = hw * 2 >= COLS + 1 ? COLS / 2 : clamp(cam.x, hw - 0.5, COLS + 0.5 - hw);
    const bot = BOT / s;
    cam.y = (hh * 2 - bot) >= ROWS + 1 ? -ROWS / 2 - bot / 2 : clamp(cam.y, -ROWS - 0.5 + hh - bot, 0.5 - hh);
  }
  function updateCamera() {
    const s = cam.scale * cam.zoom, hw = cam.w / 2 / s, hh = cam.h / 2 / s;
    const sx = cam.shake > 0 ? (Math.random() - 0.5) * cam.shake : 0, sy = cam.shake > 0 ? (Math.random() - 0.5) * cam.shake : 0;
    camera.left = -hw; camera.right = hw; camera.top = hh; camera.bottom = -hh;
    camera.position.set(cam.x + sx, cam.y + sy, 5); camera.updateProjectionMatrix();
  }
  const toWorld = (sx, sy) => { const s = cam.scale * cam.zoom; return { x: cam.x + (sx - cam.w / 2) / s, y: cam.y - (sy - cam.h / 2) / s }; };
  const toScreen = (x, y) => { const s = cam.scale * cam.zoom; return { x: (x - cam.x) * s + cam.w / 2, y: -(y - cam.y) * s + cam.h / 2 }; };
  function shake(m) { cam.shake = Math.max(cam.shake, m); }

  // ---------- Estado da run ----------
  let G = null, state = 'menu', speed = 1, paused = false, sel = null;

  function bfs(grid) {
    const d = new Int16Array(COLS * ROWS).fill(-1); const q = [idx(CORE.c, CORE.r)]; d[q[0]] = 0; let h = 0;
    while (h < q.length) {
      const i = q[h++], c = i % COLS, r = (i / COLS) | 0;
      for (const [dc, dr] of DIRS) {
        const nc = c + dc, nr = r + dr; if (nc < 0 || nr < 0 || nc >= COLS || nr >= ROWS) continue;
        const j = idx(nc, nr); if (d[j] >= 0) continue; const g = grid[j]; if (g === RUBBLE || g === TOWER) continue;
        d[j] = d[i] + 1; q.push(j);
      }
    }
    return d;
  }
  const spawnsOk = d => SPAWNS.every(s => d[idx(s.c, s.r)] >= 0);
  // Desenha a trilha pisoteada seguindo o caminho atual de cada entrada ativa
  function updateTrail() {
    if (!G) { ART3.trail(trailCv, COLS, ROWS, []); trailTex.needsUpdate = true; return; }
    const paths = [];
    SPAWNS.forEach(sp => {
      if (G.wave + 1 < sp.from) return;
      const path = [[sp.ex, -sp.ey]]; let c = sp.c, r = sp.r, guard = 0;
      path.push([c + 0.5, r + 0.5]);
      while (G.dist[idx(c, r)] > 0 && guard++ < 200) { const n = nextCell(c, r); if (!n) break; c = n.c; r = n.r; path.push([c + 0.5, r + 0.5]); }
      paths.push(path);
    });
    ART3.trail(trailCv, COLS, ROWS, paths); trailTex.needsUpdate = true;
  }
  const isReserved = (c, r) => (r === CORE.r && Math.abs(c - CORE.c) <= 1) || SPAWNS.some(s => s.c === c && s.r === r);
  const nearReserved = (c, r) => [CORE, ...SPAWNS].some(s => Math.abs(s.c - c) + Math.abs(s.r - r) <= 1);

  function clearRun() {
    if (!G) return;
    G.towers.forEach(removeTowerMeshes); G.enemies.filter(e => e.alive).forEach(releaseEnemy); G.projs.forEach(releaseProj);
    Object.values(G.rubM).forEach(o => { scene.remove(o.m); scene.remove(o.s); if (o.g) { o.g.on = false; o.g.m.visible = false; } });
    glowPool.forEach(g => { if (g !== coreGlow) { g.on = false; g.m.visible = false; } });
    partPool.forEach(p => { p.on = false; p.m.visible = false; });
    texts.length = 0;
  }

  function newRun() {
    clearRun();
    const maxHp = 20 + 3 * tl('hp');
    G = { gold: 150 + 30 * tl('gold0'), wave: 0, hp: maxHp, maxHp, kills: 0, grid: new Uint8Array(COLS * ROWS), dist: null,
      towers: [], enemies: [], projs: [], queue: [], spawnT: 0, nextT: 25, cleared: 0, time: 0, rubM: {}, dayT: 0 };
    G.grid[idx(CORE.c, CORE.r)] = COREC;
    // Destroços aleatórios (o mapa "cresce" conforme você limpa)
    const cand = [];
    for (let r = 1; r < ROWS - 1; r++) for (let c = 0; c < COLS; c++) if (!nearReserved(c, r) && Math.random() < 0.16) { G.grid[idx(c, r)] = RUBBLE; cand.push(idx(c, r)); }
    let d = bfs(G.grid);
    while (!spawnsOk(d) && cand.length) { const k = cand.splice((Math.random() * cand.length) | 0, 1)[0]; G.grid[k] = EMPTY; d = bfs(G.grid); }
    G.dist = d; updateTrail();
    const rub = []; for (let i = 0; i < G.grid.length; i++) if (G.grid[i] === RUBBLE) rub.push(i);
    const barrels = new Set(); for (let n = 0; n < 4 && rub.length; n++) barrels.add(rub.splice((Math.random() * rub.length) | 0, 1)[0]);
    for (let i = 0; i < G.grid.length; i++) if (G.grid[i] === RUBBLE) addRubbleMesh(i, barrels.has(i));
    state = 'play'; paused = false; speed = 1; sel = null; closeRadial();
    cam.zoom = 1; clampCam();
    showScreen(null); updateHud(true);
    toast(T('hint'), 5);
  }

  function addRubbleMesh(i, barrel) {
    const c = i % COLS, r = (i / COLS) | 0;
    const feet = wy(r) - 0.4, kind = (i * 7 + r) % ART3.OB_COUNT;
    const cvs = barrel ? ART3.canvas('barrel', 0) : ART3.canvas('obstacle', kind);
    const s = shadowAt(wx(c), feet + 0.05, barrel ? 0.8 : 0.95);
    const m = sprite(barrel ? ART3.tex('barrel', 0) : ART3.tex('obstacle', kind), cvs.width, cvs.height, wx(c), feet);
    const o = { m, s, barrel };
    if (barrel) { o.g = glow(wx(c), wy(r) + 0.3, 3.2, 0xff8a30, Infinity, 0.8); o.g.flicker = 1; }
    G.rubM[i] = o;
  }

  // ---------- Torres ----------
  function towerStats(t) {
    const d = TOWERS[t.type], Lv = t.lvl;
    const s = { dmg: d.dmg * (1 + 0.6 * (Lv - 1)), rate: d.rate * (1 + 0.08 * (Lv - 1)), range: d.range + 0.15 * (Lv - 1),
      splash: d.splash || 0, slow: d.slow || 0, slowT: d.slowT || 0, chain: d.chain || 0, burn: 0, freeze: 0, pulse: false };
    if (t.branch) d[t.branch](s);
    s.dmg *= 1 + 0.1 * tl('dmg'); s.rate *= 1 + 0.06 * tl('rate'); s.range *= 1 + 0.05 * tl('range');
    return s;
  }
  const upCost = t => Math.round(TOWERS[t.type].cost * 0.9 * Math.pow(1.7, t.lvl - 1));
  const sellValue = t => Math.floor(t.spent * 0.7);

  function canPlace(c, r) {
    if (G.grid[idx(c, r)] !== EMPTY || isReserved(c, r)) return 'no';
    if (G.enemies.some(e => e.alive && ((e.tc === c && e.tr === r) || (Math.floor(e.x) === c && Math.floor(-e.y) === r)))) return 'occupied';
    G.grid[idx(c, r)] = TOWER; const d = bfs(G.grid); G.grid[idx(c, r)] = EMPTY;
    if (!spawnsOk(d)) return 'blocked';
    if (G.enemies.some(e => e.alive && e.tr >= 0 && d[idx(e.tc, e.tr)] < 0)) return 'blocked';
    return d;
  }

  function build(type, c, r) {
    const cost = TOWERS[type].cost;
    if (G.gold < cost) { toast(T('noGold')); SFX.play('error'); return false; }
    const d = canPlace(c, r);
    if (d === 'blocked' || d === 'occupied') { toast(T(d)); SFX.play('error'); return false; }
    if (d === 'no') return false;
    G.gold -= cost; G.grid[idx(c, r)] = TOWER; G.dist = d; updateTrail();
    const t = { type, c, r, lvl: 1, branch: null, cd: 0.3, ang: Math.PI / 2, prio: 0, spent: cost, recoil: 0 };
    t.base = shadowAt(wx(c), wy(r) - 0.38, 1);
    t.head = sprite(ART3.tex('tower', type), 16, 22, wx(c), wy(r) - 0.42);
    t.pips = []; for (let i = 0; i < MAX_LVL; i++) { const p = mesh(null, 0.1, 0.07, L.bar, { color: 0xffe066 }); p.position.set(wx(c) - 0.24 + i * 0.12, wy(r) - 0.47, 0); t.pips.push(p); }
    t.g = glow(wx(c), wy(r) + 0.3, 1.8, TOWERS[type].light, Infinity, 0.35);
    G.towers.push(t); updatePips(t);
    particle(wx(c), wy(r), 0xc9b48a, 10, 2, 0.4, 0.09);
    SFX.play('build'); updateHud(); return true;
  }
  function updatePips(t) { t.pips.forEach((p, i) => { p.visible = i < t.lvl; p.material.color.setHex(t.branch === 'a' ? 0xf2b84b : t.branch === 'b' ? 0x6fe3d0 : 0xfff6c8); }); }
  function removeTowerMeshes(t) { scene.remove(t.base); scene.remove(t.head); t.pips.forEach(p => scene.remove(p)); if (t.g) { t.g.on = false; t.g.m.visible = false; } }
  function upgrade(t, branch) {
    if (t.lvl >= MAX_LVL) return;
    const cost = upCost(t);
    if (G.gold < cost) { toast(T('noGold')); SFX.play('error'); return; }
    G.gold -= cost; t.spent += cost; t.lvl++;
    if (branch) t.branch = branch;
    updatePips(t); particle(wx(t.c), wy(t.r), 0xf5d27a, 14, 2.5, 0.5, 0.08); glow(wx(t.c), wy(t.r), 2.4, 0xf5d27a, 0.4, 1);
    SFX.play('up'); updateHud();
  }
  function sell(t) {
    G.gold += sellValue(t); G.grid[idx(t.c, t.r)] = EMPTY; G.dist = bfs(G.grid); updateTrail();
    removeTowerMeshes(t); G.towers.splice(G.towers.indexOf(t), 1);
    particle(wx(t.c), wy(t.r), 0x8f7e5c, 12, 2, 0.4, 0.1); SFX.play('coin'); updateHud();
  }
  const rubbleCost = () => Math.round((30 + 12 * G.cleared) * (1 - 0.15 * tl('rubble')));
  function clearRubble(c, r) {
    const cost = rubbleCost();
    if (G.gold < cost) { toast(T('noGold')); SFX.play('error'); return; }
    const i = idx(c, r); G.gold -= cost; G.cleared++; G.grid[i] = EMPTY; G.dist = bfs(G.grid); updateTrail();
    const o = G.rubM[i]; scene.remove(o.m); scene.remove(o.s); if (o.g) { o.g.on = false; o.g.m.visible = false; } delete G.rubM[i];
    particle(wx(c), wy(r), 0x9da3a6, 16, 2.5, 0.5, 0.1); SFX.play('boom'); shake(0.08); updateHud();
  }

  // ---------- Inimigos ----------
  const enemyPool = [];
  function spawnEnemy(kind, si) {
    const s = SPAWNS[si], d = ENEMIES[kind], w = G.wave;
    const hp = Math.round(d.hp * Math.pow(1.13, w - 1) * (1 + w * 0.015));
    let e = enemyPool.pop();
    if (!e) {
      e = {};
      e.m = mesh(null, 1, 1, L.enemy); e.sh = shadowAt(0, 0, 0.7);
      e.bg = mesh(null, 0.7, 0.08, L.bar, { color: 0x16120f }); e.fill = mesh(null, 0.66, 0.05, L.bar, { color: 0x9be04a });
    }
    Object.assign(e, { kind, x: s.ex, y: s.ey, tc: s.c, tr: s.r, hp, maxHp: hp, spd: d.spd * (1 + Math.min(w, 60) * 0.004),
      slow: 0, slowT: 0, frz: 0, burn: 0, burnT: 0, burnAcc: 0, anim: Math.random(), rot: -Math.PI / 2, dir: -Math.PI / 2, hitT: 0,
      vx: 0, vy: 0, prog: 999, alive: true, size: d.size, core: d.core,
      gold: Math.max(1, Math.floor((3 + w * 0.45) * d.gold * (1 + 0.08 * tl('bounty')))) });
    if (si === 1) e.dir = e.rot = 0; else if (si === 2) e.dir = e.rot = Math.PI;
    e.v = (Math.random() * ART3.ZV_COUNT) | 0; e.face = si === 2 ? -1 : 1;
    const dims = kind === 'boss' ? [28, 28] : kind === 'runner' ? [16, 18] : [16, 20];
    e.pw = dims[0] * PX; e.ph = dims[1] * PX; e.by = e.ph * 0.45;
    e.m.visible = e.bg.visible = e.fill.visible = e.sh.visible = true;
    e.sh.scale.set(kind === 'boss' ? 1.5 : 0.7, kind === 'boss' ? 0.75 : 0.35, 1);
    e.m.scale.set(e.pw, e.ph, 1); e.m.material.map = enemyTex(e, 0); e.m.material.needsUpdate = true;
    G.enemies.push(e);
    if (kind === 'boss') { e.g = glow(e.x, e.y, 2.6, 0x9be04a, Infinity, 0.5); }
  }
  const enemyTex = (e, f) => e.kind === 'walker' ? ART3.tex('walker', e.v * 2 + f) : ART3.tex(e.kind, f);
  function releaseEnemy(e) { e.alive = false; e.m.visible = e.bg.visible = e.fill.visible = e.sh.visible = false; if (e.g) { e.g.on = false; e.g.m.visible = false; e.g = null; } enemyPool.push(e); }

  function nextCell(c, r) {
    let best = null, bd = 1e9;
    for (const [dc, dr] of DIRS) {
      const nc = c + dc, nr = r + dr; if (nc < 0 || nr < 0 || nc >= COLS || nr >= ROWS) continue;
      const dd = G.dist[idx(nc, nr)]; if (dd >= 0 && dd < bd) { bd = dd; best = { c: nc, r: nr }; }
    }
    return best;
  }
  function stepEnemy(e, dt) {
    if (e.burnT > 0) { e.burnT -= dt; const b = e.burn * dt; e.burnAcc += b; damage(e, b, true); if (e.burnAcc > e.maxHp * 0.04 || e.burnT <= 0) { if (e.burnAcc >= 1) floatText(e.x, e.y + 0.3, Math.round(e.burnAcc), '#f5a541'); e.burnAcc = 0; } if (!e.alive) return; }
    if (e.hitT > 0) e.hitT -= dt;
    if (e.slowT > 0) e.slowT -= dt;
    if (e.frz > 0) { e.frz -= dt; e.vx = e.vy = 0; return; }
    const sp = e.spd * (e.slowT > 0 ? 1 - e.slow : 1);
    let move = sp * dt; const ox = e.x, oy = e.y;
    while (move > 0) {
      const tx = wx(e.tc), ty = wy(e.tr), dx = tx - e.x, dy = ty - e.y, Ld = Math.hypot(dx, dy);
      if (Ld <= move) {
        e.x = tx; e.y = ty; move -= Ld;
        if (G.dist[idx(e.tc, e.tr)] === 0) { reachCore(e); return; }
        const n = nextCell(e.tc, e.tr); if (!n) break;
        e.tc = n.c; e.tr = n.r;
      } else { e.x += dx / Ld * move; e.y += dy / Ld * move; e.dir = Math.atan2(dy, dx); move = 0; }
    }
    e.vx = (e.x - ox) / dt; e.vy = (e.y - oy) / dt;
    e.prog = G.dist[idx(e.tc, e.tr)] + Math.hypot(wx(e.tc) - e.x, wy(e.tr) - e.y);
    e.anim += dt * sp * 2.2;
  }
  function damage(e, amt, quiet, crit) {
    if (!e.alive) return;
    e.hp -= amt; if (!quiet) { e.hitT = 0.08; floatText(e.x, e.y + e.ph + 0.1, Math.max(1, Math.round(amt)), crit ? '#f5d27a' : '#ece6d3', crit); }
    if (e.hp <= 0) kill(e);
  }
  function kill(e) {
    G.gold += e.gold; G.kills++;
    particle(e.x, e.y + e.by, 0x8fbf6a, e.kind === 'boss' ? 30 : 8, 2.2, 0.45, 0.1);
    particle(e.x, e.y + e.by, 0x8f2f3c, e.kind === 'boss' ? 20 : 4, 1.6, 0.5, 0.12);
    floatText(e.x + 0.2, e.y + e.by, '+' + e.gold, '#f2b84b');
    if (e.kind === 'boss') { shake(0.35); SFX.play('boom'); glow(e.x, e.y, 4, 0x9be04a, 0.6, 1.2); }
    SFX.play(e.kind === 'boss' ? 'coin' : 'die');
    releaseEnemy(e);
  }
  function reachCore(e) {
    G.hp -= e.core; shake(e.core > 1 ? 0.45 : 0.2); SFX.play('hurt');
    particle(wx(CORE.c), wy(CORE.r), 0xb04a5a, 14, 2.5, 0.5, 0.1); glow(wx(CORE.c), wy(CORE.r), 3, 0xb04a5a, 0.4, 1.2);
    releaseEnemy(e);
    if (G.hp <= 0) { G.hp = 0; endRun(false); }
  }

  // ---------- Projéteis ----------
  const projPool = [];
  function addProj(o) {
    let p = projPool.pop();
    if (!p) { p = { m: mesh(null, 1, 1, L.proj) }; }
    Object.assign(p, o, { alive: true, g: null });
    const size = o.kind === 'bullet' ? 0.16 : o.kind === 'shell' ? 0.3 : 0.22;
    p.m.material.map = ART.tex(o.kind); p.m.material.needsUpdate = true; p.m.scale.set(size, size, 1); p.m.visible = true; p.m.position.set(p.x, p.y, 0);
    if (o.kind !== 'bullet') p.g = glow(p.x, p.y, 0.9, o.kind === 'shell' ? 0xff9040 : 0x70c8ff, Infinity, 0.6);
    G.projs.push(p);
  }
  function stepProj(p, dt) {
    if (p.kind === 'shell') {
      p.t += dt; const k = Math.min(1, p.t / p.T);
      p.x = p.sx + (p.tx - p.sx) * k; p.y = p.sy + (p.ty - p.sy) * k;
      const h = Math.sin(k * Math.PI); p.m.scale.set(0.3 + h * 0.25, 0.3 + h * 0.25, 1);
      if (k >= 1) { explode(p); p.alive = false; }
      return;
    }
    const e = p.tgt;
    if (!e || !e.alive) { if (p.lx === undefined) { p.alive = false; return; } }
    const tx = e && e.alive ? e.x : p.lx, ty = e && e.alive ? e.y + e.by : p.ly;
    p.lx = tx; p.ly = ty;
    const dx = tx - p.x, dy = ty - p.y, d = Math.hypot(dx, dy), mv = p.spd * dt;
    p.m.rotation.z = Math.atan2(dy, dx) - Math.PI / 2;
    if (d <= mv + 0.05) {
      p.alive = false;
      if (e && e.alive) {
        damage(e, p.dmg, false, p.crit);
        if (p.kind === 'shard' && e.alive) { e.slow = Math.max(e.slow, p.slow); e.slowT = Math.max(e.slowT, p.slowT); if (p.freeze && Math.random() < p.freeze) { e.frz = 1; particle(e.x, e.y, 0xe8f6ff, 6, 1.2, 0.3, 0.08); } }
        particle(tx, ty, p.kind === 'shard' ? 0x5ab0d8 : 0xf5d27a, 3, 1.5, 0.2, 0.07);
      }
    } else { p.x += dx / d * mv; p.y += dy / d * mv; }
  }
  function explode(p) {
    SFX.play('boom'); shake(0.06);
    particle(p.x, p.y, 0xf5a541, 14, 2.6, 0.45, 0.11); particle(p.x, p.y, 0x4a3b30, 8, 1.4, 0.6, 0.14);
    glow(p.x, p.y, p.splash * 3.2, 0xff9040, 0.35, 1.3); ring(p.x, p.y, p.splash, 0xff9040, 0.3);
    G.enemies.forEach(e => {
      if (!e.alive) return; const d = Math.hypot(e.x - p.x, e.y - p.y);
      if (d <= p.splash) { damage(e, p.dmg * (d < p.splash * 0.4 ? 1 : 0.6), false, p.crit); if (p.burn && e.alive) { e.burn = p.dmg * p.burn; e.burnT = 3; } }
    });
  }
  function releaseProj(p) { p.m.visible = false; if (p.g) { p.g.on = false; p.g.m.visible = false; } projPool.push(p); }

  function findTarget(t, s) {
    let best = null, bv = Infinity; const x = wx(t.c), y = wy(t.r), R2 = s.range * s.range;
    for (const e of G.enemies) {
      if (!e.alive) continue; const dx = e.x - x, dy = e.y - y, d2 = dx * dx + dy * dy; if (d2 > R2) continue;
      const v = t.prio === 0 ? e.prog : t.prio === 1 ? -e.hp : d2; if (v < bv) { bv = v; best = e; }
    }
    return best;
  }
  function stepTower(t, dt) {
    t.cd -= dt; t.recoil = Math.max(0, t.recoil - dt * 6);
    if (t.cd > 0) return;
    const s = towerStats(t), e = findTarget(t, s);
    if (!e) { t.cd = 0.1; return; }
    t.cd = 1 / s.rate;
    const x = wx(t.c), y = wy(t.r);
    const crit = Math.random() < 0.03 * tl('crit'); const dmg = s.dmg * (crit ? 2 : 1);
    if (t.type !== 'tesla') t.ang = Math.atan2(e.y - y, e.x - x);
    t.recoil = 1;
    const mx = x + Math.cos(t.ang) * 0.4, my = y + 0.5 + Math.sin(t.ang) * 0.2;
    if (t.type === 'gunner') {
      addProj({ kind: 'bullet', x: mx, y: my, tgt: e, spd: 12, dmg, crit }); glow(mx, my, 0.9, 0xffc060, 0.06, 1); SFX.play('shoot');
    } else if (t.type === 'mortar') {
      const T0 = 0.7; addProj({ kind: 'shell', x, y, sx: x, sy: y, tx: e.x + e.vx * T0, ty: e.y + e.vy * T0, t: 0, T: T0, dmg, crit, splash: s.splash, burn: s.burn });
      particle(mx, my, 0x8f7e5c, 4, 1, 0.3, 0.1); SFX.play('shoot');
    } else if (t.type === 'cryo') {
      if (s.pulse) {
        ring(x, y, s.range, 0x70c8ff, 0.4); SFX.play('ice');
        G.enemies.forEach(en => { if (en.alive && Math.hypot(en.x - x, en.y - y) <= s.range) { damage(en, dmg, false, crit); if (en.alive) { en.slow = Math.max(en.slow, s.slow); en.slowT = Math.max(en.slowT, s.slowT); } } });
      } else { addProj({ kind: 'shard', x: mx, y: my, tgt: e, spd: 8, dmg, crit, slow: s.slow, slowT: s.slowT, freeze: s.freeze }); SFX.play('ice'); }
    } else if (t.type === 'tesla') {
      SFX.play('zap'); const hit = [e]; let cur = e, px = x, py = y + 0.95, d = dmg;
      for (let i = 0; i <= s.chain && cur; i++) {
        bolt(px, py, cur.x, cur.y + cur.by, 0xb890ff); glow(cur.x, cur.y + cur.by, 1.2, 0xb890ff, 0.12, 1);
        const nx = cur.x, ny = cur.y; damage(cur, d, false, crit); d *= 0.85; px = nx; py = ny + cur.by;
        let nb = null, nd = 1.8;
        G.enemies.forEach(en => { if (en.alive && !hit.includes(en)) { const q = Math.hypot(en.x - nx, en.y - ny); if (q < nd) { nd = q; nb = en; } } });
        cur = nb; if (nb) hit.push(nb);
      }
      glow(x, y + 0.95, 1.6, 0xb890ff, 0.1, 1);
    }
  }

  // ---------- Ondas ----------
  function startWave() {
    G.wave++; const w = G.wave;
    if (tl('interest')) { const bonus = Math.min(Math.floor(G.gold * 0.01 * tl('interest')), 40 + w * 12); if (bonus > 0) { G.gold += bonus; floatText(wx(CORE.c), wy(CORE.r) + 0.8, '+' + bonus, '#e0a640'); } }
    const active = SPAWNS.map((s, i) => i).filter(i => w >= SPAWNS[i].from);
    const n = Math.min(6 + Math.floor(w * 1.3), 45), gap = Math.max(0.32, 0.9 - w * 0.012);
    for (let i = 0; i < n; i++) {
      let kind = 'walker';
      if (w >= 3 && i % 3 === 2) kind = 'runner';
      if (w >= 12 && i % 5 === 4) kind = 'runner';
      G.queue.push({ kind, s: active[i % active.length], gap: kind === 'runner' ? gap * 0.6 : gap });
    }
    if (w % 10 === 0) { G.queue.push({ kind: 'boss', s: 0, gap: 1 }); toast(T('boss'), 2.5, true); SFX.play('boss'); shake(0.25); }
    else { toast(T('waveStart', w), 1.6); SFX.play('wave'); }
    if (w === 6) setTimeout(() => toast(T('sides'), 2.5), 1800);
    G.spawnT = 0.2; G.nextT = 0;
    if (w + 1 === 6) updateTrail();
    updateHud(true);
  }
  const earlyBonus = () => Math.ceil(G.nextT * (1 + G.wave * 0.25));
  function callWave() {
    if (!G || G.queue.length || state !== 'play') return;
    const b = earlyBonus(); if (b > 0) { G.gold += b; floatText(wx(SPAWNS[0].c), wy(0) - 0.3, '+' + b, '#e0a640', true); SFX.play('coin'); }
    startWave();
  }
  const essenceFor = () => { const w = Math.max(0, G.wave - 1); return Math.floor((Math.pow(w, 1.5) * 0.6 + G.kills * 0.04) * (1 + 0.1 * tl('essence'))); };

  function update(dt) {
    G.time += dt; G.dayT += dt;
    if (G.queue.length) {
      G.spawnT -= dt;
      if (G.spawnT <= 0) { const q = G.queue.shift(); spawnEnemy(q.kind, q.s); G.spawnT = q.gap; if (!G.queue.length) G.nextT = 14; }
    } else {
      G.nextT -= dt;
      if (tl('autowave') && G.wave > 0 && !G.enemies.some(e => e.alive)) callWave();
      else if (G.nextT <= 0) startWave();
    }
    for (const t of G.towers) stepTower(t, dt);
    for (const p of G.projs) if (p.alive) stepProj(p, dt);
    for (const e of G.enemies) if (e.alive) stepEnemy(e, dt);
    if (state !== 'play') return;
    G.enemies = G.enemies.filter(e => e.alive);
    G.projs = G.projs.filter(p => { if (!p.alive) releaseProj(p); return p.alive; });
  }

  // ---------- Render por quadro ----------
  function render(dt, simDt) {
    if (cam.shake > 0) cam.shake = Math.max(0, cam.shake - dt * 1.2);
    updateCamera();
    // ciclo dia/noite (100 s)
    const ph = G ? G.dayT / 100 : performance.now() / 100000;
    const night = Math.max(0, Math.sin(ph * Math.PI * 2 - 0.6));
    const dark = 0.5 * night * night * (3 - 2 * night);
    darkM.material.opacity = dark;
    const lightK = 0.18 + dark * 1.4;
    for (const g of glowPool) {
      if (!g.on) continue;
      if (g.follow) g.m.position.set(g.follow.x, g.follow.y, 0);
      let a = g.i * (g.life === Infinity ? lightK : (g.life / g.max));
      if (g.flicker) a *= 0.8 + Math.random() * 0.25;
      g.m.material.opacity = Math.min(1, a);
      if (g.life !== Infinity) { g.life -= simDt; if (g.life <= 0) { g.on = false; g.m.visible = false; } }
    }
    for (const p of partPool) {
      if (!p.on) continue; p.life -= simDt; if (p.life <= 0) { p.on = false; p.m.visible = false; continue; }
      p.x += p.vx * simDt; p.y += p.vy * simDt; p.vx *= 0.9; p.vy *= 0.9;
      const k = p.life / p.max; p.m.position.set(p.x, p.y, 0); p.m.scale.set(p.s * (0.5 + k * 0.5), p.s * (0.5 + k * 0.5), 1); p.m.material.opacity = Math.min(1, k * 1.5);
    }
    for (const b of boltPool) { if (!b.on) continue; b.life -= dt; b.m.material.opacity = Math.max(0, b.life / 0.12); if (b.life <= 0) { b.on = false; b.m.visible = false; } }
    for (const o of ringPool) { if (!o.on) continue; o.life -= simDt; const k = 1 - o.life / o.max; const r = o.r * (0.3 + 0.7 * k); o.m.scale.set(r, r, 1); o.m.material.opacity = Math.max(0, 1 - k); if (o.life <= 0) { o.on = false; o.m.visible = false; } }
    if (G) {
      const fr = Math.floor(performance.now() / 160) % 2;
      for (const o of Object.values(G.rubM)) if (o.barrel) o.m.material.map = ART3.tex('barrel', fr);
      for (const e of G.enemies) {
        if (!e.alive) continue;
        if (e.vx > 0.05) e.face = 1; else if (e.vx < -0.05) e.face = -1;
        const feet = e.y - 0.15;
        e.m.position.set(e.x, feet + e.ph / 2, 0); e.m.scale.x = e.pw * e.face; depth(e.m, feet);
        e.sh.position.set(e.x, feet + 0.02, 0);
        const f = Math.floor(e.anim) % 2; e.m.material.map = enemyTex(e, f);
        const col = e.m.material.color;
        if (e.hitT > 0) col.setRGB(1, 0.45, 0.45); else if (e.frz > 0) col.setRGB(0.7, 0.95, 1.4); else if (e.slowT > 0) col.setRGB(0.7, 0.85, 1.2); else if (e.burnT > 0) col.setRGB(1.2, 0.8, 0.5); else col.setRGB(1, 1, 1);
        const showBar = e.hp < e.maxHp; e.bg.visible = e.fill.visible = showBar;
        if (showBar) { const k = Math.max(0, e.hp / e.maxHp), by = feet + e.ph + 0.06; e.bg.position.set(e.x, by, 0); e.fill.scale.x = 0.66 * k; e.fill.position.set(e.x - 0.33 * (1 - k), by, 0); e.fill.material.color.setHex(k > 0.5 ? 0x9be04a : k > 0.25 ? 0xe0a640 : 0xb04a5a); }
        if (e.g) e.g.m.position.set(e.x, e.y + e.by, 0);
      }
      for (const t of G.towers) {
        const face = t.type === 'tesla' ? 1 : (Math.cos(t.ang) < -0.05 ? -1 : 1), back = t.recoil * 0.06 * face;
        t.head.position.x = wx(t.c) - back; t.head.scale.x = face;
      }
      for (const p of G.projs) { if (!p.alive) continue; p.m.position.set(p.x, p.y, 0); if (p.g) p.g.m.position.set(p.x, p.y, 0); }
    }
    renderer.render(scene, camera);
    drawFx(dt);
  }
  function drawFx(dt) {
    fxc.clearRect(0, 0, cam.w, cam.h);
    fxc.textAlign = 'center'; fxc.textBaseline = 'middle';
    const s = cam.scale * cam.zoom;
    for (let i = texts.length - 1; i >= 0; i--) {
      const t = texts[i]; t.t += dt; if (t.t > 0.9) { texts.splice(i, 1); continue; }
      const p = toScreen(t.x + t.dx * t.t, t.y + t.t * 0.6);
      const size = Math.round(Math.max(9, s * (t.big ? 0.36 : 0.26)));
      fxc.font = size + 'px Silkscreen, monospace';
      fxc.globalAlpha = t.t > 0.6 ? (0.9 - t.t) / 0.3 : 1;
      fxc.fillStyle = '#16120f'; fxc.fillText(t.s, Math.round(p.x) + 1, Math.round(p.y) + 1);
      fxc.fillStyle = t.color; fxc.fillText(t.s, Math.round(p.x), Math.round(p.y));
    }
    fxc.globalAlpha = 1;
  }

  // ---------- Loop ----------
  let lastT = performance.now(), hudT = 0;
  function frame(now) {
    const dt = Math.min(0.05, (now - lastT) / 1000); lastT = now;
    let simDt = 0;
    if (G && state === 'play' && !paused) {
      simDt = dt * speed; let left = simDt;
      while (left > 0 && state === 'play') { const st = Math.min(left, 1 / 60); update(st); left -= st; }
      hudT -= dt; if (hudT <= 0) { updateHud(); hudT = 0.1; }
    }
    render(dt, simDt);
    requestAnimationFrame(frame);
  }

  // ---------- Entrada: toque, pinça, arrasto ----------
  const ptrs = new Map(); let gest = null;
  stage.addEventListener('pointerdown', e => {
    if (e.target.closest('#radial')) return;
    stage.setPointerCapture && stage.setPointerCapture(e.pointerId);
    ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const pts = [...ptrs.values()];
    if (pts.length === 1) gest = { sx: e.clientX, sy: e.clientY, moved: false, pinch: false, cx: cam.x, cy: cam.y };
    else if (pts.length === 2 && gest) {
      gest.pinch = true; gest.d0 = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y); gest.z0 = cam.zoom;
      gest.mx = (pts[0].x + pts[1].x) / 2; gest.my = (pts[0].y + pts[1].y) / 2; gest.cx = cam.x; gest.cy = cam.y;
    }
  });
  stage.addEventListener('pointermove', e => {
    if (!ptrs.has(e.pointerId) || !gest) return;
    ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const pts = [...ptrs.values()];
    if (pts.length >= 2 && gest.pinch) {
      const d = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y), mx = (pts[0].x + pts[1].x) / 2, my = (pts[0].y + pts[1].y) / 2;
      const r = stage.getBoundingClientRect();
      const before = toWorld(gest.mx - r.left, gest.my - r.top);
      cam.zoom = clamp(gest.z0 * d / gest.d0, 1, 3);
      cam.x = gest.cx; cam.y = gest.cy;
      const after = toWorld(mx - r.left, my - r.top);
      cam.x += before.x - after.x; cam.y += before.y - after.y; clampCam(); closeRadial();
    } else if (pts.length === 1) {
      const dx = e.clientX - gest.sx, dy = e.clientY - gest.sy;
      if (!gest.moved && Math.hypot(dx, dy) > 10) gest.moved = true;
      if (gest.moved && !gest.pinch && cam.zoom > 1) { const s = cam.scale * cam.zoom; cam.x = gest.cx - dx / s; cam.y = gest.cy + dy / s; clampCam(); closeRadial(); }
    }
  });
  function endPtr(e) {
    if (!ptrs.has(e.pointerId)) return;
    ptrs.delete(e.pointerId);
    if (ptrs.size === 0 && gest) {
      if (!gest.moved && !gest.pinch && e.type === 'pointerup') { const r = stage.getBoundingClientRect(); onTap(e.clientX - r.left, e.clientY - r.top); }
      gest = null;
    } else if (ptrs.size === 1 && gest) { const p = [...ptrs.values()][0]; gest.sx = p.x; gest.sy = p.y; gest.cx = cam.x; gest.cy = cam.y; gest.moved = true; }
  }
  stage.addEventListener('pointerup', endPtr); stage.addEventListener('pointercancel', endPtr);
  stage.addEventListener('wheel', e => {
    e.preventDefault(); const r = stage.getBoundingClientRect(), sx = e.clientX - r.left, sy = e.clientY - r.top;
    const before = toWorld(sx, sy); cam.zoom = clamp(cam.zoom * (e.deltaY < 0 ? 1.15 : 1 / 1.15), 1, 3);
    const after = toWorld(sx, sy); cam.x += before.x - after.x; cam.y += before.y - after.y; clampCam(); closeRadial();
  }, { passive: false });

  function onTap(sx, sy) {
    SFX.unlock();
    if (state !== 'play' || paused) return;
    const w = toWorld(sx, sy), c = Math.floor(w.x), r = Math.floor(-w.y);
    const wasOpen = !$('radial').hidden; const same = sel && sel.c === c && sel.r === r;
    closeRadial();
    if (wasOpen && same) return;
    if (c < 0 || r < 0 || c >= COLS || r >= ROWS) return;
    const g = G.grid[idx(c, r)];
    if (g === COREC || isReserved(c, r)) return;
    sel = { c, r }; SFX.play('click'); openRadial();
  }

  // ---------- Menu radial ----------
  const radial = $('radial');
  function closeRadial() { radial.hidden = true; radial.innerHTML = ''; sel = null; selM.visible = false; rangeM.visible = rangeRing.visible = false; }
  function showRange(x, y, r) { rangeM.visible = rangeRing.visible = true; rangeM.position.set(x, y, 0); rangeRing.position.set(x, y, 0); rangeM.scale.set(r, r, 1); rangeRing.scale.set(r, r, 1); }
  function rbtn(html, cost, onClick, cls) {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'rb ' + (cls || '');
    b.innerHTML = html + (cost !== null && cost !== undefined ? `<span class="cost${G.gold < cost ? ' poor' : ''}">${fmt(cost)}</span>` : '');
    b.addEventListener('click', ev => { ev.stopPropagation(); SFX.unlock(); onClick(); });
    return b;
  }
  function openRadial() {
    if (!sel) return;
    const { c, r } = sel, i = idx(c, r), g = G.grid[i];
    selM.visible = true; selM.position.set(wx(c), wy(r), 0);
    const btns = []; let title = '', sub = '';
    if (g === EMPTY) {
      title = '';
      TOWER_ORDER.forEach(type => btns.push(rbtn(`<img src="${ICONS[type]}" alt=""><span class="nm">${T(type)}</span>`, TOWERS[type].cost, () => { if (build(type, c, r)) { closeRadial(); } else refreshRadial(); })));
      const ok = canPlace(c, r);
      if (ok === 'blocked') sub = T('blocked');
    } else if (g === RUBBLE) {
      const o = G.rubM[i]; title = o && o.barrel ? T('barrel') : T('rubble');
      btns.push(rbtn(`<img src="${ICONS.rubble}" alt=""><span class="nm">${T('clear')}</span>`, rubbleCost(), () => { clearRubble(c, r); closeRadial(); }));
    } else if (g === TOWER) {
      const t = G.towers.find(q => q.c === c && q.r === r); if (!t) return;
      const s = towerStats(t);
      title = (t.branch ? T(t.type + '_' + t.branch) : T(t.type)) + ' · ' + T('level', t.lvl);
      sub = T('stats', fmt(s.dmg), s.range.toFixed(1));
      showRange(wx(c), wy(r), s.range);
      if (t.lvl >= MAX_LVL) btns.push(rbtn(`<span class="nm big">${T('max')}</span>`, null, () => { }, 'off'));
      else if (t.lvl === 2) {
        ['a', 'b'].forEach(br => btns.push(rbtn(`<span class="nm">${T(t.type + '_' + br)}</span>`, upCost(t), () => { upgrade(t, br); refreshRadial(); }, 'br-' + br)));
      } else btns.push(rbtn(`<span class="up">▲</span><span class="nm">${T('upgrade')}</span>`, upCost(t), () => { upgrade(t); refreshRadial(); }));
      if (t.type !== 'cryo' || !t.branch || t.branch !== 'b') btns.push(rbtn(`<span class="nm">${T('target')}</span><span class="nm b">${T('prio' + t.prio)}</span>`, null, () => { t.prio = (t.prio + 1) % 3; SFX.play('click'); refreshRadial(); }));
      btns.push(rbtn(`<span class="nm">${T('sell')}</span><span class="cost gain">+${fmt(sellValue(t))}</span>`, null, () => { sell(t); closeRadial(); }, 'sell'));
    }
    radial.innerHTML = '';
    const p = toScreen(wx(c), wy(r));
    const R = btns.length <= 1 ? 0 : btns.length === 2 ? 52 : 62;
    const cxp = clamp(p.x, 76, cam.w - 76), cyp = clamp(p.y, 96, cam.h - 120);
    radial.style.left = cxp + 'px'; radial.style.top = cyp + 'px';
    btns.forEach((b, k) => {
      const a = btns.length === 1 ? -Math.PI / 2 : -Math.PI / 2 + (k - (btns.length - 1) / 2) * (btns.length <= 3 ? 1.15 : 0.95) + (cyp < 140 ? Math.PI : 0);
      b.style.transform = `translate(${Math.cos(a) * R}px, ${Math.sin(a) * R + (btns.length === 1 ? -44 : 0)}px)`; radial.appendChild(b);
    });
    if (title || sub) {
      const lab = document.createElement('div'); lab.className = 'rlabel';
      lab.innerHTML = `<b></b><span></span>`; lab.querySelector('b').textContent = title; lab.querySelector('span').textContent = sub;
      lab.style.transform = `translate(-50%, ${cyp < 140 ? R + (btns.length === 1 ? 0 : 38) : -(R + (btns.length === 1 ? 120 : 80))}px)`; radial.appendChild(lab);
    }
    radial.hidden = false;
    if (!$('toast').classList.contains('big')) $('toast').className = 'toast';
  }
  function refreshRadial() { if (!sel) return; const s = sel; radial.innerHTML = ''; sel = s; openRadial(); }

  // ---------- HUD e telas ----------
  const ICONS = {};
  TOWER_ORDER.forEach(t => ICONS[t] = ART3.icon('tower', t, 3));
  ICONS.rubble = ART3.icon('obstacle', 0, 3); ICONS.coin = ART.icon('coin', 3); ICONS.heart = ART.icon('heart', 3); ICONS.ess = ART.icon('ess', 3); ICONS.skull = ART.icon('skull', 3);
  document.querySelectorAll('[data-ico]').forEach(el => el.style.backgroundImage = `url(${ICONS[el.dataset.ico]})`);

  let lastHud = '';
  function updateHud(force) {
    if (!G) return;
    const running = G.queue.length > 0;
    const zleft = G.queue.length + G.enemies.filter(e => e.alive).length;
    const l1 = T('waveN', running ? G.wave : G.wave + 1), l2 = running ? T('incoming') : T('waveIn', Math.max(0, Math.ceil(G.nextT))), bonus = running ? '' : T('bonus', earlyBonus());
    const key = [Math.floor(G.gold), G.wave, G.hp, G.maxHp, essenceFor(), l1, l2, bonus, speed, zleft].join('|');
    if (!force && key === lastHud) return; lastHud = key;
    $('gold').textContent = fmt(G.gold); $('wave').textContent = T('waveN', G.wave); $('hp').textContent = G.hp + '/' + G.maxHp; $('essRun').textContent = '+' + fmt(essenceFor());
    $('zleft').textContent = G.wave === 0 ? T('getReady') : T('zLeft', zleft);
    $('waveLbl').textContent = l1; $('waveSub').textContent = l2; $('waveBonus').textContent = bonus; $('btnWave').disabled = running;
    $('btnSpeed').textContent = 'x' + speed;
    const low = G.hp <= G.maxHp * 0.3; $('hpBox').classList.toggle('low', low);
    const segs = $('hpSegs'); const n = Math.min(G.maxHp, 30);
    if (segs.childElementCount !== n) { segs.innerHTML = ''; for (let i = 0; i < n; i++) segs.appendChild(document.createElement('i')); segs.style.gridTemplateColumns = `repeat(${n}, minmax(0, 1fr))`; }
    const on = Math.ceil(G.hp / G.maxHp * n); [...segs.children].forEach((el, i) => el.className = i < on ? (low ? 'bad' : 'ok') : '');
  }
  let toastTimer = 0;
  function toast(msg, secs, big) { const t = $('toast'); t.textContent = msg; t.className = 'toast show' + (big ? ' big' : ''); clearTimeout(toastTimer); toastTimer = setTimeout(() => t.className = 'toast', (secs || 1.6) * 1000); }

  function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.hidden = s.id !== id);
  }
  function applyLang() {
    window.LANG = meta.lang;
    document.documentElement.lang = meta.lang === 'pt' ? 'pt-BR' : 'en';
    document.querySelectorAll('[data-t]').forEach(el => el.textContent = T(el.dataset.t));
    document.querySelectorAll('.optLang .val').forEach(el => el.textContent = meta.lang === 'pt' ? 'PT' : 'EN');
    document.querySelectorAll('.optSfx .val').forEach(el => el.textContent = meta.sfx ? T('on') : T('off'));
    document.querySelectorAll('.optMusic .val').forEach(el => el.textContent = meta.music ? T('on') : T('off'));
    document.title = T('title');
    $('logo').innerHTML = meta.lang === 'pt' ? 'ÚLTIMO<span>BUNKER</span>' : 'LAST<span>BUNKER</span>';
    renderMenu(); if (!$('scrTalents').hidden) renderTalents(); updateHud(true);
  }
  function renderMenu() {
    $('menuBest').textContent = T('best', meta.best);
    $('menuEss').textContent = fmt(meta.essence);
    const rate = offlineRate(), hrs = 2 + tl('offhours');
    $('menuOffline').textContent = meta.best > 0 ? T('perHour', fmt(rate), hrs) : '';
  }

  // Talentos
  let talentTab = 'atk';
  function renderTalents() {
    $('talEss').textContent = fmt(meta.essence);
    document.querySelectorAll('#talTabs button').forEach(b => b.setAttribute('aria-selected', b.dataset.br === talentTab));
    const list = $('talList'); list.innerHTML = '';
    TALENTS.filter(t => t.br === talentTab).forEach(t => {
      const lv = tl(t.id), locked = t.req && tl(t.req) < 1, maxed = lv >= t.max, cost = talentCost(t, lv);
      const el = document.createElement('div'); el.className = 'tal' + (locked ? ' locked' : '') + (maxed ? ' maxed' : '') + (lv > 0 ? ' has' : '');
      el.innerHTML = `<div class="tinfo"><b></b><p></p><small></small></div><button type="button" class="buy"></button>`;
      el.querySelector('b').textContent = T('t_' + t.id);
      el.querySelector('p').textContent = T('t_' + t.id + '_d');
      el.querySelector('small').textContent = locked ? T('requires', T('t_' + t.req)) : `${lv}/${t.max}`;
      const b = el.querySelector('.buy');
      if (maxed) { b.textContent = T('maxed'); b.disabled = true; }
      else { b.innerHTML = `<i class="ico" style="background-image:url(${ICONS.ess})"></i>${fmt(cost)}`; b.disabled = locked || meta.essence < cost; }
      b.addEventListener('click', () => { if (meta.essence < cost || locked || maxed) return; meta.essence -= cost; meta.talents[t.id] = lv + 1; saveMeta(); SFX.play('up'); renderTalents(); renderMenu(); });
      list.appendChild(el);
    });
  }

  function endRun(retreat) {
    if (state !== 'play') return;
    state = 'over'; closeRadial();
    const e = essenceFor(); meta.essence += e; meta.best = Math.max(meta.best, G.wave); meta.runs++; saveMeta();
    $('overTitle').textContent = retreat ? T('overRetreat') : T('overDead');
    $('overWave').textContent = G.wave; $('overKills').textContent = fmt(G.kills); $('overEss').textContent = '+' + fmt(e);
    SFX.play('over');
    setTimeout(() => showScreen('scrOver'), retreat ? 0 : 900);
  }

  // Ganhos offline
  const offlineRate = () => Math.max(1, meta.best) * 1.2 * (1 + 0.2 * tl('offrate'));
  function checkOffline() {
    const away = (Date.now() - (meta.last || Date.now())) / 3600000;
    if (meta.best < 1 || away < 1 / 60) return;
    const hrs = Math.min(away, 2 + tl('offhours'));
    const gain = Math.floor(hrs * offlineRate());
    if (gain < 1) return;
    const h = Math.floor(hrs), m = Math.round((hrs - h) * 60);
    $('offBody').textContent = T('offlineBody', fmt(gain), (h ? h + 'h ' : '') + m + 'min');
    $('btnCollect').onclick = () => { meta.essence += gain; saveMeta(); SFX.unlock(); SFX.play('coin'); renderMenu(); showScreen(state === 'play' ? null : 'scrMenu'); if (state === 'play') paused = false; };
    showScreen('scrOffline'); if (state === 'play') paused = true;
  }

  // Botões
  const on = (id, fn) => $(id).addEventListener('click', () => { SFX.unlock(); fn(); });
  on('btnPlay', () => { SFX.play('click'); newRun(); });
  on('btnTalents', () => { SFX.play('click'); renderTalents(); showScreen('scrTalents'); });
  on('btnTalBack', () => { SFX.play('click'); renderMenu(); showScreen(state === 'over' ? 'scrOver' : 'scrMenu'); });
  document.querySelectorAll('#talTabs button').forEach(b => b.addEventListener('click', () => { talentTab = b.dataset.br; SFX.play('click'); renderTalents(); }));
  on('btnAgain', () => { SFX.play('click'); newRun(); });
  on('btnOverTalents', () => { SFX.play('click'); renderTalents(); showScreen('scrTalents'); });
  on('btnOverMenu', () => { SFX.play('click'); state = 'menu'; renderMenu(); showScreen('scrMenu'); });
  on('btnWave', () => callWave());
  on('btnSpeed', () => { const opts = tl('speed4') ? [1, 2, 4] : [1, 2]; speed = opts[(opts.indexOf(speed) + 1) % opts.length]; SFX.play('click'); updateHud(true); });
  on('btnPause', () => { if (state !== 'play') return; paused = true; closeRadial(); SFX.play('click'); showScreen('scrPause'); });
  on('btnResume', () => { paused = false; SFX.play('click'); showScreen(null); });
  on('btnRetreat', () => { if (state !== 'play') return; paused = true; closeRadial(); $('confirmText').textContent = T('confirmRetreat', fmt(essenceFor())); showScreen('scrConfirm'); });
  on('btnPauseEnd', () => { $('confirmText').textContent = T('confirmRetreat', fmt(essenceFor())); showScreen('scrConfirm'); });
  on('btnYes', () => { paused = false; endRun(true); });
  on('btnNo', () => { paused = false; showScreen(null); });
  document.querySelectorAll('.optLang').forEach(b => b.addEventListener('click', () => { meta.lang = meta.lang === 'pt' ? 'en' : 'pt'; saveMeta(); applyLang(); }));
  document.querySelectorAll('.optSfx').forEach(b => b.addEventListener('click', () => { meta.sfx = !meta.sfx; SFX.set('sfx', meta.sfx); saveMeta(); applyLang(); SFX.unlock(); SFX.play('click'); }));
  document.querySelectorAll('.optMusic').forEach(b => b.addEventListener('click', () => { meta.music = !meta.music; SFX.set('music', meta.music); saveMeta(); SFX.unlock(); applyLang(); }));

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { saveMeta(); if (state === 'play' && !paused) { paused = true; closeRadial(); showScreen('scrPause'); } }
    else checkOffline();
  });
  setInterval(saveMeta, 10000);
  window.addEventListener('resize', () => { resize(); closeRadial(); });

  // Início
  resize(); applyLang(); showScreen('scrMenu'); checkOffline();
  requestAnimationFrame(frame);
  // Atualização da hud depende das fontes; recalcula tamanho depois do layout final
  setTimeout(resize, 300);
  window.__bunker = { get G() { return G; }, meta, newRun, callWave, endRun, cellToScreen: (c, r) => toScreen(wx(c), wy(r)), setSpeed: v => { speed = v; }, sim: n => { for (let i = 0; i < n && state === 'play'; i++) update(1 / 30); }, build, upgrade, canPlace };
})();
