"""Funções utilitárias compartilhadas pelo LimpaOne."""
from __future__ import annotations

import ctypes
import datetime
import os
import shutil
import stat
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass, field

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

# Evita abrir janelas de console ao chamar programas externos no Windows.
NO_WINDOW = 0x08000000 if IS_WIN else 0


@dataclass
class Item:
    """Uma linha de resultado em qualquer aba."""
    path: str                      # identificador (caminho, PID, chave de registro...)
    size: int = 0
    values: tuple = ()             # textos exibidos nas colunas
    raw: tuple = ()                # valores usados para ordenar (mesma ordem de values)
    kind: str = "file"
    group: int | None = None
    checked: bool = False
    data: dict = field(default_factory=dict)


# ---------------------------------------------------------------- formatação
def fmt_size(n) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            if unit == "B":
                return f"{n:.0f} B"
            return f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024
    return f"{n:.1f} TB"


def fmt_date(ts) -> str:
    if not ts:
        return "—"
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%d/%m/%Y")
    except (OverflowError, OSError, ValueError):
        return "—"


def days_since(ts) -> int | None:
    if not ts:
        return None
    return max(0, int((time.time() - ts) // 86400))


def fmt_days(ts) -> str:
    d = days_since(ts)
    if d is None:
        return "Desconhecido"
    if d == 0:
        return "Hoje"
    if d == 1:
        return "Ontem"
    if d < 60:
        return f"Há {d} dias"
    if d < 730:
        return f"Há {d // 30} meses"
    return f"Há {d // 365} anos"


# ---------------------------------------------------------------- pastas do app
def app_data_dir() -> str:
    if IS_WIN:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "LimpaOne")
    elif IS_MAC:
        d = os.path.expanduser("~/Library/Application Support/LimpaOne")
    else:
        d = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "limpaone")
    if not os.path.exists(d):   # migra os dados da versão anterior (LimpaPC)
        old = os.path.join(os.path.dirname(d), "limpapc" if os.path.basename(d) == "limpaone" else "LimpaPC")
        if os.path.isdir(old):
            try:
                os.rename(old, d)
            except OSError:
                pass
    os.makedirs(d, exist_ok=True)
    return d


def log(msg: str) -> None:
    try:
        with open(os.path.join(app_data_dir(), "historico.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}\n")
    except OSError:
        pass


def home() -> str:
    return os.path.expanduser("~")


def norm(p: str) -> str:
    p = os.path.normcase(os.path.abspath(p))
    if len(p) > 3 or not IS_WIN:
        p = p.rstrip("\\/") or os.sep
    return p


# ---------------------------------------------------------------- discos / memória
def fixed_drives() -> list[str]:
    if IS_WIN:
        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if bitmask & (1 << i):
                root = f"{chr(65 + i)}:\\"
                if ctypes.windll.kernel32.GetDriveTypeW(root) == 3:  # DRIVE_FIXED
                    drives.append(root)
        return drives
    if IS_MAC:
        vols = ["/"]
        try:
            vols += [os.path.join("/Volumes", v) for v in os.listdir("/Volumes")
                     if not os.path.islink(os.path.join("/Volumes", v))]
        except OSError:
            pass
        return vols
    real_fs = {"ext2", "ext3", "ext4", "btrfs", "xfs", "ntfs", "ntfs3", "fuseblk", "vfat",
               "exfat", "f2fs", "zfs", "jfs", "reiserfs"}
    mounts = []
    try:
        with open("/proc/mounts", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3 and parts[2] in real_fs:
                    mp = parts[1].replace("\\040", " ")
                    if not mp.startswith(("/snap", "/boot/efi")) and mp not in mounts:
                        mounts.append(mp)
    except OSError:
        pass
    return mounts or ["/"]


def disks() -> list[tuple[str, int, int, int]]:
    out = []
    for d in fixed_drives():
        try:
            u = shutil.disk_usage(d)
            out.append((d, u.total, u.used, u.free))
        except OSError:
            pass
    return out


def memory_info() -> tuple[int, int]:
    """Retorna (total, usado) em bytes."""
    try:
        import psutil  # type: ignore
        vm = psutil.virtual_memory()
        return vm.total, vm.total - vm.available
    except ImportError:
        pass
    if IS_WIN:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MEMORYSTATUSEX()
        m.dwLength = ctypes.sizeof(m)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullTotalPhys, m.ullTotalPhys - m.ullAvailPhys
    try:
        info = {}
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0]) * 1024
        total = info["MemTotal"]
        return total, total - info.get("MemAvailable", info.get("MemFree", 0))
    except (OSError, KeyError, ValueError):
        return 0, 0


