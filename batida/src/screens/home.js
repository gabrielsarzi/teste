import { h, modal } from '../ui/dom.js';
import { tileEl } from '../ui/tileView.js';
import { makeTile } from '../core/tiles.js';
import { settings, saveSettings, go, career, stats } from '../app.js';
import { CAMPEONATOS } from '../classic/cast.js';
import { sfx } from '../ui/audio.js';

export const ICONS = {
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',
  gear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/></svg>',
  help: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7"/><circle cx="12" cy="17" r=".6" fill="currentColor"/></svg>',
  paint: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="3" y="4" width="8" height="16" rx="2"/><path d="M7 8.5v.01M7 15.5v.01"/><path d="M14 6h6v12h-6z"/><path d="M14 12h6"/></svg>',
  bag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M5 8h14l-1.2 12H6.2z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/></svg>',
};

export function iconBtn(name, label, onClick) {
  return h('button', { class: 'icon-btn', 'aria-label': label, title: label, html: ICONS[name], onClick });
}

export function homeScreen(stage) {
  stage.classList.add('home');
  const st = stats();
  const car = career();
  const camp = CAMPEONATOS[Math.min(car.level, CAMPEONATOS.length - 1)];

  const deco = h('div', { class: 'home-tiles', 'aria-hidden': 'true' });
  const spots = [
    [6, 6, -96, -36, 0], [6, 3, -40, -46, 8], [3, 3, 8, -34, 0], [3, 1, 64, -50, 14], [5, 0, 104, -20, -12],
  ];
  spots.forEach(([a, b, x, y, r], i) => {
    const t = tileEl(makeTile(a, b), { top: a, bot: b, u: 30 });
    t.style.transform = `translate(${x - 15}px, ${y - 30}px) rotate(${r}deg)`;
    t.style.animation = `dealIn .5s ${0.15 + i * 0.08}s cubic-bezier(.3,.7,.4,1.2) both`;
    deco.append(t);
  });

  const art = (pairs) => {
    const wrap = h('div', { class: 'mc-art' });
    pairs.forEach(([a, b, x, y, r]) => {
      const t = tileEl(makeTile(a, b), { top: a, bot: b, u: 24 });
      t.style.cssText += `left:${x}px;top:${y}px;transform:rotate(${r}deg)`;
      wrap.append(t);
    });
    return wrap;
  };

  const done = car.level >= CAMPEONATOS.length;
  const cards = h(
    'div',
    { class: 'mode-cards' },
    h(
      'button',
      { class: 'mode-card', onClick: () => quickSetup() },
      art([[6, 6, 2, 4, -8], [1, 6, 24, 10, 10]]),
      h('div', {}, h('div', { class: 'mc-title' }, 'Jogo rápido'), h('div', { class: 'mc-sub' }, 'Uma partida de dupla, do jeito do bar.')),
      h('span', { class: 'mc-go', 'aria-hidden': 'true' }, '›'),
    ),
    h(
      'button',
      { class: 'mode-card career', onClick: () => go('career') },
      art([[5, 5, 2, 6, -10], [2, 4, 24, 2, 12]]),
      h(
        'div',
        {},
        h('div', { class: 'mc-title' }, 'Carreira'),
        h('div', { class: 'mc-sub' }, done ? 'Campeão do Brasileirão! Jogue de novo os campeonatos.' : `${car.level + 1}º de ${CAMPEONATOS.length}: ${camp.short}`),
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
      h('span', { class: 'chip-stat' }, 'Vitórias ', h('b', {}, String(st.quickWins))),
      h('span', { class: 'chip-stat' }, 'Títulos ', h('b', {}, String(car.titles.length))),
    ),
    h(
      'div',
      { style: { display: 'flex', gap: '8px' } },
      iconBtn('paint', 'Mesas e dominós', () => go('look')),
      iconBtn('help', 'Como jogar', () => rulesModal()),
      iconBtn('gear', 'Configurações', () => settingsModal()),
    ),
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
    sw('set-ajuda', 'Ajuda nas pedras', 'Destaca as pedras da sua mão que encaixam', 'ajuda'),
    sw('set-contagem', 'Contagem da mesa', 'Mostra quantas pedras de cada número já saíram e onde cada um passou', 'contagem'),
    sw('set-conversa', 'Conversa na mesa', 'Provocações, comentários e o botão de frases', 'conversa'),
    h(
      'div',
      { class: 'toggle-row' },
      h('div', {}, h('div', { class: 't' }, 'Ritmo da mesa'), h('div', { class: 'd' }, 'Quanto tempo os outros levam para jogar')),
      seg([['lento', 'Calmo'], ['normal', 'Normal'], ['rapido', 'Rápido']], settings.speed, (v) => {
        settings.speed = v;
        saveSettings();
      }),
    ),
    h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: (e) => e.target.closest('.modal-back').click() }, 'Fechar')),
  ]);
}

