"""Desinstalador avançado: sobras após desinstalar, desinstalação forçada e apps da Microsoft Store."""
from __future__ import annotations

import glob
import os
import re
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .pages import ResultsPage
from .system import _alnum, _GENERIC, delete_reg_key
from .utils import IS_WIN, Item, delete_path, entry_size, fmt_size, home, is_protected, log, norm
from .winutil import ps_json, run_ps

if IS_WIN:
    import winreg  # type: ignore


# =================================================================== sobras de um programa
def _clean_name(name: str) -> str:
    n = re.sub(r"\(.*?\)|\[.*?\]", " ", name or "")
    n = re.sub(r"\b(v(ersion|ersão)?\s*)?\d+([._]\d+)*\b", " ", n, flags=re.I)
    n = re.sub(r"\b(x64|x86|64-bit|32-bit|amd64|arm64|pt-br|en-us|setup|installer)\b", " ", n, flags=re.I)
    return " ".join(n.split())


def _keys_for(p: dict):
    """Chaves de comparação: nome limpo completo e palavras fortes do nome."""
    clean = _clean_name(p.get("name", ""))
    full = _alnum(clean)
    words = [w for w in re.split(r"[^A-Za-z0-9]+", clean) if len(w) >= 5 and w.lower() not in _GENERIC]
    strong = {full} if len(full) >= 4 else set()
    strong |= {_alnum(w) for w in words[:2]}
    return full, strong, _alnum(p.get("publisher", ""))


def _match(name: str, full: str, strong: set) -> int:
    """0 = não, 1 = provável, 2 = certeza."""
    n = _alnum(name)
    if not n:
        return 0
    if n == full:
        return 2
    if any(k and (k == n or (len(k) >= 5 and k in n)) for k in strong):
        return 1
    return 0


