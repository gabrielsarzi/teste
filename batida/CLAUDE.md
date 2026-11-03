# Batida! — dominó de boteco (memória do projeto)

Leia isto antes de mexer no jogo. Aqui está o que o jogo é, como ele foi montado,
o que o dono (Gabriel) pediu, o que já foi tentado e descartado, e de onde continuar.

## Status (nov/2026)
- O jogo offline está **pronto e aprovado** ("acho que está perfeito").
- O próximo grande passo é o **online de verdade**, mas o Gabriel **não quer mexer nisso agora**. Espere ele pedir.
- Jogável no navegador pelo artifact: https://claude.ai/artifact/Bsb5NZhtaENJyXpCd6RH9A
  (para atualizar: `npm run build` e publique `dist/batida.html` nessa mesma URL).
- Já existe um APK Android de teste (A22 do Gabriel), mas ele é antigo; gere outro só quando pedirem.

## Regras do dono (combinadas, siga sempre)
- **Só gere APK quando o Gabriel pedir explicitamente** ("só gera o apk depois de eu falar").
- **Backend futuro: tudo no Cloudflare** (Workers / Durable Objects / D1). **Não usar Supabase.**
- **Ainda sem login.** Login entra junto com o online de verdade.
- Online por enquanto: **servidor de teste** (`server/`) + servidor simulado dentro do jogo.
- Personagens **só com nome, sem rosto/avatar**.
- "Gato" no boteco = **jogada errada** ("Ó o gato!"), nunca vocativo ("não pode, gato" ficou errado).
- O jogo é **100% dominó tradicional brasileiro**: nada de roguelike, cartas especiais ou poderes.
- Gabriel escreve em português informal; responda em português.
- Mostre mockup (print) antes de mudança visual grande que ele pediu para ver primeiro.
- No celular **não pode aparecer barra de rolagem**.

## Regras do jogo (implementadas em `src/classic/engine.js`)
- 28 pedras (duplo-6), **7 pedras cada**.
- Modos: **2 jogadores** (mano a mano, com compra), **3** (com compra), **4 em dupla** (sem compra, parceiro na frente).
- **Obrigado a jogar** se tiver pedra que serve. Sem pedra: compra (2/3 jogadores) ou passa.
- **Partida até 4 pontos.** Placar em **cruz na lousa**: cada ponto é uma bolinha na **ponta** da cruz; **bolinha dourada no meio** = time de quem sai na rodada. No lugar de "Rodada X" a lousa mostra o logo "Batida!".
- Batida simples = 1 ponto. **Batida de bucha vale 2** (dá para desligar). **Lá-e-lô vale 2** (ligado por padrão).
- **5 buchas na mão volta o jogo** (reembaralha).
- **Fechar o jogo**:
  - Pode fechar de propósito.
  - **Fechamento forçado** (a pedra cabia na outra ponta, onde o jogo continuaria aberto): vai para **votação**, e empate deixa o jogo aberto.
  - **Fechamento natural** (não tinha outro jeito) conta automaticamente: ganha quem tem menos pontos na mão.
- Tempo de jogada 30s, com cobrança aos 15s. Quem começa: opção "começa com a sena".

## Conteúdo
- **Jogo rápido**: escolhe jogadores (2/3/4), nível (fácil/médio/difícil), valendo (aposta virtual), regras da casa.
- **Carreira**: 6 campeonatos (quartas, semi, final), com inscrição e prêmio. Contrata parceiro. Troféus numa estante.
- **Desafio do dia**, **Missões diárias**, **Conquistas**, **Estatísticas** (`src/progress.js`).
- **Dinheiro virtual**: carteira, valendo, inscrição, prêmios, **fiado** (empréstimo) e vídeo premiado de R$100 uma vez por dia.
- **Loja**: 10 mesas e 11 dominós (`MESAS_VISUAL` / `DOMINOS_VISUAL` em `src/classic/cast.js`) e "tirar anúncios".
- **Elenco** (`CAST` em `cast.js`): Rafa, Zezão, Naldo, Tio Rogério, Bia, Tonhão, Dona Neide, Juninho, Paulão, Lurdinha, Valter, Edu, Cida, Bené, Marquinhos, Careca. Cada um tem nível, mania e falas; sotaques regionais ficam em `src/classic/sotaques.js`.
- **Conversa na mesa** (`src/classic/talk.js`): provocações, broncas, reações, frases do jogador e emojis.
- **IA** (`src/classic/ai.js`): heurística por nível e IA mestre por Monte Carlo (4 jogadores) para os campeões. Ela sabe votar no fechamento.
- **Online pré-pronto** (`src/online/`, `src/screens/online.js`, `server/`): lobby, salas (rápido/campeonato), sala privada por código, bots completando, dono que sai passa a sala, expulsar, ranking semanal (local) e punição por abandono. O protocolo está em `server/PROTOCOLO.md`.
- **Anúncios** (`src/ads.js`): AdMob com **IDs de TESTE**, premiado e intersticial a cada 3 partidas (as 2 primeiras livres). Troque pelos IDs reais antes de publicar.
- **Página da loja**: `store/LOJA.md` (textos), `store/prints/`, `store/destaque-1024x500.png`, `store/icone-512.png`, `store/privacidade.html`, `store/CREDITOS.md` (créditos das músicas).

