// Gera os prints da Play Store (1080x1920) e o gráfico de destaque (1024x500).
// Uso: node tests/store-assets.cjs
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUT = path.join(__dirname, '..', 'store', 'prints');
fs.mkdirSync(OUT, { recursive: true });
const URL = 'file://' + path.join(__dirname, '..', 'dist', 'index.html');

async function page(b, settings = {}, extra = {}) {
  const p = await b.newPage({ viewport: { width: 360, height: 640 }, deviceScaleFactor: 3 });
  await p.goto(URL);
  await p.evaluate(([s, e]) => {
    localStorage.clear();
    localStorage.setItem('batida:settings', JSON.stringify({ rv: 4, speed: 'rapido', tempo: 0, ...s }));
    for (const [k, v] of Object.entries(e)) localStorage.setItem('batida:' + k, JSON.stringify(v));
  }, [settings, extra]);
  await p.reload();
  await p.waitForTimeout(1600);
  return p;
}

// joga sozinho até a mesa ter umas pedras
async function playSome(p, moves = 4) {
  let done = 0;
  for (let i = 0; i < 200 && done < moves; i++) {
    const tiles = await p.$$('.hand.my-turn .tile');
    for (const t of tiles) {
      await t.click().catch(() => {});
      await p.waitForTimeout(50);
      const tg = await p.$('.target');
      if (tg) await tg.click().catch(() => {});
      if (!(await p.$('.hand.my-turn'))) {
        done++;
        break;
      }
    }
    if (await p.$('.modal.result')) break;
    await p.waitForTimeout(120);
  }
}

(async () => {
  const b = await chromium.launch();

  // 1. capa
  let p = await page(b, {}, { wallet: 1250, stats3: { vitorias: 42 } });
  await p.screenshot({ path: path.join(OUT, '01-inicio.png') });
  await p.close();

  // 2. mesa de dupla no meio do jogo
  p = await page(b, { jogadores: 4, aposta: 50, contagem: true }, { wallet: 1250 });
  await p.click('.play-btn');
  await p.waitForTimeout(300);
  await p.click('.modal .actions .btn.amber');
  await playSome(p, 4);
  await p.waitForTimeout(400);
  await p.screenshot({ path: path.join(OUT, '02-mesa.png') });
  await p.close();

  // 3. mesa de feltro, mano a mano com compra
  p = await page(b, { jogadores: 2, aposta: 0, mesa: 'feltro', domino: 'colorido' }, { wallet: 800, bought: { mesa: ['feltro'], domino: ['colorido'] } });
  await p.click('.play-btn');
  await p.waitForTimeout(300);
  await p.click('.modal .actions .btn.amber');
  await playSome(p, 5);
  await p.waitForTimeout(400);
  await p.screenshot({ path: path.join(OUT, '03-mano-a-mano.png') });
  await p.close();

  // 4. carreira
  p = await page(b, {}, { wallet: 600 });
  await p.click('.tile-card.career');
  await p.waitForTimeout(600);
  await p.screenshot({ path: path.join(OUT, '04-carreira.png') });
  await p.close();

  // 5. online
  p = await page(b, {}, { wallet: 600, nick: 'Gabriel' });
  await p.click('.online-btn');
  await p.waitForTimeout(2200);
  const bora = await p.$('.modal .btn.amber');
  if (bora) await bora.click();
  await p.waitForTimeout(300);
  await p.screenshot({ path: path.join(OUT, '05-online.png') });
  await p.close();

  // 6. loja
  p = await page(b, {}, { wallet: 2300 });
  await p.click('.foot-btn');
  await p.waitForTimeout(700);
  await p.screenshot({ path: path.join(OUT, '06-loja.png') });
  await p.close();

  // gráfico de destaque 1024x500
  p = await b.newPage({ viewport: { width: 1024, height: 500 }, deviceScaleFactor: 1 });
  await p.goto(URL);
  await p.waitForTimeout(1200);
  await p.evaluate(() => {
    const app = document.getElementById('app');
    app.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.style.cssText = 'position:absolute;inset:0;display:grid;grid-template-columns:1.1fr 1fr;align-items:center;padding:0 60px;gap:20px;';
    wrap.innerHTML = `<div><h1 class="brand" style="font-size:118px;text-align:left;margin:0">Batida<span class="dot">!</span></h1>
      <p class="brand-sub" style="text-align:left;font-size:40px;margin-top:22px">dominó de boteco</p>
      <p style="font:700 22px var(--f-body);color:#e9dcc4;margin-top:22px;max-width:440px;line-height:1.35">Dupla, mano a mano, carreira de campeonatos e mesa online.</p></div>`;
    const fan = document.createElement('div');
    fan.className = 'fan feature';
    fan.style.cssText = 'height:300px;';
    wrap.append(fan);
    app.append(wrap);
    const hands = [[6, 6], [6, 4], [5, 3], [4, 4], [3, 1], [2, 0], [1, 1]];
    hands.forEach(([a, bb], i) => {
      const t = document.createElement('div');
      t.className = 'tile';
      t.style.setProperty('--u', '54px', 'important');
      t.style.setProperty('--ang', `${(i - 3) * 9}deg`);
      t.style.setProperty('--lift', `${Math.abs(i - 3) * 3}px`);
      t.style.setProperty('margin', '-54px 0 0 -27px', 'important');
      t.style.animation = 'none';
      const PIPS = { 0: [], 1: ['c'], 2: ['tl', 'br'], 3: ['tl', 'c', 'br'], 4: ['tl', 'tr', 'bl', 'br'], 5: ['tl', 'tr', 'c', 'bl', 'br'], 6: ['tl', 'tr', 'ml', 'mr', 'bl', 'br'] };
      const half = (v, pos) => `<div class="half ${pos} n${v}">${PIPS[v].map((q) => `<i class="pip ${q}"></i>`).join('')}</div>`;
      t.innerHTML = half(a, 'top') + half(bb, 'bot') + '<span class="rivet"></span>';
      fan.append(t);
    });
  });
  await p.waitForTimeout(300);
  await p.screenshot({ path: path.join(__dirname, '..', 'store', 'destaque-1024x500.png') });
  await p.close();

  await b.close();
  fs.copyFileSync(path.join(__dirname, '..', 'dist', 'icon-512.png'), path.join(__dirname, '..', 'store', 'icone-512.png'));
  console.log('prints e destaque gerados');
})();
