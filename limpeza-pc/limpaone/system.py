"""Recursos do sistema: programas, restos de desinstalação, processos, inicialização e lixeira."""
from __future__ import annotations

import codecs
import ctypes
import glob
import os
import re
import shutil
import signal
import struct
import subprocess
import time

from .utils import (IS_LINUX, IS_MAC, IS_WIN, NO_WINDOW, Item, app_data_dir, entry_size,
                    fmt_date, fmt_days, fmt_size, home, is_protected, log, memory_info, norm,
                    run_quiet)

if IS_WIN:
    import winreg  # type: ignore

try:
    import psutil  # type: ignore
except ImportError:  # psutil é opcional
    psutil = None


def _alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


_GENERIC = {"the", "and", "for", "inc", "ltd", "llc", "corp", "corporation", "software",
            "version", "edition", "update", "setup", "x64", "x86", "64bit", "32bit", "bit",
            "pro", "free", "app", "apps", "tools", "tool", "system", "systems", "pack",
            "runtime", "redistributable", "package", "client", "service", "services", "co",
            "gmbh", "company", "technologies", "technology", "limited", "microsoft", "windows"}


def _tokens(s: str) -> set[str]:
    out = set()
    full = _alnum(s)
    if len(full) >= 3:
        out.add(full)
    for w in re.split(r"[^A-Za-z0-9]+", s or ""):
        w = w.lower()
        if len(w) >= 4 and w not in _GENERIC and not w.isdigit():
            out.add(w)
    return out


def _matches(name: str, tokens: set[str]) -> bool:
    n = _alnum(name)
    if len(n) < 3:
        return True  # nomes curtos demais: não arriscamos
    if n in tokens:
        return True
    for t in tokens:
        if len(t) >= 4 and (t in n or (len(n) >= 4 and n in t)):
            return True
    return False


def _newest_mtime(path: str, max_entries=3000) -> float:
    """Data da modificação mais recente dentro da pasta (amostra limitada)."""
    try:
        newest = os.stat(path).st_mtime
    except OSError:
        return 0
    stack, n = [path], 0
    while stack and n < max_entries:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    n += 1
                    try:
                        st = e.stat(follow_symlinks=False)
                        newest = max(newest, st.st_mtime)
                        if e.is_dir(follow_symlinks=False) and not e.is_symlink():
                            stack.append(e.path)
                    except OSError:
                        pass
        except OSError:
            pass
    return newest


# =================================================================== PROGRAMAS
_UNINSTALL = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"


def _reg_values(key) -> dict:
    vals, i = {}, 0
    while True:
        try:
            name, val, _ = winreg.EnumValue(key, i)
        except OSError:
            break
        vals[name] = val
        i += 1
    return vals


def _reg_subkeys(key) -> list[str]:
    subs, i = [], 0
    while True:
        try:
            subs.append(winreg.EnumKey(key, i))
        except OSError:
            break
        i += 1
    return subs


def _filetime_to_unix(ft: int) -> float:
    return ft / 10_000_000 - 11644473600 if ft else 0


def _prefetch_times() -> dict[str, float]:
    """exe (minúsculo) -> última execução, pela pasta Prefetch (exige administrador)."""
    out: dict[str, float] = {}
    pf = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Prefetch")
    try:
        for e in os.scandir(pf):
            if e.name.lower().endswith(".pf") and "-" in e.name:
                exe = e.name.rsplit("-", 1)[0].lower()
                out[exe] = max(out.get(exe, 0), e.stat().st_mtime)
    except OSError:
        pass
    return out


_KNOWN_FOLDERS = {
    "{6d809377-6af0-444b-8957-a3773f02200e}": os.environ.get("ProgramW6432", r"C:\Program Files"),
    "{7c5a40ef-a0fb-4bfc-874a-c0f2e0b9fa8e}": os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    "{f38bf404-1d43-42f2-9305-67de0b28fc23}": os.environ.get("WINDIR", r"C:\Windows"),
    "{1ac14e77-02e7-4e5d-b744-2eb1ae5198b7}": os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32"),
    "{d65231b0-b2f1-4857-a4ce-a8e7c6ea7d27}": os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "SysWOW64"),
}


def _userassist_times() -> tuple[dict[str, float], dict[str, float]]:
    """Últimas execuções registradas pelo Windows (UserAssist) — não exige administrador.

    Retorna (caminho completo -> data, nome do exe -> data)."""
    by_path: dict[str, float] = {}
    by_exe: dict[str, float] = {}
    base = r"Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist"
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, base)
    except OSError:
        return by_path, by_exe
    for guid in _reg_subkeys(root):
        try:
            k = winreg.OpenKey(root, guid + r"\Count")
        except OSError:
            continue
        for name, data in _reg_values(k).items():
            if not isinstance(data, bytes) or len(data) < 68:
                continue
            path = codecs.decode(name, "rot_13")
            low = path.lower()
            for g, real in _KNOWN_FOLDERS.items():
                if low.startswith(g):
                    path = real + path[len(g):]
                    break
            ts = _filetime_to_unix(struct.unpack_from("<Q", data, 60)[0])
            if ts <= 0:
                continue
            p = os.path.normcase(path)
            by_path[p] = max(by_path.get(p, 0), ts)
            exe = os.path.basename(p)
            if exe.endswith(".exe"):
                by_exe[exe] = max(by_exe.get(exe, 0), ts)
    return by_path, by_exe


def _exe_from_command(cmd: str) -> str:
    cmd = (cmd or "").strip()
    if not cmd:
        return ""
    if cmd.startswith('"'):
        return cmd[1:].split('"', 1)[0]
    low = cmd.lower()
    idx = low.find(".exe")
    return cmd[: idx + 4] if idx >= 0 else cmd.split(" ")[0]


