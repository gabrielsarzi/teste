// Ranking, frases na sala e anti-abandono no online simulado.
const { chromium } = require('playwright');
const OUT = '/tmp/claude-0/-home-user-teste/ec4e5369-18d0-5a5d-a360-902f9aeb90bb/scratchpad/shots/';

(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 760 }, deviceScaleFactor: 2 });
  const errs = [];
  p.on('pageerror', (e) => errs.push(e.message + '\n' + e.stack));
  await p.goto('file://' + process.cwd() + '/dist/index.html');
  await p.evaluate(() => {
    localStorage.setItem('batida:settings', JSON.stringify({ speed: 'rapido', rv: 4 }));
    localStorage.setItem('batida:nick', JSON.stringify('Gabriel'));
    localStorage.setItem('batida:rank', JSON.stringify({ week: new Date().toISOString().slice(0, 10), pts: 120 }));
  });
  await p.reload();
  await p.waitForTimeout(400);
  await p.click('.online-btn');
  await p.waitForTimeout(1500);
  await p.screenshot({ path: OUT + 'r0-prize.png' });
  const bora = await p.$('.modal .btn.amber');
  if (bora) await bora.click();
  await p.waitForTimeout(400);
  await p.screenshot({ path: OUT + 'r0-lobby.png' });
  await p.click('.rank-btn');
  await p.waitForTimeout(1200);
  await p.screenshot({ path: OUT + 'r1-ranking.png' });
  await p.click('[aria-label="Voltar"]');
  await p.waitForTimeout(800);
  // sala valendo R$20
  await p.click('.lobby-actions .btn');
  await p.waitForTimeout(300);
  await p.click('.modal .seg >> nth=1 >> text=R$20');
  await p.click('.modal .actions .btn.amber');
  await p.waitForTimeout(1200);
  await p.click('.chip-btn');
  await p.waitForTimeout(3000);
  await p.screenshot({ path: OUT + 'r2-room.png' });
  await p.click('text=Completar com bots');
  await p.waitForSelector('.room-actions .btn.amber:not([disabled])', { timeout: 20000 });
  await p.click('.room-actions .btn.amber');
  await p.waitForTimeout(4000);
  await p.click('[aria-label="Sair da mesa"]');
  await p.waitForTimeout(300);
  await p.screenshot({ path: OUT + 'r3-quit.png' });
  await p.click('.modal .btn.chili');
  await p.waitForTimeout(1500);
  await p.screenshot({ path: OUT + 'r4-after.png' });
  const pen = await p.evaluate(() => localStorage.getItem('batida:penalty'));
  console.log('penalidade gravada:', !!pen, errs.join('\n') || 'no errors');
  await b.close();
})();
