import { h, modal, store, toast } from '../ui/dom.js';
import { tileEl } from '../ui/tileView.js';
import { makeTile } from '../core/tiles.js';
import { settings, saveSettings, go, career, stats, wallet, setWallet, money, owned } from '../app.js';
import { CAMPEONATOS, MESAS_VISUAL, DOMINOS_VISUAL, DESAFIO_OPPS, CAST } from '../classic/cast.js';
import { sfx } from '../ui/audio.js';
import { track, pendingRewards, getStats } from '../progress.js';
import { confetti } from '../ui/fx.js';
import { showRewarded } from '../ads.js';
import { STATIONS } from '../ui/music.js';

export const ICONS = {
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',
  gear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/></svg>',
  help: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7"/><circle cx="12" cy="17" r=".6" fill="currentColor"/></svg>',
  paint: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="3" y="4" width="8" height="16" rx="2"/><path d="M7 8.5v.01M7 15.5v.01"/><path d="M14 6h6v12h-6z"/><path d="M14 12h6"/></svg>',
  bag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M5 8h14l-1.2 12H6.2z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/></svg>',
  trophy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M7 6H4a3 3 0 0 0 3 4M17 6h3a3 3 0 0 1-3 4M12 14v4M8 20h8"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/></svg>',
  coin: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.5" fill="#f2c14e" stroke="#9a6a14" stroke-width="1.6"/><circle cx="12" cy="12" r="6.2" fill="none" stroke="#b9801c" stroke-width="1.3"/><path d="M12 8.3v7.4M10 10.2c0-1 1-1.5 2-1.5s2 .5 2 1.4-1 1.3-2 1.6-2 .7-2 1.6 1 1.4 2 1.4 2-.5 2-1.5" stroke="#7a4f0c" stroke-width="1.3" fill="none" stroke-linecap="round"/></svg>',
};

export function iconBtn(name, label, onClick) {
  return h('button', { class: 'icon-btn', 'aria-label': label, title: label, html: ICONS[name], onClick });
}

export function walletChip(onClick) {
  return h(
    'button',
    { class: 'wallet', 'aria-label': 'Sua carteira', onClick },
    h('span', { class: 'coin', html: ICONS.coin }),
    h('b', { 'data-wallet': '' }, money(wallet())),
  );
}

const today = () => {
  const d = new Date();
  return d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate();
};

