const { chromium } = require('playwright');
const OUT = '/tmp/claude-0/-home-user-teste/ec4e5369-18d0-5a5d-a360-902f9aeb90bb/scratchpad/shots/';
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 760 }, deviceScaleFactor: 2 });
  await p.goto('file://' + process.cwd() + '/dist/index.html');
  await p.evaluate(() => localStorage.setItem('batida:settings', JSON.stringify({ speed: 'rapido', rv: 3 })));
  await p.reload(); await p.waitForTimeout(500);
  await p.click('.mode-card'); await p.waitForTimeout(300); await p.click('.modal .btn.amber');
  for (let i = 0; i < 400; i++) {
    const res = await p.$('.modal.result .btn.amber');
    if (res) { const txt = await res.textContent(); if (txt.includes('Ver resultado')) { await res.click(); await p.waitForTimeout(600); break; } await res.click(); await p.waitForTimeout(600); await p.screenshot({ path: OUT + 'd1-cruz.png', clip: { x: 0, y: 0, width: 390, height: 90 } }); continue; }
    const tiles = await p.$$('.hand.my-turn .tile');
    for (const t of tiles) { await t.click().catch(()=>{}); await p.waitForTimeout(60); const tg = await p.$('.target'); if (tg) { await tg.click(); break; } if (!(await p.$('.hand.my-turn'))) break; }
    await p.waitForTimeout(300);
  }
  await p.screenshot({ path: OUT + 'd2-end.png' });
  await b.close();
})();
