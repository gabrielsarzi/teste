"""Interface gráfica (tkinter) do LimpaPC."""
from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from . import __version__
from .scanners import scan_duplicates, scan_junk, scan_large, scan_old
from .system import (delete_reg_key, empty_recycle_bin, kill_pid, recycle_bin_info, scan_leftovers,
                     scan_processes, scan_programs, scan_startup, set_startup_enabled, trim_memory,
                     uninstall_program)
from .utils import (IS_LINUX, IS_WIN, Item, app_data_dir, clear_contents, delete_path, disks,
                    fixed_drives, fmt_size, home, is_admin, log, memory_info,
                    open_location, open_uri, relaunch_as_admin)

MAX_ROWS = 5000
CHECK, UNCHECK = "☑", "☐"


# =================================================================== aba genérica de resultados
class ResultsTab(ttk.Frame):
    title = ""
    hint = ""
    columns: list[tuple[str, int, str]] = []
    hierarchical = False
    scan_label = "Analisar"
    action_label = "Apagar selecionados"
    action_style = "Danger.TButton"
    uses_trash = True          # respeita a opção "enviar para a Lixeira"
    uses_roots = False         # usa as pastas escolhidas na aba Início
    show_open = True
    auto_scan = False

    def __init__(self, master, app):
        super().__init__(master, padding=10)
        self.app = app
        self.items: dict[str, Item] = {}
        self.cancel = threading.Event()
        self.busy = False
        self._progress = ""
        self._sort = (None, False)
        self._scanned = False

        if self.hint:
            ttk.Label(self, text=self.hint, wraplength=1000, justify="left",
                      style="Hint.TLabel").pack(fill="x", pady=(0, 8))

        top = ttk.Frame(self)
        top.pack(fill="x")
        opts = ttk.Frame(top)
        opts.pack(side="left", fill="x", expand=True)
        self.build_options(opts)
        self.btn_stop = ttk.Button(top, text="Parar", command=self.stop, state="disabled")
        self.btn_stop.pack(side="right", padx=(6, 0))
        self.btn_scan = ttk.Button(top, text=self.scan_label, style="Accent.TButton", command=self.start_scan)
        self.btn_scan.pack(side="right")
        if self.uses_roots:
            self.lbl_roots = ttk.Label(self, style="Hint.TLabel")
            self.lbl_roots.pack(fill="x", pady=(6, 0))
            self.refresh_roots_label()

        self.pbar = ttk.Progressbar(self, mode="indeterminate")
        self.pbar.pack(fill="x", pady=(8, 2))
        self.lbl_progress = ttk.Label(self, text=f"Clique em “{self.scan_label}” para começar.")
        self.lbl_progress.pack(fill="x")

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, pady=6)
        cols = ["sel"] + [f"c{i}" for i in range(len(self.columns))]
        self.tree = ttk.Treeview(frame, columns=cols, selectmode="extended",
                                 show="tree headings" if self.hierarchical else "headings")
        if self.hierarchical:
            self.tree.column("#0", width=30, stretch=False)
        self.tree.heading("sel", text=CHECK, command=self.toggle_all)
        self.tree.column("sel", width=40, anchor="center", stretch=False)
        for i, (head, width, anchor) in enumerate(self.columns):
            self.tree.heading(f"c{i}", text=head, command=lambda i=i: self.sort_by(i))
            self.tree.column(f"c{i}", width=width, anchor=anchor, stretch=(i == len(self.columns) - 1))
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree.tag_configure("warn", foreground="#b45309")
        self.tree.tag_configure("danger", foreground="#b91c1c")
        self.tree.tag_configure("muted", foreground="#6b7280")
        self.tree.tag_configure("group", background="#eef2f7", font=app.bold)
        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<space>", lambda e: self.toggle_highlighted())
        self.tree.bind("<Double-1>", lambda e: self.open_highlighted())
        self.tree.bind("<Button-3>", self.on_menu)
        self.tree.bind("<Button-2>", self.on_menu)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Marcar tudo", command=lambda: self.set_all(True)).pack(side="left")
        ttk.Button(bottom, text="Desmarcar tudo", command=lambda: self.set_all(False)).pack(side="left", padx=4)
        ttk.Button(bottom, text="Marcar destacados", command=lambda: self.set_highlighted(True)).pack(side="left")
        if self.show_open:
            ttk.Button(bottom, text="Abrir local", command=self.open_highlighted).pack(side="left", padx=4)
        self.build_actions(bottom)
        self.btn_action = ttk.Button(bottom, text=self.action_label, style=self.action_style,
                                     command=self.run_action)
        self.btn_action.pack(side="right")
        self.lbl_sel = ttk.Label(bottom, text="")
        self.lbl_sel.pack(side="right", padx=10)

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Marcar", command=lambda: self.set_highlighted(True))
        self.menu.add_command(label="Desmarcar", command=lambda: self.set_highlighted(False))
        if self.show_open:
            self.menu.add_command(label="Abrir local", command=self.open_highlighted)
        self.menu.add_command(label="Copiar caminho", command=self.copy_path)

    # ---- pontos de extensão ----
    def build_options(self, frame): ...
    def build_actions(self, frame): ...
    def get_params(self) -> dict: return {}
    def scan_job(self, params, cancel, progress) -> list[Item]: raise NotImplementedError
    def row_tags(self, item: Item) -> tuple: return ()

    def confirm_text(self, items, to_trash) -> str:
        total = sum(i.size for i in items)
        modo = "Os itens serão enviados para a Lixeira (dá para recuperar)." if to_trash else \
            "ATENÇÃO: os itens serão apagados PERMANENTEMENTE."
        return f"Apagar {len(items)} item(ns), liberando {fmt_size(total)}?\n\n{modo}"

    def perform(self, items, to_trash, progress):
        """Executa a ação em segundo plano. Retorna (itens concluídos, erros, bytes liberados)."""
        done, errors, freed = [], [], 0
        for n, it in enumerate(items, 1):
            progress(f"Apagando {n}/{len(items)}: {os.path.basename(it.path)}")
            try:
                delete_path(it.path, to_trash)
                log(f"{'LIXEIRA' if to_trash else 'APAGADO'} {it.path} ({fmt_size(it.size)})")
                done.append(it)
                freed += it.size
            except Exception as e:  # noqa: BLE001
                errors.append((it.path, str(e)))
        return done, errors, freed

    def after_action(self, done, errors, freed):
        ids = {id(i) for i in done}
        for iid, it in list(self.items.items()):
            if id(it) in ids:
                self.tree.delete(iid)
                del self.items[iid]
        self.cleanup_groups()
        msg = f"Concluído: {len(done)} item(ns)."
        if freed:
            msg += f"\nEspaço liberado: {fmt_size(freed)}."
        if errors:
            msg += f"\n\n{len(errors)} item(ns) não puderam ser processados (em uso, sem permissão ou protegidos):\n"
            msg += "\n".join(f"• {os.path.basename(p) or p}: {m}" for p, m in errors[:12])
            if len(errors) > 12:
                msg += f"\n… e mais {len(errors) - 12}."
            messagebox.showwarning("Resultado", msg, parent=self)
        else:
            messagebox.showinfo("Resultado", msg, parent=self)
        self.update_selection()
        self.app.refresh_overview()

    def cleanup_groups(self):
        if not self.hierarchical:
            return
        for gid in self.tree.get_children(""):
            if len(self.tree.get_children(gid)) < 2:
                for c in self.tree.get_children(gid):
                    self.items.pop(c, None)
                self.tree.delete(gid)

    # ---- varredura ----
    def refresh_roots_label(self):
        if self.uses_roots:
            self.lbl_roots.config(text="Pastas analisadas: " + "; ".join(self.app.roots) +
                                  "   (altere na aba Início)")

    def on_show(self):
        if self.auto_scan and not self._scanned and not self.busy:
            self.start_scan()

    def start_scan(self):
        if self.busy:
            return
        if self.uses_roots and not self.app.roots:
            messagebox.showinfo("Pastas", "Escolha ao menos uma pasta na aba Início.", parent=self)
            return
        params = self.get_params()
        if params is None:
            return
        params["roots"] = list(self.app.roots)
        self._scanned = True
        self._background(lambda c, p: self.scan_job(params, c, p), self.populate, "Analisando…")

    def stop(self):
        self.cancel.set()
        self.lbl_progress.config(text="Parando…")

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.btn_scan.config(state=state)
        self.btn_action.config(state=state)
        self.btn_stop.config(state="normal" if busy else "disabled")
        if busy:
            self.pbar.start(12)
        else:
            self.pbar.stop()

    def _background(self, job, on_done, text):
        self.cancel.clear()
        self._progress = text
        self._set_busy(True)
        box: dict = {}

        def runner():
            try:
                box["result"] = job(self.cancel, lambda t: setattr(self, "_progress", t))
            except Exception as e:  # noqa: BLE001
                box["error"] = e

        th = threading.Thread(target=runner, daemon=True)
        th.start()

        def poll():
            self.lbl_progress.config(text=self._progress)
            if th.is_alive():
                self.after(150, poll)
                return
            self._set_busy(False)
            if "error" in box:
                self.lbl_progress.config(text=f"Erro: {box['error']}")
                messagebox.showerror("Erro", str(box["error"]), parent=self)
            else:
                if self.cancel.is_set():
                    self._progress += " (interrompido)"
                    self.lbl_progress.config(text=self._progress)
                on_done(box.get("result"))

        self.after(150, poll)

    # ---- tabela ----
    def populate(self, items):
        self.tree.delete(*self.tree.get_children(""))
        self.items = {}
        items = items or []
        if self.hierarchical:
            groups: dict[int, list[Item]] = {}
            for it in items:
                groups.setdefault(it.group or 0, []).append(it)
            rows = 0
            for gi, members in groups.items():
                if rows > MAX_ROWS:
                    break
                size = members[0].size
                gid = f"g{gi}"
                head = [""] * len(self.columns)
                head[0] = f"Grupo {gi}: {len(members)} cópias idênticas"
                head[1] = fmt_size(size)
                head[-1] = f"desperdício: {fmt_size(size * (len(members) - 1))}"
                self.tree.insert("", "end", iid=gid, values=("", *head), open=True, tags=("group",))
                for n, it in enumerate(members):
                    iid = f"{gid}_{n}"
                    self.items[iid] = it
                    self.tree.insert(gid, "end", iid=iid)
                    self.render(iid)
                    rows += 1
        else:
            for n, it in enumerate(items[:MAX_ROWS]):
                iid = str(n)
                self.items[iid] = it
                self.tree.insert("", "end", iid=iid)
                self.render(iid)
        if len(items) > MAX_ROWS and not self.hierarchical:
            self._progress += f" Mostrando os {MAX_ROWS} maiores."
            self.lbl_progress.config(text=self._progress)
        self.update_selection()

    def render(self, iid):
        it = self.items[iid]
        self.tree.item(iid, values=(CHECK if it.checked else UNCHECK, *it.values), tags=self.row_tags(it))

    def on_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region not in ("cell", "tree"):
            return
        if self.tree.identify_column(event.x) != "#1":
            return
        iid = self.tree.identify_row(event.y)
        if iid in self.items:
            self.items[iid].checked = not self.items[iid].checked
            self.render(iid)
            self.update_selection()
        elif iid:  # linha de grupo: alterna os filhos
            kids = self.tree.get_children(iid)
            state = not all(self.items[k].checked for k in kids)
            for k in kids:
                self.items[k].checked = state
                self.render(k)
            self.update_selection()
        return "break"

    def on_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid and iid not in self.tree.selection():
            self.tree.selection_set(iid)
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _highlighted(self):
        out = []
        for iid in self.tree.selection():
            if iid in self.items:
                out.append(iid)
            else:
                out.extend(self.tree.get_children(iid))
        return out

    def set_all(self, state):
        for iid in self.items:
            self.items[iid].checked = state
            self.render(iid)
        self.update_selection()

    def toggle_all(self):
        self.set_all(not all(i.checked for i in self.items.values()) if self.items else True)

    def set_highlighted(self, state):
        for iid in self._highlighted():
            self.items[iid].checked = state
            self.render(iid)
        self.update_selection()

    def toggle_highlighted(self):
        hl = self._highlighted()
        if hl:
            self.set_highlighted(not all(self.items[i].checked for i in hl))

    def open_highlighted(self):
        for iid in self._highlighted()[:5]:
            it = self.items[iid]
            target = it.data.get("location") or it.data.get("exe") or it.data.get("file") or it.path
            if target and os.path.exists(target):
                open_location(target)

    def copy_path(self):
        paths = [self.items[i].path for i in self._highlighted()]
        if paths:
            self.clipboard_clear()
            self.clipboard_append("\n".join(paths))

    def checked(self) -> list[Item]:
        return [it for it in self.items.values() if it.checked]

    def update_selection(self):
        sel = self.checked()
        total = sum(i.size for i in sel)
        self.lbl_sel.config(text=f"Marcados: {len(sel)}  ({fmt_size(total)})  de {len(self.items)} itens")

    def sort_by(self, col):
        if self.hierarchical or not self.items:
            return
        last, rev = self._sort
        rev = not rev if last == col else col in self.numeric_cols()
        self._sort = (col, rev)

        def key(iid):
            raw = self.items[iid].raw
            v = raw[col] if col < len(raw) else ""
            return (0, v) if isinstance(v, (int, float)) else (1, str(v))

        for pos, iid in enumerate(sorted(self.items, key=key, reverse=rev)):
            self.tree.move(iid, "", pos)

    def numeric_cols(self):
        it = next(iter(self.items.values()))
        return {i for i, v in enumerate(it.raw) if isinstance(v, (int, float))}

    # ---- ação principal ----
    def validate(self, items) -> bool:
        return True

    def run_action(self):
        if self.busy:
            return
        items = self.checked()
        if not items:
            messagebox.showinfo("Nada marcado", "Marque um ou mais itens na coluna ☐ primeiro.", parent=self)
            return
        if not self.validate(items):
            return
        to_trash = self.app.to_trash.get() if self.uses_trash else False
        if not messagebox.askyesno("Confirmar", self.confirm_text(items, to_trash), parent=self, icon="warning"):
            return
        self._background(lambda c, p: self.perform(items, to_trash, p),
                         lambda r: self.after_action(*r), "Processando…")


