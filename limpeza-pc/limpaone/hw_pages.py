"""Páginas de hardware: Drivers (listar, atualizar pelo Windows Update, backup) e Meu computador (ficha técnica)."""
from __future__ import annotations

import datetime
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import drivers as drv
from . import sysinfo
from .pages import BackgroundMixin, CHECK, Page, ResultsPage, UNCHECK
from .theme import draw_icon
from .utils import IS_WIN, Item, fmt_size, log, open_location, open_uri
from .widgets import Icon, ScrollFrame, card
from .winutil import run


def _soft_icon(master, t, name, size=40, bg_key="surface"):
    """Ícone num círculo suave (mesmo visual dos cards do Painel/Ferramentas)."""
    c = t.c
    sz = t.px(size)
    cv = tk.Canvas(master, width=sz, height=sz, bg=c[bg_key], highlightthickness=0, bd=0)
    cv.create_oval(0, 0, sz, sz, fill=c["accent_soft"], outline="")
    draw_icon(cv, name, sz * 0.25, sz * 0.25, sz * 0.5, c["accent"], 2.0, bg=c["accent_soft"])
    return cv


BADGE_STYLE = {"ok": "BadgeOk.TLabel", "warn": "BadgeWarn.TLabel", "bad": "BadgeWarn.TLabel", "info": "Badge.TLabel"}
BAR_STYLE = {"ok": "Success.Horizontal.TProgressbar", "warn": "Warning.Horizontal.TProgressbar",
             "bad": "Danger.Horizontal.TProgressbar"}


def _badge(master, t, badge):
    text, tone = badge
    if tone == "bad":   # não existe estilo "BadgeDanger": usa rótulo vermelho em destaque
        lbl = tk.Label(master, text=f" {text} ", bg=t.c["danger_soft"], fg=t.c["danger"], font=t.f_small,
                       padx=t.px(6), pady=t.px(1))
        return lbl
    return ttk.Label(master, text=text, style=BADGE_STYLE.get(tone, "Badge.TLabel"))


RISKY_CLASSES = ("rede", "net", "bluetooth")
RISKY_WORDS = ("wi-fi", "wifi", "wlan", "wireless", "ethernet", "network", "lan ", "bluetooth", "802.11", "realtek rtl8",
               "killer", "intel(r) wi", "mediatek wi", "qualcomm")


def is_risky_update(u: dict) -> bool:
    """Drivers que, se derem errado, deixam o PC sem internet: nunca vêm marcados e pedem confirmação."""
    cls = str(u.get("cls", "")).lower()
    txt = (str(u.get("title", "")) + " " + str(u.get("model", ""))).lower()
    return cls in RISKY_CLASSES or any(w in txt for w in RISKY_WORDS)


def _with_status(values, status):
    return values[:1] + (status,) + values[2:]


