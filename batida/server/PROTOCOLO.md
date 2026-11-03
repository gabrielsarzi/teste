# Protocolo online do Batida

Conexão WebSocket. Toda mensagem é JSON.

## Pedidos (cliente → servidor)
`{ "id": 1, "op": "<operação>", ...argumentos }` → resposta `{ "re": 1, "ok": true, "data": ... }` ou `{ "re": 1, "ok": false, "error": "texto" }`.

| op | argumentos | o que faz |
|---|---|---|
| hello | nick | entra com o apelido; devolve `{ uid, online }` |
| list | kind (`rapido`/`campeonato`), q | lista salas abertas; `q` busca nome, dono ou código (código acha sala privada) |
| create | opts `{ kind, players, stake, fee, private, name }` | cria a sala, você vira dono |
| join | code (ou id) | entra num lugar vazio ou no lugar de um bot |
| leave | — | sai; se era o dono, o próximo humano vira dono; sem humanos, a sala some |
| kick | seat | (dono) tira alguém ou um bot |
| addBot | seat? | (dono) coloca bot |
| fillBots | — | (dono) completa os lugares vazios com bots |
| ready | v | marca/desmarca "pronto" |
| moveSeat | seat | troca de lugar (escolher dupla) |
| remove | — | (dono) exclui a sala |
| start | — | (dono) começa; completa com bots; precisa de todos prontos |
| finish | text | (dono) volta a sala para a espera depois do jogo |

## Avisos (servidor → cliente)
- `{ type: "room", room }` a sala mudou
- `{ type: "lobby" }` a lista do saguão mudou (peça `list` de novo)
- `{ type: "host", me: true }` você virou dono
- `{ type: "kicked" }` / `{ type: "closed", why }`
- `{ type: "start", room }` a partida começou

## Próximo passo: a partida pela rede
Hoje, ao começar, cada aparelho joga a partida localmente com bots no lugar dos outros.
Para jogar de verdade entre pessoas, o servidor passa a rodar a partida com `src/classic/engine.js`
(o mesmo motor do jogo) e troca estas mensagens:
- servidor → todos: `deal` (cada um recebe só a própria mão), `turn`, `played`, `drew`, `passed`, `vote`, `result`
- cliente → servidor: `play { uid da pedra, lado }`, `draw`, `vote { fecha }`
- bots e quem cair da conexão jogam pela IA do servidor (`src/classic/ai.js`); o relógio de 30 s roda no servidor.
