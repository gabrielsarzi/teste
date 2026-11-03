const { chromium } = require('playwright');
const OUT = '/tmp/claude-0/-home-user-teste/ec4e5369-18d0-5a5d-a360-902f9aeb90bb/scratchpad/shots/';
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 760 }, deviceScaleFactor: 2, hasTouch: true });
  const errs = [];
  p.on('pageerror', e => errs.push('PAGEERR ' + e.message + e.stack));
  p.on('console', m => m.type() === 'error' && errs.push('CONSOLE ' + m.text()));
  await p.goto('file://' + process.cwd() + '/dist/index.html');
  await p.waitForTimeout(800);
  await p.click('.mode-card.virada');
  await p.waitForTimeout(700);
  await p.screenshot({ path: OUT + '10-rules.png' });
  await p.click('.modal .btn.amber');
  await p.waitForTimeout(400);
  await p.screenshot({ path: OUT + '11-map.png' });
  let shots = 0;
  for (let mesaN = 0; mesaN < 4; mesaN++) {
    await p.click('.actions-start, .btn.amber');
    await p.waitForTimeout(900);
    if (mesaN === 0) await p.screenshot({ path: OUT + '12-mesa.png' });
    for (let j = 0; j < 12; j++) {
      if (await p.$('.modal.result') || !(await p.$('.v-actions'))) break;
      for (let k = 0; k < 4; k++) {
        const t = await p.$('.hand:not(.locked) .tile.can');
        if (!t) break;
        await t.click(); await p.waitForTimeout(150);
        const tg = await p.$('.target'); if (tg) { await tg.click(); }
        await p.waitForTimeout(450);
      }
      if (mesaN === 0 && j === 0) await p.screenshot({ path: OUT + '13-pending.png' });
      const btn = await p.$('.v-actions .btn.amber:not([disabled]), .v-actions .btn.blue:not([disabled])');
      if (btn) { await btn.click(); }
      else { const tr = await p.$('.v-actions .btn.chili:not([disabled])'); if (tr) { await tr.click(); await p.waitForTimeout(100); for (let q=0;q<3;q++) await p.locator('.hand .tile').nth(q).click(); await p.click('.v-actions .btn.chili'); } }
      await p.waitForTimeout(mesaN === 0 && j === 0 ? 1300 : 300);
      if (mesaN === 0 && j === 0) await p.screenshot({ path: OUT + '14-scoring.png' });
      await p.waitForTimeout(2600);
    }
    await p.screenshot({ path: OUT + `15-end-${mesaN}.png` });
    const rec = await p.$('.modal.result .btn.amber');
    if (!rec) break;
    await rec.click(); await p.waitForTimeout(600);
    await p.screenshot({ path: OUT + `16-shop-${mesaN}.png` });
    const buy = await p.$('.item .btn.amber:not([disabled])'); if (buy) { await buy.click(); await p.waitForTimeout(400); const ok = await p.$('.modal .item'); if (ok) await ok.click(); }
    await p.waitForTimeout(300);
    await p.click('#stage > div:last-of-type .btn.amber');
    await p.waitForTimeout(500);
  }
  await p.screenshot({ path: OUT + '17-final.png' });
  console.log(errs.join('\n') || 'no errors');
  await b.close();
})();
