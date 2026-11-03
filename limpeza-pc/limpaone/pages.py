"""Páginas com listas de resultados (lixo, arquivos, programas, RAM, inicialização…)."""
from __future__ import annotations

import csv
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .scanners import scan_duplicates, scan_junk, scan_large, scan_old
from .system import (delete_reg_key, empty_recycle_bin, kill_pid, scan_leftovers, scan_processes,
                     scan_programs, scan_startup, set_startup_enabled, trim_memory, uninstall_program)
from .utils import (IS_LINUX, IS_WIN, Item, app_data_dir, clear_contents, delete_path, fmt_size, log,
                    memory_info, open_location)
from .widgets import Icon, RingGauge

MAX_ROWS = 5000
CHECK, UNCHECK = "☑", "☐"


class PlaceholderEntry(ttk.Entry):
    """Campo de texto com dica cinza quando vazio."""

    def __init__(self, master, var, placeholder, **kw):
        super().__init__(master, textvariable=var, style="Placeholder.TEntry", **kw)
        self.var, self.ph = var, placeholder
        self._show()
        self.bind("<FocusIn>", self._hide)
        self.bind("<FocusOut>", lambda e: self._show())

    def _show(self):
        if not self.var.get():
            self.var.set(self.ph)
            self.configure(style="Placeholder.TEntry")

    def _hide(self, _=None):
        if self.var.get() == self.ph:
            self.var.set("")
        self.configure(style="TEntry")


# =================================================================== base das páginas
class Page(ttk.Frame):
    key = ""
    title = ""
    subtitle = ""
    icon = "home"

    def __init__(self, master, app):
        super().__init__(master, padding=(app.t.px(28), app.t.px(22), app.t.px(28), app.t.px(18)))
        self.app, self.t = app, app.t
        self.header = ttk.Frame(self)
        self.header.pack(fill="x")
        self.header_right = ttk.Frame(self.header)
        self.header_right.pack(side="right", anchor="n")
        left = ttk.Frame(self.header)
        left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text=self.title, style="H1.TLabel").pack(anchor="w")
        if self.subtitle:
            self.lbl_sub = ttk.Label(left, text=self.subtitle, style="Muted.TLabel", justify="left",
                                     wraplength=self.t.px(720))
            self.lbl_sub.pack(anchor="w", pady=(self.t.px(4), 0))
            left.bind("<Configure>", lambda e: self.lbl_sub.config(wraplength=max(200, min(e.width, self.t.px(860)))))
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, pady=(self.t.px(16), 0))

    def on_show(self):
        pass

    def busy_now(self) -> bool:
        return False


class BackgroundMixin:
    """Executa tarefas em segundo plano atualizando um rótulo de progresso."""

    def run_bg(self, job, on_done, text="Processando…", on_finally=None):
        self.cancel = getattr(self, "cancel", threading.Event())
        self.cancel.clear()
        self._progress = text
        box: dict = {}

        def runner():
            try:
                box["result"] = job(self.cancel, lambda s: setattr(self, "_progress", s))
            except Exception as e:  # noqa: BLE001
                box["error"] = e

        th = threading.Thread(target=runner, daemon=True)
        th.start()

        def poll():
            self.show_progress(self._progress)
            if th.is_alive():
                self.after(120, poll)
                return
            if on_finally:
                on_finally()
            if "error" in box:
                self.show_progress(f"Erro: {box['error']}")
                messagebox.showerror("Erro", str(box["error"]), parent=self)
            else:
                if self.cancel.is_set():
                    self._progress += " (interrompido)"
                    self.show_progress(self._progress)
                on_done(box.get("result"))

        self.after(120, poll)

    def show_progress(self, text):
        pass


