<p align="center"><img src="assets/icon.png" width="96" alt="LimpaPC"></p>
<h1 align="center">LimpaPC</h1>
<p align="center"><b>Limpeza, otimização e recuperação de arquivos para o seu computador.</b><br>
Gratuito · código aberto · sem anúncios · sem coleta de dados</p>

<p align="center">
  <a href="https://github.com/gabrielsarzi/teste/releases/latest"><b>⬇ Baixar para Windows</b></a>
</p>

---

## Recursos

| | |
|---|---|
| 🏠 **Painel** | Análise completa em 1 clique, nota de saúde do PC (0 a 100), uso de disco, RAM e Lixeira, e o botão "Limpar recomendado". |
| ✨ **Lixo e cache** | Temporários, caches de navegadores (Chrome, Edge, Firefox, Brave, Opera, Vivaldi), Windows Update, miniaturas, relatórios de erro, crash dumps, caches de shaders, npm/pip, Teams, Discord, Spotify e Windows.old. |
| 🥧 **Mapa do disco** | O tamanho de cada pasta, para navegar e apagar (no estilo TreeSize), com um gráfico de espaço por tipo de arquivo. |
| 📄 **Arquivos grandes e antigos** | Os maiores arquivos e os que não são usados há meses ou anos. |
| 📑 **Arquivos repetidos** | Comparação byte a byte (hash BLAKE2). Mantém 1 cópia por grupo e nunca deixa apagar todas. |
| 🧩 **Programas** | Tamanho, data de instalação e **último uso** de cada programa. Os sem uso aparecem primeiro e dá para desinstalar dali mesmo. |
| 📦 **Restos de programas** | Pastas e chaves do registro deixadas por programas desinstalados, com backup automático (.reg). |
| ⏻ **Inicialização** | Ativa ou desativa o que abre junto com o Windows, como o Gerenciador de Tarefas faz. |
| 🧠 **Memória RAM** | O que está consumindo memória, com opção de finalizar programas e liberar memória ociosa. |
| 🔧 **Ferramentas** | Desativar hibernação (libera GBs), limpeza profunda do Windows Update (DISM), Limpeza de Disco, Sensor de Armazenamento, DNS e mais. |
| 🗑 **Lixeira** | Lista o que está na Lixeira com o local original e restaura com 1 clique. |
| 🛟 **Recuperar apagados** | Encontra arquivos apagados de vez (Shift+Delete ou Lixeira esvaziada) lendo a tabela NTFS do disco e mostra a chance de recuperação de cada um. Para pendrives e cartões FAT32/exFAT há a **busca por assinatura**, que encontra fotos JPG/PNG, vídeos MP4/MOV, PDFs e ZIP/Office. |

Também tem: modo claro e escuro, busca e exportação CSV em todas as listas, configurações salvas,
pastas de exclusão, histórico de ações e aviso automático de nova versão.

## Segurança

- Arquivos apagados vão para a **Lixeira** por padrão.
- Pastas críticas do sistema são **bloqueadas** (`C:\Windows`, raízes de disco, `Program Files`, pasta do usuário, `/usr`, `/etc`, `~/.ssh`…).
- Sempre há confirmação antes de qualquer ação, mostrando quantos itens e quanto espaço.
- Toda ação fica registrada em `%LOCALAPPDATA%\LimpaPC\historico.log`.
- **Privacidade:** nada sai do seu computador. A internet só é usada para verificar se há versão nova, e isso pode ser desligado nas Configurações.

### Sobre a recuperação de arquivos
- Funciona melhor em **HDs, pendrives e cartões de memória**, e quanto antes, melhor. Evite gravar na unidade até recuperar.
- Em **SSDs** o próprio disco costuma zerar os dados apagados (TRIM). Nesse caso a recuperação geralmente não é possível. O LimpaPC detecta o SSD e avisa.
- Sempre salve os arquivos recuperados em **outra unidade**. O programa bloqueia salvar na mesma.
- A leitura direta do disco exige executar **como administrador**.

## Como usar

**Windows:** baixe o `LimpaPC-Setup.exe` (instalador) ou o `LimpaPC.exe` (portátil) na página de
[Releases](https://github.com/gabrielsarzi/teste/releases/latest). Se aparecer "O Windows protegeu o
computador", clique em *Mais informações → Executar assim mesmo*.

**Com Python (Windows, Linux ou macOS):**
```bash
pip install -r requirements.txt   # opcional
python main.py
```
No Linux é preciso ter o tkinter instalado (`sudo apt install python3-tk`).

## Desenvolvimento

```
limpador/
├── main.py                  # ponto de entrada
├── limpapc/
│   ├── gui.py               # janela, menu lateral, Painel, Mapa do disco, Ferramentas, Configurações, Sobre
│   ├── pages.py             # páginas de listas (lixo, arquivos, programas, RAM, inicialização)
│   ├── recovery_pages.py    # páginas de Lixeira e recuperação
│   ├── theme.py / widgets.py# tema claro/escuro, ícones vetoriais e componentes visuais
│   ├── scanners.py          # arquivos grandes, repetidos, antigos e lixo
│   ├── analyzer.py          # mapa do disco
│   ├── recovery.py          # Lixeira, leitor NTFS e busca por assinatura
│   ├── system.py            # programas, restos, processos, inicialização e Lixeira
│   ├── tools.py / update.py / settings.py / utils.py
├── tools/                   # geração de ícone e metadados de versão
├── installer.iss            # instalador (Inno Setup)
└── build_windows.bat        # build local do .exe
```

Cada push em `limpador/` dispara o GitHub Actions, que gera o `.exe` e o instalador e publica uma nova
versão em Releases automaticamente.

## Licença

[MIT](LICENSE). Use por sua conta e risco e revise sempre o que vai apagar.
