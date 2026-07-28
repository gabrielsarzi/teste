# Hub de Projetos (local)

Um painel **local e privado** para organizar seus projetos: chaves/APIs, um quadro
estilo Kanban (Agora / Depois / Inspiração / Erros pra ver / Feito) e anotações livres —
tudo por projeto. Roda só na sua máquina (`127.0.0.1`), **nada é exposto na internet**.

## Como abrir (Windows)

1. Entre na pasta `hub`.
2. Dê **duplo-clique em `Iniciar.bat`**.
3. Uma janela preta abre e o navegador abre sozinho no app.
4. Para **fechar/encerrar**: feche aquela janela preta.

> O `Iniciar.bat` procura sozinho **Python** ou **Node.js** na sua máquina e usa
> qualquer um dos dois. Se não tiver nenhum, ele mostra o link pra instalar (basta um).
>
> Dica: você pode criar um atalho do `Iniciar.bat` na Área de Trabalho
> (botão direito → Enviar para → Área de trabalho).

## O que dá pra fazer

- **Projetos** (barra da esquerda): criar, renomear, escolher cor, apagar.
- **Quadro**: cartões que você arrasta entre as colunas; cada cartão tem título,
  descrição, tags e um link opcional. Use as colunas pra separar o que é pra
  **agora**, o que é pra **depois**, o que é **inspiração** e os **erros pra ver**.
- **Chaves / APIs**: guarde chaves com rótulo, valor (com botão mostrar/ocultar e
  copiar) e observações.
- **Anotações**: um espaço de texto livre por projeto, que salva sozinho.

Tudo é salvo automaticamente enquanto você mexe.

## Segurança das chaves 🔒

As chaves ficam em `data/<projeto>/secrets.local.json`, um arquivo **ignorado pelo git**
(veja `.gitignore`). Ou seja: **nunca vão para o GitHub**. Ficam só no seu computador.

Consequência importante: numa sessão nova do Claude (ambiente limpo), ele **não vê o
valor real das chaves** — só sabe que a chave existe. Isso é de propósito, é o
comportamento seguro. Você gerencia os valores aqui no app.

## Como o Claude "alimenta" em paralelo

Os dados ficam em arquivos simples dentro de `data/`:

```
data/
  projects.json              <- lista de projetos (sem segredos)
  <projeto>/
    board.json               <- o quadro Kanban
    notes.md                 <- as anotações
    secrets.local.json       <- suas chaves (LOCAL, ignorado pelo git)
    secrets.example.json     <- só um modelo
```

Quando estivermos trabalhando num projeto, o Claude edita esses mesmos arquivos
(`board.json`, `notes.md`, `projects.json`) — por exemplo, registrando um erro na
coluna "Erros pra ver" ou anotando uma decisão. Você dá `git pull` (ou já vê ao
reabrir o app) e as atualizações aparecem. Os segredos ele não toca.

## Detalhes técnicos

- Backend: `server.py` (Python, biblioteca padrão) ou `server.js` (Node) — mesma API.
- Sem dependências para instalar.
- Porta padrão: `4577` (mude com a variável de ambiente `HUB_PORT` se precisar).
- O servidor serve **apenas** o `index.html` como arquivo estático; nada mais é
  acessível por GET direto (nem o código do servidor, nem os segredos).