# ---------------------------------------------------------------- proteção do sistema
_EXACT: set[str] = set()
_PREFIXES: list[str] = []
_ALLOWED: list[str] = []
_ALLOWED_INSIDE: list[str] = []   # prefixos protegidos onde só subpastas de cache/lixo conhecidas são liberadas
_CACHE_SUBDIRS = (("windows", "wer"), ("windows", "inetcache"), ("windows", "explorer"))
_CACHE_NAMES = {"cache", "code cache", "gpucache", "cache2", "dxcache", "glcache"}
_PROTECTED_NAMES = {"system volume information", "$recycle.bin", "windowsapps",
                    "pagefile.sys", "hiberfil.sys", "swapfile.sys", "bootmgr", "bootnxt",
                    "ntuser.dat", "usrclass.dat"}


def _init_protection() -> None:
    h = home()
    if IS_WIN:
        windir = os.environ.get("WINDIR", r"C:\Windows")
        _PREFIXES.append(norm(windir))
        _ALLOWED.extend(norm(os.path.join(windir, *p)) for p in
                        (("Temp",), ("SoftwareDistribution", "Download"), ("Logs", "CBS"),
                         ("Minidump",), ("LiveKernelReports",)))
        for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "ProgramData",
                    "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PUBLIC", "CommonProgramFiles",
                    "CommonProgramFiles(x86)", "ALLUSERSPROFILE", "TEMP", "TMP"):
            v = os.environ.get(var)
            if v:
                _EXACT.add(norm(v))
        for i in range(26):
            _EXACT.add(norm(f"{chr(65 + i)}:\\"))
        # pastas inteiras que nunca devem ser apagadas (por prefixo)
        sysdrive = os.environ.get("SystemDrive", "C:") + "\\"
        for var in ("CommonProgramFiles", "CommonProgramFiles(x86)", "CommonProgramW6432"):
            v = os.environ.get(var)
            if v:
                _PREFIXES.append(norm(v))
        pf_roots = {os.environ.get(v) for v in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432")}
        pf_roots |= {os.path.join(sysdrive, "Program Files"), os.path.join(sysdrive, "Program Files (x86)")}
        for root in filter(None, pf_roots):
            _EXACT.add(norm(root))
            for sub in ("Common Files", "Windows Defender", "Windows Defender Advanced Threat Protection",
                        "Windows NT", "Windows Mail", "Windows Media Player", "Windows Photo Viewer",
                        "Windows Security", "Windows Sidebar", "WindowsPowerShell", "Internet Explorer",
                        "ModifiableWindowsApps", "Microsoft Update Health Tools", "dotnet"):
                _PREFIXES.append(norm(os.path.join(root, sub)))
        for sub in ("Boot", "EFI", "Recovery", os.path.join("Users", "Default"),
                    os.path.join("Users", "Public"), os.path.join("Users", "All Users")):
            _PREFIXES.append(norm(os.path.join(sysdrive, sub)))
        pd = os.environ.get("ProgramData") or os.path.join(sysdrive, "ProgramData")
        _PREFIXES.append(norm(os.path.join(pd, "Microsoft")))
        _ALLOWED_INSIDE.append(norm(os.path.join(pd, "Microsoft")))
        for v in ("APPDATA", "LOCALAPPDATA"):
            base = os.environ.get(v)
            if base:
                _PREFIXES.append(norm(os.path.join(base, "Microsoft")))
                _ALLOWED_INSIDE.append(norm(os.path.join(base, "Microsoft")))
        for p in (".ssh", ".gnupg"):
            _PREFIXES.append(norm(os.path.join(h, p)))
        users_root = os.path.dirname(h)
        _EXACT.add(norm(users_root))
        for sub in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos",
                    "AppData", os.path.join("AppData", "LocalLow"), "OneDrive", "Favorites", "Saved Games",
                    "Contacts", "Links", "Searches", "3D Objects", "iCloudDrive", "Dropbox", "Google Drive"):
            _EXACT.add(norm(os.path.join(h, sub)))
    else:
        for p in ("/", "/home", "/root", "/tmp", "/var", "/var/tmp", "/var/cache", "/opt",
                  "/mnt", "/media", "/srv", "/Users", "/Applications", "/Volumes", h):
            _EXACT.add(norm(p))
        for sub in (".config", ".local", ".local/share", ".cache", "Desktop", "Documents",
                    "Downloads", "Pictures", "Music", "Videos", "Área de Trabalho",
                    "Documentos", "Imagens", "Músicas", "Vídeos", "Library"):
            _EXACT.add(norm(os.path.join(h, sub)))
        for p in ("/bin", "/boot", "/dev", "/etc", "/lib", "/lib32", "/lib64", "/libx32",
                  "/proc", "/run", "/sbin", "/sys", "/usr", "/var/lib", "/snap", "/System",
                  "/Library", "/private/var/db", "/efi"):
            _PREFIXES.append(norm(p))
        for p in (".ssh", ".gnupg", ".pki", ".local/share/keyrings"):
            _PREFIXES.append(norm(os.path.join(h, p)))


