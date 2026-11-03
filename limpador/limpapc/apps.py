"""Instalação e atualização de programas pelo winget (lógica, sem interface).

- CATALOG: programas populares organizados por categoria (IDs conferidos no repositório
  microsoft/winget-pkgs).
- installed_ids(): quais programas do catálogo já estão instalados.
- install_app() / upgrade_app(): instalam/atualizam um programa, com mensagem amigável de erro.
- list_upgrades(): atualizações disponíveis (`winget upgrade`).
- make_bat() / make_import_json(): "kit pós-formatação" para levar a outro PC.

Tudo degrada com segurança fora do Windows ou sem o winget.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import tempfile
from dataclasses import dataclass

from .utils import IS_WIN, log
from .winutil import parse_winget_table, ps_json, winget, winget_path


@dataclass(frozen=True)
class CatalogApp:
    id: str          # PackageIdentifier do winget (exato)
    name: str
    desc: str
    category: str


_RAW: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("Navegadores", [
        ("Google.Chrome.EXE", "Google Chrome", "O navegador mais usado do mundo."),
        ("Mozilla.Firefox.pt-BR", "Firefox", "Navegador livre focado em privacidade (em português)."),
        ("Brave.Brave", "Brave", "Navegador com bloqueio de anúncios embutido."),
        ("Opera.Opera", "Opera", "Navegador com VPN gratuita e barra lateral."),
        ("Opera.OperaGX", "Opera GX", "Versão do Opera feita para quem joga."),
        ("Vivaldi.Vivaldi", "Vivaldi", "Navegador muito personalizável."),
    ]),
    ("Comunicação", [
        ("Discord.Discord", "Discord", "Chat de voz, vídeo e texto para grupos."),
        ("Telegram.TelegramDesktop", "Telegram", "Mensagens rápidas sincronizadas com o celular."),
        ("Zoom.Zoom", "Zoom", "Reuniões e aulas por vídeo."),
        ("Microsoft.Teams", "Microsoft Teams", "Chat e reuniões para trabalho e escola."),
        ("SlackTechnologies.Slack", "Slack", "Mensagens para equipes."),
        ("Mozilla.Thunderbird.pt-BR", "Thunderbird", "Leitor de e-mails gratuito (em português)."),
    ]),
    ("Música e vídeo", [
        ("VideoLAN.VLC", "VLC", "Toca praticamente qualquer vídeo ou música."),
        ("Spotify.Spotify", "Spotify", "Streaming de músicas e podcasts."),
        ("CodecGuide.K-LiteCodecPack.Standard", "K-Lite Codec Pack", "Codecs e player para todos os formatos."),
        ("Daum.PotPlayer", "PotPlayer", "Player de vídeo leve e completo."),
        ("Stremio.Stremio", "Stremio", "Central de filmes e séries."),
        ("Audacity.Audacity", "Audacity", "Gravação e edição de áudio."),
    ]),
    ("Imagem e criação", [
        ("OBSProject.OBSStudio", "OBS Studio", "Gravação de tela e transmissões ao vivo."),
        ("ByteDance.CapCut", "CapCut", "Editor de vídeo simples e rápido."),
        ("GIMP.GIMP.3", "GIMP", "Editor de imagens gratuito e avançado."),
        ("KDE.Krita", "Krita", "Pintura e ilustração digital."),
        ("Inkscape.Inkscape", "Inkscape", "Desenho vetorial (logos, SVG)."),
        ("BlenderFoundation.Blender", "Blender", "Modelagem e animação 3D."),
        ("HandBrake.HandBrake", "HandBrake", "Converte e comprime vídeos."),
        ("IrfanSkiljan.IrfanView", "IrfanView", "Visualizador de imagens super leve."),
        ("ShareX.ShareX", "ShareX", "Capturas e gravações de tela com atalhos."),
    ]),
    ("Utilitários e compactadores", [
        ("7zip.7zip", "7-Zip", "Compacta e abre ZIP, RAR, 7z e outros."),
        ("RARLab.WinRAR", "WinRAR", "Compactador clássico de arquivos RAR."),
        ("Notepad++.Notepad++", "Notepad++", "Bloco de notas turbinado."),
        ("voidtools.Everything", "Everything", "Encontra qualquer arquivo na hora."),
        ("Microsoft.PowerToys", "PowerToys", "Utilitários extras da Microsoft para o Windows."),
        ("qBittorrent.qBittorrent", "qBittorrent", "Cliente de torrent sem anúncios."),
        ("Tonec.InternetDownloadManager", "Internet Download Manager", "Acelerador de downloads (pago)."),
        ("RevoUninstaller.RevoUninstaller", "Revo Uninstaller", "Desinstalador que remove restos."),
    ]),
    ("Hardware e diagnóstico", [
        ("CPUID.CPU-Z", "CPU-Z", "Detalhes do processador, placa-mãe e memória."),
        ("CPUID.HWMonitor", "HWMonitor", "Temperaturas, voltagens e ventoinhas."),
        ("TechPowerUp.GPU-Z", "GPU-Z", "Informações da placa de vídeo."),
        ("CrystalDewWorld.CrystalDiskInfo", "CrystalDiskInfo", "Saúde (S.M.A.R.T.) do HD e SSD."),
        ("CrystalDewWorld.CrystalDiskMark", "CrystalDiskMark", "Teste de velocidade do disco."),
        ("AntibodySoftware.WizTree", "WizTree", "Mostra o que ocupa espaço no disco."),
        ("Guru3D.Afterburner", "MSI Afterburner", "Monitoramento e overclock da placa de vídeo."),
        ("Rufus.Rufus", "Rufus", "Cria pendrives de instalação do Windows."),
        ("Ventoy.Ventoy", "Ventoy", "Pendrive com várias ISOs ao mesmo tempo."),
    ]),
    ("Escritório e PDF", [
        ("TheDocumentFoundation.LibreOffice", "LibreOffice", "Pacote de escritório gratuito (texto, planilha…)."),
        ("ONLYOFFICE.DesktopEditors", "ONLYOFFICE", "Editor compatível com Word, Excel e PowerPoint."),
        ("Adobe.Acrobat.Reader.64-bit", "Adobe Acrobat Reader", "Leitor de PDF oficial da Adobe."),
        ("SumatraPDF.SumatraPDF", "SumatraPDF", "Leitor de PDF leve e rápido."),
        ("PDFsam.PDFsam", "PDFsam Basic", "Junta, divide e gira páginas de PDF."),
        ("Obsidian.Obsidian", "Obsidian", "Anotações em Markdown."),
        ("ReceitaFederaldoBrasil.IRPF2026", "IRPF 2026", "Programa do Imposto de Renda da Receita Federal."),
    ]),
    ("Nuvem e backup", [
        ("Google.GoogleDrive", "Google Drive", "Sincroniza arquivos com o Google Drive."),
        ("Dropbox.Dropbox", "Dropbox", "Armazenamento e sincronização na nuvem."),
        ("Microsoft.OneDrive", "OneDrive", "Nuvem da Microsoft integrada ao Windows."),
    ]),
    ("Desenvolvimento", [
        ("Microsoft.VisualStudioCode", "Visual Studio Code", "Editor de código da Microsoft."),
        ("Git.Git", "Git", "Controle de versão."),
        ("GitHub.GitHubDesktop", "GitHub Desktop", "Git com interface gráfica."),
        ("Python.Python.3.13", "Python 3.13", "Linguagem de programação Python."),
        ("OpenJS.NodeJS.LTS", "Node.js LTS", "JavaScript fora do navegador."),
        ("WinSCP.WinSCP", "WinSCP", "Transferência de arquivos SFTP/FTP."),
    ]),
    ("Jogos", [
        ("Valve.Steam", "Steam", "A maior loja de jogos para PC."),
        ("EpicGames.EpicGamesLauncher", "Epic Games", "Loja da Epic (jogos grátis toda semana)."),
        ("ElectronicArts.EADesktop", "EA app", "Jogos da Electronic Arts."),
        ("Ubisoft.Connect", "Ubisoft Connect", "Jogos da Ubisoft."),
        ("GOG.Galaxy", "GOG Galaxy", "Jogos sem DRM e biblioteca unificada."),
        ("Blizzard.BattleNet", "Battle.net", "Jogos da Blizzard."),
        ("RiotGames.LeagueOfLegends.BR", "League of Legends", "Cliente do servidor brasileiro."),
        ("Roblox.Roblox", "Roblox", "Plataforma de jogos criados pela comunidade."),
        ("Mojang.MinecraftLauncher", "Minecraft Launcher", "Launcher oficial do Minecraft."),
    ]),
    ("Segurança e acesso remoto", [
        ("Malwarebytes.Malwarebytes", "Malwarebytes", "Remove vírus e programas indesejados."),
        ("Bitwarden.Bitwarden", "Bitwarden", "Gerenciador de senhas gratuito."),
        ("KeePassXCTeam.KeePassXC", "KeePassXC", "Cofre de senhas offline."),
        ("Proton.ProtonVPN", "Proton VPN", "VPN com plano gratuito."),
        ("AnyDesk.AnyDesk", "AnyDesk", "Acesso remoto rápido."),
        ("TeamViewer.TeamViewer", "TeamViewer", "Acesso remoto e suporte."),
        ("Google.ChromeRemoteDesktopHost", "Área de Trabalho Remota do Chrome", "Acesse este PC pelo navegador."),
    ]),
    ("Componentes do sistema", [
        ("Microsoft.VCRedist.2015+.x64", "Visual C++ 2015-2022 (64 bits)", "Necessário para muitos jogos e programas."),
        ("Microsoft.VCRedist.2015+.x86", "Visual C++ 2015-2022 (32 bits)", "Versão 32 bits — instale as duas."),
        ("Microsoft.VCRedist.2013.x64", "Visual C++ 2013 (64 bits)", "Para programas e jogos mais antigos."),
        ("Microsoft.DotNet.DesktopRuntime.8", ".NET Desktop Runtime 8", "Base para vários programas modernos."),
        ("Microsoft.DotNet.DesktopRuntime.10", ".NET Desktop Runtime 10", "Versão mais nova do .NET."),
        ("Microsoft.DirectX", "DirectX (runtime)", "Bibliotecas do DirectX 9 usadas por jogos antigos."),
        ("Oracle.JavaRuntimeEnvironment", "Java (JRE)", "Necessário para alguns programas e sites."),
    ]),
]

CATALOG: list[CatalogApp] = [CatalogApp(i, n, d, cat) for cat, apps in _RAW for i, n, d in apps]
CATEGORIES: list[str] = [cat for cat, _ in _RAW]
BY_ID: dict[str, CatalogApp] = {a.id.lower(): a for a in CATALOG}

SOURCE_DETAILS = {"Argument": "https://cdn.winget.microsoft.com/cache",
                  "Identifier": "Microsoft.Winget.Source_8wekyb3d8bbwe",
                  "Name": "winget", "Type": "Microsoft.PreIndexed.Package"}

# ------------------------------------------------------------------ códigos de saída do winget
OK_CODES = {0: "Concluído",
            0x8A150061: "Já estava instalado",
            0x8A15010D: "Já estava instalado",
            0x8A150109: "Concluído — reinicie o PC para terminar",
            0x8A15010A: "Concluído — reinicie o PC para terminar",
            0x8A15010B: "Concluído — o PC será reiniciado"}
ERR_CODES = {0x8A150014: "não encontrado no catálogo do winget",
             0x8A15002B: "nenhuma atualização aplicável",
             0x8A15010C: "cancelado pelo usuário",
             0x8A150101: "o programa está aberto — feche-o e tente de novo",
             0x8A150102: "outra instalação está em andamento",
             0x8A150103: "um arquivo está em uso",
             0x8A150105: "disco cheio",
             0x8A150107: "sem conexão com a internet",
             0x8A15010E: "uma versão mais nova já está instalada",
             0x8A15010F: "bloqueado por política do sistema",
             124: "tempo esgotado",
             127: "winget não encontrado"}
ALREADY_INSTALLED = 0x8A150061 - (1 << 32)   # como o cmd.exe enxerga o código (com sinal)

UNKNOWN_VERSIONS = {"unknown", "desconhecido", "desconhecida", ""}


def available() -> bool:
    """True se o winget pode ser usado (Windows 10/11 com o Instalador de Aplicativo)."""
    return IS_WIN and bool(winget_path())


def unavailable_reason() -> str:
    if not IS_WIN:
        return ("Disponível no Windows 10/11 com o winget. Você ainda pode montar a lista e gerar o "
                "instalador (.bat) para usar em outro computador.")
    return ("O winget não foi encontrado. Instale ou atualize o “Instalador de Aplicativo” pela "
            "Microsoft Store (Windows 10/11) e abra esta tela de novo.")


def friendly_result(rc: int, out: str = "", err: str = "") -> tuple[bool, str]:
    """Converte o código de saída do winget em (sucesso, mensagem em português)."""
    code = rc & 0xFFFFFFFF
    if code in OK_CODES:
        return True, OK_CODES[code]
    if code in ERR_CODES:
        return False, ERR_CODES[code].capitalize()
    lines = [ln.strip() for ln in (err + "\n" + out).replace("\r", "\n").split("\n")]
    lines = [ln for ln in lines if len(ln) > 3 and not set(ln) <= set("-\\|/█▒ ")]
    detail = lines[-1] if lines else ""
    return False, f"Código {code:#x}" + (f": {detail[:160]}" if detail else "")


def is_unknown_version(v: str) -> bool:
    v = (v or "").strip().lower()
    return v in UNKNOWN_VERSIONS or v.startswith("<")


# ------------------------------------------------------------------ leitura das tabelas do winget
def parse_tables(text: str) -> list[dict]:
    """Lê todas as tabelas da saída do winget (o `upgrade` pode ter duas: a normal e a de
    pacotes que exigem seleção explícita), ignorando cabeçalhos repetidos e rodapés."""
    lines = [ln.split("\r")[-1] for ln in text.replace("\r\n", "\n").split("\n")]
    seps = [i for i, ln in enumerate(lines) if ln.strip().startswith("---") and set(ln.strip()) <= {"-"}]
    rows: list[dict] = []
    seen = set()
    for n, s in enumerate(seps):
        if s == 0:
            continue
        end = seps[n + 1] - 1 if n + 1 < len(seps) else len(lines)
        block = lines[s - 1:end]
        # a tabela termina na primeira linha em branco
        for k in range(2, len(block)):
            if not block[k].strip():
                block = block[:k]
                break
        for r in parse_winget_table("\n".join(block)):
            rid = r.get("id", "")
            if not rid or rid in seen or not re.match(r"^[\w.+\-…\\{}]+$", rid):
                continue
            seen.add(rid)
            rows.append(r)
    return rows


def _match_installed(ids_found: set[str]) -> set[str]:
    """Cruza IDs encontrados (talvez truncados com '…') com o catálogo. Retorna IDs do catálogo."""
    out = set()
    for raw in ids_found:
        low = raw.lower().strip()
        if low.endswith("…") or low.endswith("..."):
            pre = low.rstrip("….")
            out.update(a.id for k, a in BY_ID.items() if pre and k.startswith(pre))
        elif low in BY_ID:
            out.add(BY_ID[low].id)
    return out


def installed_ids(progress=None) -> set[str]:
    """IDs do catálogo que já estão instalados. Usa `winget export` (IDs completos) e, se falhar,
    a tabela do `winget list`."""
    if not available():
        return set()
    found: set[str] = set()
    tmp = os.path.join(tempfile.gettempdir(), f"limpapc_export_{os.getpid()}.json")
    try:
        rc, _, _ = winget(["export", "-o", tmp, "--source", "winget"], timeout=300)
        if os.path.exists(tmp):
            found = set(import_json_ids(_read_json(tmp)))
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    if not found:
        if progress:
            progress("Lendo a lista de programas instalados…")
        rc, out, _ = winget(["list"], timeout=300)
        found = {r["id"] for r in parse_tables(out)}
    return _match_installed(found)


# ------------------------------------------------------------------ instalar / atualizar
def install_app(app_id: str, timeout=3600) -> tuple[bool, str]:
    rc, out, err = winget(["install", "--id", app_id, "-e", "--source", "winget", "--silent",
                           "--accept-package-agreements"], timeout=timeout)
    ok, msg = friendly_result(rc, out, err)
    log(f"WINGET INSTALL {app_id}: {'ok' if ok else 'erro'} ({msg})")
    return ok, msg


def upgrade_app(app_id: str, unknown=False, timeout=3600) -> tuple[bool, str]:
    args = ["upgrade", "--id", app_id, "-e", "--silent", "--accept-package-agreements"]
    if unknown:
        args.append("--include-unknown")
    rc, out, err = winget(args, timeout=timeout)
    ok, msg = friendly_result(rc, out, err)
    log(f"WINGET UPGRADE {app_id}: {'ok' if ok else 'erro'} ({msg})")
    return ok, msg


def list_upgrades(include_unknown=True) -> list[dict]:
    """Atualizações disponíveis: [{name, id, version, available, source, unknown}].

    Tenta o módulo PowerShell Microsoft.WinGet.Client (dados completos, sem truncar) e cai para a
    tabela de texto do `winget upgrade`."""
    if not available():
        return []
    rows: list[dict] = []
    data = ps_json("if (Get-Command Get-WinGetPackage -ErrorAction SilentlyContinue) { "
                   "Get-WinGetPackage | Where-Object { $_.IsUpdateAvailable } | ForEach-Object { "
                   "[pscustomobject]@{name=$_.Name; id=$_.Id; version=[string]$_.InstalledVersion; "
                   "available=[string]($_.AvailableVersions | Select-Object -First 1); source=$_.Source} } }",
                   timeout=300)
    for d in data:
        if isinstance(d, dict) and d.get("id"):
            rows.append({k: str(d.get(k) or "") for k in ("name", "id", "version", "available", "source")})
    if not rows:
        args = ["upgrade"] + (["--include-unknown"] if include_unknown else [])
        rc, out, _ = winget(args, timeout=300)
        rows = [r for r in parse_tables(out) if r.get("available")]
    for r in rows:
        r["unknown"] = is_unknown_version(r.get("version", ""))
    if not include_unknown:
        rows = [r for r in rows if not r["unknown"]]
    return rows


# ------------------------------------------------------------------ arquivos do kit
def _read_json(path: str):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def import_json_ids(data) -> list[str]:
    """Extrai IDs de um JSON do `winget export`, de uma seleção salva pelo LimpaPC ou de uma lista."""
    ids: list[str] = []
    if isinstance(data, list):
        ids = [str(x) for x in data if isinstance(x, str)]
    elif isinstance(data, dict):
        if isinstance(data.get("ids"), list):
            ids = [str(x) for x in data["ids"] if isinstance(x, str)]
        for src in data.get("Sources") or []:
            for p in (src or {}).get("Packages") or []:
                if isinstance(p, dict) and p.get("PackageIdentifier"):
                    ids.append(str(p["PackageIdentifier"]))
    out, seen = [], set()
    for i in ids:
        i = i.strip()
        if i and i.lower() not in seen:
            seen.add(i.lower())
            out.append(i)
    return out


def selection_json(ids: list[str]) -> str:
    return json.dumps({"app": "LimpaPC", "tipo": "selecao-de-programas",
                       "criado_em": datetime.datetime.now().isoformat(timespec="seconds"),
                       "ids": list(ids)}, ensure_ascii=False, indent=2)


def load_selection(path: str) -> list[str]:
    return import_json_ids(_read_json(path))


def make_import_json(ids: list[str]) -> str:
    """JSON no formato do `winget export`/`winget import`."""
    data = {"$schema": "https://aka.ms/winget-packages.schema.2.0.json",
            "CreationDate": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "Sources": [{"Packages": [{"PackageIdentifier": i} for i in ids],
                         "SourceDetails": dict(SOURCE_DETAILS)}],
            "WinGetVersion": "1.6.0"}
    return json.dumps(data, indent=2)


_BAT_UNSAFE = re.compile(r'[&|<>^%!"()]')
_BAT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+\-_]*$")


def _bat_text(s: str) -> str:
    """Remove caracteres que o cmd.exe interpretaria dentro de echo/call."""
    return _BAT_UNSAFE.sub("", s).replace("  ", " ").strip()


def make_bat(apps: list[tuple[str, str]], created: datetime.datetime | None = None) -> str:
    """Gera um .bat autoexplicativo que instala os programas com o winget.

    apps: lista de (id, nome). Retorna o texto com quebras de linha CRLF."""
    created = created or datetime.datetime.now()
    valid = [(i, _bat_text(n) or i) for i, n in apps if _BAT_ID.match(i)]
    total = len(valid)
    L = [
        "@echo off",
        "chcp 65001 >nul",
        "title Kit pos-formatacao - LimpaPC",
        "setlocal",
        "",
        "REM ======================================================================",
        "REM  KIT PÓS-FORMATAÇÃO — gerado pelo LimpaPC",
        f"REM  Criado em {created:%d/%m/%Y às %H:%M} com {total} programa(s).",
        "REM",
        "REM  COMO USAR",
        "REM   1. Copie este arquivo para o computador novo (pendrive, nuvem, e-mail).",
        "REM   2. Conecte o computador à internet.",
        "REM   3. Dê dois cliques neste arquivo. Cada programa é baixado do site",
        "REM      oficial pelo winget (o instalador de pacotes da Microsoft) e",
        "REM      instalado sem perguntas. O Windows pode pedir permissão (UAC).",
        "REM   4. No fim aparece um resumo. Programas que já existem são pulados.",
        "REM",
        "REM  Requisitos: Windows 10 (1809 ou mais novo) ou Windows 11 com o",
        "REM  \"Instalador de Aplicativo\" da Microsoft Store (já vem no Windows 11).",
        "REM",
        "REM  Para tirar um programa da lista, apague a linha \"call :instalar\" dele.",
        "REM ======================================================================",
        "",
        "echo.",
        "echo  ==============================================",
        "echo   Kit pós-formatação - LimpaPC",
        f"echo   {total} programa(s) para instalar",
        "echo  ==============================================",
        "echo.",
        "",
        "REM --- 1) Verifica se o winget existe -----------------------------------",
        "where winget >nul 2>nul",
        "if errorlevel 1 goto :sem_winget",
        "",
        "REM --- 2) Atualiza a lista de programas do winget -----------------------",
        "echo Atualizando o catálogo do winget...",
        "winget source update >nul 2>nul",
        "",
        "set /a ATUAL=0",
        f"set /a TOTAL={total}",
        "set /a OK=0",
        "set /a FALHAS=0",
        "set \"LISTA_FALHAS=\"",
        "",
        "REM --- 3) Instala cada programa (ID do winget e nome) --------------------",
    ]
    for i, n in valid:
        L.append(f'call :instalar "{i}" "{n}"')
    L += [
        "",
        "REM --- 4) Resumo ---------------------------------------------------------",
        "echo.",
        "echo  ==============================================",
        "echo   Concluído: %OK% de %TOTAL% programa(s) instalado(s).",
        "if %FALHAS% GTR 0 echo   Falharam: %FALHAS% -%LISTA_FALHAS%",
        "if %FALHAS% GTR 0 echo   Dica: rode este arquivo de novo ou instale esses manualmente.",
        "echo  ==============================================",
        "echo.",
        "pause",
        "exit /b 0",
        "",
        "REM ----------------------------------------------------------------------",
        "REM  Sub-rotina: instala um programa. %%1 = ID do winget, %%2 = nome.",
        "REM ----------------------------------------------------------------------",
        ":instalar",
        "set /a ATUAL+=1",
        "echo.",
        "echo [%ATUAL%/%TOTAL%] Instalando %~2 ...",
        "winget install --id %1 -e --source winget --silent --accept-package-agreements "
        "--accept-source-agreements --disable-interactivity",
        "set RC=%errorlevel%",
        'if "%RC%"=="0" goto :instalado',
        f'if "%RC%"=="{ALREADY_INSTALLED}" goto :ja_existia',
        "set /a FALHAS+=1",
        "set \"LISTA_FALHAS=%LISTA_FALHAS% %~2;\"",
        "echo    ^> Não foi possível instalar %~2 (código %RC%).",
        "goto :eof",
        ":ja_existia",
        "echo    ^> %~2 já estava instalado.",
        ":instalado",
        "set /a OK+=1",
        "goto :eof",
        "",
        ":sem_winget",
        "echo O winget (Instalador de Aplicativo) não foi encontrado neste computador.",
        "echo.",
        "echo Abrindo a Microsoft Store: instale/atualize o \"Instalador de Aplicativo\"",
        "echo e depois rode este arquivo novamente.",
        "start \"\" \"ms-windows-store://pdp/?productid=9NBLGGH4NNS1\"",
        "echo.",
        "pause",
        "exit /b 1",
        "",
    ]
    return "\r\n".join(L)


def write_bat(path: str, apps: list[tuple[str, str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(make_bat(apps))


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
