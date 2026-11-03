import { initFx } from './ui/fx.js';
import { unlockAudio } from './ui/audio.js';
import { woodTexture } from './ui/art.js';
import { applySettings, registerScreen, go } from './app.js';
import { homeScreen } from './screens/home.js';
import { classicScreen } from './screens/classic.js';
import { viradaScreen } from './screens/virada.js';

registerScreen('home', homeScreen);
registerScreen('classic', classicScreen);
registerScreen('virada', viradaScreen);

function boot() {
  applySettings();
  const app = document.getElementById('app');
  try {
    app.style.setProperty('--wood-img', `url(${woodTexture(512, 512)})`);
  } catch {
    /* sem canvas */
  }
  initFx(app);
  const unlock = () => unlockAudio();
  addEventListener('pointerdown', unlock, { passive: true });
  addEventListener('keydown', unlock);
  go('home');
}

boot();
