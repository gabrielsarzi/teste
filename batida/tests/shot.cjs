const { chromium } = require('playwright');
const OUT = '/tmp/claude-0/-home-user-teste/ec4e5369-18d0-5a5d-a360-902f9aeb90bb/scratchpad/shots/';
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 760 }, deviceScaleFactor: 2, hasTouch: true });
  const errs = [];
  p.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  p.on('console', m => m.type() === 'error' && errs.push('CONSOLE ' + m.text()));
  await p.goto('file://' + process.cwd() + '/dist/index.html');
  await p.waitForTimeout(1200);
  await p.screenshot({ path: OUT + '01-home.png' });
  await p.click('.mode-card');
  await p.waitForTimeout(400);
  await p.screenshot({ path: OUT + '02-setup.png' });
  await p.click('.modal .btn.amber');
  await p.waitForTimeout(1500);
  await p.screenshot({ path: OUT + '03-classic.png' });
  // play ~12 human turns
  for (let i = 0; i < 40; i++) {
    if (await p.$('.modal.result')) break;
    const t = await p.$('.hand:not(.locked) .tile.can');
    if (t) {
      await t.click();
      await p.waitForTimeout(200);
      const tg = await p.$('.target');
      if (tg) await tg.click();
    }
    await p.waitForTimeout(700);
    if (i === 6) await p.screenshot({ path: OUT + '04-classic-mid.png' });
  }
  await p.waitForTimeout(800);
  await p.screenshot({ path: OUT + '05-classic-late.png' });
  console.log(errs.join('\n') || 'no errors');
  await b.close();
})();