## Som e visual: decisões tomadas (não refazer o que foi descartado)
- Música: **rádio** com 3 estações gravadas (viola caipira = **padrão**, choro, bossa) em `src/assets/*.mp3`, num **único** `<audio>`.
  - Música sintetizada foi **descartada** ("mecânico").
  - Samba **removido**: não tocava no celular dele.
- Som de bar: **barulhos soltos procedurais** (copo, talher, cadeira, garrafa, dominó ao longe), **baixinhos**.
  - Gravação com vozes **descartada** (dava pra entender as falas).
  - Burburinho **descartado** ("parece vento").
- Som ligado por padrão e também no menu. Tem botão de mudo no menu e na mesa. Os efeitos são sintetizados em WebAudio (`src/ui/audio.js`), com vibração no nativo.
- Mesa: a fileira de pedras corre **na vertical**, as buchas ficam em pé (perpendiculares), os números ficam sempre de pé, e dá pra arrastar e organizar a mão **a qualquer hora**.
- Perfumaria que entrou: batida caprichada (pancada na lousa), luz de luminária, dominó "gasto", emojis, falas regionais, abertura (splash 1x por dia), estante de troféus, moedas voando para a carteira, marcas de copo e riscos na mesa (`src/ui/decor.js`, por baixo das pedras).
- **Descartado:** copo e porção em cima da mesa (as pedras caíam por cima) e pedras dos adversários em leque (ficava ilegível). Também foi recusada a sugestão nº 9 da lista de perfumaria.

## Arquitetura
- JS puro com módulos ES. O esbuild junta tudo num **único HTML** (`build.mjs`):
  - `dist/index.html`: documento completo, usado pelo app Android.
  - `dist/batida.html`: corpo para o artifact.
  - Fontes embutidas em base64 (`src/fonts.css`) e mp3 como dataurl.
- `src/main.js`: registra as telas e trata os toques globais. `src/app.js`: configurações (com migração `settings.rv`, hoje 6), carteira, navegação `go()` e visual da mesa.
- Telas em `src/screens/`: home, classic (a mesa), career, look (loja), online, progresso, splash.
- `src/core/board.js`: layout das fileiras da mesa. `src/ui/tileView.js`: desenho das pedras.
- Dados salvos no `localStorage` com prefixo `batida:`.
- Android: **Capacitor 7** (`android/`, appId `com.batida.domino`), com @capacitor/haptics e @capacitor-community/admob@7.

## Comandos
```bash
npm install
npm run build                      # gera dist/
node tests/sim-classic.mjs         # simulações de regras (também sim-skill, sim-master, sim-layout)
node tests/rooms.test.mjs          # salas online
node tests/shot.cjs                # prints com Playwright (shot-n.cjs 2|3|4, shot-cruz, shot-cinco, shot-online)
node tests/store-assets.cjs        # regenera os prints da loja
cd server && npm install && npm start   # servidor de teste ws na porta 8787
```
Na nuvem, o Playwright e o Chromium já vêm instalados (`require('playwright')`). Os prints de teste vão para a pasta de rascunho.

### APK (só quando o Gabriel pedir)
```bash
npm run build && npx cap sync android
cd android && ./gradlew assembleDebug
```
- Precisa do Android SDK (`ANDROID_HOME`; na nuvem ele ficava em `/opt/android`).
- Se o Maven Central der **erro 429**, crie `~/.gradle/init.d/mirror.gradle` trocando `repo.maven.apache.org` por `https://maven-central.storage-download.googleapis.com/maven2/`.
- O APK sai em `android/app/build/outputs/apk/debug/app-debug.apk`. Copie para `Batida.apk` na raiz do projeto.

## Próximos passos (quando ele pedir)
1. **Online de verdade no Cloudflare**: Workers + Durable Objects (uma por sala), D1 para ranking/contas, login. O protocolo atual (`server/PROTOCOLO.md`) serve de base; `WsBackend` em `src/online/backend.js` já conversa por WebSocket.
2. **Publicar**: conta de desenvolvedor no Google Play, IDs reais do AdMob, APK/AAB assinado (release keystore), textos de `store/LOJA.md`.
3. Depois, talvez iOS (Capacitor também gera o projeto Xcode, mas precisa de Mac).

## Dicas de trabalho
- Commits em português, descritivos.
- Na ferramenta de shell, heredoc com `${...}` às vezes é bloqueado. Nesse caso, escreva um script Python/JS num arquivo e rode o arquivo.