# =================================================================== abas de arquivos
FILE_COLUMNS = [("Nome", 260, "w"), ("Tamanho", 90, "e"), ("Modificado", 95, "center"),
                ("Último uso", 110, "center"), ("Pasta", 420, "w")]


def _spin(frame, label, var, frm, to, inc=1, width=7, suffix=""):
    ttk.Label(frame, text=label).pack(side="left")
    ttk.Spinbox(frame, from_=frm, to=to, increment=inc, textvariable=var, width=width).pack(side="left", padx=(4, 2))
    if suffix:
        ttk.Label(frame, text=suffix).pack(side="left", padx=(0, 14))


def _int(var, default):
    try:
        return max(0, int(float(str(var.get()).replace(",", "."))))
    except (ValueError, tk.TclError):
        return default


class LargeFilesTab(ResultsTab):
    title = "Arquivos grandes"
    hint = ("Encontra os arquivos que mais ocupam espaço. Revise com cuidado antes de apagar: "
            "nem todo arquivo grande é inútil (vídeos, backups, máquinas virtuais…).")
    columns = FILE_COLUMNS
    uses_roots = True

    def build_options(self, f):
        self.min_mb = tk.StringVar(value="100")
        _spin(f, "Tamanho mínimo:", self.min_mb, 1, 100000, 50, suffix="MB")

    def get_params(self):
        return {"min": _int(self.min_mb, 100) * 1024 * 1024}

    def scan_job(self, p, cancel, progress):
        return scan_large(p["roots"], p["min"], cancel, progress)


