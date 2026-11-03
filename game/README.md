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

## Como funciona (v0.5 — mina idle com elevador)

- Cada andar tem um **nível**. O nível aumenta a velocidade; mineiros = 1 + 1 a cada 10 níveis (máx. 5).
- Os mineiros vão até o veio, cavam e levam o minério para o **baú do andar**. O ouro fica ali.
- O **elevador** desce, recolhe dos baús até a capacidade e sobe. Melhore capacidade e velocidade.
- Sem gerente, você toca no andar para trabalhar e no elevador para descer. **Capataz** (andar) e **Operador** (elevador) automatizam, inclusive offline.
- Minério mais fundo é mais duro e vale mais. Toque no veio para golpes extras.
- Zumbis descem pela **escada** da direita e só entram nos andares ativos: param a produção e comem o baú.
  Andar abandonado é pulado. Zumbis ficam mais fortes conforme a mina desce.
- Torres alcançam andares vizinhos e a escada; torre mais funda é mais forte; tipos novos liberam a cada andar.
- Cada andar novo acorda a Abominação, que desce pela escada. Derrote-a para cavar o próximo.

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
