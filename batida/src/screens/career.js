import { h, modal } from '../ui/dom.js';
import { tileEl } from '../ui/tileView.js';
import { makeTile } from '../core/tiles.js';
import { sfx } from '../ui/audio.js';
import { confetti } from '../ui/fx.js';
import { go, career, saveCareer, settings, saveSettings } from '../app.js';
import { CAST, CAMPEONATOS, FASES, MESAS_VISUAL, DOMINOS_VISUAL } from '../classic/cast.js';
import { iconBtn } from './home.js';

const PARTNER = 'rafa';

function stars(dupla) {
  const lv = dupla.reduce((s, id) => s + (CAST[id].master ? 0.9 + CAST[id].master / 100 : CAST[id].skill), 0) / 2;
  const n = Math.max(1, Math.min(5, Math.round(lv * 5)));
  return h('span', { class: 'stars', 'aria-label': `Dificuldade ${n} de 5` }, '★'.repeat(n), h('span', { class: 'off' }, '★'.repeat(5 - n)));
}

function vsBadge(label) {
  return h('div', { class: 'vs-badge' }, label);
}

function prizeText(prize) {
  const parts = [];
  if (prize.mesa) {
    const n = MESAS_VISUAL.find((m) => m.id === prize.mesa).name;
    parts.push(n.startsWith('Mesa') ? n : `mesa ${n}`);
  }
  if (prize.domino) parts.push(`dominó ${DOMINOS_VISUAL.find((d) => d.id === prize.domino).name}`);
  return parts.join(' e ');
}

