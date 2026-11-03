"""Proteção do sistema: ponto de restauração antes de qualquer alteração no Windows.

Regra do LimpaOne: nada que mexa no registro, em ajustes do Windows, em apps do sistema ou em restos de
programas acontece sem antes tentar criar um ponto de restauração. Se não for possível, o usuário é avisado
e a resposta padrão é NÃO continuar.
"""
from __future__ import annotations

import re
import threading
import time
from tkinter import messagebox

from .utils import IS_WIN, log

_last_ok = 0.0
_SPP = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\SPP\Clients"
_SR_CLIENT = "{09F7EDC5-294E-4180-AF6A-FB0E6A0E9513}"

RP_SCRIPT = r"""
$r = [ordered]@{ ok = $false; error = $null }
try {
  Enable-ComputerRestore -Drive ($env:SystemDrive + '\') -ErrorAction Stop
  New-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore' -Name 'SystemRestorePointCreationFrequency' -Value 0 -PropertyType DWord -Force | Out-Null
  Checkpoint-Computer -Description $desc -RestorePointType MODIFY_SETTINGS -ErrorAction Stop
  $r.ok = $true
} catch { $r.error = $_.Exception.Message }
$r | ConvertTo-Json | Set-Content -Encoding UTF8 -Path $out
"""


def restore_enabled() -> bool | None:
    """True/False se a Proteção do Sistema está ligada no disco do Windows; None fora do Windows."""
    if not IS_WIN:
        return None
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _SPP, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        val, _ = winreg.QueryValueEx(k, _SR_CLIENT)
        return bool(val)
    except OSError:
        return False


def create_restore_point(reason: str, force: bool = False) -> tuple[bool, str]:
    """Ativa a Proteção do Sistema (se preciso) e cria um ponto de restauração. Pede UAC."""
    global _last_ok
    if not IS_WIN:
        return True, ""
    if not force and time.time() - _last_ok < 1800:   # já criado há menos de 30 minutos nesta sessão
        return True, ""
    from .winutil import run_ps_elevated
    desc = re.sub(r"[^\w\s\-.,]", "", reason or "alteracao")[:60]
    rc, data = run_ps_elevated(f"$desc = 'LimpaOne - {desc}'\n" + RP_SCRIPT, timeout=900)
    if rc == -1 and not data:
        return False, "a permissão de administrador foi recusada"
    ok = bool(isinstance(data, dict) and data.get("ok"))
    if ok:
        _last_ok = time.time()
        log(f"PONTO DE RESTAURAÇÃO criado: {desc}")
        return True, ""
    err = (data or {}).get("error") if isinstance(data, dict) else None
    return False, str(err or f"código {rc}")


def guarded(widget, reason: str, action, progress=None, on_cancel=None):
    """Cria o ponto de restauração em segundo plano e só então executa `action()` (na thread da interface).

    Se não der para criar, pergunta ao usuário — com NÃO como resposta padrão."""
    if not IS_WIN:
        action()
        return
    box: dict = {}
    th = threading.Thread(target=lambda: box.setdefault("r", create_restore_point(reason)), daemon=True)
    th.start()
    if progress:
        progress("Criando ponto de restauração antes de alterar o sistema…")

    def poll():
        if th.is_alive():
            widget.after(200, poll)
            return
        ok, err = box.get("r", (False, "erro desconhecido"))
        if ok:
            action()
            return
        if messagebox.askyesno(
                "Sem ponto de restauração",
                f"Não foi possível criar um ponto de restauração ({err}).\n\n"
                "Sem ele, não há como desfazer esta alteração pelo Windows caso algo dê errado.\n\n"
                "Continuar mesmo assim?", icon="warning", default="no", parent=widget):
            log(f"SEM PONTO DE RESTAURAÇÃO (usuário confirmou): {reason}")
            action()
        else:
            if progress:
                progress("Cancelado: nenhuma alteração foi feita.")
            if on_cancel:
                on_cancel()

    widget.after(200, poll)


def make_now(widget, reason: str, on_done) -> None:
    """Cria um ponto de restauração AGORA (sem usar o cache) e chama on_done(ok, erro) na thread da interface.
    Para os botões "Ativar"/"Criar agora": a mensagem mostrada depende do resultado real."""
    box: dict = {}
    th = threading.Thread(target=lambda: box.setdefault("r", create_restore_point(reason, force=True)), daemon=True)
    th.start()

    def poll():
        if th.is_alive():
            widget.after(200, poll)
            return
        on_done(*box.get("r", (False, "erro desconhecido")))
    widget.after(200, poll)