_init_protection()


def is_link_like(path: str) -> bool:
    """True para link simbólico, junction ou qualquer ponto de reparse (o alvo NÃO deve ser tocado)."""
    try:
        if os.path.islink(path):
            return True
        isj = getattr(os.path, "isjunction", None)
        if isj is not None and isj(path):
            return True
        st = os.lstat(path)
        return bool(getattr(st, "st_file_attributes", 0) & 0x400)   # FILE_ATTRIBUTE_REPARSE_POINT
    except OSError:
        return False


def _unsafe_path_form(p: str) -> bool:
    """Formas de caminho que driblam a comparação de texto (UNC, prefixo de dispositivo, ponto final)."""
    if not IS_WIN:
        return False
    if p.startswith(("\\\\", "//")):
        return True
    return any(seg.endswith((".", " ")) and seg not in (".", "..")
               for seg in p.replace("/", "\\").split("\\")[1:] if seg)


def is_protected(path: str) -> bool:
    """True se o caminho é crítico para o sistema e nunca deve ser apagado."""
    if _unsafe_path_form(path):
        return True
    if _is_protected_text(path):
        return True
    try:
        # resolve junctions, links e nomes curtos 8.3 (GABRIE~1). Para um link, só a pasta onde ele está
        # importa (apagar um link nunca toca o destino).
        if is_link_like(path):
            real = os.path.join(os.path.realpath(os.path.dirname(os.path.abspath(path))), os.path.basename(path))
        else:
            real = os.path.realpath(path)
    except (OSError, ValueError):
        return True
    r = norm(real)
    if r != norm(path) and _is_protected_text(real):
        return True
    if IS_WIN and _USERS_ROOT and r.startswith(_USERS_ROOT + os.sep) and not (
            r == _HOME or r.startswith(_HOME + os.sep)):
        return True                     # perfil de OUTRO usuário: protegido inteiro
    return False


