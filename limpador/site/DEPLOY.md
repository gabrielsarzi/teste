# Publicar o site do LimpaOne

O site é estático (HTML + CSS + um pouco de JS), sem etapa de build. Basta servir a pasta
`limpeza-pc/site` do repositório `gabrielsarzi/teste`.

Endereço final: **https://limpaone.sarzitecnologia.com.br**

---

## Opção 1 — Cloudflare Pages (recomendado)

O domínio `sarzitecnologia.com.br` já está na Cloudflare, então o certificado HTTPS e o DNS do
subdomínio são criados automaticamente.

### 1. Criar o projeto

1. Entre no painel da Cloudflare e abra **Workers & Pages**.
2. Clique em **Create** (Criar) → aba **Pages** → **Connect to Git** (Importar um repositório Git).
3. Autorize o GitHub, se for a primeira vez, e escolha o repositório **`gabrielsarzi/teste`**.
4. Em **Set up builds and deployments**, preencha:

   | Campo                         | Valor                                    |
   |-------------------------------|------------------------------------------|
   | Project name                  | `limpaone` (vira `limpaone.pages.dev`)   |
   | Production branch             | `main` (a branch que tem a pasta do site) |
   | Framework preset              | **None**                                 |
   | Build command                 | *(deixe vazio)*                          |
   | Build output directory        | `limpeza-pc/site`                        |
   | Root directory (advanced)     | *(deixe vazio)*                          |

5. Clique em **Save and Deploy**. Em menos de um minuto o site fica no ar em
   `https://limpaone.pages.dev`.

> **Importante:** a *Production branch* precisa ser a branch que contém `limpeza-pc/site`.
> Se o site ainda estiver numa branch de trabalho, faça o merge em `main` primeiro (ou escolha
> temporariamente a outra branch e troque depois em **Settings → Builds & deployments →
> Branch control**). Commits em outras branches geram apenas *previews* com URL própria.

### 2. Ligar o subdomínio

1. No projeto, abra **Custom domains** → **Set up a custom domain**.
2. Digite **`limpaone.sarzitecnologia.com.br`** e clique em **Continue**.
3. Como o domínio já está nesta conta da Cloudflare, ela oferece criar o registro DNS
   (um `CNAME limpaone → limpaone.pages.dev`) automaticamente. Confirme em **Activate domain**.
4. Aguarde o status ficar **Active** (normalmente 1 a 5 minutos). O certificado HTTPS é emitido
   sozinho.

Pronto: cada `git push` na branch de produção que altere o site publica a nova versão
automaticamente.

### Dicas

- Para não gastar builds com mudanças fora do site, em **Settings → Builds & deployments →
  Build watch paths** use *Include paths* = `limpeza-pc/site/*`.
- Se a pasta mudar de nome de novo, atualize o **Build output directory** em
  **Settings → Builds & deployments**.
- O endereço canônico e as imagens de compartilhamento (`og:url`, `og:image`) já apontam para
  `https://limpaone.sarzitecnologia.com.br`. Se o domínio mudar, troque essas URLs no
  `<head>` do `index.html`.

---

## Opção 2 — GitHub Pages (alternativa)

O GitHub Pages só publica a raiz do repositório ou a pasta `/docs`, então para servir
`limpeza-pc/site` o caminho mais simples é um workflow do GitHub Actions:

1. Crie o arquivo `.github/workflows/site.yml` na raiz do repositório:

   ```yaml
   name: Site
   on:
     push:
       branches: [main]
       paths: ["limpeza-pc/site/**"]
     workflow_dispatch:
   permissions:
     contents: read
     pages: write
     id-token: write
   concurrency: { group: pages, cancel-in-progress: true }
   jobs:
     deploy:
       runs-on: ubuntu-latest
       environment: { name: github-pages, url: "${{ steps.d.outputs.page_url }}" }
       steps:
         - uses: actions/checkout@v4
         - uses: actions/configure-pages@v5
         - uses: actions/upload-pages-artifact@v3
           with: { path: limpeza-pc/site }
         - id: d
           uses: actions/deploy-pages@v4
   ```

2. No GitHub: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Faça um push (ou rode o workflow manualmente em **Actions**).
4. Para o subdomínio: em **Settings → Pages → Custom domain** digite
   `limpaone.sarzitecnologia.com.br`, e na Cloudflare crie o DNS
   `CNAME limpaone → gabrielsarzi.github.io` (com o proxy **desligado**, nuvem cinza, até o
   GitHub emitir o certificado; depois marque **Enforce HTTPS**).

---

## Atualizar os prints do app

Os prints em `img/` são gerados pelo script `tools/screenshots.py` (Linux com Xvfb, ImageMagick e
Pillow), que abre o app com dados de demonstração — nada é escaneado nem apagado:

```bash
cd limpeza-pc
HOME=/tmp/limpaone-home xvfb-run -a -s "-screen 0 1280x800x24" python3.12 tools/screenshots.py
python3 tools/screenshots.py --brand   # favicon, logo e og.png a partir de assets/icon.png
```

Rode o `--brand` depois dos prints (o `og.png` usa o `img/painel-escuro.png`).

## Configurar antes de divulgar

- **Doações:** no `index.html`, procure `CONFIGURAR: link de doação / PIX` e troque o `href="#"`
  do botão “Fazer uma doação”.
