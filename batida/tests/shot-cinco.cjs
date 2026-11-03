const { chromium } = require('playwright');
const OUT = '/tmp/claude-0/-home-user-teste/ec4e5369-18d0-5a5d-a360-902f9aeb90bb/scratchpad/shots/';
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 760 }, deviceScaleFactor: 2 });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + process.cwd() + '/dist/index.html'); await p.waitForTimeout(600);
  await p.evaluate(() => { globalThis.__forceCincoBuchas = 2; });
  await p.click('.mode-card'); await p.waitForTimeout(300);
  await p.click('.modal .btn.amber'); await p.waitForTimeout(900);
  await p.screenshot({ path: OUT + 'c1-shuffle.png' });
  await p.waitForTimeout(2200);
  await p.screenshot({ path: OUT + 'c2-volta.png' });
  await p.click('.modal .btn.amber'); await p.waitForTimeout(3500);
  await p.screenshot({ path: OUT + 'c3-dealt.png' });
  console.log(errs.join('\n') || 'no errors'); await b.close();
})();
