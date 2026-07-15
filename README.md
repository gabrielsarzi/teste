# Landing Page Builder

Base multi-tenant para criação de sites (landing pages) para pequenas empresas.
Um único sistema serve todos os clientes: cada empresa é um registro no banco,
com seu próprio endereço (`/slug` ou domínio próprio) e painel para editar tudo
sem tocar em código.

## Funcionalidades

- **Landing page por cliente** com seções: início (hero), sobre, serviços,
  galeria de fotos, localização (Google Maps) e contato (WhatsApp, telefone,
  e-mail, redes sociais).
- **Seções ativáveis/desativáveis** pelo painel — não quer galeria? Desliga o
  toggle e ela some do site.
- **Painel administrativo** (`/admin`): o cliente faz login e edita textos,
  imagens (com upload), serviços e cores.
- **Página "link na bio"** (`/slug/bio`) estilo Linktree: avatar, frase e
  lista de botões, tudo configurável no painel.
- **Domínio próprio por cliente**: o middleware resolve o domínio e serve o
  site certo sem mostrar o slug.
- **Mobile-first**: tudo responsivo por padrão (Tailwind CSS).

## Stack

- [Next.js 15](https://nextjs.org) (App Router) + TypeScript + Tailwind CSS 4
- [Supabase](https://supabase.com): banco Postgres, autenticação e storage de
  imagens, com Row Level Security isolando cada cliente

## Como rodar

1. Crie um projeto no [Supabase](https://supabase.com) (plano grátis serve).
2. No SQL Editor do Supabase, rode `supabase/migrations/0001_init.sql`.
3. Copie `.env.example` para `.env.local` e preencha com a URL e a anon key do
   projeto (Project Settings → API).
4. Instale e rode:

   ```bash
   npm install
   npm run dev
   ```

## Como criar um cliente novo

1. Crie o usuário do cliente em **Authentication → Users** no Supabase.
2. Rode o SQL de `supabase/seed.example.sql` ajustando slug, nome e e-mail.
3. Pronto: as seções padrão e a página bio são criadas automaticamente. O
   cliente acessa `/login`, entra no painel e edita tudo.

## Estrutura

```
src/
  app/
    [slug]/            # site público do cliente
    [slug]/bio/        # página "link na bio"
    admin/             # painel (protegido por login)
    login/             # tela de login
  components/
    sections/          # uma pasta = uma seção da landing page
    admin/             # editores usados no painel
  lib/
    types.ts           # modelo de dados central
    queries.ts         # leituras do Supabase
    supabase/          # clientes (server, browser, middleware)
supabase/
  migrations/          # schema do banco (tabelas + RLS + storage)
```

Para adicionar um tipo de seção novo: incluir a key em `types.ts`, criar o
componente em `components/sections/`, registrar no `SectionRenderer` e no
formulário do painel, e adicionar a key no check da tabela `sections`.
