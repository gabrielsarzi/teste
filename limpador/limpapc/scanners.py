"""Varreduras de arquivos: grandes, duplicados, antigos e lixo/temporários."""
from __future__ import annotations

import glob
import hashlib
import heapq
import os
import time

from .utils import (IS_LINUX, IS_MAC, IS_WIN, Item, _is_junction, entry_size, fmt_date,
                    fmt_days, fmt_size, home, is_protected, norm)

# Pastas que nunca são percorridas (sistema / pseudo-sistemas de arquivos).
_ALWAYS_SKIP_NAMES = {"$recycle.bin", "system volume information", "config.msi", "recovery",
                      "$windows.~bt", "$windows.~ws", "$winreagent", "windowsapps"}
_ALWAYS_SKIP_PATHS = set()
if IS_WIN:
    _ALWAYS_SKIP_PATHS.add(norm(os.environ.get("WINDIR", r"C:\Windows")))
else:
    for _p in ("/proc", "/sys", "/dev", "/run", "/snap", "/var/lib/docker", "/var/lib/flatpak",
               "/System", "/private/var/vm", "/Volumes/Recovery"):
        _ALWAYS_SKIP_PATHS.add(norm(_p))

# Pastas de programas/configuração: ignoradas em "duplicados" e "antigos" (opcional),
# pois arquivos repetidos ou "esquecidos" ali são normais e apagá-los quebra programas.
APP_DIR_NAMES = {"appdata", "programdata", "program files", "program files (x86)", ".config",
                 ".local", ".cache", ".var", "library", ".git", ".svn", "node_modules",
                 "site-packages", "dist-packages", "__pycache__", ".npm", ".gradle", ".m2",
                 ".cargo", ".rustup", ".nuget", "steamapps", ".steam", ".vscode", ".mozilla",
                 "venv", ".venv", "anaconda3", "miniconda3", ".wine", "snap", "flatpak"}


def walk_files(roots, cancel, progress=None, skip_names=frozenset(), skip_hidden=False):
    """Percorre as pastas gerando (caminho, stat) de cada arquivo comum."""
    stack = [r for r in roots if os.path.isdir(r)]
    seen_dirs = set()
    count = 0
    last = 0.0
    while stack:
        if cancel.is_set():
            return
        d = stack.pop()
        nd = norm(d)
        if nd in seen_dirs or nd in _ALWAYS_SKIP_PATHS:
            continue
        seen_dirs.add(nd)
        try:
            it = os.scandir(d)
        except OSError:
            continue
        with it:
            for e in it:
                try:
                    if e.is_symlink() or _is_junction(e):
                        continue
                    if e.is_dir(follow_symlinks=False):
                        low = e.name.lower()
                        if low in _ALWAYS_SKIP_NAMES or low in skip_names:
                            continue
                        if skip_hidden and e.name.startswith("."):
                            continue
                        stack.append(e.path)
                    elif e.is_file(follow_symlinks=False):
                        st = e.stat(follow_symlinks=False)
                        count += 1
                        if progress and time.monotonic() - last > 0.25:
                            last = time.monotonic()
                            progress(f"{count:,} arquivos verificados… {d}".replace(",", "."))
                        yield e.path, st
                except OSError:
                    continue
    if progress:
        progress(f"{count:,} arquivos verificados.".replace(",", "."))


def _file_item(path, st, extra_cols=(), extra_raw=(), checked=False) -> Item:
    name = os.path.basename(path)
    folder = os.path.dirname(path)
    last_use = max(st.st_atime, st.st_mtime)
    return Item(path=path, size=st.st_size,
                values=(name, fmt_size(st.st_size), fmt_date(st.st_mtime), fmt_days(last_use),
                        *extra_cols, folder),
                raw=(name.lower(), st.st_size, st.st_mtime, last_use, *extra_raw, folder.lower()),
                kind="file", checked=checked,
                data={"mtime": st.st_mtime, "last_use": last_use})


# ---------------------------------------------------------------- arquivos grandes
def scan_large(roots, min_bytes, cancel, progress, limit=3000):
    heap: list = []
    i = 0
    for path, st in walk_files(roots, cancel, progress):
        if st.st_size >= min_bytes and not is_protected(path):
            i += 1
            item = (st.st_size, i, path, st)
            if len(heap) < limit:
                heapq.heappush(heap, item)
            else:
                heapq.heappushpop(heap, item)
    heap.sort(reverse=True)
    return [_file_item(p, st) for _, _, p, st in heap]