def _program_exes(loc: str, icon: str) -> list[str]:
    exes = []
    icon_exe = _exe_from_command((icon or "").split(",")[0])
    if icon_exe.lower().endswith(".exe"):
        exes.append(icon_exe)
    if loc and os.path.isdir(loc):
        for pattern in ("*.exe", os.path.join("*", "*.exe")):
            for e in glob.glob(os.path.join(loc, pattern))[:40]:
                if not re.search(r"unins|uninst|setup|update|crash|helper|install", os.path.basename(e), re.I):
                    exes.append(e)
    return exes


def windows_programs(cancel, progress) -> list[dict]:
    progress("Lendo programas instalados no registro…")
    pf = _prefetch_times()
    ua_path, ua_exe = _userassist_times()
    sources = [(winreg.HKEY_LOCAL_MACHINE, "HKLM", winreg.KEY_WOW64_64KEY, "64"),
               (winreg.HKEY_LOCAL_MACHINE, "HKLM", winreg.KEY_WOW64_32KEY, "32"),
               (winreg.HKEY_CURRENT_USER, "HKCU", 0, "64")]
    progs, seen = [], set()
    for hive, hname, flag, view in sources:
        try:
            root = winreg.OpenKey(hive, _UNINSTALL, 0, winreg.KEY_READ | flag)
        except OSError:
            continue
        for sub in _reg_subkeys(root):
            if cancel.is_set():
                return progs
            try:
                v = _reg_values(winreg.OpenKey(root, sub, 0, winreg.KEY_READ | flag))
            except OSError:
                continue
            name = v.get("DisplayName")
            if not isinstance(name, str) or not name.strip():
                continue
            if v.get("SystemComponent") == 1 or v.get("ParentKeyName") or \
                    str(v.get("ReleaseType", "")).lower() in ("update", "hotfix", "security update", "service pack"):
                continue
            key = (name.lower().strip(), str(v.get("DisplayVersion", "")))
            if key in seen:
                continue
            seen.add(key)
            loc = str(v.get("InstallLocation") or "").strip().strip('"')
            unin = str(v.get("UninstallString") or "")
            icon = str(v.get("DisplayIcon") or "").strip('"')
            date = str(v.get("InstallDate") or "")
            inst_ts = 0.0
            if re.fullmatch(r"\d{8}", date):
                try:
                    inst_ts = time.mktime(time.strptime(date, "%Y%m%d"))
                except (ValueError, OverflowError):
                    pass
            exes = _program_exes(loc, icon)
            last = 0.0
            for exe in exes:
                b = os.path.basename(exe).lower()
                last = max(last, pf.get(b, 0), ua_path.get(os.path.normcase(exe), 0), ua_exe.get(b, 0))
            if loc and not last:
                lnorm = os.path.normcase(loc.rstrip("\\"))
                for p, ts in ua_path.items():
                    if p.startswith(lnorm + "\\"):
                        last = max(last, ts)
            size = int(v.get("EstimatedSize") or 0) * 1024
            if not size and loc and os.path.isdir(loc) and not is_protected(loc):
                progress(f"Calculando tamanho: {name}")
                size = entry_size(loc, cancel)[0]
            unin_exe = _exe_from_command(unin)
            broken = bool(unin) and not unin.lower().startswith("msiexec") and \
                os.path.isabs(unin_exe) and not os.path.exists(unin_exe) and \
                not (loc and os.path.isdir(loc))
            progs.append({
                "name": name.strip(), "version": str(v.get("DisplayVersion") or ""),
                "publisher": str(v.get("Publisher") or ""), "installed": inst_ts,
                "size": size, "location": loc, "uninstall": unin,
                "quiet": str(v.get("QuietUninstallString") or ""), "exes": exes,
                "last_used": last, "broken": broken,
                "regkey": f"{hname}\\{_UNINSTALL}\\{sub}", "view": view,
            })
    return progs


def _linux_desktop_names() -> set[str]:
    names = set()
    dirs = ["/usr/share/applications", "/usr/local/share/applications",
            os.path.expanduser("~/.local/share/applications"),
            "/var/lib/flatpak/exports/share/applications",
            os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
            "/var/lib/snapd/desktop/applications"]
    for d in dirs:
        for f in glob.glob(os.path.join(d, "*.desktop")):
            names.add(os.path.basename(f)[:-8].lower())
    return names


