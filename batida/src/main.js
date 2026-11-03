import { initFx } from './ui/fx.js';
import { unlockAudio } from './ui/audio.js';
import { applySettings, registerScreen, go } from './app.js';
import { homeScreen } from './screens/home.js';
import { classicScreen } from './screens/classic.js';
import { careerScreen } from './screens/career.js';
import { lookScreen } from './screens/look.js';

registerScreen('home', homeScreen);
registerScreen('classic', classicScreen);
registerScreen('career', careerScreen);
registerScreen('look', lookScreen);

function boot() {
  const app = document.getElementById('app');
  applySettings();
  initFx(app);
  const unlock = () => unlockAudio();
  addEventListener('pointerdown', unlock, { passive: true });
  addEventListener('keydown', unlock);
  go('home');
}

boot();