class OldFilesTab(ResultsTab):
    title = "Arquivos antigos"
    hint = ("Arquivos que não são abertos nem modificados há muito tempo. Observação: alguns sistemas "
            "não atualizam a data de último acesso; nesse caso usamos a data de modificação.")
    columns = FILE_COLUMNS
    uses_roots = True

    def build_options(self, f):
        self.days = tk.StringVar(value="365")
        self.min_mb = tk.StringVar(value="1")
        self.skip = tk.BooleanVar(value=True)
        _spin(f, "Sem uso há mais de", self.days, 30, 10000, 30, suffix="dias")
        _spin(f, "Tamanho mínimo:", self.min_mb, 0, 100000, 1, suffix="MB")
        ttk.Checkbutton(f, text="Ignorar pastas de programas/sistema", variable=self.skip).pack(side="left")

    def get_params(self):
        return {"days": _int(self.days, 365), "min": _int(self.min_mb, 1) * 1024 * 1024,
                "skip": self.skip.get()}

    def scan_job(self, p, cancel, progress):
        return scan_old(p["roots"], p["days"], p["min"], p["skip"], cancel, progress)


class DuplicatesTab(ResultsTab):
    title = "Arquivos repetidos"
    hint = ("Arquivos com conteúdo idêntico (comparação byte a byte via hash). Em cada grupo uma cópia "
            "fica desmarcada para ser mantida. Nunca é permitido apagar todas as cópias de um grupo.")
    columns = FILE_COLUMNS
    hierarchical = True
    uses_roots = True
    KEEP = {"Manter a mais antiga": "antigo", "Manter a mais recente": "recente",
            "Manter a de caminho mais curto": "curto"}

    def build_options(self, f):
        self.min_mb = tk.StringVar(value="1")
        self.keep = tk.StringVar(value="Manter a mais antiga")
        self.skip = tk.BooleanVar(value=True)
        _spin(f, "Tamanho mínimo:", self.min_mb, 0, 100000, 1, suffix="MB")
        ttk.Combobox(f, textvariable=self.keep, values=list(self.KEEP), state="readonly",
                     width=28).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(f, text="Ignorar pastas de programas/sistema", variable=self.skip).pack(side="left")

    def build_actions(self, f):
        ttk.Button(f, text="Marcar cópias (manter 1 por grupo)", command=self.mark_copies).pack(side="left")

    def mark_copies(self):
        mode = self.KEEP.get(self.keep.get(), "antigo")
        for gid in self.tree.get_children(""):
            kids = list(self.tree.get_children(gid))
            members = [self.items[k] for k in kids]
            if mode == "recente":
                keep = max(members, key=lambda i: i.data["mtime"])
            elif mode == "curto":
                keep = min(members, key=lambda i: (len(i.path), i.path))
            else:
                keep = min(members, key=lambda i: i.data["mtime"])
            for k in kids:
                self.items[k].checked = self.items[k] is not keep
                self.render(k)
        self.update_selection()

    def get_params(self):
        return {"min": max(1, _int(self.min_mb, 1) * 1024 * 1024), "keep": self.KEEP.get(self.keep.get(), "antigo"),
                "skip": self.skip.get()}

    def scan_job(self, p, cancel, progress):
        return scan_duplicates(p["roots"], p["min"], p["skip"], p["keep"], cancel, progress)

    def validate(self, items):
        for gid in self.tree.get_children(""):
            kids = self.tree.get_children(gid)
            if kids and all(self.items[k].checked for k in kids):
                messagebox.showwarning(
                    "Todas as cópias marcadas",
                    f"No {self.tree.item(gid, 'values')[1]} todas as cópias estão marcadas.\n"
                    "Deixe pelo menos uma desmarcada para não perder o arquivo.", parent=self)
                self.tree.see(gid)
                self.tree.selection_set(gid)
                return False
        return True


