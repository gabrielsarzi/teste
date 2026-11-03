"""Páginas “Instalar programas” (kit pós-formatação) e “Atualizar programas” (winget)."""
from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .apps import (CATALOG, CATEGORIES, BY_ID, available, install_app, installed_ids, list_upgrades,
                   load_selection, make_import_json, selection_json, unavailable_reason, upgrade_app,
                   write_bat, write_text)
from .pages import BackgroundMixin, Page, PlaceholderEntry, ResultsPage
from .utils import IS_WIN, Item, log
from .widgets import Icon, ScrollFrame

ALL_CATS = "Todas as categorias"
SEARCH_PH = "Buscar programa…"

# estado de cada programa -> (texto do selo, estilo)
BADGES = {
    "installed": ("Instalado", "BadgeOk.TLabel"),
    "queued": ("Na fila", "Badge.TLabel"),
    "running": ("Instalando…", "BadgeWarn.TLabel"),
    "ok": ("Concluído ✓", "BadgeOk.TLabel"),
    "error": ("Erro", "AppsErr.TLabel"),
}


def _styles(t):
    """Estilos extras usados só nestas páginas (derivados da paleta atual)."""
    c, px = t.c, t.px
    st = ttk.Style()
    st.configure("AppsErr.TLabel", background=c["danger_soft"], foreground=c["danger"], font=t.f_small,
                 padding=(px(8), px(2)))
    st.configure("AppTile.Card.TCheckbutton", font=t.f_bold)
    st.configure("AppSel.TFrame", background=c["surface"], relief="solid", borderwidth=1,
                 bordercolor=c["accent"], lightcolor=c["accent"], darkcolor=c["accent"])
    st.configure("Link.TLabel", background=c["bg"], foreground=c["accent"], font=t.f_small)
    st.configure("Notice.TFrame", background=c["warning_soft"])
    st.configure("Notice.TLabel", background=c["warning_soft"], foreground=c["text"], font=t.f_base)
    st.configure("Notice.Bold.TLabel", background=c["warning_soft"], foreground=c["text"], font=t.f_bold)


def _notice(master, t, title, text):
    """Faixa de aviso (fundo amarelo-claro) com ícone."""
    f = ttk.Frame(master, style="Notice.TFrame", padding=(t.px(14), t.px(10)))
    Icon(f, "info", t.px(20), t.c["warning"], t.c["warning_soft"], 2.0).pack(side="left", anchor="n",
                                                                            padx=(0, t.px(10)))
    box = ttk.Frame(f, style="Notice.TFrame")
    box.pack(side="left", fill="x", expand=True)
    ttk.Label(box, text=title, style="Notice.Bold.TLabel").pack(anchor="w")
    lbl = ttk.Label(box, text=text, style="Notice.TLabel", justify="left", wraplength=t.px(760))
    lbl.pack(anchor="w")
    box.bind("<Configure>", lambda e: lbl.config(wraplength=max(200, e.width - 4)))
    return f


