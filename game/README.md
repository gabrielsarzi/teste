# Último Bunker

Tower defense incremental em pixel art, top-down, em pé, para celular. Feito com three.js (câmera ortográfica 2D).

## Rodar

Qualquer servidor estático na pasta `game/`:

```bash
cd game
python3 -m http.server 8000
# abra http://localhost:8000 (ou o IP da máquina no celular)
```

O three.js r128 está em `vendor/`, então funciona offline e serve depois para empacotar com Capacitor.
Para gerar um HTML único (JS embutido, three.js via CDN), útil para Cloudflare Pages ou para compartilhar:

```bash
python3 tools/build_single.py dist/ultimo-bunker.html
```

## Estrutura

| Arquivo | O que tem |
|---|---|
| `src/i18n.js` | Textos PT/EN |
| `src/data.js` | Balanceamento: torres, inimigos, talentos |
| `src/audio.js` | Efeitos chiptune e música (WebAudio, sem arquivos) |
| `src/art.js` | Pixel art procedural 16×16 (paleta fixa de 25 cores) |
| `src/game.js` | Simulação, render, entrada (toque/pinça) e interface |

## Como funciona (v0.4 — Mina sob ataque)

- Corte vertical de uma mina. Toque no veio para cavar; contrate mineiros para cavar sozinhos.
- Minério mais fundo é mais duro (1, 3, 5, 8… golpes por pedaço) e vale muito mais. Picareta e ferramentas valem para todos os andares.
- O barulho de toda a mina atrai zumbis. Eles entram pelo andar 1 e descem em zigue-zague.
  Param e atacam o primeiro andar com mineiros; andar abandonado (sem mineiros, botão ✕) é atravessado.
- Quanto mais fundo você abre, mais fortes os zumbis — em algum momento vale abandonar os andares de cima.
- Torres alcançam o próprio andar e os vizinhos; torre construída mais fundo é mais forte.
  Tipos novos liberam com a profundidade (criogênico no 2, morteiro no 3, tesla no 4).
- Cada andar novo acorda a Abominação, que entra pelo topo e desce. Derrote-a para liberar o próximo.
- Offline: a mina continua rendendo; andares mal defendidos rendem menos. Save no aparelho.

## Decisões do briefing (v0.1)

- Pós-apocalíptico, tom épico. Defender o bunker.
- Grade livre de 9×16: as torres formam o labirinto (BFS recalculado a cada construção; não deixa bloquear o caminho).
- Entrada no topo; laterais a partir da onda 6. Destroços aleatórios que você limpa com ouro (o mapa cresce).
- 4 torres: Atirador, Morteiro, Criogênico, Tesla. Nível 1–5, escolha de ramo no nível 3, prioridade de alvo.
- Inimigos: normal, rápido, chefe a cada 10 ondas. Ondas infinitas com contador e bônus por chamar antes.
- Run acaba → Essência → árvore de talentos (Ataque, Economia, Tecnologia). Ganho offline com limite de horas.
- Velocidade x1/x2 (x4 por talento), chamada automática de ondas por talento.
- Efeitos: números de dano, partículas, tremor em chefes, luzes dinâmicas, ciclo dia/noite (100 s).
- Save local (localStorage). Menu radial ao tocar num tile. HUD em cima, ações embaixo.

## Próximos passos sugeridos

- Torres restantes: Sniper, Veneno, Suporte, Mina de ouro.
- Mais inimigos (voador, escudo, regeneração, divisor) — você escolheu só 3 por agora.
- Salvar a run em andamento, PWA instalável, deploy no Cloudflare Pages.
