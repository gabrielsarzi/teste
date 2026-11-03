// Último Bunker — Mina sob ataque: os zumbis entram pelo topo e descem a mina em zigue-zague.
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
  const COLS = 9, SURF = 3, FH = 2.5, PX = 1 / 16;
  const floorTop = f => -(SURF + f * FH);
  const ledgeY = f => floorTop(f) - 0.5, walkFeet = f => floorTop(f) - 1.95, towerFeet = f => floorTop(f) - 0.92;
  // Andares ímpares são espelhados: o caminho dos zumbis vira um zigue-zague
  const mir = f => f % 2 === 1;
  const X = (f, x) => mir(f) ? COLS - x : x;
  const MINER_X = 3.7, ENTRY_X = 8.8, EXIT_X = 0.3;
  const slotCol = (f, i) => mir(f) ? COLS - 1 - MINE.slots[i] : MINE.slots[i];

  // ---------- Save ----------
  const SAVE_KEY = 'ultimo-bunker-mina-v2';
  const fresh = () => ({ gold: 0, floors: [{ miners: 0, towers: {}, boss: true }], up: {}, lang: null, sfx: true, music: true, last: Date.now(), total: 0 });
  let S = fresh();
  try { const o = JSON.parse(localStorage.getItem(SAVE_KEY)); if (o && o.floors) S = Object.assign(fresh(), o); } catch (e) { }
  function save() { S.last = Date.now(); try { localStorage.setItem(SAVE_KEY, JSON.stringify(S)); } catch (e) { } }
  const ul = id => S.up[id] || 0;
  if (!S.lang) S.lang = (navigator.language || 'pt').toLowerCase().startsWith('pt') ? 'pt' : 'en';
  window.LANG = S.lang;
  SFX.set('sfx', S.sfx); SFX.set('music', S.music);

  // ---------- Economia ----------
  const level = () => S.floors.length - 1;                       // força dos zumbis cresce com a profundidade aberta
  const minerPower = () => MINE.minerPower * Math.pow(1.25, ul('tools'));
  const floorRate = f => S.floors[f].miners * minerPower() / FLOORS[f].h * FLOORS[f].v;
  const tapPower = () => 1 + ul('pick');
  const totalMiners = () => S.floors.reduce((a, fl) => a + fl.miners, 0);
  const zombieBaseHp = () => MINE.zombieHp(level()) * (1 + 0.03 * totalMiners());
  function totalNoise() { let n = 0; S.floors.forEach((fl, f) => { n += fl.miners + (RT[f] ? RT[f].tapNoise : 0); }); return n * Math.pow(0.92, ul('silence')); }
  const spawnInterval = n => Math.max(0.5, 10 / (0.4 + 0.3 * Math.pow(n, 0.85)));
  function totalRate() { let r = 0; S.floors.forEach((fl, f) => { if (!RT[f] || !RT[f].invaded) r += floorRate(f); }); return r; }

  // ---------- Three.js ----------
  const stage = $('stage'), glc = $('gl'), fx = $('fx'), fxc = fx.getContext('2d');
  const renderer = new THREE.WebGLRenderer({ canvas: glc, antialias: false });
  renderer.setClearColor(0x16121c);
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -10, 10);
  const cam = { y: -2, scale: 40, w: 1, h: 1, shake: 0 };
  const geo = new THREE.PlaneGeometry(1, 1);
  const matOf = (map, o) => new THREE.MeshBasicMaterial(Object.assign({ map: map || null, transparent: true, depthTest: false, depthWrite: false, side: THREE.DoubleSide }, o || {}));
  function mesh(map, w, h, order, o) { const m = new THREE.Mesh(geo, matOf(map, o)); m.scale.set(w, h, 1); m.renderOrder = order; scene.add(m); return m; }
  const L = { bg: 0, shadow: 2, obj: 100, proj: 900, glow: 1001, part: 1002, bar: 1003, ui: 1004 };
  const depth = (m, feetY) => { m.renderOrder = 100 + Math.round(-feetY * 24); };
  function sprite(tex, wpx, hpx, x, feetY) { const m = mesh(tex, wpx * PX, hpx * PX, L.obj); m.position.set(x, feetY + hpx * PX / 2, 0); depth(m, feetY); return m; }
  function shadowAt(x, y, w) { const m = mesh(ART3.tex('shadow', 0), w, w * 0.5, L.shadow); m.position.set(x, y, 0); return m; }

  // Efeitos
  const GLOW = ART.glowTex(), glowPool = [];
  function glow(x, y, size, color, life, intensity) {
    let g = glowPool.find(o => !o.on);
    if (!g) { g = { m: mesh(GLOW, 1, 1, L.glow, { blending: THREE.AdditiveBlending }), on: false }; glowPool.push(g); }
    g.on = true; g.m.visible = true; g.m.position.set(x, y, 0); g.m.scale.set(size, size, 1); g.m.material.color.setHex(color);
    g.life = life; g.max = life; g.i = intensity || 1; g.flicker = 0; return g;
  }
  const partPool = [];
  function particle(x, y, color, n, spd, life, size) {
    for (let i = 0; i < n; i++) {
      let p = partPool.find(o => !o.on);
      if (!p) { if (partPool.length > 400) return; p = { m: mesh(null, 1, 1, L.part), on: false }; partPool.push(p); }
      const a = Math.random() * Math.PI * 2, v = spd * (0.3 + Math.random() * 0.7);
      p.on = true; p.m.visible = true; p.x = x; p.y = y; p.vx = Math.cos(a) * v; p.vy = Math.sin(a) * v + 1;
      p.life = p.max = life * (0.6 + Math.random() * 0.6); p.s = size || 0.1; p.m.material.color.set(color); p.m.material.opacity = 1;
    }
  }
  const boltPool = [];
  function bolt(x0, y0, x1, y1, color) {
    const pts = [[x0, y0]]; for (let i = 1; i < 4; i++) { const t = i / 4; pts.push([x0 + (x1 - x0) * t + (Math.random() - 0.5) * 0.3, y0 + (y1 - y0) * t + (Math.random() - 0.5) * 0.3]); } pts.push([x1, y1]);
    for (let i = 0; i < pts.length - 1; i++) {
      let b = boltPool.find(o => !o.on); if (!b) { b = { m: mesh(null, 1, 1, L.part, { blending: THREE.AdditiveBlending }), on: false }; boltPool.push(b); }
      const [ax, ay] = pts[i], [bx, by] = pts[i + 1]; b.on = true; b.m.visible = true; b.life = 0.12; b.m.material.color.setHex(color); b.m.material.opacity = 1;
      b.m.position.set((ax + bx) / 2, (ay + by) / 2, 0); b.m.scale.set(Math.hypot(bx - ax, by - ay) + 0.04, 0.07, 1); b.m.rotation.z = Math.atan2(by - ay, bx - ax);
    }
  }
  const ringPool = [], ringGeo = new THREE.RingGeometry(0.85, 1, 32);
  function ring(x, y, r, color, life) {
    let o = ringPool.find(q => !q.on); if (!o) { o = { m: new THREE.Mesh(ringGeo, matOf(null, { blending: THREE.AdditiveBlending })), on: false }; o.m.renderOrder = L.part; scene.add(o.m); ringPool.push(o); }
    o.on = true; o.m.visible = true; o.m.position.set(x, y, 0); o.r = r; o.life = o.max = life; o.m.material.color.setHex(color);
  }
  const texts = [];
  function floatText(x, y, s, color, big) { if (texts.length > 60) texts.shift(); texts.push({ x, y, s, color, t: 0, big: !!big, dx: (Math.random() - 0.5) * 0.3 }); }

  // ---------- Câmera (rolagem vertical) ----------
  const worldBottom = () => floorTop(S.floors.length) - FH;
  function resize() {
    const r = stage.getBoundingClientRect(); cam.w = Math.max(1, r.width); cam.h = Math.max(1, r.height);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(dpr); renderer.setSize(cam.w, cam.h, false);
    fx.width = Math.round(cam.w * dpr); fx.height = Math.round(cam.h * dpr); fxc.setTransform(dpr, 0, 0, dpr, 0, 0);
    const s = cam.w / (COLS + 0.2), snapped = Math.floor(s * dpr / 16) * 16 / dpr;
    cam.scale = snapped >= s * 0.85 ? snapped : s;
    clampCam();
  }
  function clampCam() { const hh = cam.h / 2 / cam.scale, bot = 1.6, lo = worldBottom() + hh - bot, hi = 0.3 - hh; cam.y = lo > hi ? hi : clamp(cam.y, lo, hi); }
  function updateCamera() {
    const hw = cam.w / 2 / cam.scale, hh = cam.h / 2 / cam.scale, sh = cam.shake > 0 ? (Math.random() - 0.5) * cam.shake : 0;
    camera.left = -hw; camera.right = hw; camera.top = hh; camera.bottom = -hh;
    camera.position.set(COLS / 2 + sh, cam.y + sh, 5); camera.updateProjectionMatrix();
  }
  const toWorld = (sx, sy) => ({ x: COLS / 2 + (sx - cam.w / 2) / cam.scale, y: cam.y - (sy - cam.h / 2) / cam.scale });
  const toScreen = (x, y) => ({ x: (x - COLS / 2) * cam.scale + cam.w / 2, y: -(y - cam.y) * cam.scale + cam.h / 2 });
  const shake = m => { cam.shake = Math.max(cam.shake, m); };

  // ---------- Mundo ----------
  const surfM = mesh(ART3.tex('surface', 0), COLS, 3, L.bg); surfM.position.set(COLS / 2, -1.5, 0);
  const skyM = mesh(null, 40, 20, -1, { color: 0x7a8448, transparent: false }); skyM.position.set(COLS / 2, 10, 0);
  shadowAt(5.0, -2.05, 2.1);
  sprite(ART3.tex('bunker', 0), 32, 28, 5.0, -2.1);
  const RT = [];
  let zombies = [], projs = [], lockedM = [], spawnT = 4;

  function buildFloor(f) {
    const rt = { tapNoise: 0, ore: 0, invaded: false, fleeT: 0, minerM: [], slotM: {}, towerM: {} };
    rt.bg = mesh(ART3.tex('floor', f), COLS, FH, L.bg); rt.bg.position.set(COLS / 2, floorTop(f) - FH / 2, 0);
    if (mir(f)) rt.bg.scale.x = -COLS;
    [3, 6].forEach(c => { const g = glow(X(f, c + 0.5), ledgeY(f) + 0.2, 2.2, 0xffd77a, Infinity, 0.45); g.flicker = 1; });
    MINE.slots.forEach((_, i) => { const m = sprite(ART3.tex('slot', 0), 16, 8, slotCol(f, i) + 0.5, towerFeet(f) - 0.06); m.renderOrder = 90; rt.slotM[i] = m; });
    RT[f] = rt;
    refreshMiners(f);
    Object.keys(S.floors[f].towers).forEach(i => placeTowerMesh(f, +i));
  }
  function refreshMiners(f) {
    const rt = RT[f], n = Math.min(S.floors[f].miners, 4);
    while (rt.minerM.length < n) {
      const k = rt.minerM.length, x = X(f, 2.3 + (k % 2) * 0.75 + (k >= 2 ? 0.35 : 0)), feet = walkFeet(f) + (k >= 2 ? 0.25 : 0);
      const m = sprite(ART3.tex('miner', 0), 16, 20, x, feet); m.scale.x = mir(f) ? m.scale.x : -m.scale.x; m.userData = { ph: Math.random(), feet }; rt.minerM.push(m);
    }
    while (rt.minerM.length > n) scene.remove(rt.minerM.pop());
  }
  function refreshLocked() {
    lockedM.forEach(m => scene.remove(m)); lockedM = [];
    for (let f = S.floors.length; f < S.floors.length + 6; f++) { const m = mesh(ART3.tex('locked', 0), COLS, FH, L.bg); m.position.set(COLS / 2, floorTop(f) - FH / 2, 0); if (mir(f)) m.scale.x = -COLS; lockedM.push(m); }
  }

  // ---------- Torres ----------
  function towerStats(t, f) {
    const d = TOWERS[t.type], Lv = t.lvl;
    const s = { dmg: d.dmg * Math.pow(1.35, Lv - 1) * MINE.towerPower(f), rate: d.rate * (1 + 0.04 * (Lv - 1)), range: d.range + 0.6 + 0.1 * Math.min(Lv - 1, 10),
      splash: d.splash || 0, slow: d.slow || 0, slowT: d.slowT || 0, chain: d.chain || 0, burn: 0, freeze: 0, pulse: false };
    if (t.branch) d[t.branch](s);
    s.range *= 1 + 0.06 * ul('range');
    return s;
  }
  const towerCost = (type, f) => Math.round(TOWERS[type].cost * Math.pow(4, f));
  const upCost = (t, f) => Math.round(TOWERS[t.type].cost * Math.pow(1.6, t.lvl) * Math.pow(4, f));
  const towerOpen = type => S.floors.length >= MINE.towerUnlock[type];
  function placeTowerMesh(f, i) {
    const t = S.floors[f].towers[i], rt = RT[f], c = slotCol(f, i);
    if (rt.towerM[i]) { scene.remove(rt.towerM[i].m); scene.remove(rt.towerM[i].sh); rt.towerM[i].g.on = false; rt.towerM[i].g.m.visible = false; }
    if (!t) { delete rt.towerM[i]; rt.slotM[i].visible = true; return; }
    rt.slotM[i].visible = false;
    rt.towerM[i] = { sh: shadowAt(c + 0.5, towerFeet(f) + 0.02, 0.9), m: sprite(ART3.tex('tower', t.type), 16, 22, c + 0.5, towerFeet(f)), g: glow(c + 0.5, towerFeet(f) + 0.8, 1.6, TOWERS[t.type].light, Infinity, 0.35), cd: 0.3, ang: 0, recoil: 0 };
  }
  function buyTower(f, i, type) {
    const cost = towerCost(type, f);
    if (S.gold < cost) { toast(T('noGold')); SFX.play('error'); return false; }
    S.gold -= cost; S.floors[f].towers[i] = { type, lvl: 1, branch: null, prio: 0, spent: cost };
    placeTowerMesh(f, i); particle(slotCol(f, i) + 0.5, towerFeet(f) + 0.3, '#c8b07a', 10, 2, 0.4, 0.09); SFX.play('build'); save(); return true;
  }
  function upgradeTower(f, i, branch) {
    const t = S.floors[f].towers[i], cost = upCost(t, f);
    if (S.gold < cost) { toast(T('noGold')); SFX.play('error'); return; }
    S.gold -= cost; t.spent += cost; t.lvl++; if (branch) t.branch = branch;
    const x = slotCol(f, i) + 0.5; particle(x, towerFeet(f) + 0.6, '#ffd77a', 14, 2.5, 0.5, 0.08); glow(x, towerFeet(f) + 0.6, 2.2, 0xffd77a, 0.4, 1); SFX.play('up'); save();
  }
  function sellTower(f, i) { const t = S.floors[f].towers[i]; S.gold += Math.floor(t.spent * 0.5); delete S.floors[f].towers[i]; placeTowerMesh(f, i); SFX.play('coin'); save(); }

  // ---------- Zumbis ----------
  const enemyPool = [];
  function spawnZombie(kind, bossFor) {
    const base = zombieBaseHp(), L0 = level();
    const hp = kind === 'boss' ? base * 30 : kind === 'runner' ? base * 0.6 : base;
    let e = enemyPool.pop();
    if (!e) { e = { m: mesh(null, 1, 1, L.obj), sh: shadowAt(0, 0, 0.7), bg: mesh(null, 0.7, 0.08, L.bar, { color: 0x16120f }), fill: mesh(null, 0.66, 0.05, L.bar, { color: 0x9fe870 }) }; }
    const dims = kind === 'boss' ? [28, 28] : kind === 'runner' ? [16, 18] : [16, 20];
    Object.assign(e, { kind, f: 0, x: X(0, ENTRY_X) + Math.random() * 0.2, hp, maxHp: hp, alive: true, attacking: false, hitT: 0, slow: 0, slowT: 0, frz: 0, burn: 0, burnT: 0, anim: Math.random(),
      spd: (kind === 'runner' ? 1.2 : kind === 'boss' ? 0.55 : 0.65) * (1 + L0 * 0.05), v: (Math.random() * ART3.ZV_COUNT) | 0, drop: 0, face: -1, bossFor,
      pw: dims[0] * PX, ph: dims[1] * PX, lane: (Math.random() - 0.5) * 0.25 });
    e.by = e.ph * 0.45; e.y = walkFeet(0) + e.lane; e.m.visible = e.sh.visible = true; e.bg.visible = e.fill.visible = false;
    e.m.scale.set(-e.pw, e.ph, 1); e.sh.scale.set(kind === 'boss' ? 1.4 : 0.7, kind === 'boss' ? 0.7 : 0.35, 1);
    zombies.push(e);
    if (kind === 'boss') e.g = glow(e.x, e.y + 0.8, 2.6, 0x9fe870, Infinity, 0.5);
    return e;
  }
  const zTex = (e, fr) => e.kind === 'walker' ? ART3.tex('walker', e.v * 2 + fr) : ART3.tex(e.kind, fr);
  function releaseZombie(e) { e.alive = false; e.m.visible = e.sh.visible = e.bg.visible = e.fill.visible = false; if (e.g) { e.g.on = false; e.g.m.visible = false; e.g = null; } enemyPool.push(e); }
  function damage(e, amt, crit, quiet) {
    if (!e.alive) return;
    e.hp -= amt; if (!quiet) { e.hitT = 0.08; floatText(e.x, e.y + e.ph + 0.1, fmt(Math.max(1, amt)), crit ? '#ffd77a' : '#fbf4e0', crit); }
    if (e.hp <= 0) killZombie(e);
  }
  function killZombie(e) {
    particle(e.x, e.y + e.by, '#8fbf6a', e.kind === 'boss' ? 30 : 8, 2.2, 0.45, 0.1); particle(e.x, e.y + e.by, '#8f2f3c', e.kind === 'boss' ? 20 : 4, 1.6, 0.5, 0.12);
    SFX.play('die');
    if (e.kind === 'boss') {
      const nf = e.bossFor, bonus = Math.ceil(Math.max(totalRate() * 120, MINE.floorCost(Math.max(1, nf)) * 0.5));
      S.gold += bonus; if (S.floors[nf]) S.floors[nf].boss = true; floatText(e.x, e.y + 1.4, '+' + fmt(bonus), '#f2b84b', true);
      toast(T('bossDown', fmt(bonus)), 3); shake(0.35); SFX.play('coin'); glow(e.x, e.y + 0.8, 4, 0x9fe870, 0.6, 1.2); save();
    }
    releaseZombie(e);
  }
  // Para em andar com mineiros; andar abandonado é atravessado e o zumbi desce
  function stepZombie(e, dt) {
    if (e.burnT > 0) { e.burnT -= dt; damage(e, e.burn * dt, false, true); if (!e.alive) return; }
    if (e.hitT > 0) e.hitT -= dt; if (e.slowT > 0) e.slowT -= dt;
    if (e.frz > 0) { e.frz -= dt; return; }
    if (e.drop > 0) {
      e.drop -= dt; const k = 1 - Math.max(0, e.drop) / 0.6;
      e.y = walkFeet(e.f) + (walkFeet(e.f + 1) - walkFeet(e.f)) * k * k;
      if (e.drop <= 0) { e.f++; e.y = walkFeet(e.f) + e.lane; e.x = X(e.f, ENTRY_X); }
      return;
    }
    const fl = S.floors[e.f], last = e.f === S.floors.length - 1;
    const stop = fl.miners > 0 || last, tx = stop ? X(e.f, MINER_X + (e.kind === 'boss' ? 0.4 : 0)) : X(e.f, EXIT_X);
    const dx = tx - e.x, sp = e.spd * (e.slowT > 0 ? 1 - e.slow : 1) * dt;
    if (Math.abs(dx) > 0.02) { e.x += Math.sign(dx) * Math.min(Math.abs(dx), sp); e.face = Math.sign(dx); e.anim += dt * e.spd * 3.5; e.attacking = false; }
    else if (stop) { e.attacking = fl.miners > 0; e.anim += dt * 2; }
    else { e.drop = 0.6; e.attacking = false; }
    e.prog = e.f * 20 + Math.abs(e.x - X(e.f, ENTRY_X));
  }

  // ---------- Disparos ----------
  const projPool = [];
  function addProj(o) {
    let p = projPool.pop(); if (!p) p = { m: mesh(null, 1, 1, L.proj) };
    Object.assign(p, o, { alive: true, g: null });
    const size = o.kind === 'bullet' ? 0.16 : o.kind === 'shell' ? 0.3 : 0.22;
    p.m.material.map = ART.tex(o.kind); p.m.material.needsUpdate = true; p.m.scale.set(size, size, 1); p.m.visible = true; p.m.position.set(p.x, p.y, 0);
    if (o.kind !== 'bullet') p.g = glow(p.x, p.y, 0.9, o.kind === 'shell' ? 0xff9040 : 0x70c8ff, Infinity, 0.6);
    projs.push(p);
  }
  function releaseProj(p) { p.m.visible = false; if (p.g) { p.g.on = false; p.g.m.visible = false; } projPool.push(p); }
  function stepProj(p, dt) {
    if (p.kind === 'shell') {
      p.t += dt; const k = Math.min(1, p.t / p.T); p.x = p.sx + (p.tx - p.sx) * k; p.y = p.sy + (p.ty - p.sy) * k + Math.sin(k * Math.PI) * 0.8;
      if (k >= 1) { explode(p); p.alive = false; } return;
    }
    const e = p.tgt; if (!e || !e.alive) { p.alive = false; return; }
    const tx = e.x, ty = e.y + e.by, dx = tx - p.x, dy = ty - p.y, d = Math.hypot(dx, dy), mv = p.spd * dt;
    p.m.rotation.z = Math.atan2(dy, dx) - Math.PI / 2;
    if (d <= mv + 0.05) {
      p.alive = false; damage(e, p.dmg, p.crit);
      if (p.kind === 'shard' && e.alive) { e.slow = Math.max(e.slow, p.slow); e.slowT = Math.max(e.slowT, p.slowT); if (p.freeze && Math.random() < p.freeze) e.frz = 1; }
      particle(tx, ty, p.kind === 'shard' ? '#7fd3f5' : '#ffd77a', 3, 1.5, 0.2, 0.07);
    } else { p.x += dx / d * mv; p.y += dy / d * mv; }
  }
  function explode(p) {
    SFX.play('boom'); particle(p.x, p.y, '#ff8c2a', 12, 2.6, 0.45, 0.11); glow(p.x, p.y, p.splash * 3, 0xff9040, 0.35, 1.2); ring(p.x, p.y, p.splash, 0xff9040, 0.3);
    zombies.forEach(e => { if (!e.alive || e.drop > 0) return; const d = Math.hypot(e.x - p.x, (e.y + e.by) - p.y); if (d <= p.splash) { damage(e, p.dmg * (d < p.splash * 0.4 ? 1 : 0.6), p.crit); if (p.burn && e.alive) { e.burn = p.dmg * p.burn; e.burnT = 3; } } });
  }
  function stepTower(f, i, dt) {
    const t = S.floors[f].towers[i], tm = RT[f].towerM[i]; if (!t || !tm) return;
    tm.cd -= dt; tm.recoil = Math.max(0, tm.recoil - dt * 6); if (tm.cd > 0) return;
    const s = towerStats(t, f), x = slotCol(f, i) + 0.5, y = towerFeet(f) + 0.7;
    let best = null, bv = Infinity;
    for (const e of zombies) {
      if (!e.alive) continue; const d = Math.hypot(e.x - x, e.y + e.by - y); if (d > s.range) continue;
      const v = t.prio === 0 ? -e.prog : t.prio === 1 ? -e.hp : d; if (v < bv) { bv = v; best = e; }
    }
    if (!best) { tm.cd = 0.1; return; }
    tm.cd = 1 / s.rate; tm.recoil = 1; tm.ang = Math.atan2(best.y - y, best.x - x);
    const crit = Math.random() < 0.05, dmg = s.dmg * (crit ? 2 : 1);
    if (t.type === 'gunner') { addProj({ kind: 'bullet', x, y, tgt: best, spd: 12, dmg, crit }); SFX.play('shoot'); glow(x, y, 0.8, 0xffc060, 0.06, 1); }
    else if (t.type === 'mortar') { addProj({ kind: 'shell', x, y, sx: x, sy: y, tx: best.x + best.face * best.spd * 0.7, ty: best.y + best.by, t: 0, T: 0.7, dmg, crit, splash: s.splash, burn: s.burn }); SFX.play('shoot'); }
    else if (t.type === 'cryo') {
      if (s.pulse) { ring(x, y, s.range, 0x70c8ff, 0.4); SFX.play('ice'); zombies.forEach(e => { if (e.alive && Math.hypot(e.x - x, e.y + e.by - y) <= s.range) { damage(e, dmg, crit); if (e.alive) { e.slow = Math.max(e.slow, s.slow); e.slowT = Math.max(e.slowT, s.slowT); } } }); }
      else { addProj({ kind: 'shard', x, y, tgt: best, spd: 8, dmg, crit, slow: s.slow, slowT: s.slowT, freeze: s.freeze }); SFX.play('ice'); }
    } else if (t.type === 'tesla') {
      SFX.play('zap'); const hit = [best]; let cur = best, px = x, py = y + 0.3, d = dmg;
      for (let k = 0; k <= s.chain && cur; k++) {
        bolt(px, py, cur.x, cur.y + cur.by, 0xb890ff); glow(cur.x, cur.y + cur.by, 1.1, 0xb890ff, 0.12, 1);
        const nx = cur.x, ny = cur.y + cur.by; damage(cur, d, crit); d *= 0.85; px = nx; py = ny;
        let nb = null, nd = 1.8; zombies.forEach(e => { if (e.alive && !hit.includes(e)) { const q = Math.hypot(e.x - nx, e.y + e.by - ny); if (q < nd) { nd = q; nb = e; } } }); cur = nb; if (nb) hit.push(nb);
      }
    }
  }

  // ---------- Loop de simulação ----------
  function update(dt) {
    let gain = 0;
    S.floors.forEach((fl, f) => {
      const rt = RT[f]; if (!rt) return;
      rt.tapNoise *= Math.pow(0.85, dt);
      rt.invaded = fl.miners > 0 && zombies.some(e => e.alive && e.f === f && e.attacking);
      if (!rt.invaded) gain += floorRate(f) * dt;
      if (rt.invaded) { rt.fleeT += dt; if (rt.fleeT > 7) { rt.fleeT = 0; fl.miners--; refreshMiners(f); toast(T('minerFled', f + 1), 2); SFX.play('hurt'); shake(0.12); } }
      else rt.fleeT = 0;
      for (let i = 0; i < MINE.slots.length; i++) stepTower(f, i, dt);
    });
    S.gold += gain; S.total += gain;
    // o barulho de toda a mina atrai zumbis pela entrada do primeiro andar
    const n = totalNoise();
    if (n > 0.2) { spawnT -= dt; if (spawnT <= 0) { spawnZombie(Math.random() < 0.25 + level() * 0.03 ? 'runner' : 'walker'); spawnT = spawnInterval(n) * (0.7 + Math.random() * 0.6); } }
    for (const p of projs) if (p.alive) stepProj(p, dt);
    for (const e of zombies) if (e.alive) stepZombie(e, dt);
    zombies = zombies.filter(e => e.alive);
    projs = projs.filter(p => { if (!p.alive) releaseProj(p); return p.alive; });
  }

  // ---------- Render ----------
  function render(dt) {
    if (cam.shake > 0) cam.shake = Math.max(0, cam.shake - dt * 1.2);
    updateCamera();
    const now = performance.now() / 1000;
    for (const g of glowPool) { if (!g.on) continue; let a = g.i * (g.life === Infinity ? 1 : g.life / g.max); if (g.flicker) a *= 0.85 + Math.random() * 0.2; g.m.material.opacity = Math.min(1, a); if (g.life !== Infinity) { g.life -= dt; if (g.life <= 0) { g.on = false; g.m.visible = false; } } }
    for (const p of partPool) { if (!p.on) continue; p.life -= dt; if (p.life <= 0) { p.on = false; p.m.visible = false; continue; } p.vy -= 6 * dt; p.x += p.vx * dt; p.y += p.vy * dt; p.vx *= 0.92; const k = p.life / p.max; p.m.position.set(p.x, p.y, 0); p.m.scale.set(p.s, p.s, 1); p.m.material.opacity = Math.min(1, k * 1.5); }
    for (const b of boltPool) { if (!b.on) continue; b.life -= dt; b.m.material.opacity = Math.max(0, b.life / 0.12); if (b.life <= 0) { b.on = false; b.m.visible = false; } }
    for (const o of ringPool) { if (!o.on) continue; o.life -= dt; const k = 1 - o.life / o.max, r = o.r * (0.3 + 0.7 * k); o.m.scale.set(r, r, 1); o.m.material.opacity = Math.max(0, 1 - k); if (o.life <= 0) { o.on = false; o.m.visible = false; } }
    S.floors.forEach((fl, f) => { const rt = RT[f]; if (!rt) return; rt.minerM.forEach(m => { const fr = rt.invaded ? 0 : Math.floor(now * 3 + m.userData.ph * 2) % 2; m.material.map = ART3.tex('miner', fr); m.position.y = m.userData.feet + 20 * PX / 2 + (rt.invaded ? Math.sin(now * 20) * 0.03 : 0); }); });
    for (const e of zombies) {
      if (!e.alive) continue;
      e.m.position.set(e.x, e.y + e.ph / 2, 0); e.m.scale.x = e.pw * e.face; depth(e.m, e.y); e.sh.position.set(e.x, e.y + 0.02, 0); e.sh.visible = e.drop <= 0;
      e.m.material.map = zTex(e, Math.floor(e.anim) % 2);
      const col = e.m.material.color; if (e.hitT > 0) col.setRGB(1, 0.45, 0.45); else if (e.frz > 0 || e.slowT > 0) col.setRGB(0.7, 0.88, 1.25); else if (e.burnT > 0) col.setRGB(1.2, 0.8, 0.5); else col.setRGB(1, 1, 1);
      const show = e.hp < e.maxHp; e.bg.visible = e.fill.visible = show;
      if (show) { const kk = Math.max(0, e.hp / e.maxHp), by = e.y + e.ph + 0.06; e.bg.position.set(e.x, by, 0); e.fill.scale.x = 0.66 * kk; e.fill.position.set(e.x - 0.33 * (1 - kk), by, 0); e.fill.material.color.setHex(kk > 0.5 ? 0x9fe870 : kk > 0.25 ? 0xf2b84b : 0xe8735a); }
      if (e.g) e.g.m.position.set(e.x, e.y + 0.8, 0);
    }
    S.floors.forEach((fl, f) => { const rt = RT[f]; if (!rt) return; for (const i in rt.towerM) { const tm = rt.towerM[i], face = fl.towers[i].type === 'tesla' ? 1 : (Math.cos(tm.ang) < -0.05 ? -1 : 1); tm.m.scale.x = face; tm.m.position.x = slotCol(f, +i) + 0.5 - tm.recoil * 0.06 * face; } });
    for (const p of projs) { if (!p.alive) continue; p.m.position.set(p.x, p.y, 0); if (p.g) p.g.m.position.set(p.x, p.y, 0); }
    renderer.render(scene, camera);
    drawFx(dt);
    placeFloorUi();
  }
  function drawFx(dt) {
    fxc.clearRect(0, 0, cam.w, cam.h); fxc.textBaseline = 'middle';
    const s = cam.scale;
    S.floors.forEach((fl, f) => {
      const lx = mir(f) ? 0.95 : 3.75, p = toScreen(lx, floorTop(f) - 0.2); if (p.y < -30 || p.y > cam.h + 30) return;
      const rt = RT[f]; fxc.textAlign = 'left'; fxc.font = '700 ' + Math.round(s * 0.24) + 'px Silkscreen, monospace';
      const label = `${f + 1} · ${T(FLOORS[f].ore).toUpperCase()}`;
      fxc.fillStyle = '#16121c'; fxc.fillText(label, p.x + 1, p.y + 1); fxc.fillStyle = '#fbf4e0'; fxc.fillText(label, p.x, p.y);
      const w = fxc.measureText(label).width;
      let tag, col;
      if (rt && rt.invaded) { tag = T('invaded'); col = '#e8735a'; }
      else if (!fl.miners) { tag = T('abandoned'); col = '#d9cfae'; }
      else { tag = T('perSec', fmt(floorRate(f))); col = '#f2b84b'; }
      fxc.fillStyle = col; fxc.fillText(' ' + tag, p.x + w, p.y);
      // barra de dureza do minério sobre o veio
      if (FLOORS[f].h > 1 && rt) {
        const q = toScreen(X(f, 1.5), walkFeet(f) + 1.25), bw = s * 0.7, k = rt.ore / FLOORS[f].h;
        fxc.fillStyle = '#16121c'; fxc.fillRect(q.x - bw / 2 - 1, q.y - 3, bw + 2, 6);
        fxc.fillStyle = ART3.ORES[f % ART3.ORES.length]; fxc.fillRect(q.x - bw / 2, q.y - 2, bw * k, 4);
      }
    });
    fxc.textAlign = 'center';
    for (let i = texts.length - 1; i >= 0; i--) {
      const t = texts[i]; t.t += dt; if (t.t > 0.9) { texts.splice(i, 1); continue; }
      const p = toScreen(t.x + t.dx * t.t, t.y + t.t * 0.6);
      fxc.font = '700 ' + Math.round(Math.max(10, s * (t.big ? 0.38 : 0.27))) + 'px Silkscreen, monospace';
      fxc.globalAlpha = t.t > 0.6 ? (0.9 - t.t) / 0.3 : 1;
      fxc.fillStyle = '#16121c'; fxc.fillText(t.s, Math.round(p.x) + 1, Math.round(p.y) + 1); fxc.fillStyle = t.color; fxc.fillText(t.s, Math.round(p.x), Math.round(p.y));
    }
    fxc.globalAlpha = 1;
  }

  // ---------- Interface dentro do mundo ----------
  const floorUi = $('floorUi');
  function buildFloorUi() {
    floorUi.innerHTML = '';
    S.floors.forEach((fl, f) => {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'hire'; b.dataset.f = f;
      b.innerHTML = `<span class="hn"></span><span class="hc"></span>`;
      b.addEventListener('click', ev => { ev.stopPropagation(); SFX.unlock(); hireMiner(f); });
      floorUi.appendChild(b);
      // abandonar o andar: dois toques para confirmar
      const q = document.createElement('button'); q.type = 'button'; q.className = 'quit'; q.dataset.f = f; q.textContent = '✕'; q.setAttribute('aria-label', T('abandon'));
      q.addEventListener('click', ev => {
        ev.stopPropagation(); SFX.unlock();
        if (!q.classList.contains('arm')) { q.classList.add('arm'); q.textContent = T('abandon'); setTimeout(() => { q.classList.remove('arm'); q.textContent = '✕'; }, 2500); return; }
        S.floors[f].miners = 0; refreshMiners(f); q.classList.remove('arm'); q.textContent = '✕'; toast(T('abandonedMsg', f + 1), 2); SFX.play('hurt'); save(); updateHud(true);
      });
      floorUi.appendChild(q);
    });
    if (S.floors.length < FLOORS.length) {
      const d = document.createElement('button'); d.type = 'button'; d.className = 'dig'; d.id = 'digBtn';
      d.innerHTML = `<b></b><span></span>`;
      d.addEventListener('click', ev => { ev.stopPropagation(); SFX.unlock(); digFloor(); });
      floorUi.appendChild(d);
    }
  }
  function placeFloorUi() {
    floorUi.querySelectorAll('.hire').forEach(b => {
      const f = +b.dataset.f, p = toScreen(X(f, 2.65), ledgeY(f) - 0.05), cost = MINE.minerCost(f, S.floors[f].miners);
      b.style.transform = `translate(${Math.round(p.x)}px, ${Math.round(p.y)}px)`;
      b.hidden = p.y < -40 || p.y > cam.h + 40;
      const nm = b.querySelector('.hn'), hc = b.querySelector('.hc');
      const t1 = `⛏ ${S.floors[f].miners}`, t2 = '+ ' + fmt(cost);
      if (nm.textContent !== t1) nm.textContent = t1; if (hc.textContent !== t2) hc.textContent = t2;
      b.classList.toggle('poor', S.gold < cost);
    });
    floorUi.querySelectorAll('.quit').forEach(q => {
      const f = +q.dataset.f, p = toScreen(X(f, 2.65) + (mir(f) ? -1.25 : 1.25), ledgeY(f) - 0.05);
      q.style.transform = `translate(${Math.round(p.x)}px, ${Math.round(p.y)}px)`;
      q.hidden = !S.floors[f].miners || p.y < -40 || p.y > cam.h + 40;
    });
    const d = $('digBtn');
    if (d) {
      const f = S.floors.length, p = toScreen(COLS / 2, floorTop(f) - FH / 2), cost = MINE.floorCost(f), ok = S.floors[f - 1].boss;
      d.style.transform = `translate(${Math.round(p.x)}px, ${Math.round(p.y)}px)`; d.hidden = p.y < -60 || p.y > cam.h + 60;
      const t1 = T('dig', f + 1) + ' · ' + T(FLOORS[f].ore) + ' · ' + T('hard', FLOORS[f].h), t2 = ok ? fmt(cost) : T('needBoss');
      if (d.querySelector('b').textContent !== t1) d.querySelector('b').textContent = t1;
      if (d.querySelector('span').textContent !== t2) d.querySelector('span').textContent = t2;
      d.classList.toggle('poor', S.gold < cost || !ok); d.disabled = !ok;
    }
  }
  function hireMiner(f) {
    const cost = MINE.minerCost(f, S.floors[f].miners);
    if (S.gold < cost) { toast(T('noGold')); SFX.play('error'); return; }
    S.gold -= cost; S.floors[f].miners++; refreshMiners(f); SFX.play('build');
    particle(X(f, 2.6), walkFeet(f) + 0.6, '#f1c40f', 8, 1.8, 0.4, 0.08); save(); updateHud(true);
  }
  function digFloor() {
    const f = S.floors.length; if (f >= FLOORS.length || !S.floors[f - 1].boss) return;
    const cost = MINE.floorCost(f);
    if (S.gold < cost) { toast(T('noGold')); SFX.play('error'); return; }
    S.gold -= cost; S.floors.push({ miners: 1, towers: {}, boss: false });
    buildFloor(f); refreshLocked(); buildFloorUi(); SFX.play('boom'); shake(0.3);
    particle(COLS / 2, floorTop(f) - 1, ART3.ORES[f % ART3.ORES.length], 30, 3, 0.7, 0.12);
    toast(T('newFloor', f + 1, T(FLOORS[f].ore)), 2.5);
    // a escavação acorda a Abominação, que entra pelo topo e desce
    setTimeout(() => { spawnZombie('boss', f); toast(T('bossFloor'), 3, true); SFX.play('boss'); shake(0.3); }, 3000);
    save();
  }

  // ---------- Entrada ----------
  let drag = null;
  stage.addEventListener('pointerdown', e => {
    if (e.target.closest('#radial') || e.target.closest('#floorUi button')) return;
    drag = { id: e.pointerId, sy: e.clientY, cy: cam.y, moved: false };
    stage.setPointerCapture && stage.setPointerCapture(e.pointerId);
  });
  stage.addEventListener('pointermove', e => {
    if (!drag || drag.id !== e.pointerId) return;
    const dy = e.clientY - drag.sy; if (!drag.moved && Math.abs(dy) > 10) { drag.moved = true; closeRadial(); }
    if (drag.moved) { cam.y = drag.cy + dy / cam.scale; clampCam(); }
  });
  stage.addEventListener('pointerup', e => { if (!drag || drag.id !== e.pointerId) return; const d = drag; drag = null; if (!d.moved) { const r = stage.getBoundingClientRect(); onTap(e.clientX - r.left, e.clientY - r.top); } });
  stage.addEventListener('pointercancel', () => { drag = null; });
  stage.addEventListener('wheel', e => { e.preventDefault(); cam.y -= e.deltaY / cam.scale; clampCam(); closeRadial(); }, { passive: false });

  function floorAt(y) { for (let f = 0; f < S.floors.length; f++) if (y <= floorTop(f) && y > floorTop(f) - FH) return f; return -1; }
  function onTap(sx, sy) {
    SFX.unlock();
    if (paused) return;
    const w = toWorld(sx, sy);
    const wasOpen = !radial.hidden, prev = sel; closeRadial();
    let hitZ = null, hd = 0.7;
    zombies.forEach(e => { if (!e.alive) return; const d = Math.hypot(e.x - w.x, (e.y + e.by) - w.y); if (d < hd) { hd = d; hitZ = e; } });
    if (hitZ) { const dmg = MINE.zombieHp(level()) * 0.2 * (1 + 0.25 * ul('pick')); damage(hitZ, dmg, false); particle(hitZ.x, hitZ.y + hitZ.by, '#8f2f3c', 4, 1.6, 0.3, 0.08); SFX.play('shoot'); shake(0.04); return; }
    const f = floorAt(w.y); if (f < 0) return;
    const c = Math.floor(w.x), si = MINE.slots.findIndex((_, i) => slotCol(f, i) === c);
    if (si >= 0 && w.y > floorTop(f) - 1.05) { if (!(wasOpen && prev && prev.f === f && prev.i === si)) { sel = { f, i: si }; openRadial(); } return; }
    const lx = mir(f) ? COLS - w.x : w.x;
    if (lx >= 1 && lx <= 4) {
      const rt = RT[f], h = FLOORS[f].h; rt.ore += tapPower(); rt.tapNoise = Math.min(rt.tapNoise + 0.35, 6);
      particle(X(f, 1.5), w.y, ART3.ORES[f % ART3.ORES.length], 4, 2.2, 0.35, 0.09); SFX.play('click');
      if (rt.ore >= h) { const n = Math.floor(rt.ore / h); rt.ore -= n * h; const g = n * FLOORS[f].v; S.gold += g; S.total += g; floatText(w.x, w.y + 0.3, '+' + fmt(g), '#f2b84b'); particle(X(f, 1.5), w.y, '#f2b84b', 6, 2.5, 0.4, 0.1); SFX.play('coin'); }
      updateHud(true);
    }
  }

  // ---------- Menu radial das torres ----------
  const radial = $('radial'); let sel = null;
  function closeRadial() { radial.hidden = true; radial.innerHTML = ''; sel = null; }
  function rbtn(html, cost, onClick, cls) {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'rb ' + (cls || '');
    b.innerHTML = html + (cost !== null && cost !== undefined ? `<span class="cost${S.gold < cost ? ' poor' : ''}">${fmt(cost)}</span>` : '');
    b.addEventListener('click', ev => { ev.stopPropagation(); SFX.unlock(); onClick(); });
    return b;
  }
  function openRadial() {
    if (!sel) return; const { f, i } = sel, t = S.floors[f].towers[i], c = slotCol(f, i);
    const refresh = () => { const s2 = sel; radial.innerHTML = ''; sel = s2; openRadial(); };
    const btns = []; let title = '', sub = '';
    if (!t) TOWER_ORDER.forEach(type => {
      if (towerOpen(type)) btns.push(rbtn(`<img src="${ICONS[type]}" alt=""><span class="nm">${T(type)}</span>`, towerCost(type, f), () => { if (buyTower(f, i, type)) closeRadial(); else refresh(); }));
      else btns.push(rbtn(`<img src="${ICONS[type]}" alt="" style="opacity:.35"><span class="nm">${T('towerLocked', MINE.towerUnlock[type])}</span>`, null, () => { toast(T('towerLocked', MINE.towerUnlock[type])); }, 'off'));
    });
    else {
      const s = towerStats(t, f), cost = upCost(t, f);
      title = (t.branch ? T(t.type + '_' + t.branch) : T(t.type)) + ' · ' + T('level', t.lvl); sub = T('stats', fmt(s.dmg), s.range.toFixed(1));
      if (t.lvl === 2 && !t.branch) ['a', 'b'].forEach(br => btns.push(rbtn(`<span class="nm">${T(t.type + '_' + br)}</span>`, cost, () => { upgradeTower(f, i, br); refresh(); }, 'br-' + br)));
      else btns.push(rbtn(`<span class="up">▲</span><span class="nm">${T('upgrade')}</span>`, cost, () => { upgradeTower(f, i); refresh(); }));
      btns.push(rbtn(`<span class="nm">${T('target')}</span><span class="nm b">${T('prio' + t.prio)}</span>`, null, () => { t.prio = (t.prio + 1) % 3; save(); refresh(); }));
      btns.push(rbtn(`<span class="nm">${T('sell')}</span><span class="cost gain">+${fmt(Math.floor(t.spent * 0.5))}</span>`, null, () => { sellTower(f, i); closeRadial(); }, 'sell'));
    }
    radial.innerHTML = '';
    const p = toScreen(c + 0.5, towerFeet(f) + 0.5), R = btns.length === 2 ? 52 : 64;
    const cx = clamp(p.x, 76, cam.w - 76), cy = clamp(p.y, 150, cam.h - 40);
    radial.style.left = cx + 'px'; radial.style.top = cy + 'px';
    btns.forEach((b, k) => { const a = -Math.PI / 2 + (k - (btns.length - 1) / 2) * (btns.length <= 3 ? 1.1 : 0.9); b.style.transform = `translate(${Math.cos(a) * R}px, ${Math.sin(a) * R}px)`; radial.appendChild(b); });
    if (title) { const lab = document.createElement('div'); lab.className = 'rlabel'; lab.innerHTML = '<b></b><span></span>'; lab.querySelector('b').textContent = title; lab.querySelector('span').textContent = sub; lab.style.transform = `translate(-50%, ${-(R + 78)}px)`; radial.appendChild(lab); }
    radial.hidden = false;
  }

  // ---------- HUD, telas ----------
  const ICONS = {};
  TOWER_ORDER.forEach(t => ICONS[t] = ART3.icon('tower', t, 3));
  ICONS.coin = ART.icon('coin', 3); ICONS.ess = ART.icon('ess', 3); ICONS.skull = ART.icon('skull', 3); ICONS.heart = ART.icon('heart', 3);
  document.querySelectorAll('[data-ico]').forEach(el => el.style.backgroundImage = `url(${ICONS[el.dataset.ico]})`);
  let lastHud = '', paused = false;
  function updateHud(force) {
    const rate = totalRate(), key = [Math.floor(S.gold), Math.round(rate * 10), S.floors.length].join('|');
    if (!force && key === lastHud) return; lastHud = key;
    $('gold').textContent = fmt(S.gold); $('rate').textContent = T('perSec', fmt(rate));
    $('depth').textContent = T('floorN', S.floors.length);
  }
  let toastTimer = 0;
  function toast(msg, secs, big) { const t = $('toast'); t.textContent = msg; t.className = 'toast show' + (big ? ' big' : ''); clearTimeout(toastTimer); toastTimer = setTimeout(() => t.className = 'toast', (secs || 1.6) * 1000); }
  function showScreen(id) { document.querySelectorAll('.screen').forEach(s => s.hidden = s.id !== id); paused = !!id; }
  function applyLang() {
    window.LANG = S.lang; document.documentElement.lang = S.lang === 'pt' ? 'pt-BR' : 'en';
    document.querySelectorAll('[data-t]').forEach(el => el.textContent = T(el.dataset.t));
    document.querySelectorAll('.optLang .val').forEach(el => el.textContent = S.lang === 'pt' ? 'PT' : 'EN');
    document.querySelectorAll('.optSfx .val').forEach(el => el.textContent = S.sfx ? T('on') : T('off'));
    document.querySelectorAll('.optMusic .val').forEach(el => el.textContent = S.music ? T('on') : T('off'));
    document.title = T('title'); $('logo').innerHTML = S.lang === 'pt' ? 'ÚLTIMO<span>BUNKER</span>' : 'LAST<span>BUNKER</span>';
    $('btnPlay').textContent = S.total > 0 ? T('continueGame') : T('newGame');
    $('menuGold').textContent = fmt(S.gold); updateHud(true);
    if (!$('scrUpgrades').hidden) renderUpgrades();
  }
  function renderUpgrades() {
    $('upGold').textContent = fmt(S.gold);
    const list = $('upList'); list.innerHTML = '';
    UPGRADES.forEach(u => {
      const lv = ul(u.id), maxed = lv >= u.max, cost = upgradeCost(u, lv);
      const el = document.createElement('div'); el.className = 'tal' + (lv > 0 ? ' has' : '');
      el.innerHTML = '<div class="tinfo"><b></b><p></p><small></small></div><button type="button" class="buy"></button>';
      el.querySelector('b').textContent = T('u_' + u.id); el.querySelector('p').textContent = T('u_' + u.id + '_d'); el.querySelector('small').textContent = `${lv}/${u.max}`;
      const b = el.querySelector('.buy');
      if (maxed) { b.textContent = T('maxed'); b.disabled = true; }
      else { b.innerHTML = `<i class="ico" style="background-image:url(${ICONS.coin})"></i>${fmt(cost)}`; b.disabled = S.gold < cost; }
      b.addEventListener('click', () => { if (S.gold < cost || maxed) return; S.gold -= cost; S.up[u.id] = lv + 1; save(); SFX.play('up'); renderUpgrades(); updateHud(true); });
      list.appendChild(el);
    });
  }
  // Offline: cada andar com mineiros rende conforme as torres que o alcançam (do próprio andar e dos vizinhos)
  function defenseFactor(f) {
    const fl = S.floors[f]; if (!fl.miners) return 1;
    let dps = 0;
    [f - 1, f, f + 1].forEach(g => { if (!S.floors[g]) return; Object.values(S.floors[g].towers).forEach(t => { const s = towerStats(t, g); if (g !== f && s.range < FH) return; dps += s.dmg * s.rate * (t.type === 'tesla' ? 1 + s.chain * 0.5 : t.type === 'mortar' ? 2 : 1) * (g === f ? 1 : 0.5); }); });
    const need = zombieBaseHp() / spawnInterval(totalNoise()) * 1.3;
    return clamp(dps / need, 0.1, 1);
  }
  let started = false;
  function checkOffline() {
    const away = (Date.now() - (S.last || Date.now())) / 3600000;
    if (S.total <= 0 || away < 1 / 60) return;
    const hrs = Math.min(away, 2 + ul('store')); let gain = 0, hurt = false;
    S.floors.forEach((fl, f) => { if (!fl.miners) return; const k = defenseFactor(f); if (k < 0.99) hurt = true; gain += floorRate(f) * k * hrs * 3600; });
    gain = Math.floor(gain); S.last = Date.now(); if (gain < 1) return;
    const h = Math.floor(hrs), m = Math.round((hrs - h) * 60);
    $('offBody').textContent = T('offlineMine', fmt(gain), (h ? h + 'h ' : '') + m + 'min') + (hurt ? T('offlineHurt') : '');
    $('btnCollect').onclick = () => { S.gold += gain; S.total += gain; save(); SFX.unlock(); SFX.play('coin'); showScreen(started ? null : 'scrMenu'); applyLang(); };
    showScreen('scrOffline');
  }

  // Botões
  const on = (id, fn) => $(id).addEventListener('click', () => { SFX.unlock(); fn(); });
  on('btnPlay', () => { SFX.play('click'); started = true; showScreen(null); if (S.total === 0) toast(T('mineHint'), 8); });
  on('btnUp', () => { SFX.play('click'); closeRadial(); renderUpgrades(); showScreen('scrUpgrades'); });
  on('btnUpBack', () => { SFX.play('click'); showScreen(started ? null : 'scrMenu'); applyLang(); });
  on('btnPause', () => { SFX.play('click'); closeRadial(); showScreen('scrPause'); });
  on('btnResume', () => { SFX.play('click'); showScreen(null); });
  on('btnMenuUp', () => { SFX.play('click'); renderUpgrades(); showScreen('scrUpgrades'); });
  on('btnReset', () => { $('confirmText').textContent = T('confirmReset'); showScreen('scrConfirm'); });
  on('btnYes', () => { try { localStorage.removeItem(SAVE_KEY); } catch (e) { } S = fresh(); S.lang = LANG; save(); location.reload(); });
  on('btnNo', () => showScreen('scrPause'));
  on('btnTop', () => { SFX.play('click'); cam.y = 0; clampCam(); });
  document.querySelectorAll('.optLang').forEach(b => b.addEventListener('click', () => { S.lang = S.lang === 'pt' ? 'en' : 'pt'; save(); applyLang(); }));
  document.querySelectorAll('.optSfx').forEach(b => b.addEventListener('click', () => { S.sfx = !S.sfx; SFX.set('sfx', S.sfx); save(); applyLang(); SFX.unlock(); SFX.play('click'); }));
  document.querySelectorAll('.optMusic').forEach(b => b.addEventListener('click', () => { S.music = !S.music; SFX.set('music', S.music); save(); SFX.unlock(); applyLang(); }));
  document.addEventListener('visibilitychange', () => { if (document.hidden) save(); else checkOffline(); });
  window.addEventListener('pagehide', save);
  setInterval(save, 5000);
  window.addEventListener('resize', () => { resize(); closeRadial(); });

  // ---------- Loop ----------
  let lastT = performance.now(), hudT = 0;
  function frame(now) {
    const dt = Math.min(0.05, (now - lastT) / 1000); lastT = now;
    if (!paused) { let left = dt; while (left > 0) { const st = Math.min(left, 1 / 60); update(st); left -= st; } }
    hudT -= dt; if (hudT <= 0) { updateHud(); hudT = 0.15; }
    render(dt);
    requestAnimationFrame(frame);
  }

  // Início
  S.floors.forEach((fl, f) => buildFloor(f)); refreshLocked(); buildFloorUi();
  S.floors.forEach((fl, f) => { if (!fl.boss) setTimeout(() => spawnZombie('boss', f), 3000); });
  resize(); cam.y = 0; clampCam(); applyLang(); showScreen('scrMenu'); checkOffline();
  requestAnimationFrame(frame); setTimeout(resize, 300);
  window.__bunker = { get S() { return S; }, get zombies() { return zombies; }, hireMiner, digFloor, buyTower, upgradeTower, update, toScreen, floorTop, ledgeY, walkFeet, setGold: g => { S.gold = g; } };
})();