def linux_programs(cancel, progress, only_apps=True) -> list[dict]:
    progs = []
    desktop = _linux_desktop_names()
    if shutil.which("dpkg-query"):
        progress("Lendo pacotes instalados (dpkg)…")
        out = run_quiet(["dpkg-query", "-W", "-f=${Package}\t${Installed-Size}\t${Version}\t"
                         "${db:Status-Status}\t${binary:Summary}\n"])
        for line in out.splitlines():
            if cancel.is_set():
                break
            parts = line.split("\t")
            if len(parts) < 5 or parts[3] != "installed":
                continue
            pkg = parts[0]
            files = []
            for lst in glob.glob(f"/var/lib/dpkg/info/{pkg}.list") + glob.glob(f"/var/lib/dpkg/info/{pkg}:*.list"):
                try:
                    with open(lst, encoding="utf-8", errors="replace") as f:
                        files += [x.strip() for x in f]
                except OSError:
                    pass
            has_desktop = any(x.startswith("/usr/share/applications/") and x.endswith(".desktop") for x in files)
            if only_apps and not has_desktop:
                continue
            last = 0.0
            for x in files:
                if "/bin/" in x or x.startswith("/opt/"):
                    try:
                        st = os.stat(x)
                        if os.path.isfile(x) and os.access(x, os.X_OK):
                            last = max(last, st.st_atime)
                    except OSError:
                        pass
            progs.append({"name": pkg, "version": parts[2], "publisher": parts[4],
                          "installed": 0, "size": int(parts[1] or 0) * 1024, "location": "",
                          "uninstall": ["apt-get", "remove", "-y", pkg], "root": True,
                          "last_used": last, "broken": False, "exes": []})
    elif shutil.which("rpm"):
        progress("Lendo pacotes instalados (rpm)…")
        out = run_quiet(["rpm", "-qa", "--qf", "%{NAME}\t%{SIZE}\t%{VERSION}\t%{INSTALLTIME}\t%{SUMMARY}\n"])
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            if only_apps and parts[0].lower() not in desktop:
                continue
            exe = shutil.which(parts[0])
            last = os.stat(exe).st_atime if exe else 0
            progs.append({"name": parts[0], "version": parts[2], "publisher": parts[4],
                          "installed": float(parts[3] or 0), "size": int(parts[1] or 0),
                          "location": "", "uninstall": ["dnf", "remove", "-y", parts[0]], "root": True,
                          "last_used": last, "broken": False, "exes": []})
    elif shutil.which("pacman"):
        progress("Lendo pacotes instalados (pacman)…")
        for pkg in run_quiet(["pacman", "-Qeq"]).split():
            if only_apps and pkg.lower() not in desktop:
                continue
            exe = shutil.which(pkg)
            progs.append({"name": pkg, "version": "", "publisher": "", "installed": 0, "size": 0,
                          "location": "", "uninstall": ["pacman", "-R", "--noconfirm", pkg], "root": True,
                          "last_used": os.stat(exe).st_atime if exe else 0, "broken": False, "exes": []})
    if shutil.which("flatpak"):
        progress("Lendo aplicativos Flatpak…")
        out = run_quiet(["flatpak", "list", "--app", "--columns=application,name,version,size"])
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 2 or parts[0] == "Application ID":
                continue
            app_id = parts[0]
            data = os.path.expanduser(f"~/.var/app/{app_id}")
            last = _newest_mtime(data, 500) if os.path.isdir(data) else 0
            progs.append({"name": f"{parts[1]} (Flatpak)", "version": parts[2] if len(parts) > 2 else "",
                          "publisher": app_id, "installed": 0,
                          "size": _parse_human_size(parts[3]) if len(parts) > 3 else 0,
                          "location": data, "uninstall": ["flatpak", "uninstall", "-y", app_id],
                          "root": False, "last_used": last, "broken": False, "exes": []})
    if shutil.which("snap"):
        progress("Lendo aplicativos Snap…")
        for line in run_quiet(["snap", "list"]).splitlines()[1:]:
            parts = line.split()
            if not parts or parts[0] in ("core", "core18", "core20", "core22", "core24", "snapd", "bare") \
                    or parts[0].startswith(("gnome-", "gtk-", "kf5-", "kf6-", "mesa-")):
                continue
            snapdir = os.path.join("/snap", parts[0], "current")
            size = 0
            for f in glob.glob(f"/var/lib/snapd/snaps/{parts[0]}_*.snap"):
                size = max(size, os.path.getsize(f))
            data = os.path.expanduser(f"~/snap/{parts[0]}")
            progs.append({"name": f"{parts[0]} (Snap)", "version": parts[1] if len(parts) > 1 else "",
                          "publisher": parts[4] if len(parts) > 4 else "", "installed": 0,
                          "size": size, "location": snapdir, "uninstall": ["snap", "remove", parts[0]],
                          "root": True, "last_used": _newest_mtime(data, 500) if os.path.isdir(data) else 0,
                          "broken": False, "exes": []})
    return progs


def _parse_human_size(s: str) -> int:
    m = re.match(r"([\d.,]+)\s*([kKMGT]?)B?", (s or "").strip().replace("\xa0", " "))
    if not m:
        return 0
    num = float(m.group(1).replace(",", "."))
    return int(num * {"": 1, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12}[m.group(2)])


def mac_programs(cancel, progress) -> list[dict]:
    progs = []
    for app in sorted(glob.glob("/Applications/*.app") + glob.glob(os.path.expanduser("~/Applications/*.app"))):
        if cancel.is_set():
            break
        progress(f"Analisando {os.path.basename(app)}")
        last = 0.0
        out = run_quiet(["mdls", "-raw", "-name", "kMDItemLastUsedDate", app], timeout=10).strip()
        if out and out != "(null)":
            try:
                last = time.mktime(time.strptime(out[:19], "%Y-%m-%d %H:%M:%S")) - time.timezone
            except ValueError:
                pass
        progs.append({"name": os.path.basename(app)[:-4], "version": "", "publisher": "",
                      "installed": os.stat(app).st_ctime, "size": entry_size(app, cancel)[0],
                      "location": app, "uninstall": "::trash::", "root": False,
                      "last_used": last, "broken": False, "exes": []})
    return progs


def installed_programs(cancel, progress, only_apps=True) -> list[dict]:
    if IS_WIN:
        return windows_programs(cancel, progress)
    if IS_MAC:
        return mac_programs(cancel, progress)
    return linux_programs(cancel, progress, only_apps)


def scan_programs(cancel, progress, unused_days=90, only_apps=True) -> list[Item]:
    items = []
    limit = time.time() - unused_days * 86400
    for p in installed_programs(cancel, progress, only_apps):
        status = "Desinstalador ausente" if p["broken"] else \
            ("Pouco usado" if p["last_used"] and p["last_used"] < limit else
             ("Sem registro de uso" if not p["last_used"] else "Em uso"))
        items.append(Item(
            path=p["name"], size=p["size"],
            values=(p["name"], p["version"], p["publisher"], fmt_size(p["size"]) if p["size"] else "—",
                    fmt_date(p["installed"]), fmt_days(p["last_used"]), status),
            raw=(p["name"].lower(), p["version"], p["publisher"].lower(), p["size"],
                 p["installed"], p["last_used"] or 0, status),
            kind="program", data=p))
    items.sort(key=lambda i: (i.data["last_used"] or 0, -i.size))
    progress(f"{len(items)} programas encontrados.")
    return items


