"""Páginas de otimização: limpeza do registro, ajustes do Windows, otimização de discos e destruidor
de arquivos."""
from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import diskopt
from . import regclean as rc
from . import shredder as sh
from . import tweaks as tw
from .pages import BackgroundMixin, Page, ResultsPage
from .theme import draw_icon
from .utils import IS_WIN, fixed_drives, fmt_date, fmt_size, is_admin, is_protected, open_location
from .widgets import ScrollFrame, card


def _soft_icon(master, t, name, size=40, bg_key="surface", fg=None, soft=None):
    """Ícone num círculo suave (mesmo visual dos cards do Painel/Ferramentas)."""
    c = t.c
    s = t.px(size)
    cv = tk.Canvas(master, width=s, height=s, bg=c[bg_key], highlightthickness=0, bd=0)
    cv.create_oval(0, 0, s, s, fill=soft or c["accent_soft"], outline="")
    draw_icon(cv, name, s * 0.25, s * 0.25, s * 0.5, fg or c["accent"], 2.0, bg=soft or c["accent_soft"])
    return cv


def _sep(master, t, pady=10):
    f = ttk.Frame(master, style="Sep.TFrame", height=1)
    f.pack(fill="x", pady=t.px(pady))
    return f


def _wrap(label, minimum=200, extra=0):
    """Faz o texto de um rótulo quebrar conforme a largura disponível."""
    label.bind("<Configure>", lambda e: label.configure(wraplength=max(minimum, e.width - extra)))


def _windows_only(master, t, what):
    f = card(master, t, 22, fill="x")
    row = ttk.Frame(f, style="Flat.TFrame")
    row.pack(fill="x")
    _soft_icon(row, t, "info", 40).pack(side="left", anchor="n")
    txt = ttk.Frame(row, style="Flat.TFrame")
    txt.pack(side="left", fill="x", expand=True, padx=t.px(14))
    ttk.Label(txt, text="Disponível no Windows", style="Card.H3.TLabel").pack(anchor="w")
    lbl = ttk.Label(txt, text=what, style="Card.Muted.TLabel", justify="left")
    lbl.pack(anchor="w", fill="x", pady=(t.px(4), 0))
    _wrap(lbl)
    return f


# =================================================================== LIMPEZA DO REGISTRO
class RegistryPage(ResultsPage):
    key, icon = "registry", "database"
    title = "Limpeza do registro"
    subtitle = ("Procura só entradas comprovadamente quebradas: referências a programas e arquivos que não "
                "existem mais. Antes de corrigir, tudo o que será alterado é salvo num backup .reg — dá para "
                "desfazer a qualquer momento.")
    columns = [("Categoria", 170, "w"), ("Entrada", 230, "w"), ("Problema", 240, "w"), ("Local", 560, "w")]
    scan_label = "Procurar problemas"
    action_label = "Corrigir selecionados"
    action_style = "Primary.TButton"
    uses_trash = False
    show_open = False

    def __init__(self, master, app):
        if not IS_WIN:
            self.empty_text = ("A limpeza do registro está disponível no Windows.\n"
                               "Neste sistema não existe registro para analisar.")
        self._last_backup = None
        super().__init__(master, app)
        self.menu.add_separator()
        self.menu.add_command(label="Abrir pasta de backups", command=lambda: open_location(rc.backup_dir()))
        if not IS_WIN:
            self.btn_scan.config(state="disabled")
            self.btn_action.config(state="disabled")

    def _set_busy(self, busy):
        super()._set_busy(busy)
        if not IS_WIN:
            self.btn_scan.config(state="disabled")
            self.btn_action.config(state="disabled")

    def build_options(self, f):
        self.cat_vars = {k: tk.BooleanVar(value=True) for k, _ in rc.CATEGORIES}
        ttk.Label(f, text="Procurar em", style="Card.TLabel").pack(side="left")
        self.btn_cats = ttk.Button(f, text="", command=self._cats_menu)
        self.btn_cats.pack(side="left", padx=(self.t.px(8), 0))
        self.cat_menu = tk.Menu(self, tearoff=0)
        for k, label in rc.CATEGORIES:
            self.cat_menu.add_checkbutton(label=label, variable=self.cat_vars[k], command=self._cats_label)
        self._cats_label()

    def _cats_label(self):
        n = sum(v.get() for v in self.cat_vars.values())
        total = len(self.cat_vars)
        self.btn_cats.config(text=f"Todas as categorias ({total})  ▾" if n == total else
                             f"{n} de {total} categorias  ▾")

    def _cats_menu(self):
        b = self.btn_cats
        try:
            self.cat_menu.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())
        finally:
            self.cat_menu.grab_release()

    def build_actions(self, f):
        ttk.Button(f, text="Restaurar um backup…", command=self.restore).pack(side="left")

    def get_params(self):
        cats = [k for k, v in self.cat_vars.items() if v.get()]
        if not cats:
            messagebox.showinfo("Categorias", "Escolha pelo menos uma categoria para analisar.", parent=self)
            return None
        return {"cats": cats}

    def scan_job(self, p, cancel, progress):
        if not IS_WIN:
            progress("Disponível apenas no Windows.")
            return []
        return rc.scan_registry(rc.WinRegReader(), p["cats"], cancel, progress)

    def row_tags(self, item):
        return ("warn",) if item.data.get("hive") == "HKLM" and not is_admin() else ()

    def validate(self, items):
        lm = [i for i in items if i.data.get("hive") == "HKLM"]
        if lm and IS_WIN and not is_admin():
            return messagebox.askyesno(
                "Permissão de administrador",
                f"{len(lm)} entrada(s) ficam em HKEY_LOCAL_MACHINE e só podem ser corrigidas com o LimpaOne "
                "aberto como administrador (destacadas em laranja). Elas serão puladas.\n\nContinuar mesmo assim?",
                parent=self)
        return True

    def confirm_text(self, items, to_trash):
        cats: dict = {}
        for i in items:
            cats[i.values[0]] = cats.get(i.values[0], 0) + 1
        lines = "\n".join(f"• {k}: {v}" for k, v in sorted(cats.items()))
        return (f"Corrigir {len(items)} entrada(s) inválida(s) do registro?\n\n{lines}\n\n"
                "Antes de qualquer alteração, um backup .reg com todas as chaves envolvidas será salvo. "
                "Para desfazer, use “Restaurar um backup…”.")

    def perform(self, items, to_trash, progress):
        done, errors, backup = rc.fix_items(items, progress, self.cancel)
        self._last_backup = backup
        return done, errors, 0

    def success_text(self, done, freed):
        return f"{len(done)} entrada(s) corrigida(s) · backup salvo em “{os.path.basename(self._last_backup or '')}”"

    def restore(self):
        if not IS_WIN:
            messagebox.showinfo("Restaurar backup", "Disponível apenas no Windows.", parent=self)
            return
        path = filedialog.askopenfilename(parent=self, title="Escolha o backup do registro",
                                          initialdir=rc.backup_dir(), filetypes=[("Backup do registro", "*.reg")])
        if not path:
            return
        if not messagebox.askyesno("Restaurar backup",
                                   f"Importar “{os.path.basename(path)}” de volta para o registro?\n\n"
                                   "As entradas removidas voltarão a existir exatamente como estavam.",
                                   parent=self):
            return

        def done(res):
            ok, msg = res
            if ok:
                self.app.toast("Backup do registro restaurado")
            else:
                messagebox.showerror("Restaurar backup", f"Não foi possível restaurar:\n{msg}", parent=self)

        self.run_bg(lambda c, p: rc.restore_backup(path), done, "Restaurando backup…")


