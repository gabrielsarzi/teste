# Tirei

App de sorteio de amigo secreto (e variações) em que o organizador manda **um link só no grupo** e cada pessoa descobre, no próprio celular, quem tirou. Ninguém vê o resultado dos outros, nem o organizador.

> "Tirei" é um nome provisório.

## O que tem nesta pasta

| Caminho | O que é |
|---|---|
| `prototipo/index.html` | Protótipo clicável em React. Simula o organizador e o celular de quem recebe o link, nos dois modos de identificação. |
| `docs/identificacao.md` | Explicação completa de como o app descobre quem é quem. |
| `docs/arquitetura.md` | Proposta técnica: telas, dados, servidor, pagamento e etapas de construção. |
| `docs/whatsapp-meta.md` | Pesquisa sobre a API oficial do WhatsApp: cadastro na Meta, custos, regras e limites. |

## Fluxo em uma frase

Organizador escolhe o tipo de evento → digita os nomes → define as regras → sorteia → manda a mensagem no grupo → cada pessoa toca no link, se identifica e vê quem tirou.

## Planos propostos

- **Grátis:** até 5 pessoas, identificação escolhendo o nome no link, com anúncio.
- **Plus, R$ 1,99 no Pix:** sem limite de pessoas, identificação pelo WhatsApp, sem anúncio.

## Decisões em aberto

1. Nome definitivo e domínio.
2. Se o modo grátis aceita mais de 5 pessoas com anúncio, ou se trava em 5.
3. Se o organizador precisa criar conta (login) ou basta um link secreto de administração.
4. Quando contratar o número oficial do WhatsApp e abrir CNPJ (MEI) para a verificação na Meta.

## Como ver o protótipo

O arquivo está no formato de página do Claude (sem `<html>` e `<body>`). Ele também abre direto no navegador.
