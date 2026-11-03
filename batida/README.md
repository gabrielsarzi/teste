# Batida! — dominó de boteco

Dominó brasileiro de dupla (4 jogadores, 7 pedras, sem compra), para celular.

- **Jogo rápido**: escolha o nível dos adversários (fácil, médio, difícil) e as regras da casa.
- **Carreira**: 6 campeonatos (quartas, semi e final), do boteco do bairro ao Brasileirão. Cada título libera mesas e dominós.
- Regras: obrigado a jogar se tiver pedra; jogo fechado conta os pontos na mão; batida de bucha vale 2 e lá-e-lô vale 2 (as duas dão para desligar); 4 rodadas, um início de cada.
- Opções: ajuda nas pedras, contagem da mesa, conversa na mesa (provocações e frases), ritmo.
- IA: heurística com níveis e uma IA mestre (Monte Carlo) para os campeões.

## Rodar
```bash
npm install
npm run build      # gera dist/index.html (arquivo único) e dist/batida.html (artifact)
```
Testes: `node tests/sim-classic.mjs`, `node tests/sim-skill.mjs`, `node tests/sim-master.mjs`, `node tests/sim-layout.mjs`, `node tests/shot.cjs` (Playwright).