# =================================================================== OTIMIZAR WINDOWS
class TweaksPage(BackgroundMixin, Page):
    key, icon = "tweaks", "rocket"
    title = "Otimizar Windows"
    subtitle = ("Ajustes seguros e reversíveis de desempenho, privacidade e conveniência. Ligue ou desligue "
                "cada um quando quiser: o valor original fica guardado para desfazer.")

    def __init__(self, master, app):
        super().__init__(master, app)
        t = self.t
        self.cancel = threading.Event()
        self.store = tw.default_store()
        self.busy = False
        self.vars: dict[str, tk.BooleanVar] = {}
        self.checks: dict[str, ttk.Checkbutton] = {}
        self.pending: set[str] = set()
        self._power = None

        self.sf = sf = ScrollFrame(self.body, t)
        sf.pack(fill="both", expand=True)
        root = sf.inner

        # ---- resumo e ações
        top = card(root, t, 18, fill="x", pady=(0, t.px(14)))
        row = ttk.Frame(top, style="Flat.TFrame")
        row.pack(fill="x")
        _soft_icon(row, t, "rocket", 44).pack(side="left")
        mid = ttk.Frame(row, style="Flat.TFrame")
        mid.pack(side="left", fill="x", expand=True, padx=t.px(14))
        self.lbl_summary = ttk.Label(mid, text="", style="Card.H3.TLabel")
        self.lbl_summary.pack(anchor="w")
        self.lbl_summary_sub = ttk.Label(mid, text="", style="Card.Small.TLabel")
        self.lbl_summary_sub.pack(anchor="w", pady=(t.px(2), 0))
        self.btn_rec = ttk.Button(row, text="Aplicar recomendados", style="Primary.TButton",
                                  command=self.apply_recommended)
        self.btn_rec.pack(side="right")
        self.btn_undo = ttk.Button(row, text="Desfazer tudo", command=self.undo_all)
        self.btn_undo.pack(side="right", padx=t.px(8))
        self.pbar = ttk.Progressbar(top, mode="indeterminate", style="Thin.Horizontal.TProgressbar")

        # aviso de reinício (aparece quando necessário)
        self.notice = tk.Frame(root, bg=t.c["warning_soft"])
        self.lbl_notice = tk.Label(self.notice, text="", bg=t.c["warning_soft"], fg=t.c["text"], font=t.f_base,
                                   justify="left", anchor="w")
        self.lbl_notice.pack(side="left", fill="x", expand=True, padx=t.px(14), pady=t.px(10))
        self.btn_explorer = ttk.Button(self.notice, text="Reiniciar Explorer", command=self.restart_explorer)
        self.btn_explorer.pack(side="right", padx=t.px(12), pady=t.px(8))
        self._notice_anchor = ttk.Frame(root, height=1)
        self._notice_anchor.pack(fill="x")

        self.win_only = None
        if not IS_WIN:
            self.win_only = _windows_only(root, t, "Estes ajustes alteram configurações do Windows. Neste sistema "
                                                   "você pode ver a lista, mas nada será alterado.")
            self.win_only.pack(fill="x", pady=(0, t.px(14)))

        # ---- plano de energia
        self._build_power(root)

        # ---- grupos
        for group in tw.GROUPS:
            self._build_group(root, group)

        self.refresh()

    # ---------------------------------------------------------------- construção
    def _build_power(self, root):
        t = self.t
        f = card(root, t, 18, fill="x", pady=(0, t.px(14)))
        head = ttk.Frame(f, style="Flat.TFrame")
        head.pack(fill="x")
        _soft_icon(head, t, "power", 34).pack(side="left")
        txt = ttk.Frame(head, style="Flat.TFrame")
        txt.pack(side="left", fill="x", expand=True, padx=t.px(12))
        ttk.Label(txt, text="Plano de energia", style="Card.H3.TLabel").pack(anchor="w")
        ttk.Label(txt, text="Desempenho máximo do processador. Em notebooks gasta mais bateria.",
                  style="Card.Small.TLabel").pack(anchor="w")
        self.lbl_power = ttk.Label(head, text="", style="Badge.TLabel")
        self.lbl_power.pack(side="right")
        _sep(f, t, 12)
        btns = ttk.Frame(f, style="Flat.TFrame")
        btns.pack(fill="x")
        self.power_btns = {}
        for k, label, style in (("high", "Alto desempenho", "TButton"), ("ultimate", "Desempenho máximo", "TButton"),
                                ("balanced", "Voltar ao Equilibrado", "Ghost.TButton")):
            b = ttk.Button(btns, text=label, style=style, command=lambda k=k: self.set_power(k))
            b.pack(side="left", padx=(0, t.px(8)))
            self.power_btns[k] = b
        hint = ttk.Label(f, text="“Desempenho máximo” é um plano escondido do Windows: o LimpaOne cria e ativa para "
                                 "você. Em notebooks com “Modern Standby” só o Equilibrado está disponível.",
                         style="Card.Small.TLabel", justify="left", wraplength=t.px(600))
        hint.pack(anchor="w", fill="x", pady=(t.px(10), 0))
        _wrap(hint)

    def _build_group(self, root, group):
        t = self.t
        icon, desc = tw.GROUP_INFO[group]
        f = card(root, t, 18, fill="x", pady=(0, t.px(14)))
        head = ttk.Frame(f, style="Flat.TFrame")
        head.pack(fill="x")
        _soft_icon(head, t, icon, 34).pack(side="left")
        txt = ttk.Frame(head, style="Flat.TFrame")
        txt.pack(side="left", fill="x", expand=True, padx=t.px(12))
        ttk.Label(txt, text=group, style="Card.H3.TLabel").pack(anchor="w")
        ttk.Label(txt, text=desc, style="Card.Small.TLabel").pack(anchor="w")
        items = [x for x in tw.TWEAKS if x.group == group]
        for tweak in items:
            _sep(f, t, 10)
            row = ttk.Frame(f, style="Flat.TFrame")
            row.pack(fill="x")
            var = tk.BooleanVar(value=False)
            self.vars[tweak.id] = var
            cb = ttk.Checkbutton(row, variable=var, style="Card.TCheckbutton",
                                 command=lambda tid=tweak.id: self.toggle(tid))
            cb.pack(side="left", anchor="n", pady=(t.px(1), 0))
            self.checks[tweak.id] = cb
            badges = ttk.Frame(row, style="Flat.TFrame")
            badges.pack(side="right", anchor="n")
            if tweak.recommended:
                ttk.Label(badges, text="Recomendado", style="BadgeOk.TLabel").pack(side="right", padx=(t.px(6), 0))
            if tweak.admin:
                ttk.Label(badges, text="Precisa de admin", style="BadgeWarn.TLabel").pack(side="right",
                                                                                          padx=(t.px(6), 0))
            if tweak.restart:
                ttk.Label(badges, text=tw.RESTART_TEXT[tweak.restart], style="Badge.TLabel").pack(
                    side="right", padx=(t.px(6), 0))
            body = ttk.Frame(row, style="Flat.TFrame")
            body.pack(side="left", fill="x", expand=True, padx=(t.px(2), t.px(12)))
            title = ttk.Label(body, text=tweak.title, style="Card.Bold.TLabel", cursor="hand2")
            title.pack(anchor="w")
            title.bind("<Button-1>", lambda e, cb=cb: cb.invoke())
            d = tweak.desc + (f" {tweak.note}" if tweak.note else "")
            lbl = ttk.Label(body, text=d, style="Card.Muted.TLabel", justify="left")
            lbl.pack(anchor="w", fill="x", pady=(t.px(2), 0))
            _wrap(lbl)

    # ---------------------------------------------------------------- estado
    @property
    def backup(self) -> dict:
        b = self.app.settings.get("tweaks_backup")
        if not isinstance(b, dict):
            b = {}
            self.app.settings["tweaks_backup"] = b
        return b

    def on_show(self):
        self.refresh()
        if IS_WIN and not self.busy:
            self.run_bg(lambda c, p: tw.power_status(self.app.settings), self._power_done, "Lendo plano de energia…")

    def refresh(self):
        n_on = 0
        for tweak in tw.TWEAKS:
            on = bool(self.store) and tw.is_applied(self.store, tweak)
            n_on += on
            self.vars[tweak.id].set(on)
            state = "normal" if self.store and not self.busy else "disabled"
            self.checks[tweak.id].state(["!disabled"] if state == "normal" else ["disabled"])
        total = len(tw.TWEAKS)
        if self.store:
            self.lbl_summary.config(text=f"{n_on} de {total} ajustes aplicados")
            self.lbl_summary_sub.config(text="Tudo é reversível: o valor original de cada ajuste fica guardado.")
        else:
            self.lbl_summary.config(text=f"{total} ajustes disponíveis")
            self.lbl_summary_sub.config(text="Disponível no Windows.")
        for b in (self.btn_rec, self.btn_undo, *self.power_btns.values()):
            b.config(state="normal" if self.store and not self.busy else "disabled")
        if self.win_only is not None and self.store:
            self.win_only.pack_forget()
        self._render_notice()
        self._render_power()

    def _render_power(self):
        if not IS_WIN and not self._power:
            self.lbl_power.config(text="Disponível no Windows")
            return
        p = self._power or {}
        name = tw.POWER_PLANS[p["active"]][1] if p.get("active") else p.get("active_name") or "—"
        self.lbl_power.config(text=f"Atual: {name}")

    def _power_done(self, status):
        self._power = status
        self._render_power()

    def _render_notice(self):
        kinds = {tw.TWEAK_BY_ID[i].restart for i in self.pending if tw.TWEAK_BY_ID[i].restart}
        if not kinds:
            self.notice.pack_forget()
            return
        parts = []
        if "explorer" in kinds:
            parts.append("Algumas mudanças só aparecem depois de reiniciar o Explorer (a barra de tarefas pisca "
                         "por um instante; janelas de pastas abertas serão fechadas).")
        if "logoff" in kinds:
            parts.append("Outras valem depois de sair e entrar de novo na sua conta.")
        if "reboot" in kinds:
            parts.append("A telemetria muda totalmente após reiniciar o computador.")
        self.lbl_notice.config(text=" ".join(parts), wraplength=self.t.px(640))
        if "explorer" in kinds:
            self.btn_explorer.pack(side="right", padx=self.t.px(12), pady=self.t.px(8))
        else:
            self.btn_explorer.pack_forget()
        self.notice.pack(fill="x", pady=(0, self.t.px(14)), after=self._notice_anchor)

    def _set_busy(self, busy):
        self.busy = busy
        if busy:
            self.pbar.pack(fill="x", pady=(self.t.px(12), 0))
            self.pbar.start(12)
        else:
            self.pbar.stop()
            self.pbar.pack_forget()
        self.app.set_nav_busy(self.key, busy)
        self.refresh()

    def busy_now(self):
        return self.busy

    # ---------------------------------------------------------------- ações
    def _run(self, changes, success):
        """changes: [(tweak, aplicar?)]"""
        if not self.store:
            messagebox.showinfo(self.title, "Disponível apenas no Windows.", parent=self)
            self.refresh()
            return
        if not changes:
            self.refresh()
            return
        backup = self.backup

        def job(cancel, progress):
            errors = []
            for tweak, on in changes:
                progress(f"{'Aplicando' if on else 'Desfazendo'}: {tweak.title}")
                try:
                    (tw.apply_tweak if on else tw.undo_tweak)(self.store, tweak, backup)
                except Exception as e:  # noqa: BLE001
                    errors.append(f"• {tweak.title}: {e}")
            return errors

        def done(errors):
            self.app.settings.save()
            ok = len(changes) - len(errors)
            for tweak, on in changes:
                self.pending.add(tweak.id)
            if ok:
                self.app.toast(success if len(changes) > 1 else
                               f"{'Aplicado' if changes[0][1] else 'Desfeito'}: {changes[0][0].title}")
            if errors:
                messagebox.showwarning(self.title, "Alguns ajustes não puderam ser alterados:\n\n" + "\n".join(errors) +
                                       "\n\nAjustes marcados como “Precisa de admin” pedem permissão do Windows.",
                                       parent=self)

        self._set_busy(True)
        self.run_bg(job, done, "Aplicando…", on_finally=lambda: self._set_busy(False))

    def toggle(self, tid):
        if self.busy:
            return
        tweak = tw.TWEAK_BY_ID[tid]
        self._run([(tweak, self.vars[tid].get())], "")

    def apply_recommended(self):
        if not self.store:
            return
        todo = [(x, True) for x in tw.TWEAKS if x.recommended and not tw.is_applied(self.store, x)]
        if not todo:
            self.app.toast("Todos os ajustes recomendados já estão aplicados.")
            return
        names = "\n".join(f"• {x.title}" for x, _ in todo)
        admin = any(x.admin for x, _ in todo) and not is_admin()
        msg = f"Aplicar {len(todo)} ajuste(s) recomendado(s)?\n\n{names}"
        if admin:
            msg += "\n\nAlguns precisam de permissão de administrador: o Windows vai pedir confirmação."
        if messagebox.askyesno("Aplicar recomendados", msg, parent=self):
            self._run(todo, f"{len(todo)} ajuste(s) aplicado(s)")

    def undo_all(self):
        if not self.store:
            return
        todo = [(x, False) for x in tw.TWEAKS if x.id in self.backup or tw.is_applied(self.store, x)]
        if not todo:
            self.app.toast("Não há ajustes para desfazer.")
            return
        if messagebox.askyesno("Desfazer tudo", f"Voltar {len(todo)} ajuste(s) aos valores originais?",
                               parent=self):
            self._run(todo, f"{len(todo)} ajuste(s) desfeito(s)")

    def set_power(self, kind):
        def done(label):
            self.app.toast(f"Plano de energia: {label}")
            self.run_bg(lambda c, p: tw.power_status(self.app.settings), self._power_done)

        self.run_bg(lambda c, p: tw.set_power_plan(kind, self.app.settings), done, "Alterando plano de energia…")

    def restart_explorer(self):
        if not messagebox.askyesno("Reiniciar Explorer", "A barra de tarefas e as janelas de pastas vão fechar e "
                                   "abrir de novo em alguns segundos. Seus programas continuam abertos.\n\n"
                                   "Continuar?", parent=self):
            return
        try:
            tw.restart_explorer()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Reiniciar Explorer", str(e), parent=self)
            return
        self.pending = {i for i in self.pending if tw.TWEAK_BY_ID[i].restart != "explorer"}
        self._render_notice()
        self.app.toast("Explorer reiniciado")