def uninstall_program(p: dict) -> str:
    """Inicia o desinstalador e espera terminar. Retorna mensagem de resultado."""
    cmd = p.get("uninstall")
    if not cmd:
        return "sem desinstalador registrado"
    log(f"DESINSTALAR {p['name']}")
    if cmd == "::trash::":
        from .utils import send_to_trash
        send_to_trash(p["location"])
        return "movido para a Lixeira"
    if isinstance(cmd, list):
        if p.get("root") and os.geteuid() != 0:
            if shutil.which("pkexec"):
                cmd = ["pkexec"] + cmd
            else:
                return "execute no terminal: sudo " + " ".join(cmd)
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        return "ok" if r.returncode == 0 else (r.stderr.strip().splitlines() or ["falhou"])[-1]
    proc = subprocess.Popen(cmd, shell=True)
    proc.wait()
    return "ok" if proc.returncode in (0, 3010, 1641) else f"código de saída {proc.returncode}"


# =================================================================== RESTOS DE PROGRAMAS
_WIN_SKIP = {
    "microsoft", "windows", "windowsapps", "packages", "temp", "tmp", "commonfiles",
    "internetexplorer", "windowsdefender", "windowsdefenderadvancedthreatprotection",
    "windowsmail", "windowsmediaplayer", "windowsmultimediaplatform", "windowsnt",
    "windowsphotoviewer", "windowsportabledevices", "windowssidebar", "windowspowershell",
    "modifiablewindowsapps", "referenceassemblies", "msbuild", "uninstallinformation",
    "microsoftnet", "dotnet", "packagecache", "ssh", "applicationdata", "comms",
    "connecteddevicesplatform", "d3dscache", "history", "publishers", "virtualstore",
    "crashdumps", "programs", "peernetworking", "placeholdertilelogofolder", "desktopini",
    "regidcommicrosoft", "usoshared", "usoprivate", "softwaredistribution", "ssh",
    "startmenu", "templates", "desktop", "documents", "favorites", "intel", "nvidia",
    "nvidiacorporation", "amd", "ati", "realtek", "oem", "drivers", "driverstore", "msi",
    "intelcorporation", "dell", "hp", "lenovo", "asus", "acer", "identities", "media",
    "mozilla", "google", "adobe", "apple", "applecomputer", "java", "oracle", "python",
    "pip", "npm", "npmcache", "nuget", "vscode", "code", "github", "githubdesktop",
    "squirreltemp", "elevateddiagnostics", "diagnosis", "sentinel", "fontcache",
    "gameanalytics", "unity", "unitytechnologies", "steam", "electron", "chromium",
    "cef", "webview2", "edgewebview", "onedrive", "teams", "skype", "office", "outlook",
    "ms", "logs", "log", "cache", "caches", "data", "config", "settings", "backup",
    "inputpersonalization", "speech", "speechone", "ubisoftgamelauncher", "epicgames",
    "unrealengine", "riotgames", "battlenet", "blizzardentertainment", "origin", "ea",
    "electronicarts", "rockstargames", "packagemanagement", "gamedvr", "tile",
    "systemcertificates", "vault", "credentials", "protect", "crypto", "spoolerdata",
    "wsl", "lxss", "docker", "dockerdesktop", "jetbrains", "gradle", "android", "limpaone",
}

_WIN_REG_SKIP = {"microsoft", "classes", "policies", "wow6432node", "clients", "appdatalow",
                 "registeredapplications", "khronos", "odbc", "chromium", "intel", "nvidia",
                 "nvidiacorporation", "realtek", "volatileenvironment", "environment",
                 "wow6432", "partner", "google", "mozilla", "python", "javasoft", "oracle",
                 "apple", "appleinc", "applecomputerinc", "adobe", "gnu", "cygwin", "git",
                 "github", "unity", "unitytechnologies", "valve", "epicgames", "jetbrains",
                 "vmware", "vmwareinc", "inteleditor", "amd", "ati", "atitechnologies",
                 "microsoftcorporation", "pythoncore", "wsl", "docker", "dockerinc", "qtproject",
                 "trolltech", "kde", "freedesktop", "sysinternals", "7zip", "winrar"}


def _process_paths() -> list[str]:
    paths = []
    if psutil:
        for p in psutil.process_iter(["exe"]):
            try:
                if p.info.get("exe"):
                    paths.append(os.path.normcase(p.info["exe"]))
            except Exception:  # noqa: BLE001
                pass
    return paths


def _reg_key_mtime(hive, path) -> float:
    try:
        k = winreg.OpenKey(hive, path)
        return _filetime_to_unix(winreg.QueryInfoKey(k)[2])
    except OSError:
        return 0