class JunkTab(ResultsTab):
    title = "Lixo e temporários"
    hint = ("Arquivos temporários, caches de navegadores e programas, relatórios de erro, cache do "
            "Windows Update etc. São recriados automaticamente quando necessário e são apagados "
            "permanentemente (não vão para a Lixeira). Arquivos em uso são pulados. Feche os navegadores "
            "antes de limpar. Algumas pastas exigem executar como administrador.")
    columns = [("Local", 380, "w"), ("Tamanho", 100, "e"), ("Arquivos", 90, "e"), ("Caminho", 450, "w")]
    scan_label = "Analisar lixo"
    action_label = "Limpar selecionados"
    uses_trash = False

    def build_options(self, f):
        self.recycle = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Incluir a Lixeira", variable=self.recycle).pack(side="left")

    def get_params(self):
        return {"recycle": self.recycle.get()}

    def scan_job(self, p, cancel, progress):
        return scan_junk(cancel, progress, p["recycle"])

    def confirm_text(self, items, to_trash):
        total = sum(i.size for i in items)
        return (f"Limpar {len(items)} local(is), liberando até {fmt_size(total)}?\n\n"
                "Os arquivos temporários serão apagados permanentemente.")

    def perform(self, items, to_trash, progress):
        done, errors, freed = [], [], 0
        for it in items:
            label = it.values[0]
            progress(f"Limpando: {label}")
            try:
                if it.kind == "recyclebin":
                    empty_recycle_bin()
                    freed += it.size
                    done.append(it)
                    continue
                f, errs = clear_contents(it.path, it.data.get("patterns"), it.data.get("age", 0),
                                         it.data.get("only_mine", False))
                freed += f
                log(f"LIMPEZA {label}: {fmt_size(f)} liberados, {errs} em uso")
                if errs:
                    errors.append((label, f"{errs} item(ns) em uso ou sem permissão — {fmt_size(f)} liberados"))
                done.append(it)
            except Exception as e:  # noqa: BLE001
                errors.append((label, str(e)))
        return done, errors, freed


