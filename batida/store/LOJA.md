# Batida! na Google Play — o que preencher

## Arquivos desta pasta
- `icone-512.png`: ícone do app (512×512)
- `destaque-1024x500.png`: gráfico de destaque
- `prints/01..06`: capturas de tela de celular (1080×1920)
- `privacidade.html`: política de privacidade (precisa de um endereço público, por exemplo no Cloudflare Pages)

Para gerar de novo os prints e o destaque: `npm run build && node tests/store-assets.cjs`.

## Ficha da loja

**Nome do app (até 30 caracteres)**
Batida! Dominó de Boteco

**Descrição curta (até 80 caracteres)**
Dominó brasileiro de dupla, mano a mano e campeonatos, com a resenha do bar.

**Descrição completa**
Puxa uma cadeira que a mesa tá montada!

Batida! é o dominó do jeito que se joga no boteco: em dupla, com a cruz marcada no giz, provocação na mesa e a regra da casa valendo.

COMO NO BAR
• Dupla contra dupla, 7 pedras pra cada, sem compra. Ou mano a mano e com 3 jogadores, comprando do monte até achar a pedra.
• Batida de bucha vale 2. Lá-e-lô também.
• Jogo fechado: ganha quem tem menos pontos na mão. Se alguém fechar à força, a mesa vota.
• Cinco buchas na mão? Volta o jogo!
• A partida vai até 4 pontos, marcados na cruz da lousa.

A RESENHA
• Zezão, Naldo, Tio Rogério, Rafa e a turma toda jogam, conversam e provocam.
• Tocou na pedra errada? "Ó o gato!"
• Mande frases pra mesa e veja eles responderem.

CARREIRA
• Seis campeonatos, do torneio do boteco do bairro até o Brasileirão de Dominó.
• Quartas, semi e final contra duplas cada vez mais fortes.
• Contrate parceiros melhores e ganhe mesas e dominós novos.

E MAIS
• Desafio do dia, missões e conquistas.
• Loja com mesas (madeira, feltro, mármore, mesa da praça, azulejo...) e dominós (osso, colorido, madeira, acrílico...).
• Salas online com amigos e ranking da semana.
• Contagem da mesa e números nas pedras para quem está começando ou tem a vista cansada.

O dinheiro do jogo é de mentira: não vale dinheiro de verdade e não pode ser comprado nem sacado.

**Categoria:** Jogos › Tabuleiro
**Tags sugeridas:** dominó, dupla, tabuleiro, clássico, brasileiro

## Classificação de conteúdo (questionário IARC) — como responder
- Jogo de azar simulado: **sim**. O jogo tem partidas "valendo" com moedas virtuais. As moedas **não** podem ser compradas com dinheiro real e **não** têm valor fora do jogo. Isso costuma resultar em classificação 12+ (pode variar).
- Violência, linguagem imprópria, conteúdo sexual, drogas: **não**. As falas dos personagens são brincadeiras de mesa, sem palavrão.
- Interação entre usuários: **sim** quando o online estiver no ar (salas e frases prontas; não há chat livre).
- Compartilha localização: **não**.
- Compras no app: **sim** ("Tirar os anúncios").
- Contém anúncios: **sim** (AdMob).

## Antes de publicar
1. Trocar os IDs de teste do AdMob (em `src/ads.js` e `android/app/src/main/AndroidManifest.xml`) pelos IDs da sua conta AdMob.
2. Criar o produto "remover_anuncios" no Play Console e ligar o Google Play Billing.
3. Gerar o build de release assinado (AAB) com a sua chave.
4. Publicar a `privacidade.html` num endereço público e colocar o link na ficha da loja.
5. Preencher o e-mail de contato na política de privacidade.