# =================================================================== INSTALAR PROGRAMAS
class InstallAppsPage(BackgroundMixin, Page):
    key, icon, title = "install", "download", "Instalar programas"
    subtitle = ("Escolha seus programas e instale todos de uma vez — perfeito depois de formatar. "
                "Cada um vem do site oficial pelo winget, o instalador de pacotes da Microsoft. "
                "Você também pode gerar um instalador (.bat) para levar a outro PC.")

    def __init__(self, master, app):
        super().__init__(master, app)
        t = self.t
        _styles(t)
        self.cancel = threading.Event()
        self.busy = False
        self.ok = available()
        self._progress = ""
        self.app_state: dict[str, str] = {}      # id -> installed/queued/running/ok/error
        self.errors: dict[str, str] = {}
        self._shown_state: dict[str, str] = {}
        self._done = 0
        self._checked_installed = False
        self._cols = 0
        self._wrap = 0
        self._filter_job = None
        self._save_job = None
        self.extra_ids: list[str] = []       # IDs carregados que não estão no catálogo

        # busca (canto superior direito, como nas outras listas)
        sbox = ttk.Frame(self.header_right)
        sbox.pack(side="right", anchor="s", pady=(t.px(10), 0))
        Icon(sbox, "search", t.px(16), t.c["muted"], t.c["bg"]).pack(side="left", padx=(0, t.px(6)))
        self.search = tk.StringVar()
        PlaceholderEntry(sbox, self.search, SEARCH_PH, width=24).pack(side="left")
        self.search.trace_add("write", lambda *a: self._schedule_filter())

        if not self.ok:
            _notice(self.body, t, "Instalação automática indisponível neste computador",
                    unavailable_reason()).pack(fill="x", pady=(0, t.px(12)))

        # barra de opções
        bar = ttk.Frame(self.body, style="Card.TFrame", padding=(t.px(14), t.px(10)))
        bar.pack(fill="x")
        ttk.Label(bar, text="Categoria", style="Card.TLabel").pack(side="left")
        self.cat = tk.StringVar(value=ALL_CATS)
        cb = ttk.Combobox(bar, textvariable=self.cat, values=[ALL_CATS] + CATEGORIES, state="readonly", width=24)
        cb.pack(side="left", padx=(t.px(8), t.px(16)))
        cb.bind("<<ComboboxSelected>>", lambda e: self.relayout())
        self.only_sel = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Só os selecionados", variable=self.only_sel, style="Card.TCheckbutton",
                        command=self.relayout).pack(side="left", padx=(0, t.px(16)))
        self.hide_inst = tk.BooleanVar(value=False)
        self.chk_hide = ttk.Checkbutton(bar, text="Ocultar já instalados", variable=self.hide_inst,
                                        style="Card.TCheckbutton", command=self.relayout)
        if self.ok:
            self.chk_hide.pack(side="left")

        # progresso
        prog = ttk.Frame(self.body)
        prog.pack(fill="x", pady=(t.px(10), t.px(6)))
        self.pbar = ttk.Progressbar(prog, mode="determinate", style="Thin.Horizontal.TProgressbar")
        if self.ok:
            self.btn_recheck = ttk.Label(prog, text="Verificar de novo", style="Link.TLabel", cursor="hand2")
            self.btn_recheck.pack(side="right")
            self.btn_recheck.bind("<Button-1>", lambda e: self.check_installed())
        self.lbl_inst = ttk.Label(prog, text="", style="Small.TLabel")
        self.lbl_inst.pack(side="right", padx=(0, t.px(10)))
        self.lbl_progress = ttk.Label(prog, text="", style="Small.TLabel")
        self.lbl_progress.pack(side="left")

        # rodapé (empacotado antes da lista para nunca ser cortado)
        foot = ttk.Frame(self.body)
        foot.pack(side="bottom", fill="x", pady=(t.px(12), 0))
        self.btn_install = ttk.Button(foot, text="Instalar selecionados", style="Primary.TButton",
                                      command=self.install_selected)
        self.btn_install.pack(side="right")
        self.btn_stop = ttk.Button(foot, text="Parar", command=self.stop)
        self.btn_bat = ttk.Button(foot, text="Gerar instalador…", command=self.generate)
        self.btn_bat.pack(side="right", padx=(0, t.px(8)))
        self.lbl_sel = ttk.Label(foot, text="", style="Bold.TLabel")
        self.lbl_sel.pack(side="right", padx=t.px(14))
        self.list_menu = tk.Menu(self, tearoff=0)
        self.list_menu.add_command(label="Salvar seleção…", command=self.save_selection)
        self.list_menu.add_command(label="Carregar seleção…", command=self.load_selection)
        self.list_menu.add_separator()
        self.list_menu.add_command(label="Limpar seleção", command=self.clear_selection)
        self.btn_list = ttk.Button(foot, text="Salvar / abrir lista  ▾", command=self._popup_list_menu)
        self.btn_list.pack(side="left")

        # catálogo
        self.sf = ScrollFrame(self.body, t)
        self.sf.pack(fill="both", expand=True)
        self.vars: dict[str, tk.BooleanVar] = {}
        self.tiles: dict[str, dict] = {}
        self.sections: dict[str, dict] = {}
        for cat in CATEGORIES:
            self._build_section(cat)
        self.lbl_empty = ttk.Label(self.sf.inner, text="Nenhum programa encontrado para essa busca.",
                                   style="Muted.TLabel")
        self.sf.canvas.bind("<Configure>", self._on_resize, add="+")

        saved = app.settings.get("apps_selection") or []
        self._apply_ids(saved if isinstance(saved, list) else [], replace=True, save=False)
        self.relayout()
        self.update_count()

    # ---------------------------------------------------------------- construção
    def _build_section(self, cat):
        t = self.t
        sec = ttk.Frame(self.sf.inner)
        head = ttk.Frame(sec)
        head.pack(fill="x", pady=(t.px(4), t.px(8)))
        ttk.Label(head, text=cat, style="H3.TLabel").pack(side="left")
        cnt = ttk.Label(head, text="", style="Small.TLabel")
        cnt.pack(side="left", padx=(t.px(8), 0), pady=(t.px(3), 0))
        link = ttk.Label(head, text="Marcar todos", style="Link.TLabel", cursor="hand2")
        link.pack(side="right", padx=(0, t.px(4)))
        link.bind("<Button-1>", lambda e, c=cat: self.toggle_category(c))
        grid = ttk.Frame(sec)
        grid.pack(fill="x")
        self.sections[cat] = {"frame": sec, "grid": grid, "count": cnt, "link": link}
        for a in [a for a in CATALOG if a.category == cat]:
            self._build_tile(grid, a)

    def _build_tile(self, grid, a):
        t = self.t
        var = tk.BooleanVar(value=False)
        self.vars[a.id] = var
        f = ttk.Frame(grid, style="Card.TFrame", padding=(t.px(12), t.px(10), t.px(12), t.px(10)))
        top = ttk.Frame(f, style="Flat.TFrame")
        top.pack(fill="x")
        chk = ttk.Checkbutton(top, text=a.name, variable=var, style="AppTile.Card.TCheckbutton",
                              command=lambda i=a.id: self._on_toggle(i))
        chk.pack(side="left")
        badge = ttk.Label(top, text="", style="Badge.TLabel")
        desc = ttk.Label(f, text=a.desc, style="Card.Small.TLabel", justify="left", wraplength=t.px(240))
        desc.pack(anchor="w", fill="x", pady=(t.px(4), 0), padx=(t.px(22), 0))
        for w in (f, top, desc):
            w.bind("<Button-1>", lambda e, i=a.id: self._click_tile(i))
        self.tiles[a.id] = {"frame": f, "badge": badge, "desc": desc, "app": a}

    # ---------------------------------------------------------------- layout / filtro
    def _on_resize(self, e):
        w = e.width
        cols = 3 if w >= self.t.px(860) else 2 if w >= self.t.px(520) else 1
        gap = self.t.px(10)
        wrap = max(self.t.px(140), int((w - gap * (cols - 1)) / cols) - self.t.px(52))
        if abs(wrap - self._wrap) > 6:
            self._wrap = wrap
            for tile in self.tiles.values():
                tile["desc"].config(wraplength=wrap)
        if cols != self._cols:
            self._cols = cols
            self.relayout()

    def _schedule_filter(self):
        if self._filter_job:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(200, self.relayout)

    def _query(self):
        q = self.search.get().strip().lower()
        return "" if q == SEARCH_PH.lower() else q

    def _visible(self, a) -> bool:
        cat = self.cat.get()
        if cat != ALL_CATS and a.category != cat:
            return False
        if self.only_sel.get() and not self.vars[a.id].get():
            return False
        if self.hide_inst.get() and self.app_state.get(a.id) == "installed" and not self.vars[a.id].get():
            return False
        q = self._query()
        return not q or any(q in s.lower() for s in (a.name, a.desc, a.id, a.category))

    def relayout(self):
        self._filter_job = None
        cols = self._cols or 3
        gap = self.t.px(10)
        any_visible = False
        for sec in self.sections.values():
            sec["frame"].pack_forget()
        self.lbl_empty.pack_forget()
        for cat in CATEGORIES:
            sec = self.sections[cat]
            grid = sec["grid"]
            for c in range(3):
                grid.columnconfigure(c, weight=1 if c < cols else 0, uniform="tile" if c < cols else "")
            n = 0
            members = [a for a in CATALOG if a.category == cat]
            for a in members:
                tile = self.tiles[a.id]["frame"]
                if self._visible(a):
                    r, c = divmod(n, cols)
                    tile.grid(row=r, column=c, sticky="nsew",
                              padx=(0 if c == 0 else gap // 2, 0 if c == cols - 1 else gap // 2), pady=(0, gap))
                    n += 1
                else:
                    tile.grid_forget()
            if n:
                any_visible = True
                sec["frame"].pack(fill="x", pady=(0, self.t.px(10)))
                self._update_section_head(cat)
        if not any_visible:
            self.lbl_empty.pack(pady=self.t.px(40))
        self.sf.canvas.yview_moveto(0)

    def _update_section_head(self, cat):
        sec = self.sections[cat]
        members = [a for a in CATALOG if a.category == cat]
        sel = sum(1 for a in members if self.vars[a.id].get())
        txt = f"{len(members)} programas" + (f"  ·  {sel} selecionado(s)" if sel else "")
        sec["count"].config(text=txt)
        sec["link"].config(text="Desmarcar todos" if sel == len(members) else "Marcar todos")

    # ---------------------------------------------------------------- seleção
    def _click_tile(self, app_id):
        if self.busy:
            return
        v = self.vars[app_id]
        v.set(not v.get())
        self._on_toggle(app_id)

    def _on_toggle(self, app_id):
        if self.busy:  # durante a instalação a lista fica congelada
            self.vars[app_id].set(not self.vars[app_id].get())
            return
        self._paint_tile(app_id)
        self._update_section_head(BY_ID[app_id.lower()].category)
        self.update_count()
        self._schedule_save()

    def toggle_category(self, cat):
        if self.busy:
            return
        members = [a for a in CATALOG if a.category == cat and self._visible(a)] or \
                  [a for a in CATALOG if a.category == cat]
        state = not all(self.vars[a.id].get() for a in members)
        for a in members:
            self.vars[a.id].set(state)
            self._paint_tile(a.id)
        self._update_section_head(cat)
        self.update_count()
        self._schedule_save()
        if self.only_sel.get():
            self.relayout()

    def selected_ids(self) -> list[str]:
        return [a.id for a in CATALOG if self.vars[a.id].get()] + list(self.extra_ids)

    def update_count(self):
        n = len(self.selected_ids())
        extra = f" (+{len(self.extra_ids)} fora do catálogo)" if self.extra_ids else ""
        self.lbl_sel.config(text=(f"{n} selecionado(s){extra}" if n else "Nenhum selecionado"))

    def _schedule_save(self):
        if self._save_job:
            self.after_cancel(self._save_job)
        self._save_job = self.after(800, lambda: self.app.settings.set("apps_selection", self.selected_ids()))

    def _apply_ids(self, ids, replace=True, save=True):
        known = {i.lower() for i in ids}
        if replace:
            self.extra_ids = []
        for a in CATALOG:
            if replace:
                self.vars[a.id].set(a.id.lower() in known)
            elif a.id.lower() in known:
                self.vars[a.id].set(True)
        for i in ids:
            if i.lower() not in BY_ID and i not in self.extra_ids:
                self.extra_ids.append(i)
        for a in CATALOG:
            self._paint_tile(a.id)
        for cat in CATEGORIES:
            self._update_section_head(cat)
        self.update_count()
        if save:
            self._schedule_save()

    def _popup_list_menu(self):
        b = self.btn_list
        try:
            self.list_menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() - self.list_menu.winfo_reqheight())
        finally:
            self.list_menu.grab_release()

    def clear_selection(self):
        if not self.busy:
            self._apply_ids([], replace=True)
            if self.only_sel.get():
                self.relayout()

    def save_selection(self):
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo("Salvar seleção", "Selecione pelo menos um programa.", parent=self)
            return
        path = filedialog.asksaveasfilename(parent=self, title="Salvar seleção", defaultextension=".json",
                                            initialfile="Meus programas - LimpaOne.json",
                                            filetypes=[("Seleção do LimpaOne", "*.json")])
        if not path:
            return
        try:
            write_text(path, selection_json(ids))
        except OSError as e:
            messagebox.showerror("Salvar seleção", f"Não foi possível salvar o arquivo.\n\n{e}", parent=self)
            return
        self.app.toast(f"Seleção com {len(ids)} programa(s) salva em {os.path.basename(path)}")

    def load_selection(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self, title="Carregar seleção",
                                          filetypes=[("Seleção do LimpaOne ou winget export", "*.json"),
                                                     ("Todos os arquivos", "*.*")])
        if not path:
            return
        try:
            ids = load_selection(path)
        except (OSError, ValueError) as e:
            messagebox.showerror("Carregar seleção", f"Arquivo inválido.\n\n{e}", parent=self)
            return
        if not ids:
            messagebox.showwarning("Carregar seleção", "O arquivo não contém nenhum programa.", parent=self)
            return
        self._apply_ids(ids, replace=True)
        self.relayout()
        extra = len(self.extra_ids)
        self.app.toast(f"{len(ids)} programa(s) carregado(s)" + (f" · {extra} fora do catálogo" if extra else ""))

    # ---------------------------------------------------------------- selos de estado
    def _paint_tile(self, app_id):
        tile = self.tiles.get(app_id)
        if not tile:
            return
        tile["frame"].configure(style="AppSel.TFrame" if self.vars[app_id].get() else "Card.TFrame")
        st = self.app_state.get(app_id, "")
        if self._shown_state.get(app_id) == st:
            return
        self._shown_state[app_id] = st
        b = tile["badge"]
        if st in BADGES:
            text, style = BADGES[st]
            b.config(text=text, style=style)
            b.pack(side="right", padx=(self.t.px(6), 0))
        else:
            b.pack_forget()

    def set_installed(self, ids):
        for i in ids:
            if self.app_state.get(i) not in ("ok", "queued", "running", "error"):
                self.app_state[i] = "installed"
        for a in CATALOG:
            self._paint_tile(a.id)
        n = sum(1 for v in self.app_state.values() if v in ("installed", "ok"))
        self.lbl_inst.config(text=f"{n} do catálogo já instalado(s) neste PC" if n else
                             "Nenhum programa do catálogo instalado ainda")
        if self.hide_inst.get():
            self.relayout()

    # ---------------------------------------------------------------- segundo plano
    def on_show(self):
        if self.ok and not self._checked_installed and not self.busy:
            self.check_installed()

    def busy_now(self):
        return self.busy

    def show_progress(self, text):
        self.lbl_progress.config(text=text)
        if self.busy:
            self.pbar.config(value=self._done)
        for i in list(self.app_state):
            if self._shown_state.get(i) != self.app_state[i]:
                self._paint_tile(i)

    def _set_busy(self, busy, installing=False):
        self.busy = busy
        st = "disabled" if busy else "normal"
        for b in (self.btn_install, self.btn_bat, self.btn_list):
            b.config(state=st)
        if installing and busy:
            self.btn_bat.pack_forget()
            self.btn_stop.pack(side="right", padx=(0, self.t.px(8)), after=self.btn_install)
            self.pbar.pack(side="bottom", fill="x", before=self.pbar.master.pack_slaves()[0], pady=(self.t.px(4), 0))
        elif not busy:
            self.btn_stop.pack_forget()
            self.btn_bat.pack(side="right", padx=(0, self.t.px(8)), after=self.btn_install)
            self.pbar.pack_forget()
        self.app.set_nav_busy(self.key, busy)

    def stop(self):
        self.cancel.set()
        self.show_progress("Parando depois do programa atual…")

    def check_installed(self):
        if self.busy or not self.ok:
            return
        self._checked_installed = True
        self.lbl_inst.config(text="Verificando o que já está instalado…")
        for i, s in list(self.app_state.items()):
            if s == "installed":
                del self.app_state[i]

        def job(cancel, progress):
            progress("Verificando programas instalados (pode levar alguns segundos)…")
            return installed_ids(progress)

        def done(ids):
            self.set_installed(ids or set())
            self.show_progress("")

        self._set_busy(True)
        self.run_bg(job, done, "Verificando programas instalados…", on_finally=lambda: self._set_busy(False))

    # ---------------------------------------------------------------- instalar
    def install_selected(self):
        if self.busy:
            return
        if not self.ok:
            messagebox.showinfo("Instalar programas", unavailable_reason() +
                                "\n\nUse “Gerar instalador…” para criar um arquivo .bat.", parent=self)
            return
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo("Nada selecionado", "Marque os programas que deseja instalar.", parent=self)
            return
        names = [self._app_name(i) for i in ids]
        lst = "\n".join(f"• {n}" for n in names[:14]) + (f"\n… e mais {len(names) - 14}" if len(names) > 14 else "")
        if not messagebox.askyesno(
                "Instalar programas",
                f"Instalar {len(ids)} programa(s), um de cada vez?\n\n{lst}\n\n"
                "Os programas são baixados dos sites oficiais. O Windows pode pedir permissão de "
                "administrador para alguns deles. Os que já estiverem instalados serão pulados.",
                parent=self):
            return
        for i in ids:
            self.app_state[i] = "queued"
            self.errors.pop(i, None)
        self._done = 0
        self.pbar.config(maximum=len(ids), value=0)

        def job(cancel, progress):
            ok, failed = [], []
            for n, i in enumerate(ids, 1):
                if cancel.is_set():
                    break
                self.app_state[i] = "running"
                progress(f"Instalando {n} de {len(ids)}: {self._app_name(i)}… (feche os programas que forem abrir)")
                try:
                    success, msg = install_app(i)
                except Exception as e:  # noqa: BLE001
                    success, msg = False, str(e)
                self.app_state[i] = "ok" if success else "error"
                (ok if success else failed).append((i, msg))
                if not success:
                    self.errors[i] = msg
                self._done = n
            for i in ids:
                if self.app_state.get(i) == "queued":
                    del self.app_state[i]
            return ok, failed

        self._set_busy(True, installing=True)
        self.run_bg(job, self._after_install, "Preparando…", on_finally=lambda: self._set_busy(False))

    def _after_install(self, res):
        ok, failed = res or ([], [])
        self.show_progress(f"{len(ok)} instalado(s), {len(failed)} com erro." if ok or failed else "")
        n = sum(1 for v in self.app_state.values() if v in ("installed", "ok"))
        self.lbl_inst.config(text=f"{n} do catálogo já instalado(s) neste PC")
        if ok:
            self.app.toast(f"{len(ok)} programa(s) instalado(s) com sucesso")
        if failed:
            msg = "\n".join(f"• {self._app_name(i)}: {m}" for i, m in failed[:12])
            if len(failed) > 12:
                msg += f"\n… e mais {len(failed) - 12}."
            messagebox.showwarning("Alguns programas não foram instalados",
                                   f"{len(failed)} programa(s) falharam:\n\n{msg}\n\n"
                                   "Verifique a internet e tente de novo. Detalhes no histórico do LimpaOne.",
                                   parent=self)

    @staticmethod
    def _app_name(app_id):
        a = BY_ID.get(app_id.lower())
        return a.name if a else app_id

    # ---------------------------------------------------------------- gerar kit
    def generate(self):
        ids = self.selected_ids()
        if not ids:
            messagebox.showinfo("Gerar instalador", "Selecione os programas que o instalador deve conter.",
                                parent=self)
            return
        path = filedialog.asksaveasfilename(parent=self, title="Salvar instalador", defaultextension=".bat",
                                            initialfile="Kit pos-formatacao - LimpaOne.bat",
                                            filetypes=[("Arquivo em lotes do Windows", "*.bat")])
        if not path:
            return
        also_json = messagebox.askyesno(
            "Gerar instalador",
            "Também salvar um arquivo .json para o comando “winget import”?\n\n"
            "Ele contém a mesma lista e serve para quem prefere instalar pelo terminal:\n"
            "winget import -i arquivo.json", parent=self)
        try:
            write_bat(path, [(i, self._app_name(i)) for i in ids])
            jpath = None
            if also_json:
                jpath = os.path.splitext(path)[0] + ".json"
                write_text(jpath, make_import_json(ids))
        except OSError as e:
            messagebox.showerror("Gerar instalador", f"Não foi possível salvar.\n\n{e}", parent=self)
            return
        log(f"KIT GERADO {path} ({len(ids)} programas)")
        files = os.path.basename(path) + (f" e {os.path.basename(jpath)}" if jpath else "")
        self.app.toast(f"Instalador com {len(ids)} programa(s) salvo: {files}")


# =================================================================== ATUALIZAR PROGRAMAS
class UpdateAppsPage(ResultsPage):
    key, icon = "updates", "refresh"
    title = "Atualizar programas"
    subtitle = ("Programas com versão nova disponível, segundo o winget. Atualizar mantém suas configurações "
                "e corrige falhas de segurança. Feche os programas antes de atualizar.")
    columns = [("Programa", 240, "w"), ("Versão atual", 110, "w"), ("Nova versão", 110, "w"),
               ("ID", 220, "w"), ("Situação", 180, "w")]
    scan_label = "Procurar atualizações"
    action_label = "Atualizar selecionados"
    action_style = "Primary.TButton"
    uses_trash = False
    show_open = False
    auto_scan = True
    empty_text = "Clique em “Procurar atualizações” para ver o que pode ser atualizado."

    def __init__(self, master, app):
        self.ok = available()
        super().__init__(master, app)
        if not self.ok:
            self.empty.config(text=self.unavailable_text())
            self.empty.configure(wraplength=self.t.px(520))
            self.btn_scan.config(state="disabled")
            self.btn_action.config(state="disabled")

    @staticmethod
    def unavailable_text():
        if not IS_WIN:
            return ("Disponível no Windows 10/11 com o winget.\n"
                    "Neste sistema, atualize os programas pela loja de aplicativos ou pelo gerenciador de pacotes.")
        return unavailable_reason()

    def build_options(self, f):
        self.unknown = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Mostrar programas com versão desconhecida", variable=self.unknown,
                        style="Card.TCheckbutton").pack(side="left")

    def get_params(self):
        return {"unknown": self.unknown.get()}

    def on_show(self):
        if self.ok:
            super().on_show()

    def start_scan(self):
        if not self.ok:
            messagebox.showinfo(self.title, self.unavailable_text(), parent=self)
            return
        super().start_scan()

    def scan_job(self, p, cancel, progress):
        progress("Consultando o winget (pode levar até um minuto)…")
        return [self.make_item(r) for r in list_upgrades(p["unknown"])]

    @staticmethod
    def make_item(r: dict) -> Item:
        unknown = bool(r.get("unknown"))
        name = r.get("name") or r["id"]
        cur = "Desconhecida" if unknown and not (r.get("version") or "").startswith("<") else r.get("version", "")
        status = "Versão atual desconhecida" if unknown else "Disponível"
        return Item(path=r["id"], values=(name, cur, r.get("available", ""), r["id"], status),
                    raw=(name.lower(), cur, r.get("available", ""), r["id"].lower(), status),
                    kind="upgrade", checked=not unknown, data=dict(r))

    def row_tags(self, item):
        st = item.data.get("state")
        if st == "error":
            return ("danger",)
        if st == "ok":
            return ("ok",)
        if st == "running":
            return ("warn",)
        return ("muted",) if item.data.get("unknown") else ()

    def populate(self, items):
        super().populate(items)
        if self._scanned:
            n = len(self.all_items)
            unk = sum(1 for i in self.all_items if i.data.get("unknown"))
            txt = (f"{n} atualização(ões) disponível(is)" if n else "Nenhuma atualização disponível")
            if unk:
                txt += f" · {unk} com versão atual desconhecida (desmarcados — confira antes de atualizar)"
            self._progress = txt
            self.show_progress(txt)

    def render_rows(self):
        super().render_rows()
        if not self.all_items and self._scanned and self.ok:
            self.empty.config(text="Tudo em dia! ✓\nNenhuma atualização disponível.")

    def _set_status(self, it: Item, state: str, text: str):
        it.data["state"] = state
        it.values = it.values[:4] + (text,)

    def show_progress(self, text):
        super().show_progress(text)
        for iid, it in self.items.items():
            if it.data.get("_shown") != it.values[4]:
                it.data["_shown"] = it.values[4]
                self._rerender(iid)

    def confirm_text(self, items, to_trash):
        names = "\n".join(f"• {i.values[0]}  ({i.values[1]} → {i.values[2]})" for i in items[:14])
        more = f"\n… e mais {len(items) - 14}" if len(items) > 14 else ""
        return (f"Atualizar {len(items)} programa(s)?\n\n{names}{more}\n\n"
                "Feche esses programas antes de continuar. O Windows pode pedir permissão de administrador.")

    def perform(self, items, to_trash, progress):
        done, errors = [], []
        for it in items:
            self._set_status(it, "queued", "Na fila")
        for n, it in enumerate(items, 1):
            if self.cancel.is_set():
                break
            self._set_status(it, "running", "Atualizando…")
            progress(f"Atualizando {n} de {len(items)}: {it.values[0]}…")
            try:
                ok, msg = upgrade_app(it.path, unknown=bool(it.data.get("unknown")))
            except Exception as e:  # noqa: BLE001
                ok, msg = False, str(e)
            if ok:
                self._set_status(it, "ok", msg if msg != "Concluído" else "Atualizado ✓")
                done.append(it)
            else:
                self._set_status(it, "error", f"Erro: {msg}")
                errors.append((it.values[0], msg))
        for it in items:
            if it.data.get("state") == "queued":
                self._set_status(it, "", "Disponível")
        return done, errors, 0

    def success_text(self, done, freed):
        return f"{len(done)} programa(s) atualizado(s)"
