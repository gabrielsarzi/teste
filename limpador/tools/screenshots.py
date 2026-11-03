"""Gera os prints do app e as imagens de marca usadas no site (site/img/).

Abre o app de verdade num servidor X virtual, mostra cada página e injeta DADOS DE DEMONSTRAÇÃO
(nada é escaneado, apagado ou alterado no sistema). Páginas que ainda não existem são puladas.

Uso (Linux, precisa de Xvfb, ImageMagick e Pillow):
    cd limpeza-pc   # (ou limpador, antes da renomeação)
    HOME=/tmp/limpaone-home xvfb-run -a -s "-screen 0 1280x800x24" python3.12 tools/screenshots.py [--out site/img]
          [--only painel,lixo]

Imagens de marca (favicon, logo e og.png 1200×630) a partir de assets/icon.png — não precisa de Xvfb:
    python3 tools/screenshots.py --brand
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=os.path.join(ROOT, "site", "img"))
ap.add_argument("--only", default="", help="lista de arquivos (sem .png) separados por vírgula")
ap.add_argument("--wait", type=int, default=900, help="ms de espera antes de cada print")
ap.add_argument("--brand", action="store_true", help="só gera favicon, logo e og.png a partir de assets/icon.png")
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)


# ------------------------------------------------------------------ imagens de marca
def make_brand(out=args.out, name="LimpaOne"):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    site = os.path.dirname(os.path.abspath(out))
    icon = Image.open(os.path.join(ROOT, "assets", "icon.png")).convert("RGBA")
    big = icon.resize((512, 512), Image.LANCZOS) if icon.width < 512 else icon
    for size, fname in ((128, "logo.png"), (180, "apple-touch-icon.png"), (32, "favicon-32.png")):
        big.resize((size, size), Image.LANCZOS).save(os.path.join(out, fname), optimize=True)
    big.save(os.path.join(site, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

    def font(weight, size):
        for path in (f"/usr/share/fonts/opentype/inter/Inter-{weight}.otf", f"C:/Windows/Fonts/segoeui{'b' if weight != 'Medium' else ''}.ttf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    W_, H_ = 1200, 630
    img = Image.new("RGB", (W_, H_), "#0f1426")
    glow = Image.new("RGB", (W_, H_), "#0f1426")
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-260, -320, 560, 360), fill="#3b2f9e")
    gd.ellipse((760, 330, 1500, 900), fill="#0f5f78")
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(140)), 0.9)
    d = ImageDraw.Draw(img)
    # print do app à direita, cortado pela borda
    shot = os.path.join(out, "painel-escuro.png")
    if os.path.exists(shot):
        sc = Image.open(shot).convert("RGB")
        sc = sc.resize((int(sc.width * 0.62), int(sc.height * 0.62)), Image.LANCZOS)
        x0, y0 = 700, 150
        mask = Image.new("L", sc.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, sc.width, sc.height), 16, fill=255)
        shadow = Image.new("L", (W_, H_), 0)
        ImageDraw.Draw(shadow).rounded_rectangle((x0 + 10, y0 + 24, x0 + sc.width + 10, y0 + sc.height + 24), 16, fill=150)
        img.paste(Image.new("RGB", (W_, H_), "#05070f"), (0, 0), shadow.filter(ImageFilter.GaussianBlur(24)))
        img.paste(sc, (x0, y0), mask)
        d.rounded_rectangle((x0 - 1, y0 - 1, x0 + sc.width, y0 + sc.height), 16, outline="#4b4fc9", width=2)
    ic = big.resize((132, 132), Image.LANCZOS)
    img.paste(ic, (80, 92), ic)
    d.text((80, 262), name, font=font("ExtraBold", 92), fill="#ffffff")
    d.text((82, 378), "Limpeza, otimização e", font=font("SemiBold", 36), fill="#c9cff0")
    d.text((82, 424), "recuperação de arquivos", font=font("SemiBold", 36), fill="#c9cff0")
    d.text((82, 470), "para Windows 10 e 11", font=font("SemiBold", 36), fill="#c9cff0")
    x = 82
    f = font("SemiBold", 22)
    for label in ("Grátis", "Código aberto", "Sem anúncios"):
        w = d.textlength(label, font=f)
        d.rounded_rectangle((x, 540, x + w + 32, 580), 20, fill="#1d2546", outline="#3a4377")
        d.text((x + 16, 547), label, font=f, fill="#e6e9f7")
        x += w + 44
    bar = Image.linear_gradient("L").rotate(90).resize((W_, 8))
    grad = Image.composite(Image.new("RGB", (W_, 8), "#22d3ee"), Image.new("RGB", (W_, 8), "#6d5dfc"), bar)
    img.paste(grad, (0, H_ - 8))
    img.save(os.path.join(out, "og.png"), optimize=True)
    print("imagens de marca geradas em", out, "e", os.path.join(site, "favicon.ico"))


if args.brand:
    make_brand()
    sys.exit(0)
W, H = 1280, 800

GB, MB, KB = 1024 ** 3, 1024 ** 2, 1024
NOW = time.time()
DAY = 86400

# ------------------------------------------------------------------ dados falsos do "sistema"
# Substituem leituras reais (discos, RAM, Lixeira, unidades) para os prints parecerem de um PC com Windows.
FAKE_DISKS = [("C:\\", 476 * GB, 389 * GB, 87 * GB), ("D:\\", 931 * GB, 512 * GB, 419 * GB),
              ("E:\\  (pendrive)", 58 * GB, 21 * GB, 37 * GB)]
FAKE_MEM = (16 * GB, int(11.4 * GB))
FAKE_BIN = (int(2.7 * GB), 148)
FAKE_VOLUMES = [("C:  Disco local  (NTFS)", "\\\\.\\C:", "C:\\"), ("D:  Dados  (NTFS)", "\\\\.\\D:", "D:\\"),
                ("E:  PENDRIVE  (exFAT)", "\\\\.\\E:", "E:\\")]

from limpapc import gui, pages, recovery_pages  # noqa: E402
from limpapc.analyzer import CATEGORY_NAMES, Node  # noqa: E402
from limpapc.utils import Item, fmt_date, fmt_size  # noqa: E402

for mod in (gui, pages):
    for name, val in (("disks", lambda: FAKE_DISKS), ("memory_info", lambda: FAKE_MEM),
                      ("recycle_bin_info", lambda: FAKE_BIN)):
        if hasattr(mod, name):
            setattr(mod, name, val)
recovery_pages.list_volumes = lambda: FAKE_VOLUMES
gui.App.check_updates = lambda self, *a, **k: None      # nada de internet
try:  # a página de instalar/atualizar só mostra o catálogo quando o winget existe
    from limpapc import apps_pages
    apps_pages.available = lambda: True
except Exception:  # noqa: BLE001
    apps_pages = None


def ago(days):
    return NOW - days * DAY


def files(rows, folder_default=""):
    """rows: (nome, tamanho, dias desde modificação, dias desde uso, pasta[, marcado])"""
    out = []
    for r in rows:
        name, size, mod, use, folder = r[:5]
        out.append(Item(path=folder + "\\" + name, size=size,
                        values=(name, fmt_size(size), fmt_date(ago(mod)), fmt_date(ago(use)), folder),
                        raw=(name.lower(), size, ago(mod), ago(use), folder.lower()),
                        checked=r[5] if len(r) > 5 else False, data={"mtime": ago(mod)}))
    return out


U = "C:\\Users\\Ana"


def demo_junk():
    rows = [("Arquivos temporários do usuário", 3.1 * GB, 18342, U + "\\AppData\\Local\\Temp", True, False),
            ("Cache do Windows Update", 2.4 * GB, 1210, "C:\\Windows\\SoftwareDistribution\\Download", True, False),
            ("Lixeira", FAKE_BIN[0], FAKE_BIN[1], "Todas as unidades", True, False),
            ("Navegador — cache", 1.3 * GB, 9876, U + "\\AppData\\Local\\…\\Cache", True, False),
            ("Cache de shaders (DirectX)", 812 * MB, 2214, U + "\\AppData\\Local\\D3DSCache", True, False),
            ("Relatórios de erro do Windows", 640 * MB, 87, "C:\\ProgramData\\Microsoft\\Windows\\WER", True, False),
            ("Miniaturas do Explorador", 418 * MB, 24, U + "\\AppData\\Local\\Microsoft\\Windows\\Explorer", True, False),
            ("Crash dumps", 356 * MB, 6, U + "\\AppData\\Local\\CrashDumps", True, False),
            ("Cache do pip", 288 * MB, 1432, U + "\\AppData\\Local\\pip\\Cache", True, False),
            ("Arquivos temporários do Windows", 196 * MB, 640, "C:\\Windows\\Temp", True, False),
            ("Logs de instalação", 74 * MB, 311, "C:\\Windows\\Logs", True, False),
            ("Privacidade — histórico de navegação", 92 * MB, 14, U + "\\AppData\\Local\\…\\History", False, True),
            ("Privacidade — cookies", 18 * MB, 3, U + "\\AppData\\Local\\…\\Cookies", False, True),
            ("Privacidade — documentos recentes", 1 * MB, 212, U + "\\AppData\\Roaming\\Microsoft\\Windows\\Recent",
             False, True)]
    return [Item(path=p, size=int(s), values=(n, fmt_size(s), f"{c:,}".replace(",", "."), p),
                 raw=(n.lower(), int(s), c, p.lower()), kind="junk", checked=ck, data={"privacy": pv})
            for n, s, c, p, ck, pv in rows]


def demo_large():
    return files([("Backup do celular 2023.zip", 18.6 * GB, 410, 400, U + "\\Documents\\Backups"),
                  ("Windows 11 23H2.iso", 6.2 * GB, 380, 380, U + "\\Downloads"),
                  ("Casamento - vídeo completo.mp4", 4.8 * GB, 900, 610, "D:\\Vídeos"),
                  ("MaquinaVirtual-Linux.vdi", 4.1 * GB, 220, 160, U + "\\VirtualBox VMs\\Linux"),
                  ("Gravação da tela 2024-03-12.mkv", 2.9 * GB, 590, 590, U + "\\Videos\\Captures"),
                  ("Fotos viagem 2022 (RAW).zip", 2.3 * GB, 730, 700, "D:\\Fotos"),
                  ("instalador-jogo-setup.exe", 1.9 * GB, 120, 118, U + "\\Downloads"),
                  ("Projeto final - edição.prproj", 1.2 * GB, 300, 300, U + "\\Documents\\Projetos"),
                  ("Aulas gravadas - módulo 3.mp4", 980 * MB, 450, 440, U + "\\Videos"),
                  ("dataset-vendas-completo.csv", 760 * MB, 260, 210, U + "\\Documents\\Trabalho"),
                  ("Podcast episódio 41 (bruto).wav", 690 * MB, 520, 510, U + "\\Music\\Podcast"),
                  ("drivers-placa-de-video.exe", 612 * MB, 330, 330, U + "\\Downloads"),
                  ("Apresentação cliente final.pptx", 384 * MB, 95, 30, U + "\\Documents\\Trabalho"),
                  ("Planta da casa.dwg", 212 * MB, 800, 790, U + "\\Documents")])


def demo_old():
    return files([("Apostila concurso 2019.pdf", 86 * MB, 2100, 2000, U + "\\Documents\\Estudos"),
                  ("Fotos formatura 2018.zip", 1.4 * GB, 2400, 2300, "D:\\Fotos"),
                  ("Trabalho TCC versão final(2).docx", 12 * MB, 1900, 1800, U + "\\Documents\\Faculdade"),
                  ("setup-impressora-antiga.exe", 310 * MB, 1600, 1600, U + "\\Downloads"),
                  ("Música aniversário.mp3", 9 * MB, 1500, 1400, U + "\\Music"),
                  ("Planilha gastos 2020.xlsx", 2 * MB, 1400, 1350, U + "\\Documents"),
                  ("Backup WhatsApp 2021.zip", 2.1 * GB, 1200, 1150, U + "\\Documents\\Backups"),
                  ("Vídeo chá de bebê.mov", 3.3 * GB, 1100, 1000, "D:\\Vídeos"),
                  ("Currículo 2020.pdf", 1 * MB, 1600, 1450, U + "\\Documents"),
                  ("jogo-antigo-mods.rar", 870 * MB, 1300, 1300, U + "\\Downloads"),
                  ("Notas fiscais 2019.zip", 48 * MB, 1700, 1700, U + "\\Documents\\Finanças"),
                  ("Aula de violão 01.mp4", 640 * MB, 1250, 1240, U + "\\Videos")])


def demo_dups():
    groups = [("IMG_20230714_183022.jpg", 6.4 * MB, ["D:\\Fotos\\Praia 2023", U + "\\Pictures\\Celular",
                                                    U + "\\Downloads"]),
              ("Contrato aluguel.pdf", 2.1 * MB, [U + "\\Documents", U + "\\Downloads"]),
              ("Vídeo aniversário.mp4", 845 * MB, ["D:\\Vídeos", U + "\\Desktop"]),
              ("Relatório anual.xlsx", 3.2 * MB, [U + "\\Documents\\Trabalho", U + "\\OneDrive\\Trabalho",
                                                  U + "\\Desktop"]),
              ("instalador-office.exe", 412 * MB, [U + "\\Downloads", "D:\\Programas"])]
    out = []
    for g, (name, size, folders) in enumerate(groups, 1):
        for n, folder in enumerate(folders):
            it = files([(name, size, 200 + n * 40, 100 + n * 30, folder, n > 0)])[0]
            it.group = g
            out.append(it)
    return out


def demo_leftovers():
    rows = [("Pasta", "EditorDeFotos Pro", 1.2 * GB, 400, "C:\\Program Files\\EditorDeFotos Pro"),
            ("Pasta (AppData)", "EditorDeFotos Pro", 386 * MB, 400, U + "\\AppData\\Roaming\\EditorDeFotos"),
            ("Pasta (AppData)", "JogoCorrida", 2.4 * GB, 260, U + "\\AppData\\Local\\JogoCorrida"),
            ("Chave do registro", "JogoCorrida", 0, 260, "HKCU\\Software\\JogoCorrida"),
            ("Pasta", "ConversorVideo", 94 * MB, 510, "C:\\Program Files (x86)\\ConversorVideo"),
            ("Chave do registro", "ConversorVideo", 0, 510, "HKLM\\SOFTWARE\\WOW6432Node\\ConversorVideo"),
            ("Pasta (ProgramData)", "AntivirusTrial", 640 * MB, 700, "C:\\ProgramData\\AntivirusTrial"),
            ("Entrada sem desinstalador", "Toolbar Busca", 0, 900, "HKLM\\…\\Uninstall\\ToolbarBusca"),
            ("Atalho quebrado", "Leitor PDF antigo", 2 * KB, 820, U + "\\Desktop\\Leitor PDF.lnk")]
    return [Item(path=p, size=int(s), values=(tp, n, fmt_size(s) if s else "—", fmt_date(ago(d)), p),
                 raw=(tp, n.lower(), int(s), ago(d), p.lower()),
                 kind="regkey" if tp.startswith("Chave") else "dir", checked=True)
            for tp, n, s, d, p in rows]


def demo_programs():
    rows = [("Editor de vídeo (teste)", "3.2.1", "VideoSoft", 1.8 * GB, 420, 380, "Pouco usado"),
            ("Jogo de corrida", "1.0.44", "Estúdio Indie", 24.6 * GB, 600, 310, "Pouco usado"),
            ("Barra de ferramentas Busca", "8.1", "Busca Ltda.", 46 * MB, 900, 900, "Desinstalador ausente"),
            ("Conversor de áudio", "2.4", "AudioTools", 120 * MB, 500, 260, "Pouco usado"),
            ("Driver da impressora (antiga)", "5.0", "Impressoras S.A.", 310 * MB, 1300, 700, "Pouco usado"),
            ("GIMP", "2.10.38", "The GIMP Team", 412 * MB, 210, 95, "Pouco usado"),
            ("7-Zip", "24.08", "Igor Pavlov", 5 * MB, 300, 3, "Em uso"),
            ("LibreOffice", "24.8.2", "The Document Foundation", 1.1 * GB, 180, 1, "Em uso"),
            ("VLC media player", "3.0.21", "VideoLAN", 172 * MB, 260, 2, "Em uso"),
            ("Notepad++", "8.7", "Notepad++ Team", 16 * MB, 150, 0, "Em uso"),
            ("OBS Studio", "30.2.3", "OBS Project", 420 * MB, 120, 12, "Em uso"),
            ("Audacity", "3.6.4", "Audacity Team", 98 * MB, 220, 40, "Em uso"),
            ("Python 3.12", "3.12.7", "Python Software Foundation", 112 * MB, 90, 0, "Em uso"),
            ("Git", "2.47.0", "The Git Development Community", 340 * MB, 90, 0, "Em uso")]
    return [Item(path=n, size=int(s), values=(n, v, e, fmt_size(s), fmt_date(ago(inst)), fmt_date(ago(use)), st),
                 raw=(n.lower(), v, e.lower(), int(s), ago(inst), ago(use), st), kind="program",
                 checked=st == "Pouco usado" and inst < 1000, data={"broken": st == "Desinstalador ausente"})
            for n, v, e, s, inst, use, st in rows]


def demo_ram():
    rows = [("Navegador (32 abas)", "28", 3.2 * GB, "", "C:\\Program Files\\…\\navegador.exe"),
            ("Editor de vídeo", "1", 1.6 * GB, "", "C:\\Program Files\\VideoSoft\\editor.exe"),
            ("Jogo de corrida", "1", 1.4 * GB, "", "D:\\Jogos\\Corrida\\game.exe"),
            ("Antimalware Service Executable", "1", 412 * MB, "Sistema (protegido)", "C:\\ProgramData\\…\\MsMpEng.exe"),
            ("LibreOffice", "2", 380 * MB, "", "C:\\Program Files\\LibreOffice\\program\\soffice.bin"),
            ("Explorador de Arquivos", "1", 210 * MB, "Sistema (protegido)", "C:\\Windows\\explorer.exe"),
            ("OBS Studio", "1", 196 * MB, "", "C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"),
            ("Desktop Window Manager", "1", 150 * MB, "Sistema (protegido)", "C:\\Windows\\System32\\dwm.exe"),
            ("Chat corporativo", "6", 640 * MB, "", U + "\\AppData\\Local\\Chat\\chat.exe"),
            ("Player de música", "3", 280 * MB, "", U + "\\AppData\\Roaming\\Player\\player.exe"),
            ("Sincronização na nuvem", "1", 120 * MB, "", U + "\\AppData\\Local\\Nuvem\\sync.exe"),
            ("VLC media player", "1", 88 * MB, "", "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe")]
    rows.sort(key=lambda r: -r[2])
    return [Item(path=n, size=int(m), values=(n, i, fmt_size(m), ob, p), raw=(n.lower(), int(i), int(m), ob, p),
                 kind="process", data={"critical": bool(ob), "pids": []}) for n, i, m, ob, p in rows]


def demo_startup():
    rows = [("Chat corporativo", True, "Registro (usuário)", U + "\\AppData\\Local\\Chat\\chat.exe --minimized"),
            ("Sincronização na nuvem", True, "Registro (usuário)", U + "\\AppData\\Local\\Nuvem\\sync.exe /background"),
            ("Atualizador do leitor de PDF", True, "Tarefa agendada", "C:\\Program Files\\PDF\\updater.exe"),
            ("Player de música", True, "Pasta Inicializar", U + "\\AppData\\Roaming\\Player\\player.exe"),
            ("Launcher de jogos", True, "Registro (usuário)", "C:\\Program Files (x86)\\Launcher\\launcher.exe -silent"),
            ("Assistente da impressora", True, "Registro (todos)", "C:\\Program Files\\Impressora\\monitor.exe"),
            ("Áudio Realtek HD", True, "Registro (todos)", "C:\\Windows\\System32\\RtkAudUService64.exe"),
            ("Segurança do Windows", True, "Registro (todos)", "%windir%\\system32\\SecurityHealthSystray.exe"),
            ("Editor de vídeo — ajudante", False, "Registro (usuário)", "C:\\Program Files\\VideoSoft\\helper.exe"),
            ("Conversor de áudio", False, "Pasta Inicializar", "C:\\Program Files\\AudioTools\\tray.exe")]
    return [Item(path=n, values=(n, "Ativado" if e else "Desativado", o, c), raw=(n.lower(), e, o, c),
                 kind="startup", checked=e and n in ("Chat corporativo", "Launcher de jogos", "Player de música"),
                 data={"enabled": e}) for n, e, o, c in rows]


def demo_trash():
    rows = [("Relatório trimestral.docx", 2.4 * MB, 1, U + "\\Documents\\Trabalho"),
            ("Fotos aniversário", 1.2 * GB, 3, U + "\\Pictures"),
            ("orcamento-reforma.xlsx", 180 * KB, 4, U + "\\Desktop"),
            ("Video_20240512.mp4", 640 * MB, 6, "D:\\Vídeos"),
            ("instalador-antigo.exe", 210 * MB, 9, U + "\\Downloads"),
            ("Anotações reunião.txt", 4 * KB, 12, U + "\\Documents"),
            ("Projeto logo (versões)", 86 * MB, 15, U + "\\Documents\\Design"),
            ("Playlist viagem.m3u", 2 * KB, 20, U + "\\Music"),
            ("Boletos 2024.pdf", 1.1 * MB, 28, U + "\\Documents\\Finanças")]
    return [Item(path=p + "\\" + n, size=int(s), values=(n, fmt_size(s), fmt_date(ago(d)), p),
                 raw=(n.lower(), int(s), ago(d), p.lower()), kind="trash", checked=d < 5) for n, s, d, p in rows]


def demo_recover():
    rows = [("IMG_4021.JPG", "Imagens", 4.8 * MB, 12, "Excelente", "E:\\DCIM\\100CANON"),
            ("IMG_4022.JPG", "Imagens", 5.1 * MB, 12, "Excelente", "E:\\DCIM\\100CANON"),
            ("Contrato assinado.pdf", "Documentos", 1.3 * MB, 20, "Excelente", "C:\\Users\\Ana\\Documents"),
            ("Planilha de vendas.xlsx", "Documentos", 640 * KB, 25, "Boa", "C:\\Users\\Ana\\Documents\\Trabalho"),
            ("Video_festa.mp4", "Vídeos", 412 * MB, 30, "Boa", "C:\\Users\\Ana\\Videos"),
            ("TCC - versão final.docx", "Documentos", 3.2 * MB, 33, "Excelente", "C:\\Users\\Ana\\Desktop"),
            ("audio_reuniao.m4a", "Músicas", 38 * MB, 41, "Boa", "C:\\Users\\Ana\\Music"),
            ("Foto RG frente.png", "Imagens", 2.2 * MB, 44, "Excelente", "C:\\Users\\Ana\\Downloads"),
            ("Projeto casa.dwg", "Outros", 8.4 * MB, 60, "Boa", "C:\\Users\\Ana\\Documents"),
            ("apresentacao.pptx", "Documentos", 14 * MB, 75, "Parcial", "C:\\Users\\Ana\\Documents"),
            ("backup-antigo.zip", "Compactados", 1.1 * GB, 120, "Baixa", "C:\\Users\\Ana\\Downloads")]
    rank = {"Excelente": 0, "Boa": 1, "Parcial": 2, "Baixa": 3}
    return [Item(path=p + "\\" + n, size=int(s), values=(n, t, fmt_size(s), fmt_date(ago(d)), ch, p),
                 raw=(n.lower(), t, int(s), ago(d), rank[ch], p.lower()), kind="deleted",
                 checked=rank[ch] == 0, data={"file": None}) for n, t, s, d, ch, p in rows]


def demo_store():
    rows = [("Solitaire Collection", "4.19", 312 * MB, "Pré-instalado (bloatware)", "Microsoft.MicrosoftSolitaireCollection"),
            ("Notícias", "4.55", 64 * MB, "Pré-instalado (bloatware)", "Microsoft.BingNews"),
            ("Clima", "4.53", 38 * MB, "Pré-instalado (bloatware)", "Microsoft.BingWeather"),
            ("Introdução / Dicas", "10.2", 22 * MB, "Pré-instalado (bloatware)", "Microsoft.Getstarted"),
            ("Mixed Reality Portal", "2000.21", 180 * MB, "Pré-instalado (bloatware)", "Microsoft.MixedReality.Portal"),
            ("Hub de Comentários", "1.2", 54 * MB, "Pré-instalado (bloatware)", "Microsoft.WindowsFeedbackHub"),
            ("Mapas", "11.2", 41 * MB, "Pré-instalado (bloatware)", "Microsoft.WindowsMaps"),
            ("Calculadora", "11.24", 26 * MB, "", "Microsoft.WindowsCalculator"),
            ("Fotos", "2024.11", 410 * MB, "", "Microsoft.Windows.Photos"),
            ("Bloco de Notas", "11.24", 12 * MB, "", "Microsoft.WindowsNotepad"),
            ("Ferramenta de Captura", "11.24", 48 * MB, "", "Microsoft.ScreenSketch"),
            ("Terminal", "1.21", 96 * MB, "", "Microsoft.WindowsTerminal")]
    return [Item(path=pk, size=int(s), values=(n, v, fmt_size(s), st, pk), raw=(n.lower(), v, int(s), st, pk),
                 kind="appx", checked=bool(st)) for n, v, s, st, pk in rows]


def demo_updates():
    rows = [("7-Zip", "23.01", "24.08", "7zip.7zip", "Atualização disponível"),
            ("VLC media player", "3.0.20", "3.0.21", "VideoLAN.VLC", "Atualização disponível"),
            ("LibreOffice", "24.2.5", "24.8.2", "TheDocumentFoundation.LibreOffice", "Atualização disponível"),
            ("Notepad++", "8.6.9", "8.7", "Notepad++.Notepad++", "Atualização disponível"),
            ("Git", "2.45.2", "2.47.0", "Git.Git", "Atualização disponível"),
            ("Python 3.12", "3.12.4", "3.12.7", "Python.Python.3.12", "Atualização disponível"),
            ("OBS Studio", "30.1.2", "30.2.3", "OBSProject.OBSStudio", "Atualização disponível"),
            ("GIMP", "2.10.36", "2.10.38", "GIMP.GIMP", "Atualização disponível"),
            ("Audacity", "3.5.1", "3.6.4", "Audacity.Audacity", "Atualização disponível"),
            ("PowerToys", "0.84.1", "0.86.0", "Microsoft.PowerToys", "Atualização disponível")]
    return [Item(path=i, values=(n, a, b, i, s), raw=(n.lower(), a, b, i, s), kind="upgrade", checked=True,
                 data={"id": i}) for n, a, b, i, s in rows]


def demo_diskmap():
    def node(name, path, size, nfiles, kids=(), top=(), days=10):
        n = Node(name, path)
        n.size, n.files, n.mtime = int(size), nfiles, ago(days)
        n.children = list(kids)
        n.top_files = [(int(s), nm, ago(d)) for s, nm, d in top]
        return n

    base = U
    kids = [node("Videos", base + "\\Videos", 48 * GB, 412, days=3,
                 top=[(4.8 * GB, "Casamento.mp4", 900), (2.9 * GB, "Gravação.mkv", 590)]),
            node("Downloads", base + "\\Downloads", 31 * GB, 1834, days=0,
                 top=[(6.2 * GB, "Windows 11.iso", 380), (1.9 * GB, "jogo-setup.exe", 120)]),
            node("Documents", base + "\\Documents", 27 * GB, 9120, days=1,
                 top=[(18.6 * GB, "Backup do celular 2023.zip", 410)]),
            node("Pictures", base + "\\Pictures", 22 * GB, 15420, days=2,
                 top=[(6 * MB, "IMG_0001.jpg", 30)]),
            node("AppData", base + "\\AppData", 19 * GB, 140233, days=0,
                 top=[(300 * MB, "cache.db", 1)]),
            node("VirtualBox VMs", base + "\\VirtualBox VMs", 12 * GB, 22, days=160,
                 top=[(4.1 * GB, "Linux.vdi", 160)]),
            node("Music", base + "\\Music", 8.4 * GB, 2210, days=40, top=[(690 * MB, "Podcast41.wav", 510)]),
            node("Desktop", base + "\\Desktop", 3.2 * GB, 214, days=0, top=[(845 * MB, "Vídeo aniversário.mp4", 200)]),
            node("OneDrive", base + "\\OneDrive", 2.1 * GB, 1320, days=5, top=[(3 * MB, "Relatório.xlsx", 20)])]
    total = sum(k.size for k in kids)
    root = node(base, base, total, sum(k.files for k in kids), kids)
    for k in kids:
        k.parent = root
    shares = {"Vídeos": .33, "Compactados": .17, "Imagens": .14, "Instaladores e ISOs": .11,
              "Documentos": .08, "Músicas e áudio": .06, "Programas e sistema": .07}
    cats, counts = {}, {}
    rest = 1.0
    for c in CATEGORY_NAMES:
        frac = shares.get(c, 0)
        if not frac:
            # nomes de categoria podem variar: distribui o que sobrar entre as primeiras desconhecidas
            frac = min(rest, .05) if c != CATEGORY_NAMES[-1] else rest
        rest = max(0.0, rest - frac)
        cats[c] = int(total * frac)
        counts[c] = int(170000 * frac) + 1
    return root, cats, counts


def demo_registry():
    rows = [("Programas desinstalados", "JogoCorrida", "Desinstalador não existe mais",
             "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\JogoCorrida", "HKCU"),
            ("Programas desinstalados", "Toolbar Busca", "Desinstalador não existe mais",
             "HKLM\\SOFTWARE\\…\\Uninstall\\ToolbarBusca", "HKLM"),
            ("Extensões de arquivo", ".cvx", "Programa associado não existe", "HKCU\\Software\\Classes\\.cvx", "HKCU"),
            ("Extensões de arquivo", ".edfp", "Programa associado não existe", "HKCU\\Software\\Classes\\.edfp", "HKCU"),
            ("Caminhos de aplicativos", "conversor.exe", "Arquivo não encontrado",
             "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\conversor.exe", "HKCU"),
            ("Inicialização", "AtualizadorAntigo", "Programa não existe mais",
             "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run", "HKCU"),
            ("Arquivos recentes (MUI)", "editor-fotos.exe", "Arquivo não encontrado",
             "HKCU\\Software\\Classes\\Local Settings\\…\\MuiCache", "HKCU"),
            ("Arquivos recentes (MUI)", "setup-impressora.exe", "Arquivo não encontrado",
             "HKCU\\Software\\Classes\\Local Settings\\…\\MuiCache", "HKCU"),
            ("Pastas compartilhadas", "C:\\Program Files\\EditorDeFotos", "Pasta não existe",
             "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\SharedDLLs", "HKLM")]
    return [Item(path=loc + "\\" + e, values=(c, e, pr, loc), raw=(c, e.lower(), pr, loc.lower()), kind="reg",
                 checked=True, data={"hive": hv}) for c, e, pr, loc, hv in rows]


def demo_drivers():
    rows = [("Placa de vídeo integrada", "Intel Corporation", "31.0.101.4502", 380, "Vídeo", "Atualização disponível no Windows Update", "warn"),
            ("Adaptador de rede sem fio", "Realtek", "2024.0.10.111", 300, "Rede", "Atualização disponível no Windows Update", "warn"),
            ("Leitor de cartões USB", "Genérico", "10.0.22621.1", 900, "USB", "Dispositivo com problema (código 28)", "danger"),
            ("Áudio de alta definição", "Realtek", "6.0.9600.1", 420, "Som", "OK", ""),
            ("Controlador NVMe", "Microsoft", "10.0.22621.3880", 120, "Armazenamento", "OK", ""),
            ("Bluetooth", "Intel Corporation", "23.60.0.1", 200, "Bluetooth", "OK", ""),
            ("Teclado HID", "Microsoft", "10.0.22621.1", 700, "Teclado", "OK", ""),
            ("Mouse compatível com HID", "Microsoft", "10.0.22621.1", 700, "Mouse", "OK", ""),
            ("Webcam integrada", "Chicony", "10.0.22621.1", 650, "Câmera", "OK", ""),
            ("Adaptador Ethernet", "Realtek", "10.68.815.2023", 330, "Rede", "OK", ""),
            ("Monitor PnP genérico", "Microsoft", "10.0.22621.1", 700, "Monitor", "OK", "")]
    return [Item(path=n, values=(n, f, v, fmt_date(ago(d)), c, st), raw=(n.lower(), f.lower(), v, ago(d), c, st),
                 kind="driver", checked=tag == "warn", data={"tag": tag, "hwid": ""})
            for n, f, v, d, c, st, tag in rows]


DASH_SUMMARY = {"when": "03/11/2026 às 09:42", "junk": int(9.8 * GB), "dups": int(1.3 * GB), "dup_groups": 5,
                "large": int(45.9 * GB), "large_n": 14, "old": int(8.7 * GB), "old_n": 12, "left": int(4.7 * GB),
                "left_n": 9, "prog_total": 86, "prog_unused": 5, "startup": 8}

# (arquivo, chave da página, tema, função que injeta os dados)
SHOTS = [
    ("painel", "dashboard", "light", "dashboard"),
    ("painel-escuro", "dashboard", "dark", "dashboard"),
    ("lixo", "junk", "light", demo_junk),
    ("mapa-disco", "diskmap", "light", "diskmap"),
    ("mapa-disco-escuro", "diskmap", "dark", "diskmap"),
    ("grandes", "large", "light", demo_large),
    ("repetidos", "dups", "light", demo_dups),
    ("antigos", "old", "light", demo_old),
    ("programas", "programs", "light", demo_programs),
    ("programas-escuro", "programs", "dark", demo_programs),
    ("store", "store_apps", "light", demo_store),
    ("atualizar", "updates", "light", demo_updates),
    ("instalar", "install", "light", None),
    ("restos", "leftovers", "light", demo_leftovers),
    ("inicializacao", "startup", "light", demo_startup),
    ("ram", "ram", "light", demo_ram),
    ("ram-escuro", "ram", "dark", demo_ram),
    ("ferramentas", "tools", "light", None),
    ("lixeira", "trash", "light", demo_trash),
    ("recuperar", "recover", "light", demo_recover),
    ("recuperar-escuro", "recover", "dark", demo_recover),
    # páginas novas: entram sozinhas quando existirem (sem dados de demonstração específicos)
    ("registro", "registry", "light", demo_registry),
    ("otimizar-windows", "tweaks", "light", None),
    ("otimizar-discos", "diskopt", "light", None),
    ("drivers", "drivers", "light", demo_drivers),
    ("meu-computador", "sysinfo", "light", None),
    ("teste-desempenho", "bench", "light", None),
    ("velocidade", "speed", "light", None),
    ("destruidor", "shredder", "light", None),
    ("configuracoes", "settings", "light", None),
    ("sobre", "about", "dark", None),
]
if args.only:
    wanted = set(args.only.split(","))
    SHOTS = [s for s in SHOTS if s[0] in wanted]

SHOTS.sort(key=lambda s: s[2] == "dark")   # todos os claros primeiro: só uma troca de tema
app = gui.App()
app.geometry(f"{W}x{H}+0+0")
errors: list = []
app.report_callback_exception = lambda *e: errors.append(e)
queue = list(SHOTS)
saved: list[str] = []
skipped: list[str] = []


def set_theme(theme, key):
    if app.settings.get("theme") != theme or not hasattr(app, "_shot_theme"):
        app.settings["theme"] = theme
        app._shot_theme = theme
        app.rebuild(key if key in app.page_classes else "dashboard")
        app.geometry(f"{W}x{H}+0+0")


def inject(page, key, demo):
    if demo == "dashboard":
        page.summary = dict(DASH_SUMMARY)
        page.refresh()
        page.render_summary()
    elif demo == "diskmap":
        page.target.set(U)
        page.populate(demo_diskmap())
        page.lbl.config(text="Análise concluída em 41 s.")
    elif callable(demo) and hasattr(page, "populate"):
        items = demo()
        cols = getattr(page, "columns", None)
        if cols and items and len(items[0].values) != len(cols):
            print(f"  aviso: colunas de '{key}' mudaram; dados de demonstração ignorados")
            return
        page._scanned = True
        if key == "recover":
            page.good_only.set(False)
        page.populate(items)
        if hasattr(page, "show_progress"):
            msg = {"junk": "Análise concluída: 9,8 GB podem ser liberados com segurança.",
                   "recover": "11 arquivos apagados encontrados (9 com boa chance de recuperação).",
                   "programs": "86 programas instalados · 5 pouco usados."}.get(key, f"{len(items)} itens encontrados.")
            try:
                page.show_progress(msg)
            except Exception:  # noqa: BLE001
                pass


def next_shot():
    if not queue:
        finish()
        return
    name, key, theme, demo = queue.pop(0)
    if key not in app.page_classes:
        skipped.append(f"{name} ({key})")
        app.after(10, next_shot)
        return
    try:
        set_theme(theme, key)
        page = app.page(key)
        if key != "dashboard":
            page.on_show = lambda: None   # nunca dispara varreduras automáticas
        app.show(key)
        inject(page, key, demo)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        skipped.append(f"{name} ({key}: erro)")
        app.after(10, next_shot)
        return
    app.update_idletasks()
    app.after(args.wait, lambda: capture(name))


def capture(name):
    out = os.path.join(args.out, name + ".png")
    app.update()
    subprocess.run(["import", "-window", "root", "-crop", f"{W}x{H}+0+0", "+repage", out], check=False)
    optimize(out)
    saved.append(out)
    print("ok", os.path.relpath(out, ROOT))
    app.after(50, next_shot)


def optimize(path):
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        q = im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        q.save(path, optimize=True)
    except Exception as e:  # noqa: BLE001
        print("  (sem otimização:", e, ")")


def finish():
    for e in errors:
        traceback.print_exception(*e)
    print(f"\n{len(saved)} prints salvos em {args.out}")
    if skipped:
        print("pulados (página inexistente ou erro):", ", ".join(skipped))
    app.destroy()


app.after(1200, next_shot)
app.mainloop()
