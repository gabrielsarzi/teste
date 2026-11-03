"""Janela principal do LimpaPC: menu lateral, Painel, Mapa do disco, Ferramentas, Configurações e Sobre."""
from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import APP_NAME, HOMEPAGE, __version__
from .analyzer import CATEGORY_NAMES, analyze, remove_size
from .pages import (BackgroundMixin, DuplicatesPage, JunkPage, LargeFilesPage, LeftoversPage, OldFilesPage, Page,
                    ProcessesPage, ProgramsPage, ResultsPage, StartupPage)
from .recovery_pages import RecoverPage, TrashPage
from .scanners import set_exclusions
from .settings import Settings
from .system import empty_recycle_bin, recycle_bin_info
from .theme import CATEGORY_COLORS, Theme, draw_icon, draw_logo, set_dark_titlebar
from .tools import available_tools, run_tool
from .update import check_for_update
from .utils import (IS_WIN, app_data_dir, delete_path, disks, fixed_drives, fmt_date, fmt_size, home, is_admin,
                    is_protected, log, memory_info, open_location, open_uri, relaunch_as_admin)
from .widgets import (CategoryBars, Icon, ListEditor, NavGroup, NavItem, RingGauge, ScrollFrame, Toast, card,
                      install_wheel, register_scroll)


def _soft_icon(master, t, name, size=40, bg_key="surface", fg=None, soft=None):
    """Ícone dentro de um círculo suave (usado em cards)."""
    c = t.c
    s = t.px(size)
    cv = tk.Canvas(master, width=s, height=s, bg=c[bg_key], highlightthickness=0, bd=0)
    cv.create_oval(0, 0, s, s, fill=soft or c["accent_soft"], outline="")
    draw_icon(cv, name, s * 0.25, s * 0.25, s * 0.5, fg or c["accent"], 2.0, bg=soft or c["accent_soft"])
    return cv


def health_score(disk_pct, ram_pct, junk, recycle, startup_on, dup_waste):
    score = 100
    score -= 30 if disk_pct > 0.92 else 18 if disk_pct > 0.85 else 8 if disk_pct > 0.75 else 0
    score -= 15 if ram_pct > 0.88 else 8 if ram_pct > 0.75 else 0
    score -= min(25, int(junk / (1 << 30) * 5))
    score -= 5 if recycle > (1 << 30) else 0
    score -= 10 if startup_on > 10 else 5 if startup_on > 5 else 0
    score -= 5 if dup_waste > (1 << 30) else 0
    return max(5, score)


def score_label(s):
    return "Ótimo" if s >= 85 else "Bom" if s >= 70 else "Regular" if s >= 50 else "Precisa de atenção"