# ---------------------------------------------------------------- arquivos antigos
def scan_old(roots, days, min_bytes, skip_app_dirs, cancel, progress, limit=5000):
    cutoff = time.time() - days * 86400
    skip = APP_DIR_NAMES if skip_app_dirs else frozenset()
    found = []
    for path, st in walk_files(roots, cancel, progress, skip_names=skip, skip_hidden=skip_app_dirs):
        if st.st_size < min_bytes:
            continue
        last_use = max(st.st_atime, st.st_mtime)
        if last_use < cutoff and not is_protected(path):
            found.append((st.st_size, path, st))
    found.sort(reverse=True)
    return [_file_item(p, st) for _, p, st in found[:limit]]


# ---------------------------------------------------------------- duplicados
def _hash(path, cancel, partial=False, block=1 << 20):
    h = hashlib.blake2b(digest_size=20)
    with open(path, "rb") as f:
        if partial:
            h.update(f.read(64 * 1024))
            try:
                f.seek(-64 * 1024, os.SEEK_END)
                h.update(f.read(64 * 1024))
            except OSError:
                pass
            return h.hexdigest()
        while True:
            if cancel.is_set():
                raise InterruptedError
            chunk = f.read(block)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def scan_duplicates(roots, min_bytes, skip_app_dirs, keep, cancel, progress):
    """Encontra arquivos idênticos: tamanho -> hash parcial -> hash completo.

    keep: "antigo" | "recente" | "curto" — qual cópia de cada grupo fica DESMARCADA.
    """
    skip = APP_DIR_NAMES if skip_app_dirs else frozenset()
    by_size: dict[int, list] = {}
    inodes = set()
    for path, st in walk_files(roots, cancel, progress, skip_names=skip, skip_hidden=skip_app_dirs):
        if st.st_size < min_bytes:
            continue
        key = (st.st_dev, st.st_ino)
        if st.st_ino and key in inodes:  # hardlink: mesmo arquivo físico
            continue
        inodes.add(key)
        by_size.setdefault(st.st_size, []).append((path, st))
    candidates = [v for v in by_size.values() if len(v) > 1]
    total = sum(len(v) for v in candidates)
    done = 0
    groups = []
    for files in candidates:
        if cancel.is_set():
            break
        by_partial: dict[str, list] = {}
        for path, st in files:
            done += 1
            if done % 20 == 0:
                progress(f"Comparando conteúdo… {done}/{total} arquivos")
            try:
                by_partial.setdefault(_hash(path, cancel, partial=True), []).append((path, st))
            except (OSError, InterruptedError):
                pass
        for same in by_partial.values():
            if len(same) < 2:
                continue
            if same[0][1].st_size <= 128 * 1024:   # hash parcial já cobriu o arquivo inteiro
                groups.append(same)
                continue
            by_full: dict[str, list] = {}
            for path, st in same:
                try:
                    progress(f"Comparando conteúdo… {done}/{total} — {os.path.basename(path)}")
                    by_full.setdefault(_hash(path, cancel), []).append((path, st))
                except InterruptedError:
                    return []
                except OSError:
                    pass
            groups.extend(g for g in by_full.values() if len(g) > 1)
    groups.sort(key=lambda g: g[0][1].st_size * (len(g) - 1), reverse=True)

    items = []
    for gi, g in enumerate(groups, 1):
        if keep == "recente":
            original = max(g, key=lambda x: x[1].st_mtime)
        elif keep == "curto":
            original = min(g, key=lambda x: (len(x[0]), x[0]))
        else:
            original = min(g, key=lambda x: x[1].st_mtime)
        for path, st in g:
            it = _file_item(path, st, checked=(path != original[0]) and not is_protected(path))
            it.group = gi
            items.append(it)
    progress(f"{len(groups)} grupos de arquivos repetidos encontrados.")
    return items


