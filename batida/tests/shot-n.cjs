// Joga partidas de 2, 3 ou 4 jogadores no navegador e tira prints.
// Uso: node tests/shot-n.cjs 3
const { chromium } = require('playwright');
const OUT = '/tmp/claude-0/-home-user-teste/ec4e5369-18d0-5a5d-a360-902f9aeb90bb/scratchpad/shots/';
const N = Number(process.argv[2]) || 3;

(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 760 }, deviceScaleFactor: 2 });
  const errs = [];
  p.on('pageerror', (e) => errs.push(e.message + '\n' + e.stack));
  await p.goto('file://' + process.cwd() + '/dist/index.html');
  await p.evaluate((n) => localStorage.setItem('batida:settings', JSON.stringify({ speed: 'rapido', rv: 3, jogadores: n, contagem: true })), N);
  await p.reload();
  await p.waitForTimeout(500);
  await p.click('.play-btn');
  await p.waitForTimeout(300);
  await p.click('.modal .actions .btn.amber');
  let shots = 0;
  let mid = false;
  let rounds = 0;
  const t0 = Date.now();
  while (Date.now() - t0 < 80000) {
    const res = await p.$('.modal.result .actions .btn.amber');
    const vote = await p.$('.modal .vote-list');
    if (vote) {
      await p.screenshot({ path: OUT + `n${N}-vote.png` });
      const yb = await p.$('.modal .actions .btn.amber');
      if (yb) await yb.click();
      await p.waitForTimeout(800);
      continue;
    }
    if (res) {
      if (shots < 2) await p.screenshot({ path: OUT + `n${N}-res${shots++}.png` });
      const txt = await res.textContent();
      await res.click();
      rounds++;
      await p.waitForTimeout(500);
      if (txt.includes('Ver resultado') || rounds > 3) break;
      continue;
    }
    const db = await p.$('.draw-btn:not([hidden])');
    if (db) {
      await db.click();
      await p.waitForTimeout(400);
      continue;
    }
    const tiles = await p.$$('.hand.my-turn .tile');
    for (const t of tiles) {
      await t.click().catch(() => {});
      await p.waitForTimeout(60);
      const tg = await p.$('.target');
      if (tg) {
        await tg.click().catch(() => {});
        break;
      }
      if (!(await p.$('.hand.my-turn'))) break;
    }
    await p.waitForTimeout(300);
    if (!mid && Date.now() - t0 > 14000) {
      mid = true;
      await p.screenshot({ path: OUT + `n${N}-mid.png` });
    }
  }
  await p.screenshot({ path: OUT + `n${N}-end.png` });
  console.log('rounds', rounds, errs.join('\n') || 'no errors');
  await b.close();
})();