# =================================================================== OTIMIZAR DISCOS
class DiskOptimizePage(BackgroundMixin, Page):
    key, icon = "diskopt", "drive"
    title = "Otimizar discos"
    subtitle = ("O Windows escolhe o tratamento certo para cada disco: em SSDs faz o TRIM (avisa o disco sobre "
                "o espaço livre, mantendo-o rápido); em HDs desfragmenta (junta os pedaços dos arquivos). "
                "SSDs nunca são desfragmentados.")

    def __init__(self, master, app):
        super().__init__(master, app)
        t = self.t
        self.cancel = threading.Event()
        self.busy = False
        self.volumes: list[dict] = []
        self._loaded = False
        self.btn_refresh = ttk.Button(self.header_right, text="Atualizar", command=self.load)
        self.btn_refresh.pack(side="right", anchor="s", pady=(t.px(10), 0))

        foot = ttk.Frame(self.body)
        foot.pack(side="bottom", fill="x", pady=(t.px(12), 0))
        self.btn_all = ttk.Button(foot, text="Otimizar todos", style="Primary.TButton", command=self.optimize_all)
        self.btn_all.pack(side="right")
        self.btn_analyze = ttk.Button(foot, text="Analisar fragmentação (HDs)", command=self.analyze_all)
        self.btn_analyze.pack(side="right", padx=t.px(8))
        self.lbl_status = ttk.Label(foot, text="", style="Small.TLabel")
        self.lbl_status.pack(side="left")
        self.pbar = ttk.Progressbar(self.body, mode="indeterminate", style="Thin.Horizontal.TProgressbar")

        sf = ScrollFrame(self.body, t)
        sf.pack(fill="both", expand=True)
        self.list = sf.inner
        self.render()

    def on_show(self):
        if not self._loaded and IS_WIN:
            self.load()

    def busy_now(self):
        return self.busy

    def show_progress(self, text):
        self.lbl_status.config(text=text)

    def _set_busy(self, busy):
        self.busy = busy
        st = "disabled" if busy or not IS_WIN else "normal"
        for b in (self.btn_all, self.btn_analyze, self.btn_refresh):
            b.config(state=st)
        if busy:
            self.pbar.pack(fill="x", pady=(0, self.t.px(8)), before=self.list.master.master)
            self.pbar.start(12)
        else:
            self.pbar.stop()
            self.pbar.pack_forget()
        self.app.set_nav_busy(self.key, busy)
        self.render()

    def load(self):
        if self.busy:
            return
        self._loaded = True
        self._set_busy(True)
        self.run_bg(lambda c, p: diskopt.list_volumes(), self.populate, "Lendo discos…",
                    on_finally=lambda: self._set_busy(False))

    def populate(self, vols):
        old = {v["letter"]: v for v in self.volumes}
        self.volumes = list(vols or [])
        for v in self.volumes:   # mantém a análise já feita
            if v["letter"] in old and v.get("frag") is None:
                v["frag"], v["frag_msg"] = old[v["letter"]].get("frag"), old[v["letter"]].get("frag_msg", "")
        n = len(self.volumes)
        self.show_progress(f"{n} unidade(s) encontrada(s)." if n else "Nenhuma unidade encontrada.")
        self.render()

    # ---------------------------------------------------------------- desenho
    def render(self):
        t = self.t
        for w in self.list.winfo_children():
            w.destroy()
        if not IS_WIN and not self.volumes:
            for b in (self.btn_all, self.btn_analyze, self.btn_refresh):
                b.config(state="disabled")
            _windows_only(self.list, t, "A otimização de discos usa o “Otimizador de unidades” do Windows. "
                                        "Em Linux e macOS os sistemas de arquivos modernos dispensam desfragmentação "
                                        "e o TRIM é feito automaticamente.")
            return
        if not self.volumes:
            f = card(self.list, t, 22, fill="x")
            ttk.Label(f, text="Lendo discos…" if self.busy else "Clique em “Atualizar” para listar os discos.",
                      style="Card.Muted.TLabel").pack(anchor="w")
            return
        for v in self.volumes:
            f = card(self.list, t, 16, fill="x", pady=(0, t.px(12)))
            row = ttk.Frame(f, style="Flat.TFrame")
            row.pack(fill="x")
            ssd = v["kind"] == "SSD"
            _soft_icon(row, t, "bolt" if ssd else "drive", 44).pack(side="left", anchor="n")
            mid = ttk.Frame(row, style="Flat.TFrame")
            mid.pack(side="left", fill="x", expand=True, padx=t.px(14))
            top = ttk.Frame(mid, style="Flat.TFrame")
            top.pack(fill="x")
            name = v["label"] or ("Disco local" if not v.get("removable") else "Unidade removível")
            ttk.Label(top, text=f"{name} ({v['letter']}:)", style="Card.H3.TLabel").pack(side="left")
            kind_txt = {"SSD": "SSD", "HD": "HD"}.get(v["kind"], "Tipo desconhecido")
            ttk.Label(top, text=kind_txt, style="Badge.TLabel" if v["kind"] != "?" else "BadgeWarn.TLabel").pack(
                side="left", padx=(t.px(10), 0))
            if v.get("fs"):
                ttk.Label(top, text=v["fs"], style="Card.Small.TLabel").pack(side="left", padx=(t.px(8), 0))
            sub = " · ".join(x for x in (v.get("model"), v.get("bus")) if x)
            if sub:
                ttk.Label(mid, text=sub, style="Card.Small.TLabel").pack(anchor="w", pady=(t.px(2), 0))
            used = max(0, v["size"] - v["free"])
            pct = used / v["size"] if v["size"] else 0
            bar_style = ("Danger." if pct > .92 else "Warning." if pct > .8 else "") + "Horizontal.TProgressbar"
            pb = ttk.Progressbar(mid, maximum=1.0, value=pct, style=bar_style)
            pb.pack(fill="x", pady=(t.px(8), t.px(4)))
            ttk.Label(mid, text=f"{fmt_size(v['free'])} livres de {fmt_size(v['size'])}",
                      style="Card.Small.TLabel").pack(anchor="w")

            # colunas de informação
            info = ttk.Frame(row, style="Flat.TFrame")
            info.pack(side="left", padx=(t.px(8), t.px(18)), anchor="n")
            self._field(info, "Última otimização", fmt_date(v["last"]) if v.get("last") else "Sem registro")
            if ssd:
                frag, tone = "Não se aplica (SSD)", "Card.Muted.TLabel"
            elif v.get("frag") is not None:
                frag = f"{v['frag']:.0f}%".replace(".", ",") + (f" · {v['frag_msg']}" if v.get("frag_msg") else "")
                tone = "Card.Warning.TLabel" if v["frag"] >= 10 else "Card.Success.TLabel"
            else:
                frag, tone = v.get("frag_msg") or "Não analisado", "Card.Muted.TLabel"
            self._field(info, "Fragmentação", frag, tone)

            btns = ttk.Frame(row, style="Flat.TFrame")
            btns.pack(side="right", anchor="center")
            st = "disabled" if self.busy or not IS_WIN else "normal"
            ttk.Button(btns, text="Otimizar", style="Primary.TButton", state=st,
                       command=lambda v=v: self.optimize([v])).pack(fill="x")
            if not ssd:
                ttk.Button(btns, text="Analisar", state=st, command=lambda v=v: self.analyze([v])).pack(
                    fill="x", pady=(t.px(6), 0))
        has_hd = any(v["kind"] != "SSD" for v in self.volumes)
        self.btn_analyze.config(state="normal" if has_hd and IS_WIN and not self.busy else "disabled")
        note = ttk.Label(self.list, text="Otimizar e analisar pedem permissão de administrador. A otimização de um HD "
                                         "grande pode levar mais de uma hora; você pode continuar usando o computador.",
                         style="Small.TLabel", justify="left")
        note.pack(anchor="w", fill="x", pady=(t.px(2), 0))
        _wrap(note)

    def _field(self, master, label, value, style="Card.Bold.TLabel"):
        f = ttk.Frame(master, style="Flat.TFrame")
        f.pack(anchor="w", pady=(0, self.t.px(6)))
        ttk.Label(f, text=label.upper(), style="Card.Small.TLabel").pack(anchor="w")
        ttk.Label(f, text=value, style=style).pack(anchor="w")

    # ---------------------------------------------------------------- ações
    def analyze_all(self):
        self.analyze([v for v in self.volumes if v["kind"] != "SSD"])

    def analyze(self, vols):
        if self.busy or not vols:
            return
        letters = [v["letter"] for v in vols]

        def done(res):
            for v in self.volumes:
                if v["letter"] in res:
                    v["frag"], v["frag_msg"] = res[v["letter"]]
            self.render()
            self.app.toast("Análise concluída")

        self._set_busy(True)
        self.run_bg(lambda c, p: diskopt.analyze_fragmentation(letters), done,
                    f"Analisando {', '.join(x + ':' for x in letters)}… (pode levar alguns minutos)",
                    on_finally=lambda: self._set_busy(False))

    def optimize_all(self):
        self.optimize(list(self.volumes))

    def optimize(self, vols):
        if self.busy or not vols:
            return
        lines = []
        for v in vols:
            what = {"SSD": "TRIM (SSD)", "HD": "desfragmentação (HD)"}.get(v["kind"], "o Windows escolhe o método")
            lines.append(f"• {v['letter']}: — {what}")
        if not messagebox.askyesno("Otimizar discos", "Otimizar estas unidades?\n\n" + "\n".join(lines) +
                                   "\n\nO Windows vai pedir permissão de administrador. Em HDs pode demorar bastante.",
                                   parent=self):
            return
        pairs = [(v["letter"], v["kind"]) for v in vols]

        def done(res):
            ok = [k for k, (good, _) in res.items() if good]
            bad = [(k, err) for k, (good, err) in res.items() if not good]
            if ok:
                self.app.toast(f"Otimização concluída: {', '.join(k + ':' for k in sorted(ok))}")
            if bad:
                messagebox.showwarning("Otimizar discos", "Algumas unidades não foram otimizadas:\n\n" +
                                       "\n".join(f"• {k}: {e or 'erro desconhecido'}" for k, e in bad), parent=self)
            for v in self.volumes:
                if v["letter"] in ok and v["kind"] != "SSD":
                    v["frag"], v["frag_msg"] = None, "Otimizado agora"
            self._loaded = False
            self.load()

        self._set_busy(True)
        self.run_bg(lambda c, p: diskopt.optimize_volumes(pairs), done,
                    "Otimizando… acompanhe aqui. Não desligue o computador.",
                    on_finally=lambda: self._set_busy(False))


