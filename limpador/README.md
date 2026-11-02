# 🧹 LimpaPC

Programa com interface gráfica para **analisar o computador e liberar espaço em disco e memória RAM**.
Funciona no **Windows** (foco principal), **Linux** e **macOS**. Pode ser usado de três formas:
portátil (`LimpaPC.exe`, sem instalar), com instalador (`LimpaPC-Setup.exe`) ou direto pelo Python.

## O que ele faz

| Aba | Função |
|---|---|
| **Início** | Uso de cada disco e da RAM, tamanho da Lixeira (com botão **Esvaziar Lixeira**), escolha das pastas a analisar e atalhos de limpeza rápida. |
| **Lixo e temporários** | Temporários do usuário e do Windows, cache do Windows Update, caches de navegadores (Chrome, Edge, Firefox, Brave, Opera, Vivaldi), miniaturas, relatórios de erro, crash dumps, caches de shaders (DirectX/NVIDIA/AMD), npm/pip, Teams, Discord, Spotify, Windows.old e a Lixeira. |
| **Arquivos grandes** | Lista os maiores arquivos acima do tamanho mínimo escolhido. |
| **Arquivos repetidos** | Encontra arquivos de conteúdo idêntico (tamanho → hash parcial → hash completo BLAKE2). Mantém automaticamente 1 cópia por grupo (a mais antiga, a mais recente ou a de caminho mais curto) e **nunca deixa apagar todas as cópias**. |
| **Arquivos antigos** | Arquivos não abertos/modificados há mais de N dias. |
| **Restos de programas** | Pastas em Program Files, ProgramData e AppData (e chaves em `HKCU\Software`) que não pertencem a nenhum programa instalado e não são usadas há algum tempo, além de entradas de desinstalação quebradas. Chaves do registro ganham **backup .reg automático** antes de serem apagadas. |
| **Programas** | Programas instalados com tamanho, data de instalação e **último uso** (via Prefetch e UserAssist do Windows). Os pouco usados aparecem primeiro, e o botão **Desinstalar** abre o desinstalador oficial de cada um. |
| **Memória RAM** | Processos abertos agrupados por programa e ordenados por consumo de RAM. Permite finalizar processos e **liberar memória ociosa** (Windows). Processos essenciais do sistema ficam protegidos. |
| **Inicialização** | Programas que abrem junto com o sistema. Dá para desativá-los ou reativá-los, do mesmo jeito que o Gerenciador de Tarefas faz. |

Em todas as listas você pode marcar um ou vários itens (clicando no ☐, com *Marcar tudo* ou selecionando
linhas e apertando **Espaço**), ordenar por coluna, abrir o local do arquivo (duplo clique) e apagar.

### Segurança
- Por padrão, os arquivos apagados vão para a **Lixeira**, então dá para recuperar. A opção fica na aba Início.
- Pastas críticas do sistema (`C:\Windows`, raízes de disco, `Program Files`, pasta do usuário, `/usr`, `/etc`, `~/.ssh`…) são **bloqueadas** e nunca são apagadas.
- Sempre aparece uma confirmação antes de qualquer ação, mostrando quantos itens e quanto espaço serão liberados.
- Todas as ações ficam registradas em `historico.log` (botão *Ver histórico de ações*).
  - Windows: `%LOCALAPPDATA%\LimpaPC\`
  - Linux: `~/.local/share/limpapc/`

> **Dica:** para limpar pastas do sistema (Temp do Windows, cache do Windows Update, itens de inicialização
> de todos os usuários), use **Reabrir como administrador** na aba Início.

## Como usar

### Opção 1: baixar o .exe pronto (Windows)
Cada push no GitHub roda o workflow **Build LimpaPC (Windows)** (*Actions* → execução mais recente →
*Artifacts* → `LimpaPC-Windows`). O pacote traz:
- `LimpaPC.exe`: versão portátil, é só dar dois cliques;
- `LimpaPC-Setup.exe`: instalador com atalho no Menu Iniciar e na Área de Trabalho.

O workflow também pode ser disparado manualmente em *Actions → Build LimpaPC (Windows) → Run workflow*.

### Opção 2: gerar o .exe no seu PC
1. Instale o [Python 3.10+](https://www.python.org/downloads/) (marque **Add python.exe to PATH**).
2. Dê dois cliques em `build_windows.bat`. O executável fica em `dist\LimpaPC.exe`.
3. (Opcional) Abra `installer.iss` no [Inno Setup](https://jrsoftware.org/isdl.php) e clique em *Compile* para gerar o instalador.

### Opção 3: rodar direto com Python
```bash
pip install -r requirements.txt   # opcional (psutil e send2trash)
python main.py
```
No Windows também dá para usar o `LimpaPC.bat`. No Linux é preciso ter o tkinter (`sudo apt install python3-tk`).

## Estrutura
```
limpador/
├── main.py              # ponto de entrada
├── limpapc/
│   ├── gui.py           # interface (tkinter)
│   ├── scanners.py      # arquivos grandes, repetidos, antigos, lixo
│   ├── system.py        # programas, restos, processos, inicialização, lixeira
│   └── utils.py         # formatação, proteção de caminhos, apagar/Lixeira
├── build_windows.bat    # gera o .exe com PyInstaller
├── installer.iss        # instalador (Inno Setup)
└── requirements.txt
```
