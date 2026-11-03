import { initFx } from './ui/fx.js';
import { unlockAudio, setAmbient, sfx, haptic } from './ui/audio.js';
import { applySettings, registerScreen, go, settings, updateMusic } from './app.js';
import { homeScreen } from './screens/home.js';
import { classicScreen } from './screens/classic.js';
import { careerScreen } from './screens/career.js';
import { lookScreen } from './screens/look.js';
import { onlineScreen } from './screens/online.js';
import { progressoScreen } from './screens/progresso.js';

registerScreen('home', homeScreen);
registerScreen('classic', classicScreen);
registerScreen('career', careerScreen);
registerScreen('look', lookScreen);
registerScreen('online', onlineScreen);
registerScreen('progresso', progressoScreen);

function boot() {
  const app = document.getElementById('app');
  applySettings();
  initFx(app);
  const unlock = () => {
    unlockAudio();
    setAmbient(settings.sound && settings.somBar);
    updateMusic();
  };
  addEventListener('pointerdown', unlock, { passive: true });
  // som em todo botão do menu (a mão e a mesa têm os sons próprios)
  addEventListener(
    'click',
    (e) => {
      const b = e.target.closest('button');
      if (!b || b.disabled || b.closest('.hand, .seg, .switch, .board')) return;
      const label = b.getAttribute('aria-label') || '';
      if (/^(Voltar|Sair da mesa|Campeonatos)/.test(label)) sfx.uiBack();
      else if (b.matches('.play-btn, .online-btn, .btn.amber, .btn.chili, .btn.blue')) sfx.uiPrimary();
      else sfx.uiTap();
      haptic(6);
    },
    true,
  );
  addEventListener('keydown', unlock);
  go('home');
}

boot();
