const { chromium } = require('playwright');
const OUT = '/tmp/claude-0/-home-user-teste/ec4e5369-18d0-5a5d-a360-902f9aeb90bb/scratchpad/shots/';
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 760 }, deviceScaleFactor: 2, hasTouch: true });
  const errs = [];
  p.on('pageerror', e => errs.push('PAGEERR ' + e.message));
  p.on('console', m => m.type() === 'error' && errs.push('CONSOLE ' + m.text()));
  await p.goto('file://' + process.cwd() + '/dist/index.html');
  await p.evaluate(() => { localStorage.setItem('batida:settings', JSON.stringify({ speed: 'rapido', contagem: true, rv: 2, laeloVale2: true })); });
  await p.reload(); await p.waitForTimeout(1000);
  await p.screenshot({ path: OUT + 'a1-home.png' });
  await p.click('.mode-card.career'); await p.waitForTimeout(500);
  await p.screenshot({ path: OUT + 'a2-bracket.png' });
  await p.click('.career-actions .btn'); await p.waitForTimeout(3500);
  await p.screenshot({ path: OUT + 'a3-game.png' });
  await p.click('.chat-btn'); await p.waitForTimeout(300); await p.screenshot({ path: OUT + 'a3b-chat.png' });
  await p.click('.phrase'); await p.waitForTimeout(1500); await p.screenshot({ path: OUT + 'a3c-react.png' });
  let broncaShot = false;
  for (let i = 0; i < 160; i++) {
    const res = await p.$('.modal.result .btn.amber');
    if (res) { await p.screenshot({ path: OUT + `a5-result.png` }); await res.click(); await p.waitForTimeout(800); if (!(await p.$('.hand'))) break; continue; }
    const mine = await p.$('.hand.my-turn');
    if (mine) {
      const tiles = await p.$$('.hand.my-turn .tile');
      if (!broncaShot && tiles.length > 2) { // try tapping all until a bronca appears
        for (const t of tiles) { await t.click().catch(()=>{}); await p.waitForTimeout(120); if (await p.$('.bubble.bronca')) { await p.screenshot({ path: OUT + 'a4-bronca.png' }); broncaShot = true; break; } if (!(await p.$('.hand.my-turn'))) break; }
      } else {
        for (const t of tiles) { await t.click().catch(()=>{}); await p.waitForTimeout(100); const tg = await p.$('.target'); if (tg) { await tg.click(); break; } if (!(await p.$('.hand.my-turn'))) break; }
      }
    }
    await p.waitForTimeout(400);
    if (i === 60) await p.screenshot({ path: OUT + 'a6-mid.png' });
  }
  await p.waitForTimeout(500);
  await p.screenshot({ path: OUT + 'a7-after.png' });
  await p.goto('file://' + process.cwd() + '/dist/index.html'); await p.waitForTimeout(600);
  await p.click('[aria-label="Mesas e dominós"]'); await p.waitForTimeout(500);
  await p.screenshot({ path: OUT + 'a8-look.png', fullPage: true });
  console.log(errs.join('\n') || 'no errors');
  await b.close();
})();