# =================================================================== DESTRUIDOR DE ARQUIVOS
class ConfirmTyped(tk.Toplevel):
    """Confirmação forte: o usuário precisa digitar uma palavra."""

    def __init__(self, parent, t, title, message, word="DESTRUIR"):
        super().__init__(parent)
        c = t.c
        self.result = False
        self.word = word
        self.title(title)
        self.configure(bg=c["surface"])
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        f = ttk.Frame(self, style="Flat.TFrame", padding=t.px(22))
        f.pack(fill="both", expand=True)
        head = ttk.Frame(f, style="Flat.TFrame")
        head.pack(fill="x")
        _soft_icon(head, t, "eraser", 40, fg=c["danger"], soft=c["danger_soft"]).pack(side="left", anchor="n")
        ttk.Label(head, text=title, style="Card.H3.TLabel").pack(side="left", padx=t.px(12))
        ttk.Label(f, text=message, style="Card.TLabel", justify="left", wraplength=t.px(440)).pack(
            anchor="w", pady=(t.px(14), t.px(12)))
        ttk.Label(f, text=f"Para confirmar, digite {word}:", style="Card.Bold.TLabel").pack(anchor="w")
        self.var = tk.StringVar()
        ent = ttk.Entry(f, textvariable=self.var, width=30)
        ent.pack(anchor="w", fill="x", pady=(t.px(6), t.px(16)))
        btns = ttk.Frame(f, style="Flat.TFrame")
        btns.pack(fill="x")
        self.ok = ttk.Button(btns, text="Destruir para sempre", style="Danger.TButton", command=self._ok,
                             state="disabled")
        self.ok.pack(side="right")
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="right", padx=t.px(8))
        self.var.trace_add("write", lambda *a: self.ok.config(
            state="normal" if self.var.get().strip().upper() == word else "disabled"))
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self._ok())
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(0, px)}+{max(0, py)}")
        ent.focus_set()
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _ok(self):
        if self.var.get().strip().upper() == self.word:
            self.result = True
            self.destroy()

    @classmethod
    def ask(cls, parent, t, title, message, word="DESTRUIR") -> bool:
        d = cls(parent, t, title, message, word)
        parent.wait_window(d)
        return d.result


