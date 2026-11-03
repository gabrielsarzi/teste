// Anúncios.
// No app (Android) usa o AdMob; por enquanto com os IDs de TESTE do Google
// (trocar pelos IDs da sua conta AdMob antes de publicar — ver ADS_IDS abaixo).
// No navegador, mostra um "anúncio de teste" simulado, para dar para testar o fluxo.
import { h } from './ui/dom.js';
import { settings, saveSettings } from './app.js';
import { store } from './ui/dom.js';

export const ADS_IDS = {
  // IDs de teste oficiais do Google. Os de verdade vêm do painel do AdMob.
  rewarded: 'ca-app-pub-3940256099942544/5224354917',
  interstitial: 'ca-app-pub-3940256099942544/1033173712',
};

const INTERSTITIAL_EVERY = 3; // um anúncio a cada 3 partidas terminadas
const FIRST_FREE = 2; // as 2 primeiras partidas de quem acabou de instalar não têm anúncio

function admob() {
  const C = window.Capacitor;
  return C && C.isNativePlatform && C.isNativePlatform() && C.Plugins && C.Plugins.AdMob ? C.Plugins.AdMob : null;
}

let ready = false;
async function init() {
  const A = admob();
  if (!A || ready) return A;
  try {
    await A.initialize({ initializeForTesting: true });
    ready = true;
  } catch {
    return null;
  }
  return A;
}

export const adsRemoved = () => !!settings.semAnuncios;

// Vídeo premiado: devolve true se a pessoa assistiu até o fim.
export async function showRewarded() {
  const A = await init();
  if (A) {
    try {
      await A.prepareRewardVideoAd({ adId: ADS_IDS.rewarded, isTesting: true });
      const reward = await A.showRewardVideoAd();
      return !!reward;
    } catch {
      return false;
    }
  }
  return fakeAd({ rewarded: true });
}

// Entre partidas (nunca durante o jogo). Não aparece para quem tirou os anúncios.
export async function maybeInterstitial() {
  if (adsRemoved()) return;
  const n = store.get('adCount', 0) + 1;
  store.set('adCount', n);
  if (n <= FIRST_FREE || n % INTERSTITIAL_EVERY !== 0) return;
  const A = await init();
  if (A) {
    try {
      await A.prepareInterstitial({ adId: ADS_IDS.interstitial, isTesting: true });
      await A.showInterstitial();
    } catch {
      /* sem anúncio disponível: segue o jogo */
    }
    return;
  }
  await fakeAd({ rewarded: false });
}

// "Remover anúncios": compra única. A cobrança de verdade (Google Play Billing) entra
// na versão da loja; aqui fica o fluxo pronto.
export function buyRemoveAds() {
  const C = window.Capacitor;
  const billing = C && C.Plugins && C.Plugins.Billing;
  if (!billing) return Promise.resolve({ ok: false, reason: 'loja' });
  return billing
    .purchase({ productId: 'remover_anuncios' })
    .then(() => {
      settings.semAnuncios = true;
      saveSettings();
      return { ok: true };
    })
    .catch(() => ({ ok: false, reason: 'cancelado' }));
}

// Anúncio simulado (navegador): tela escura com contagem, deixa claro que é teste.
function fakeAd({ rewarded }) {
  return new Promise((resolve) => {
    const secs = rewarded ? 5 : 4;
    let left = secs;
    const count = h('b', {}, String(left));
    const close = h('button', { class: 'btn ghost small', disabled: true }, 'Fechar');
    const box = h(
      'div',
      { class: 'fake-ad', role: 'dialog', 'aria-label': 'Anúncio de teste' },
      h('div', { class: 'fa-card' }, h('small', {}, 'ANÚNCIO DE TESTE'), h('div', { class: 'fa-title' }, 'Aqui vai aparecer um anúncio'), h('p', {}, rewarded ? 'Assista até o fim para ganhar o prêmio.' : 'Anúncio entre partidas.'), h('div', { class: 'fa-count' }, count, ' s'), close),
    );
    document.getElementById('app').append(box);
    const t = setInterval(() => {
      left--;
      count.textContent = String(Math.max(0, left));
      if (left <= 0) {
        clearInterval(t);
        close.disabled = false;
        close.textContent = rewarded ? 'Pegar prêmio' : 'Fechar';
      }
    }, 1000);
    close.addEventListener('click', () => {
      box.remove();
      resolve(true);
    });
  });
}