export function homeScreen(stage) {
  stage.classList.add('home');
  const st = stats();
  const car = career();
  const done = car.level >= CAMPEONATOS.length;
  const camp = CAMPEONATOS[Math.min(car.level, CAMPEONATOS.length - 1)];
  const desafio = store.get('desafio', {});
  const desafioFeito = desafio.date === today();

  // ---------- capa: título sob a luz e uma mão de dominó aberta em leque ----------
  const hero = h(
    'div',
    { class: 'hero' },
    h('div', { class: 'lamp-glow', 'aria-hidden': 'true' }),
    h('h1', { class: 'brand' }, 'Batida', h('span', { class: 'dot' }, '!')),
    h('p', { class: 'brand-sub' }, 'dominó de boteco'),
  );
  const fan = h('div', { class: 'fan', 'aria-hidden': 'true' });
  const hand = [[6, 6], [6, 4], [5, 3], [4, 4], [3, 1], [2, 0], [1, 1]];
  hand.forEach(([a, b], i) => {
    const ang = (i - 3) * 9;
    const t = tileEl(makeTile(a, b), { top: a, bot: b, u: 40 });
    t.style.setProperty('--ang', `${ang}deg`);
    t.style.setProperty('--lift', `${Math.abs(i - 3) * 2}px`);
    t.style.animationDelay = `${0.1 + i * 0.06}s`;
    fan.append(t);
  });

  const top = h(
    'div',
    { class: 'home-top' },
    h('div', { class: 'home-stats' }, h('span', { html: ICONS.trophy }), `${car.titles.length} título${car.titles.length === 1 ? '' : 's'}`, h('span', { class: 'sep' }), `${getStats().vitorias} vitória${getStats().vitorias === 1 ? '' : 's'}`),
    walletChip(() => walletModal()),
  );

  const play = h('button', { class: 'play-btn', onClick: () => quickSetup() }, h('span', {}, 'Jogar'), h('small', {}, 'Jogo rápido · 2, 3 ou 4 na mesa'));
  const online = h(
    'button',
    { class: 'online-btn', onClick: () => go('online') },
    h('span', { class: 'live-dot', 'aria-hidden': 'true' }),
    h('span', { class: 'ob-t' }, 'Online'),
    h('span', { class: 'ob-s' }, 'Salas, jogo rápido e campeonato'),
    h('span', { class: 'mc-go', 'aria-hidden': 'true' }, '›'),
  );

  const careerCard = h(
    'button',
    { class: 'tile-card career', onClick: () => go('career') },
    h('div', { class: 'tc-ico', html: ICONS.trophy }),
    h('div', { class: 'tc-body' }, h('div', { class: 'tc-title' }, 'Carreira'), h('div', { class: 'tc-sub' }, done ? 'Campeão do Brasileirão!' : camp.short), h('div', { class: 'tc-meta' }, done ? 'Jogue de novo' : `Inscrição ${money(camp.fee)}`)),
  );
  const oppId = DESAFIO_OPPS[new Date().getDay()];
  const desafioCard = h(
    'button',
    { class: `tile-card desafio ${desafioFeito ? 'feito' : ''}`, onClick: () => (desafioFeito ? toast('Desafio de hoje já foi. Volta amanhã!') : startDesafio(oppId)) },
    h('div', { class: 'tc-ico', html: ICONS.star }),
    h('div', { class: 'tc-body' }, h('div', { class: 'tc-title' }, 'Desafio do dia'), h('div', { class: 'tc-sub' }, desafioFeito ? (desafio.won ? 'Vencido hoje' : 'Volta amanhã') : `Mano a mano com ${CAST[oppId].name}`), h('div', { class: 'tc-meta' }, desafioFeito ? '' : 'Vale R$ 100')),
  );

  const foot = h(
    'div',
    { class: 'home-foot' },
    h('button', { class: 'foot-btn', onClick: () => go('look') }, h('span', { html: ICONS.bag }), 'Loja'),
    h('button', { class: 'foot-btn', onClick: () => go('progresso') }, h('span', { html: ICONS.star }), 'Missões', pendingRewards() ? h('i', { class: 'dot-badge', 'aria-label': 'Prêmios para recolher' }) : null),
    h('button', { class: 'foot-btn', onClick: () => rulesModal() }, h('span', { html: ICONS.help }), 'Regras'),
    h('button', { class: 'foot-btn', onClick: () => settingsModal() }, h('span', { html: ICONS.gear }), 'Ajustes'),
  );

  stage.append(top, hero, fan, h('div', { class: 'home-actions' }, play, online, h('div', { class: 'tile-cards' }, careerCard, desafioCard), foot));
  if (wallet() < 10) setTimeout(() => fiadoModal(), 500);
}

// ---------- carteira e fiado ----------
export function walletModal() {
  const m = modal([
    h('h2', {}, 'Carteira'),
    h('div', { class: 'big', style: { color: 'var(--amber-hi)' } }, money(wallet())),
    h('p', {}, 'Ganhe dinheiro em mesas valendo no jogo rápido, vencendo campeonatos e no desafio do dia. Gaste na loja, nas inscrições e contratando parceiros.'),
    wallet() < 10 ? h('button', { class: 'btn chili wide', onClick: () => { m.close(); fiadoModal(); } }, 'Pendurar no fiado') : null,
    h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Fechar')),
  ]);
}

const videoHoje = () => store.get('fiadoVideo', 0) === today();

export function fiadoModal() {
  const m = modal(
    [
      h('div', { class: 'eyebrow' }, 'Tá liso?'),
      h('h2', {}, 'Pendura no fiado!'),
      h('p', { class: 'quote' }, '“Tranquilo, depois você acerta. Só não some, hein!”', h('span', {}, ' · Zezão, dono do boteco')),
      h('div', { class: 'big', style: { color: 'var(--good)' } }, '+R$ 50'),
      videoHoje() ? null : h('button', { class: 'btn blue wide', style: { marginTop: '12px' }, onClick: async (e) => {
        e.currentTarget.disabled = true;
        if (await showRewarded()) {
          store.set('fiadoVideo', today());
          setWallet(wallet() + 100);
          sfx.coins();
          m.close();
          toast('Fiado + vídeo: +R$ 100');
        }
      } }, 'Ver um vídeo e pegar R$ 100'),
      h('div', { class: 'actions' }, h('button', { class: 'btn amber wide', onClick: () => { setWallet(wallet() + 50); sfx.coins(); m.close(); } }, 'Valeu, Zezão')),
    ],
    { cls: 'result' },
  );
}

