"""Limpeza do registro: encontra só entradas COMPROVADAMENTE inválidas (apontam para arquivos que
não existem mais) e as corrige com backup .reg completo antes de qualquer alteração.

Categorias (todas conservadoras):
  • DLLs compartilhadas inexistentes (SharedDLLs)
  • Caminhos de aplicativos (App Paths) apontando para .exe inexistente
  • Cache de nomes de programas (MuiCache) de programas que não existem mais
  • Itens de inicialização (Run) apontando para arquivo inexistente
  • Associações "Abrir com" (HKCU\\Software\\Classes\\Applications) de programas removidos
  • Entradas de desinstalação cujo desinstalador e pasta não existem mais

Regra de ouro: na dúvida, NÃO marca. Caminhos relativos, de rede, com variáveis não resolvidas ou em
unidades que não estão conectadas nunca são considerados inválidos.

A lógica de leitura usa um "leitor" abstrato (WinRegReader no Windows) para que a análise possa ser
testada em qualquer sistema com um leitor falso.
"""
from __future__ import annotations

import ntpath
import os
import re
import subprocess
import time

from .utils import IS_WIN, NO_WINDOW, Item, app_data_dir, log

if IS_WIN:
    import winreg  # type: ignore

HIVES = {"HKLM": "HKEY_LOCAL_MACHINE", "HKCU": "HKEY_CURRENT_USER"}

CATEGORIES = [
    ("dll", "DLLs compartilhadas"),
    ("apppaths", "Caminhos de aplicativos"),
    ("muicache", "Cache de nomes"),
    ("run", "Inicialização"),
    ("assoc", "Abrir com"),
    ("uninstall", "Desinstalação"),
]
CAT_LABEL = dict(CATEGORIES)

_CV = r"SOFTWARE\Microsoft\Windows\CurrentVersion"
SHARED_DLLS = _CV + r"\SharedDLLs"
APP_PATHS = _CV + r"\App Paths"
RUN = _CV + r"\Run"
UNINSTALL = _CV + r"\Uninstall"
MUICACHE = r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
APPLICATIONS = r"Software\Classes\Applications"

# extensões que encerram o "programa" numa linha de comando sem aspas
_EXTS = ("exe", "com", "bat", "cmd", "scr", "cpl", "msc", "dll", "ocx", "sys", "drv", "ax", "lnk",
         "vbs", "vbe", "js", "jse", "wsf", "ps1", "msi", "tlb", "olb", "mui", "ico")
_EXT_RE = re.compile(r"\.(?:%s)(?=$|[\s,;\"'])" % "|".join(_EXTS), re.I)
_DRIVE_ABS = re.compile(r"^[A-Za-z]:\\")
_BAD_CHARS = set('*?<>|"')


# =================================================================== análise de caminhos
def expand_env(s: str) -> str:
    """Expande %VARIAVEIS% no estilo Windows (funciona em qualquer sistema)."""
    return ntpath.expandvars(s or "")