class LeftoversTab(ResultsTab):
    title = "Restos de programas"
    hint = ("Pastas (e, no Windows, chaves do registro) que parecem ter sobrado de programas já "
            "desinstalados: não pertencem a nenhum programa instalado e não são modificadas há algum tempo. "
            "É uma estimativa — confira cada item antes de apagar. Chaves do registro têm backup automático "
            "(.reg) antes de serem removidas.")
    columns = [("Tipo", 150, "w"), ("Nome", 230, "w"), ("Tamanho", 90, "e"),
               ("Última modificação", 145, "center"), ("Local", 480, "w")]
    scan_label = "Procurar restos"

    def build_options(self, f):
        self.days = tk.StringVar(value="60")
        _spin(f, "Sem modificação há mais de", self.days, 0, 3650, 30, suffix="dias")
        if IS_WIN:
            ttk.Button(f, text="Abrir backups do registro",
                       command=lambda: open_location(self._backup_dir())).pack(side="left")

    @staticmethod
    def _backup_dir():
        d = os.path.join(app_data_dir(), "backup-registro")
        os.makedirs(d, exist_ok=True)
        return d

    def get_params(self):
        return {"days": _int(self.days, 60)}

    def scan_job(self, p, cancel, progress):
        return scan_leftovers(p["days"], cancel, progress)

    def row_tags(self, item):
        return ("warn",) if item.kind == "regkey" else ()

    def perform(self, items, to_trash, progress):
        done, errors, freed = [], [], 0
        for it in items:
            progress(f"Removendo {it.values[1]}")
            try:
                if it.kind == "regkey":
                    delete_reg_key(it.path, it.data.get("view", "64"))
                else:
                    delete_path(it.path, to_trash)
                    log(f"RESTO REMOVIDO {it.path}")
                    freed += it.size
                done.append(it)
            except Exception as e:  # noqa: BLE001
                errors.append((it.path, str(e)))
        return done, errors, freed


# =================================================================== programas / RAM / inicialização
class ProgramsTab(ResultsTab):
    title = "Programas"
    hint = ("Programas instalados, com tamanho e a última vez que foram usados (quando o sistema registra "
            "isso). Programas não usados há muito tempo aparecem primeiro. Desinstalar abre o desinstalador "
            "oficial de cada programa.")
    columns = [("Programa", 280, "w"), ("Versão", 100, "w"), ("Editor", 170, "w"), ("Tamanho", 90, "e"),
               ("Instalado em", 100, "center"), ("Último uso", 110, "center"), ("Situação", 160, "w")]
    scan_label = "Listar programas"
    action_label = "Desinstalar selecionados"
    uses_trash = False

    def build_options(self, f):
        self.days = tk.StringVar(value="90")
        _spin(f, "Considerar pouco usado após", self.days, 7, 3650, 30, suffix="dias")
        self.only_apps = tk.BooleanVar(value=True)
        if IS_LINUX:
            ttk.Checkbutton(f, text="Só aplicativos com ícone no menu", variable=self.only_apps).pack(side="left")
        if IS_WIN:
            ttk.Button(f, text="Aplicativos da Microsoft Store…",
                       command=lambda: open_uri("ms-settings:appsfeatures")).pack(side="left", padx=6)

    def get_params(self):
        return {"days": _int(self.days, 90), "only_apps": self.only_apps.get()}

    def scan_job(self, p, cancel, progress):
        return scan_programs(cancel, progress, p["days"], p["only_apps"])

    def row_tags(self, item):
        st = item.values[-1]
        return ("danger",) if st == "Desinstalador ausente" else ("warn",) if st == "Pouco usado" else ()

    def confirm_text(self, items, to_trash):
        names = "\n".join(f"• {i.values[0]}" for i in items[:15])
        more = f"\n… e mais {len(items) - 15}" if len(items) > 15 else ""
        return (f"Desinstalar {len(items)} programa(s)?\n\n{names}{more}\n\n"
                "O desinstalador de cada programa será aberto, um de cada vez. Siga as instruções dele.")

    def perform(self, items, to_trash, progress):
        done, errors, freed = [], [], 0
        for n, it in enumerate(items, 1):
            if self.cancel.is_set():
                break
            progress(f"Desinstalando {n}/{len(items)}: {it.values[0]} (aguardando o desinstalador…)")
            if it.data.get("broken"):
                errors.append((it.values[0], "desinstalador não existe mais — remova a entrada na aba "
                                              "“Restos de programas”"))
                continue
            try:
                res = uninstall_program(it.data)
                if res == "ok" or res.startswith("movido"):
                    done.append(it)
                    freed += it.size
                else:
                    errors.append((it.values[0], res))
            except Exception as e:  # noqa: BLE001
                errors.append((it.values[0], str(e)))
        return done, errors, freed

    def after_action(self, done, errors, freed):
        super().after_action(done, errors, 0)
        self.start_scan()  # atualiza a lista (alguns desinstaladores terminam depois)