def _is_protected_text(path: str) -> bool:
    p = norm(path)
    if p in _EXACT:
        return True
    if IS_WIN and os.path.dirname(p) == _HOME and os.path.basename(p).startswith("onedrive"):
        return True     # "OneDrive - Empresa" etc. (a pasta em si; apagar apaga em todos os dispositivos)
    parts = [x.lower() for x in p.replace("\\", "/").split("/") if x]
    if any(x in _PROTECTED_NAMES for x in parts):
        return True
    for a in _ALLOWED:
        if p.startswith(a + os.sep):
            return False
    for a in _ALLOWED_INSIDE:
        if p.startswith(a + os.sep):
            rest = [x.lower() for x in p[len(a) + 1:].split(os.sep)]
            if any(tuple(rest[:len(c)]) == c and len(rest) > len(c) for c in _CACHE_SUBDIRS):
                return False
            if any(x in _CACHE_NAMES for x in rest[:-1]):     # algo DENTRO de uma pasta de cache
                return False
    for pre in _PREFIXES:
        if p == pre or p.startswith(pre + os.sep):
            return True
    return False


_HOME = norm(os.path.realpath(home()))
_USERS_ROOT = norm(os.path.dirname(_HOME)) if IS_WIN else ""


# ---------------------------------------------------------------- apagar / lixeira
def _retry_writable(func, path, *_):
    if func in (os.path.islink, getattr(os.path, "isjunction", None)):
        raise OSError(f"recusado: {path} é um link/junction")
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
    func(path)


def remove_link(path: str) -> None:
    """Remove só o link/junction (nunca o conteúdo do alvo)."""
    try:
        os.unlink(path)
    except (IsADirectoryError, PermissionError, OSError):
        os.rmdir(path)          # junction de pasta no Windows sai com rmdir (o alvo fica intacto)


def _rmtree(path: str) -> None:
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_retry_writable)
    else:
        shutil.rmtree(path, onerror=_retry_writable)


def delete_path(path: str, to_trash: bool) -> None:
    """Apaga arquivo/pasta (ou envia para a Lixeira). Lança exceção em caso de erro."""
    if is_protected(path):
        raise PermissionError("caminho protegido do sistema — não será apagado")
    if not os.path.lexists(path):
        return
    if is_link_like(path):
        remove_link(path)       # link/junction: apaga só o atalho, nunca o destino
        return
    if to_trash:
        send_to_trash(path)
        return
    if os.path.isdir(path):
        _rmtree(path)
    else:
        try:
            os.remove(path)
        except PermissionError:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            os.remove(path)


def entry_size(path: str, cancel=None) -> tuple[int, int]:
    """Tamanho total e número de arquivos de um arquivo ou pasta."""
    try:
        if not os.path.isdir(path) or is_link_like(path):
            return os.lstat(path).st_size, 1
    except OSError:
        return 0, 0
    total = files = 0
    stack = [path]
    while stack:
        if cancel is not None and cancel.is_set():
            break
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_symlink() or _is_junction(e):
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(e.path)
                        else:
                            total += e.stat(follow_symlinks=False).st_size
                            files += 1
                    except OSError:
                        pass
        except OSError:
            pass
    return total, files


def _is_junction(entry) -> bool:
    fn = getattr(entry, "is_junction", None)
    if fn is not None:
        try:
            return fn()
        except OSError:
            return False
    if IS_WIN:
        try:
            return bool(entry.stat(follow_symlinks=False).st_file_attributes & 0x400)
        except (OSError, AttributeError):
            return False
    return False


