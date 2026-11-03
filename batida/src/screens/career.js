import { h, modal } from '../ui/dom.js';
import { tileEl } from '../ui/tileView.js';
import { makeTile } from '../core/tiles.js';
import { sfx } from '../ui/audio.js';
import { confetti } from '../ui/fx.js';
import { go, career, saveCareer, settings, saveSettings, wallet, setWallet, money } from '../app.js';
import { CAST, CAMPEONATOS, FASES, MESAS_VISUAL, DOMINOS_VISUAL, PARCEIROS } from '../classic/cast.js';
import { iconBtn, walletChip, fiadoModal } from './home.js';
import { track } from '../progress.js';
import { maybeInterstitial } from '../ads.js';

const SUBS = ['marquinhos', 'careca', 'tonhao', 'paulao', 'valter', 'cida'];

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

function prizeLine(c) {
  return `${money(c.cash)} + ${prizeText(c.prize)}`;
}

export function careerScreen(stage, params = {}) {
  const car = career();
  car.partner = car.partner || 'rafa';
  car.hired = car.hired || ['rafa'];
  const PARTNER = car.partner;
  stage.classList.add('career');

  const showList = () => {
    stage.innerHTML = '';
    stage.append(
      h(
        'div',
        { class: 'topbar' },
        iconBtn('back', 'Voltar', () => go('home')),
        h('div', { class: 'grow' }, h('div', { class: 'eyebrow' }, `${car.titles.length} de ${CAMPEONATOS.length} títulos`), h('div', { class: 'title-sm' }, 'Carreira')),
        walletChip(),
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
          h('div', { class: 'camp-prize' }, `Inscrição ${money(c.fee)} · prêmio ${prizeLine(c)}`),
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
        walletChip(),
      ),
    );
    const fmt = `Jogos até ${c.format.metaPontos} pontos`;
    const box = h('div', { class: 'bracket' });
    box.append(
      h(
        'div',
        { class: 'us-pair' },
        vsBadge('Nós'),
        h('div', {}, h('div', { class: 'pair-name' }, `Você e ${CAST[car.partner].name}`), h('div', { class: 'camp-sub' }, fmt)),
        fase === 0 ? h('button', { class: 'btn ghost small', onClick: () => partnerModal(c) }, 'Trocar parceiro') : h('span'),
      ),
    );
    c.duplas.forEach((d0, i) => {
      let d = d0;
      d = lineup(d);
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
    box.append(h('div', { class: 'camp-prize center' }, `Campeão leva: ${prizeLine(c)}`));
    const paid = car.active.paid;
    const broke = !paid && wallet() < c.fee;
    const play = h('button', { class: 'btn amber wide' }, paid ? `Jogar ${FASES[fase].toLowerCase()}` : `Pagar inscrição de ${money(c.fee)} e jogar`);
    play.addEventListener('click', () => {
      if (broke) return fiadoModal();
      if (!paid) {
        setWallet(wallet() - c.fee);
        sfx.coins();
        car.active.paid = true;
        saveCareer(car);
      }
      startMatch(c, fase);
    });
    if (broke) play.textContent = `Falta dinheiro para a inscrição (${money(c.fee)})`;
    stage.append(box, h('div', { class: 'career-actions' }, play));
  };

  // se o parceiro contratado está na dupla adversária, entra um substituto
  function lineup(d) {
    if (!d.includes(car.partner)) return d;
    const sub = SUBS.find((x) => !d.includes(x) && x !== car.partner);
    return d.map((x) => (x === car.partner ? sub : x));
  }

  function partnerModal(c) {
    const list = h('div', { class: 'partner-list' });
    const m = modal([h('h2', {}, 'Seu parceiro'), h('p', {}, 'Parceiro melhor joga melhor com você. Contrata uma vez e fica pra sempre.'), list, h('div', { class: 'actions' }, h('button', { class: 'btn ghost', onClick: () => m.close() }, 'Fechar'))]);
    const render = () => {
      list.innerHTML = '';
      for (const pt of PARCEIROS) {
        const have = car.hired.includes(pt.id);
        const using = car.partner === pt.id;
        const lv = Math.max(1, Math.min(5, Math.round((pt.skill || 0.6) * 5)));
        const btn = h('button', { class: `btn small ${using ? 'ghost' : 'amber'}`, disabled: using || (!have && wallet() < pt.price) }, using ? 'Jogando' : have ? 'Escolher' : `Contratar ${money(pt.price)}`);
        btn.addEventListener('click', () => {
          if (!have) {
            setWallet(wallet() - pt.price);
            car.hired.push(pt.id);
            sfx.coins();
          } else sfx.pick();
          car.partner = pt.id;
          saveCareer(car);
          render();
        });
        list.append(
          h('div', { class: `partner-row ${using ? 'on' : ''}` },
            h('div', {}, h('b', {}, CAST[pt.id].name), h('span', { class: 'stars' }, '★'.repeat(lv), h('span', { class: 'off' }, '★'.repeat(5 - lv))), h('div', { class: 'camp-sub' }, pt.pitch)),
            btn),
        );
      }
    };
    render();
    m.el.querySelector('.actions .btn').addEventListener('click', () => showBracket(c));
  }

  const startMatch = (c, fase) => {
    const d = lineup(c.duplas[fase]);
    const pt = PARCEIROS.find((x) => x.id === car.partner) || PARCEIROS[0];
    go('classic', {
      mode: 'career',
      players: 4,
      opps: [d[0], d[1]],
      partner: car.partner,
      partnerLevel: { skill: pt.skill, master: pt.master },
      rules: { players: 4, buchaVale2: true, laeloVale2: true, comecaSena: true, cincoBuchas: true, votacao: true, ...c.format },
      onEnd: async (won, match, quit) => {
        await maybeInterstitial();
        go('career', { result: { id: c.id, fase, won, quit, score: match.score } });
      },
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
        const cash = first ? c.cash : Math.round(c.cash / 2);
        setWallet(wallet() + cash);
        car.lastCash = cash;
        if (idx === car.level) car.level = Math.min(CAMPEONATOS.length, car.level + 1);
        for (const k of ['mesa', 'domino']) if (c.prize[k] && !car.unlocked[k].includes(c.prize[k])) car.unlocked[k].push(c.prize[k]);
        saveCareer(car);
        track('title');
        showList();
        championModal(c, first);
      } else {
        car.active = { id: c.id, fase: r.fase + 1, paid: true };
        saveCareer(car);
        showBracket(c);
        sfx.win();
        const m = modal(
          [
            h('div', { class: 'eyebrow' }, `${FASES[r.fase]} · ${r.score[0]} × ${r.score[1]}`),
            h('h2', {}, 'Classificado!'),
            h('p', {}, `Próximo jogo: ${FASES[r.fase + 1].toLowerCase()} contra ${lineup(c.duplas[r.fase + 1]).map((x) => CAST[x].name).join(' e ')}.`),
            h('div', { class: 'actions' }, h('button', { class: 'btn amber', onClick: () => m.close() }, 'Bora')),
          ],
          { cls: 'result' },
        );
      }
    } else {
      car.active = { id: c.id, fase: 0, paid: false };
      saveCareer(car);
      showBracket(c);
      sfx.lose();
      const m = modal(
        [
          h('div', { class: 'eyebrow' }, r.quit ? 'Você levantou da mesa' : `${FASES[r.fase]} · ${r.score[0]} × ${r.score[1]}`),
          h('h2', {}, 'Eliminados.'),
          h('p', {}, `O ${c.short} recomeça das quartas, com inscrição nova. Bora de novo?`),
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
        h('div', { class: 'money-delta up' }, `+${money(car.lastCash || c.cash)}`),
        prev,
        h('div', { class: 'actions' }, buttons),
      ],
      { cls: 'result' },
    );
  }

  return null;
}
