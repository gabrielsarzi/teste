import { h, modal, store, fmt } from '../ui/dom.js';
import { tileEl } from '../ui/tileView.js';
import { makeTile } from '../core/tiles.js';
import { settings, saveSettings, go } from '../app.js';
import { sfx } from '../ui/audio.js';

export const ICONS = {
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',
  gear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/></svg>',
  help: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7"/><circle cx="12" cy="17" r=".6" fill="currentColor"/></svg>',
  bag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M5 8h14l-1.2 12H6.2z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/></svg>',
};

export function iconBtn(name, label, onClick) {
  return h('button', { class: 'icon-btn', 'aria-label': label, title: label, html: ICONS[name], onClick });
}

export function homeScreen(stage) {
  stage.classList.add('home');
  const stats = store.get('stats', { classicWins: 0, classicPlayed: 0, viradaBest: 0, viradaWins: 0 });
  const run = store.get('run', null);

  const deco = h('div', { class: 'home-tiles', 'aria-hidden': 'true' });
  const spots = [
    [6, 6, -96, -40, -18], [6, 3, -40, -46, 8], [3, 3, 8, -30, 90], [3, 1, 64, -50, 14], [5, 0, 104, -20, -12],
  ];
  spots.forEach(([a, b, x, y, r], i) => {
    const t = tileEl(makeTile(a, b), { top: a, bot: b, u: 30 });
    t.style.transform = `translate(${x - 15}px, ${y - 30}px) rotate(${r}deg)`;
    t.style.animation = `dealIn .5s ${0.15 + i * 0.08}s cubic-bezier(.3,.7,.4,1.2) both`;
    deco.append(t);
  });

  const artClassic = h('div', { class: 'mc-art' });
  const t1 = tileEl(makeTile(6, 6), { u: 24 });
  t1.style.cssText += 'left:2px;top:4px;transform:rotate(-8deg)';
  const t2 = tileEl(makeTile(1, 6), { top: 6, bot: 1, u: 24 });
  t2.style.cssText += 'left:24px;top:10px;transform:rotate(10deg)';
  artClassic.append(t1, t2);

  const artVirada = h('div', { class: 'mc-art' });
  const v1 = tileEl(makeTile(5, 5, { mod: 'ouro' }), { u: 24 });
  v1.style.cssText += 'left:2px;top:6px;transform:rotate(-10deg)';
  const v2 = tileEl(makeTile(2, 4, { mod: 'brasa' }), { top: 4, bot: 2, u: 24 });
  v2.style.cssText += 'left:24px;top:2px;transform:rotate(12deg)';
  artVirada.append(v1, v2);

  const cards = h(
    'div',
    { class: 'mode-cards' },
    h(
      'button',
      { class: 'mode-card', onClick: () => classicSetup() },
      artClassic,
      h('div', {}, h('div', { class: 'mc-title' }, 'Clássico'), h('div', { class: 'mc-sub' }, 'Dominó de dupla, do jeito do bar. Você e seu parceiro contra a mesa.')),
      h('span', { class: 'mc-go', 'aria-hidden': 'true' }, '›'),
    ),
    h(
      'button',
      { class: 'mode-card virada', onClick: () => go('virada', { resume: !!run }) },
      artVirada,
      h(
        'div',
        {},
        h('div', { class: 'mc-title' }, 'Virada'),
        h('div', { class: 'mc-sub' }, run ? `Continuar: Boteco ${run.ante} de 8, $${run.money}` : 'Monte correntes, junte parceiros e vire 8 botecos de ponta-cabeça.'),
      ),
      h('span', { class: 'mc-go', 'aria-hidden': 'true' }, '›'),
    ),
  );

  const foot = h(
    'div',
    { class: 'home-foot' },
    h(
      'div',
      { style: { display: 'flex', gap: '14px', flexWrap: 'wrap' } },
      h('span', { class: 'chip-stat' }, 'Vitórias ', h('b', {}, String(stats.classicWins))),
      h('span', { class: 'chip-stat' }, 'Recorde Virada ', h('b', {}, fmt(stats.viradaBest || 0))),
    ),
    h('div', { style: { display: 'flex', gap: '8px' } }, iconBtn('help', 'Como jogar', () => rulesModal()), iconBtn('gear', 'Configurações', () => settingsModal())),
  );

  stage.append(
    h('div', { class: 'sign' }, h('div', { class: 'lamp' }), h('h1', {}, 'Batida', h('span', { class: 'dot' }, '!')), h('p', {}, 'dominó de boteco')),
    deco,
    h('div', {}, cards, foot),
  );
}

function sw(id, label, desc, key, obj = settings, onChange) {
  const input = h('input', { type: 'checkbox', id, role: 'switch' });
  input.checked = !!obj[key];
  input.addEventListener('change', () => {
    obj[key] = input.checked;
    sfx.pick();
    onChange ? onChange() : saveSettings();
  });
  return h(
    'div',
    { class: 'toggle-row' },
    h('label', { for: id }, h('div', { class: 't' }, label), desc && h('div', { class: 'd' }, desc)),
    h('span', { class: 'switch' }, input, h('span')),
  );
}

function seg(options, value, onPick) {
  const wrap = h('div', { class: 'seg', role: 'group' });
  for (const [v, label] of options) {
    const b = h('button', { class: v === value ? 'on' : '', 'aria-pressed': String(v === value) }, label);
    b.addEventListener('click', () => {
      wrap.querySelectorAll('button').forEach((x) => {
        x.classList.remove('on');
        x.setAttribute('aria-pressed', 'false');
      });
      b.classList.add('on');
      b.setAttribute('aria-pressed', 'true');
      sfx.pick();
      onPick(v);
    });
    wrap.append(b);
  }
  return wrap;
}

