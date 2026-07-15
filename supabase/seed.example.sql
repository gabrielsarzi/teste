-- Exemplo de como criar um cliente novo.
-- 1. Crie o usuário do cliente em Authentication -> Users (ou convide por e-mail).
-- 2. Rode o bloco abaixo trocando slug/nome e o e-mail do usuário.

with new_site as (
  insert into public.sites (slug, name, published)
  values ('padaria-do-joao', 'Padaria do João', true)
  returning id
)
insert into public.site_members (site_id, user_id, role)
select new_site.id, u.id, 'owner'
from new_site
join auth.users u on u.email = 'cliente@exemplo.com';

-- Pronto: as seções padrão e a página bio são criadas automaticamente
-- pelo trigger. O cliente já pode entrar em /admin e editar tudo.