class ProcessesTab(ResultsTab):
    title = "Memória RAM"
    hint = ("Programas abertos agora e quanta memória RAM cada um usa. Finalize os que você não está "
            "usando para liberar RAM (salve seu trabalho antes!). Processos essenciais do sistema são "
            "protegidos. Veja também a aba “Inicialização” para impedir que programas abram sozinhos.")
    columns = [("Processo", 260, "w"), ("PID / Qtd.", 90, "e"), ("Memória", 100, "e"),
               ("Observação", 150, "w"), ("Caminho", 480, "w")]
    scan_label = "Atualizar"
    action_label = "Finalizar selecionados"
    uses_trash = False
    auto_scan = True

    def build_options(self, f):
        self.group = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Agrupar por programa", variable=self.group,
                        command=self.start_scan).pack(side="left")
        self.ram_bar = ttk.Progressbar(f, length=220, maximum=100)
        self.ram_bar.pack(side="left", padx=(20, 6))
        self.ram_lbl = ttk.Label(f, text="")
        self.ram_lbl.pack(side="left")

    def build_actions(self, f):
        if IS_WIN:
            ttk.Button(f, text="Liberar memória ociosa", command=self.trim).pack(side="left", padx=4)

    def get_params(self):
        return {"group": self.group.get()}

    def scan_job(self, p, cancel, progress):
        return scan_processes(p["group"], cancel, progress)

    def populate(self, items):
        super().populate(items)
        total, used = memory_info()
        if total:
            self.ram_bar["value"] = used * 100 / total
            self.ram_lbl.config(text=f"RAM: {fmt_size(used)} de {fmt_size(total)} ({used * 100 // total}%)")

    def row_tags(self, item):
        return ("muted",) if item.data.get("critical") else ()

    def validate(self, items):
        crit = [i.values[0] for i in items if i.data.get("critical")]
        if crit:
            messagebox.showwarning("Protegido", "Estes processos são essenciais e não serão finalizados:\n"
                                   + ", ".join(crit), parent=self)
            for i in items:
                if i.data.get("critical"):
                    i.checked = False
            for iid in self.items:
                self.render(iid)
            self.update_selection()
            return False
        return True

    def confirm_text(self, items, to_trash):
        names = ", ".join(i.values[0] for i in items[:12])
        return (f"Finalizar {len(items)} processo(s)?\n{names}\n\n"
                f"Libera cerca de {fmt_size(sum(i.size for i in items))} de RAM.\n"
                "Trabalho não salvo nesses programas será perdido.")

    def perform(self, items, to_trash, progress):
        done, errors, freed = [], [], 0
        for it in items:
            progress(f"Finalizando {it.values[0]}…")
            ok = True
            for pid in it.data["pids"]:
                try:
                    kill_pid(pid)
                except Exception as e:  # noqa: BLE001
                    ok = False
                    errors.append((f"{it.values[0]} (PID {pid})", str(e) or "acesso negado"))
            if ok:
                done.append(it)
                freed += it.size
                log(f"PROCESSO FINALIZADO {it.values[0]}")
        return done, errors, 0

    def after_action(self, done, errors, freed):
        super().after_action(done, errors, 0)
        self.start_scan()

    def trim(self):
        before = memory_info()[1]

        def job(c, p):
            p("Liberando memória ociosa dos processos…")
            return trim_memory()

        def done(n):
            after = memory_info()[1]
            messagebox.showinfo("Memória", f"Memória ociosa liberada de {n} processos.\n"
                                f"RAM em uso: {fmt_size(before)} → {fmt_size(after)}\n\n"
                                "Dica: execute como administrador para alcançar mais processos.", parent=self)
            self.start_scan()

        self._background(job, done, "Liberando memória…")


