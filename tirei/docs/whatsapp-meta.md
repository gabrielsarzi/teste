# API oficial do WhatsApp (Meta)

Pesquisa feita em novembro de 2026. As fontes são em boa parte blogs de empresas que revendem a API. Confira valores e nomes de menu no painel da Meta antes de decidir.

## Pontos que mudam o projeto

1. **A Meta não fornece número.** Dá só um número de teste grátis que envia para até 5 destinatários cadastrados. Para produção é preciso um número próprio que **não** esteja em uso no WhatsApp do celular (um chip novo resolve). Depois de registrado na API, ele só funciona por ela.
2. **Aceite obrigatório.** Só pode receber mensagem quem deu o próprio número e aceitou. O organizador digitar o número dos amigos não conta. Por isso, no Tirei, quem manda a primeira mensagem é o participante (ver `identificacao.md`).
3. **Categorias de mensagem.** Mensagens fora da janela de 24h usam modelos aprovados. Precisam ser da categoria **Utilidade**. Texto com cara de propaganda ("Parabéns!", "Aproveite!") é reclassificado como **Marketing**, que custa bem mais.

## Custos (Brasil, aproximados)

| Item | Valor |
|---|---|
| Modelo de Utilidade | R$ 0,035 a R$ 0,08 por mensagem (as fontes divergem) |
| Respostas dentro da janela de 24h aberta pelo cliente | grátis até agora; um blog diz que passa a ser cobrado a partir de 1º/10/2026, sem confirmação oficial |
| Sorteio de 10 pessoas | menos de R$ 1 no pior caso |

## Limites de envio

Contas sem verificação começam com cerca de **250 envios por dia** (o limite é por portfólio empresarial). A verificação do negócio aumenta o limite e pede documento de empresa (provavelmente um CNPJ de MEI serve).

## Tutorial de cadastro

A porta de entrada é **developers.facebook.com**. O Meta Business Suite e o app WhatsApp Business não servem para isso.

**Antes de começar:** conta pessoal no Facebook, chip novo, cartão de crédito e, mais para frente, um CNPJ.

1. **Conta de desenvolvedor.** Entrar em developers.facebook.com com o Facebook e clicar em **Começar**. Confirmar telefone e e-mail.
2. **Criar o app.** **Meus apps → Criar app**, escolher o caso de uso de WhatsApp e criar um **portfólio empresarial** com o nome do projeto.
3. **Testar.** Em **WhatsApp → Configuração da API** aparecem o número de teste e um token temporário. Cadastrar o próprio número como destinatário (chega um código no WhatsApp) e enviar o modelo `hello_world`.
4. **Número real.** Na mesma tela, **Adicionar número de telefone**: colocar o chip novo, confirmar por SMS ou ligação, criar o **PIN de 6 dígitos** da confirmação em duas etapas e escolher o **nome de exibição** (a Meta revisa).
5. **Pagamento.** No **Gerenciador do WhatsApp**, cadastrar o cartão.
6. **Token permanente.** Em business.facebook.com, **Configurações → Usuários do sistema**, criar um usuário e gerar um token com `whatsapp_business_messaging` e `whatsapp_business_management`.
7. **Webhook.** Em **WhatsApp → Configuração**, informar a URL do servidor e assinar o evento `messages`.
8. **Modelos.** Criar os modelos na categoria **Utilidade**.
9. **Verificação do negócio.** Na **Central de Segurança** do Business, quando precisar passar dos ~250 envios por dia.

Os nomes dos menus podem estar um pouco diferentes.

## Fontes

- [Meta: Get Started (Cloud API)](https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started)
- [Meta: preços](https://developers.facebook.com/docs/whatsapp/pricing)
- [WANotifier: limites do número de teste](https://help.wanotifier.com/en/article/test-phone-number-limitations-kt0ly2/)
- [ChatMaxima: preços no Brasil](https://chatmaxima.com/whatsapp-api-pricing/brazil/)
- [Chatalog: mudança de preço em out/2026](https://docs.chatalog.ai/platform-setup/whatsapp-connection-guide/whatsapp-pricing-update)
- [Chatarmin: limites de envio](https://chatarmin.com/en/blog/whats-app-messaging-limits)
- [360dialog: aceite (opt-in)](https://docs.360dialog.com/docs/messaging/overview/opt-in.md)
- [WATI: reclassificação de modelos](https://support.wati.io/en/articles/15932488-best-practices-to-reduce-whatsapp-utility-to-marketing-template-reclassification)