class ShredderPage(BackgroundMixin, Page):
    key, icon = "shredder", "eraser"
    title = "Destruidor de arquivos"
    subtitle = ("Apaga arquivos de forma irreversível: o conteúdo é sobrescrito, o nome é trocado por um "
                "aleatório e só então o arquivo é removido — nem programas de recuperação conseguem trazê-lo "
                "de volta. Não passa pela Lixeira.")
    columns = [("Nome", 220, "w"), ("Tipo", 70, "w"), ("Tamanho", 90, "e"), ("Local", 300, "w")]

    def __init__(self, master, app):
        super().__init__(master, app)
        t, c = self.t, self.t.c
        self.cancel = threading.Event()
        self.busy = False
        self.paths: list[str] = []
        self.sizes: dict[str, int] = {}

        cols = ttk.Frame(self.body)
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=1)
        cols.columnconfigure(1, weight=0, minsize=t.px(310))
        cols.rowconfigure(0, weight=1)

        # ---------------------------------------------------------- lista
        left = card(cols, t, 16)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, t.px(14)))
        bar = ttk.Frame(left, style="Flat.TFrame")
        bar.pack(fill="x")
        ttk.Label(bar, text="Itens para destruir", style="Card.H3.TLabel").pack(side="left")
        self.btn_clear = ttk.Button(bar, text="Limpar lista", style="Ghost.TButton", command=self.clear)
        self.btn_clear.pack(side="right")
        self.btn_remove = ttk.Button(bar, text="Remover", style="Ghost.TButton", command=self.remove)
        self.btn_remove.pack(side="right")
        add = ttk.Frame(left, style="Flat.TFrame")
        add.pack(fill="x", pady=(t.px(10), t.px(10)))
        self.btn_add_files = ttk.Button(add, text="Adicionar arquivos…", command=self.add_files)
        self.btn_add_files.pack(side="left")
        self.btn_add_dir = ttk.Button(add, text="Adicionar pasta…", command=self.add_folder)
        self.btn_add_dir.pack(side="left", padx=t.px(8))

        tbox = ttk.Frame(left, style="Card.TFrame", padding=1)
        tbox.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tbox, columns=[f"c{i}" for i in range(len(self.columns))], show="headings",
                                 selectmode="extended", height=8)
        for i, (head, width, anchor) in enumerate(self.columns):
            self.tree.heading(f"c{i}", text=head.upper(), anchor=anchor)
            self.tree.column(f"c{i}", width=t.px(width), anchor=anchor, stretch=(i == len(self.columns) - 1))
        vsb = ttk.Scrollbar(tbox, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tbox.rowconfigure(0, weight=1)
        tbox.columnconfigure(0, weight=1)
        self.tree.tag_configure("odd", background=c["row_alt"])
        self.tree.bind("<Delete>", lambda e: self.remove())
        self.empty = ttk.Label(tbox, text="Nenhum item adicionado.\nUse “Adicionar arquivos…” ou “Adicionar pasta…”.",
                               style="Card.Muted.TLabel", justify="center")
        self.empty.place(relx=0.5, rely=0.5, anchor="center")

        meth = ttk.Frame(left, style="Flat.TFrame")
        meth.pack(fill="x", pady=(t.px(14), 0))
        ttk.Label(meth, text="Método", style="Card.Bold.TLabel").pack(side="left", padx=(0, t.px(14)))
        self.method = tk.StringVar(value="random3")
        self.method_radios = []
        for k, (label, _) in sh.METHODS.items():
            r = ttk.Radiobutton(meth, text=label, value=k, variable=self.method, style="Card.TRadiobutton")
            r.pack(side="left", padx=(0, t.px(16)))
            self.method_radios.append(r)
        hint = ttk.Label(left, text="1 passagem já impede a recuperação por programas. Mais passagens só deixam o "
                                    "processo mais lento.", style="Card.Small.TLabel", justify="left",
                         wraplength=t.px(480))
        hint.pack(anchor="w", fill="x", pady=(t.px(6), 0))
        _wrap(hint)

        _sep(left, t, 12)
        foot = ttk.Frame(left, style="Flat.TFrame")
        foot.pack(fill="x")
        self.btn_shred = ttk.Button(foot, text="Destruir para sempre", style="Danger.TButton", command=self.shred)
        self.btn_shred.pack(side="right")
        self.btn_stop = ttk.Button(foot, text="Parar", command=self.stop)
        self.lbl_total = ttk.Label(foot, text="", style="Card.Bold.TLabel")
        self.lbl_total.pack(side="left")
        self.prog_shred = ttk.Progressbar(left, maximum=1.0, style="Danger.Horizontal.TProgressbar")
        self.lbl_shred = ttk.Label(left, text="", style="Card.Small.TLabel")

        # ---------------------------------------------------------- coluna direita
        right = ttk.Frame(cols, width=t.px(310))
        right.grid(row=0, column=1, sticky="nsew")
        fs = card(right, t, 16, fill="x")
        head = ttk.Frame(fs, style="Flat.TFrame")
        head.pack(fill="x")
        _soft_icon(head, t, "drive", 34).pack(side="left")
        ttk.Label(head, text="Limpar espaço livre", style="Card.H3.TLabel").pack(side="left", padx=t.px(10))
        lbl = ttk.Label(fs, text="Arquivos apagados do jeito comum continuam no disco até serem sobrescritos. "
                                 "Isto enche o espaço livre com zeros e depois apaga, eliminando essas sobras. "
                                 "Seus arquivos não são tocados.", style="Card.Muted.TLabel", justify="left",
                        wraplength=t.px(276))
        lbl.pack(anchor="w", fill="x", pady=(t.px(10), t.px(10)))
        self.drives = fixed_drives() or [os.path.expanduser("~")]
        self.drive_var = tk.StringVar(value=self.drives[0])
        self.drive_box = ttk.Combobox(fs, textvariable=self.drive_var, state="readonly", width=28,
                                      values=self.drives + ["Escolher pasta…"])
        self.drive_box.pack(fill="x")
        self.drive_box.bind("<<ComboboxSelected>>", self._drive_selected)
        self.lbl_free = ttk.Label(fs, text="", style="Card.Small.TLabel")
        self.lbl_free.pack(anchor="w", pady=(t.px(6), 0))
        self.prog_free = ttk.Progressbar(fs, maximum=1.0, style="Horizontal.TProgressbar")
        self.lbl_free_prog = ttk.Label(fs, text="", style="Card.Small.TLabel")
        fbtns = ttk.Frame(fs, style="Flat.TFrame")
        fbtns.pack(fill="x", pady=(t.px(12), 0))
        self.btn_free = ttk.Button(fbtns, text="Limpar espaço livre", style="Primary.TButton", command=self.wipe_free)
        self.btn_free.pack(side="left")
        self.btn_free_stop = ttk.Button(fbtns, text="Parar", command=self.stop)
        ttk.Label(fs, text="Demora: o disco inteiro é gravado. Fica sempre uma margem livre de 2 GB.",
                  style="Card.Small.TLabel", justify="left", wraplength=t.px(276)).pack(anchor="w", fill="x",
                                                                                   pady=(t.px(8), 0))

        ssd = tk.Frame(right, bg=c["warning_soft"])
        ssd.pack(fill="x", pady=(t.px(14), 0))
        inner = tk.Frame(ssd, bg=c["warning_soft"])
        inner.pack(fill="x", padx=t.px(14), pady=t.px(12))
        tk.Label(inner, text="Sobre SSDs e pendrives", bg=c["warning_soft"], fg=c["warning"], font=t.f_bold,
                 anchor="w").pack(fill="x")
        msg = tk.Label(inner, text="SSDs, pendrives e cartões espalham as gravações pelo chip (wear leveling) e o "
                                   "TRIM descarta blocos apagados. Por isso nenhum programa consegue garantir que a "
                                   "posição física antiga foi sobrescrita. Em SSDs o TRIM normalmente já torna os "
                                   "dados apagados irrecuperáveis; para segurança total use a criptografia do disco "
                                   "(BitLocker).", bg=c["warning_soft"], fg=c["text"], font=t.f_small,
                       justify="left", anchor="w", wraplength=t.px(276))
        msg.pack(fill="x", pady=(t.px(4), 0))

        self._update_free()
        self.render()

    # ---------------------------------------------------------------- lista
    def _add(self, paths):
        refused = []
        for p in paths:
            p = os.path.normpath(p)
            if is_protected(p):
                refused.append(p)
                continue
            if p in self.paths or any(p.startswith(x + os.sep) for x in self.paths):
                continue
            # adicionar uma pasta absorve itens que estavam dentro dela
            self.paths = [x for x in self.paths if not x.startswith(p + os.sep)]
            self.paths.append(p)
        if refused:
            messagebox.showwarning("Protegido", "Estes caminhos são do sistema (ou pastas principais do usuário) e "
                                   "não podem ser destruídos:\n\n" + "\n".join(f"• {x}" for x in refused[:10]),
                                   parent=self)
        self.render()
        self._measure()

    def _measure(self):
        todo = [p for p in self.paths if p not in self.sizes]
        if not todo:
            return

        def job():
            for p in todo:
                try:
                    _, _, total = sh.collect([p])
                except OSError:
                    total = 0
                self.sizes[p] = total
            try:
                self.after(0, self.render)
            except (tk.TclError, RuntimeError):
                pass
        threading.Thread(target=job, daemon=True).start()

    def add_files(self):
        files = filedialog.askopenfilenames(parent=self, title="Escolha os arquivos para destruir")
        if files:
            self._add(list(files))

    def add_folder(self):
        d = filedialog.askdirectory(parent=self, title="Escolha a pasta para destruir")
        if d:
            self._add([d])

    def remove(self):
        sel = set(self.tree.selection())
        self.paths = [p for i, p in enumerate(self.paths) if f"r{i}" not in sel]
        self.render()

    def clear(self):
        self.paths = []
        self.render()

    def render(self):
        self.tree.delete(*self.tree.get_children(""))
        for i, p in enumerate(self.paths):
            isdir = os.path.isdir(p) and not os.path.islink(p)
            name = os.path.basename(p) or p
            size = self.sizes.get(p)
            self.tree.insert("", "end", iid=f"r{i}", tags=("odd",) if i % 2 else (),
                             values=(name, "Pasta" if isdir else "Arquivo",
                                     fmt_size(size) if size is not None else "…", os.path.dirname(p)))
        if self.paths:
            self.empty.place_forget()
            total = sum(self.sizes.get(p, 0) for p in self.paths)
            self.lbl_total.config(text=f"{len(self.paths)} item(ns) · {fmt_size(total)}")
        else:
            self.empty.place(relx=0.5, rely=0.5, anchor="center")
            self.lbl_total.config(text="")
        self._buttons()

    def _buttons(self):
        st = "disabled" if self.busy else "normal"
        for b in (self.btn_add_files, self.btn_add_dir, self.btn_remove, self.btn_clear, self.btn_free):
            b.config(state=st)
        for r in self.method_radios:
            r.config(state=st)
        self.btn_shred.config(state="disabled" if self.busy or not self.paths else "normal")

    # ---------------------------------------------------------------- progresso
    def show_progress(self, value):
        if isinstance(value, tuple):
            frac, text = value
        else:
            frac, text = None, str(value)
        if self._mode == "shred":
            if frac is not None:
                self.prog_shred.config(value=frac)
            self.lbl_shred.config(text=text)
        elif self._mode == "free":
            if frac is not None:
                self.prog_free.config(value=frac)
            self.lbl_free_prog.config(text=text)

    _mode = ""

    def _set_busy(self, busy, mode=""):
        self.busy = busy
        t = self.t
        if busy:
            self._mode = mode
            if mode == "shred":
                self.btn_stop.pack(side="right", padx=(0, t.px(8)))
                self.prog_shred.config(value=0)
                self.prog_shred.pack(fill="x", pady=(t.px(12), t.px(4)))
                self.lbl_shred.pack(anchor="w")
            else:
                self.btn_free_stop.pack(side="left", padx=(t.px(8), 0))
                self.prog_free.config(value=0)
                self.prog_free.pack(fill="x", pady=(t.px(12), t.px(4)), before=self.btn_free.master)
                self.lbl_free_prog.pack(anchor="w", before=self.btn_free.master)
        else:
            self.btn_stop.pack_forget()
            self.btn_free_stop.pack_forget()
        self.app.set_nav_busy(self.key, busy)
        self._buttons()

    def busy_now(self):
        return self.busy

    def stop(self):
        self.cancel.set()
        self.show_progress("Parando…")

    # ---------------------------------------------------------------- destruir
    def shred(self):
        if self.busy or not self.paths:
            return
        n_total = sum(self.sizes.get(p, 0) for p in self.paths)
        names = "\n".join(f"• {os.path.basename(p) or p}" for p in self.paths[:8])
        if len(self.paths) > 8:
            names += f"\n… e mais {len(self.paths) - 8}"
        method = sh.METHODS[self.method.get()][0]
        msg = (f"{len(self.paths)} item(ns), {fmt_size(n_total)}, serão destruídos com {method}:\n\n{names}\n\n"
               "Isto NÃO pode ser desfeito: os arquivos não vão para a Lixeira e nenhum programa de "
               "recuperação conseguirá trazê-los de volta.")
        if not ConfirmTyped.ask(self, self.t, "Destruir para sempre", msg):
            return
        paths, method_key = list(self.paths), self.method.get()

        def job(cancel, progress):
            res = sh.shred_paths(paths, method_key, cancel, progress)
            progress(f"{len(res[0])} item(ns) destruído(s).")   # texto final (run_bg pode anexar "interrompido")
            return res

        def done(res):
            ok, errors, _ = res
            gone = [p for p in paths if not os.path.lexists(p)]
            self.paths = [p for p in self.paths if p not in gone]
            self.render()
            if gone:
                self.app.toast(f"{len(gone)} item(ns) destruído(s) para sempre")
            if errors:
                msg = "\n".join(f"• {os.path.basename(p) or p}: {e}" for p, e in errors[:12])
                messagebox.showwarning("Alguns itens não foram destruídos",
                                       f"{len(errors)} item(ns) não puderam ser destruídos (em uso, sem permissão "
                                       f"ou protegidos):\n\n{msg}", parent=self)
            self.app.data_changed()

        def fin():
            self._set_busy(False)
            self.after(2500, lambda: (self.prog_shred.pack_forget(), self.lbl_shred.pack_forget())
                       if not self.busy else None)

        self._set_busy(True, "shred")
        self.run_bg(job, done, (0.0, "Preparando…"), on_finally=fin)

    # ---------------------------------------------------------------- espaço livre
    def _drive_selected(self, _=None):
        if self.drive_var.get() == "Escolher pasta…":
            d = filedialog.askdirectory(parent=self, title="Escolha uma pasta na unidade a limpar")
            if d:
                d = os.path.normpath(d)
                if d not in self.drives:
                    self.drives.append(d)
                    self.drive_box.config(values=self.drives + ["Escolher pasta…"])
                self.drive_var.set(d)
            else:
                self.drive_var.set(self.drives[0])
        self._update_free()

    def _update_free(self):
        try:
            import shutil
            u = shutil.disk_usage(self.drive_var.get())
            self.lbl_free.config(text=f"{fmt_size(u.free)} livres de {fmt_size(u.total)}")
        except OSError:
            self.lbl_free.config(text="Unidade indisponível")

    def wipe_free(self, max_bytes=None):
        if self.busy:
            return
        target = self.drive_var.get()
        import shutil
        try:
            free = shutil.disk_usage(target).free
        except OSError as e:
            messagebox.showerror("Limpar espaço livre", f"Unidade indisponível:\n{e}", parent=self)
            return
        goal = max(0, free - 2 * sh.GB)
        if max_bytes is not None:
            goal = min(goal, max_bytes)
        if goal <= 0:
            messagebox.showinfo("Limpar espaço livre", "Há menos de 2 GB livres nesta unidade: não há o que limpar "
                                "com segurança.", parent=self)
            return
        if not messagebox.askyesno(
                "Limpar espaço livre",
                f"Gravar cerca de {fmt_size(goal)} de zeros em “{target}” e depois apagar?\n\n"
                "Isso pode levar bastante tempo e deixa o disco cheio temporariamente — evite baixar ou salvar "
                "arquivos grandes enquanto roda. Você pode parar a qualquer momento.\n\n"
                "Em SSDs o TRIM do Windows normalmente já cuida disso: só é útil em HDs, pendrives e cartões.",
                parent=self, icon="warning"):
            return

        def done(written):
            self._update_free()
            if self.cancel.is_set():
                self.app.toast(f"Interrompido · {fmt_size(written)} sobrescritos", kind="warning")
            else:
                self.app.toast(f"Espaço livre limpo · {fmt_size(written)} sobrescritos")

        def fin():
            self._set_busy(False)
            self.after(2500, lambda: (self.prog_free.pack_forget(), self.lbl_free_prog.pack_forget())
                       if not self.busy else None)

        def job(cancel, progress):
            n = sh.wipe_free_space(target, cancel, progress, max_bytes=max_bytes)
            progress(f"{fmt_size(n)} sobrescritos e apagados.")
            return n

        self._set_busy(True, "free")
        self.run_bg(job, done, (0.0, "Preparando…"), on_finally=fin)