export function settingsModal() {
  modal([
    h('h2', {}, 'Configurações'),
    sw('set-sound', 'Som e vibração', null, 'sound'),
    h(
      'div',
      { class: 'toggle-row' },
      h('div', {}, h('div', { class: 't' }, 'Velocidade dos outros'), h('div', { class: 'd' }, 'Quanto tempo a mesa leva para jogar')),
      seg([['normal', 'Normal'], ['rapido', 'Rápida']], settings.speed, (v) => {
        settings.speed = v;
        saveSettings();
      }),
    ),
    h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: (e) => e.target.closest('.modal-back').click() }, 'Fechar')),
  ]);
}

function classicSetup() {
  const m = modal([
    h('h2', {}, 'Mesa clássica'),
    h('p', {}, 'Você joga com o parceiro de cima contra a dupla dos lados. 7 pedras para cada um, sem compra. Quem tem jogo, joga.'),
    h(
      'div',
      { class: 'toggle-row' },
      h('div', {}, h('div', { class: 't' }, 'Formato'), h('div', { class: 'd' }, settings.formato === 'pontos' ? 'Até 6 pontos' : '4 rodadas, cada um começa uma')),
      seg([['rodadas', '4 rodadas'], ['pontos', 'Até 6']], settings.formato, (v) => {
        settings.formato = v;
        saveSettings();
        m.el.querySelector('.toggle-row .d').textContent = v === 'pontos' ? 'Até 6 pontos' : '4 rodadas, cada um começa uma';
      }),
    ),
    sw('r-bucha', 'Batida de bucha vale 2', 'Bater com uma bucha conta dois pontos', 'buchaVale2'),
    sw('r-laelo', 'Lá-e-lô vale 2', 'Bater com pedra que serve nas duas pontas', 'laeloVale2'),
    sw('r-sena', 'Começa com a sena', 'Na 1ª rodada, quem tem a bucha de sena sai com ela', 'comecaSena'),
    h(
      'div',
      { class: 'actions' },
      h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Voltar'),
      h('button', { class: 'btn amber', onClick: () => { m.close(); go('classic'); } }, 'Sentar à mesa'),
    ),
  ]);
}

export function rulesModal(tab = 'classico') {
  const body = h('div');
  const render = (t) => {
    body.innerHTML = '';
    if (t === 'classico') {
      body.append(
        h('h3', {}, 'A mesa'),
        h('ul', {}, h('li', {}, 'Duas duplas: você e o parceiro de cima contra os dois dos lados.'), h('li', {}, 'Cada um recebe 7 pedras. A vez anda para a direita.'), h('li', {}, 'Encaixe uma pedra numa das duas pontas com o mesmo número.')),
        h('h3', {}, 'Regras da casa'),
        h('ul', {}, h('li', {}, 'Quem tem pedra que encaixa é obrigado a jogar. Só passa quem não tem jogo.'), h('li', {}, 'Bater (acabar as pedras) vale 1 ponto. Bater com bucha vale 2 (dá para desligar).'), h('li', {}, 'Dá para fechar o jogo de propósito: quando ninguém mais consegue jogar, vence a dupla com menos pontos na mão.'), h('li', {}, 'São 4 rodadas e cada jogador começa uma. Na primeira, sai a bucha de sena.')),
      );
    } else {
      body.append(
        h('h3', {}, 'O objetivo'),
        h('p', {}, 'Faça os pontos da meta de cada mesa antes de acabarem suas jogadas. São 3 mesas por boteco e 8 botecos. A terceira mesa é do dono, que muda as regras.'),
        h('h3', {}, 'Como jogar'),
        h('ul', {}, h('li', {}, 'Toque nas pedras da mão para encaixar até 5 numa jogada. Depois toque em Jogar.'), h('li', {}, 'A mesa continua de uma jogada para outra. Pense nas pontas que vai deixar.'), h('li', {}, 'Trocar descarta pedras marcadas e compra outras.')),
        h('h3', {}, 'Pontos'),
        h('ul', {}, h('li', {}, 'Pontos = base do jogo + soma das pedras. O total é Pontos × Mult.'), h('li', {}, 'Jogos: Encaixe, Parelha, Corrente, Buchada, Trem, Naipe, Expresso e Naipe Real.'), h('li', {}, 'Lá e Lô: se as duas pontas ficarem iguais depois da jogada, ×1,5 Mult.')),
        h('h3', {}, 'No balcão'),
        h('ul', {}, h('li', {}, 'Parceiros dão bônus permanentes. Cabem 5.'), h('li', {}, 'Bebidas sobem o nível de um jogo. Simpatias benzem pedras do seu saco.'), h('li', {}, 'Juros: $1 a cada $5 guardados, até $5 por mesa.')),
      );
    }
  };
  const tabs = h(
    'div',
    { class: 'rules-tabs' },
    seg([['classico', 'Clássico'], ['virada', 'Virada']], tab, (v) => render(v)),
  );
  render(tab);
  modal([h('h2', {}, 'Como jogar'), tabs, body, h('div', { class: 'actions' }, h('button', { class: 'btn amber', onClick: (e) => e.target.closest('.modal-back').click() }, 'Entendi'))]);
}