def program_leftovers(p: dict, remaining_locations: list[str]) -> list[Item]:
    """Procura pastas, chaves do registro e atalhos deixados por um programa desinstalado."""
    full, strong, pub = _keys_for(p)
    if not full and not strong:
        return []
    items: list[Item] = []
    seen = set()
    keep = [norm(x) for x in remaining_locations if x]

    def in_use(path):
        n = norm(path)
        return any(k == n or k.startswith(n + os.sep) or n.startswith(k + os.sep) for k in keep)

    def add_path(path, kind, certainty):
        n = norm(path)
        if n in seen or is_protected(path) or in_use(path) or not os.path.lexists(path):
            return
        seen.add(n)
        size = entry_size(path)[0]
        label = {"dir": "Pasta", "file": "Atalho" if path.lower().endswith(".lnk") else "Arquivo"}[kind]
        items.append(Item(path=path, size=size, values=(label, os.path.basename(path), fmt_size(size), path),
                          raw=(label, os.path.basename(path).lower(), size, path.lower()), kind=kind,
                          checked=certainty >= 2))

    loc = p.get("location") or ""
    if loc and os.path.isdir(loc):
        add_path(loc, "dir", 2)

    if IS_WIN:
        env = os.environ.get
        parents = [env("ProgramW6432") or env("ProgramFiles"), env("ProgramFiles(x86)"), env("ProgramData"),
                   env("APPDATA"), env("LOCALAPPDATA"), os.path.join(env("LOCALAPPDATA") or "", "Programs"),
                   os.path.join(home(), "AppData", "LocalLow"), os.path.join(home(), "Documents")]
    else:
        parents = [os.path.join(home(), ".config"), os.path.join(home(), ".local", "share"),
                   os.path.join(home(), ".cache"), home()]
    for parent in parents:
        if not parent or not os.path.isdir(parent):
            continue
        try:
            entries = list(os.scandir(parent))
        except OSError:
            continue
        for e in entries:
            try:
                if not e.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            name = e.name.lstrip(".")
            if parent == home() and not e.name.startswith("."):
                continue
            m = _match(name, full, strong)
            if m:
                add_path(e.path, "dir", m)
            elif pub and len(pub) >= 4 and _alnum(name) == pub:
                # pasta do fabricante: procura a subpasta do programa
                try:
                    subs = [s for s in os.scandir(e.path) if s.is_dir(follow_symlinks=False)]
                except OSError:
                    subs = []
                hits = [s for s in subs if _match(s.name, full, strong)]
                if hits and len(hits) == len(subs):
                    add_path(e.path, "dir", 1)
                for s in hits:
                    add_path(s.path, "dir", _match(s.name, full, strong))

    # atalhos (menu Iniciar e Área de Trabalho)
    if IS_WIN:
        starts = [os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
                  os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
                  os.path.join(home(), "Desktop"), os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop")]
        for d in starts:
            for f in glob.glob(os.path.join(d, "*")) + glob.glob(os.path.join(d, "*", "*.lnk")):
                base = os.path.splitext(os.path.basename(f))[0]
                m = _match(base, full, strong)
                if m and (f.lower().endswith(".lnk") or os.path.isdir(f)):
                    # atalho só é sobra se o alvo não existe mais
                    if f.lower().endswith(".lnk") and _lnk_target_exists(f):
                        continue
                    add_path(f, "dir" if os.path.isdir(f) else "file", m)

        # registro
        roots = [(winreg.HKEY_CURRENT_USER, "HKCU", "Software", 0),
                 (winreg.HKEY_LOCAL_MACHINE, "HKLM", "SOFTWARE", winreg.KEY_WOW64_64KEY),
                 (winreg.HKEY_LOCAL_MACHINE, "HKLM", "SOFTWARE", winreg.KEY_WOW64_32KEY)]
        for hive, hname, base, flag in roots:
            view = "32" if flag == winreg.KEY_WOW64_32KEY else "64"
            for sub, certainty in _reg_candidates(hive, base, flag, full, strong, pub):
                key = f"{hname}\\{base}\\{sub}"
                if key.lower() in seen:
                    continue
                seen.add(key.lower())
                items.append(Item(path=key, size=0, values=("Registro", sub.split("\\")[-1], "—", key),
                                  raw=("registro", sub.lower(), 0, key.lower()), kind="regkey",
                                  checked=certainty >= 2, data={"view": view}))
    items.sort(key=lambda i: (not i.checked, i.raw[0], -i.size))
    return items


def _reg_candidates(hive, base, flag, full, strong, pub):
    from .system import _reg_subkeys
    out = []
    try:
        root = winreg.OpenKey(hive, base, 0, winreg.KEY_READ | flag)
    except OSError:
        return out
    for sub in _reg_subkeys(root):
        low = _alnum(sub)
        if low in ("microsoft", "classes", "policies", "wow6432node", "clients", "windows"):
            continue
        m = _match(sub, full, strong)
        if m:
            out.append((sub, m))
        elif pub and len(pub) >= 4 and low == pub:
            try:
                k = winreg.OpenKey(root, sub, 0, winreg.KEY_READ | flag)
                inner = _reg_subkeys(k)
            except OSError:
                inner = []
            hits = [s for s in inner if _match(s, full, strong)]
            for s in hits:
                out.append((f"{sub}\\{s}", _match(s, full, strong)))
            if hits and len(hits) == len(inner):
                out.append((sub, 1))
    return out


def _lnk_target_exists(lnk: str) -> bool:
    """Lê o caminho de destino de um atalho .lnk (formato Shell Link) de forma simples."""
    try:
        with open(lnk, "rb") as f:
            data = f.read(65536)
        m = re.findall(rb"([A-Za-z]:\\[^\x00]{3,259}?\.exe)\x00", data)
        if not m:
            return True   # não deu para ler: considera válido (não sugerir apagar)
        return any(os.path.exists(os.path.expandvars(x.decode("latin-1"))) for x in m)
    except OSError:
        return True


def remove_items(items, to_trash, progress=lambda s: None):
    done, errors, freed = [], [], 0
    for it in items:
        progress(f"Removendo {it.values[1]}…")
        try:
            if it.kind == "regkey":
                delete_reg_key(it.path, it.data.get("view", "64"))
            else:
                delete_path(it.path, to_trash)
                freed += it.size
            log(f"SOBRA REMOVIDA {it.path}")
            done.append(it)
        except Exception as e:  # noqa: BLE001
            errors.append((it.path, str(e)))
    return done, errors, freed


class LeftoverDialog(tk.Toplevel):
    """Janela exibida depois de desinstalar: lista as sobras encontradas para remover."""

    def __init__(self, page, programs: list[dict], forced=False):
        app = page.app
        t, c = app.t, app.t.c
        super().__init__(app)
        self.app, self.programs, self.forced = app, programs, forced
        self.title("Procurar sobras — LimpaOne")
        self.configure(bg=c["bg"])
        self.geometry(f"{t.px(860)}x{t.px(560)}")
        self.transient(app)
        f = ttk.Frame(self, padding=t.px(22))
        f.pack(fill="both", expand=True)
        names = ", ".join(p["name"] for p in programs[:3]) + ("…" if len(programs) > 3 else "")
        ttk.Label(f, text="Sobras encontradas", style="H2.TLabel").pack(anchor="w")
        self.sub = ttk.Label(f, text=f"Procurando pastas, registro e atalhos deixados por {names}…",
                             style="Muted.TLabel", wraplength=t.px(800), justify="left")
        self.sub.pack(anchor="w", pady=(t.px(4), t.px(12)))
        box = ttk.Frame(f, style="Card.TFrame", padding=1)
        box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(box, columns=("sel", "tipo", "nome", "tam", "local"), show="headings")
        for col, head, w, anc in (("sel", "☑", 40, "center"), ("tipo", "TIPO", 90, "w"), ("nome", "NOME", 200, "w"),
                                  ("tam", "TAMANHO", 90, "e"), ("local", "LOCAL", 420, "w")):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=t.px(w), anchor=anc, stretch=col == "local")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Button-1>", self._click)
        foot = ttk.Frame(f)
        foot.pack(fill="x", pady=(t.px(12), 0))
        self.btn = ttk.Button(foot, text="Remover selecionados", style="Danger.TButton", command=self.remove,
                              state="disabled")
        self.btn.pack(side="right")
        ttk.Button(foot, text="Fechar", command=self.destroy).pack(side="right", padx=t.px(8))
        ttk.Label(foot, text="Itens marcados têm alta certeza. Revise os desmarcados antes de incluir. "
                             "Chaves do registro ganham backup.", style="Small.TLabel").pack(side="left")
        self.items: dict[str, Item] = {}
        threading.Thread(target=self._scan, daemon=True).start()

    def _scan(self):
        from .system import installed_programs
        try:
            remaining = installed_programs(threading.Event(), lambda s: None)
            locs = [r.get("location") for r in remaining if r.get("location")]
            names = {r["name"].lower() for r in remaining}
            found = []
            for p in self.programs:
                if p["name"].lower() in names and not self.forced:
                    continue   # ainda instalado (desinstalação cancelada)
                found += program_leftovers(p, locs)
            if self.forced:
                for p in self.programs:
                    if p.get("regkey"):
                        found.append(Item(path=p["regkey"], values=("Registro", "Entrada de desinstalação", "—",
                                                                    p["regkey"]), raw=(), kind="regkey",
                                          checked=True, data={"view": p.get("view", "64")}))
        except Exception as e:  # noqa: BLE001
            found = []
            log(f"erro procurando sobras: {e}")
        try:
            self.after(0, lambda: self._show(found))
        except tk.TclError:
            pass

    def _show(self, found):
        for n, it in enumerate(found):
            iid = f"i{n}"
            self.items[iid] = it
            self.tree.insert("", "end", iid=iid, values=("☑" if it.checked else "☐", *it.values))
        total = sum(i.size for i in found)
        if found:
            self.sub.config(text=f"{len(found)} sobra(s) encontrada(s), {fmt_size(total)}. Marque o que deseja remover.")
            self.btn.config(state="normal")
        else:
            self.sub.config(text="Nenhuma sobra encontrada — a desinstalação foi completa. ✓")

    def _click(self, e):
        if self.tree.identify_column(e.x) != "#1":
            return
        iid = self.tree.identify_row(e.y)
        if iid in self.items:
            it = self.items[iid]
            it.checked = not it.checked
            self.tree.set(iid, "sel", "☑" if it.checked else "☐")
        return "break"

    def remove(self):
        sel = [i for i in self.items.values() if i.checked]
        if not sel:
            return
        if not messagebox.askyesno("Remover sobras", f"Remover {len(sel)} item(ns)?", parent=self):
            return
        done, errors, freed = remove_items(sel, self.app.settings["to_trash"])
        for iid, it in list(self.items.items()):
            if it in done:
                self.tree.delete(iid)
                del self.items[iid]
        self.app.toast(f"{len(done)} sobra(s) removida(s) · {fmt_size(freed)} liberados")
        if errors:
            messagebox.showwarning("Alguns itens foram pulados",
                                   "\n".join(f"• {p}: {m}" for p, m in errors[:10]), parent=self)
        if not self.items:
            self.destroy()