class StartupTab(ResultsTab):
    title = "Inicialização"
    hint = ("Programas que abrem sozinhos quando o computador liga. Cada um consome RAM e deixa a "
            "inicialização mais lenta. Desativar não desinstala nada e pode ser desfeito a qualquer "
            "momento (no Windows funciona igual ao Gerenciador de Tarefas).")
    columns = [("Programa", 260, "w"), ("Situação", 100, "center"), ("Origem", 210, "w"), ("Comando", 520, "w")]
    scan_label = "Atualizar"
    action_label = "Desativar selecionados"
    action_style = "Accent.TButton"
    uses_trash = False
    auto_scan = True

    def build_actions(self, f):
        ttk.Button(f, text="Ativar selecionados", command=lambda: self.toggle(True)).pack(side="left", padx=4)

    def scan_job(self, p, cancel, progress):
        return scan_startup(cancel, progress)

    def row_tags(self, item):
        return () if item.data["enabled"] else ("muted",)

    def run_action(self):
        self.toggle(False)

    def toggle(self, enable):
        items = self.checked()
        if not items:
            messagebox.showinfo("Nada marcado", "Marque um ou mais itens primeiro.", parent=self)
            return
        errors = []
        for it in items:
            try:
                set_startup_enabled(it, enable)
            except Exception as e:  # noqa: BLE001
                errors.append(f"• {it.values[0]}: {e} (itens de “todos os usuários” exigem administrador)")
        if errors:
            messagebox.showwarning("Inicialização", "Alguns itens não puderam ser alterados:\n" + "\n".join(errors),
                                   parent=self)
        self.start_scan()


