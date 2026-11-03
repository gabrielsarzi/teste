"""Ferramentas extras do sistema (hibernação, limpeza do Windows, DNS etc.)."""
from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
from dataclasses import dataclass

from .utils import IS_MAC, IS_WIN, NO_WINDOW, fmt_size, is_admin, log, open_uri


@dataclass
class Tool:
    key: str
    icon: str
    title: str
    desc: str
    button: str
    kind: str          # "admin_console" | "run" | "open" | "root"
    cmd: object
    badge: str = ""


def _system_file_size(name: str) -> int:
    root = os.environ.get("SystemDrive", "C:") + "\\"
    try:
        for e in os.scandir(root):
            if e.name.lower() == name:
                return e.stat(follow_symlinks=False).st_size
    except OSError:
        pass
    return 0


def available_tools() -> list[Tool]:
    tools: list[Tool] = []
    if IS_WIN:
        hib = _system_file_size("hiberfil.sys")
        if hib:
            tools.append(Tool("hib_off", "power", "Desativar hibernação",
                              f"O arquivo hiberfil.sys ocupa {fmt_size(hib)} no disco do sistema. Desativar a "
                              "hibernação devolve esse espaço. O modo Suspender continua funcionando "
                              "normalmente (a Inicialização Rápida do Windows é desligada).",
                              "Desativar", "admin_console", "powercfg /hibernate off", fmt_size(hib)))
        else:
            tools.append(Tool("hib_on", "power", "Reativar hibernação",
                              "A hibernação está desativada. Reative se quiser usar Hibernar ou a "
                              "Inicialização Rápida do Windows.",
                              "Reativar", "admin_console", "powercfg /hibernate on"))
        tools += [
            Tool("dism", "package", "Limpeza profunda do Windows Update",
                 "Remove versões antigas de componentes do Windows que ficam guardadas após atualizações "
                 "(WinSxS). Pode liberar vários GB. Leva alguns minutos e abre uma janela de progresso.",
                 "Executar", "admin_console", "Dism.exe /Online /Cleanup-Image /StartComponentCleanup"),
            Tool("cleanmgr", "sparkles", "Limpeza de Disco do Windows",
                 "Abre a ferramenta oficial do Windows, que inclui itens como arquivos de instalação "
                 "antigos e pacotes de driver.", "Abrir", "open", "cleanmgr.exe"),
            Tool("storagesense", "drive", "Sensor de Armazenamento",
                 "Configura o Windows para apagar automaticamente arquivos temporários e esvaziar a "
                 "Lixeira periodicamente.", "Abrir", "open", "ms-settings:storagesense"),
            Tool("defrag", "pie", "Otimizar unidades",
                 "Otimiza SSDs (TRIM) e desfragmenta HDs, deixando a leitura dos arquivos mais rápida.",
                 "Abrir", "open", "dfrgui.exe"),
            Tool("dns", "sparkles", "Limpar cache de DNS",
                 "Resolve problemas de sites que não carregam ou endereços desatualizados.",
                 "Limpar", "run", ["ipconfig", "/flushdns"]),
            Tool("netrepair", "wifi", "Reparar rede (sem internet / Código 56)",
                 "Use quando o Wi-Fi ou o cabo pararem de funcionar depois de instalar algo. Faz backup e "
                 "corrige a configuração de rede do Windows: remove componentes de rede quebrados, limpa "
                 "ligações inválidas, reseta a rede e reinstala as placas. Gera um relatório na Área de Trabalho.",
                 "Reparar rede", "netrepair", None),
            Tool("repair", "shield", "Reparar arquivos do Windows",
                 "Verifica e corrige arquivos corrompidos do sistema (SFC) e a imagem do Windows (DISM). Use quando o "
                 "Windows estiver travando ou com erros estranhos. Leva de 10 a 30 minutos.",
                 "Reparar", "admin_console",
                 "sfc /scannow & Dism.exe /Online /Cleanup-Image /RestoreHealth & echo. & echo Concluido."),
            Tool("chkdsk", "drive", "Verificar erros no disco",
                 "Procura erros no sistema de arquivos da unidade C: sem precisar reiniciar (chkdsk /scan).",
                 "Verificar", "admin_console", "chkdsk C: /scan"),
            Tool("battery", "bolt", "Relatório da bateria",
                 "Para notebooks: mostra a saúde da bateria (capacidade original × atual) e o histórico de uso.",
                 "Gerar relatório", "battery", None),
            Tool("memtest", "chip", "Diagnóstico de memória",
                 "Testa a memória RAM do computador ao reiniciar. Útil para investigar telas azuis e travamentos.",
                 "Abrir", "open", "mdsched.exe"),
            Tool("restore", "shield", "Pontos de restauração",
                 "Gerencie o espaço usado pelos pontos de restauração do sistema (Proteção do Sistema).",
                 "Abrir", "open", "SystemPropertiesProtection.exe"),
            Tool("resmon", "chip", "Monitor de Recursos",
                 "Veja em detalhes o uso de CPU, memória, disco e rede por cada programa.",
                 "Abrir", "open", "resmon.exe"),
        ]
    elif IS_MAC:
        tools += [
            Tool("storage", "drive", "Armazenamento do macOS",
                 "Recomendações do próprio sistema para liberar espaço.", "Abrir", "open",
                 "x-apple.systempreferences:com.apple.settings.Storage"),
            Tool("activity", "chip", "Monitor de Atividade", "Uso de CPU e memória por programa.", "Abrir",
                 "run", ["open", "-a", "Activity Monitor"]),
        ]
    else:
        if shutil.which("apt-get"):
            tools += [
                Tool("autoremove", "package", "Remover pacotes órfãos",
                     "Desinstala dependências que nenhum programa usa mais (apt autoremove).",
                     "Executar", "root", ["apt-get", "autoremove", "-y"]),
                Tool("aptclean", "trash", "Limpar cache de pacotes",
                     "Apaga os instaladores .deb já usados (apt clean).", "Limpar", "root", ["apt-get", "clean"]),
            ]
        elif shutil.which("dnf"):
            tools.append(Tool("autoremove", "package", "Remover pacotes órfãos",
                              "Desinstala dependências não usadas (dnf autoremove).", "Executar", "root",
                              ["dnf", "autoremove", "-y"]))
        if shutil.which("journalctl"):
            tools.append(Tool("journal", "file", "Reduzir logs do sistema",
                              "Mantém só os últimos 200 MB de registros do systemd (journal).", "Reduzir",
                              "root", ["journalctl", "--vacuum-size=200M"]))
        if shutil.which("flatpak"):
            tools.append(Tool("flatpak", "package", "Remover runtimes Flatpak não usados",
                              "Apaga bibliotecas Flatpak que nenhum aplicativo usa mais.", "Executar", "run",
                              ["flatpak", "uninstall", "--unused", "-y"]))
        for exe, title in (("gnome-system-monitor", "Monitor do sistema"), ("plasma-systemmonitor", "Monitor do sistema"),
                           ("baobab", "Analisador de uso de disco do GNOME")):
            if shutil.which(exe):
                tools.append(Tool(exe, "chip", title, "Ferramenta do seu ambiente gráfico.", "Abrir", "run", [exe]))
    return tools