// ---------- desafio do dia ----------
function startDesafio(oppId) {
  go('classic', {
    mode: 'desafio',
    players: 2,
    opps: [oppId],
    seed: today(),
    rules: { players: 2, metaPontos: 1, buchaVale2: true, laeloVale2: true, comecaSena: true, cincoBuchas: true, votacao: true },
    onEnd: (won) => {
      store.set('desafio', { date: today(), won });
      track('desafio', { won });
      if (won) setWallet(wallet() + 100);
      go('home');
      setTimeout(() => {
        if (won) {
          confetti(120);
          sfx.coins();
          toast('Desafio vencido! +R$ 100');
        } else toast('Não foi dessa vez. Amanhã tem outro desafio.');
      }, 300);
    },
  });
}

// ---------- controles ----------
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

export function seg(options, value, onPick) {
  const wrap = h('div', { class: 'seg', role: 'group' });
  for (const [v, label, disabled] of options) {
    const b = h('button', { class: v === value ? 'on' : '', 'aria-pressed': String(v === value), disabled: !!disabled }, label);
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

function row(title, desc, control) {
  return h('div', { class: 'toggle-row' }, h('div', {}, h('div', { class: 't' }, title), desc ? h('div', { class: 'd' }, desc) : null), control);
}

export function settingsModal() {
  modal([
    h('h2', {}, 'Ajustes'),
    h('h3', {}, 'Mesa'),
    sw('set-ajuda', 'Ajuda nas pedras', 'Destaca as pedras da sua mão que encaixam', 'ajuda'),
    sw('set-contagem', 'Contagem da mesa', 'Quantas pedras de cada número já saíram e onde cada um passou', 'contagem'),
    sw('set-limpa', 'Tela limpa', 'Esconde os textos de pontas e de quem é a vez', 'telaLimpa'),
    sw('set-conversa', 'Conversa na mesa', 'Provocações, comentários e o botão de frases', 'conversa'),
    row('Tempo para jogar', 'Depois da metade, o adversário cobra', seg([[30, '30 s'], [60, '60 s'], [0, 'Livre']], settings.tempo, (v) => { settings.tempo = v; saveSettings(); })),
    row('Ritmo da mesa', 'Quanto tempo os outros levam para jogar', seg([['lento', 'Calmo'], ['normal', 'Normal'], ['rapido', 'Rápido']], settings.speed, (v) => { settings.speed = v; saveSettings(); })),
    h('h3', {}, 'Pedras'),
    row('Tamanho', 'Pedras grandes deixam a mesa e a mão com mais zoom', seg([['normal', 'Normal'], ['grande', 'Grande']], settings.pedras, (v) => { settings.pedras = v; saveSettings(); })),
    sw('set-num', 'Números nas pedras', 'Troca as pintas por números. Bom para vista cansada e daltônicos', 'numeros'),
    h('h3', {}, 'Som'),
    sw('set-sound', 'Som e vibração', null, 'sound'),
    sw('set-musica', 'Rádio', 'Música de fundo. Na mesa, toque no radinho para trocar', 'musica'),
    row('Estação', null, seg(STATIONS.map((s) => [s.id, s.name.split(' ')[0]]), settings.radio, (v) => { settings.radio = v; settings.musica = true; saveSettings(); })),
    sw('set-bar', 'Sons do bar', 'Copos, talheres, cadeiras e pedras de outras mesas, de vez em quando', 'somBar'),
    h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: (e) => e.target.closest('.modal-back').click() }, 'Fechar')),
  ]);
}

function lookPicker(kind) {
  const list = kind === 'mesa' ? MESAS_VISUAL : DOMINOS_VISUAL;
  const have = owned(kind);
  return seg(
    list.filter((x) => have.includes(x.id)).map((x) => [x.id, x.name.split(' ')[0]]),
    settings[kind],
    (v) => {
      settings[kind] = v;
      saveSettings();
    },
  );
}