# =================================================================== DRIVERS
class DriversPage(ResultsPage):
    key, icon = "drivers", "chip"
    title = "Drivers"
    subtitle = ("Diagnóstico dos drivers: veja o que está com problema ou desatualizado, consulte o que existe de "
                "novo no Windows Update e faça backup. Por segurança, o LimpaOne não instala drivers.")
    columns = [("Dispositivo", 250, "w"), ("Situação", 345, "w"), ("Versão", 122, "w"), ("Data", 88, "center"),
               ("Fabricante", 150, "w"), ("Categoria", 120, "w")]
    scan_label = "Listar drivers"
    action_label = "Abrir Windows Update"
    action_style = "Primary.TButton"
    uses_trash = False
    show_open = False
    auto_scan = True
    empty_text = "Nenhum dispositivo listado ainda.\nClique em “Listar drivers” para começar."

    def __init__(self, master, app):
        super().__init__(master, app)
        t = self.t
        self.updates: list[Item] = []
        self._reboot = False
        self.tree.tag_configure("accent", foreground=t.c["accent"], font=t.f_bold)
        # botão principal: atualizações (o "Listar drivers" vira secundário)
        self.btn_scan.config(style="TButton")
        self.btn_updates = ttk.Button(self.btn_scan.master, text="Procurar atualizações", style="Primary.TButton",
                                      command=self.search_updates)
        self.btn_updates.pack(side="right", padx=(0, t.px(8)), before=self.btn_scan)
        # aviso de segurança
        note = ttk.Frame(self.body, style="Card.TFrame", padding=(t.px(14), t.px(10)))
        note.pack(fill="x", pady=(0, t.px(10)), before=self.body.winfo_children()[0])
        Icon(note, "shield", t.px(20), t.c["success"], t.c["surface"], 2.0).pack(side="left", padx=(0, t.px(12)))
        self.lbl_note = ttk.Label(
            note, style="Card.Muted.TLabel", justify="left", wraplength=t.px(820),
            text="O LimpaOne NÃO instala drivers: uma instalação que dá errado pode deixar o PC sem internet, som "
                 "ou vídeo. Aqui você vê o diagnóstico e o que há de novo; se realmente precisar atualizar, use o "
                 "Windows Update (Atualizações opcionais) ou o app do fabricante (Lenovo Vantage, NVIDIA, AMD, "
                 "Intel), de preferência depois de fazer o backup dos drivers.")
        extra = 0
        if IS_WIN:
            ttk.Button(note, text="Gerenciador de Dispositivos", style="Ghost.TButton",
                       command=self.open_devmgmt).pack(side="right", padx=(t.px(12), 0))
            extra = t.px(220)
        self.lbl_note.pack(side="left", fill="x", expand=True)
        note.bind("<Configure>", lambda e: self.lbl_note.config(wraplength=max(300, e.width - t.px(70) - extra)))
        self.menu.add_separator()
        self.menu.add_command(label="Copiar nome, versão e situação", command=self.copy_info)
        if IS_WIN:
            self.menu.add_command(label="Abrir Gerenciador de Dispositivos", command=self.open_devmgmt)

    # ---- opções / ações extras
    def build_options(self, f):
        self.show_all = tk.BooleanVar(value=False)
        self.only_attention = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Só os que precisam de atenção", variable=self.only_attention,
                        style="Card.TCheckbutton", command=self.render_rows).pack(side="left")
        ttk.Checkbutton(f, text="Mostrar componentes internos do sistema", variable=self.show_all,
                        style="Card.TCheckbutton", command=self.start_scan).pack(side="left", padx=(self.t.px(16), 0))

    def build_actions(self, f):
        ttk.Button(f, text="Backup dos drivers", command=self.backup).pack(side="left")

    def get_params(self):
        return {"all": self.show_all.get()}

    # ---- listagem
    def scan_job(self, p, cancel, progress):
        progress("Lendo dispositivos e drivers…")
        rows = drv.list_drivers(show_all=p["all"])
        items = []
        for r in rows:
            d = r["date"]
            items.append(Item(path=r["id"] or r["name"], kind="driver",
                              values=(r["name"], r["status"], r["version"], r["date_txt"], r["maker"], r["cls"]),
                              raw=(r["name"].lower(), r["rank"], r["version"], d.toordinal() if d else 0,
                                   r["maker"].lower(), r["cls"].lower()),
                              data=r))
        probs = sum(1 for r in rows if r["tag"] == "danger")
        old = sum(1 for r in rows if r["tag"] == "warn")
        parts = [f"{len(rows)} dispositivos"]
        if probs:
            parts.append(f"{probs} com problema")
        if old:
            parts.append(f"{old} com driver antigo")
        progress(" · ".join(parts) + ("" if probs or old else " · tudo certo ✓"))
        return items

    def populate(self, items):
        drivers = [i for i in (items or []) if i.kind == "driver"]
        hw = {u.data["hwid"].lower() for u in self.updates if u.data.get("hwid")}
        for it in drivers:
            if hw and it.data.get("hwid") and it.data["hwid"].lower() in hw:
                it.data["has_update"] = True
                it.values = _with_status(it.values, "Atualização disponível (veja acima)")
        super().populate(self.updates + drivers)

    def _visible(self):
        items = super()._visible()
        if self.only_attention.get():
            items = [i for i in items if i.kind == "update" or i.data.get("tag") in ("danger", "warn")
                     or i.data.get("has_update")]
        return items

    def row_tags(self, item):
        if item.kind == "update" or item.data.get("has_update"):
            return ("accent",)
        return {"danger": ("danger",), "warn": ("warn",), "muted": ("muted",)}.get(item.data.get("tag"), ())

    def render(self, iid, n=0):
        it = self.items[iid]
        tags = self.row_tags(it) + (("odd",) if n % 2 else ())
        box = (CHECK if it.checked else UNCHECK) if it.kind == "update" else ""
        self.tree.item(iid, values=(box, *it.values), tags=tags)

    def checked(self):
        return [it for it in self.all_items if it.kind == "update" and it.checked]

    def set_all(self, state):
        for it in self.updates:
            it.checked = state
        for iid in self.items:
            self._rerender(iid)
        self.update_selection()

    def update_selection(self):
        sel = self.checked()
        if sel:
            size = sum(i.size for i in sel)
            self.lbl_sel.config(text=f"{len(sel)} marcada(s)" + (f"  ·  {fmt_size(size)}" if size else ""))
        else:
            n = sum(1 for i in self.all_items if i.kind == "driver")
            self.lbl_sel.config(text=f"{n} dispositivos" if n else "")

    def _set_busy(self, busy):
        super()._set_busy(busy)
        self.btn_updates.config(state="disabled" if busy else "normal")

    def copy_info(self):
        lines = [f"{self.items[i].values[0]} — {self.items[i].values[2]} ({self.items[i].values[3]}) — "
                 f"{self.items[i].values[1]}"
                 for i in self._highlighted()]
        if lines:
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
            self.app.toast("Copiado para a área de transferência")

    def open_devmgmt(self):
        try:
            os.startfile("devmgmt.msc")  # type: ignore[attr-defined]
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Gerenciador de Dispositivos", str(e), parent=self)

    # ---- Windows Update
    def search_updates(self):
        if self.busy:
            return
        if not IS_WIN:
            messagebox.showinfo("Procurar atualizações",
                                "A busca de drivers usa o Windows Update e só está disponível no Windows.\n\n"
                                "No Linux, os drivers vêm junto com o kernel e são atualizados pelo "
                                "gerenciador de atualizações da sua distribuição.", parent=self)
            return
        self._set_busy(True)
        self.empty.config(text="Consultando o Windows Update…")

        def job(cancel, progress):
            progress("Consultando o Windows Update oficial… (pode levar alguns minutos)")
            return drv.search_updates()

        self.run_bg(job, self._updates_found, "Consultando o Windows Update…",
                    on_finally=lambda: self._set_busy(False))

    def _updates_found(self, res):
        res = res or {"error": "Sem resposta do Windows Update.", "updates": []}
        if res.get("error"):
            self.show_progress("Não foi possível consultar o Windows Update.")
            messagebox.showerror("Windows Update", "Não foi possível procurar atualizações de drivers.\n\n"
                                 + res["error"], parent=self)
            return
        self.updates = []
        for u in res["updates"]:
            d = u["date"]
            risky = is_risky_update(u)
            self.updates.append(Item(
                path=u["id"], size=u["size"], kind="update", checked=False,
                values=(u["title"], ("Disponível no Windows Update · ⚠ rede/Bluetooth: só se precisar" if risky
                                     else "Disponível no Windows Update")
                        + (f" · {fmt_size(u['size'])}" if u["size"] else "")
                        + (" · pede reinício" if u["reboot"] else ""), u["version"], u["date_txt"], u["maker"], u["cls"]),
                raw=(u["title"].lower(), -1, u["version"], d.toordinal() if d else 0, u["maker"].lower(), u["cls"].lower()),
                data=u))
        drivers = [i for i in self.all_items if i.kind == "driver"]
        for it in drivers:
            it.data.pop("has_update", None)
            it.values = _with_status(it.values, it.data["status"])
        self.populate(drivers)
        n = len(self.updates)
        if n:
            self.show_progress(f"{n} atualização(ões) de driver encontrada(s) no Windows Update.")
            self.app.toast(f"{n} atualização(ões) de driver encontrada(s)")
        else:
            self.show_progress("Nenhuma atualização de driver pendente no Windows Update.")
            messagebox.showinfo("Windows Update", "Nenhuma atualização de driver encontrada no Windows Update.\n\n"
                                "Segundo a Microsoft, seus drivers estão em dia. Para placas de vídeo, confira "
                                "também o aplicativo do fabricante (NVIDIA App, AMD Adrenalin ou Intel Arc/"
                                "Driver & Support Assistant).", parent=self)

    def run_action(self):
        """O LimpaOne não instala drivers: abre a tela oficial do Windows Update."""
        if not IS_WIN:
            messagebox.showinfo("Windows Update", "Disponível apenas no Windows.", parent=self)
            return
        messagebox.showinfo(
            "Atualizar drivers pelo Windows",
            "O LimpaOne não instala drivers por segurança.\n\n"
            "Vai abrir: Windows Update → Opções avançadas → Atualizações opcionais → Atualizações de driver.\n\n"
            "Dicas:\n• Só atualize se algum dispositivo estiver com problema.\n"
            "• Evite atualizar drivers de rede (Wi-Fi, cabo, Bluetooth) se a sua internet funciona.\n"
            "• Faça o “Backup dos drivers” antes.", parent=self)
        open_uri("ms-settings:windowsupdate-optionalupdates")

    def perform(self, items, to_trash, progress):
        progress(f"Baixando e instalando {len(items)} driver(s) pelo Windows Update… (não desligue o PC)")
        res = drv.install_updates([i.data["id"] for i in items])
        self._reboot = res.get("reboot", False)
        if res.get("error"):
            return [], [(i.values[0], res["error"]) for i in items[:1]], 0
        ok = set(res["ok"])
        done = [i for i in items if i.data["id"] in ok]
        errors = list(res["failed"])
        return done, errors, 0

    def success_text(self, done, freed):
        return f"{len(done)} driver(s) instalado(s) pelo Windows Update"

    def after_action(self, done, errors, freed):
        ids = {id(i) for i in done}
        self.updates = [u for u in self.updates if id(u) not in ids]
        super().after_action(done, errors, freed)
        if done and self._reboot:
            if messagebox.askyesno("Reiniciar", "Para concluir a instalação dos drivers é preciso reiniciar o "
                                   "computador.\n\nReiniciar agora? (salve seus trabalhos antes)", parent=self):
                run(["shutdown", "/r", "/t", "5"], timeout=30)
                return
        if done:
            self.start_scan()

    # ---- backup
    def backup(self):
        if self.busy:
            return
        if not IS_WIN:
            messagebox.showinfo("Backup dos drivers", "O backup de drivers só está disponível no Windows.",
                                parent=self)
            return
        folder = filedialog.askdirectory(parent=self, title="Onde salvar o backup dos drivers?")
        if not folder:
            return
        dest = os.path.join(os.path.normpath(folder), f"Backup de drivers {datetime.date.today():%Y-%m-%d}")
        if not messagebox.askyesno(
                "Backup dos drivers",
                f"Copiar todos os drivers instalados (exceto os que já vêm com o Windows) para:\n\n{dest}\n\n"
                "Isso pede permissão de administrador e pode levar alguns minutos. Guarde a pasta num pen drive "
                "ou HD externo: ela ajuda a reinstalar os drivers depois de formatar o PC.", parent=self):
            return
        self._set_busy(True)

        def job(cancel, progress):
            progress("Copiando os drivers… (pnputil /export-driver)")
            return drv.backup_drivers(dest)

        def done(res):
            res = res or {}
            if res.get("ok"):
                self.show_progress(f"Backup concluído: {res['count']} drivers em {dest}")
                self.app.toast(f"Backup concluído: {res['count']} drivers salvos")
                if messagebox.askyesno("Backup concluído", f"{res['count']} drivers foram salvos em:\n{dest}\n\n"
                                       "Para restaurar depois, use no Gerenciador de Dispositivos: “Atualizar driver” → "
                                       "“Procurar drivers no meu computador” e aponte para essa pasta.\n\n"
                                       "Abrir a pasta agora?", parent=self):
                    open_location(dest)
            else:
                self.show_progress("O backup não foi concluído.")
                messagebox.showerror("Backup dos drivers", res.get("error") or "Falha desconhecida.", parent=self)

        self.run_bg(job, done, "Fazendo backup dos drivers…", on_finally=lambda: self._set_busy(False))