# =================================================================== PAINEL
class DashboardPage(BackgroundMixin, Page):
    key, icon, title = "dashboard", "home", "Painel"
    subtitle = "Visão geral do seu computador. Faça uma análise completa para descobrir quanto espaço dá para liberar."
    STEPS = [("junk", "Procurando lixo e cache"), ("dups", "Procurando arquivos repetidos"),
             ("large", "Procurando arquivos grandes"), ("old", "Procurando arquivos antigos"),
             ("leftovers", "Procurando restos de programas"), ("programs", "Verificando programas"),
             ("startup", "Verificando a inicialização")]

    def __init__(self, master, app):
        super().__init__(master, app)
        t = self.t
        self.busy = False
        self.cancel = threading.Event()
        self.summary = app.settings.get("last_scan") or None
        sf = ScrollFrame(self.body, t)
        sf.pack(fill="both", expand=True)
        root = sf.inner
        root.columnconfigure((0, 1, 2), weight=1, uniform="col")

        # ---- destaque
        hero = card(root, t, 22)
        hero.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.score = RingGauge(hero, t, size=148, thickness=13)
        self.score.pack(side="left", padx=(0, t.px(26)))
        txt = ttk.Frame(hero, style="Flat.TFrame")
        txt.pack(side="left", fill="both", expand=True)
        self.h_title = ttk.Label(txt, text="", style="Card.H2.TLabel")
        self.h_title.pack(anchor="w")
        self.h_desc = ttk.Label(txt, text="", style="Card.Muted.TLabel", wraplength=t.px(560), justify="left")
        self.h_desc.pack(anchor="w", pady=(t.px(6), t.px(14)))
        btns = ttk.Frame(txt, style="Flat.TFrame")
        btns.pack(anchor="w")
        self.btn_scan = ttk.Button(btns, text="Analisar agora", style="Big.Primary.TButton", command=self.smart_scan)
        self.btn_scan.pack(side="left")
        self.btn_clean = ttk.Button(btns, text="Limpar recomendado", style="Big.Primary.TButton",
                                    command=self.clean_recommended)
        self.btn_stop = ttk.Button(btns, text="Parar", command=lambda: self.cancel.set())
        self.prog = ttk.Progressbar(txt, mode="determinate", maximum=len(self.STEPS))
        self.lbl_prog = ttk.Label(txt, text="", style="Card.Small.TLabel")

        # ---- três cards de status
        self.disk_card = self._stat_card(root, 1, 0, "Disco do sistema")
        self.ram_card = self._stat_card(root, 1, 1, "Memória RAM", ("Ver programas", lambda: app.show("ram")))
        self.bin_card = self._stat_card(root, 1, 2, "Lixeira", ("Esvaziar", self.empty_bin))

        # ---- resultados
        self.res = card(root, t, 20)
        self.res.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(t.px(16), 0))
        # ---- discos
        self.disks = card(root, t, 20)
        self.disks.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(t.px(16), t.px(4)))
        self.refresh()

    def _stat_card(self, root, r, col, title, action=None):
        t = self.t
        f = card(root, t, 18)
        f.grid(row=r, column=col, sticky="nsew", pady=(t.px(16), 0),
               padx=(0 if col == 0 else t.px(8), 0 if col == 2 else t.px(8)))
        top = ttk.Frame(f, style="Flat.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text=title, style="Card.Muted.TLabel").pack(side="left")
        if action:
            ttk.Button(top, text=action[0], style="Ghost.TButton", command=action[1]).pack(side="right")
        body = ttk.Frame(f, style="Flat.TFrame")
        body.pack(fill="x", pady=(t.px(8), 0))
        f.gauge = RingGauge(body, t, size=88, thickness=9)
        f.gauge.pack(side="left")
        f.big = ttk.Label(body, text="—", style="Card.H2.TLabel")
        f.big.pack(anchor="w", padx=(t.px(14), 0), pady=(t.px(14), 0))
        f.small = ttk.Label(body, text="", style="Card.Muted.TLabel")
        f.small.pack(anchor="w", padx=(t.px(14), 0))
        return f

    def _color(self, pct):
        c = self.t.c
        return c["danger"] if pct > .9 else c["warning"] if pct > .75 else c["success"]

    def refresh(self):
        """Atualiza discos, RAM e Lixeira (rápido) e redesenha o resumo."""
        t = self.t
        sysdrive = (os.environ.get("SystemDrive", "C:") + "\\") if IS_WIN else "/"
        dl = disks()
        main = next((d for d in dl if d[0].lower() == sysdrive.lower()), dl[0] if dl else None)
        if main:
            _, total, used, free = main
            pct = used / total if total else 0
            self.disk_card.gauge.set(pct, f"{pct * 100:.0f}%", "", self._color(pct))
            self.disk_card.big.config(text=fmt_size(free))
            self.disk_card.small.config(text=f"livres de {fmt_size(total)} ({main[0]})")
        total, used = memory_info()
        if total:
            pct = used / total
            self.ram_card.gauge.set(pct, f"{pct * 100:.0f}%", "", self._color(pct))
            self.ram_card.big.config(text=fmt_size(used))
            self.ram_card.small.config(text=f"em uso de {fmt_size(total)}")

        def load_bin():
            size, n = recycle_bin_info()
            try:
                self.after(0, lambda: self._set_bin(size, n) if self.winfo_exists() else None)
            except (tk.TclError, RuntimeError):
                pass
        threading.Thread(target=load_bin, daemon=True).start()

        for w in self.disks.winfo_children():
            w.destroy()
        ttk.Label(self.disks, text="Unidades de armazenamento", style="Card.H3.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, t.px(10)))
        for i, (mount, tot, used, free) in enumerate(dl, 1):
            pct = used / tot if tot else 0
            ttk.Label(self.disks, text=mount, style="Card.Bold.TLabel", width=18).grid(row=i, column=0, sticky="w")
            style = "Danger.Horizontal.TProgressbar" if pct > .9 else \
                "Warning.Horizontal.TProgressbar" if pct > .75 else "Horizontal.TProgressbar"
            bar = ttk.Progressbar(self.disks, maximum=100, value=pct * 100, style=style)
            bar.grid(row=i, column=1, sticky="ew", padx=t.px(12), pady=t.px(6))
            ttk.Label(self.disks, text=f"{fmt_size(free)} livres de {fmt_size(tot)}",
                      style="Card.Muted.TLabel").grid(row=i, column=2, sticky="e")
        self.disks.columnconfigure(1, weight=1)
        self.render_summary()

    def _set_bin(self, size, n):
        self.bin_size = size
        self.bin_card.gauge.set(0, str(n), "itens", self.t.c["accent"])
        self.bin_card.big.config(text=fmt_size(size))
        self.bin_card.small.config(text="podem ser liberados" if size else "a Lixeira está vazia")
        self.render_hero()

    # ---- resumo / destaque
    def render_hero(self):
        s = self.summary
        if self.busy:
            return
        if not s:
            self.score.set(0, "—", "saúde", self.t.c["subtle"])
            self.h_title.config(text="Vamos deixar seu PC mais leve")
            self.h_desc.config(text="A análise completa procura lixo, cache, arquivos repetidos, grandes e antigos, "
                                    "restos de programas e o que abre junto com o sistema. Nada é apagado sem a "
                                    "sua confirmação.")
            self.btn_clean.pack_forget()
            self.btn_scan.config(text="Analisar agora", style="Big.Primary.TButton")
            return
        dl = disks()
        dpct = max((u / t for _, t, u, _ in dl if t), default=0)
        tot, used = memory_info()
        sc = health_score(dpct, used / tot if tot else 0, s.get("junk", 0), getattr(self, "bin_size", 0),
                          s.get("startup", 0), s.get("dups", 0))
        col = self.t.c["success"] if sc >= 70 else self.t.c["warning"] if sc >= 50 else self.t.c["danger"]
        self.score.set(sc / 100, str(sc), score_label(sc), col)
        junk = s.get("junk", 0)
        free_total = junk + s.get("dups", 0)
        self.h_title.config(text=f"Você pode liberar até {fmt_size(free_total)}" if free_total else
                            "Seu computador está limpo!")
        self.h_desc.config(text=f"Última análise em {s.get('when', '—')}. "
                                f"{fmt_size(junk)} em lixo e cache podem ser limpos com segurança agora; "
                                "o restante (repetidos, grandes, antigos) vale revisar item a item.")
        if junk and self.app.page_exists("junk"):
            self.btn_clean.config(text=f"Limpar {fmt_size(junk)} com segurança")
            self.btn_clean.pack(side="left", padx=(0, self.t.px(10)), before=self.btn_scan)
            self.btn_scan.config(text="Analisar de novo", style="TButton")
        else:
            self.btn_clean.pack_forget()
            self.btn_scan.config(text="Analisar de novo", style="Big.Primary.TButton")

    def render_summary(self):
        t = self.t
        for w in self.res.winfo_children():
            w.destroy()
        ttk.Label(self.res, text="Resultado da análise", style="Card.H3.TLabel").pack(anchor="w")
        s = self.summary
        if not s:
            ttk.Label(self.res, text="Nenhuma análise feita ainda. Clique em “Analisar agora”.",
                      style="Card.Muted.TLabel").pack(anchor="w", pady=(t.px(8), 0))
            self.render_hero()
            return
        rows = [
            ("sparkles", "Lixo e cache", "Temporários, caches de navegadores, relatórios de erro e Lixeira",
             fmt_size(s.get("junk", 0)), "junk", s.get("junk", 0) > 0),
            ("copy", "Arquivos repetidos", f"{s.get('dup_groups', 0)} grupos de arquivos idênticos",
             fmt_size(s.get("dups", 0)), "dups", s.get("dups", 0) > 0),
            ("file", "Arquivos grandes", f"{s.get('large_n', 0)} arquivos grandes para revisar",
             fmt_size(s.get("large", 0)), "large", False),
            ("clock", "Arquivos antigos", f"{s.get('old_n', 0)} arquivos sem uso há mais de 1 ano",
             fmt_size(s.get("old", 0)), "old", False),
            ("package", "Restos de programas", f"{s.get('left_n', 0)} possíveis sobras de programas desinstalados",
             fmt_size(s.get("left", 0)), "leftovers", s.get("left_n", 0) > 0),
            ("grid", "Programas pouco usados", f"Sem uso há mais de 90 dias, de {s.get('prog_total', 0)} instalados",
             str(s.get("prog_unused", 0)), "programs", s.get("prog_unused", 0) > 0),
            ("power", "Inicialização", "Programas que abrem sozinhos com o sistema",
             str(s.get("startup", 0)), "startup", s.get("startup", 0) > 5),
        ]
        for icon, title, desc, value, key, attention in rows:
            ttk.Frame(self.res, style="Sep.TFrame", height=1).pack(fill="x", pady=(t.px(10), t.px(10)))
            row = ttk.Frame(self.res, style="Flat.TFrame", cursor="hand2")
            row.pack(fill="x")
            ic = _soft_icon(row, t, icon, 38, soft=t.c["warning_soft"] if attention else None,
                            fg=t.c["warning"] if attention else None)
            ic.pack(side="left")
            mid = ttk.Frame(row, style="Flat.TFrame")
            mid.pack(side="left", fill="x", expand=True, padx=t.px(14))
            ttk.Label(mid, text=title, style="Card.Bold.TLabel").pack(anchor="w")
            ttk.Label(mid, text=desc, style="Card.Small.TLabel").pack(anchor="w")
            ttk.Button(row, text="Ver  ›", style="Ghost.TButton", command=lambda k=key: self.app.show(k)).pack(side="right")
            ttk.Label(row, text=value, style="Card.H3.TLabel").pack(side="right", padx=t.px(16))
            for w in (row, mid, ic):
                w.bind("<Button-1>", lambda e, k=key: self.app.show(k))
        self.render_hero()

    # ---- análise completa
    def smart_scan(self):
        if self.busy:
            return
        pages = {k: self.app.page(k) for k, _ in self.STEPS}
        if any(p.busy for p in pages.values()):
            messagebox.showinfo("Aguarde", "Há uma análise em andamento em outra página.", parent=self)
            return
        params = {}
        for k, p in pages.items():
            prm = p.get_params() or {}
            prm["roots"] = list(self.app.settings["roots"])
            params[k] = prm
        self.busy = True
        self.btn_scan.pack_forget()
        self.btn_clean.pack_forget()
        self.btn_stop.pack(side="left")
        self.prog.configure(value=0)
        self.prog.pack(fill="x", pady=(self.t.px(14), 0))
        self.lbl_prog.pack(anchor="w", pady=(self.t.px(6), 0))
        self.h_title.config(text="Analisando seu computador…")
        self.h_desc.config(text="Isso pode levar alguns minutos na primeira vez. Você pode continuar usando o PC.")
        self.score.set(0, "…", "analisando", self.t.c["accent"])
        self.step = 0

        def job(cancel, progress):
            out = {}
            for i, (k, label) in enumerate(self.STEPS):
                if cancel.is_set():
                    break
                self.step = i
                progress(f"Etapa {i + 1} de {len(self.STEPS)}: {label}…")
                try:
                    out[k] = pages[k].scan_job(params[k], cancel, lambda s, lb=label, i=i:
                                               progress(f"Etapa {i + 1} de {len(self.STEPS)}: {lb} — {s}"))
                except Exception as e:  # noqa: BLE001
                    log(f"ERRO na análise ({k}): {e}")
                    out[k] = []
            return out

        def done(out):
            self.busy = False
            for k, items in (out or {}).items():
                p = pages[k]
                p._scanned = True
                p.populate(items)
                p.show_progress(f"{len(items)} itens (da análise completa).")
            if out:
                self._summarize(out)
            self.btn_stop.pack_forget()
            self.prog.pack_forget()
            self.lbl_prog.pack_forget()
            self.btn_scan.pack(side="left")
            self.render_summary()
            if out:
                self.app.toast("Análise concluída!")

        self.run_bg(job, done, "Preparando…")

    def show_progress(self, text):
        self.lbl_prog.config(text=text)
        self.prog.configure(value=getattr(self, "step", 0) + 0.5)

    def _summarize(self, out):
        import datetime
        junk = out.get("junk", [])
        dups = out.get("dups", [])
        large = out.get("large", [])
        old = out.get("old", [])
        left = out.get("leftovers", [])
        progs = out.get("programs", [])
        start = out.get("startup", [])
        self.summary = {
            "when": datetime.datetime.now().strftime("%d/%m/%Y às %H:%M"),
            "junk": sum(i.size for i in junk if i.checked),
            "dups": sum(i.size for i in dups if i.checked), "dup_groups": len({i.group for i in dups}),
            "large": sum(i.size for i in large), "large_n": len(large),
            "old": sum(i.size for i in old), "old_n": len(old),
            "left": sum(i.size for i in left), "left_n": len(left),
            "prog_total": len(progs), "prog_unused": sum(1 for i in progs if i.values[-1] == "Pouco usado"),
            "startup": sum(1 for i in start if i.data.get("enabled")),
        }
        self.app.settings.set("last_scan", self.summary)

    def clean_recommended(self):
        jp = self.app.page("junk")
        items = jp.checked()
        if not items:
            self.app.show("junk")
            return
        total = sum(i.size for i in items)
        if not messagebox.askyesno("Limpeza recomendada",
                                   f"Limpar {len(items)} locais de lixo e cache ({fmt_size(total)})?\n\n"
                                   "Inclui temporários, caches e a Lixeira (se marcada). Seus documentos, "
                                   "fotos e programas não são tocados.", parent=self):
            return
        self.busy = True
        self.btn_clean.config(state="disabled")
        self.lbl_prog.pack(anchor="w", pady=(self.t.px(8), 0))

        def done(res):
            self.busy = False
            self.btn_clean.config(state="normal")
            self.lbl_prog.pack_forget()
            d, errors, freed = res
            jp.after_action(d, [], freed)
            if self.summary:
                self.summary["junk"] = sum(i.size for i in jp.checked())
                self.app.settings.set("last_scan", self.summary)
            self.refresh()

        self.run_bg(lambda c, p: jp.perform(items, False, p), done, "Limpando…")

    def empty_bin(self):
        size, n = recycle_bin_info()
        if not n and not size:
            self.app.toast("A Lixeira já está vazia.")
            return
        if messagebox.askyesno("Esvaziar Lixeira", f"Apagar permanentemente {n} item(ns) ({fmt_size(size)})?",
                               icon="warning", parent=self):
            try:
                empty_recycle_bin()
                self.app.toast(f"Lixeira esvaziada · {fmt_size(size)} liberados")
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("Lixeira", str(e), parent=self)
            self.refresh()

    def on_show(self):
        if not self.busy:
            self.refresh()

    def busy_now(self):
        return self.busy


# =================================================================== MAPA DO DISCO
class DiskMapPage(BackgroundMixin, Page):
    key, icon, title = "diskmap", "pie", "Mapa do disco"
    subtitle = ("Descubra o que está ocupando espaço: veja o tamanho de cada pasta, navegue pelas subpastas e "
                "apague o que não precisa. O gráfico mostra o espaço por tipo de arquivo.")

    def __init__(self, master, app):
        super().__init__(master, app)
        t, c = self.t, self.t.c
        self.busy = False
        self.cancel = threading.Event()
        self.nodes: dict[str, object] = {}
        self.root_node = None
        bar = card(self.body, t, 12, fill="x")
        targets = [d[0] for d in disks()] + [home()]
        self.target = tk.StringVar(value=home())
        ttk.Label(bar, text="Analisar", style="Card.TLabel").pack(side="left")
        self.cb = ttk.Combobox(bar, textvariable=self.target, values=targets, width=40)
        self.cb.pack(side="left", padx=t.px(8))
        ttk.Button(bar, text="Escolher pasta…", command=self.pick).pack(side="left")
        self.btn_scan = ttk.Button(bar, text="Analisar", style="Primary.TButton", command=self.start)
        self.btn_scan.pack(side="right")
        self.btn_stop = ttk.Button(bar, text="Parar", command=lambda: self.cancel.set())
        prog = ttk.Frame(self.body)
        prog.pack(fill="x", pady=(t.px(10), t.px(6)))
        self.lbl = ttk.Label(prog, text="", style="Small.TLabel")
        self.lbl.pack(side="left")
        self.pbar = ttk.Progressbar(prog, mode="indeterminate", style="Thin.Horizontal.TProgressbar")

        main = ttk.Frame(self.body)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)
        tc = ttk.Frame(main, style="Card.TFrame", padding=1)
        tc.grid(row=0, column=0, sticky="nsew")
        self.tree = ttk.Treeview(tc, columns=("size", "bar", "items", "mod"), selectmode="extended")
        self.tree.heading("#0", text="NOME", anchor="w")
        self.tree.column("#0", width=t.px(330))
        for col, head, w, anc in (("size", "TAMANHO", 95, "e"), ("bar", "USO NA PASTA", 190, "w"),
                                  ("items", "ARQUIVOS", 90, "e"), ("mod", "MODIFICADO", 105, "center")):
            self.tree.heading(col, text=head, anchor=anc if anc != "center" else "center")
            self.tree.column(col, width=t.px(w), anchor=anc, stretch=col == "bar")
        vsb = ttk.Scrollbar(tc, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tc.rowconfigure(0, weight=1)
        tc.columnconfigure(0, weight=1)
        self.tree.tag_configure("odd", background=c["row_alt"])
        self.tree.tag_configure("file", foreground=c["muted"])
        self.tree.bind("<<TreeviewOpen>>", self.on_open)
        self.tree.bind("<Double-1>", lambda e: self.open_sel())
        self.empty = ttk.Label(tc, text="Escolha um disco ou pasta e clique em “Analisar”.",
                               style="Card.Muted.TLabel", justify="center")
        self.empty.place(relx=0.5, rely=0.5, anchor="center")
        self.img_folder, self.img_file = self._make_icons()

        side = card(main, t, 18)
        side.grid(row=0, column=1, sticky="nsew", padx=(t.px(16), 0))
        ttk.Label(side, text="Por tipo de arquivo", style="Card.H3.TLabel").pack(anchor="w")
        self.lbl_total = ttk.Label(side, text="", style="Card.Muted.TLabel")
        self.lbl_total.pack(anchor="w", pady=(t.px(2), t.px(14)))
        self.chart = CategoryBars(side, t, CATEGORY_COLORS, width=280)
        self.chart.pack(fill="x")
        self.chart.set([])

        foot = ttk.Frame(self.body)
        foot.pack(fill="x", pady=(t.px(12), 0))
        ttk.Button(foot, text="Abrir local", command=self.open_sel).pack(side="left")
        ttk.Label(foot, text="Selecione linhas (Ctrl/Shift para várias) e use o botão ao lado.",
                  style="Small.TLabel").pack(side="left", padx=t.px(12))
        self.btn_del = ttk.Button(foot, text="Apagar selecionados", style="Danger.TButton", command=self.delete_sel)
        self.btn_del.pack(side="right")

    def _make_icons(self):
        s = self.t.px(16)
        c = self.t.c
        folder = tk.PhotoImage(width=s, height=s)
        k = s / 16
        rect = lambda img, x0, y0, x1, y1, col: img.put(col, to=(int(x0 * k), int(y0 * k), int(x1 * k), int(y1 * k)))  # noqa: E731
        rect(folder, 1, 3, 7, 5, "#f2b33d")
        rect(folder, 1, 4, 15, 14, "#f6c453")
        rect(folder, 1, 6, 15, 7, "#e9a92a")
        file = tk.PhotoImage(width=s, height=s)
        rect(file, 3, 1, 13, 15, c["subtle"])
        rect(file, 4, 2, 12, 14, c["surface"])
        rect(file, 5, 5, 11, 6, c["subtle"])
        rect(file, 5, 8, 11, 9, c["subtle"])
        rect(file, 5, 11, 9, 12, c["subtle"])
        return folder, file

    def pick(self):
        d = filedialog.askdirectory(parent=self, title="Escolha a pasta para analisar")
        if d:
            self.target.set(os.path.normpath(d))

    def show_progress(self, text):
        self.lbl.config(text=text)

    def busy_now(self):
        return self.busy

    def _busy(self, b):
        self.busy = b
        self.btn_scan.config(state="disabled" if b else "normal")
        self.btn_del.config(state="disabled" if b else "normal")
        if b:
            self.btn_stop.pack(side="right", padx=self.t.px(8), before=self.btn_scan)
        else:
            self.btn_stop.pack_forget()
        if b:
            self.pbar.pack(side="right", fill="x", expand=True, padx=(self.t.px(20), 0))
            self.pbar.start(12)
        else:
            self.pbar.stop()
            self.pbar.pack_forget()
        self.app.set_nav_busy(self.key, b)

    def start(self):
        target = self.target.get().strip()
        if not os.path.isdir(target):
            messagebox.showerror("Pasta inválida", "Escolha um disco ou uma pasta existente.", parent=self)
            return
        self._busy(True)
        self.empty.config(text="Analisando…")
        self.run_bg(lambda c, p: analyze(target, c, p), self.populate, "Analisando…",
                    on_finally=lambda: self._busy(False))

    def populate(self, res):
        root, cats, counts = res
        self.root_node = root
        self.tree.delete(*self.tree.get_children(""))
        self.nodes = {}
        self.empty.place_forget()
        iid = self._insert("", root, root.size or 1, 0)
        self.tree.item(iid, open=True)
        self._fill(iid)
        data = sorted(((n, cats[n], counts[n]) for n in CATEGORY_NAMES), key=lambda x: x[1], reverse=True)
        self.chart.set(data)
        self.lbl_total.config(text=f"{fmt_size(root.size)} em {root.files:,}".replace(",", ".") + " arquivos")

    def _bar(self, size, parent_size):
        frac = size / parent_size if parent_size else 0
        n = int(round(frac * 16))
        pct = f"{frac * 100:.1f}%".replace(".", ",")
        return f"{pct:>6}   {'█' * n}"

    def _insert(self, parent_iid, node, parent_size, idx):
        name = node.name if parent_iid else node.path
        iid = self.tree.insert(parent_iid, "end", text=f"  {name}", image=self.img_folder,
                               values=(fmt_size(node.size), self._bar(node.size, parent_size),
                                       f"{node.files:,}".replace(",", "."), fmt_date(node.mtime)),
                               tags=("odd",) if idx % 2 else ())
        self.nodes[iid] = node
        if node.children or node.top_files:
            self.tree.insert(iid, "end", text="…")
        return iid

    def _fill(self, iid):
        node = self.nodes.get(iid)
        if node is None or getattr(node, "path", None) is None:
            return
        kids = self.tree.get_children(iid)
        if len(kids) == 1 and self.tree.item(kids[0], "text") == "…":
            self.tree.delete(kids[0])
        elif kids:
            return
        entries = [("d", ch.size, ch) for ch in node.children] + [("f", sz, (sz, nm, mt)) for sz, nm, mt in node.top_files]
        entries.sort(key=lambda e: e[1], reverse=True)
        for i, (kind, size, obj) in enumerate(entries[:400]):
            if kind == "d":
                self._insert(iid, obj, node.size, i)
            else:
                sz, nm, mt = obj
                fid = self.tree.insert(iid, "end", text=f"  {nm}", image=self.img_file,
                                       values=(fmt_size(sz), self._bar(sz, node.size), "", fmt_date(mt)),
                                       tags=("file",) + (("odd",) if i % 2 else ()))
                self.nodes[fid] = ("file", os.path.join(node.path, nm), sz, node)
        if node.hidden_files > 0:
            self.tree.insert(iid, "end", text=f"  + {node.hidden_files} arquivos menores", tags=("file",))

    def on_open(self, _):
        self._fill(self.tree.focus())

    def _sel_paths(self):
        out = []
        for iid in self.tree.selection():
            obj = self.nodes.get(iid)
            if obj is None:
                continue
            if isinstance(obj, tuple):
                out.append((iid, obj[1], obj[2], obj[3], 1))
            elif obj is not self.root_node:
                out.append((iid, obj.path, obj.size, obj.parent, obj.files))
        return out

    def open_sel(self):
        for _, path, *_ in self._sel_paths()[:5]:
            open_location(path)

    def delete_sel(self):
        sel = self._sel_paths()
        if not sel:
            messagebox.showinfo("Nada selecionado", "Selecione pastas ou arquivos na lista (clique na linha).",
                                parent=self)
            return
        prot = [p for _, p, *_ in sel if is_protected(p)]
        if prot:
            messagebox.showwarning("Protegido", "Itens do sistema não podem ser apagados:\n" + "\n".join(prot[:5]),
                                   parent=self)
            return
        to_trash = self.app.settings["to_trash"]
        total = sum(s[2] for s in sel)
        names = "\n".join(f"• {os.path.basename(p)}" for _, p, *_ in sel[:8])
        modo = "Vão para a Lixeira." if to_trash else "Serão apagados PERMANENTEMENTE."
        if not messagebox.askyesno("Confirmar", f"Apagar {len(sel)} item(ns) ({fmt_size(total)})?\n\n{names}\n\n{modo}",
                                   icon="warning", parent=self):
            return

        def job(cancel, progress):
            done, errors = [], []
            for s in sel:
                progress(f"Apagando {os.path.basename(s[1])}…")
                try:
                    delete_path(s[1], to_trash)
                    log(f"{'LIXEIRA' if to_trash else 'APAGADO'} {s[1]} ({fmt_size(s[2])})")
                    done.append(s)
                except Exception as e:  # noqa: BLE001
                    errors.append((s[1], str(e)))
            return done, errors

        def after(res):
            done, errors = res
            freed = 0
            for iid, path, size, parent, files in done:
                obj = self.nodes.pop(iid, None)
                if parent is not None:
                    if not isinstance(obj, tuple) and obj in parent.children:
                        parent.children.remove(obj)
                    elif isinstance(obj, tuple):
                        parent.top_files = [f for f in parent.top_files if os.path.join(parent.path, f[1]) != path]
                    remove_size(parent, size, files)
                freed += size
                if self.tree.exists(iid):
                    self.tree.delete(iid)
            self._refresh_values("")
            if done:
                self.app.toast(f"{len(done)} item(ns) apagado(s) · {fmt_size(freed)} liberados")
            if errors:
                messagebox.showwarning("Alguns itens foram pulados",
                                       "\n".join(f"• {os.path.basename(p)}: {m}" for p, m in errors[:10]), parent=self)
            self.app.data_changed()

        self._busy(True)
        self.run_bg(job, after, "Apagando…", on_finally=lambda: self._busy(False))

    def _refresh_values(self, iid, parent_size=None):
        for ch in self.tree.get_children(iid):
            obj = self.nodes.get(ch)
            if obj is None or isinstance(obj, tuple):
                continue
            ps = parent_size if parent_size is not None else (obj.size or 1)
            self.tree.set(ch, "size", fmt_size(obj.size))
            self.tree.set(ch, "bar", self._bar(obj.size, ps))
            self.tree.set(ch, "items", f"{obj.files:,}".replace(",", "."))
            if self.tree.item(ch, "open"):
                self._refresh_values(ch, obj.size or 1)


# =================================================================== FERRAMENTAS
class ToolsPage(BackgroundMixin, Page):
    key, icon, title = "tools", "tools", "Ferramentas"
    subtitle = "Ajustes do sistema que liberam espaço ou resolvem problemas. Algumas pedem permissão de administrador."

    def __init__(self, master, app):
        super().__init__(master, app)
        t = self.t
        self.cancel = threading.Event()
        sf = ScrollFrame(self.body, t)
        sf.pack(fill="both", expand=True)
        grid = sf.inner
        grid.columnconfigure((0, 1), weight=1, uniform="tools")
        tools = available_tools()
        if not tools:
            ttk.Label(grid, text="Nenhuma ferramenta disponível neste sistema.", style="Muted.TLabel").grid(row=0, column=0)
        for i, tool in enumerate(tools):
            f = card(grid, t, 18)
            f.grid(row=i // 2, column=i % 2, sticky="nsew", padx=(0 if i % 2 == 0 else t.px(8), t.px(8) if i % 2 == 0 else 0),
                   pady=(0, t.px(16)))
            top = ttk.Frame(f, style="Flat.TFrame")
            top.pack(fill="x")
            _soft_icon(top, t, tool.icon, 40).pack(side="left")
            ttk.Label(top, text=tool.title, style="Card.H3.TLabel").pack(side="left", padx=t.px(12))
            if tool.badge:
                ttk.Label(top, text=f"  {tool.badge}  ", style="Badge.TLabel").pack(side="right")
            ttk.Label(f, text=tool.desc, style="Card.Muted.TLabel", wraplength=t.px(400), justify="left").pack(
                anchor="w", pady=(t.px(12), t.px(14)))
            ttk.Button(f, text=tool.button, style="Primary.TButton" if tool.kind != "open" else "TButton",
                       command=lambda tool=tool: self.run(tool)).pack(anchor="w")

    def run(self, tool):
        if tool.kind in ("open", "admin_console", "battery"):
            msg = run_tool(tool)
            if msg:
                messagebox.showinfo(tool.title, msg, parent=self)
            return
        self.app.toast(f"Executando: {tool.title}…", kind="info")
        self.run_bg(lambda c, p: run_tool(tool), lambda msg: messagebox.showinfo(tool.title, msg or "Concluído.",
                                                                                  parent=self))


# =================================================================== CONFIGURAÇÕES
class SettingsPage(Page):
    key, icon, title = "settings", "gear", "Configurações"
    subtitle = "Personalize o LimpaPC. As escolhas ficam salvas para as próximas vezes."

    def __init__(self, master, app):
        super().__init__(master, app)
        t, s = self.t, app.settings
        sf = ScrollFrame(self.body, t)
        sf.pack(fill="both", expand=True)
        root = sf.inner

        def section(title, desc=""):
            f = card(root, t, 20, fill="x", pady=(0, t.px(14)))
            ttk.Label(f, text=title, style="Card.H3.TLabel").pack(anchor="w")
            if desc:
                ttk.Label(f, text=desc, style="Card.Muted.TLabel", wraplength=t.px(760), justify="left").pack(
                    anchor="w", pady=(t.px(2), t.px(10)))
            return f

        f = section("Aparência", "Escolha o tema da janela.")
        self.theme_var = tk.StringVar(value=s["theme"])
        row = ttk.Frame(f, style="Flat.TFrame")
        row.pack(anchor="w")
        for val, label in (("auto", "Automático (igual ao sistema)"), ("light", "Claro"), ("dark", "Escuro")):
            ttk.Radiobutton(row, text=label, value=val, variable=self.theme_var, style="Card.TRadiobutton",
                            command=self.change_theme).pack(side="left", padx=(0, t.px(22)))

        f = section("Segurança")
        self.trash_var = tk.BooleanVar(value=s["to_trash"])
        ttk.Checkbutton(f, text="Enviar arquivos apagados para a Lixeira (recomendado — permite desfazer)",
                        variable=self.trash_var, style="Card.TCheckbutton",
                        command=lambda: s.set("to_trash", self.trash_var.get())).pack(anchor="w")
        adm = ttk.Frame(f, style="Flat.TFrame")
        adm.pack(fill="x", pady=(t.px(12), 0))
        if is_admin():
            ttk.Label(adm, text="  Executando como administrador  ", style="BadgeOk.TLabel").pack(side="left")
        else:
            ttk.Label(adm, text="Sem permissão de administrador: pastas do sistema e a recuperação profunda "
                                "ficam limitadas.", style="Card.Muted.TLabel").pack(side="left")
            if IS_WIN:
                ttk.Button(adm, text="Reabrir como administrador", command=app.elevate).pack(side="right")

        f = section("Pastas analisadas", "Usadas para procurar arquivos grandes, repetidos e antigos.")

        def all_drives(items):
            for d in fixed_drives():
                if d not in items:
                    items.append(d)

        def default(items):
            items[:] = [home()]

        ListEditor(f, t, s["roots"], lambda items: (s.save(), app.roots_changed()),
                   extra=(("Adicionar todos os discos", all_drives), ("Restaurar padrão", default))).pack(fill="x")

        f = section("Exclusões", "Pastas que o LimpaPC nunca vai analisar nem sugerir apagar.")
        ListEditor(f, t, s["exclusions"], lambda items: (s.save(), set_exclusions(items))).pack(fill="x")

        f = section("Limpeza automática",
                    "Limpa lixo e cache sozinho, no horário escolhido, mesmo com o programa fechado (usa o "
                    "Agendador de Tarefas do Windows). Itens de privacidade nunca são limpos automaticamente.")
        from .autoclean import FREQS, set_schedule
        row = ttk.Frame(f, style="Flat.TFrame")
        row.pack(anchor="w")
        ttk.Label(row, text="Frequência", style="Card.TLabel").pack(side="left")
        self.freq_var = tk.StringVar(value=FREQS.get(s.get("auto_clean", "off"), FREQS["off"]))
        cb = ttk.Combobox(row, textvariable=self.freq_var, values=list(FREQS.values()), state="readonly", width=18)
        cb.pack(side="left", padx=t.px(10))
        self.bin_var = tk.BooleanVar(value=s.get("auto_clean_recycle", False))
        ttk.Checkbutton(row, text="Esvaziar a Lixeira também", variable=self.bin_var, style="Card.TCheckbutton",
                        command=lambda: s.set("auto_clean_recycle", self.bin_var.get())).pack(side="left", padx=t.px(10))

        def changed(_=None):
            key = next(k for k, v in FREQS.items() if v == self.freq_var.get())
            err = set_schedule(key)
            if err:
                messagebox.showerror("Limpeza automática", err, parent=self)
                self.freq_var.set(FREQS[s.get("auto_clean", "off")])
                return
            s.set("auto_clean", key)
            app.toast("Limpeza automática desligada." if key == "off" else f"Limpeza automática: {FREQS[key].lower()}.")
        cb.bind("<<ComboboxSelected>>", changed)
        last = s.get("auto_clean_last")
        if last:
            ttk.Label(f, text=f"Última limpeza automática: {last['when']} — {fmt_size(last['freed'])} liberados.",
                      style="Card.Small.TLabel").pack(anchor="w", pady=(t.px(8), 0))

        f = section("Atualizações")
        self.upd_var = tk.BooleanVar(value=s["check_updates"])
        ttk.Checkbutton(f, text="Verificar novas versões ao abrir o programa", variable=self.upd_var,
                        style="Card.TCheckbutton", command=lambda: s.set("check_updates", self.upd_var.get())).pack(anchor="w")
        ttk.Button(f, text="Verificar agora", command=lambda: app.check_updates(manual=True)).pack(anchor="w", pady=(t.px(10), 0))

        f = section("Dados e privacidade",
                    "O LimpaPC funciona 100% no seu computador: não coleta nem envia nenhum dado. A internet só é "
                    "usada para verificar se existe uma nova versão (e isso pode ser desligado acima). Todas as "
                    "ações ficam registradas num histórico local.")
        row = ttk.Frame(f, style="Flat.TFrame")
        row.pack(anchor="w")
        ttk.Button(row, text="Abrir histórico de ações",
                   command=lambda: open_location(os.path.join(app_data_dir(), "historico.log"))).pack(side="left")
        ttk.Button(row, text="Abrir pasta de dados", command=lambda: open_location(app_data_dir())).pack(
            side="left", padx=t.px(8))

    def change_theme(self):
        self.app.settings.set("theme", self.theme_var.get())
        self.app.rebuild("settings")


# =================================================================== SOBRE
class AboutPage(Page):
    key, icon, title = "about", "info", "Sobre"
    subtitle = ""

    def __init__(self, master, app):
        super().__init__(master, app)
        t, c = self.t, self.t.c
        f = card(self.body, t, 30, fill="x")
        top = ttk.Frame(f, style="Flat.TFrame")
        top.pack(fill="x")
        cv = tk.Canvas(top, width=t.px(84), height=t.px(84), bg=c["surface"], highlightthickness=0)
        draw_logo(cv, 2, 2, t.px(80))
        cv.pack(side="left")
        info = ttk.Frame(top, style="Flat.TFrame")
        info.pack(side="left", padx=t.px(20))
        name = ttk.Frame(info, style="Flat.TFrame")
        name.pack(anchor="w")
        ttk.Label(name, text=APP_NAME, style="Card.H1.TLabel").pack(side="left")
        ttk.Label(name, text=f"  versão {__version__}  ", style="Badge.TLabel").pack(side="left", padx=t.px(12))
        ttk.Label(info, text="Limpeza, otimização e recuperação de arquivos para o seu computador.",
                  style="Card.Muted.TLabel").pack(anchor="w", pady=(t.px(4), 0))
        ttk.Label(info, text="Gratuito e de código aberto · sem anúncios · sem coleta de dados",
                  style="Card.Accent.TLabel").pack(anchor="w", pady=(t.px(6), 0))

        feats = card(self.body, t, 24, fill="x", pady=(t.px(16), 0))
        ttk.Label(feats, text="O que o LimpaPC faz", style="Card.H3.TLabel").grid(row=0, column=0, columnspan=2,
                                                                                    sticky="w", pady=(0, t.px(12)))
        items = [("sparkles", "Limpa lixo, cache e temporários"), ("pie", "Mostra o que ocupa o disco"),
                 ("copy", "Encontra arquivos repetidos"), ("file", "Lista arquivos grandes e antigos"),
                 ("grid", "Desinstala programas sem uso"), ("package", "Remove restos de programas"),
                 ("chip", "Libera memória RAM"), ("power", "Controla a inicialização"),
                 ("trash", "Restaura itens da Lixeira"), ("download", "Recupera arquivos apagados")]
        for i, (ic, txt) in enumerate(items):
            r = ttk.Frame(feats, style="Flat.TFrame")
            r.grid(row=1 + i // 2, column=i % 2, sticky="w", pady=t.px(5), padx=(0, t.px(40)))
            Icon(r, ic, t.px(18), c["accent"], c["surface"]).pack(side="left")
            ttk.Label(r, text=txt, style="Card.TLabel").pack(side="left", padx=t.px(10))

        row = ttk.Frame(self.body)
        row.pack(anchor="w", pady=(t.px(16), 0))
        ttk.Button(row, text="Site do projeto", style="Primary.TButton", command=lambda: open_uri(HOMEPAGE)).pack(side="left")
        ttk.Button(row, text="Verificar atualizações", command=lambda: app.check_updates(manual=True)).pack(
            side="left", padx=t.px(8))
        ttk.Button(row, text="Licença (MIT)", command=lambda: open_uri(HOMEPAGE + "/blob/main/limpador/LICENSE")).pack(side="left")
        ttk.Label(self.body, text=f"© {APP_NAME} — distribuído sob a licença MIT. Use por sua conta e risco: revise "
                                  "sempre o que vai apagar.", style="Small.TLabel").pack(anchor="w", pady=(t.px(18), 0))


# =================================================================== JANELA PRINCIPAL
def _load_pages():
    """Junta todas as páginas disponíveis (módulos opcionais são carregados se existirem)."""
    import importlib
    classes = [DashboardPage, JunkPage, DiskMapPage, LargeFilesPage, DuplicatesPage, OldFilesPage, ProgramsPage,
               LeftoversPage, StartupPage, ProcessesPage, ToolsPage, TrashPage, RecoverPage, SettingsPage, AboutPage]
    optional = [("limpapc.uninstall_pages", ["StoreAppsPage"]), ("limpapc.donate", ["DonatePage"]),
                ("limpapc.apps_pages", ["InstallAppsPage", "UpdateAppsPage"]),
                ("limpapc.hw_pages", ["DriversPage", "SystemInfoPage"]),
                ("limpapc.test_pages", ["BenchmarkPage", "SpeedTestPage"]),
                ("limpapc.optimize_pages", ["RegistryPage", "TweaksPage", "DiskOptimizePage", "ShredderPage"])]
    for mod, names in optional:
        try:
            m = importlib.import_module(mod)
        except Exception as e:  # noqa: BLE001
            log(f"módulo opcional indisponível: {mod}: {e}")
            continue
        classes += [getattr(m, n) for n in names if hasattr(m, n)]
    return {cls.key: cls for cls in classes}


# menu lateral: (título do grupo, ícone, [chaves das páginas]); grupo de 1 item vira item simples
NAV = [
    ("Painel", "home", ["dashboard"]),
    ("Limpeza", "broom", ["junk", "registry", "diskmap", "large", "dups", "old"]),
    ("Programas", "grid", ["programs", "updates", "install", "store_apps", "leftovers", "startup"]),
    ("Desempenho", "rocket", ["ram", "tweaks", "diskopt", "drivers", "tools"]),
    ("Diagnóstico", "gauge", ["sysinfo", "bench", "speed"]),
    ("Recuperação", "shield", ["trash", "recover", "shredder"]),
]
BOTTOM = [("donate", "heart", "Apoie"), ("settings", "gear", "Ajustes"), ("about", "info", "Sobre")]
NAV_TITLES = {"junk": "Lixo e cache", "registry": "Registro", "diskmap": "Mapa do disco", "large": "Arquivos grandes",
              "dups": "Arquivos repetidos", "old": "Arquivos antigos", "programs": "Desinstalar programas",
              "updates": "Atualizar programas", "install": "Instalar programas", "store_apps": "Apps da Store",
              "leftovers": "Restos de programas", "startup": "Inicialização", "ram": "Memória RAM",
              "tweaks": "Otimizar Windows", "diskopt": "Otimizar discos", "drivers": "Drivers", "tools": "Ferramentas",
              "sysinfo": "Meu computador", "bench": "Teste de desempenho", "speed": "Velocidade da internet",
              "trash": "Lixeira", "recover": "Recuperar apagados", "shredder": "Destruidor de arquivos"}


class BottomButton(tk.Frame):
    def __init__(self, master, theme, icon, text, command):
        c = theme.c
        super().__init__(master, bg=c["sidebar"], cursor="hand2")
        self.theme, self.active = theme, False
        self.icon = Icon(self, icon, theme.px(18), c["sidebar_text"], c["sidebar"])
        self.icon.pack(pady=(theme.px(8), theme.px(2)))
        self.label = tk.Label(self, text=text, bg=c["sidebar"], fg=c["sidebar_text"], font=theme.f_small)
        self.label.pack(pady=(0, theme.px(8)))
        for w in (self, self.icon, self.label):
            w.bind("<Enter>", lambda e: self._paint(True))
            w.bind("<Leave>", lambda e: self._paint())
            w.bind("<Button-1>", lambda e: command())

    def set_active(self, v):
        self.active = v
        self._paint()

    def set_badge(self, text):
        pass

    def _paint(self, hover=False):
        c = self.theme.c
        bg = c["sidebar_active"] if self.active else c["sidebar_hover"] if hover else c["sidebar"]
        for w in (self, self.label):
            w.configure(bg=bg)
        self.label.configure(fg="#ffffff" if self.active else c["sidebar_text"])
        self.icon.redraw(color=c["sidebar_accent"] if self.active else c["sidebar_text"], bg=bg)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title(f"{APP_NAME} — limpeza e otimização")
        self.settings = Settings()
        set_exclusions(self.settings["exclusions"])
        self._icon_img = None
        self.update_info = None
        self.build("dashboard")
        w, h = self.t.px(1240), self.t.px(800)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(w, sw - 40), min(h, sh - 80)
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
        self.minsize(self.t.px(1000), self.t.px(640))
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.deiconify()
        set_dark_titlebar(self, self.t.dark)
        if self.settings["check_updates"]:
            self.after(2500, self.check_updates)

    # ---- construção da interface
    def build(self, page_key):
        self.t = Theme(self, self.settings["theme"])
        self.t.apply()
        self._set_window_icon()
        c, px = self.t.c, self.t.px
        self.pages: dict[str, Page] = {}
        self.page_classes = _load_pages()
        self.current = None

        self.sidebar = tk.Frame(self, bg=c["sidebar"], width=px(240))
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        brand = tk.Frame(self.sidebar, bg=c["sidebar"])
        brand.pack(fill="x", padx=px(18), pady=(px(20), px(14)))
        cv = tk.Canvas(brand, width=px(36), height=px(36), bg=c["sidebar"], highlightthickness=0)
        draw_logo(cv, 0, 0, px(36))
        cv.pack(side="left")
        bt = tk.Frame(brand, bg=c["sidebar"])
        bt.pack(side="left", padx=px(10))
        tk.Label(bt, text=APP_NAME, bg=c["sidebar"], fg="#ffffff", font=self.t.f_brand).pack(anchor="w")
        tk.Label(bt, text=f"versão {__version__}", bg=c["sidebar"], fg=c["sidebar_muted"],
                 font=self.t.f_small).pack(anchor="w")

        # rodapé do menu (Apoie / Ajustes / Sobre)
        bottom = tk.Frame(self.sidebar, bg=c["sidebar"])
        bottom.pack(side="bottom", fill="x", pady=(px(4), px(10)))
        self.update_pill = tk.Label(bottom, text="", bg=c["accent"], fg="#ffffff", font=self.t.f_bold,
                                    cursor="hand2", padx=px(10), pady=px(6))
        self.update_pill.bind("<Button-1>", lambda e: self._open_update())
        self.bottom_row = tk.Frame(bottom, bg=c["sidebar"])
        self.bottom_row.pack(fill="x", padx=px(10))
        self.nav: dict = {}
        for key, icon, text in BOTTOM:
            if key in self.page_classes:
                b_ = BottomButton(self.bottom_row, self.t, icon, text, lambda k=key: self.show(k))
                b_.pack(side="left", fill="x", expand=True)
                self.nav[key] = b_
        tk.Frame(self.sidebar, bg=c["sidebar_hover"], height=1).pack(side="bottom", fill="x", padx=px(16))

        # área rolável com os grupos
        holder = tk.Frame(self.sidebar, bg=c["sidebar"])
        holder.pack(fill="both", expand=True)
        self.nav_canvas = tk.Canvas(holder, bg=c["sidebar"], highlightthickness=0, bd=0)
        self.nav_canvas.pack(fill="both", expand=True)
        inner = tk.Frame(self.nav_canvas, bg=c["sidebar"])
        win = self.nav_canvas.create_window((0, 0), window=inner, anchor="nw")
        self.nav_canvas.bind("<Configure>", lambda e: self.nav_canvas.itemconfigure(win, width=e.width))
        inner.bind("<Configure>", lambda e: self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all")))

        register_scroll(holder, self.nav_canvas, lambda: inner.winfo_reqheight())
        install_wheel(self)

        self.groups: list[NavGroup] = []
        self.group_of: dict[str, NavGroup] = {}
        for title, icon, keys in NAV:
            keys = [k for k in keys if k in self.page_classes]
            if not keys:
                continue
            if len(keys) == 1:
                item = NavItem(inner, self.t, icon, title, lambda k=keys[0]: self.show(k))
                item.pack(fill="x")
                self.nav[keys[0]] = item
                continue
            g = NavGroup(inner, self.t, icon, title, self._toggle_group)
            g.pack(fill="x")
            for k in keys:
                item = NavItem(g.body, self.t, None, NAV_TITLES.get(k, self.page_classes[k].title),
                               lambda k=k: self.show(k), sub=True)
                g.add(item)
                self.nav[k] = item
                self.group_of[k] = g
            self.groups.append(g)
        if self.update_info:
            self._show_update_pill()

        self.content = ttk.Frame(self)
        self.content.pack(side="left", fill="both", expand=True)
        self.show(page_key)

    def _set_window_icon(self):
        try:
            from .icon_data import ICON_PNG
            self._icon_img = tk.PhotoImage(data=ICON_PNG)
            self.iconphoto(True, self._icon_img)
        except Exception:  # noqa: BLE001
            pass

    def rebuild(self, page_key):
        if any(p.busy_now() for p in self.pages.values()):
            messagebox.showinfo("Aguarde", "O novo tema será aplicado quando a análise em andamento terminar.",
                                parent=self)
            return
        for w in list(self.winfo_children()):
            w.destroy()
        self.build(page_key)
        set_dark_titlebar(self, self.t.dark)

    def page(self, key) -> Page:
        if key not in self.pages:
            self.pages[key] = self.page_classes[key](self.content, self)
        return self.pages[key]

    def page_exists(self, key):
        return key in self.pages

    def show(self, key):
        page = self.page(key)
        if self.current is page:
            return
        if self.current is not None:
            self.current.pack_forget()
        page.pack(fill="both", expand=True)
        self.current = page
        for k, item in self.nav.items():
            item.set_active(k == key)
        g = self.group_of.get(key)
        for grp in self.groups:
            grp.set_has_active(grp is g)
        if g is not None and not g.expanded:
            self._toggle_group(g, navigate=False)
        page.on_show()

    def _toggle_group(self, group, navigate=True):
        """Sanfona: abre o grupo clicado e fecha os outros."""
        opening = not group.expanded
        for g in self.groups:
            g.set_expanded(g is group and opening)
        self.nav_canvas.update_idletasks()
        self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all"))

    def set_nav_busy(self, key, busy):
        if key in self.nav:
            self.nav[key].set_badge("●" if busy else "")

    def toast(self, text, kind="success"):
        Toast(self, self.t, text, kind)

    def data_changed(self):
        if "dashboard" in self.pages and self.current is self.pages["dashboard"]:
            self.pages["dashboard"].refresh()

    def roots_changed(self):
        for p in self.pages.values():
            if isinstance(p, ResultsPage):
                p.refresh_roots_label()

    def elevate(self):
        if relaunch_as_admin():
            self._close()

    # ---- atualizações
    def check_updates(self, manual=False):
        def job():
            try:
                info = check_for_update()
            except Exception as e:  # noqa: BLE001
                info = e
            self.after(0, lambda: self._update_result(info, manual))
        threading.Thread(target=job, daemon=True).start()

    def _update_result(self, info, manual):
        if isinstance(info, Exception):
            if manual:
                messagebox.showwarning("Atualizações", f"Não foi possível verificar agora.\n\n{info}", parent=self)
            return
        if not info:
            if manual:
                self.toast(f"Você já está na versão mais recente ({__version__}).")
            return
        self.update_info = info
        self._show_update_pill()
        if manual:
            self._open_update()

    def _show_update_pill(self):
        self.update_pill.config(text=f"↓  Nova versão {self.update_info[0]}")
        self.update_pill.pack(fill="x", padx=self.t.px(16), pady=(0, self.t.px(8)), before=self.bottom_row)

    def _open_update(self):
        ver, page_url, setup = self.update_info
        if messagebox.askyesno("Nova versão disponível",
                               f"A versão {ver} do {APP_NAME} está disponível (você usa a {__version__}).\n\n"
                               "Abrir a página de download?", parent=self):
            open_uri(setup or page_url)

    def _close(self):
        for p in self.pages.values():
            if hasattr(p, "cancel"):
                p.cancel.set()
        self.destroy()


def main():
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LimpaPC.App")
        except Exception:  # noqa: BLE001
            pass
    app = App()
    app.mainloop()


if __name__ == "__main__":
    sys.exit(main())
