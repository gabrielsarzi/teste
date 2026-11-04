# Como o app sabe quem é quem

## O problema

Na página atual (`amigo-secreto.html`), cada pessoa recebe um link diferente, e o resultado vai escondido dentro do link. Isso obriga o organizador a mandar uma mensagem no privado para cada um.

No Tirei, o organizador manda **um link só no grupo**. Como o link é igual para todo mundo, ele não carrega resultado nenhum. Quando alguém toca nele, o app precisa descobrir quem é aquela pessoa antes de mostrar quem ela tirou.

Por isso o resultado passa a ficar guardado **no servidor**, e não no link. O servidor só entrega o resultado de uma pessoa para quem provou ser ela.

## Modo 1: escolher o nome no link (grátis)

### Passo a passo de quem participa

1. Toca no link do grupo, por exemplo `tirei.app/K7Q2`.
2. Abre uma página com o nome do evento e a lista de participantes.
3. Toca no próprio nome. A página pergunta "Você é a Júlia?" e avisa que o nome vai ficar preso àquele celular.
4. Toca em "Sou eu".
5. Toca em "Mostrar quem eu tirei" quando ninguém estiver olhando, e vê o nome.
6. Pode escrever a própria lista de desejos, que aparece para quem a tirou.
7. Se abrir o link de novo no mesmo celular, vai direto para o resultado.

### O que acontece por trás

1. Ao tocar em "Sou eu", o navegador manda para o servidor: código do sorteio + participante escolhido.
2. O servidor verifica se esse participante ainda está livre.
   - Se estiver, gera uma **chave secreta aleatória** (um texto longo, impossível de adivinhar), grava "Júlia ↔ hash da chave" e devolve a chave para o navegador.
   - Se não estiver, responde "já entrou".
3. O navegador guarda a chave no próprio aparelho (armazenamento local).
4. Para ver o resultado, o navegador manda a chave. O servidor confere e devolve só o nome sorteado para a Júlia.
5. Para todos os outros, a Júlia aparece riscada na lista.

### Ponto fraco e como lidar

- **Alguém escolhe o nome de outra pessoa de propósito.** A pessoa certa vai ver o próprio nome riscado e avisar o organizador. O organizador toca em "Liberar" e a pessoa certa entra. Mas quem trapaceou viu um resultado que não era dele, então o certo é **refazer o sorteio**. Em família e entre amigos isso é raro, e o modo é o mais simples para todo mundo.
- **A pessoa troca de celular ou limpa o navegador.** Perde a chave. O organizador libera o nome e ela entra de novo. Como o sorteio não muda, ela vê o mesmo resultado.

### Melhoria possível

O organizador pode ligar um **PIN de 4 dígitos por pessoa**. O app gera os PINs, e o organizador manda cada PIN no privado. Fica mais seguro, mas volta a dar o trabalho de mandar uma mensagem por pessoa. Deixar como opção, desligada por padrão.

## Modo 2: confirmar pelo WhatsApp (Plus)

### Passo a passo de quem participa

1. Toca no link do grupo.
2. O WhatsApp abre uma conversa com o número oficial do Tirei, já com a mensagem `ENTRAR K7Q2` escrita.
3. Aperta enviar.
4. Se o organizador cadastrou o telefone dessa pessoa, o robô responde na hora: "Oi, Júlia! Você tirou: Pedro".
5. Se não cadastrou, o robô pergunta "Quem é você?" e mostra os nomes livres. Ela toca no próprio nome e recebe o resultado.
6. Se mandar mensagem de novo depois, o robô repete o resultado dela.

### O que acontece por trás

1. O link do grupo é, na prática, um link `wa.me/<número do Tirei>?text=ENTRAR K7Q2`. Pode passar antes por uma página nossa, que mostra o evento e um botão "Abrir no WhatsApp".
2. Quando a pessoa envia, a Meta chama o nosso servidor (webhook) com o texto da mensagem e o **número de quem mandou**. Esse número é confirmado pelo próprio WhatsApp e não dá para falsificar.
3. O servidor encontra o sorteio pelo código `K7Q2`.
4. Procura o número entre os telefones que o organizador cadastrou.
   - Achou: liga o participante a esse número e responde com o resultado.
   - Não achou: responde com uma lista de botões só com os participantes **sem telefone cadastrado** e ainda livres. Quem tem telefone cadastrado nunca aparece nessa lista, então não pode ser imitado.
5. A escolha volta pelo webhook, o servidor grava "participante ↔ número" e responde com o resultado.

### Por que esse modo é melhor

- Quem tem telefone cadastrado é reconhecido automaticamente e ninguém consegue se passar por ele.
- Quem não tem telefone fica preso ao primeiro número que o escolheu, igual ao modo 1, mas agora com um número de verdade associado. Se der problema, o organizador sabe de qual número veio.
- A própria pessoa mandou a primeira mensagem. Isso cumpre a regra de aceite da Meta, porque a empresa não pode mandar mensagem para quem não pediu.
- Como a pessoa escreveu primeiro, abre a janela de 24 horas, e as respostas do robô entram como mensagem de atendimento. É o jeito mais barato de usar a API. Ver `whatsapp-meta.md`.

### Custos e requisitos

- Número oficial cadastrado na Meta (chip novo, que não pode estar em uso no WhatsApp do celular).
- Centavos por mensagem. Um sorteio de 10 pessoas custa menos de R$ 1 mesmo no pior caso.
- Para passar de uns 250 envios por dia, a Meta pede a verificação do negócio, com documento de empresa.

## Por que o organizador não vê o resultado

O painel do organizador consulta o servidor e recebe só a lista de participantes com "entrou" ou "ainda não entrou". O servidor nunca manda os pares para essa tela. Assim o organizador pode participar do próprio sorteio sem saber de nada.

Se o organizador quiser poder consultar em caso de emergência (por exemplo, alguém esqueceu quem tirou e perdeu o celular), dá para criar um botão "Reenviar resultado para a pessoa", que reenvia pelo mesmo canal sem mostrar nada na tela do organizador.

## Resumo

| | Escolher o nome | Confirmar pelo WhatsApp |
|---|---|---|
| Custo para nós | zero | centavos por mensagem |
| O que prova quem é | a chave guardada no celular | o número de telefone |
| Dá para se passar por outro? | sim, e o organizador percebe depois | não, se o telefone foi cadastrado |
| Esforço de quem participa | tocar no nome | apertar enviar |
| Precisa de número oficial | não | sim |