# ---------------------------------------------------------------- lixo / temporários
def junk_locations():
    """Lista de (descrição, pasta, padrões|None, idade mínima em horas, só do usuário)."""
    h = home()
    locs = []
    if IS_WIN:
        env = os.environ.get
        windir = env("WINDIR", r"C:\Windows")
        local = env("LOCALAPPDATA", os.path.join(h, "AppData", "Local"))
        roaming = env("APPDATA", os.path.join(h, "AppData", "Roaming"))
        progdata = env("PROGRAMDATA", r"C:\ProgramData")
        temp = env("TEMP", os.path.join(local, "Temp"))
        locs += [
            ("Arquivos temporários do usuário", temp, None, 2, False),
            ("Arquivos temporários do Windows", os.path.join(windir, "Temp"), None, 2, False),
            ("Cache do Windows Update", os.path.join(windir, "SoftwareDistribution", "Download"), None, 0, False),
            ("Relatórios de erro do Windows", os.path.join(progdata, "Microsoft", "Windows", "WER", "ReportArchive"), None, 0, False),
            ("Relatórios de erro (fila)", os.path.join(progdata, "Microsoft", "Windows", "WER", "ReportQueue"), None, 0, False),
            ("Relatórios de erro do usuário", os.path.join(local, "Microsoft", "Windows", "WER"), None, 0, False),
            ("Despejos de memória (crash dumps)", os.path.join(local, "CrashDumps"), None, 0, False),
            ("Minidumps do sistema", os.path.join(windir, "Minidump"), None, 0, False),
            ("Logs de manutenção (CBS)", os.path.join(windir, "Logs", "CBS"), ["*.log", "*.cab"], 24, False),
            ("Cache de miniaturas (thumbnails)", os.path.join(local, "Microsoft", "Windows", "Explorer"), ["thumbcache_*.db", "iconcache_*.db"], 0, False),
            ("Cache da internet (IE/Edge legado)", os.path.join(local, "Microsoft", "Windows", "INetCache"), None, 0, False),
            ("Cache do DirectX (shaders)", os.path.join(local, "D3DSCache"), None, 0, False),
            ("Cache de shaders NVIDIA", os.path.join(local, "NVIDIA", "DXCache"), None, 0, False),
            ("Cache de shaders NVIDIA (GL)", os.path.join(local, "NVIDIA", "GLCache"), None, 0, False),
            ("Cache de shaders AMD", os.path.join(local, "AMD", "DxCache"), None, 0, False),
            ("Cache do npm", os.path.join(local, "npm-cache"), None, 0, False),
            ("Cache do pip", os.path.join(local, "pip", "cache"), None, 0, False),
            ("Cache do Teams", os.path.join(roaming, "Microsoft", "Teams", "Cache"), None, 0, False),
            ("Cache do Discord", os.path.join(roaming, "discord", "Cache"), None, 0, False),
            ("Cache do Spotify", os.path.join(local, "Spotify", "Data"), None, 0, False),
            ("Instaladores baixados (Downloaded Program Files)", os.path.join(windir, "Downloaded Program Files"), None, 0, False),
        ]
        browsers = [("Chrome", os.path.join(local, "Google", "Chrome", "User Data")),
                    ("Edge", os.path.join(local, "Microsoft", "Edge", "User Data")),
                    ("Brave", os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data")),
                    ("Opera", os.path.join(roaming, "Opera Software", "Opera Stable")),
                    ("Opera GX", os.path.join(roaming, "Opera Software", "Opera GX Stable")),
                    ("Vivaldi", os.path.join(local, "Vivaldi", "User Data"))]
        for bname, base in browsers:
            for sub in ("Cache", "Code Cache", "GPUCache"):
                for m in sorted(glob.glob(os.path.join(base, "*", sub)) + [os.path.join(base, sub)]):
                    if not os.path.isdir(m):
                        continue
                    parent = os.path.dirname(m)
                    prof = "" if norm(parent) == norm(base) else os.path.basename(parent)
                    label = f"Cache do {bname} ({sub})"
                    if prof and prof.lower() != "default":
                        label += f" — perfil {prof}"
                    locs.append((label, m, None, 0, False))
        for prof in glob.glob(os.path.join(local, "Mozilla", "Firefox", "Profiles", "*", "cache2")):
            locs.append((f"Cache do Firefox — {os.path.basename(os.path.dirname(prof))}", prof, None, 0, False))
        winold = os.path.join(os.environ.get("SystemDrive", "C:") + "\\", "Windows.old")
        if os.path.isdir(winold):
            locs.append(("Instalação anterior do Windows (Windows.old)", winold, None, 0, False))
    elif IS_MAC:
        locs += [
            ("Caches de aplicativos", os.path.join(h, "Library", "Caches"), None, 0, False),
            ("Logs de aplicativos", os.path.join(h, "Library", "Logs"), None, 0, False),
            ("Relatórios de falha", os.path.join(h, "Library", "Logs", "DiagnosticReports"), None, 0, False),
            ("Dados derivados do Xcode", os.path.join(h, "Library", "Developer", "Xcode", "DerivedData"), None, 0, False),
            ("Temporários", os.environ.get("TMPDIR", "/tmp"), None, 24, True),
        ]
    else:
        cache = os.environ.get("XDG_CACHE_HOME") or os.path.join(h, ".cache")
        locs += [
            ("Cache de miniaturas", os.path.join(cache, "thumbnails"), None, 0, False),
            ("Miniaturas antigas (~/.thumbnails)", os.path.join(h, ".thumbnails"), None, 0, False),
            ("Temporários do sistema (/tmp) — seus arquivos", "/tmp", None, 24, True),
            ("Temporários persistentes (/var/tmp) — seus arquivos", "/var/tmp", None, 24, True),
            ("Pacotes baixados do APT (precisa de root)", "/var/cache/apt/archives", ["*.deb"], 0, False),
            ("Pacotes baixados do DNF (precisa de root)", "/var/cache/dnf", None, 0, False),
            ("Pacotes baixados do Pacman (precisa de root)", "/var/cache/pacman/pkg", None, 0, False),
            ("Logs antigos compactados (precisa de root)", "/var/log", ["*.gz", "*.old", "*.[0-9]"], 0, False),
            ("Relatórios de falha", "/var/crash", None, 0, False),
        ]
        # cada subpasta de ~/.cache vira uma linha (exceto miniaturas, já listada)
        try:
            for e in sorted(os.scandir(cache), key=lambda x: x.name.lower()):
                if e.is_dir(follow_symlinks=False) and e.name != "thumbnails":
                    locs.append((f"Cache: {e.name}", e.path, None, 0, False))
        except OSError:
            pass
        # Flatpak guarda o cache de cada app em ~/.var/app/<id>/cache
        for c in glob.glob(os.path.join(h, ".var", "app", "*", "cache")):
            locs.append((f"Cache Flatpak: {os.path.basename(os.path.dirname(c))}", c, None, 0, False))
    return locs


def _sized_contents(path, patterns, min_age_hours, only_mine, cancel):
    import fnmatch
    limit = time.time() - min_age_hours * 3600
    uid = os.getuid() if (only_mine and hasattr(os, "getuid")) else None
    total = files = 0
    try:
        entries = list(os.scandir(path))
    except OSError:
        return 0, 0
    for e in entries:
        if cancel.is_set():
            break
        try:
            if patterns and not any(fnmatch.fnmatch(e.name.lower(), p) for p in patterns):
                continue
            st = e.stat(follow_symlinks=False)
            if min_age_hours and st.st_mtime > limit:
                continue
            if uid is not None and st.st_uid != uid:
                continue
            s, n = entry_size(e.path, cancel)
            total += s
            files += n
        except OSError:
            pass
    return total, files


def scan_junk(cancel, progress, include_recycle=True):
    from .system import recycle_bin_info
    items = []
    for label, path, patterns, age, only_mine in junk_locations():
        if cancel.is_set():
            break
        if not os.path.isdir(path):
            continue
        progress(f"Verificando: {label}")
        size, files = _sized_contents(path, patterns, age, only_mine, cancel)
        if size <= 0 and files == 0:
            continue
        items.append(Item(path=path, size=size,
                          values=(label, fmt_size(size), f"{files:,}".replace(",", "."), path),
                          raw=(label.lower(), size, files, path.lower()),
                          kind="dircontents", checked=True,
                          data={"patterns": patterns, "age": age, "only_mine": only_mine}))
    if include_recycle:
        size, count = recycle_bin_info()
        if size or count:
            items.append(Item(path="::lixeira::", size=size,
                              values=("Lixeira", fmt_size(size), f"{count:,}".replace(",", "."), "Lixeira do sistema"),
                              raw=("lixeira", size, count, ""), kind="recyclebin", checked=False))
    items.sort(key=lambda i: i.size, reverse=True)
    progress(f"{len(items)} locais com lixo encontrados.")
    return items


__all__ = ["scan_large", "scan_old", "scan_duplicates", "scan_junk", "junk_locations",
           "walk_files", "IS_LINUX"]