def windows_leftovers(min_idle_days, cancel, progress) -> list[Item]:
    progs = windows_programs(cancel, lambda m: progress("Lendo programas instalados…"))
    tokens: set[str] = set()
    locations: list[str] = []
    for p in progs:
        tokens |= _tokens(p["name"]) | _tokens(p["publisher"])
        for loc in [p["location"]] + [os.path.dirname(e) for e in p["exes"]]:
            if loc:
                locations.append(norm(loc))
                tokens |= _tokens(os.path.basename(loc.rstrip("\\/")))
    running = _process_paths()
    for r in running:
        tokens |= _tokens(os.path.basename(os.path.dirname(r)))
    tokens = {t for t in tokens if _alnum(t) not in _WIN_SKIP}
    idle_limit = time.time() - min_idle_days * 86400
    env = os.environ.get
    h = home()
    parents = [
        ("Program Files", env("ProgramW6432") or env("ProgramFiles")),
        ("Program Files (x86)", env("ProgramFiles(x86)")),
        ("ProgramData", env("ProgramData")),
        ("AppData\\Roaming", env("APPDATA")),
        ("AppData\\Local", env("LOCALAPPDATA")),
        ("AppData\\Local\\Programs", os.path.join(env("LOCALAPPDATA") or "", "Programs")),
        ("AppData\\LocalLow", os.path.join(h, "AppData", "LocalLow")),
    ]
    items: list[Item] = []
    seen = set()
    for label, parent in parents:
        if not parent or not os.path.isdir(parent):
            continue
        progress(f"Procurando restos em {label}…")
        try:
            entries = list(os.scandir(parent))
        except OSError:
            continue
        for e in entries:
            if cancel.is_set():
                return items
            try:
                if not e.is_dir(follow_symlinks=False) or e.is_symlink():
                    continue
            except OSError:
                continue
            n = _alnum(e.name)
            nd = norm(e.path)
            if nd in seen or n in _WIN_SKIP or e.name.startswith((".", "{", "$")) or is_protected(e.path):
                continue
            seen.add(nd)
            if any(loc == nd or loc.startswith(nd + os.sep) or nd.startswith(loc + os.sep) for loc in locations):
                continue
            if any(r.startswith(nd + os.sep) for r in running):
                continue
            if _matches(e.name, tokens):
                continue
            newest = _newest_mtime(e.path)
            if newest > idle_limit:
                continue
            size, files = entry_size(e.path, cancel)
            items.append(Item(
                path=e.path, size=size,
                values=("Pasta", e.name, fmt_size(size), fmt_date(newest), e.path),
                raw=("pasta", e.name.lower(), size, newest, e.path.lower()),
                kind="dir", data={"files": files}))
    # chaves de registro órfãs em HKCU\Software
    progress("Procurando restos no registro (HKCU\\Software)…")
    try:
        sw = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software")
        for sub in _reg_subkeys(sw):
            n = _alnum(sub)
            if n in _WIN_REG_SKIP or n in _WIN_SKIP or _matches(sub, tokens):
                continue
            mt = _reg_key_mtime(winreg.HKEY_CURRENT_USER, "Software\\" + sub)
            if mt and mt > idle_limit:
                continue
            key = f"HKCU\\Software\\{sub}"
            items.append(Item(path=key, size=0,
                              values=("Registro", sub, "—", fmt_date(mt), key),
                              raw=("registro", sub.lower(), 0, mt, key.lower()),
                              kind="regkey", data={"view": "64"}))
    except OSError:
        pass
    # entradas de desinstalação quebradas
    for p in progs:
        if p["broken"]:
            items.append(Item(path=p["regkey"], size=0,
                              values=("Entrada de desinstalação quebrada", p["name"], "—", "—", p["regkey"]),
                              raw=("entrada", p["name"].lower(), 0, 0, p["regkey"].lower()),
                              kind="regkey", data={"view": p["view"]}))
    return items


_LINUX_SKIP = {
    "autostart", "systemd", "dconf", "pulse", "pipewire", "wireplumber", "fontconfig",
    "fonts", "icons", "themes", "applications", "mime", "menus", "desktopdirectories",
    "keyrings", "trash", "recentlyusedxbel", "gtk20", "gtk30", "gtk40", "gtk", "gnome",
    "gnomesession", "gnomeshell", "gnomesettingsdaemon", "nautilus", "kde", "kdeconnect",
    "plasma", "kwin", "xfce4", "lxsession", "lxqt", "cinnamon", "mate", "ibus", "fcitx",
    "evolution", "tracker", "tracker3", "gvfsmetadata", "gvfs", "dbus", "xorg", "x11",
    "session", "sessions", "userdirsdirs", "user", "dirs", "mimeapps", "environmentd",
    "flatpak", "snap", "containers", "nvim", "vim", "emacs", "git", "ssh", "gnupg",
    "pki", "local", "config", "cache", "share", "state", "bin", "lib", "include", "man",
    "doc", "locale", "sounds", "backgrounds", "wallpapers", "templates", "zsh", "bash",
    "fish", "npm", "pip", "cargo", "rustup", "go", "java", "python", "nodejs", "node",
    "qtproject", "trolltech", "kdeglobals", "baloo", "akonadi", "kactivitymanagerd",
    "goa10", "grilo", "gsconnect", "geoclue", "colord", "xdgdesktopportal", "vlc",
    "libreoffice", "evolutiondataserver", "folks", "telepathy", "zeitgeist", "gstreamer10",
    "rygel", "totem", "eog", "gedit", "orca", "speechdispatcher", "monitorsxml", "weston",
    "abrt", "fwupd", "packagekit", "ubuntuadvantage", "update-notifier", "updatenotifier",
    "vulkan", "mesa", "nvidia", "mesashadercache", "dotnet", "docker", "kube", "android",
    "mozilla", "chromium", "googlechrome", "code", "vscode", "jetbrains", "wine", "steam",
    "local", "var", "nv", "debconf", "limpaone", "launchpadlib", "sudoasadmin", "lesshst", "xsession",
}


def linux_leftovers(min_idle_days, cancel, progress) -> list[Item]:
    progress("Montando lista de programas instalados…")
    known: set[str] = set()
    if shutil.which("dpkg-query"):
        known |= {x.split(":")[0].lower() for x in run_quiet(["dpkg-query", "-W", "-f=${Package}\n"]).split()}
    elif shutil.which("rpm"):
        known |= {x.lower() for x in run_quiet(["rpm", "-qa", "--qf", "%{NAME}\n"]).split()}
    elif shutil.which("pacman"):
        known |= {x.lower() for x in run_quiet(["pacman", "-Qq"]).split()}
    if shutil.which("flatpak"):
        for app_id in run_quiet(["flatpak", "list", "--columns=application"]).split():
            known.add(app_id.lower())
            known.add(app_id.split(".")[-1].lower())
    if shutil.which("snap"):
        known |= {ln.split()[0].lower() for ln in run_quiet(["snap", "list"]).splitlines()[1:] if ln.split()}
    for d in os.environ.get("PATH", "").split(os.pathsep):
        try:
            known |= {x.lower() for x in os.listdir(d)}
        except OSError:
            pass
    for n in _linux_desktop_names():
        known.add(n)
        known.add(n.split(".")[-1])
    tokens = {_alnum(k) for k in known if len(_alnum(k)) >= 3}
    idle_limit = time.time() - min_idle_days * 86400
    h = home()
    parents = [("~/.config", os.path.join(h, ".config")),
               ("~/.local/share", os.path.join(h, ".local", "share")),
               ("~ (pastas ocultas)", h)]
    items = []
    for label, parent in parents:
        progress(f"Procurando restos em {label}…")
        try:
            entries = list(os.scandir(parent))
        except OSError:
            continue
        for e in entries:
            if cancel.is_set():
                return items
            try:
                if not e.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            if parent == h and not e.name.startswith("."):
                continue
            name = e.name.lstrip(".")
            n = _alnum(name)
            if not n or n in _LINUX_SKIP or is_protected(e.path):
                continue
            if n in tokens or any(len(t) >= 4 and (t == n or (len(n) >= 4 and (n in t or t in n)))
                                  for t in tokens):
                continue
            newest = _newest_mtime(e.path)
            if newest > idle_limit:
                continue
            size, files = entry_size(e.path, cancel)
            items.append(Item(path=e.path, size=size,
                              values=("Pasta", e.name, fmt_size(size), fmt_date(newest), e.path),
                              raw=("pasta", e.name.lower(), size, newest, e.path.lower()),
                              kind="dir", data={"files": files}))
    return items