def run_tool(tool: Tool) -> str:
    """Executa a ferramenta. Retorna uma mensagem curta para o usuário."""
    log(f"FERRAMENTA {tool.title}")
    if tool.kind == "open":
        open_uri(tool.cmd)
        return ""
    if tool.kind == "netrepair":
        from .netrepair import run_network_repair
        return run_network_repair()
    if tool.kind == "battery":
        out = os.path.join(os.path.expanduser("~"), "Desktop", "LimpaOne - relatorio da bateria.html")
        r = subprocess.run(["powercfg", "/batteryreport", "/output", out], capture_output=True, text=True,
                           errors="replace", creationflags=NO_WINDOW)
        if r.returncode == 0 and os.path.exists(out):
            open_uri(out)
            return ""
        return "Não foi possível gerar o relatório (este computador tem bateria?)."
    if tool.kind == "admin_console" and IS_WIN:
        # abre um console visível (com pedido de administrador) para o usuário acompanhar
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f'/k "{tool.cmd}"', None, 1)
        return "" if rc > 32 else "A ação foi cancelada (é preciso permitir como administrador)."
    cmd = list(tool.cmd)
    if tool.kind == "root" and not is_admin():
        if not shutil.which("pkexec"):
            return "Execute no terminal: sudo " + " ".join(cmd)
        cmd = ["pkexec"] + cmd
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=1800,
                           creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as e:
        return f"Erro: {e}"
    out = (r.stdout or r.stderr or "").strip().splitlines()
    tail = "\n".join(out[-6:])
    return ("Concluído." if r.returncode == 0 else f"Terminou com erro (código {r.returncode}).") + \
        (f"\n\n{tail}" if tail else "")