# =================================================================== MEU COMPUTADOR
class SystemInfoPage(BackgroundMixin, Page):
    key, icon = "sysinfo", "monitor"
    title = "Meu computador"
    subtitle = ("A ficha técnica do seu PC: sistema, processador, memória, vídeo, discos (com a saúde de cada um), "
                "rede e bateria. Útil para saber o que dá para melhorar ou para mandar ao suporte técnico.")

    def __init__(self, master, app):
        super().__init__(master, app)
        t = self.t
        self.busy = False
        self.cancel = threading.Event()
        self.info: dict | None = None
        self._wrap_labels: list[tuple[ttk.Label, ttk.Frame]] = []
        # botões no topo
        btns = ttk.Frame(self.header_right)
        btns.pack(side="right", anchor="n", pady=(t.px(4), 0))
        self.btn_save = ttk.Button(btns, text="Salvar relatório…", command=self.save_report)
        self.btn_save.pack(side="right")
        self.btn_copy = ttk.Button(btns, text="Copiar resumo", command=self.copy_summary)
        self.btn_copy.pack(side="right", padx=t.px(8))
        self.btn_refresh = ttk.Button(btns, text="Atualizar", style="Primary.TButton", command=self.refresh)
        self.btn_refresh.pack(side="right")
        # progresso
        prog = ttk.Frame(self.body)
        prog.pack(fill="x", pady=(0, t.px(8)))
        self.lbl_progress = ttk.Label(prog, text="", style="Small.TLabel")
        self.lbl_progress.pack(side="left")
        self.pbar = ttk.Progressbar(self.body, mode="indeterminate", style="Thin.Horizontal.TProgressbar")
        # conteúdo
        self.sf = ScrollFrame(self.body, t)
        self.sf.pack(fill="both", expand=True)
        self._render_empty("Clique em “Atualizar” para ler as informações do computador.")

    # ---- ciclo de vida
    def on_show(self):
        if self.info is None and not self.busy:
            self.refresh()

    def busy_now(self):
        return self.busy

    def show_progress(self, text):
        self.lbl_progress.config(text=text)

    def _set_busy(self, busy):
        self.busy = busy
        for b in (self.btn_refresh, self.btn_copy, self.btn_save):
            b.config(state="disabled" if busy else "normal")
        if busy:
            self.pbar.pack(fill="x", pady=(0, self.t.px(8)), before=self.sf)
            self.pbar.start(12)
        else:
            self.pbar.stop()
            self.pbar.pack_forget()
        self.app.set_nav_busy(self.key, busy)

    def refresh(self):
        if self.busy:
            return
        self._set_busy(True)
        if self.info is None:
            self._render_empty("Lendo as informações do computador…\nIsso leva alguns segundos.")

        def job(cancel, progress):
            progress("Lendo as informações do hardware e do sistema…")
            return sysinfo.collect()

        def done(info):
            if info:
                self.populate(info)

        def fin():
            self._set_busy(False)
            if self.info is None:
                self._render_empty("Não foi possível ler as informações deste computador.")

        self.run_bg(job, done, "Coletando…", on_finally=fin)

    # ---- desenho
    def _clear(self):
        for w in self.sf.inner.winfo_children():
            w.destroy()
        self._wrap_labels = []

    def _render_empty(self, text):
        self._clear()
        f = card(self.sf.inner, self.t, 40, fill="x")
        _soft_icon(f, self.t, "monitor", 56).pack(pady=(0, self.t.px(14)))
        ttk.Label(f, text=text, style="Card.Muted.TLabel", justify="center").pack()

    def populate(self, info):
        self.info = info
        t = self.t
        try:
            cards = sysinfo.build_cards(info)
            top = sysinfo.hero(info)
        except Exception as e:  # noqa: BLE001
            log(f"ERRO ao montar a ficha do computador: {e}")
            self._render_empty(f"Não foi possível montar a ficha do computador.\n{e}")
            return
        self._clear()
        root = self.sf.inner
        root.columnconfigure((0, 1), weight=1, uniform="si")
        self._hero(root, top)
        cols = []
        for i in range(2):
            col = ttk.Frame(root)
            col.grid(row=1, column=i, sticky="new", padx=(0, t.px(8)) if i == 0 else (t.px(8), 0))
            cols.append(col)
        heights = [0, 0]
        for c in cards:
            k = 0 if heights[0] <= heights[1] else 1
            self._card(cols[k], c)
            heights[k] += 3 + len(c["rows"]) + sum(2 + len(b.get("rows", [])) + (1 if b.get("meter") else 0)
                                                   for b in c["blocks"]) + (2 if c.get("note") else 0)
        when = info.get("collected")
        self.show_progress(f"Atualizado às {when:%H:%M}." if when else "")
        self.sf.canvas.yview_moveto(0)

    def _hero(self, root, top):
        t = self.t
        f = card(root, t, 20)
        f.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, t.px(16)))
        head = ttk.Frame(f, style="Flat.TFrame")
        head.pack(fill="x")
        _soft_icon(head, t, "monitor", 52).pack(side="left")
        txt = ttk.Frame(head, style="Flat.TFrame")
        txt.pack(side="left", fill="x", expand=True, padx=t.px(16))
        ttk.Label(txt, text=top["title"], style="Card.H2.TLabel").pack(anchor="w")
        if top["sub"]:
            ttk.Label(txt, text=top["sub"], style="Card.Muted.TLabel").pack(anchor="w", pady=(t.px(2), 0))
        chips = ttk.Frame(f, style="Flat.TFrame")
        chips.pack(fill="x", pady=(t.px(16), 0))
        for i, (icon, label, value) in enumerate(top["chips"]):
            chips.columnconfigure(i, weight=1, uniform="chip")
            ch = ttk.Frame(chips, style="Soft.TFrame", padding=(t.px(12), t.px(10)))
            ch.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else t.px(5), 0 if i == 3 else t.px(5)))
            Icon(ch, icon, t.px(18), t.c["accent"], t.c["surface2"], 2.0).pack(side="left", anchor="n",
                                                                                 padx=(0, t.px(10)), pady=t.px(2))
            box = ttk.Frame(ch, style="Soft.TFrame")
            box.pack(side="left", fill="x", expand=True, anchor="n")
            ttk.Label(box, text=label, style="Soft.Small.TLabel").pack(anchor="w")
            val = ttk.Label(box, text=value, style="Soft.Bold.TLabel", justify="left", wraplength=t.px(180))
            val.pack(anchor="w", fill="x")
            box.bind("<Configure>", lambda e, v=val: v.config(wraplength=max(80, e.width)))

    def _card(self, parent, c):
        t = self.t
        f = card(parent, t, 18, fill="x", pady=(0, t.px(16)))
        head = ttk.Frame(f, style="Flat.TFrame")
        head.pack(fill="x")
        _soft_icon(head, t, c["icon"], 34).pack(side="left")
        ttk.Label(head, text=c["title"], style="Card.H3.TLabel").pack(side="left", padx=t.px(10))
        if c.get("badge"):
            _badge(head, t, c["badge"]).pack(side="right")
        if c["rows"]:
            self._rows(f, c["rows"], pady=(t.px(12), 0))
        for b in c["blocks"]:
            self._block(f, b)
        if c.get("note"):
            lbl = ttk.Label(f, text=c["note"], style="Card.Small.TLabel", justify="left", wraplength=t.px(380))
            lbl.pack(anchor="w", fill="x", pady=(t.px(12), 0))
            f.bind("<Configure>", lambda e, w=lbl: w.config(wraplength=max(150, e.width - t.px(40))), add="+")

    def _rows(self, parent, rows, pady=(0, 0)):
        t = self.t
        g = ttk.Frame(parent, style="Flat.TFrame")
        g.pack(fill="x", pady=pady)
        g.columnconfigure(0, minsize=t.px(110))
        g.columnconfigure(1, weight=1)
        vals = []
        for r, (k, v) in enumerate(rows):
            ttk.Label(g, text=k, style="Card.Muted.TLabel").grid(row=r, column=0, sticky="nw", pady=t.px(2),
                                                                 padx=(0, t.px(16)))
            lbl = ttk.Label(g, text=v, style="Card.Bold.TLabel", justify="left", wraplength=t.px(260))
            lbl.grid(row=r, column=1, sticky="nw", pady=t.px(2))
            vals.append(lbl)

        def wrap(e):
            w = max(120, e.width - g.grid_bbox(0, 0, 0, len(rows) - 1)[2] - t.px(20))
            for lbl in vals:
                lbl.config(wraplength=w)
        g.bind("<Configure>", wrap)
        return g

    def _block(self, parent, b):
        t = self.t
        f = ttk.Frame(parent, style="Card.TFrame", padding=(t.px(12), t.px(10)))
        f.pack(fill="x", pady=(t.px(10), 0))
        head = ttk.Frame(f, style="Flat.TFrame")
        head.pack(fill="x")
        if b.get("badge"):
            _badge(head, t, b["badge"]).pack(side="right", anchor="n")
        title = ttk.Label(head, text=b["title"], style="Card.Bold.TLabel", justify="left", wraplength=t.px(300))
        title.pack(side="left", anchor="w", fill="x", expand=True)
        head.bind("<Configure>", lambda e: title.config(wraplength=max(120, e.width - t.px(100))))
        if b.get("sub"):
            ttk.Label(f, text=b["sub"], style="Card.Small.TLabel").pack(anchor="w")
        if b.get("meter"):
            frac, tone, text = b["meter"]
            ttk.Progressbar(f, maximum=100, value=frac * 100, style=BAR_STYLE.get(tone, "Horizontal.TProgressbar")
                            ).pack(fill="x", pady=(t.px(8), t.px(2)))
            ttk.Label(f, text=text, style="Card.Small.TLabel").pack(anchor="w")
        if b.get("rows"):
            self._rows(f, b["rows"], pady=(t.px(6), 0))

    # ---- exportação
    def copy_summary(self):
        if not self.info:
            messagebox.showinfo("Copiar resumo", "Aguarde a leitura das informações.", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append(sysinfo.summary_text(self.info))
        self.app.toast("Resumo copiado — é só colar (Ctrl+V) onde quiser")

    def save_report(self):
        if not self.info:
            messagebox.showinfo("Salvar relatório", "Aguarde a leitura das informações.", parent=self)
            return
        name = (self.info.get("os") or {}).get("computer") or "computador"
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".html", initialfile=f"Ficha do {name} - {datetime.date.today():%Y-%m-%d}.html",
            filetypes=[("Página HTML (abre no navegador)", "*.html"), ("Texto simples", "*.txt")])
        if not path:
            return
        try:
            text = sysinfo.summary_text(self.info) if path.lower().endswith(".txt") else sysinfo.report_html(self.info)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:
            messagebox.showerror("Salvar relatório", f"Não foi possível salvar o arquivo:\n{e}", parent=self)
            return
        self.app.toast(f"Relatório salvo: {os.path.basename(path)}")