# =================================================================== Início e Lixeira
class OverviewTab(ttk.Frame):
    title = "Início"

    def __init__(self, master, app):
        super().__init__(master, padding=14)
        self.app = app
        ttk.Label(self, text="Visão geral do computador", style="Title.TLabel").pack(anchor="w")
        quick = ttk.Frame(self)
        quick.pack(fill="x", pady=(8, 0))
        ttk.Button(quick, text="⚡ Limpeza rápida (lixo e temporários)", style="Accent.TButton",
                   command=lambda: app.show_tab(JunkTab, scan=True)).pack(side="left")
        ttk.Button(quick, text="Encontrar arquivos grandes",
                   command=lambda: app.show_tab(LargeFilesTab, scan=True)).pack(side="left", padx=6)
        ttk.Button(quick, text="Encontrar repetidos",
                   command=lambda: app.show_tab(DuplicatesTab, scan=True)).pack(side="left")

        self.disk_frame = ttk.LabelFrame(self, text="Discos", padding=10)
        self.disk_frame.pack(fill="x", pady=(6, 6))
        self.ram_frame = ttk.LabelFrame(self, text="Memória RAM", padding=10)
        self.ram_frame.pack(fill="x", pady=6)
        self.ram_bar = ttk.Progressbar(self.ram_frame, maximum=100, length=400)
        self.ram_bar.pack(side="left")
        self.ram_lbl = ttk.Label(self.ram_frame)
        self.ram_lbl.pack(side="left", padx=10)
        ttk.Button(self.ram_frame, text="Ver o que está usando a RAM",
                   command=lambda: app.show_tab(ProcessesTab)).pack(side="right")

        rb = ttk.LabelFrame(self, text="Lixeira", padding=10)
        rb.pack(fill="x", pady=6)
        self.rb_lbl = ttk.Label(rb, text="…")
        self.rb_lbl.pack(side="left")
        ttk.Button(rb, text="Esvaziar Lixeira", style="Danger.TButton", command=self.empty_bin).pack(side="right")
        ttk.Button(rb, text="Atualizar", command=self.refresh).pack(side="right", padx=6)

        opts = ttk.LabelFrame(self, text="Opções", padding=10)
        opts.pack(fill="x", pady=6)
        ttk.Checkbutton(opts, text="Enviar arquivos apagados para a Lixeira (recomendado — permite recuperar)",
                        variable=app.to_trash).pack(anchor="w")
        row = ttk.Frame(opts)
        row.pack(fill="x", pady=(6, 0))
        adm = "Executando como administrador ✔" if is_admin() else \
            "Executando sem privilégios de administrador (algumas pastas do sistema não serão limpas)."
        ttk.Label(row, text=adm).pack(side="left")
        if IS_WIN and not is_admin():
            ttk.Button(row, text="Reabrir como administrador", command=app.elevate).pack(side="left", padx=8)
        ttk.Button(row, text="Ver histórico de ações",
                   command=lambda: open_location(os.path.join(app_data_dir(), "historico.log"))).pack(side="right")

        roots = ttk.LabelFrame(self, text="Pastas a analisar (arquivos grandes, repetidos e antigos)", padding=10)
        roots.pack(fill="both", expand=True, pady=6)
        self.roots_list = tk.Listbox(roots, height=3, activestyle="none")
        self.roots_list.pack(side="left", fill="both", expand=True)
        btns = ttk.Frame(roots)
        btns.pack(side="left", fill="y", padx=(8, 0))
        for n, (txt, cmd) in enumerate((("Adicionar pasta…", self.add_root),
                                        ("Adicionar todos os discos", self.add_drives),
                                        ("Remover", self.remove_root),
                                        ("Restaurar padrão", self.reset_roots))):
            ttk.Button(btns, text=txt, command=cmd).grid(row=n // 2, column=n % 2, sticky="ew", padx=2, pady=2)

        self.refresh_roots()

    def refresh(self):
        for w in self.disk_frame.winfo_children():
            w.destroy()
        for i, (mount, total, used, free) in enumerate(disks()):
            ttk.Label(self.disk_frame, text=mount, width=16).grid(row=i, column=0, sticky="w")
            bar = ttk.Progressbar(self.disk_frame, maximum=100, length=400,
                                  style="Red.Horizontal.TProgressbar" if total and used / total > 0.9 else
                                  "Horizontal.TProgressbar")
            bar["value"] = used * 100 / total if total else 0
            bar.grid(row=i, column=1, padx=8, pady=2)
            ttk.Label(self.disk_frame, text=f"{fmt_size(free)} livres de {fmt_size(total)}"
                      f" ({used * 100 // max(total, 1)}% usado)").grid(row=i, column=2, sticky="w")
        total, used = memory_info()
        if total:
            self.ram_bar["value"] = used * 100 / total
            self.ram_lbl.config(text=f"{fmt_size(used)} em uso de {fmt_size(total)} ({used * 100 // total}%)")

        def load_bin():
            size, count = recycle_bin_info()
            self.after(0, lambda: self.rb_lbl.config(text=f"{count} item(ns) — {fmt_size(size)}"))
        threading.Thread(target=load_bin, daemon=True).start()

    def empty_bin(self):
        size, count = recycle_bin_info()
        if not count and not size:
            messagebox.showinfo("Lixeira", "A Lixeira já está vazia.", parent=self)
            return
        if messagebox.askyesno("Esvaziar Lixeira", f"Apagar permanentemente {count} item(ns) ({fmt_size(size)}) "
                               "da Lixeira?", icon="warning", parent=self):
            try:
                empty_recycle_bin()
                messagebox.showinfo("Lixeira", f"Lixeira esvaziada. {fmt_size(size)} liberados.", parent=self)
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("Lixeira", str(e), parent=self)
            self.refresh()

    def refresh_roots(self):
        self.roots_list.delete(0, "end")
        for r in self.app.roots:
            self.roots_list.insert("end", r)
        self.app.roots_changed()

    def add_root(self):
        d = filedialog.askdirectory(parent=self, title="Escolha uma pasta para analisar")
        if d:
            d = os.path.normpath(d)
            if d not in self.app.roots:
                self.app.roots.append(d)
            self.refresh_roots()

    def add_drives(self):
        for d in fixed_drives():
            if d not in self.app.roots:
                self.app.roots.append(d)
        self.refresh_roots()

    def remove_root(self):
        for idx in reversed(self.roots_list.curselection()):
            del self.app.roots[idx]
        self.refresh_roots()

    def reset_roots(self):
        self.app.roots[:] = [home()]
        self.refresh_roots()


# =================================================================== janela principal
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"LimpaPC {__version__} — limpeza e otimização do computador")
        self.geometry("1200x800")
        self.minsize(950, 600)
        self._style()
        self.roots = [home()]
        self.to_trash = tk.BooleanVar(value=True)

        header = ttk.Frame(self, padding=(14, 10, 14, 0))
        header.pack(fill="x")
        ttk.Label(header, text="🧹 LimpaPC", style="Brand.TLabel").pack(side="left")
        ttk.Label(header, text="Libere espaço em disco e memória RAM", style="Hint.TLabel").pack(side="left", padx=12)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.tabs = {}
        for cls in (OverviewTab, JunkTab, LargeFilesTab, DuplicatesTab, OldFilesTab, LeftoversTab,
                    ProgramsTab, ProcessesTab, StartupTab):
            tab = cls(self.nb, self)
            self.nb.add(tab, text=cls.title)
            self.tabs[cls] = tab
        self.nb.bind("<<NotebookTabChanged>>", self._tab_changed)
        self.after(100, self.tabs[OverviewTab].refresh)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _style(self):
        st = ttk.Style(self)
        themes = st.theme_names()
        st.theme_use("vista" if "vista" in themes else "clam" if "clam" in themes else themes[0])
        base = tkfont.nametofont("TkDefaultFont")
        if IS_WIN:
            base.configure(family="Segoe UI", size=9)
        self.bold = base.copy()
        self.bold.configure(weight="bold")
        big = base.copy()
        big.configure(size=16, weight="bold")
        title = base.copy()
        title.configure(size=13, weight="bold")
        self._fonts = (big, title)
        st.configure("Brand.TLabel", font=big)
        st.configure("Title.TLabel", font=title)
        st.configure("Hint.TLabel", foreground="#4b5563")
        st.configure("Accent.TButton", font=self.bold)
        st.configure("Danger.TButton", foreground="#b91c1c", font=self.bold)
        st.configure("Treeview", rowheight=max(22, base.metrics("linespace") + 8))
        st.configure("Red.Horizontal.TProgressbar", background="#dc2626")

    def _tab_changed(self, _):
        tab = self.nametowidget(self.nb.select())
        if isinstance(tab, ResultsTab):
            tab.on_show()
        elif isinstance(tab, OverviewTab):
            tab.refresh()

    def show_tab(self, cls, scan=False):
        tab = self.tabs[cls]
        self.nb.select(tab)
        if scan and not tab.busy:
            tab.start_scan()

    def roots_changed(self):
        for tab in getattr(self, "tabs", {}).values():
            if isinstance(tab, ResultsTab):
                tab.refresh_roots_label()

    def refresh_overview(self):
        self.tabs[OverviewTab].refresh()

    def elevate(self):
        if relaunch_as_admin():
            self.destroy()

    def _close(self):
        for tab in self.tabs.values():
            if isinstance(tab, ResultsTab):
                tab.cancel.set()
        self.destroy()


def main():
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
    app = App()
    app.mainloop()


if __name__ == "__main__":
    sys.exit(main())