def mac_leftovers(min_idle_days, cancel, progress) -> list[Item]:
    apps = set()
    for app in glob.glob("/Applications/*.app") + glob.glob("/System/Applications/*.app") + \
            glob.glob(os.path.expanduser("~/Applications/*.app")):
        apps |= _tokens(os.path.basename(app)[:-4])
        plist = os.path.join(app, "Contents", "Info.plist")
        try:
            import plistlib
            with open(plist, "rb") as f:
                bid = plistlib.load(f).get("CFBundleIdentifier", "")
            apps.add(_alnum(bid))
            apps |= _tokens(bid.split(".")[-1])
            if bid.count(".") >= 2:
                apps.add(_alnum(bid.split(".")[1]))
        except Exception:  # noqa: BLE001
            pass
    idle_limit = time.time() - min_idle_days * 86400
    lib = os.path.expanduser("~/Library")
    items = []
    for sub in ("Application Support", "Preferences", "Caches", "Containers", "Saved Application State", "Logs"):
        parent = os.path.join(lib, sub)
        progress(f"Procurando restos em ~/Library/{sub}…")
        try:
            entries = list(os.scandir(parent))
        except OSError:
            continue
        for e in entries:
            if cancel.is_set():
                return items
            name = e.name.replace(".plist", "").replace(".savedState", "")
            if name.lower().startswith(("com.apple.", "apple", ".")) or _matches(name, apps):
                continue
            newest = _newest_mtime(e.path)
            if newest > idle_limit:
                continue
            size, _ = entry_size(e.path, cancel)
            items.append(Item(path=e.path, size=size,
                              values=(sub, e.name, fmt_size(size), fmt_date(newest), e.path),
                              raw=(sub.lower(), e.name.lower(), size, newest, e.path.lower()),
                              kind="dir"))
    return items


def scan_leftovers(min_idle_days, cancel, progress) -> list[Item]:
    if IS_WIN:
        items = windows_leftovers(min_idle_days, cancel, progress)
    elif IS_MAC:
        items = mac_leftovers(min_idle_days, cancel, progress)
    else:
        items = linux_leftovers(min_idle_days, cancel, progress)
    items.sort(key=lambda i: i.size, reverse=True)
    progress(f"{len(items)} possíveis restos encontrados.")
    return items


def delete_reg_key(key: str, view: str) -> None:
    """Exporta um backup .reg e apaga a chave (Windows)."""
    backup_dir = os.path.join(app_data_dir(), "backup-registro")
    os.makedirs(backup_dir, exist_ok=True)
    fname = re.sub(r"[^A-Za-z0-9_.-]+", "_", key)[-120:] + time.strftime("_%Y%m%d%H%M%S") + ".reg"
    backup = os.path.join(backup_dir, fname)
    flag = [f"/reg:{view}"] if view in ("32", "64") else []
    r = subprocess.run(["reg", "export", key, backup, "/y"] + flag, capture_output=True,
                       text=True, creationflags=NO_WINDOW, errors="replace")
    if r.returncode != 0:
        raise OSError("falha ao criar backup do registro: " + (r.stderr or r.stdout).strip())
    r = subprocess.run(["reg", "delete", key, "/f"] + flag, capture_output=True,
                       text=True, creationflags=NO_WINDOW, errors="replace")
    if r.returncode != 0:
        raise OSError((r.stderr or r.stdout).strip() or "acesso negado (tente como administrador)")
    log(f"REGISTRO APAGADO {key} (backup: {backup})")


# =================================================================== PROCESSOS / RAM
_CRITICAL_PROCS = {"system", "idle", "system idle process", "registry", "memory compression",
                   "secure system", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
                   "services.exe", "lsass.exe", "lsaiso.exe", "svchost.exe", "dwm.exe",
                   "fontdrvhost.exe", "sihost.exe", "ctfmon.exe", "explorer.exe",
                   "systemd", "init", "kthreadd", "xorg", "xwayland", "gnome-shell", "kwin_x11",
                   "kwin_wayland", "plasmashell", "dbus-daemon", "pipewire", "pulseaudio",
                   "kernel_task", "launchd", "windowserver", "loginwindow"}


def list_processes() -> list[dict]:
    me = os.getpid()
    out = []
    if psutil:
        for p in psutil.process_iter(["pid", "name", "memory_info", "exe", "username"]):
            try:
                mi = p.info.get("memory_info")
                out.append({"pid": p.info["pid"], "name": p.info.get("name") or "?",
                            "mem": mi.rss if mi else 0, "exe": p.info.get("exe") or "",
                            "user": p.info.get("username") or ""})
            except Exception:  # noqa: BLE001
                pass
    elif IS_WIN:
        txt = run_quiet(["tasklist", "/fo", "csv", "/nh"])
        import csv
        import io
        for row in csv.reader(io.StringIO(txt)):
            if len(row) >= 5:
                try:
                    mem = int(re.sub(r"\D", "", row[4]) or 0) * 1024
                    out.append({"pid": int(row[1]), "name": row[0], "mem": mem, "exe": "", "user": ""})
                except ValueError:
                    pass
    else:
        page = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
        for d in glob.glob("/proc/[0-9]*"):
            try:
                pid = int(os.path.basename(d))
                with open(os.path.join(d, "statm")) as f:
                    rss = int(f.read().split()[1]) * page
                with open(os.path.join(d, "comm")) as f:
                    name = f.read().strip()
                try:
                    exe = os.readlink(os.path.join(d, "exe"))
                except OSError:
                    exe = ""
                out.append({"pid": pid, "name": name, "mem": rss, "exe": exe, "user": ""})
            except (OSError, ValueError, IndexError):
                pass
    return [p for p in out if p["pid"] not in (0, me) and p["mem"] > 0]


