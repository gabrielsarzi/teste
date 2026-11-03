// Gera os ícones do app Android (pedra de dominó num fundo âmbar) com o Chromium.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const RES = path.join(__dirname, '..', 'android', 'app', 'src', 'main', 'res');
const DENS = { mdpi: 1, hdpi: 1.5, xhdpi: 2, xxhdpi: 3, xxxhdpi: 4 };

// pedra 6·6 inclinada; "full" desenha o fundo, "fg" só a pedra (ícone adaptativo)
function html(size, mode) {
  const pip = (cx, cy) => `<circle cx="${cx}" cy="${cy}" r="5.2" fill="#1a120d"/>`;
  const six = (oy) => [16, 30, 44].flatMap((y) => [pip(25, y + oy), pip(55, y + oy)]).join('');
  const tile = `<g transform="translate(50 50) rotate(-14) translate(-40 -60)">
    <rect x="0" y="4" width="80" height="120" rx="12" fill="#b5a283"/>
    <rect x="0" y="0" width="80" height="120" rx="12" fill="#f4eddc"/>
    <rect x="10" y="59" width="60" height="2.5" fill="#6b5442" opacity=".55"/>
    <circle cx="40" cy="60" r="4.5" fill="#c6953e"/>
    <g transform="translate(-0 -0)">${six(0)}</g>
    <g transform="translate(0 60)">${six(0)}</g>
  </g>`;
  const scale = mode === 'fg' ? 0.5 : 0.64;
  const bg = mode === 'fg' ? '' : `<rect width="100" height="100" rx="${mode === 'round' ? 50 : 22}" fill="url(#g)"/>`;
  return `<html><body style="margin:0;background:transparent"><svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 100 100">
    <defs><radialGradient id="g" cx="50%" cy="35%" r="75%"><stop offset="0" stop-color="#ffd27a"/><stop offset="1" stop-color="#e08a1e"/></radialGradient></defs>
    ${bg}
    <g transform="translate(50 50) scale(${scale}) translate(-50 -50)">${tile}</g>
  </svg></body></html>`;
}

(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  async function shot(size, mode, file) {
    await p.setViewportSize({ width: size, height: size });
    await p.setContent(html(size, mode));
    await p.screenshot({ path: file, omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } });
  }
  for (const [d, k] of Object.entries(DENS)) {
    const dir = path.join(RES, `mipmap-${d}`);
    fs.mkdirSync(dir, { recursive: true });
    await shot(Math.round(48 * k), 'full', path.join(dir, 'ic_launcher.png'));
    await shot(Math.round(48 * k), 'round', path.join(dir, 'ic_launcher_round.png'));
    await shot(Math.round(108 * k), 'fg', path.join(dir, 'ic_launcher_foreground.png'));
  }
  await shot(512, 'full', path.join(__dirname, '..', 'dist', 'icon-512.png'));
  await b.close();
  console.log('ícones gerados');
})();
