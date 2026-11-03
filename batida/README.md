# Batida! — dominó de boteco

Dominó brasileiro de dupla (4 jogadores, 7 pedras, sem compra), para celular.

- **Jogo rápido**: escolha o nível dos adversários (fácil, médio, difícil) e as regras da casa.
- **Carreira**: 6 campeonatos (quartas, semi e final), do boteco do bairro ao Brasileirão. Cada título libera mesas e dominós.
- Regras: obrigado a jogar se tiver pedra; jogo fechado conta os pontos na mão; batida de bucha vale 2 e lá-e-lô vale 2 (as duas dão para desligar); 4 rodadas, um início de cada.
- Opções: ajuda nas pedras, contagem da mesa, conversa na mesa (provocações e frases), ritmo.
- IA: heurística com níveis e uma IA mestre (Monte Carlo) para os campeões.

## Online
- Tela Online com salas de jogo rápido e campeonato: criar, buscar (nome, dono ou código), sala privada por código, completar com bots, pronto, trocar de lugar, expulsar, excluir, dono que sai passa a sala para outro.
- Sem servidor configurado, usa um servidor simulado dentro do jogo.
- Servidor de verdade: `cd server && npm install && npm start` (porta 8787). No jogo, toque no nome do servidor no salão e coloque `ws://SEU_IP:8787`.
- Protocolo e próximos passos em `server/PROTOCOLO.md`. Testes: `node tests/rooms.test.mjs`, `cd server && node test-client.mjs`.

## Android (APK)
```bash
npm run build && npx cap sync android
cd android && ./gradlew assembleDebug   # precisa do Android SDK (ANDROID_HOME)
```
O APK sai em `android/app/build/outputs/apk/debug/app-debug.apk`. Ícones: `node tests/make-icons.cjs`.

## Rodar
```bash
npm install
npm run build      # gera dist/index.html (arquivo único) e dist/batida.html (artifact)
```
Testes: `node tests/sim-classic.mjs`, `node tests/sim-skill.mjs`, `node tests/sim-master.mjs`, `node tests/sim-layout.mjs`, `node tests/shot.cjs` (Playwright).
