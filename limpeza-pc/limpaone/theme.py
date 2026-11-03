"""Tema visual do LimpaOne: paletas claro/escuro, fontes, estilos ttk e ícones vetoriais."""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from .utils import IS_MAC, IS_WIN

LIGHT = {
    "bg": "#f3f5fa", "surface": "#ffffff", "surface2": "#eef1f7", "border": "#e3e8f1", "border_strong": "#cdd5e3",
    "text": "#0f172a", "muted": "#64748b", "subtle": "#94a3b8",
    "accent": "#5b5bf0", "accent_hover": "#4646d9", "accent_soft": "#e8e8fe", "on_accent": "#ffffff",
    "success": "#16a34a", "success_soft": "#dcfce7", "warning": "#d97706", "warning_soft": "#fef3c7",
    "danger": "#dc2626", "danger_hover": "#b91c1c", "danger_soft": "#fee2e2",
    "row_alt": "#f8fafc", "select": "#e4e4fd", "select_text": "#1e1b4b",
    "sidebar": "#0f1426", "sidebar_hover": "#1a2140", "sidebar_active": "#262d57",
    "sidebar_text": "#c7cde0", "sidebar_muted": "#6b7394", "sidebar_accent": "#8b8bff",
}
DARK = {
    "bg": "#0b1020", "surface": "#141a2e", "surface2": "#1c2440", "border": "#26304f", "border_strong": "#36436a",
    "text": "#e6e9f2", "muted": "#9aa3bd", "subtle": "#6b7394",
    "accent": "#7070ff", "accent_hover": "#8a8aff", "accent_soft": "#23264f", "on_accent": "#ffffff",
    "success": "#22c55e", "success_soft": "#12301f", "warning": "#f59e0b", "warning_soft": "#33270d",
    "danger": "#ef4444", "danger_hover": "#f87171", "danger_soft": "#3a1418",
    "row_alt": "#171e35", "select": "#2c2f66", "select_text": "#ffffff",
    "sidebar": "#070a16", "sidebar_hover": "#121831", "sidebar_active": "#1f2550",
    "sidebar_text": "#c7cde0", "sidebar_muted": "#5d6584", "sidebar_accent": "#9a9aff",
}

# cores das categorias de arquivo (mapa do disco)
CATEGORY_COLORS = ["#5b5bf0", "#06b6d4", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#ef4444", "#64748b", "#94a3b8"]


def system_prefers_dark() -> bool:
    if IS_WIN:
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        except OSError:
            return False
    if IS_MAC:
        import subprocess
        try:
            out = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True)
            return "dark" in out.stdout.lower()
        except OSError:
            return False
    import os
    return "dark" in (os.environ.get("GTK_THEME", "") + os.environ.get("COLORFGBG", "")).lower()