def clear_contents(path: str, patterns=None, min_age_hours: float = 0,
                   only_mine: bool = False) -> tuple[int, int]:
    """Apaga o conteúdo de uma pasta (sem apagar a própria pasta).

    Retorna (bytes liberados, itens que não puderam ser apagados — geralmente em uso).
    """
    import fnmatch
    freed = errors = 0
    reason = unsafe_clear_target(path)
    if reason:
        log(f"LIMPEZA RECUSADA em {path!r}: {reason}")
        return 0, 1
    limit = time.time() - min_age_hours * 3600
    uid = os.getuid() if (only_mine and hasattr(os, "getuid")) else None
    try:
        entries = list(os.scandir(path))
    except OSError:
        return 0, 1
    for e in entries:
        try:
            if patterns and not any(fnmatch.fnmatch(e.name.lower(), p) for p in patterns):
                continue
            st = e.stat(follow_symlinks=False)
            if min_age_hours and newest_time(e.path, st, limit) > limit:
                continue
            if uid is not None and st.st_uid != uid:
                continue
            size, _ = entry_size(e.path)
            delete_path(e.path, to_trash=False)
            freed += size
        except Exception:  # noqa: BLE001 - arquivos em uso são esperados
            errors += 1
    return freed, errors


def unsafe_clear_target(path: str) -> str:
    """Motivo para NÃO esvaziar esta pasta (ou "" se é segura). Evita apagar um disco ou perfil inteiro
    quando uma variável (TEMP, LOCALAPPDATA…) está vazia, errada ou aponta para outro lugar."""
    if not path or not os.path.isabs(path):
        return "caminho relativo ou vazio"
    if is_link_like(path):
        return "a pasta é um link/junction"
    try:
        real = os.path.realpath(path)
    except (OSError, ValueError):
        return "caminho inválido"
    if norm(real) != norm(os.path.abspath(path)):
        return f"o caminho real é outro ({real})"
    p = norm(path)
    if os.path.dirname(p) == p:
        return "é a raiz de um disco"
    if p == _HOME or p == _USERS_ROOT or (not IS_WIN and p in ("/home", "/root", "/Users")):
        return "é a pasta de usuários ou o perfil"
    for sub in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos", "OneDrive",
                "AppData", os.path.join("AppData", "Local"), os.path.join("AppData", "Roaming")):
        if p == norm(os.path.join(home(), sub)):
            return "é uma pasta pessoal"
    if IS_WIN:
        for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramData", "WINDIR", "SystemRoot",
                    "APPDATA", "LOCALAPPDATA", "USERPROFILE"):
            v = os.environ.get(var)
            if v and p == norm(v):
                return f"é a pasta %{var}%"
    return ""


def newest_time(path: str, st=None, stop_at: float | None = None, budget: int = 5000) -> float:
    """O momento mais recente em que algo dentro do item foi criado/alterado (mtime e ctime, recursivo).
    Para quando acha algo mais novo que `stop_at` ou após `budget` entradas (aí devolve "agora")."""
    if st is None:
        st = os.lstat(path)
    best = max(st.st_mtime, getattr(st, "st_birthtime", 0) or 0, st.st_ctime if IS_WIN else 0)
    if not stat.S_ISDIR(st.st_mode) or is_link_like(path):
        return best
    stack, seen = [path], 0
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    seen += 1
                    if seen > budget:
                        return time.time()
                    try:
                        s2 = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    t = max(s2.st_mtime, getattr(s2, "st_birthtime", 0) or 0, s2.st_ctime if IS_WIN else 0)
                    best = max(best, t)
                    if stop_at is not None and best > stop_at:
                        return best
                    if e.is_dir(follow_symlinks=False) and not (e.is_symlink() or _is_junction(e)):
                        stack.append(e.path)
        except OSError:
            continue
    return best


def send_to_trash(path: str) -> None:
    path = os.path.abspath(path)
    if IS_WIN:
        _win_trash(path)        # implementação própria: NUNCA apaga de vez sem avisar
        return
    try:
        from send2trash import send2trash  # type: ignore
        send2trash(path)
        return
    except ImportError:
        pass
    if IS_WIN:
        _win_trash(path)
    elif IS_MAC:
        dest_dir = os.path.expanduser("~/.Trash")
        dest = _unique(dest_dir, os.path.basename(path))
        shutil.move(path, dest)
    else:
        _fdo_trash(path)