function quickSetup() {
  const w = wallet();
  const bets = [0, 10, 20, 50, 100, 200];
  if (!bets.includes(settings.aposta) || settings.aposta > w) settings.aposta = bets.filter((b) => b <= w).pop() || 0;
  const goBtn = h('button', { class: 'btn amber' });
  const label = () => (goBtn.textContent = settings.aposta ? `Sentar · ${money(settings.aposta)}` : 'Sentar à mesa');
  label();
  const m = modal([
    h('h2', {}, 'Jogo rápido'),
    row('Na mesa', settings.jogadores === 4 ? 'Dupla: você e o Rafa contra dois' : 'Cada um por si, com compra no monte', seg([[2, '2'], [3, '3'], [4, '4 (dupla)']], settings.jogadores, (v) => {
      settings.jogadores = v;
      saveSettings();
      m.el.querySelector('.toggle-row .d').textContent = v === 4 ? 'Dupla: você e o Rafa contra dois' : 'Cada um por si, com compra no monte';
    })),
    row('Adversários', null, seg([['facil', 'Fácil'], ['medio', 'Médio'], ['dificil', 'Difícil']], settings.nivel, (v) => { settings.nivel = v; saveSettings(); })),
    row('Valendo', `Na carteira: ${money(w)}`, seg(bets.map((b) => [b, b ? `R$${b}` : 'Nada', b > w]), settings.aposta, (v) => { settings.aposta = v; saveSettings(); label(); })),
    row('Mesa', null, lookPicker('mesa')),
    row('Dominó', null, lookPicker('domino')),
    h(
      'details',
      { class: 'rules-box' },
      h('summary', {}, 'Regras da casa'),
      sw('r-bucha', 'Batida de bucha vale 2', null, 'buchaVale2'),
      sw('r-laelo', 'Lá-e-lô vale 2', 'Bater com pedra que entra nos dois lados', 'laeloVale2'),
      sw('r-cinco', '5 buchas volta o jogo', 'Quem recebe 5 buchas ou mais mostra e embaralha de novo', 'cincoBuchas'),
      sw('r-sena', 'Começa com a maior bucha', 'Na 1ª rodada sai a sena (ou a maior bucha na mesa)', 'comecaSena'),
    ),
    h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Voltar'), goBtn),
  ]);
  goBtn.addEventListener('click', () => {
    m.close();
    go('classic', { players: settings.jogadores, stake: settings.aposta });
  });
}

export function rulesModal() {
  modal([
    h('h2', {}, 'Como jogar'),
    h('h3', {}, 'A mesa'),
    h('ul', {}, h('li', {}, 'Com 4: duas duplas, você e o parceiro de cima contra os dois dos lados. 7 pedras para cada, sem compra.'), h('li', {}, 'Com 2 ou 3: cada um por si, 7 pedras para cada e o resto fica no monte. Sem jogo, compra até achar.'), h('li', {}, 'A vez anda para a direita. Encaixe uma pedra numa das pontas com o mesmo número.')),
    h('h3', {}, 'Regras da casa'),
    h('ul', {}, h('li', {}, 'Quem tem pedra que encaixa é obrigado a jogar. Tocar numa pedra que não entra é gato.'), h('li', {}, 'Bater vale 1 ponto. Bater com bucha vale 2, e com pedra que entra nos dois lados (lá-e-lô) também vale 2.'), h('li', {}, 'Jogo fechado: ninguém consegue jogar e vence quem tem menos pontos na mão. Se a pedra fechou de propósito mas cabia na outra ponta, a mesa vota se fecha ou abre. No empate, abre.'), h('li', {}, '5 buchas ou mais na mão: volta o jogo.'), h('li', {}, 'A partida vai até 4 pontos: cada ponto é uma bolinha numa ponta da cruz da lousa. A bolinha dourada no meio marca quem sai na rodada.')),
    h('h3', {}, 'Dinheiro'),
    h('ul', {}, h('li', {}, 'No jogo rápido a mesa pode valer dinheiro do jogo. Ganhou, cada adversário paga o valor.'), h('li', {}, 'Campeonato tem inscrição e prêmio em dinheiro, além de mesas e dominós.'), h('li', {}, 'Ficou liso? O Zezão pendura no fiado.')),
    h('h3', {}, 'Créditos'),
    h('p', {}, 'Rádio: “Pagode de Viola No 1”, Projeto Música Artesanal (CC BY-SA 3.0); “Choro da Banda”, Coelho de Moraes (CC BY 3.0); “Mecha Bossa”, Pequenas Alegrias (CC BY 2.5 BR). Todas via Jamendo/Internet Archive.'),
    h('h3', {}, 'Contagem'),
    h('p', {}, 'Ligue em Ajustes. Cada número mostra quantas pedras dele já estão na mesa (de 7) e quantas ainda estão com os outros. Embaixo do nome de cada jogador aparece em que números ele já passou.'),
    h('div', { class: 'actions' }, h('button', { class: 'btn amber', onClick: (e) => e.target.closest('.modal-back').click() }, 'Entendi')),
  ]);
}
