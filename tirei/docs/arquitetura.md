# Arquitetura proposta

## Telas

**Organizador**
1. Evento: tipo (amigo secreto, amigo chocolate, amigo livro, outro), nome do grupo, valor máximo e dia da troca.
2. Pessoas: nome e telefone opcional. Mostra se o sorteio é grátis ou Plus.
3. Regras: quem não pode tirar quem (vale para os dois lados) e o modo de identificação.
4. Sorteio: pagamento via Pix quando for Plus, código do sorteio, mensagem pronta para o grupo, lista de quem já entrou, "Liberar" e "Refazer sorteio".

**Participante**
- Modo nome: lista de nomes → confirmação → resultado + lista de desejos.
- Modo WhatsApp: conversa com o robô.

## Pilha sugerida

| Parte | Escolha | Por quê |
|---|---|---|
| Interface | React + Vite | Simples, rápido, hospedagem estática barata ou grátis. |
| Servidor | Cloudflare Workers ou Supabase (Edge Functions) | Os dois têm plano grátis que aguenta o começo e recebem o webhook do WhatsApp. |
| Banco | Cloudflare D1 ou Postgres do Supabase | Poucas tabelas e pouco volume. |
| WhatsApp | Cloud API oficial da Meta | Ver `whatsapp-meta.md`. |
| Pagamento | Pix pelo Mercado Pago (ou outro gateway com Pix) | Cartão sai caro para cobrar R$ 1,99. |

## Dados

```
sorteio      (id, codigo, tipo, titulo, valor, data, modo, plano, pago, chave_admin_hash, criado_em)
participante (id, sorteio_id, nome, telefone, chave_hash, entrou_via, entrou_em, desejos)
restricao    (sorteio_id, participante_a, participante_b)
par          (sorteio_id, quem_tira, quem_e_tirado)
```

- `chave_admin_hash`: o organizador não precisa de conta. Ao criar o sorteio ele recebe um link secreto de administração. Login pode vir depois.
- Chaves são guardadas só como hash, nunca em texto puro.
- A tabela `par` nunca é exposta em rota nenhuma do organizador.

## Rotas principais

```
POST /sorteios                      cria o sorteio (organizador)
POST /sorteios/:codigo/sortear      faz o sorteio (organizador, após pagamento se Plus)
GET  /sorteios/:codigo/status       quem entrou (organizador)
POST /sorteios/:codigo/liberar      libera um nome (organizador)
GET  /s/:codigo                     dados públicos do evento + nomes livres (participante)
POST /s/:codigo/entrar              trava o nome e devolve a chave (participante, modo nome)
GET  /s/:codigo/resultado           devolve quem a pessoa tirou, mediante a chave
POST /webhook/whatsapp              mensagens recebidas pelo número oficial
POST /webhook/pix                   confirmação de pagamento
```

## Sorteio com restrições

Embaralha a ordem e tenta encaixar cada pessoa com alguém livre que não seja ela mesma nem uma restrição, voltando atrás quando trava. Para grupos de família (até umas 50 pessoas) é instantâneo. Se não existir combinação possível, avisa o organizador para tirar uma regra. O protótipo já usa esse algoritmo.

## Etapas de construção

1. **Protótipo** (feito): `prototipo/index.html`.
2. **Versão grátis de verdade:** React + servidor + banco, só modo nome, sem pagamento. Dá para usar no Natal da família.
3. **Pix:** cobrança de R$ 1,99 para mais de 5 pessoas.
4. **WhatsApp:** número de teste da Meta primeiro (só 5 destinatários), depois número oficial.
5. **Anúncios** no modo grátis.