export function careerScreen(stage, params = {}) {
  const car = career();
  stage.classList.add('career');

  const showList = () => {
    stage.innerHTML = '';
    stage.append(
      h(
        'div',
        { class: 'topbar' },
        iconBtn('back', 'Voltar', () => go('home')),
        h('div', { class: 'grow' }, h('div', { class: 'eyebrow' }, `${car.titles.length} de ${CAMPEONATOS.length} títulos`), h('div', { class: 'title-sm' }, 'Carreira')),
      ),
    );
    const list = h('div', { class: 'ladder' });
    CAMPEONATOS.forEach((c, i) => {
      const won = car.titles.includes(c.id);
      const locked = i > car.level;
      const now = i === Math.min(car.level, CAMPEONATOS.length - 1) && !won;
      const active = car.active && car.active.id === c.id && car.active.fase > 0;
      const card = h(
        'button',
        { class: `camp ${won ? 'won' : ''} ${locked ? 'locked' : ''} ${now ? 'now' : ''}`, disabled: locked, onClick: () => showBracket(c) },
        h('div', { class: 'camp-num', html: won ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M7 6H4a3 3 0 0 0 3 4M17 6h3a3 3 0 0 1-3 4M12 14v4M8 20h8"/></svg>' : locked ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>' : String(i + 1) }),
        h(
          'div',
          { class: 'camp-body' },
          h('div', { class: 'camp-name' }, c.name),
          h('div', { class: 'camp-sub' }, locked ? `Vença o ${CAMPEONATOS[i - 1].short} para liberar` : active ? `Em andamento: ${FASES[car.active.fase]}` : c.place),
          h('div', { class: 'camp-prize' }, `Prêmio: ${prizeText(c.prize)}`),
        ),
        h('div', { class: 'camp-final' }, h('small', {}, 'final'), `${CAST[c.duplas[2][0]].name.split(' ').pop()} e ${CAST[c.duplas[2][1]].name.split(' ').pop()}`),
      );
      list.append(card);
    });
    stage.append(list);
  };

  const showBracket = (c) => {
    if (!car.active || car.active.id !== c.id) {
      car.active = { id: c.id, fase: 0 };
      saveCareer(car);
    }
    const fase = car.active.fase;
    stage.innerHTML = '';
    stage.append(
      h(
        'div',
        { class: 'topbar' },
        iconBtn('back', 'Campeonatos', () => showList()),
        h('div', { class: 'grow' }, h('div', { class: 'eyebrow' }, c.place), h('div', { class: 'title-sm' }, c.name)),
      ),
    );
    const fmt = c.format.formato === 'pontos' ? `Jogos até ${c.format.metaPontos} pontos` : 'Jogos de 4 rodadas';
    const box = h('div', { class: 'bracket' });
    box.append(
      h(
        'div',
        { class: 'us-pair' },
        vsBadge('Nós'),
        h('div', {}, h('div', { class: 'pair-name' }, `Você e ${CAST[PARTNER].name}`), h('div', { class: 'camp-sub' }, fmt)),
        h('span'),
      ),
    );
    c.duplas.forEach((d, i) => {
      const st = i < fase ? 'done' : i === fase ? 'next' : 'later';
      box.append(
        h(
          'div',
          { class: `match-row ${st}` },
          h('div', { class: 'fase' }, FASES[i]),
          h(
            'div',
            { class: 'opp' },
            vsBadge(String(i + 1)),
            h('div', { class: 'opp-names' }, h('b', {}, `${CAST[d[0]].name} e ${CAST[d[1]].name}`), stars(d)),
            h('div', { class: 'state' }, st === 'done' ? '✓' : st === 'next' ? 'Próximo' : ''),
          ),
        ),
      );
    });
    box.append(h('div', { class: 'camp-prize center' }, `Campeão leva: ${prizeText(c.prize)}`));
    const play = h('button', { class: 'btn amber wide' }, `Jogar ${FASES[fase].toLowerCase()}`);
    play.addEventListener('click', () => startMatch(c, fase));
    stage.append(box, h('div', { class: 'career-actions' }, play));
  };

  const startMatch = (c, fase) => {
    const d = c.duplas[fase];
    go('classic', {
      mode: 'career',
      opps: [d[0], d[1]],
      partner: PARTNER,
      rules: { buchaVale2: true, laeloVale2: true, comecaSena: true, cincoBuchas: true, ...c.format },
      onEnd: (won, match, quit) => go('career', { result: { id: c.id, fase, won, quit, score: match.score } }),
    });
  };

  // resultado de um jogo do campeonato
  if (params.result) {
    const r = params.result;
    const c = CAMPEONATOS.find((x) => x.id === r.id);
    const idx = CAMPEONATOS.indexOf(c);
    if (r.won) {
      if (r.fase >= 2) {
        car.active = null;
        const first = !car.titles.includes(c.id);
        if (first) car.titles.push(c.id);
        if (idx === car.level) car.level = Math.min(CAMPEONATOS.length, car.level + 1);
        for (const k of ['mesa', 'domino']) if (c.prize[k] && !car.unlocked[k].includes(c.prize[k])) car.unlocked[k].push(c.prize[k]);
        saveCareer(car);
        showList();
        championModal(c, first);
      } else {
        car.active = { id: c.id, fase: r.fase + 1 };
        saveCareer(car);
        showBracket(c);
        sfx.win();
        const m = modal(
          [
            h('div', { class: 'eyebrow' }, `${FASES[r.fase]} · ${r.score[0]} × ${r.score[1]}`),
            h('h2', {}, 'Classificado!'),
            h('p', {}, `Próximo jogo: ${FASES[r.fase + 1].toLowerCase()} contra ${CAST[c.duplas[r.fase + 1][0]].name} e ${CAST[c.duplas[r.fase + 1][1]].name}.`),
            h('div', { class: 'actions' }, h('button', { class: 'btn amber', onClick: () => m.close() }, 'Bora')),
          ],
          { cls: 'result' },
        );
      }
    } else {
      car.active = { id: c.id, fase: 0 };
      saveCareer(car);
      showBracket(c);
      sfx.lose();
      const m = modal(
        [
          h('div', { class: 'eyebrow' }, r.quit ? 'Você levantou da mesa' : `${FASES[r.fase]} · ${r.score[0]} × ${r.score[1]}`),
          h('h2', {}, 'Eliminados.'),
          h('p', {}, `O ${c.short} recomeça das quartas. Bora de novo?`),
          h('div', { class: 'actions' }, h('button', { class: 'btn amber', onClick: () => m.close() }, 'Bora')),
        ],
        { cls: 'result' },
      );
    }
  } else {
    const cur = CAMPEONATOS[Math.min(car.level, CAMPEONATOS.length - 1)];
    if (car.active && car.active.fase > 0) showBracket(CAMPEONATOS.find((x) => x.id === car.active.id));
    else if (car.level < CAMPEONATOS.length && car.titles.length === 0 && !params.list) showBracket(cur);
    else showList();
  }

  function championModal(c, first) {
    confetti(180);
    sfx.win();
    const prev = h('div', { class: 'prize-preview' });
    if (c.prize.domino) {
      const w = h('div', { 'data-domino': c.prize.domino, class: 'prize-tiles' }, tileEl(makeTile(6, 6), { u: 30 }), tileEl(makeTile(3, 5), { top: 5, bot: 3, u: 30 }));
      prev.append(w);
    }
    const buttons = [h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Depois')];
    if (first && (c.prize.mesa || c.prize.domino)) {
      buttons.push(
        h('button', {
          class: 'btn amber',
          onClick: () => {
            if (c.prize.mesa) settings.mesa = c.prize.mesa;
            if (c.prize.domino) settings.domino = c.prize.domino;
            saveSettings();
            m.close();
          },
        }, 'Usar agora'),
      );
    }
    const m = modal(
      [
        h('div', { class: 'eyebrow' }, c.name),
        h('h2', {}, 'Campeões!'),
        h('p', {}, first ? `Você e ${CAST[PARTNER].name} levaram o título. Liberado: ${prizeText(c.prize)}.` : 'Título defendido. Respeito na mesa.'),
        prev,
        h('div', { class: 'actions' }, buttons),
      ],
      { cls: 'result' },
    );
  }

  return null;
}