class Theme:
    """Guarda a paleta atual, fontes e o fator de escala (DPI)."""

    def __init__(self, root: tk.Tk, mode: str = "auto"):
        self.root = root
        self.mode = mode
        dark = system_prefers_dark() if mode == "auto" else mode == "dark"
        self.dark = dark
        self.c = dict(DARK if dark else LIGHT)
        try:
            self.scale = max(1.0, root.winfo_fpixels("1i") / 96.0) if IS_WIN else 1.0
        except tk.TclError:
            self.scale = 1.0
        self._fonts()

    def px(self, n: float) -> int:
        return int(round(n * self.scale))

    def _fonts(self):
        fams = set(tkfont.families(self.root))
        if IS_WIN:
            fam = "Segoe UI"
            semi = "Segoe UI Semibold" if "Segoe UI Semibold" in fams else "Segoe UI"
        elif IS_MAC:
            fam = semi = "SF Pro Text" if "SF Pro Text" in fams else "Helvetica Neue"
        else:
            pick = next((f for f in ("Inter", "Cantarell", "Ubuntu", "Noto Sans", "DejaVu Sans") if f in fams), None)
            fam = semi = pick or tkfont.nametofont("TkDefaultFont").actual("family")
        semi_w = "normal" if semi != fam else "bold"
        F = lambda f, s, w="normal": tkfont.Font(root=self.root, family=f, size=s, weight=w)  # noqa: E731
        self.f_base = F(fam, 10)
        self.f_small = F(fam, 9)
        self.f_bold = F(semi, 10, semi_w)
        self.f_h1 = F(semi, 19, semi_w)
        self.f_h2 = F(semi, 13, semi_w)
        self.f_h3 = F(semi, 11, semi_w)
        self.f_kpi = F(semi, 22, semi_w)
        self.f_brand = F(semi, 15, semi_w)
        self.f_nav = F(fam, 10)
        self.f_section = F(semi, 8, semi_w)
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(name).configure(family=fam, size=10)
            except tk.TclError:
                pass

    # ------------------------------------------------------------ estilos ttk
    def apply(self):
        c, px = self.c, self.px
        st = ttk.Style(self.root)
        st.theme_use("clam")
        self.root.configure(bg=c["bg"])
        st.configure(".", background=c["bg"], foreground=c["text"], font=self.f_base,
                     bordercolor=c["border"], lightcolor=c["bg"], darkcolor=c["bg"],
                     troughcolor=c["surface2"], focuscolor=c["accent"], selectbackground=c["select"],
                     selectforeground=c["select_text"], fieldbackground=c["surface"],
                     insertcolor=c["text"], arrowcolor=c["muted"])
        st.map(".", foreground=[("disabled", c["subtle"])])

        # quadros
        st.configure("TFrame", background=c["bg"])
        st.configure("Card.TFrame", background=c["surface"], relief="solid", borderwidth=1,
                     bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"])
        st.configure("Flat.TFrame", background=c["surface"])
        st.configure("Soft.TFrame", background=c["surface2"])
        st.configure("TSeparator", background=c["border"])
        st.configure("Sep.TFrame", background=c["border"])

        # rótulos (fundo da página e fundo de card)
        for prefix, bg in (("", c["bg"]), ("Card.", c["surface"]), ("Soft.", c["surface2"])):
            st.configure(f"{prefix}TLabel", background=bg, foreground=c["text"], font=self.f_base)
            st.configure(f"{prefix}Muted.TLabel", background=bg, foreground=c["muted"], font=self.f_base)
            st.configure(f"{prefix}Small.TLabel", background=bg, foreground=c["muted"], font=self.f_small)
            st.configure(f"{prefix}Bold.TLabel", background=bg, foreground=c["text"], font=self.f_bold)
            st.configure(f"{prefix}H1.TLabel", background=bg, foreground=c["text"], font=self.f_h1)
            st.configure(f"{prefix}H2.TLabel", background=bg, foreground=c["text"], font=self.f_h2)
            st.configure(f"{prefix}H3.TLabel", background=bg, foreground=c["text"], font=self.f_h3)
            st.configure(f"{prefix}KPI.TLabel", background=bg, foreground=c["text"], font=self.f_kpi)
            st.configure(f"{prefix}Accent.TLabel", background=bg, foreground=c["accent"], font=self.f_bold)
            st.configure(f"{prefix}Success.TLabel", background=bg, foreground=c["success"], font=self.f_bold)
            st.configure(f"{prefix}Warning.TLabel", background=bg, foreground=c["warning"], font=self.f_bold)
            st.configure(f"{prefix}Danger.TLabel", background=bg, foreground=c["danger"], font=self.f_bold)
            st.configure(f"{prefix}TCheckbutton", background=bg, foreground=c["text"],
                         indicatorbackground=c["surface"], indicatorforeground=c["on_accent"],
                         upperbordercolor=c["subtle"], lowerbordercolor=c["subtle"], indicatormargin=(0, 0, px(6), 0))
            st.map(f"{prefix}TCheckbutton", background=[("active", bg)],
                   indicatorbackground=[("selected", c["accent"]), ("active", c["surface2"])],
                   upperbordercolor=[("selected", c["accent"])], lowerbordercolor=[("selected", c["accent"])])
            st.configure(f"{prefix}TRadiobutton", background=bg, foreground=c["text"],
                         indicatorbackground=c["surface"], indicatorforeground=c["on_accent"],
                         upperbordercolor=c["subtle"], lowerbordercolor=c["subtle"], indicatormargin=(0, 0, px(6), 0))
            st.map(f"{prefix}TRadiobutton", background=[("active", bg)],
                   indicatorbackground=[("selected", c["accent"]), ("active", c["surface2"])],
                   upperbordercolor=[("selected", c["accent"])], lowerbordercolor=[("selected", c["accent"])])
        st.configure("Badge.TLabel", background=c["accent_soft"], foreground=c["accent"], font=self.f_small,
                     padding=(px(8), px(2)))
        st.configure("BadgeWarn.TLabel", background=c["warning_soft"], foreground=c["warning"], font=self.f_small,
                     padding=(px(8), px(2)))
        st.configure("BadgeOk.TLabel", background=c["success_soft"], foreground=c["success"], font=self.f_small,
                     padding=(px(8), px(2)))

        # botões
        pad = (px(14), px(7))
        common = dict(relief="flat", borderwidth=1, focusthickness=0, padding=pad, font=self.f_bold, anchor="center",
                      width=0)
        st.configure("TButton", background=c["surface"], foreground=c["text"], bordercolor=c["border_strong"],
                     lightcolor=c["surface"], darkcolor=c["surface"], **common)
        st.configure("TButton", relief="solid")
        st.map("TButton", background=[("disabled", c["surface2"]), ("pressed", c["surface2"]), ("active", c["surface2"])],
               lightcolor=[("active", c["surface2"])], darkcolor=[("active", c["surface2"])],
               bordercolor=[("disabled", c["border"]), ("active", c["subtle"])])
        for name, bg, hover, fg in (("Primary", c["accent"], c["accent_hover"], c["on_accent"]),
                                    ("Danger", c["danger"], c["danger_hover"], "#ffffff"),
                                    ("Success", c["success"], c["success"], "#ffffff")):
            st.configure(f"{name}.TButton", background=bg, foreground=fg, bordercolor=bg,
                         lightcolor=bg, darkcolor=bg, **common)
            st.map(f"{name}.TButton",
                   background=[("disabled", c["surface2"]), ("pressed", hover), ("active", hover)],
                   foreground=[("disabled", c["subtle"])],
                   bordercolor=[("disabled", c["surface2"]), ("active", hover)],
                   lightcolor=[("disabled", c["surface2"]), ("active", hover)],
                   darkcolor=[("disabled", c["surface2"]), ("active", hover)])
        st.configure("Big.Primary.TButton", padding=(px(26), px(11)), font=self.f_h3)
        st.configure("Ghost.TButton", background=c["surface"], foreground=c["accent"], bordercolor=c["surface"],
                     lightcolor=c["surface"], darkcolor=c["surface"], **common)
        st.map("Ghost.TButton", background=[("active", c["accent_soft"])], bordercolor=[("active", c["accent_soft"])],
               lightcolor=[("active", c["accent_soft"])], darkcolor=[("active", c["accent_soft"])])

        # campos
        field = dict(fieldbackground=c["surface"], background=c["surface"], foreground=c["text"],
                     bordercolor=c["border"], lightcolor=c["surface"], darkcolor=c["surface"],
                     arrowcolor=c["muted"], padding=(px(6), px(4)), insertcolor=c["text"])
        for w in ("TEntry", "TSpinbox", "TCombobox"):
            st.configure(w, **field)
            st.map(w, bordercolor=[("focus", c["accent"])], lightcolor=[("focus", c["surface"])],
                   fieldbackground=[("readonly", c["surface"])], selectbackground=[("readonly", c["surface"])],
                   selectforeground=[("readonly", c["text"])])
        st.configure("Placeholder.TEntry", foreground=c["subtle"])
        self.root.option_add("*TCombobox*Listbox.background", c["surface"])
        self.root.option_add("*TCombobox*Listbox.foreground", c["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", c["select"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", c["select_text"])
        self.root.option_add("*TCombobox*Listbox.font", self.f_base)
        self.root.option_add("*Menu.background", c["surface"])
        self.root.option_add("*Menu.foreground", c["text"])
        self.root.option_add("*Menu.activeBackground", c["select"])
        self.root.option_add("*Menu.activeForeground", c["select_text"])

        # barras de progresso
        for name, color in (("", c["accent"]), ("Success.", c["success"]), ("Warning.", c["warning"]),
                            ("Danger.", c["danger"])):
            st.configure(f"{name}Horizontal.TProgressbar", troughcolor=c["surface2"], background=color,
                         bordercolor=c["surface2"], lightcolor=color, darkcolor=color, thickness=px(6))
        st.configure("Thin.Horizontal.TProgressbar", troughcolor=c["bg"], background=c["accent"],
                     bordercolor=c["bg"], lightcolor=c["accent"], darkcolor=c["accent"], thickness=px(3))

        # tabelas
        st.configure("Treeview", background=c["surface"], fieldbackground=c["surface"], foreground=c["text"],
                     rowheight=px(30), borderwidth=0, relief="flat", font=self.f_base)
        st.map("Treeview", background=[("selected", c["select"])], foreground=[("selected", c["select_text"])])
        st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        st.configure("Treeview.Heading", background=c["surface"], foreground=c["muted"], font=self.f_section,
                     relief="flat", borderwidth=0, padding=(px(8), px(8)), bordercolor=c["border"],
                     lightcolor=c["surface"], darkcolor=c["border"])
        st.map("Treeview.Heading", background=[("active", c["surface2"])], foreground=[("active", c["text"])])
        st.configure("Treeview.Item", indicatorsize=px(12))

        # barras de rolagem finas, sem setas
        for orient in ("Vertical", "Horizontal"):
            st.layout(f"{orient}.TScrollbar", [(f"{orient}.Scrollbar.trough", {"sticky": "nswe", "children": [
                (f"{orient}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
            st.configure(f"{orient}.TScrollbar", troughcolor=c["surface"], background=c["border"],
                         bordercolor=c["surface"], lightcolor=c["border"], darkcolor=c["border"],
                         arrowsize=px(9), gripcount=0, relief="flat")
            st.map(f"{orient}.TScrollbar", background=[("active", c["subtle"])],
                   lightcolor=[("active", c["subtle"])], darkcolor=[("active", c["subtle"])])
        st.configure("TPanedwindow", background=c["bg"])
        return st


# =================================================================== ícones vetoriais (grade 24x24)
def _pts(x, y, s, coords):
    k = s / 24.0
    return [v * k + (x if i % 2 == 0 else y) for i, v in enumerate(coords)]


def draw_icon(cv: tk.Canvas, name: str, x: float, y: float, size: float, color: str, width: float = 1.8,
              bg: str | None = None, tag: str = "icon"):
    """Desenha um ícone de traço fino (estilo 'outline') no canvas."""
    w = max(1.0, width * size / 22)
    P = lambda *c: _pts(x, y, size, c)  # noqa: E731
    line = lambda *c, **kw: cv.create_line(*P(*c), fill=color, width=w, capstyle="round", joinstyle="round", tags=tag, **kw)  # noqa: E731
    poly = lambda *c, fill="": cv.create_polygon(*P(*c), outline=color, fill=fill, width=w, joinstyle="round", tags=tag)  # noqa: E731
    oval = lambda x0, y0, x1, y1, fill="": cv.create_oval(*P(x0, y0, x1, y1), outline=color, fill=fill, width=w, tags=tag)  # noqa: E731
    rect = lambda x0, y0, x1, y1, fill="": cv.create_rectangle(*P(x0, y0, x1, y1), outline=color, fill=fill, width=w, tags=tag)  # noqa: E731
    arc = lambda x0, y0, x1, y1, **kw: cv.create_arc(*P(x0, y0, x1, y1), outline=color, width=w, style="arc", tags=tag, **kw)  # noqa: E731

    if name == "home":
        line(3, 11, 12, 3.5, 21, 11)
        line(5.5, 9.5, 5.5, 20.5, 18.5, 20.5, 18.5, 9.5)
        line(10, 20.5, 10, 14.5, 14, 14.5, 14, 20.5)
    elif name == "sparkles":
        poly(10, 3, 12, 10, 19, 12, 12, 14, 10, 21, 8, 14, 1.5, 12, 8, 10)
        poly(19, 2, 19.9, 4.6, 22.5, 5.5, 19.9, 6.4, 19, 9, 18.1, 6.4, 15.5, 5.5, 18.1, 4.6)
    elif name == "pie":
        oval(3, 3, 21, 21)
        cv.create_arc(*P(3, 3, 21, 21), start=90, extent=-110, style="pieslice", outline=color,
                      fill=color, width=w, tags=tag)
    elif name == "file":
        poly(6, 2.5, 14, 2.5, 19, 7.5, 19, 21.5, 6, 21.5)
        line(14, 2.5, 14, 7.5, 19, 7.5)
        line(9, 13, 16, 13)
        line(9, 17, 16, 17)
    elif name == "copy":
        rect(8, 8, 20.5, 20.5)
        line(4, 16, 4, 4, 16, 4)
    elif name == "clock":
        oval(3, 3, 21, 21)
        line(12, 7, 12, 12, 15.5, 14)
    elif name == "grid":
        for a, b in ((4, 4), (13.5, 4), (4, 13.5), (13.5, 13.5)):
            rect(a, b, a + 6.5, b + 6.5)
    elif name == "package":
        poly(3, 7, 12, 3, 21, 7, 21, 17, 12, 21, 3, 17)
        line(3, 7, 12, 11, 21, 7)
        line(12, 11, 12, 21)
        line(7.5, 5, 16.5, 9)
    elif name == "power":
        arc(4.5, 4.5, 19.5, 19.5, start=125, extent=290)
        line(12, 2.5, 12, 11)
    elif name == "chip":
        rect(6, 6, 18, 18)
        rect(9.5, 9.5, 14.5, 14.5)
        for v in (9.5, 14.5):
            line(v, 2.5, v, 6)
            line(v, 18, v, 21.5)
            line(2.5, v, 6, v)
            line(18, v, 21.5, v)
    elif name == "tools":
        for yy, kx in ((6, 9), (12, 15), (18, 7)):
            line(3.5, yy, 20.5, yy)
            oval(kx - 2.2, yy - 2.2, kx + 2.2, yy + 2.2, fill=bg or color)
    elif name == "gear":
        oval(8.5, 8.5, 15.5, 15.5)
        oval(5, 5, 19, 19)
        for i in range(8):
            a = i * math.pi / 4
            line(12 + 7 * math.cos(a), 12 + 7 * math.sin(a), 12 + 10 * math.cos(a), 12 + 10 * math.sin(a))
    elif name == "info":
        oval(3, 3, 21, 21)
        line(12, 11, 12, 16.5)
        oval(11.3, 7, 12.7, 8.4, fill=color)
    elif name == "trash":
        line(4, 6.5, 20, 6.5)
        line(9, 6.5, 9, 3.5, 15, 3.5, 15, 6.5)
        line(6, 6.5, 7, 20.5, 17, 20.5, 18, 6.5)
        line(10, 10.5, 10, 16.5)
        line(14, 10.5, 14, 16.5)
    elif name == "search":
        oval(4, 4, 16, 16)
        line(14.5, 14.5, 20, 20)
    elif name == "check":
        line(5, 12.5, 10, 17.5, 19.5, 7)
    elif name == "bolt":
        poly(13, 2.5, 4.5, 13.5, 11, 13.5, 10, 21.5, 19.5, 10, 13, 10)
    elif name == "shield":
        poly(12, 2.5, 20, 5.5, 20, 11.5, 12, 21.5, 4, 11.5, 4, 5.5)
        line(8.5, 12, 11, 14.5, 15.5, 9.5)
    elif name == "drive":
        rect(3, 13, 21, 20)
        line(5, 13, 7.5, 5, 16.5, 5, 19, 13)
        oval(16, 15.5, 17.6, 17.1, fill=color)
    elif name == "download":
        line(12, 3.5, 12, 15)
        line(7, 10.5, 12, 15.5, 17, 10.5)
        line(4, 20, 20, 20)
    elif name == "moon":
        cv.create_arc(*P(4, 4, 20, 20), start=60, extent=240, style="arc", outline=color, width=w, tags=tag)
        cv.create_arc(*P(9, 2, 23, 16), start=-100, extent=-140, style="arc", outline=color, width=w, tags=tag)
    elif name == "sun":
        oval(8, 8, 16, 16)
        for i in range(8):
            a = i * math.pi / 4
            line(12 + 6.5 * math.cos(a), 12 + 6.5 * math.sin(a), 12 + 9 * math.cos(a), 12 + 9 * math.sin(a))
    elif name == "folder":
        poly(2.5, 6, 9, 6, 11, 8.5, 21.5, 8.5, 21.5, 19.5, 2.5, 19.5)
    elif name == "chevron":
        line(9, 6, 15, 12, 9, 18)
    elif name == "refresh":
        arc(4, 4, 20, 20, start=30, extent=280)
        line(20, 3.5, 20, 9, 14.5, 9)
    elif name == "gauge":
        arc(2.5, 4, 21.5, 23, start=0, extent=180)
        line(12, 13.5, 16.5, 8)
        oval(10.5, 12, 13.5, 15, fill=color)
        line(4, 17.5, 20, 17.5)
    elif name == "wifi":
        arc(2, 5, 22, 25, start=45, extent=90)
        arc(5.5, 9, 18.5, 22, start=45, extent=90)
        arc(9, 13, 15, 19, start=45, extent=90)
        oval(11, 18.5, 13, 20.5, fill=color)
    elif name == "database":
        oval(4, 3, 20, 8)
        line(4, 5.5, 4, 18.5)
        line(20, 5.5, 20, 18.5)
        arc(4, 9, 20, 14, start=180, extent=180)
        arc(4, 16, 20, 21, start=180, extent=180)
    elif name == "heart":
        poly(12, 20.5, 3.5, 12, 3, 8, 5, 4.8, 8.5, 4, 12, 7, 15.5, 4, 19, 4.8, 21, 8, 20.5, 12)
    elif name == "monitor":
        rect(3, 4, 21, 16)
        line(12, 16, 12, 20)
        line(8, 20.5, 16, 20.5)
    elif name == "store":
        line(3.5, 8, 20.5, 8, 19.5, 20.5, 4.5, 20.5, 3.5, 8)
        arc(8, 3, 16, 12, start=0, extent=180)
    elif name == "eraser":
        poly(14, 3.5, 21, 10.5, 11, 20.5, 6, 20.5, 3, 17.5)
        line(8.5, 9, 15.5, 16)
        line(11, 20.5, 21, 20.5)
    elif name == "rocket":
        poly(12, 2.5, 16, 7, 16, 15, 8, 15, 8, 7)
        line(8, 11, 4.5, 15.5, 8, 15)
        line(16, 11, 19.5, 15.5, 16, 15)
        line(10.5, 18, 10.5, 21)
        line(13.5, 18, 13.5, 21)
        oval(10.5, 7.5, 13.5, 10.5)
    elif name == "layers":
        poly(12, 3, 21, 8, 12, 13, 3, 8)
        line(3, 12, 12, 17, 21, 12)
        line(3, 16, 12, 21, 21, 16)
    elif name == "broom":
        line(19, 3, 12, 12)
        poly(12, 12, 15, 15, 10, 21.5, 3, 21.5, 3, 18)
        line(7, 21.5, 10, 16.5)
    elif name == "external":
        line(14, 4, 20, 4, 20, 10)
        line(20, 4, 11, 13)
        line(17, 14, 17, 20, 4, 20, 4, 7, 10, 7)
    else:
        oval(4, 4, 20, 20)


def draw_logo(cv: tk.Canvas, x: float, y: float, size: float, c1="#6d5dfc", c2="#22d3ee"):
    """Logotipo: quadrado arredondado em degradê com um brilho (vassoura mágica)."""
    r = size * 0.28
    steps = max(8, int(size / 2))
    for i in range(steps):
        t = i / (steps - 1)
        col = _mix(c1, c2, t)
        y0 = y + size * i / steps
        y1 = y + size * (i + 1) / steps + 1
        inset = 0.0
        # recorte aproximado dos cantos arredondados
        for yy in (y0 - y, y1 - y):
            if yy < r:
                inset = max(inset, r - math.sqrt(max(0.0, r * r - (r - yy) ** 2)))
            elif yy > size - r:
                d = yy - (size - r)
                inset = max(inset, r - math.sqrt(max(0.0, r * r - d * d)))
        cv.create_rectangle(x + inset, y0, x + size - inset, min(y1, y + size), fill=col, outline="", tags="logo")
    draw_icon(cv, "broom", x + size * 0.17, y + size * 0.15, size * 0.66, "#ffffff", width=2.4, tag="logo")


def _mix(a: str, b: str, t: float) -> str:
    a = a.lstrip("#")
    b = b.lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{int(ca[i] + (cb[i] - ca[i]) * t):02x}" for i in range(3))


def set_dark_titlebar(root: tk.Tk, dark: bool):
    """Barra de título escura no Windows 10/11."""
    if not IS_WIN:
        return
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        val = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (novo e antigo)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), ctypes.sizeof(val)) == 0:
                break
    except Exception:  # noqa: BLE001
        pass