# =================================================================== apps da Microsoft Store
BLOAT = {
    "microsoft.bingnews": "Notícias (MSN)", "microsoft.bingweather": "Clima (MSN)", "microsoft.bingsearch": "Pesquisa Bing",
    "microsoft.gethelp": "Obter Ajuda", "microsoft.getstarted": "Dicas", "microsoft.microsoftsolitairecollection":
    "Microsoft Solitaire Collection", "microsoft.microsoftofficehub": "Office (atalho)", "microsoft.people": "Pessoas",
    "microsoft.skypeapp": "Skype", "microsoft.windowsfeedbackhub": "Hub de Comentários", "microsoft.zunemusic":
    "Groove Música / Media Player", "microsoft.zunevideo": "Filmes e TV", "microsoft.mixedreality.portal":
    "Portal de Realidade Misturada", "microsoft.microsoft3dviewer": "Visualizador 3D", "microsoft.3dbuilder": "3D Builder",
    "microsoft.mspaint": "Paint 3D", "microsoft.print3d": "Print 3D", "microsoft.office.onenote": "OneNote (antigo)",
    "microsoft.oneconnect": "Planos Móveis", "microsoft.wallet": "Carteira", "microsoft.windowsmaps": "Mapas",
    "microsoft.549981c3f5f10": "Cortana", "clipchamp.clipchamp": "Clipchamp", "microsoft.powerautomatedesktop":
    "Power Automate", "microsoft.todos": "To Do", "microsoft.windowscommunicationsapps": "Email e Calendário (antigo)",
    "microsoft.messaging": "Mensagens", "microsoft.bingfinance": "Finanças (MSN)", "microsoft.bingsports": "Esportes (MSN)",
    "microsoft.news": "Notícias", "microsoft.yourphone": "Vincular ao Celular", "msteams": "Microsoft Teams (pessoal)",
    "microsoftteams": "Microsoft Teams (pessoal)", "microsoft.outlookforwindows": "Outlook (novo)",
    "microsoft.windows.devhome": "Dev Home", "microsoft.copilot": "Copilot",
}
BLOAT_PREFIX = ("king.com.", "spotifyab.", "disney.", "facebook.", "bytedancepte.", "amazon.com.", "5a894077.",
                "4df9e0f8.", "e046963f.", "adobesystemsincorporated.", "dolbylaboratories.", "a278ab0d.")
