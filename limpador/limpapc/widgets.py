"""Componentes visuais reutilizáveis (menu lateral, cards, medidores, avisos…)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .theme import draw_icon
from .utils import fmt_size


class Icon(tk.Canvas):
    """Ícone vetorial em um canvas do tamanho exato."""

    def __init__(self, master, name, size, color, bg, width=1.8):
        super().__init__(master, width=size, height=size, bg=bg, highlightthickness=0, bd=0)
        self.name, self.size_, self.color, self.width_ = name, size, color, width
        self.redraw()

    def redraw(self, color=None, bg=None):
        if color:
            self.color = color
        if bg:
            self.configure(bg=bg)
        self.delete("all")
        pad = self.size_ * 0.04
        draw_icon(self, self.name, pad, pad, self.size_ - 2 * pad, self.color, self.width_, bg=self["bg"])


class NavItem(tk.Frame):
    def __init__(self, master, theme, icon, text, command):
        c = theme.c
        super().__init__(master, bg=c["sidebar"], cursor="hand2")
        self.theme, self.command, self.active = theme, command, False
        self.bar = tk.Frame(self, bg=c["sidebar"], width=theme.px(3))
        self.bar.pack(side="left", fill="y")
        self.icon = Icon(self, icon, theme.px(18), c["sidebar_text"], c["sidebar"])
        self.icon.pack(side="left", padx=(theme.px(14), theme.px(10)), pady=theme.px(8))
        self.label = tk.Label(self, text=text, bg=c["sidebar"], fg=c["sidebar_text"], font=theme.f_nav, anchor="w")
        self.label.pack(side="left", fill="x", expand=True)
        self.badge = tk.Label(self, text="", bg=c["sidebar"], fg=c["sidebar_accent"], font=theme.f_small)
        self.badge.pack(side="right", padx=theme.px(10))
        for w in (self, self.icon, self.label, self.badge):
            w.bind("<Enter>", lambda e: self._paint(hover=True))
            w.bind("<Leave>", lambda e: self._paint())
            w.bind("<Button-1>", lambda e: self.command())

    def set_active(self, active):
        self.active = active
        self._paint()

    def set_badge(self, text):
        self.badge.configure(text=text)

    def _paint(self, hover=False):
        c = self.theme.c
        bg = c["sidebar_active"] if self.active else (c["sidebar_hover"] if hover else c["sidebar"])
        fg = "#ffffff" if self.active else c["sidebar_text"]
        for w in (self, self.label, self.badge):
            w.configure(bg=bg)
        self.label.configure(fg=fg, font=self.theme.f_bold if self.active else self.theme.f_nav)
        self.bar.configure(bg=c["sidebar_accent"] if self.active else bg)
        self.icon.redraw(color=c["sidebar_accent"] if self.active else c["sidebar_text"], bg=bg)


class RingGauge(tk.Canvas):
    """Medidor circular com valor no centro."""

    def __init__(self, master, theme, size=120, thickness=11, bg_key="surface"):
        super().__init__(master, width=theme.px(size), height=theme.px(size), bg=theme.c[bg_key],
                         highlightthickness=0, bd=0)
        self.theme, self.size_, self.th = theme, theme.px(size), theme.px(thickness)
        self.value, self.text, self.sub, self.color = 0.0, "—", "", theme.c["accent"]
        self.draw()

    def set(self, value, text, sub="", color=None):
        self.value = max(0.0, min(1.0, value))
        self.text, self.sub = text, sub
        self.color = color or self.theme.c["accent"]
        self.draw()

    def draw(self):
        c, s, t = self.theme.c, self.size_, self.th
        self.delete("all")
        box = (t / 2 + 2, t / 2 + 2, s - t / 2 - 2, s - t / 2 - 2)
        self.create_arc(*box, start=0, extent=359.9, style="arc", outline=c["surface2"], width=t)
        if self.value > 0:
            self.create_arc(*box, start=90, extent=-359.9 * self.value, style="arc", outline=self.color, width=t)
        cy = s / 2 - (self.theme.px(8) if self.sub else 0)
        self.create_text(s / 2, cy, text=self.text, fill=c["text"], font=self.theme.f_h2)
        if self.sub:
            self.create_text(s / 2, cy + self.theme.px(19), text=self.sub, fill=c["muted"], font=self.theme.f_small)


def card(master, theme, padding=16, **pack):
    f = ttk.Frame(master, style="Card.TFrame", padding=theme.px(padding))
    if pack:
        f.pack(**pack)
    return f


class Toast:
    """Aviso discreto no canto da janela, some sozinho."""

    def __init__(self, root, theme, text, kind="success", ms=4000):
        c = theme.c
        color = {"success": c["success"], "warning": c["warning"], "danger": c["danger"]}.get(kind, c["accent"])
        self.f = tk.Frame(root, bg=c["surface"], highlightthickness=1, highlightbackground=c["border"])
        tk.Frame(self.f, bg=color, width=theme.px(4)).pack(side="left", fill="y")
        icon = Icon(self.f, "check" if kind == "success" else "info", theme.px(18), color, c["surface"], 2.2)
        icon.pack(side="left", padx=(theme.px(12), theme.px(8)), pady=theme.px(12))
        tk.Label(self.f, text=text, bg=c["surface"], fg=c["text"], font=theme.f_bold, justify="left",
                 wraplength=theme.px(380)).pack(side="left", padx=(0, theme.px(16)))
        self.f.place(relx=1.0, rely=1.0, x=-theme.px(24), y=-theme.px(24), anchor="se")
        self.f.lift()
        root.after(ms, self.close)
        self.f.bind("<Button-1>", lambda e: self.close())

    def close(self):
        try:
            self.f.destroy()
        except tk.TclError:
            pass


class ScrollFrame(ttk.Frame):
    """Área com rolagem vertical (para páginas longas)."""

    def __init__(self, master, theme, **kw):
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, bg=theme.c["bg"], highlightthickness=0, bd=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self._update())
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: (self.canvas.itemconfigure(self.win, width=e.width), self._update()))
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y", padx=(theme.px(6), 0))
        self.canvas.pack(side="left", fill="both", expand=True)

    def _update(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        need = self.inner.winfo_reqheight() > self.canvas.winfo_height() > 1
        if need and not self.vsb.winfo_ismapped():
            self.vsb.pack(side="right", fill="y", padx=(6, 0), before=self.canvas)
        elif not need and self.vsb.winfo_ismapped():
            self.vsb.pack_forget()
            self.canvas.yview_moveto(0)
        self.bind_all_wheel(self.canvas)

    def bind_all_wheel(self, w):
        def on_wheel(e):
            if self.winfo_ismapped() and self.inner.winfo_reqheight() > self.canvas.winfo_height():
                delta = -1 if (getattr(e, "num", 0) == 4 or e.delta > 0) else 1
                self.canvas.yview_scroll(delta, "units")
        w.bind("<Enter>", lambda e: (w.bind_all("<MouseWheel>", on_wheel), w.bind_all("<Button-4>", on_wheel),
                                     w.bind_all("<Button-5>", on_wheel)))
        w.bind("<Leave>", lambda e: (w.unbind_all("<MouseWheel>"), w.unbind_all("<Button-4>"),
                                     w.unbind_all("<Button-5>")))


class CategoryBars(tk.Canvas):
    """Gráfico de barras horizontais por categoria (tipos de arquivo)."""

    def __init__(self, master, theme, colors, width=300):
        super().__init__(master, width=theme.px(width), height=theme.px(60), bg=theme.c["surface"],
                         highlightthickness=0, bd=0)
        self.theme, self.colors, self.data = theme, colors, []
        self.bind("<Configure>", lambda e: self.draw())

    def set(self, data):
        """data: lista de (nome, bytes, quantidade)."""
        self.data = [d for d in data if d[1] > 0]
        self.draw()

    def draw(self):
        c, px = self.theme.c, self.theme.px
        self.delete("all")
        w = max(self.winfo_width(), px(200))
        if not self.data:
            self.configure(height=px(40))
            self.create_text(0, px(12), text="Analise uma pasta para ver o gráfico.", anchor="w",
                             fill=c["muted"], font=self.theme.f_base)
            return
        total = sum(d[1] for d in self.data) or 1
        # barra empilhada
        x, h = 0.0, px(14)
        for i, (name, size, _) in enumerate(self.data):
            seg = w * size / total
            self.create_rectangle(x, 0, x + seg, h, fill=self.colors[i % len(self.colors)], outline="")
            x += seg
        y = h + px(16)
        row = px(40)
        for i, (name, size, n) in enumerate(self.data):
            col = self.colors[i % len(self.colors)]
            self.create_oval(0, y + px(3), px(10), y + px(13), fill=col, outline="")
            self.create_text(px(18), y + px(8), text=name, anchor="w", fill=c["text"], font=self.theme.f_bold)
            self.create_text(w, y + px(8), text=fmt_size(size), anchor="e", fill=c["text"], font=self.theme.f_bold)
            pct = size / total
            self.create_text(px(18), y + px(26), text=f"{n:,} arquivos · {pct * 100:.1f}%".replace(",", "X")
                             .replace(".", ",").replace("X", "."), anchor="w", fill=c["muted"],
                             font=self.theme.f_small)
            y += row
        self.configure(height=y)


class ListEditor(ttk.Frame):
    """Lista editável de pastas (usada em Configurações)."""

    def __init__(self, master, theme, items, on_change, add_label="Adicionar pasta…", extra=()):
        from tkinter import filedialog
        super().__init__(master, style="Flat.TFrame")
        c = theme.c
        self.items, self.on_change, self.fd = items, on_change, filedialog
        self.lb = tk.Listbox(self, height=4, activestyle="none", bg=c["surface2"], fg=c["text"],
                             selectbackground=c["select"], selectforeground=c["select_text"], bd=0,
                             highlightthickness=0, font=theme.f_base, relief="flat")
        self.lb.pack(side="left", fill="both", expand=True)
        btns = ttk.Frame(self, style="Flat.TFrame")
        btns.pack(side="left", fill="y", padx=(theme.px(10), 0))
        ttk.Button(btns, text=add_label, command=self.add).pack(fill="x")
        for text, cmd in extra:
            ttk.Button(btns, text=text, command=lambda cmd=cmd: (cmd(self.items), self.refresh())).pack(
                fill="x", pady=(theme.px(6), 0))
        ttk.Button(btns, text="Remover", command=self.remove).pack(fill="x", pady=(theme.px(6), 0))
        self.refresh(notify=False)

    def refresh(self, notify=True):
        self.lb.delete(0, "end")
        for it in self.items:
            self.lb.insert("end", "  " + it)
        if notify:
            self.on_change(self.items)

    def add(self):
        import os
        d = self.fd.askdirectory(parent=self, title="Escolha uma pasta")
        if d:
            d = os.path.normpath(d)
            if d not in self.items:
                self.items.append(d)
            self.refresh()

    def remove(self):
        for idx in reversed(self.lb.curselection()):
            del self.items[idx]
        self.refresh()