def scan_processes(group_by_name, cancel, progress) -> list[Item]:
    progress("Lendo processos…")
    procs = list_processes()
    items = []
    if group_by_name:
        groups: dict[str, list] = {}
        for p in procs:
            groups.setdefault(p["name"].lower(), []).append(p)
        for name, ps in groups.items():
            mem = sum(p["mem"] for p in ps)
            exe = next((p["exe"] for p in ps if p["exe"]), "")
            crit = name in _CRITICAL_PROCS
            items.append(Item(path=name, size=mem,
                              values=(ps[0]["name"], str(len(ps)), fmt_size(mem),
                                      "Sistema (protegido)" if crit else "", exe),
                              raw=(name, len(ps), mem, crit, exe.lower()), kind="process",
                              data={"pids": [p["pid"] for p in ps], "critical": crit, "exe": exe}))
    else:
        for p in procs:
            crit = p["name"].lower() in _CRITICAL_PROCS
            items.append(Item(path=str(p["pid"]), size=p["mem"],
                              values=(p["name"], str(p["pid"]), fmt_size(p["mem"]),
                                      "Sistema (protegido)" if crit else "", p["exe"]),
                              raw=(p["name"].lower(), p["pid"], p["mem"], crit, p["exe"].lower()),
                              kind="process", data={"pids": [p["pid"]], "critical": crit, "exe": p["exe"]}))
    items.sort(key=lambda i: i.size, reverse=True)
    total, used = memory_info()
    progress(f"{len(procs)} processos — RAM em uso: {fmt_size(used)} de {fmt_size(total)}")
    return items


def kill_pid(pid: int) -> None:
    if psutil:
        p = psutil.Process(pid)
        p.terminate()
        try:
            p.wait(3)
        except psutil.TimeoutExpired:
            p.kill()
        return
    if IS_WIN:
        r = subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, text=True,
                           creationflags=NO_WINDOW, errors="replace")
        if r.returncode != 0:
            raise OSError((r.stderr or r.stdout).strip())
    else:
        os.kill(pid, signal.SIGTERM)