def _unique(folder: str, name: str) -> str:
    base, ext = os.path.splitext(name)
    cand = os.path.join(folder, name)
    i = 1
    while os.path.lexists(cand):
        cand = os.path.join(folder, f"{base}.{i}{ext}")
        i += 1
    return cand


def _fdo_trash(path: str) -> None:
    """Lixeira padrão freedesktop.org (GNOME, KDE, XFCE...)."""
    trash = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "Trash")
    files_dir = os.path.join(trash, "files")
    info_dir = os.path.join(trash, "info")
    os.makedirs(files_dir, exist_ok=True)
    os.makedirs(info_dir, exist_ok=True)
    dest = _unique(files_dir, os.path.basename(path))
    name = os.path.basename(dest)
    info = ("[Trash Info]\nPath=" + urllib.parse.quote(path) +
            "\nDeletionDate=" + datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S") + "\n")
    with open(os.path.join(info_dir, name + ".trashinfo"), "w", encoding="utf-8") as f:
        f.write(info)
    shutil.move(path, dest)


def _win_trash(path: str) -> None:
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        if ctypes.sizeof(ctypes.c_void_p) == 4:
            _pack_ = 1
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                    ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    drive = os.path.splitdrive(path)[0]
    if not drive or drive.startswith("\\\\"):
        raise OSError("unidade de rede não tem Lixeira — use a exclusão permanente se tiver certeza")
    dtype = ctypes.windll.kernel32.GetDriveTypeW(drive + "\\")
    if dtype == 2:
        raise OSError("pendrive/cartão não tem Lixeira — use a exclusão permanente se tiver certeza")
    if dtype == 4:
        raise OSError("unidade de rede não tem Lixeira — use a exclusão permanente se tiver certeza")
    FO_DELETE = 3
    # ALLOWUNDO | NOCONFIRMATION | SILENT | NOERRORUI | WANTNUKEWARNING
    # WANTNUKEWARNING: se o item não couber na Lixeira o Windows PERGUNTA antes de apagar de vez.
    flags = 0x40 | 0x10 | 0x04 | 0x400 | 0x4000
    op = SHFILEOPSTRUCTW(None, FO_DELETE, path + "\0", None, flags, False, None, None)
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if rc != 0 or op.fAnyOperationsAborted:
        raise OSError(f"não foi possível enviar para a Lixeira (código {rc})")
    if os.path.lexists(path):
        raise OSError("o arquivo pode estar em uso")


# ---------------------------------------------------------------- sistema
def open_location(path: str) -> None:
    try:
        if IS_WIN:
            if os.path.isdir(path):
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif IS_MAC:
            subprocess.Popen(["open", "-R", path])
        else:
            target = path if os.path.isdir(path) else os.path.dirname(path)
            subprocess.Popen(["xdg-open", target])
    except Exception:  # noqa: BLE001
        pass


def open_uri(uri: str) -> None:
    try:
        if IS_WIN:
            os.startfile(uri)  # type: ignore[attr-defined]
        elif IS_MAC:
            subprocess.Popen(["open", uri])
        else:
            subprocess.Popen(["xdg-open", uri])
    except Exception:  # noqa: BLE001
        pass


def is_admin() -> bool:
    try:
        if IS_WIN:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        return os.geteuid() == 0
    except Exception:  # noqa: BLE001
        return False


def relaunch_as_admin() -> bool:
    """Reabre o programa pedindo permissão de administrador (Windows)."""
    if not IS_WIN:
        return False
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, ""
    else:
        exe = sys.executable
        params = subprocess.list2cmdline([os.path.abspath(sys.argv[0])] + sys.argv[1:])
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
    return rc > 32


def run_quiet(cmd, timeout=60) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=NO_WINDOW, errors="replace")
        return r.stdout
    except (OSError, subprocess.SubprocessError):
        return ""