PROTECTED_APPX = ("microsoft.windowsstore", "microsoft.desktopappinstaller", "microsoft.sechealthui",
                  "microsoft.windows.shellexperiencehost", "microsoft.windows.startmenuexperiencehost",
                  "microsoft.aad.brokerplugin", "microsoft.accountscontrol", "microsoft.windows.cloudexperiencehost",
                  "microsoft.ui.xaml", "microsoft.vclibs", "microsoft.net", "microsoft.services.store",
                  "microsoft.storepurchaseapp", "microsoft.windowsappruntime", "microsoftwindows.client",
                  "windows.", "microsoft.windows.search", "microsoft.lockapp", "microsoft.xboxgameoverlay",
                  "microsoft.gamingservices")
FRIENDLY = {"microsoft.windowscalculator": "Calculadora", "microsoft.windowsnotepad": "Bloco de Notas",
            "microsoft.paint": "Paint", "microsoft.windows.photos": "Fotos", "microsoft.screensketch": "Ferramenta de Captura",
            "microsoft.windowsalarms": "Relógio", "microsoft.windowscamera": "Câmera", "microsoft.windowssoundrecorder":
            "Gravador de Som", "microsoft.windowsterminal": "Terminal", "microsoft.xboxapp": "Xbox",
            "microsoft.gamingapp": "Xbox", "microsoft.xboxidentityprovider": "Xbox (login)",
            "microsoft.xboxspeechtotextoverlay": "Xbox (legendas)", "microsoft.xbox.tcui": "Xbox (interface)",
            "microsoft.xboxgamingoverlay": "Xbox Game Bar", "microsoft.whiteboard": "Whiteboard",
            "microsoft.microsoftstickynotes": "Notas Autoadesivas", "microsoft.windows.ai.copilot.provider": "Copilot",
            "microsoft.edge.gameassist": "Edge Game Assist", "microsoftcorporationii.quickassist": "Assistência Rápida"}