def trim_memory() -> int:
    """Pede ao Windows para devolver memória ociosa dos processos (EmptyWorkingSet)."""
    if not IS_WIN:
        return 0
    from ctypes import wintypes
    psapi = ctypes.WinDLL("psapi")
    k32 = ctypes.WinDLL("kernel32")
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
    arr = (wintypes.DWORD * 8192)()
    needed = wintypes.DWORD()
    if not psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(needed)):
        return 0
    count = 0
    for i in range(needed.value // ctypes.sizeof(wintypes.DWORD)):
        h = k32.OpenProcess(0x0400 | 0x0100, False, arr[i])  # QUERY_INFORMATION | SET_QUOTA
        if h:
            if psapi.EmptyWorkingSet(h):
                count += 1
            k32.CloseHandle(h)
    return count


# =================================================================== INICIALIZAÇÃO
_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"


def _approved_enabled(hive, sub, name) -> bool:
    try:
        k = winreg.OpenKey(hive, f"{_APPROVED}\\{sub}", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        data, _ = winreg.QueryValueEx(k, name)
        return not (isinstance(data, bytes) and data and data[0] & 1)
    except OSError:
        return True


def scan_startup(cancel, progress) -> list[Item]:
    progress("Lendo programas que iniciam com o sistema…")
    items = []

    def add(name, cmd, where, enabled, data):
        items.append(Item(path=f"{where}|{name}", size=0,
                          values=(name, "Ativado" if enabled else "Desativado", where, cmd),
                          raw=(name.lower(), enabled, where, cmd.lower()),
                          kind="startup", data={"name": name, "enabled": enabled, **data}))

    if IS_WIN:
        sources = [(winreg.HKEY_CURRENT_USER, "HKCU", 0, "Run", "Registro (usuário)"),
                   (winreg.HKEY_LOCAL_MACHINE, "HKLM", winreg.KEY_WOW64_64KEY, "Run", "Registro (todos os usuários)"),
                   (winreg.HKEY_LOCAL_MACHINE, "HKLM", winreg.KEY_WOW64_32KEY, "Run32", "Registro (todos, 32 bits)")]
        for hive, hname, flag, sub, where in sources:
            try:
                k = winreg.OpenKey(hive, _RUN, 0, winreg.KEY_READ | flag)
            except OSError:
                continue
            for name, cmd in _reg_values(k).items():
                if not name:
                    continue
                add(name, str(cmd), where, _approved_enabled(hive, sub, name),
                    {"hive": hname, "sub": sub})
        folders = [(os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"),
                    "HKCU", "Pasta Inicializar (usuário)"),
                   (os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs\StartUp"),
                    "HKLM", "Pasta Inicializar (todos)")]
        for folder, hname, where in folders:
            for f in glob.glob(os.path.join(folder, "*")):
                name = os.path.basename(f)
                if name.lower() == "desktop.ini":
                    continue
                hive = winreg.HKEY_CURRENT_USER if hname == "HKCU" else winreg.HKEY_LOCAL_MACHINE
                add(name, f, where, _approved_enabled(hive, "StartupFolder", name),
                    {"hive": hname, "sub": "StartupFolder", "file": f})
    elif IS_LINUX:
        user_dir = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(home(), ".config"), "autostart")
        entries: dict[str, tuple[str, str]] = {}
        for d, where in (("/etc/xdg/autostart", "Sistema"), (user_dir, "Usuário")):
            for f in glob.glob(os.path.join(d, "*.desktop")):
                entries[os.path.basename(f)] = (f, where)
        for base, (f, where) in sorted(entries.items()):
            info = _read_desktop(f)
            if info.get("onlyshowin") and os.environ.get("XDG_CURRENT_DESKTOP", "").lower() not in info["onlyshowin"].lower():
                continue
            enabled = info.get("hidden", "false").lower() != "true" and \
                info.get("x-gnome-autostart-enabled", "true").lower() != "false"
            add(info.get("name", base), info.get("exec", ""), where, enabled,
                {"file": f, "base": base, "user_dir": user_dir})
    elif IS_MAC:
        for d in (os.path.expanduser("~/Library/LaunchAgents"), "/Library/LaunchAgents"):
            for f in glob.glob(os.path.join(d, "*.plist")):
                add(os.path.basename(f)[:-6], f, d, True, {"file": f})
    progress(f"{len(items)} itens de inicialização.")
    return items


def _read_desktop(path) -> dict:
    out = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            in_entry = False
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    in_entry = line == "[Desktop Entry]"
                    continue
                if in_entry and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip().lower()
                    if k not in out:
                        out[k] = v.strip()
    except OSError:
        pass
    return out


def set_startup_enabled(item: Item, enabled: bool) -> None:
    d = item.data
    if IS_WIN:
        hive = winreg.HKEY_CURRENT_USER if d["hive"] == "HKCU" else winreg.HKEY_LOCAL_MACHINE
        k = winreg.CreateKeyEx(hive, f"{_APPROVED}\\{d['sub']}", 0,
                               winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY)
        if enabled:
            data = bytes([2]) + bytes(11)
        else:
            ft = int((time.time() + 11644473600) * 10_000_000)
            data = bytes([3, 0, 0, 0]) + struct.pack("<Q", ft)
        winreg.SetValueEx(k, d["name"], 0, winreg.REG_BINARY, data)
    elif IS_LINUX:
        os.makedirs(d["user_dir"], exist_ok=True)
        target = os.path.join(d["user_dir"], d["base"])
        if not os.path.exists(target):
            shutil.copy2(d["file"], target)
        with open(target, encoding="utf-8", errors="replace") as f:
            lines = [ln for ln in f.read().splitlines()
                     if not ln.lower().startswith(("hidden=", "x-gnome-autostart-enabled="))]
        out, inserted = [], False
        for ln in lines:
            out.append(ln)
            if ln.strip() == "[Desktop Entry]" and not inserted:
                out.append("Hidden=false" if enabled else "Hidden=true")
                out.append("X-GNOME-Autostart-enabled=" + ("true" if enabled else "false"))
                inserted = True
        with open(target, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
    elif IS_MAC:
        action = "load" if enabled else "unload"
        subprocess.run(["launchctl", action, "-w", d["file"]], capture_output=True)
    log(f"INICIALIZAÇÃO {'ATIVADA' if enabled else 'DESATIVADA'}: {d['name']}")


# =================================================================== LIXEIRA
def _linux_trash_dirs() -> list[str]:
    dirs = [os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.join(home(), ".local", "share"), "Trash")]
    uid = os.getuid() if hasattr(os, "getuid") else 0
    try:
        with open("/proc/mounts", encoding="utf-8") as f:
            for line in f:
                mp = line.split()[1].replace("\\040", " ")
                for cand in (os.path.join(mp, ".Trash", str(uid)), os.path.join(mp, f".Trash-{uid}")):
                    if os.path.isdir(cand):
                        dirs.append(cand)
    except OSError:
        pass
    return dirs


def _win_rb_struct():
    class SHQUERYRBINFO(ctypes.Structure):
        if ctypes.sizeof(ctypes.c_void_p) == 4:
            _pack_ = 1
        _fields_ = [("cbSize", ctypes.c_uint32), ("i64Size", ctypes.c_int64), ("i64NumItems", ctypes.c_int64)]
    return SHQUERYRBINFO


def recycle_bin_info() -> tuple[int, int]:
    """(tamanho em bytes, número de itens) na Lixeira."""
    if IS_WIN:
        S = _win_rb_struct()
        info = S()
        info.cbSize = ctypes.sizeof(S)
        if ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info)) == 0:
            return int(info.i64Size), int(info.i64NumItems)
        return 0, 0
    if IS_MAC:
        t = os.path.expanduser("~/.Trash")
        try:
            return entry_size(t)[0], len(os.listdir(t))
        except OSError:
            return 0, 0
    size = count = 0
    for d in _linux_trash_dirs():
        files = os.path.join(d, "files")
        try:
            count += len(os.listdir(files))
            size += entry_size(files)[0]
        except OSError:
            pass
    return size, count


def empty_recycle_bin() -> None:
    if IS_WIN:
        rc = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 1 | 2 | 4)
        if rc not in (0, -2147418113):  # S_OK ou E_UNEXPECTED (lixeira já vazia)
            raise OSError(f"falha ao esvaziar a Lixeira (código {rc & 0xFFFFFFFF:#x})")
    elif IS_MAC:
        t = os.path.expanduser("~/.Trash")
        for e in os.listdir(t):
            p = os.path.join(t, e)
            shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) and not os.path.islink(p) else os.remove(p)
    else:
        for d in _linux_trash_dirs():
            for sub in ("files", "info", "expunged"):
                p = os.path.join(d, sub)
                if not os.path.isdir(p):
                    continue
                for e in os.listdir(p):
                    q = os.path.join(p, e)
                    try:
                        if os.path.isdir(q) and not os.path.islink(q):
                            shutil.rmtree(q, ignore_errors=True)
                        else:
                            os.remove(q)
                    except OSError:
                        pass
            try:
                os.remove(os.path.join(d, "directorysizes"))
            except OSError:
                pass
    log("LIXEIRA ESVAZIADA")
