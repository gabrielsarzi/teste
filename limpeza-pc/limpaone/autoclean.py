"""Limpeza automática agendada (Agendador de Tarefas do Windows) e modo linha de comando."""
from __future__ import annotations

import datetime
import os
import sys
import threading

from .utils import IS_WIN, clear_contents, fmt_size, log

TASK_NAME = r"LimpaOne\Limpeza automatica"
FREQS = {"off": "Desligada", "daily": "Todos os dias", "weekly": "Toda semana", "monthly": "Todo mês"}


def _command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --auto-clean'
    main = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{pyw}" "{main}" --auto-clean'


def set_schedule(freq: str) -> str:
    """Cria/remove a tarefa agendada. Retorna "" se ok ou a mensagem de erro."""
    if not IS_WIN:
        return "A limpeza automática está disponível no Windows."
    from .winutil import run
    schtasks = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "schtasks.exe")
    if freq == "off":
        run([schtasks, "/Delete", "/TN", TASK_NAME, "/F"])
        return ""
    sc = {"daily": ["/SC", "DAILY"], "weekly": ["/SC", "WEEKLY", "/D", "SUN"],
          "monthly": ["/SC", "MONTHLY", "/D", "1"]}[freq]
    rc, out, err = run([schtasks, "/Create", "/TN", TASK_NAME, "/TR", _command(), *sc, "/ST", "12:00", "/F"])
    return "" if rc == 0 else (err or out).strip() or f"erro {rc}"


def run_auto_clean(empty_bin=False, locations=None) -> int:
    """Limpa só lixo e cache seguros (sem itens de privacidade). Retorna bytes liberados."""
    from .scanners import scan_junk
    from .system import empty_recycle_bin, recycle_bin_info
    if locations is None:
        items = scan_junk(threading.Event(), lambda s: None, include_recycle=False, include_privacy=False)
        from .settings import Settings
        skipped = set(Settings().get("auto_clean_skip", []) or [])   # o que o usuário desmarcou na tela
        targets = [(i.path, i.data.get("patterns"), i.data.get("age", 0), i.data.get("only_mine")) for i in items
                   if i.checked and i.data.get("auto_ok") and i.path not in skipped]
    else:
        targets = locations
    freed = 0
    for path, patterns, age, only_mine in targets:
        f, _ = clear_contents(path, patterns, age, only_mine)
        freed += f
    if empty_bin:
        size, _ = recycle_bin_info()
        try:
            empty_recycle_bin()
            freed += size
        except OSError:
            pass
    log(f"LIMPEZA AUTOMÁTICA: {fmt_size(freed)} liberados")
    try:
        from .settings import Settings
        Settings().set("auto_clean_last", {"when": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                                           "freed": freed})
    except Exception:  # noqa: BLE001
        pass
    return freed


def cli_main(argv) -> bool:
    """Trata argumentos de linha de comando. Retorna True se algo foi executado (sem abrir a janela)."""
    if "--auto-clean" in argv:
        from .settings import Settings
        run_auto_clean(Settings().get("auto_clean_recycle", False))
        return True
    return False
