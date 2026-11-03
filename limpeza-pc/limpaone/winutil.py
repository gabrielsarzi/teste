"""Utilitários para comandos do Windows: PowerShell, execução elevada e winget.

Todas as funções degradam com segurança fora do Windows (retornam vazio / erro amigável).
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import tempfile
import time

from .utils import IS_WIN, NO_WINDOW, is_admin

PS_PREFIX = ("$ErrorActionPreference='SilentlyContinue';"
             "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;$OutputEncoding=[System.Text.Encoding]::UTF8;")


class NotWindows(RuntimeError):
    pass


def run(cmd, timeout=120, input_text=None) -> tuple[int, str, str]:
    """Executa um comando sem abrir janela. Retorna (código, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=NO_WINDOW,
                           input=input_text.encode("utf-8") if input_text else None)
    except FileNotFoundError:
        return 127, "", f"comando não encontrado: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "tempo esgotado"
    except OSError as e:
        return 1, "", str(e)
    dec = lambda b: b.decode("utf-8", "replace") if b else ""  # noqa: E731
    return r.returncode, dec(r.stdout), dec(r.stderr)


def run_ps(script: str, timeout=120) -> tuple[int, str, str]:
    """Executa um script PowerShell (saída em UTF-8)."""
    if not IS_WIN:
        return 1, "", "disponível apenas no Windows"
    return run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-Command", PS_PREFIX + script], timeout=timeout)


def ps_json(script: str, timeout=120, depth=5) -> list:
    """Executa o script e converte a saída para lista de dicionários (via ConvertTo-Json)."""
    rc, out, err = run_ps(f"@({script}) | ConvertTo-Json -Depth {depth} -Compress", timeout)
    out = out.strip()
    if not out:
        return []
    try:
        data = json.loads(out)
    except ValueError:
        return []
    if isinstance(data, dict):
        return [data]
    return data if isinstance(data, list) else []


def shell_execute_wait(exe: str, params: str = "", verb: str = "runas", show: int = 0, timeout=None) -> int:
    """ShellExecuteEx (com UAC quando verb='runas') esperando terminar. Retorna o código de saída
    ou -1 se o usuário recusou / falhou."""
    if not IS_WIN:
        raise NotWindows("disponível apenas no Windows")
    from ctypes import wintypes

    class SHELLEXECUTEINFOW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR),
                    ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR),
                    ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p),
                    ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY), ("dwHotKey", wintypes.DWORD),
                    ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]

    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040 | 0x00000400  # SEE_MASK_NOCLOSEPROCESS | SEE_MASK_FLAG_NO_UI
    info.lpVerb = verb
    info.lpFile = exe
    info.lpParameters = params
    info.nShow = show
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)) or not info.hProcess:
        return -1
    k32 = ctypes.windll.kernel32
    k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k32.WaitForSingleObject(info.hProcess, 0xFFFFFFFF if timeout is None else int(timeout * 1000))
    code = wintypes.DWORD()
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle(info.hProcess)
    return int(code.value)


def run_ps_elevated(script: str, timeout=3600, visible=False):
    """Executa um script PowerShell como administrador (pede UAC se preciso) e devolve o que o
    script gravar em $env:LIMPAPC_OUT como JSON. Use no script: `$result | ConvertTo-Json -Depth 5 |
    Set-Content -Encoding UTF8 $out` (a variável $out já vem definida).

    Retorna (código, dados_ou_None). Código -1 = usuário recusou o UAC."""
    if not IS_WIN:
        raise NotWindows("disponível apenas no Windows")
    tmp = tempfile.mkdtemp(prefix="limpaone_")
    out = os.path.join(tmp, "out.json")
    ps1 = os.path.join(tmp, "script.ps1")
    with open(ps1, "w", encoding="utf-8-sig") as f:
        f.write(PS_PREFIX + f"\n$out = '{out}'\n" + script)
    args = f'-NoProfile -ExecutionPolicy Bypass -File "{ps1}"'
    if is_admin():
        rc, _, _ = run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1], timeout=timeout)
    else:
        rc = shell_execute_wait("powershell.exe", args, "runas", 1 if visible else 0, timeout)
    data = None
    if os.path.exists(out):
        try:
            with open(out, encoding="utf-8-sig") as f:
                data = json.load(f)
        except ValueError:
            data = None
    shutil.rmtree(tmp, ignore_errors=True)
    return rc, data


def open_admin_console(command: str) -> bool:
    """Abre um console visível (como administrador) executando o comando, para o usuário acompanhar."""
    if not IS_WIN:
        return False
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f'/k "{command}"', None, 1)
    return rc > 32


# ------------------------------------------------------------------ winget
def winget_path() -> str | None:
    if not IS_WIN:
        return None
    p = shutil.which("winget")
    if p:
        return p
    local = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "winget.exe")
    return local if os.path.exists(local) else None


WINGET_FLAGS = ["--accept-source-agreements", "--disable-interactivity"]


def winget(args: list[str], timeout=1800) -> tuple[int, str, str]:
    exe = winget_path()
    if not exe:
        return 127, "", "winget não encontrado (instale o 'Instalador de Aplicativo' pela Microsoft Store)"
    return run([exe] + args + WINGET_FLAGS, timeout=timeout)


def parse_winget_table(text: str) -> list[dict]:
    """Converte a tabela de texto do winget (list/upgrade/search) em dicionários.

    As colunas são detectadas pela linha de cabeçalho (acima da linha de traços), o que funciona
    em qualquer idioma. Chaves retornadas: name, id, version, available, source (as que existirem)."""
    lines = [ln.rstrip("\r") for ln in text.replace("\r\n", "\n").split("\n")]
    # remove animações de progresso (linhas com \r ou caracteres de barra)
    lines = [ln.split("\r")[-1] for ln in lines]
    sep = next((i for i, ln in enumerate(lines) if ln.strip().startswith("---") and set(ln.strip()) <= {"-"}), None)
    if sep is None or sep == 0:
        return []
    header = lines[sep - 1]
    starts = []
    i = 0
    while i < len(header):
        if header[i] != " " and (i == 0 or header[i - 1] == " "):
            starts.append(i)
        i += 1
    keys = ["name", "id", "version", "available", "source"]
    if len(starts) == 4:            # winget list sem coluna "Disponível"
        keys = ["name", "id", "version", "source"]
    elif len(starts) == 3:          # winget search sem "Origem"
        keys = ["name", "id", "version"]
    rows = []
    for ln in lines[sep + 1:]:
        if not ln.strip() or len(ln) < starts[-1] - 5:
            continue
        if ln.strip()[0].isdigit() and ("upgrade" in ln.lower() or "atualiza" in ln.lower()):
            continue  # linha de rodapé "N atualizações disponíveis"
        row = {}
        for k, key in enumerate(keys[:len(starts)]):
            a = starts[k]
            b = starts[k + 1] if k + 1 < len(starts) else None
            row[key] = ln[a:b].strip() if b else ln[a:].strip()
        if row.get("id") and " " not in row["id"]:
            rows.append(row)
    return rows


def wait_until(pred, timeout=10.0, step=0.2) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(step)
    return False