def _friendly(name: str) -> str:
    low = name.lower()
    if low in BLOAT:
        return BLOAT[low]
    if low in FRIENDLY:
        return FRIENDLY[low]
    tail = name.split(".", 1)[-1] if "." in name else name
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", tail)


def is_bloat(name: str) -> bool:
    low = name.lower()
    return low in BLOAT or low.startswith(BLOAT_PREFIX)


def is_protected_appx(name: str) -> bool:
    return name.lower().startswith(PROTECTED_APPX)


def scan_store_apps(cancel, progress) -> list[Item]:
    if not IS_WIN:
        progress("Disponível apenas no Windows 10/11.")
        return []
    progress("Lendo apps da Microsoft Store…")
    rows = ps_json("Get-AppxPackage | Where-Object { -not $_.IsFramework -and $_.SignatureKind -ne 'System' -and "
                   "-not $_.NonRemovable } | Select-Object Name, PackageFullName, Version, InstallLocation, "
                   "@{n='Publisher';e={$_.Publisher -replace '^CN=([^,]+).*','$1'}}", timeout=120)
    items = []
    for r in rows:
        if cancel.is_set():
            break
        name = r.get("Name") or ""
        if not name or is_protected_appx(name):
            continue
        loc = r.get("InstallLocation") or ""
        size = entry_size(loc)[0] if loc and os.path.isdir(loc) else 0
        bloat = is_bloat(name)
        status = "Pré-instalado dispensável" if bloat else ""
        items.append(Item(path=r.get("PackageFullName") or name, size=size,
                          values=(_friendly(name), str(r.get("Version") or ""), fmt_size(size) if size else "—",
                                  status, name),
                          raw=(_friendly(name).lower(), str(r.get("Version")), size, status, name.lower()),
                          kind="appx", checked=bloat, data={"location": loc}))
    items.sort(key=lambda i: (not i.checked, i.raw[0]))
    progress(f"{len(items)} apps encontrados ({sum(1 for i in items if i.checked)} dispensáveis sugeridos).")
    return items


class StoreAppsPage(ResultsPage):
    key, icon = "store_apps", "store"
    title = "Apps da Microsoft Store"
    subtitle = ("Apps que vêm com o Windows ou da Microsoft Store. Os marcados são pré-instalados que a maioria "
                "das pessoas não usa (bloatware). Apps essenciais do sistema ficam fora da lista. Dá para "
                "reinstalar qualquer um pela Microsoft Store.")
    columns = [("App", 260, "w"), ("Versão", 120, "w"), ("Tamanho", 90, "e"), ("Situação", 190, "w"),
               ("Pacote", 380, "w")]
    scan_label = "Listar apps"
    action_label = "Remover selecionados"
    uses_trash = False
    auto_scan = True
    show_open = False
    empty_text = "Disponível no Windows 10 e 11." if not IS_WIN else "Clique em “Listar apps”."

    def scan_job(self, p, cancel, progress):
        return scan_store_apps(cancel, progress)

    def row_tags(self, item):
        return ("warn",) if item.checked and item.values[3] else ()

    def confirm_text(self, items, to_trash):
        names = "\n".join(f"• {i.values[0]}" for i in items[:15])
        return f"Remover {len(items)} app(s) para a sua conta?\n\n{names}\n\nDá para reinstalar pela Microsoft Store."

    def perform(self, items, to_trash, progress):
        done, errors, freed = [], [], 0
        for n, it in enumerate(items, 1):
            progress(f"Removendo {n}/{len(items)}: {it.values[0]}…")
            rc, out, err = run_ps(f"Remove-AppxPackage -Package '{it.path}' -ErrorAction Stop", timeout=300)
            if rc == 0 and not err.strip():
                done.append(it)
                freed += it.size
                log(f"APP REMOVIDO {it.path}")
            else:
                errors.append((it.values[0], (err.strip().splitlines() or ["falhou"])[0][:200]))
        return done, errors, freed

    def success_text(self, done, freed):
        return f"{len(done)} app(s) removido(s)" + (f" · {fmt_size(freed)} liberados" if freed else "")