def _clean(p: str) -> str:
    p = (p or "").strip().strip('"').strip()
    if p.startswith("\\??\\"):
        p = p[4:]
    low = p.lower()
    if low.startswith("\\systemroot\\"):
        p = (os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows") + p[11:]
    return p.replace("/", "\\")


def command_candidates(cmd: str) -> list[str]:
    """Caminhos possíveis do programa/arquivo de uma linha de comando ou referência do registro.

    Trata: aspas, argumentos, %VARIAVEIS%, prefixo "@" de recursos ("@C:\\x.dll,-101"),
    índices de ícone (",0"), "\\??\\" e caminhos com espaços sem aspas (devolve todas as
    interpretações possíveis, da mais curta à mais longa)."""
    s = (cmd or "").strip()
    if not s:
        return []
    if s.startswith("@"):
        s = s[1:].strip()
    s = expand_env(s)
    if s.startswith('"'):
        end = s.find('"', 1)
        path = s[1:end] if end > 0 else s[1:]
        return [_clean(path)] if path.strip() else []
    out = []
    for m in _EXT_RE.finditer(s):
        out.append(_clean(s[:m.end()]))
    if not out:
        first = re.split(r"[\s,]", s, maxsplit=1)[0]
        out.append(_clean(first))
        # "C:\Program Files\App\app -arg" sem extensão: tenta também a linha até o primeiro " -" ou " /"
        m = re.search(r"\s[-/]", s)
        whole = _clean(s[:m.start()] if m else s)
        if whole != out[0]:
            out.append(whole)
    seen, res = set(), []
    for p in out:
        if p and p.lower() not in seen:
            seen.add(p.lower())
            res.append(p)
    return res


def command_target(cmd: str) -> str:
    """O caminho mais provável (para exibir)."""
    c = command_candidates(cmd)
    return c[0] if c else ""


def _default_exists(p: str) -> bool:
    return os.path.exists(p)


def path_state(path: str, exists=_default_exists) -> str:
    """'ok' (existe), 'missing' (comprovadamente não existe) ou 'unknown' (não dá para afirmar)."""
    p = _clean(path)
    if not p or not _DRIVE_ABS.match(p) or "%" in p or any(ch in _BAD_CHARS for ch in p):
        return "unknown"
    root = p[:3]
    if not exists(root):
        return "unknown"          # unidade desconectada (pendrive, HD externo, rede mapeada…)
    if exists(p):
        return "ok"
    low = p.lower()
    alts = []
    if not ntpath.splitext(p)[1]:
        alts.append(p + ".exe")          # CreateProcess completa ".exe"
    # redirecionamento de pastas do sistema para programas 32 bits
    for a, b in (("\\system32\\", "\\sysnative\\"), ("\\system32\\", "\\syswow64\\"),
                 ("\\syswow64\\", "\\system32\\")):
        i = low.find(a)
        if i >= 0:
            alts.append(p[:i] + b + p[i + len(a):])
    if any(exists(a) for a in alts):
        return "ok"
    if exists is _default_exists and not _ancestor_listable(p):
        return "unknown"          # sem permissão para olhar a pasta (ex.: perfil de outro usuário)
    return "missing"


def _ancestor_listable(p: str) -> bool:
    """A pasta existente mais próxima do caminho pode ser listada? (senão a ausência não é prova)"""
    d = os.path.dirname(p)
    while d and not os.path.isdir(d):
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    try:
        os.listdir(d)
        return True
    except OSError:
        return False


def command_state(cmd: str, exists=_default_exists) -> tuple[str, str]:
    """Estado de uma linha de comando: ('ok'|'missing'|'unknown', caminho exibido).

    Só é 'missing' quando TODAS as interpretações possíveis do caminho comprovadamente não existem."""
    cands = command_candidates(cmd)
    if not cands:
        return "unknown", ""
    states = [path_state(c, exists) for c in cands]
    if "ok" in states:
        # existe (inclusive hospedeiros como rundll32: não dá para afirmar nada dos argumentos)
        return "ok", cands[states.index("ok")]
    if all(s == "missing" for s in states):
        return "missing", cands[0]
    return "unknown", cands[0]


def mui_name_path(name: str) -> str | None:
    """Converte o nome de um valor do MuiCache no caminho do programa (ou None se não for um caminho)."""
    if not name or name.startswith("@") or name.lower() == "langid":
        return None
    base = name
    for suf in (".FriendlyAppName", ".ApplicationCompany"):
        if base.endswith(suf):
            base = base[: -len(suf)]
            break
    return base if _DRIVE_ABS.match(base) else None


# =================================================================== leitores de registro
class RegReader:
    """Interface mínima de leitura. Caminhos são relativos à colmeia ('HKLM'/'HKCU')."""
    is_64bit_os = True

    def subkeys(self, hive: str, path: str) -> list[str]:
        raise NotImplementedError

    def values(self, hive: str, path: str) -> dict:
        """nome -> (dado, tipo). {} se a chave não existe."""
        raise NotImplementedError

    def has_key(self, hive: str, path: str) -> bool:
        raise NotImplementedError


class WinRegReader(RegReader):
    def __init__(self):
        arch = os.environ.get("PROCESSOR_ARCHITECTURE", "").upper()
        self.is_64bit_os = arch.endswith("64") or "PROCESSOR_ARCHITEW6432" in os.environ

    @staticmethod
    def _open(hive, path):
        h = winreg.HKEY_LOCAL_MACHINE if hive == "HKLM" else winreg.HKEY_CURRENT_USER
        return winreg.OpenKey(h, path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)

    def subkeys(self, hive, path):
        try:
            k = self._open(hive, path)
        except OSError:
            return []
        out, i = [], 0
        with k:
            while True:
                try:
                    out.append(winreg.EnumKey(k, i))
                except OSError:
                    break
                i += 1
        return out

    def values(self, hive, path):
        try:
            k = self._open(hive, path)
        except OSError:
            return {}
        out, i = {}, 0
        with k:
            while True:
                try:
                    name, data, typ = winreg.EnumValue(k, i)
                except OSError:
                    break
                out[name] = (data, typ)
                i += 1
        return out

    def has_key(self, hive, path):
        try:
            self._open(hive, path).Close()
            return True
        except OSError:
            return False


class FakeReader(RegReader):
    """Leitor em memória para testes: {'HKLM\\caminho': {'valor': (dado, tipo)}}."""
    REG_SZ, REG_EXPAND_SZ = 1, 2

    def __init__(self, data: dict, is_64bit_os=True):
        self.data = {k.lower(): (k, v) for k, v in data.items()}
        self.is_64bit_os = is_64bit_os

    def subkeys(self, hive, path):
        pre = f"{hive}\\{path}\\".lower()
        out = []
        for low, (orig, _) in self.data.items():
            if low.startswith(pre):
                name = orig[len(pre):].split("\\")[0]
                if name not in out:
                    out.append(name)
        return out

    def values(self, hive, path):
        return dict(self.data.get(f"{hive}\\{path}".lower(), (None, {}))[1])

    def has_key(self, hive, path):
        return f"{hive}\\{path}".lower() in self.data or bool(self.subkeys(hive, path))


def _str(v) -> str:
    return v if isinstance(v, str) else ""


def _wow(path: str) -> str:
    """Caminho equivalente na visão 32 bits (SOFTWARE\\WOW6432Node\\…)."""
    return "SOFTWARE\\WOW6432Node\\" + path[len("SOFTWARE\\"):]


# =================================================================== varredura
def _make_item(cat, hive, key, value, entry, problem, target, extra=None) -> Item:
    full = f"{hive}\\{key}"
    shown = full + (f"  →  {value}" if value is not None else "")
    data = {"cat": cat, "hive": hive, "key": key, "value": value, "target": target}
    data.update(extra or {})
    return Item(path=shown, size=0, values=(CAT_LABEL[cat], entry, problem, shown),
                raw=(CAT_LABEL[cat], entry.lower(), problem, shown.lower()), kind="value" if value is not None
                else "key", checked=True, data=data)


def _lm_paths(reader: RegReader, path: str) -> list[str]:
    """Caminhos HKLM a analisar: o nativo e, em Windows 64 bits, o de 32 bits (se for separado)."""
    paths = [path]
    if reader.is_64bit_os and path.upper().startswith("SOFTWARE\\"):
        w = _wow(path)
        # chaves "compartilhadas" entre as visões aparecem iguais nos dois caminhos: analisa uma só vez
        if reader.has_key("HKLM", w) and (reader.values("HKLM", w) != reader.values("HKLM", path)
                                          or reader.subkeys("HKLM", w) != reader.subkeys("HKLM", path)):
            paths.append(w)
    return paths


def scan_registry(reader: RegReader, cats=None, cancel=None, progress=lambda s: None,
                  exists=_default_exists) -> list[Item]:
    cats = set(cats or CAT_LABEL)
    items: list[Item] = []
    stop = lambda: bool(cancel and cancel.is_set())  # noqa: E731

    if "dll" in cats and not stop():
        progress("Verificando DLLs compartilhadas…")
        for key in _lm_paths(reader, SHARED_DLLS):
            for name in reader.values("HKLM", key):
                if stop():
                    break
                if path_state(expand_env(name), exists) == "missing":
                    items.append(_make_item("dll", "HKLM", key, name, ntpath.basename(name),
                                            "Arquivo da DLL não existe mais", name))

    if "apppaths" in cats and not stop():
        progress("Verificando caminhos de aplicativos…")
        for hive, base in (("HKLM", APP_PATHS), ("HKCU", APP_PATHS)):
            for key in (_lm_paths(reader, base) if hive == "HKLM" else [base]):
                for sub in reader.subkeys(hive, key):
                    vals = reader.values(hive, f"{key}\\{sub}")
                    default = _str(vals.get("", (None,))[0])
                    if not default:
                        continue
                    st, target = command_state(default, exists)
                    if st == "missing":
                        items.append(_make_item("apppaths", hive, f"{key}\\{sub}", None, sub,
                                                "Programa não existe mais", target))

    if "muicache" in cats and not stop():
        progress("Verificando cache de nomes de programas…")
        for name, (data, _) in reader.values("HKCU", MUICACHE).items():
            p = mui_name_path(name)
            if p and path_state(p, exists) == "missing":
                label = _str(data) or ntpath.basename(p)
                items.append(_make_item("muicache", "HKCU", MUICACHE, name, label,
                                        "Programa não existe mais", p))

    if "run" in cats and not stop():
        progress("Verificando itens de inicialização…")
        for hive in ("HKCU", "HKLM"):
            keys = _lm_paths(reader, RUN) if hive == "HKLM" else ["Software\\Microsoft\\Windows\\CurrentVersion\\Run"]
            for key in keys:
                for name, (data, _) in reader.values(hive, key).items():
                    if not name:
                        continue
                    st, target = command_state(_str(data), exists)
                    if st == "missing":
                        items.append(_make_item("run", hive, key, name, name,
                                                "Abre um arquivo que não existe mais", target))

    if "assoc" in cats and not stop():
        progress("Verificando associações “Abrir com”…")
        for app in reader.subkeys("HKCU", APPLICATIONS):
            base = f"{APPLICATIONS}\\{app}\\shell"
            states, target = [], ""
            for verb in reader.subkeys("HKCU", base):
                cmd = _str(reader.values("HKCU", f"{base}\\{verb}\\command").get("", (None,))[0])
                if cmd:
                    st, tg = command_state(cmd, exists)
                    states.append(st)
                    target = target or tg
            if states and all(s == "missing" for s in states):
                items.append(_make_item("assoc", "HKCU", f"{APPLICATIONS}\\{app}", None, app,
                                        "Programa associado não existe mais", target))

    if "uninstall" in cats and not stop():
        progress("Verificando entradas de desinstalação…")
        for hive in ("HKLM", "HKCU"):
            keys = _lm_paths(reader, UNINSTALL) if hive == "HKLM" else [UNINSTALL]
            for key in keys:
                for sub in reader.subkeys(hive, key):
                    if stop():
                        break
                    vals = reader.values(hive, f"{key}\\{sub}")
                    cmd = _str(vals.get("UninstallString", (None,))[0])
                    if not cmd or vals.get("WindowsInstaller", (0,))[0] == 1:
                        continue
                    st, target = command_state(cmd, exists)
                    if st != "missing":
                        continue
                    loc = expand_env(_str(vals.get("InstallLocation", ("",))[0])).strip().strip('"')
                    if loc and path_state(loc.rstrip("\\") or loc, exists) != "missing":
                        continue      # a pasta do programa ainda existe: não mexe
                    name = _str(vals.get("DisplayName", ("",))[0]) or sub
                    items.append(_make_item("uninstall", hive, f"{key}\\{sub}", None, name,
                                            "Desinstalador não existe mais", target))

    items.sort(key=lambda i: (i.values[0], i.values[1].lower()))
    progress(f"{len(items)} problema(s) encontrado(s) no registro." if items else
             "Nenhum problema encontrado no registro.")
    return items


# =================================================================== backup e correção
def backup_dir() -> str:
    d = os.path.join(app_data_dir(), "backup-registro")
    os.makedirs(d, exist_ok=True)
    return d


def combine_reg_files(files: list[str], out: str) -> None:
    """Junta vários .reg exportados pelo `reg export` (UTF-16) num único arquivo importável."""
    parts = []
    for f in files:
        with open(f, "rb") as fh:
            raw = fh.read()
        if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            text = raw.decode("utf-16")
        else:
            text = raw.decode("utf-8-sig", "replace")
        lines = text.replace("\r\n", "\n").split("\n")
        if lines and lines[0].strip().lower().startswith(("windows registry editor", "regedit4")):
            lines = lines[1:]
        parts.append("\n".join(lines).strip("\n"))
    body = "Windows Registry Editor Version 5.00\n\n" + "\n\n".join(p for p in parts if p) + "\n\n"
    with open(out, "w", encoding="utf-16", newline="") as fh:
        fh.write(body.replace("\n", "\r\n"))


def _reg_exe(args, timeout=120):
    try:
        r = subprocess.run(["reg"] + args, capture_output=True, text=True, creationflags=NO_WINDOW,
                           errors="replace", timeout=timeout)
        return r.returncode, (r.stderr or r.stdout).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def export_backup(keys: list[tuple[str, str]], progress=lambda s: None) -> tuple[str | None, dict]:
    """Exporta cada chave (colmeia, caminho) e junta tudo num único .reg.
    Retorna (arquivo_final ou None, {(colmeia, caminho): erro})."""
    folder = backup_dir()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    tmp_files, errors = [], {}
    for n, (hive, key) in enumerate(keys, 1):
        progress(f"Criando backup {n}/{len(keys)}…")
        tmp = os.path.join(folder, f".tmp-{stamp}-{n}.reg")
        rc, msg = _reg_exe(["export", f"{hive}\\{key}", tmp, "/y", "/reg:64"])
        if rc == 0 and os.path.exists(tmp):
            tmp_files.append(tmp)
        else:
            errors[(hive, key)] = msg or "falha ao exportar"
    final = None
    if tmp_files:
        final = os.path.join(folder, f"limpeza-registro-{stamp}.reg")
        combine_reg_files(tmp_files, final)
    for f in tmp_files:
        try:
            os.remove(f)
        except OSError:
            pass
    return final, errors


def _delete_tree(root, path):
    flags = winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY
    with winreg.OpenKey(root, path, 0, flags) as k:
        while True:
            try:
                sub = winreg.EnumKey(k, 0)
            except OSError:
                break
            _delete_tree(root, f"{path}\\{sub}")
    winreg.DeleteKeyEx(root, path, winreg.KEY_WOW64_64KEY, 0)


def fix_items(items: list[Item], progress=lambda s: None, cancel=None, exists=_default_exists):
    """Faz o backup e corrige. Retorna (feitos, erros[(rótulo, msg)], arquivo_de_backup)."""
    if not IS_WIN:
        raise RuntimeError("A limpeza do registro está disponível apenas no Windows.")
    keys = []
    for it in items:
        k = (it.data["hive"], it.data["key"])
        if k not in keys:
            keys.append(k)
    backup, exp_err = export_backup(keys, progress)
    done, errors = [], []
    for n, it in enumerate(items, 1):
        if cancel and cancel.is_set():
            break
        d = it.data
        label = f"{it.values[1]} ({it.values[0]})"
        if (d["hive"], d["key"]) in exp_err:
            errors.append((label, "backup não pôde ser criado, item não alterado: " + exp_err[(d["hive"], d["key"])]))
            continue
        # confere de novo: se o arquivo voltou a existir, não mexe
        if d.get("target") and path_state(d["target"], exists) == "ok":
            errors.append((label, "o arquivo voltou a existir — item mantido"))
            continue
        progress(f"Corrigindo {n}/{len(items)}: {it.values[1]}")
        root = winreg.HKEY_LOCAL_MACHINE if d["hive"] == "HKLM" else winreg.HKEY_CURRENT_USER
        try:
            if d["value"] is not None:
                with winreg.OpenKey(root, d["key"], 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as k:
                    winreg.DeleteValue(k, d["value"])
            else:
                _delete_tree(root, d["key"])
            log(f"REGISTRO CORRIGIDO {it.path} (backup: {backup})")
            done.append(it)
        except FileNotFoundError:
            done.append(it)       # já não existia
        except PermissionError:
            errors.append((label, "acesso negado — abra o LimpaPC como administrador"))
        except OSError as e:
            errors.append((label, str(e)))
    return done, errors, backup


def list_backups() -> list[str]:
    d = backup_dir()
    files = [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(".reg")]
    return sorted(files, key=lambda f: os.path.getmtime(f), reverse=True)


def restore_backup(path: str) -> tuple[bool, str]:
    """Importa um .reg. Se faltar permissão, tenta de novo como administrador (UAC)."""
    if not IS_WIN:
        return False, "disponível apenas no Windows"
    rc, msg = _reg_exe(["import", path, "/reg:64"])
    if rc == 0:
        log(f"REGISTRO RESTAURADO de {path}")
        return True, ""
    from .winutil import shell_execute_wait
    rc = shell_execute_wait("reg.exe", f'import "{path}" /reg:64', "runas", 0, 300)
    if rc == 0:
        log(f"REGISTRO RESTAURADO (admin) de {path}")
        return True, ""
    return False, "permissão de administrador negada" if rc == -1 else (msg or f"código {rc}")