function quickSetup() {
  const m = modal([
    h('h2', {}, 'Jogo rápido'),
    h('p', {}, 'Você e o Rafa contra a dupla dos lados. 7 pedras para cada um, sem compra. Quem tem jogo, joga.'),
    h(
      'div',
      { class: 'toggle-row' },
      h('div', {}, h('div', { class: 't' }, 'Adversários')),
      seg([['facil', 'Fácil'], ['medio', 'Médio'], ['dificil', 'Difícil']], settings.nivel, (v) => {
        settings.nivel = v;
        saveSettings();
      }),
    ),
    sw('r-bucha', 'Batida de bucha vale 2', 'Bater com uma bucha conta dois pontos', 'buchaVale2'),
    sw('r-laelo', 'Lá-e-lô vale 2', 'Bater com pedra que entra nos dois lados', 'laeloVale2'),
    sw('r-cinco', '5 buchas volta o jogo', 'Quem recebe 5 buchas ou mais mostra a mão e embaralha de novo', 'cincoBuchas'),
    sw('r-sena', 'Começa com a sena', 'Na 1ª rodada, quem tem a bucha de sena sai com ela', 'comecaSena'),
    h(
      'div',
      { class: 'actions' },
      h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Voltar'),
      h('button', { class: 'btn amber', onClick: () => { m.close(); go('classic'); } }, 'Sentar à mesa'),
    ),
  ]);
}

export function rulesModal() {
  modal([
    h('h2', {}, 'Como jogar'),
    h('h3', {}, 'A mesa'),
    h('ul', {}, h('li', {}, 'Duas duplas: você e o parceiro de cima contra os dois dos lados.'), h('li', {}, 'Cada um recebe 7 pedras. A vez anda para a direita.'), h('li', {}, 'Encaixe uma pedra numa das duas pontas com o mesmo número.')),
    h('h3', {}, 'Regras da casa'),
    h('ul', {}, h('li', {}, 'Quem tem pedra que encaixa é obrigado a jogar. Só passa quem não tem jogo.'), h('li', {}, 'Bater (acabar as pedras) vale 1 ponto. Bater com bucha vale 2, e bater com pedra que entra nos dois lados (lá-e-lô) também vale 2. Dá para desligar as duas.'), h('li', {}, 'Dá para fechar o jogo de propósito: quando ninguém mais consegue jogar, vence a dupla com menos pontos na mão.'), h('li', {}, 'Quem recebe 5 buchas ou mais na mão: volta o jogo, embaralha e distribui de novo.'), h('li', {}, 'A partida vai até alguém fazer 4 pontos: a cruz da lousa completa. A saída vai rodando entre os jogadores, e na primeira rodada sai a bucha de sena.')),
    h('h3', {}, 'Contagem'),
    h('p', {}, 'Ligue em Configurações. Cada número mostra quantas pedras dele já estão na mesa (de 7) e quantas ainda estão com os outros. Embaixo do nome de cada jogador aparece em que números ele já passou.'),
    h('h3', {}, 'Carreira'),
    h('ul', {}, h('li', {}, 'Seis campeonatos, do boteco do bairro até o Brasileirão. Todos os jogos vão até 4 pontos.'), h('li', {}, 'Cada um tem quartas, semi e final. Perdeu, recomeça o campeonato.'), h('li', {}, 'Cada título libera mesas e dominós novos.')),
    h('div', { class: 'actions' }, h('button', { class: 'btn amber', onClick: (e) => e.target.closest('.modal-back').click() }, 'Entendi')),
  ]);
}
