-- Schema inicial do Landing Page Builder (multi-tenant)
-- Rode no SQL Editor do Supabase ou via `supabase db push`.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Tabelas
-- ---------------------------------------------------------------------------

create table public.sites (
  id            uuid primary key default gen_random_uuid(),
  slug          text not null unique check (slug ~ '^[a-z0-9-]{2,60}$'),
  name          text not null,
  custom_domain text unique,
  published     boolean not null default false,
  theme         jsonb not null default '{"primary": "#0ea5e9"}',
  created_at    timestamptz not null default now()
);

create table public.sections (
  id       uuid primary key default gen_random_uuid(),
  site_id  uuid not null references public.sites (id) on delete cascade,
  key      text not null check (key in ('hero','about','services','gallery','location','contact')),
  enabled  boolean not null default true,
  position integer not null default 0,
  content  jsonb not null default '{}',
  unique (site_id, key)
);

create table public.bio_pages (
  site_id      uuid primary key references public.sites (id) on delete cascade,
  enabled      boolean not null default false,
  display_name text not null default '',
  tagline      text not null default '',
  avatar_url   text not null default ''
);

create table public.bio_links (
  id       uuid primary key default gen_random_uuid(),
  site_id  uuid not null references public.sites (id) on delete cascade,
  label    text not null,
  url      text not null,
  position integer not null default 0,
  enabled  boolean not null default true
);

create table public.site_members (
  site_id    uuid not null references public.sites (id) on delete cascade,
  user_id    uuid not null references auth.users (id) on delete cascade,
  role       text not null default 'owner' check (role in ('owner','editor')),
  created_at timestamptz not null default now(),
  primary key (site_id, user_id)
);

create index sections_site_idx on public.sections (site_id, position);
create index bio_links_site_idx on public.bio_links (site_id, position);
create index site_members_user_idx on public.site_members (user_id);

-- ---------------------------------------------------------------------------
-- Seções padrão criadas junto com o site
-- ---------------------------------------------------------------------------

create or replace function public.create_default_site_content()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.sections (site_id, key, enabled, position, content) values
    (new.id, 'hero',     true,  0, '{"title":"Bem-vindo","subtitle":"Apresente seu negócio em uma frase.","image_url":"","cta_label":"Fale conosco","cta_url":"#contact"}'),
    (new.id, 'about',    true,  1, '{"title":"Sobre nós","text":"Conte a história do seu negócio aqui.","image_url":""}'),
    (new.id, 'services', true,  2, '{"title":"Serviços","items":[]}'),
    (new.id, 'gallery',  false, 3, '{"title":"Galeria","images":[]}'),
    (new.id, 'location', true,  4, '{"title":"Onde estamos","address":"","maps_embed_url":""}'),
    (new.id, 'contact',  true,  5, '{"title":"Contato","phone":"","whatsapp":"","email":"","instagram":"","facebook":""}');

  insert into public.bio_pages (site_id, display_name) values (new.id, new.name);

  return new;
end;
$$;

create trigger sites_create_defaults
  after insert on public.sites
  for each row execute function public.create_default_site_content();

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

alter table public.sites        enable row level security;
alter table public.sections     enable row level security;
alter table public.bio_pages    enable row level security;
alter table public.bio_links    enable row level security;
alter table public.site_members enable row level security;

create or replace function public.is_site_member(target_site uuid)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists (
    select 1 from public.site_members
    where site_id = target_site and user_id = auth.uid()
  );
$$;

-- Leitura pública: apenas sites publicados (e seu conteúdo).
create policy "public read published sites"
  on public.sites for select
  using (published or public.is_site_member(id));

create policy "public read sections of published sites"
  on public.sections for select
  using (
    exists (select 1 from public.sites s where s.id = site_id and s.published)
    or public.is_site_member(site_id)
  );

create policy "public read bio of published sites"
  on public.bio_pages for select
  using (
    exists (select 1 from public.sites s where s.id = site_id and s.published)
    or public.is_site_member(site_id)
  );

create policy "public read bio links of published sites"
  on public.bio_links for select
  using (
    exists (select 1 from public.sites s where s.id = site_id and s.published)
    or public.is_site_member(site_id)
  );

-- Escrita: apenas membros do site.
create policy "members update site"
  on public.sites for update
  using (public.is_site_member(id))
  with check (public.is_site_member(id));

create policy "members write sections"
  on public.sections for all
  using (public.is_site_member(site_id))
  with check (public.is_site_member(site_id));

create policy "members write bio page"
  on public.bio_pages for all
  using (public.is_site_member(site_id))
  with check (public.is_site_member(site_id));

create policy "members write bio links"
  on public.bio_links for all
  using (public.is_site_member(site_id))
  with check (public.is_site_member(site_id));

-- Cada usuário enxerga apenas os próprios vínculos.
create policy "members read own memberships"
  on public.site_members for select
  using (user_id = auth.uid());

-- ---------------------------------------------------------------------------
-- Storage: bucket público para imagens dos sites
-- ---------------------------------------------------------------------------

insert into storage.buckets (id, name, public)
values ('images', 'images', true)
on conflict (id) do nothing;

create policy "public read images"
  on storage.objects for select
  using (bucket_id = 'images');

-- Upload permitido apenas dentro da pasta do site que o usuário administra
-- (caminho: <site_id>/arquivo.jpg).
create policy "members upload images"
  on storage.objects for insert
  with check (
    bucket_id = 'images'
    and public.is_site_member(((storage.foldername(name))[1])::uuid)
  );

create policy "members delete images"
  on storage.objects for delete
  using (
    bucket_id = 'images'
    and public.is_site_member(((storage.foldername(name))[1])::uuid)
  );
