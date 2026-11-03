// Percorre o modo online simulado: apelido, saguão, criar sala, bots, começar, campeonato.
const { chromium } = require('playwright');
const OUT = '/tmp/claude-0/-home-user-teste/ec4e5369-18d0-5a5d-a360-902f9aeb90bb/scratchpad/shots/';

(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 760 }, deviceScaleFactor: 2 });
  const errs = [];
  p.on('pageerror', (e) => errs.push(e.message + '\n' + e.stack));
  await p.goto('file://' + process.cwd() + '/dist/index.html');
  await p.evaluate(() => localStorage.setItem('batida:settings', JSON.stringify({ speed: 'rapido', rv: 4 })));
  await p.reload();
  await p.waitForTimeout(500);
  await p.screenshot({ path: OUT + 'o0-home.png' });
  await p.click('.online-btn');
  await p.waitForTimeout(300);
  await p.fill('#nick', 'Gabriel');
  await p.click('.modal .actions .btn.amber');
  await p.waitForTimeout(1500);
  await p.screenshot({ path: OUT + 'o1-lobby.png' });
  await p.fill('#room-q', 'mesa');
  await p.waitForTimeout(800);
  await p.fill('#room-q', '');
  // criar sala de 4
  await p.click('.lobby-actions .btn');
  await p.waitForTimeout(300);
  await p.screenshot({ path: OUT + 'o2-create.png' });
  await p.click('.modal .actions .btn.amber');
  await p.waitForTimeout(6000);
  await p.screenshot({ path: OUT + 'o3-room.png' });
  await p.click('text=Completar com bots');
  await p.waitForSelector('.room-actions .btn.amber:not([disabled])', { timeout: 20000 });
  await p.click('.room-actions .btn.amber');
  await p.waitForTimeout(6000);
  await p.screenshot({ path: OUT + 'o4-game.png' });
  // sai da partida e volta pro saguão
  await p.click('[aria-label="Sair da mesa"]');
  await p.click('.modal .btn.chili');
  await p.waitForTimeout(1500);
  await p.screenshot({ path: OUT + 'o5-back.png' });
  // campeonato
  await p.click('[aria-label="Voltar"]');
  await p.click('.modal .btn.chili').catch(() => {});
  await p.waitForTimeout(800);
  await p.click('.lobby-tabs button:nth-child(2)');
  await p.waitForTimeout(500);
  await p.click('.lobby-actions .btn');
  await p.waitForTimeout(300);
  await p.click('.modal .actions .btn.amber');
  await p.waitForTimeout(1200);
  await p.screenshot({ path: OUT + 'o6-camp.png' });
  await p.click('text=Completar com bots');
  await p.waitForTimeout(700);
  const st2 = await p.$('.room-actions .btn.amber:not([disabled])');
  if (st2) await st2.click();
  await p.waitForTimeout(1500);
  await p.screenshot({ path: OUT + 'o7-bracket.png' });
  console.log(errs.join('\n') || 'no errors');
  await b.close();
})();
