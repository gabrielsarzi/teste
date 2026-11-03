# Batida! — dominó de boteco

Dois modos:
- **Clássico**: dominó brasileiro de dupla (4 jogadores, 7 pedras, sem compra). Obrigado a jogar se tiver pedra, jogo fechado conta pontos na mão, batida de bucha vale 2 (opcional), 4 rodadas com um início de cada.
- **Virada**: roguelike de combos. Monte correntes de até 5 pedras, junte parceiros, bebidas e simpatias e vire 8 botecos.

## Rodar
```bash
npm install
npm run build      # gera dist/index.html (arquivo único) e dist/batida.html (artifact)
```
Abra `dist/index.html` no navegador. Testes: `node tests/sim-classic.mjs`, `node tests/sim-virada.mjs`.

Feito em JS puro (sem framework), pronto para empacotar com Capacitor (iOS/Android) ou Electron/Steam.