# =================================================================== página genérica de lista
class ResultsPage(BackgroundMixin, Page):
    columns: list[tuple[str, int, str]] = []
    hierarchical = False
    scan_label = "Analisar"
    action_label = "Apagar selecionados"
    action_style = "Danger.TButton"
    uses_trash = True
    uses_roots = False
    show_open = True
    auto_scan = False
    needs_restore_point = False   # True = cria ponto de restauração antes da ação principal
    empty_text = "Nenhum resultado ainda.\nClique em “Analisar” para começar."

    def __init__(self, master, app):
        super().__init__(master, app)
        t = self.t
        self.all_items: list[Item] = []
        self.items: dict[str, Item] = {}
        self.cancel = threading.Event()
        self.busy = False
        self._progress = ""
        self._sort = (None, False)
        self._scanned = False
        self._filter_job = None

        # barra de ferramentas
        bar = ttk.Frame(self.body, style="Card.TFrame", padding=(t.px(14), t.px(10)))
        bar.pack(fill="x")
        opts = ttk.Frame(bar, style="Flat.TFrame")
        opts.pack(side="left", fill="x", expand=True)
        self.build_options(opts)
        self.btn_scan = ttk.Button(bar, text=self.scan_label, style="Primary.TButton", command=self.start_scan)
        self.btn_scan.pack(side="right")
        self.btn_stop = ttk.Button(bar, text="Parar", command=self.stop)
        # busca (no canto superior direito da página)
        sbox = ttk.Frame(self.header_right)
        sbox.pack(side="right", anchor="s", pady=(t.px(10), 0))
        Icon(sbox, "search", t.px(16), t.c["muted"], t.c["bg"]).pack(side="left", padx=(0, t.px(6)))
        self.filter_var = tk.StringVar()
        ent = PlaceholderEntry(sbox, self.filter_var, "Buscar na lista…", width=24)
        ent.pack(side="left")
        self.filter_var.trace_add("write", lambda *a: self._schedule_filter())

        # progresso
        prog = ttk.Frame(self.body)
        prog.pack(fill="x", pady=(t.px(10), t.px(6)))
        self.pbar = ttk.Progressbar(prog, mode="indeterminate", style="Thin.Horizontal.TProgressbar")
        self.lbl_progress = ttk.Label(prog, text="", style="Small.TLabel")
        self.lbl_progress.pack(side="left")
        if self.uses_roots:
            self.lbl_roots = ttk.Label(prog, text="", style="Small.TLabel", cursor="hand2")
            self.lbl_roots.pack(side="right")
            self.lbl_roots.bind("<Button-1>", lambda e: self.app.show("settings"))
            self.refresh_roots_label()

        # tabela
        tcard = ttk.Frame(self.body, style="Card.TFrame", padding=1)
        tcard.pack(fill="both", expand=True)
        cols = ["sel"] + [f"c{i}" for i in range(len(self.columns))]
        self.tree = ttk.Treeview(tcard, columns=cols, selectmode="extended",
                                 show="tree headings" if self.hierarchical else "headings")
        if self.hierarchical:
            self.tree.column("#0", width=t.px(28), stretch=False)
        self.tree.heading("sel", text=CHECK, command=self.toggle_all)
        self.tree.column("sel", width=t.px(44), anchor="center", stretch=False)
        for i, (head, width, anchor) in enumerate(self.columns):
            self.tree.heading(f"c{i}", text=head.upper(), anchor=anchor if anchor != "e" else "e",
                              command=lambda i=i: self.sort_by(i))
            self.tree.column(f"c{i}", width=t.px(width), anchor=anchor, stretch=(i == len(self.columns) - 1))
        vsb = ttk.Scrollbar(tcard, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tcard, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tcard.rowconfigure(0, weight=1)
        tcard.columnconfigure(0, weight=1)
        c = t.c
        self.tree.tag_configure("odd", background=c["row_alt"])
        self.tree.tag_configure("warn", foreground=c["warning"])
        self.tree.tag_configure("danger", foreground=c["danger"])
        self.tree.tag_configure("ok", foreground=c["success"])
        self.tree.tag_configure("muted", foreground=c["subtle"])
        self.tree.tag_configure("group", background=c["surface2"], font=t.f_bold)
        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<space>", lambda e: self.toggle_highlighted())
        self.tree.bind("<Double-1>", lambda e: self.open_highlighted())
        self.tree.bind("<Button-3>", self.on_menu)
        self.tree.bind("<Button-2>", self.on_menu)
        self.empty = ttk.Label(tcard, text=self.empty_text, style="Card.Muted.TLabel", justify="center")
        self.empty.place(relx=0.5, rely=0.5, anchor="center")

        # rodapé
        foot = ttk.Frame(self.body)
        foot.pack(fill="x", pady=(t.px(12), 0))
        self.btn_action = ttk.Button(foot, text=self.action_label, style=self.action_style, command=self.run_action)
        self.btn_action.pack(side="right")
        self.lbl_sel = ttk.Label(foot, text="", style="Bold.TLabel")
        self.lbl_sel.pack(side="right", padx=t.px(14))
        ttk.Button(foot, text="Marcar tudo", command=lambda: self.set_all(True)).pack(side="left")
        ttk.Button(foot, text="Desmarcar", command=lambda: self.set_all(False)).pack(side="left", padx=t.px(6))
        if self.show_open:
            ttk.Button(foot, text="Abrir local", command=self.open_highlighted).pack(side="left")
        ttk.Button(foot, text="Exportar", command=self.export_csv).pack(side="left", padx=t.px(6))
        self.build_actions(foot)

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Marcar", command=lambda: self.set_highlighted(True))
        self.menu.add_command(label="Desmarcar", command=lambda: self.set_highlighted(False))
        if self.show_open:
            self.menu.add_command(label="Abrir local", command=self.open_highlighted)
        self.menu.add_command(label="Copiar caminho", command=self.copy_path)
        self.update_selection()

    # ---- pontos de extensão ----
    def build_options(self, frame): ...
    def build_actions(self, frame): ...
    def get_params(self) -> dict: return {}
    def scan_job(self, params, cancel, progress) -> list[Item]: raise NotImplementedError
    def row_tags(self, item: Item) -> tuple: return ()

    def confirm_text(self, items, to_trash) -> str:
        total = sum(i.size for i in items)
        modo = "Os itens vão para a Lixeira (dá para recuperar depois)." if to_trash else \
            "ATENÇÃO: os itens serão apagados PERMANENTEMENTE."
        return f"Apagar {len(items)} item(ns), liberando {fmt_size(total)}?\n\n{modo}"

    def perform(self, items, to_trash, progress):
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

    def success_text(self, done, freed):
        return f"{len(done)} item(ns) concluído(s)" + (f" · {fmt_size(freed)} liberados" if freed else "")

    def after_action(self, done, errors, freed):
        ids = {id(i) for i in done}
        self.all_items = [i for i in self.all_items if id(i) not in ids]
        if self.hierarchical:
            counts: dict = {}
            for i in self.all_items:
                counts[i.group] = counts.get(i.group, 0) + 1
            self.all_items = [i for i in self.all_items if counts.get(i.group, 0) > 1]
        self.render_rows()
        if done:
            self.app.toast(self.success_text(done, freed))
        if errors:
            msg = f"{len(errors)} item(ns) não puderam ser processados (em uso, sem permissão ou protegidos):\n\n"
            msg += "\n".join(f"• {os.path.basename(str(p)) or p}: {m}" for p, m in errors[:12])
            if len(errors) > 12:
                msg += f"\n… e mais {len(errors) - 12}."
            messagebox.showwarning("Alguns itens foram pulados", msg, parent=self)
        self.app.data_changed()

    # ---- varredura ----
    def refresh_roots_label(self):
        if self.uses_roots:
            roots = self.app.settings["roots"]
            txt = roots[0] if len(roots) == 1 else f"{len(roots)} pastas"
            self.lbl_roots.config(text=f"Analisando: {txt}  ·  alterar")

    def on_show(self):
        if self.auto_scan and not self._scanned and not self.busy:
            self.start_scan()

    def busy_now(self):
        return self.busy

    def start_scan(self):
        if self.busy:
            return
        if self.uses_roots and not self.app.settings["roots"]:
            messagebox.showinfo("Pastas", "Escolha ao menos uma pasta em Configurações.", parent=self)
            return
        params = self.get_params()
        if params is None:
            return
        params["roots"] = list(self.app.settings["roots"])
        self._scanned = True
        self._set_busy(True)
        self.run_bg(lambda c, p: self.scan_job(params, c, p), self.populate, "Analisando…",
                    on_finally=lambda: self._set_busy(False))

    def stop(self):
        self.cancel.set()
        self.show_progress("Parando…")

    def show_progress(self, text):
        self.lbl_progress.config(text=text)

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.btn_scan.config(state=state)
        self.btn_action.config(state=state)
        if busy:
            self.btn_stop.pack(side="right", padx=(0, self.t.px(8)), before=self.btn_scan)
        else:
            self.btn_stop.pack_forget()
        if busy:
            self.pbar.pack(side="bottom", fill="x", before=self.lbl_progress)
            self.pbar.start(12)
            self.empty.config(text="Analisando…")
        else:
            self.pbar.stop()
            self.pbar.pack_forget()
        self.app.set_nav_busy(self.key, busy)

    # ---- tabela ----
    def populate(self, items):
        self.all_items = list(items or [])
        self._sort = (None, False)
        self.render_rows()

    def _schedule_filter(self):
        if self._filter_job:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(220, self.render_rows)

    def _visible(self):
        q = self.filter_var.get().strip().lower()
        if q == "buscar na lista…":
            q = ""
        if not q:
            return self.all_items
        match = lambda it: any(q in str(v).lower() for v in it.values)  # noqa: E731
        if self.hierarchical:
            groups = {it.group for it in self.all_items if match(it)}
            return [it for it in self.all_items if it.group in groups]
        return [it for it in self.all_items if match(it)]

    def render_rows(self):
        self.tree.delete(*self.tree.get_children(""))
        self.items = {}
        items = self._visible()
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
                head[0] = f"{len(members)} cópias idênticas"
                head[1] = fmt_size(size)
                head[-1] = f"Espaço desperdiçado: {fmt_size(size * (len(members) - 1))}"
                self.tree.insert("", "end", iid=gid, values=("", *head), open=True, tags=("group",))
                for n, it in enumerate(members):
                    iid = f"{gid}_{n}"
                    self.items[iid] = it
                    self.tree.insert(gid, "end", iid=iid)
                    self.render(iid, n)
                    rows += 1
        else:
            for n, it in enumerate(items[:MAX_ROWS]):
                iid = f"r{n}"
                self.items[iid] = it
                self.tree.insert("", "end", iid=iid)
                self.render(iid, n)
        if self.all_items:
            self.empty.place_forget()
        else:
            self.empty.config(text=self.empty_text if not self._scanned else "Tudo limpo por aqui! ✓\nNada encontrado.")
            self.empty.place(relx=0.5, rely=0.5, anchor="center")
        if len(items) > MAX_ROWS and not self.hierarchical:
            self.show_progress(self._progress + f"  ·  Mostrando os primeiros {MAX_ROWS}.")
        self.update_selection()

    def render(self, iid, n=0):
        it = self.items[iid]
        tags = self.row_tags(it) + (("odd",) if n % 2 else ())
        self.tree.item(iid, values=(CHECK if it.checked else UNCHECK, *it.values), tags=tags)

    def _rerender(self, iid):
        idx = self.tree.index(iid)
        self.render(iid, idx)

    def on_click(self, event):
        if self.tree.identify_region(event.x, event.y) not in ("cell", "tree"):
            return
        if self.tree.identify_column(event.x) != "#1":
            return
        iid = self.tree.identify_row(event.y)
        if iid in self.items:
            self.items[iid].checked = not self.items[iid].checked
            self._rerender(iid)
            self.update_selection()
        elif iid:
            kids = self.tree.get_children(iid)
            state = not all(self.items[k].checked for k in kids)
            for k in kids:
                self.items[k].checked = state
                self._rerender(k)
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
            self._rerender(iid)
        self.update_selection()

    def toggle_all(self):
        self.set_all(not all(i.checked for i in self.items.values()) if self.items else True)

    def set_highlighted(self, state):
        for iid in self._highlighted():
            self.items[iid].checked = state
            self._rerender(iid)
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
        return [it for it in self.all_items if it.checked]

    def update_selection(self):
        sel = self.checked()
        total = sum(i.size for i in sel)
        if sel:
            self.lbl_sel.config(text=f"{len(sel)} marcado(s)" + (f"  ·  {fmt_size(total)}" if total else ""))
        else:
            self.lbl_sel.config(text=f"{len(self.all_items)} itens" if self.all_items else "")

    def sort_by(self, col):
        if self.hierarchical or not self.all_items:
            return
        last, rev = self._sort
        nums = {i for i, v in enumerate(self.all_items[0].raw) if isinstance(v, (int, float))}
        rev = (not rev) if last == col else (col in nums)
        self._sort = (col, rev)

        def key(it):
            v = it.raw[col] if col < len(it.raw) else ""
            return (0, v) if isinstance(v, (int, float)) else (1, str(v))

        self.all_items.sort(key=key, reverse=rev)
        for i, (head, _, anchor) in enumerate(self.columns):
            arrow = (" ↓" if rev else " ↑") if i == col else ""
            self.tree.heading(f"c{i}", text=head.upper() + arrow)
        self.render_rows()

    def export_csv(self):
        if not self.all_items:
            messagebox.showinfo("Exportar", "Não há itens para exportar.", parent=self)
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".csv",
                                            initialfile=f"LimpaOne - {self.title}.csv",
                                            filetypes=[("Planilha CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow([h for h, _, _ in self.columns] + ["Caminho completo"])
            for it in self.all_items:
                w.writerow(list(it.values) + [it.path])
        self.app.toast(f"Lista exportada para {os.path.basename(path)}")

    # ---- ação principal ----
    def validate(self, items) -> bool:
        return True

    def run_action(self):
        if self.busy:
            return
        items = self.checked()
        if not items:
            messagebox.showinfo("Nada marcado", "Marque um ou mais itens clicando na caixa ☐ de cada linha.",
                                parent=self)
            return
        if not self.validate(items):
            return
        to_trash = self.app.settings["to_trash"] if self.uses_trash else False
        if not messagebox.askyesno("Confirmar", self.confirm_text(items, to_trash), parent=self, icon="warning"):
            return

        def go():
            self._set_busy(True)
            self.run_bg(lambda c, p: self.perform(items, to_trash, p), lambda r: self.after_action(*r),
                        "Processando…", on_finally=lambda: self._set_busy(False))

        if self.needs_restore_point:
            from .safety import guarded
            guarded(self, self.title, go, self.show_progress)
        else:
            go()


# =================================================================== utilitários de formulário
FILE_COLUMNS = [("Nome", 260, "w"), ("Tamanho", 95, "e"), ("Modificado", 105, "center"),
                ("Último uso", 115, "center"), ("Pasta", 420, "w")]


def spin(frame, label, var, frm, to, inc=1, width=6, suffix=""):
    ttk.Label(frame, text=label, style="Card.TLabel").pack(side="left")
    ttk.Spinbox(frame, from_=frm, to=to, increment=inc, textvariable=var, width=width).pack(side="left", padx=(6, 4))
    if suffix:
        ttk.Label(frame, text=suffix, style="Card.Muted.TLabel").pack(side="left", padx=(0, 16))


def as_int(var, default):
    try:
        return max(0, int(float(str(var.get()).replace(",", "."))))
    except (ValueError, tk.TclError):
        return default


# =================================================================== páginas de limpeza
class JunkPage(ResultsPage):
    key, icon = "junk", "sparkles"
    title = "Lixo e cache"
    subtitle = ("Temporários, caches de navegadores e programas, relatórios de erro e restos do Windows Update — "
                "tudo é recriado quando necessário. Itens de Privacidade (histórico, cookies, recentes) vêm "
                "desmarcados: marque se quiser apagar seus rastros.")
    columns = [("Local", 380, "w"), ("Tamanho", 100, "e"), ("Arquivos", 90, "e"), ("Caminho", 450, "w")]
    scan_label = "Analisar"
    action_label = "Limpar selecionados"
    uses_trash = False
    show_open = True

    def build_options(self, f):
        self.recycle = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Incluir a Lixeira", variable=self.recycle, style="Card.TCheckbutton").pack(side="left")

    def get_params(self):
        return {"recycle": self.recycle.get()}

    def scan_job(self, p, cancel, progress):
        return scan_junk(cancel, progress, p["recycle"])

    def validate(self, items):
        procs = {p.lower() for i in items for p in i.data.get("procs", ())}
        if not procs:
            return True
        from .system import list_processes
        running = {p["name"].lower() for p in list_processes()}
        open_ = sorted(procs & running)
        if open_:
            return messagebox.askyesno("Feche os navegadores",
                                       "Para limpar histórico e cookies, feche antes: " + ", ".join(open_) +
                                       ".\n\nCom o navegador aberto esses arquivos ficam bloqueados e não são "
                                       "apagados. Continuar mesmo assim?", parent=self)
        return True

    def confirm_text(self, items, to_trash):
        total = sum(i.size for i in items)
        priv = [i for i in items if i.data.get("privacy")]
        if priv:
            return (f"Limpar {len(items)} local(is), liberando até {fmt_size(total)}?\n\n"
                    f"Inclui {len(priv)} item(ns) de privacidade (histórico/cookies): você pode precisar fazer "
                    "login de novo nos sites. Temporários são apagados permanentemente.")
        return (f"Limpar {len(items)} local(is), liberando até {fmt_size(total)}?\n\n"
                "Arquivos temporários são apagados permanentemente. Arquivos em uso são pulados.")

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
                if errs and not f:
                    errors.append((label, f"{errs} item(ns) em uso ou sem permissão"))
                else:
                    done.append(it)
            except Exception as e:  # noqa: BLE001
                errors.append((label, str(e)))
        return done, errors, freed


class LargeFilesPage(ResultsPage):
    key, icon = "large", "file"
    title = "Arquivos grandes"
    subtitle = ("Os arquivos que mais ocupam espaço. Revise antes de apagar: nem todo arquivo grande é inútil "
                "(vídeos, backups, máquinas virtuais…).")
    columns = FILE_COLUMNS
    uses_roots = True

    def build_options(self, f):
        self.min_mb = tk.StringVar(value="100")
        spin(f, "Maiores que", self.min_mb, 1, 100000, 50, suffix="MB")

    def get_params(self):
        return {"min": as_int(self.min_mb, 100) * 1024 * 1024}

    def scan_job(self, p, cancel, progress):
        return scan_large(p["roots"], p["min"], cancel, progress)


class DuplicatesPage(ResultsPage):
    key, icon = "dups", "copy"
    title = "Arquivos repetidos"
    subtitle = ("Arquivos com conteúdo idêntico (comparados byte a byte). Uma cópia de cada grupo fica "
                "desmarcada para ser mantida. Nunca é permitido apagar todas as cópias.")
    columns = FILE_COLUMNS
    hierarchical = True
    uses_roots = True
    KEEP = {"Manter a mais antiga": "antigo", "Manter a mais recente": "recente",
            "Manter a de caminho mais curto": "curto"}

    def build_options(self, f):
        self.min_mb = tk.StringVar(value="1")
        self.keep = tk.StringVar(value="Manter a mais antiga")
        self.skip = tk.BooleanVar(value=True)
        spin(f, "Maiores que", self.min_mb, 0, 100000, 1, suffix="MB")
        ttk.Combobox(f, textvariable=self.keep, values=list(self.KEEP), state="readonly",
                     width=27).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(f, text="Ignorar pastas de programas", variable=self.skip,
                        style="Card.TCheckbutton").pack(side="left")

    def build_actions(self, f):
        ttk.Button(f, text="Remarcar cópias", command=self.mark_copies).pack(side="left")

    def mark_copies(self):
        mode = self.KEEP.get(self.keep.get(), "antigo")
        groups: dict = {}
        for it in self.all_items:
            groups.setdefault(it.group, []).append(it)
        for members in groups.values():
            if mode == "recente":
                keep = max(members, key=lambda i: i.data["mtime"])
            elif mode == "curto":
                keep = min(members, key=lambda i: (len(i.path), i.path))
            else:
                keep = min(members, key=lambda i: i.data["mtime"])
            for it in members:
                it.checked = it is not keep
        self.render_rows()

    def get_params(self):
        return {"min": max(1, as_int(self.min_mb, 1) * 1024 * 1024),
                "keep": self.KEEP.get(self.keep.get(), "antigo"), "skip": self.skip.get()}

    def scan_job(self, p, cancel, progress):
        return scan_duplicates(p["roots"], p["min"], p["skip"], p["keep"], cancel, progress)

    def validate(self, items):
        groups: dict = {}
        for it in self.all_items:
            groups.setdefault(it.group, []).append(it)
        for members in groups.values():
            if all(m.checked for m in members):
                messagebox.showwarning("Todas as cópias marcadas",
                                       f"Todas as cópias de “{members[0].values[0]}” estão marcadas.\n"
                                       "Deixe pelo menos uma desmarcada para não perder o arquivo.", parent=self)
                return False
        return True


class OldFilesPage(ResultsPage):
    key, icon = "old", "clock"
    title = "Arquivos antigos"
    subtitle = ("Arquivos que não são abertos nem modificados há muito tempo. Ótimos candidatos para apagar "
                "ou mover para um HD externo / nuvem.")
    columns = FILE_COLUMNS
    uses_roots = True

    def build_options(self, f):
        self.days = tk.StringVar(value="365")
        self.min_mb = tk.StringVar(value="1")
        self.skip = tk.BooleanVar(value=True)
        spin(f, "Sem uso há mais de", self.days, 30, 10000, 30, suffix="dias")
        spin(f, "Maiores que", self.min_mb, 0, 100000, 1, suffix="MB")
        ttk.Checkbutton(f, text="Ignorar pastas de programas", variable=self.skip,
                        style="Card.TCheckbutton").pack(side="left")

    def get_params(self):
        return {"days": as_int(self.days, 365), "min": as_int(self.min_mb, 1) * 1024 * 1024, "skip": self.skip.get()}

    def scan_job(self, p, cancel, progress):
        return scan_old(p["roots"], p["days"], p["min"], p["skip"], cancel, progress)


class LeftoversPage(ResultsPage):
    key, icon = "leftovers", "package"
    title = "Restos de programas"
    subtitle = ("Pastas e chaves do registro que sobraram de programas já desinstalados. É uma estimativa: "
                "confira cada item. Chaves do registro ganham backup automático (.reg) antes de serem removidas.")
    columns = [("Tipo", 150, "w"), ("Nome", 230, "w"), ("Tamanho", 90, "e"),
               ("Modificado em", 120, "center"), ("Local", 480, "w")]
    scan_label = "Procurar restos"
    needs_restore_point = True

    def build_options(self, f):
        self.days = tk.StringVar(value="60")
        spin(f, "Sem uso há mais de", self.days, 0, 3650, 30, suffix="dias")

    def build_actions(self, f):
        if IS_WIN:
            ttk.Button(f, text="Backups do registro", command=self.open_backups).pack(side="left")

    @staticmethod
    def open_backups():
        d = os.path.join(app_data_dir(), "backup-registro")
        os.makedirs(d, exist_ok=True)
        open_location(d)

    def get_params(self):
        return {"days": as_int(self.days, 60)}

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


# =================================================================== programas, RAM e inicialização
class ProgramsPage(ResultsPage):
    key, icon = "programs", "grid"
    title = "Desinstalar programas"
    subtitle = ("Programas instalados, do menos usado para o mais usado. Depois do desinstalador oficial, o LimpaOne "
                "procura as sobras (pastas, registro e atalhos) para remover. Programas quebrados podem ser "
                "removidos com a desinstalação forçada.")
    columns = [("Programa", 270, "w"), ("Versão", 95, "w"), ("Editor", 170, "w"), ("Tamanho", 90, "e"),
               ("Instalado em", 105, "center"), ("Último uso", 115, "center"), ("Situação", 160, "w")]
    scan_label = "Listar programas"
    action_label = "Desinstalar"
    uses_trash = False
    needs_restore_point = True
    auto_scan = True

    def build_options(self, f):
        self.days = tk.StringVar(value="90")
        spin(f, "Pouco usado após", self.days, 7, 3650, 30, suffix="dias")
        self.only_apps = tk.BooleanVar(value=True)
        if IS_LINUX:
            ttk.Checkbutton(f, text="Só aplicativos com ícone", variable=self.only_apps,
                            style="Card.TCheckbutton").pack(side="left")

    def build_actions(self, f):
        ttk.Button(f, text="Desinstalação forçada", command=self.force).pack(side="left")

    def force(self):
        items = self.checked()
        if not items:
            messagebox.showinfo("Desinstalação forçada", "Marque o(s) programa(s) primeiro.", parent=self)
            return
        names = "\n".join(f"• {i.values[0]}" for i in items[:10])
        if not messagebox.askyesno("Desinstalação forçada",
                                   f"Use só quando o desinstalador normal não funciona.\n\n{names}\n\n"
                                   "O LimpaOne vai procurar e remover as pastas, chaves do registro e atalhos desses "
                                   "programas sem rodar o desinstalador deles. Continuar?", icon="warning", parent=self):
            return
        from .uninstall_pages import LeftoverDialog
        LeftoverDialog(self, [i.data for i in items], forced=True)

    def get_params(self):
        return {"days": as_int(self.days, 90), "only_apps": self.only_apps.get()}

    def scan_job(self, p, cancel, progress):
        return scan_programs(cancel, progress, p["days"], p["only_apps"])

    def row_tags(self, item):
        st = item.values[-1]
        return ("danger",) if st == "Desinstalador ausente" else ("warn",) if st == "Pouco usado" else ()

    def confirm_text(self, items, to_trash):
        names = "\n".join(f"• {i.values[0]}" for i in items[:15])
        more = f"\n… e mais {len(items) - 15}" if len(items) > 15 else ""
        return (f"Desinstalar {len(items)} programa(s)?\n\n{names}{more}\n\n"
                "O desinstalador de cada programa será aberto, um de cada vez.")

    def perform(self, items, to_trash, progress):
        done, errors, freed = [], [], 0
        for n, it in enumerate(items, 1):
            if self.cancel.is_set():
                break
            progress(f"Desinstalando {n}/{len(items)}: {it.values[0]} — siga as instruções do desinstalador…")
            if it.data.get("broken"):
                errors.append((it.values[0], "o desinstalador não existe mais — remova a entrada em "
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

    def success_text(self, done, freed):
        return f"{len(done)} programa(s) desinstalado(s)"

    def after_action(self, done, errors, freed):
        super().after_action(done, errors, freed)
        progs = [i.data for i in done if i.data.get("uninstall") != "::trash::"]
        if progs:
            from .uninstall_pages import LeftoverDialog
            self.after(800, lambda: LeftoverDialog(self, progs))
        self.start_scan()


class ProcessesPage(ResultsPage):
    key, icon = "ram", "chip"
    title = "Memória RAM"
    subtitle = ("Programas abertos agora e quanta memória cada um usa. Finalize o que não está usando para "
                "liberar RAM (salve seu trabalho antes). Processos essenciais do sistema são protegidos.")
    columns = [("Processo", 260, "w"), ("Instâncias / PID", 120, "e"), ("Memória", 100, "e"),
               ("Observação", 150, "w"), ("Caminho", 460, "w")]
    scan_label = "Atualizar"
    action_label = "Finalizar selecionados"
    uses_trash = False
    auto_scan = True

    def __init__(self, master, app):
        super().__init__(master, app)
        self.gauge = RingGauge(self.header_right, self.t, size=96, thickness=9, bg_key="bg")
        self.gauge.pack(side="right")
        self.lbl_ram = ttk.Label(self.header_right, text="", style="Muted.TLabel", justify="right")
        self.lbl_ram.pack(side="right", padx=self.t.px(12))

    def build_options(self, f):
        self.group = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Agrupar por programa", variable=self.group, style="Card.TCheckbutton",
                        command=self.start_scan).pack(side="left")

    def build_actions(self, f):
        if IS_WIN:
            ttk.Button(f, text="Liberar memória ociosa", command=self.trim).pack(side="left")

    def get_params(self):
        return {"group": self.group.get()}

    def scan_job(self, p, cancel, progress):
        return scan_processes(p["group"], cancel, progress)

    def populate(self, items):
        super().populate(items)
        total, used = memory_info()
        if total:
            pct = used / total
            color = self.t.c["danger"] if pct > .85 else self.t.c["warning"] if pct > .7 else self.t.c["success"]
            self.gauge.set(pct, f"{pct * 100:.0f}%", "em uso", color)
            self.lbl_ram.config(text=f"{fmt_size(used)} usados\nde {fmt_size(total)}")

    def row_tags(self, item):
        return ("muted",) if item.data.get("critical") else ()

    def validate(self, items):
        crit = [i for i in items if i.data.get("critical")]
        if crit:
            messagebox.showwarning("Protegido", "Estes processos são essenciais e foram desmarcados:\n"
                                   + ", ".join(i.values[0] for i in crit), parent=self)
            for i in crit:
                i.checked = False
            self.render_rows()
            return False
        return True

    def confirm_text(self, items, to_trash):
        names = ", ".join(i.values[0] for i in items[:12])
        return (f"Finalizar {len(items)} programa(s)?\n{names}\n\n"
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
        return done, errors, freed

    def success_text(self, done, freed):
        return f"{len(done)} programa(s) finalizado(s) · ~{fmt_size(freed)} de RAM liberados"

    def after_action(self, done, errors, freed):
        super().after_action(done, errors, freed)
        self.start_scan()

    def trim(self):
        before = memory_info()[1]

        def job(c, p):
            p("Liberando memória ociosa dos processos…")
            return trim_memory()

        def done(n):
            after = memory_info()[1]
            self.app.toast(f"Memória ociosa liberada de {n} processos · {fmt_size(max(0, before - after))} recuperados")
            self.start_scan()

        self._set_busy(True)
        self.run_bg(job, done, "Liberando memória…", on_finally=lambda: self._set_busy(False))


class StartupPage(ResultsPage):
    key, icon = "startup", "power"
    title = "Inicialização"
    subtitle = ("Programas que abrem sozinhos quando o computador liga. Cada um consome RAM e deixa o boot "
                "mais lento. Desativar não desinstala nada e pode ser desfeito quando quiser.")
    columns = [("Programa", 260, "w"), ("Situação", 110, "center"), ("Origem", 210, "w"), ("Comando", 520, "w")]
    scan_label = "Atualizar"
    action_label = "Desativar selecionados"
    action_style = "Primary.TButton"
    uses_trash = False
    auto_scan = True

    def build_actions(self, f):
        ttk.Button(f, text="Ativar selecionados", command=lambda: self.toggle(True)).pack(side="left")

    def scan_job(self, p, cancel, progress):
        return scan_startup(cancel, progress)

    def row_tags(self, item):
        return ("ok",) if item.data["enabled"] else ("muted",)

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
        ok = len(items) - len(errors)
        if ok:
            self.app.toast(f"{ok} item(ns) {'ativado(s)' if enable else 'desativado(s)'} na inicialização")
        self.start_scan()
