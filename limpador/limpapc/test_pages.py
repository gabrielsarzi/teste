"""Páginas de testes: desempenho do PC (BenchmarkPage) e velocidade da internet (SpeedTestPage)."""
from __future__ import annotations

import datetime
import math
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from . import bench
from .pages import Page
from .speedtest import DEFAULT_BASE, Cancelled, SpeedTester, fmt_mbps, interpret
from .theme import _mix, draw_icon
from .utils import fmt_size, log
from .widgets import RingGauge, ScrollFrame, card

HISTORY_MAX = 20


# =================================================================== utilidades visuais
def fmt_num(v, dec=0) -> str:
    """Número no formato brasileiro (1.234,5)."""
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def soft_icon(master, t, name, size=38, fg=None, soft=None, bg_key="surface", draw=None):
    c = t.c
    s = t.px(size)
    cv = tk.Canvas(master, width=s, height=s, bg=c[bg_key], highlightthickness=0, bd=0)
    cv.create_oval(0, 0, s, s, fill=soft or c["accent_soft"], outline="")
    if draw:
        draw(cv, s * 0.27, s * 0.27, s * 0.46, fg or c["accent"])
    else:
        draw_icon(cv, name, s * 0.25, s * 0.25, s * 0.5, fg or c["accent"], 2.0, bg=soft or c["accent_soft"])
    return cv


def draw_arrow(cv, x, y, size, color, up=True):
    """Seta simples (o tema não tem ícone de upload)."""
    w = max(1.5, 2.0 * size / 22)
    k = size / 24
    if up:
        cv.create_line(x + 12 * k, y + 20 * k, x + 12 * k, y + 5 * k, fill=color, width=w, capstyle="round")
        cv.create_line(x + 6 * k, y + 10.5 * k, x + 12 * k, y + 4.5 * k, x + 18 * k, y + 10.5 * k, fill=color,
                       width=w, capstyle="round", joinstyle="round")
    else:
        cv.create_line(x + 12 * k, y + 4 * k, x + 12 * k, y + 19 * k, fill=color, width=w, capstyle="round")
        cv.create_line(x + 6 * k, y + 13.5 * k, x + 12 * k, y + 19.5 * k, x + 18 * k, y + 13.5 * k, fill=color,
                       width=w, capstyle="round", joinstyle="round")


def ensure_styles(t):
    """Estilos extras usados só nestas páginas (criados em tempo de execução, sem mexer no tema)."""
    c = t.c
    st = ttk.Style(t.root)
    st.configure("BadgeBad.TLabel", background=c["danger_soft"], foreground=c["danger"], font=t.f_small,
                 padding=(t.px(8), t.px(2)))
    st.configure("BadgeNeutral.TLabel", background=c["surface2"], foreground=c["muted"], font=t.f_small,
                 padding=(t.px(8), t.px(2)))
    st.configure("Card.Live.TLabel", background=c["surface"], foreground=c["accent"], font=t.f_kpi)
    st.configure("Soft.Live.TLabel", background=c["surface2"], foreground=c["accent"], font=t.f_kpi)


STATUS_BADGE = {"ok": ("BadgeOk.TLabel", "Ótimo"), "warn": ("BadgeWarn.TLabel", "Razoável"),
                "bad": ("BadgeBad.TLabel", "Limitado")}


def delta_badge(master, new, old, higher_is_better=True):
    """Selo com a variação em relação ao teste anterior (ou None)."""
    if not new or not old:
        return None
    pct = (new - old) / old * 100
    if abs(pct) < 3:
        return ttk.Label(master, text="= anterior", style="BadgeNeutral.TLabel")
    better = (pct > 0) == higher_is_better
    sign = "+" if pct > 0 else "−"
    return ttk.Label(master, text=f"{sign}{abs(pct):.0f}%", style="BadgeOk.TLabel" if better else "BadgeWarn.TLabel")


class RefBar(tk.Canvas):
    """Barra fina comparando uma nota com a referência (1000 pontos fica no meio)."""

    def __init__(self, master, t):
        super().__init__(master, height=t.px(18), bg=t.c["surface"], highlightthickness=0, bd=0)
        self.t, self.score, self.color = t, 0, t.c["accent"]
        self.bind("<Configure>", lambda e: self.draw())

    def set(self, score, color):
        self.score, self.color = score, color
        self.draw()

    def draw(self):
        c, px = self.t.c, self.t.px
        self.delete("all")
        w = max(self.winfo_width(), px(100))
        h = px(6)
        y = px(6)
        self.create_rectangle(0, y, w, y + h, fill=c["surface2"], outline="")
        if self.score:
            frac = min(1.0, self.score / 2000)
            self.create_rectangle(0, y, max(h, w * frac), y + h, fill=self.color, outline="")
        mx = w / 2
        self.create_line(mx, y - px(4), mx, y + h + px(4), fill=c["subtle"], width=max(1, px(1.5)))


# =================================================================== TESTE DE DESEMPENHO
METRICS = [  # chave, título, ícone, unidade
    ("cpu1", "Processador (1 núcleo)", "chip", "op/s"),
    ("cpuN", "Processador (multinúcleo)", "chip", "op/s"),
    ("mem", "Memória RAM", "layers", "GB/s"),
    ("disk_read", "Disco · leitura sequencial", "drive", "MB/s"),
    ("disk_write", "Disco · escrita sequencial", "drive", "MB/s"),
    ("disk_iops", "Disco · leitura aleatória 4K", "drive", "IOPS"),
]
STAGE_TEXT = {"cpu1": "Testando o processador (1 núcleo)", "cpuN": "Testando o processador (todos os núcleos)",
              "mem": "Testando a memória", "disk": "Testando o disco do sistema"}
DISK_PHASE_TEXT = {"disk_write": "escrita", "disk_read": "leitura", "disk_iops": "leitura aleatória"}


def metric_value(key, v):
    """(texto, unidade) para exibir um resultado."""
    if key == "mem":
        return fmt_num(v / 1000, 1), "GB/s"
    if key == "disk_iops":
        return fmt_num(v), "IOPS"
    if key.startswith("disk"):
        return fmt_num(v), "MB/s"
    return fmt_num(v, 1 if v < 100 else 0), "op/s"


class BenchmarkPage(Page):
    key, icon, title = "bench", "gauge", "Teste de desempenho"
    subtitle = ("Mede processador, memória e disco em cerca de um minuto e dá uma nota para o seu PC. "
                "Feche jogos e programas pesados antes de começar para um resultado mais fiel.")
    disk_dir = None   # None = pasta temporária da unidade do sistema (os testes de desenvolvimento mudam isto)
    quick = 1.0       # < 1 encurta os testes (desenvolvimento)
    disk_size = None  # None = 512 MB a 1 GB conforme o espaço livre

    def __init__(self, master, app):
        super().__init__(master, app)
        t = self.t
        ensure_styles(t)
        self.cancel = threading.Event()
        self.busy = False
        self.state: dict = {}
        self.thread = None
        sf = ScrollFrame(self.body, t)
        sf.pack(fill="both", expand=True)
        root = self.root_frame = sf.inner
        root.columnconfigure((0, 1, 2), weight=1, uniform="bcol")

        # ---- destaque: nota geral
        hero = card(root, t, 22)
        hero.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.ring = RingGauge(hero, t, size=150, thickness=13)
        self.ring.pack(side="left", padx=(0, t.px(26)))
        txt = ttk.Frame(hero, style="Flat.TFrame")
        txt.pack(side="left", fill="both", expand=True)
        self.h_kicker = ttk.Label(txt, text="", style="Card.Small.TLabel")
        self.h_kicker.pack(anchor="w")
        self.h_title = ttk.Label(txt, text="", style="Card.H2.TLabel")
        self.h_title.pack(anchor="w")
        self.h_desc = ttk.Label(txt, text="", style="Card.Muted.TLabel", wraplength=t.px(600), justify="left")
        self.h_desc.pack(anchor="w", pady=(t.px(6), t.px(4)))
        self.h_cmp = ttk.Label(txt, text="", style="Card.Small.TLabel")
        self.h_cmp.pack(anchor="w", pady=(0, t.px(12)))
        btns = ttk.Frame(txt, style="Flat.TFrame")
        btns.pack(anchor="w", fill="x")
        self.btn_start = ttk.Button(btns, text="Iniciar teste", style="Big.Primary.TButton", command=self.start)
        self.btn_start.pack(side="left")
        self.btn_stop = ttk.Button(btns, text="Parar", command=self.stop)
        self.prog_box = ttk.Frame(txt, style="Flat.TFrame")
        self.prog = ttk.Progressbar(self.prog_box, mode="determinate", maximum=1000)
        self.prog.pack(fill="x", pady=(t.px(12), t.px(4)))
        self.lbl_prog = ttk.Label(self.prog_box, text="", style="Card.Small.TLabel")
        self.lbl_prog.pack(anchor="w")
        txt.bind("<Configure>", lambda e: self.h_desc.config(wraplength=max(t.px(300), e.width - t.px(10))))

        # ---- cards de resultados
        self.cards = {}
        for i, (key, title, icon, unit) in enumerate(METRICS):
            r, col = 1 + i // 3, i % 3
            f = card(root, t, 18)
            f.grid(row=r, column=col, sticky="nsew", pady=(t.px(16), 0),
                   padx=(0 if col == 0 else t.px(8), 0 if col == 2 else t.px(8)))
            top = ttk.Frame(f, style="Flat.TFrame")
            top.pack(fill="x")
            soft_icon(top, t, icon, 34).pack(side="left")
            ttk.Label(top, text=title, style="Card.Bold.TLabel").pack(side="left", padx=(t.px(10), 0))
            row = ttk.Frame(f, style="Flat.TFrame")
            row.pack(fill="x", pady=(t.px(12), 0))
            f.big = ttk.Label(row, text="—", style="Card.KPI.TLabel")
            f.big.pack(side="left")
            f.unit = ttk.Label(row, text=unit, style="Card.Muted.TLabel")
            f.unit.pack(side="left", padx=(t.px(6), 0), pady=(t.px(8), 0))
            f.badge_box = ttk.Frame(row, style="Flat.TFrame")
            f.badge_box.pack(side="right", pady=(t.px(6), 0))
            f.bar = RefBar(f, t)
            f.bar.pack(fill="x", pady=(t.px(8), t.px(2)))
            f.small = ttk.Label(f, text="Aguardando", style="Card.Small.TLabel", wraplength=t.px(280),
                                justify="left")
            f.small.pack(anchor="w")
            f.bind("<Configure>", lambda e, f=f: f.small.config(wraplength=max(t.px(160), e.width - t.px(40))))
            self.cards[key] = f

        # ---- uso no dia a dia + histórico
        self.daily = card(root, t, 20)
        self.daily.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(t.px(16), 0), padx=(0, t.px(8)))
        self.hist = card(root, t, 20)
        self.hist.grid(row=3, column=2, sticky="nsew", pady=(t.px(16), 0), padx=(t.px(8), 0))
        ref = bench.REFERENCE
        ttk.Label(root, style="Small.TLabel", justify="left", wraplength=t.px(900), text=(
            "Como a nota é calculada: cada resultado é comparado com um PC de referência que vale 1000 pontos "
            "(desktop intermediário de 2020–2022: processador de 6 núcleos/12 threads como Core i5-10400 ou "
            f"Ryzen 5 3600, memória DDR4 em dois canais e SSD SATA — {fmt_num(ref['disk_read'])} MB/s de leitura). "
            "A nota geral é a média ponderada das notas; a linha vertical nas barras marca a referência. "
            "O teste de disco grava um arquivo temporário de até 1 GB, que é apagado ao final.")).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(t.px(14), t.px(4)))
        self.render_idle()

    # ------------------------------------------------------------ histórico
    def history(self) -> list:
        h = self.app.settings.get("bench_history") or []
        return [e for e in h if isinstance(e, dict) and e.get("score")]

    # ------------------------------------------------------------ desenho
    def render_idle(self):
        """Estado sem teste em andamento: mostra o último resultado salvo (se houver)."""
        h = self.history()
        last = h[-1] if h else None
        prev = h[-2] if len(h) > 1 else None
        if last:
            self.show_results(last.get("results", {}), prev.get("results") if prev else None,
                              last.get("score", 0), prev.get("score") if prev else None, when=last.get("when"))
        else:
            t = self.t
            self.ring.set(0, "—", "nota", t.c["subtle"])
            self.h_kicker.config(text="")
            self.h_title.config(text="Quanto o seu PC é rápido?")
            self.h_desc.config(text="O teste mede o processador (um núcleo e todos juntos), a velocidade da "
                                    "memória e a leitura e escrita do disco do sistema. Leva cerca de um minuto; "
                                    "você pode parar a qualquer momento.")
            self.h_cmp.config(text="")
            for key, f in self.cards.items():
                self._card_reset(f, "Aguardando o teste")
            self.render_daily({})
        self.render_history()

    def _card_reset(self, f, text):
        f.big.config(text="—", style="Card.KPI.TLabel")
        f.bar.set(0, self.t.c["accent"])
        f.small.config(text=text)
        for w in f.badge_box.winfo_children():
            w.destroy()

    def _score_color(self, s):
        c = self.t.c
        return c["success"] if s >= 1000 else c["accent"] if s >= 600 else c["warning"] if s >= 300 else c["danger"]

    def show_results(self, res, prev_res, score, prev_score, when=None, fresh=False):
        c = self.t.c
        name, color_key, desc = bench.level_of(score)
        self.ring.set(min(1.0, score / 2000), fmt_num(score), name, c[color_key])
        self.h_kicker.config(text=("RESULTADO DO TESTE" if fresh else f"ÚLTIMO TESTE · {when or '—'}"))
        self.h_title.config(text=f"Nota {fmt_num(score)} — {name}")
        self.h_desc.config(text=desc)
        if prev_score:
            pct = (score - prev_score) / prev_score * 100
            word = "igual ao" if abs(pct) < 3 else (f"{abs(pct):.0f}% acima do" if pct > 0 else
                                                    f"{abs(pct):.0f}% abaixo do")
            self.h_cmp.config(text=f"Nota {word} teste anterior ({fmt_num(prev_score)} pontos).",
                              style="Card.Success.TLabel" if pct >= 3 else
                              "Card.Warning.TLabel" if pct <= -3 else "Card.Small.TLabel")
        else:
            self.h_cmp.config(text="Este é o primeiro teste salvo. Os próximos serão comparados com ele.",
                              style="Card.Small.TLabel")
        threads = res.get("threads")
        for key, f in self.cards.items():
            v = res.get(key)
            for w in f.badge_box.winfo_children():
                w.destroy()
            if not v:
                self._card_reset(f, res.get("disk_error") or "Não medido")
                continue
            txt, unit = metric_value(key, v)
            s = bench.score_of(key, v)
            f.big.config(text=txt, style="Card.KPI.TLabel")
            f.unit.config(text=unit)
            f.bar.set(s, self._score_color(s))
            extra = ""
            if key == "cpuN" and res.get("cpu1"):
                extra = f" · {res['cpuN'] / res['cpu1']:.1f}x um núcleo".replace(".", ",")
                if threads:
                    extra += f" ({threads} threads)"
            if key == "disk_read" and res.get("direct") is False:
                extra = " · pode incluir cache do sistema"
            if key == "disk_write" and res.get("size"):
                extra = f" · arquivo de {fmt_size(res['size'])}"
            f.small.config(text=f"{fmt_num(s)} pontos ({fmt_num(s / 10)}% da referência){extra}")
            b = delta_badge(f.badge_box, v, (prev_res or {}).get(key))
            if b:
                b.pack()
        self.render_daily(res)

    def render_daily(self, res):
        t = self.t
        for w in self.daily.winfo_children():
            w.destroy()
        ttk.Label(self.daily, text="O que isso significa no dia a dia", style="Card.H3.TLabel").pack(anchor="w")
        rows = bench.daily_use(res) if res.get("cpu1") else []
        if not rows:
            ttk.Label(self.daily, text="Faça o teste para ver como o seu PC se sai em escritório, jogos, edição "
                                       "de fotos e vídeos e no tempo de carregamento.",
                      style="Card.Muted.TLabel", wraplength=t.px(560), justify="left").pack(anchor="w",
                                                                                             pady=(t.px(8), 0))
            return
        for icon, title, status, desc in rows:
            ttk.Frame(self.daily, style="Sep.TFrame", height=1).pack(fill="x", pady=t.px(9))
            row = ttk.Frame(self.daily, style="Flat.TFrame")
            row.pack(fill="x")
            col = {"ok": "success", "warn": "warning", "bad": "danger"}[status]
            soft_icon(row, t, icon, 34, fg=t.c[col], soft=t.c[col + "_soft"]).pack(side="left", anchor="n")
            style, label = STATUS_BADGE[status]
            ttk.Label(row, text=label, style=style).pack(side="right", anchor="n", pady=(t.px(2), 0))
            mid = ttk.Frame(row, style="Flat.TFrame")
            mid.pack(side="left", fill="x", expand=True, padx=t.px(12))
            ttk.Label(mid, text=title, style="Card.Bold.TLabel").pack(anchor="w")
            lbl = ttk.Label(mid, text=desc, style="Card.Small.TLabel", wraplength=t.px(460), justify="left")
            lbl.pack(anchor="w")
            mid.bind("<Configure>", lambda e, lbl=lbl: lbl.config(wraplength=max(t.px(200), e.width - 4)))

    def render_history(self):
        t = self.t
        for w in self.hist.winfo_children():
            w.destroy()
        ttk.Label(self.hist, text="Histórico", style="Card.H3.TLabel").grid(row=0, column=0, columnspan=3,
                                                                           sticky="w", pady=(0, t.px(8)))
        h = list(reversed(self.history()))[:7]
        if not h:
            ttk.Label(self.hist, text="Os resultados dos testes ficam salvos aqui para você comparar depois.",
                      style="Card.Muted.TLabel", wraplength=t.px(260), justify="left").grid(row=1, column=0,
                                                                                            columnspan=3, sticky="w")
            return
        for i, e in enumerate(h, 1):
            s = e.get("score", 0)
            name = bench.level_of(s)[0]
            ttk.Label(self.hist, text=e.get("when", "—"), style="Card.Small.TLabel").grid(
                row=i, column=0, sticky="w", pady=t.px(3))
            ttk.Label(self.hist, text=fmt_num(s), style="Card.Bold.TLabel").grid(row=i, column=1, sticky="e",
                                                                                padx=(t.px(10), t.px(8)))
            ttk.Label(self.hist, text=name, style="Card.Small.TLabel").grid(row=i, column=2, sticky="w")
        self.hist.columnconfigure(0, weight=1)

    # ------------------------------------------------------------ execução
    def busy_now(self):
        return self.busy

    def start(self):
        if self.busy:
            return
        self.busy = True
        self.cancel.clear()
        self.state = {"results": {}, "disk_size": self.disk_size}
        self.app.set_nav_busy(self.key, True)
        self.btn_start.pack_forget()
        self.btn_stop.pack(side="left")
        self.prog.config(value=0)
        self.prog_box.pack(fill="x")
        self.ring.set(0, "…", "testando", self.t.c["accent"])
        self.h_kicker.config(text="TESTE EM ANDAMENTO")
        self.h_title.config(text="Testando o seu PC…")
        self.h_desc.config(text="Evite usar o computador até o fim para não atrapalhar a medição.")
        self.h_cmp.config(text="", style="Card.Small.TLabel")
        for f in self.cards.values():
            self._card_reset(f, "Aguardando")
        self.render_daily({})
        # thread não-daemon: se a janela for fechada no meio, o programa espera o teste parar e apagar o
        # arquivo temporário (o fechamento do app aciona self.cancel).
        self.thread = threading.Thread(target=bench.run_all, args=(self.state, self.cancel, self.disk_dir,
                                                                   self.quick), daemon=False)
        self.thread.start()
        self.after(100, self.poll)

    def stop(self):
        self.cancel.set()
        self.btn_stop.config(state="disabled")
        self.lbl_prog.config(text="Parando e apagando arquivos temporários…")

    def poll(self):
        st = self.state
        stage = st.get("stage")
        if stage:
            weights = {k: w for k, _, w in bench.STAGES}
            order = [k for k, _, _ in bench.STAGES]
            done = sum(weights[k] for k in order[:order.index(stage)])
            frac = (done + weights[stage] * st.get("stage_frac", 0)) / sum(weights.values())
            self.prog.config(value=frac * 1000)
            text = STAGE_TEXT[stage]
            key = stage
            if stage == "disk":
                key = st.get("disk_phase", "disk_write")
                text += f" ({DISK_PHASE_TEXT[key]})"
            if not self.cancel.is_set():
                self.lbl_prog.config(text=f"{text}…  {frac * 100:.0f}%")
            live = st.get("live") or 0
            f = self.cards.get(key)
            if f and live:
                txt, unit = metric_value(key, live)
                f.big.config(text=txt, style="Card.Live.TLabel")
                f.small.config(text="Medindo…")
            for k, v in st["results"].items():  # cards já concluídos
                if k in self.cards and k != key and isinstance(v, float) and \
                        self.cards[k].big.cget("style") != "Card.KPI.TLabel":
                    self._show_partial(k, v)
        if not st.get("done"):
            self.after(100, self.poll)
            return
        self.finish()

    def _show_partial(self, key, v):
        f = self.cards[key]
        txt, unit = metric_value(key, v)
        s = bench.score_of(key, v)
        f.big.config(text=txt, style="Card.KPI.TLabel")
        f.bar.set(s, self._score_color(s))
        f.small.config(text=f"{fmt_num(s)} pontos")

    def finish(self):
        self.busy = False
        self.app.set_nav_busy(self.key, False)
        self.btn_stop.pack_forget()
        self.btn_stop.config(state="normal")
        self.btn_start.pack(side="left")
        self.prog_box.pack_forget()
        st = self.state
        res = dict(st.get("results") or {})
        if st.get("error"):
            self.btn_start.config(text="Tentar de novo")
            self.render_idle()
            self.h_kicker.config(text="O TESTE NÃO PÔDE SER CONCLUÍDO")
            self.h_cmp.config(text=f"Erro: {st['error']}", style="Card.Danger.TLabel")
            log(f"Teste de desempenho: erro {st['error']}")
            return
        if self.cancel.is_set() or not res.get("cpu1"):
            self.render_idle()
            self.app.toast("Teste interrompido. Nenhum arquivo temporário ficou para trás.", kind="info")
            return
        res["threads"] = st.get("threads")
        if st.get("disk_error"):
            res["disk_error"] = st["disk_error"]
        score = bench.overall_score(res)
        hist = self.history()
        prev = hist[-1] if hist else None
        entry = {"when": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "ts": time.time(), "score": score,
                 "scores": {k: bench.score_of(k, res.get(k)) for k in bench.REFERENCE},
                 "results": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in res.items()}}
        hist.append(entry)
        self.app.settings.set("bench_history", hist[-HISTORY_MAX:])
        self.show_results(res, prev.get("results") if prev else None, score, prev.get("score") if prev else None,
                          fresh=True)
        self.render_history()
        self.btn_start.config(text="Testar de novo")
        log(f"Teste de desempenho: nota {score} ({bench.level_of(score)[0]})")
        self.app.toast(f"Teste concluído: nota {fmt_num(score)} ({bench.level_of(score)[0]}).")


# =================================================================== VELOCÍMETRO
class SpeedGauge(tk.Canvas):
    """Velocímetro em arco (270°) com escala não linear, arco preenchido animado e número central."""

    TICKS = [0, 5, 10, 25, 50, 100, 250, 500, 1000]
    START, SWEEP = 225.0, 270.0

    def __init__(self, master, t, width=340, height=300, bg_key="surface"):
        super().__init__(master, width=t.px(width), height=t.px(height), bg=t.c[bg_key], highlightthickness=0,
                         bd=0)
        self.t = t
        self.w, self.h = t.px(width), t.px(height)
        base = t.f_kpi.actual()
        self.f_big = tkfont.Font(root=t.root, family=base["family"], size=40, weight=base["weight"])
        self.frac = 0.0       # fração exibida (animada)
        self.target = 0.0
        self.value_text, self.unit, self.label = "0", "Mbps", "PRONTO"
        self.color2 = "#22d3ee"
        self._anim = None
        self.draw_static()
        self.draw_dynamic()

    @classmethod
    def to_frac(cls, v):
        tk_ = cls.TICKS
        if v <= 0:
            return 0.0
        if v >= tk_[-1]:
            return 1.0
        for i in range(len(tk_) - 1):
            if v <= tk_[i + 1]:
                return (i + (v - tk_[i]) / (tk_[i + 1] - tk_[i])) / (len(tk_) - 1)
        return 1.0

    def _geom(self):
        r = min(self.w / 2, self.h / 1.72) - self.t.px(14)
        cx, cy = self.w / 2, self.t.px(14) + r
        return cx, cy, r

    def _pt(self, frac, rr):
        cx, cy, _ = self._geom()
        a = math.radians(self.START - self.SWEEP * frac)
        return cx + rr * math.cos(a), cy - rr * math.sin(a)

    def draw_static(self):
        t, c = self.t, self.t.c
        self.delete("static")
        cx, cy, r = self._geom()
        th = t.px(16)
        box = (cx - r, cy - r, cx + r, cy + r)
        self.create_arc(*box, start=self.START, extent=-self.SWEEP, style="arc", outline=c["surface2"],
                        width=th, tags="static")
        for i, v in enumerate(self.TICKS):
            f = i / (len(self.TICKS) - 1)
            x, y = self._pt(f, r - th - t.px(14))
            self.create_text(x, y, text=str(v), fill=c["muted"], font=t.f_small, tags="static")
            x0, y0 = self._pt(f, r - th / 2 - t.px(3))
            x1, y1 = self._pt(f, r - th / 2 - t.px(7))
            self.create_line(x0, y0, x1, y1, fill=c["subtle"], width=max(1, t.px(1.5)), tags="static")

    def draw_dynamic(self):
        t, c = self.t, self.t.c
        self.delete("dyn")
        cx, cy, r = self._geom()
        th = t.px(16)
        box = (cx - r, cy - r, cx + r, cy + r)
        if self.frac > 0.002:
            n = max(1, int(self.frac * 60))
            seg = self.SWEEP * self.frac / n
            for i in range(n):
                col = _mix(c["accent"], self.color2, (i + 0.5) / 60)
                self.create_arc(*box, start=self.START - i * seg, extent=-(seg + 0.6), style="arc", outline=col,
                                width=th, tags="dyn")
            # ponteiro: marcador na ponta do arco
            x, y = self._pt(self.frac, r)
            col = _mix(c["accent"], self.color2, self.frac)
            k = th * 0.62
            self.create_oval(x - k, y - k, x + k, y + k, fill=c["surface"], outline=col, width=t.px(3), tags="dyn")
        self.create_text(cx, cy - t.px(40), text=self.label, fill=c["muted"], font=t.f_section, tags="dyn")
        self.create_text(cx, cy, text=self.value_text, fill=c["text"], font=self.f_big, tags="dyn")
        self.create_text(cx, cy + t.px(38), text=self.unit, fill=c["muted"], font=t.f_h3, tags="dyn")

    def set(self, value, text=None, unit="Mbps", label=None, instant=False):
        self.target = self.to_frac(value)
        self.value_text = text if text is not None else fmt_mbps(value)
        self.unit = unit
        if label is not None:
            self.label = label
        if instant:
            self.frac = self.target
        self._kick()

    def _kick(self):
        if self._anim is None:
            self._anim = self.after(16, self._step)

    def _step(self):
        self._anim = None
        d = self.target - self.frac
        self.frac = self.target if abs(d) < 0.002 else self.frac + d * 0.2
        try:
            self.draw_dynamic()
        except tk.TclError:
            return
        if self.frac != self.target:
            self._anim = self.after(33, self._step)


# =================================================================== VELOCIDADE DA INTERNET
class SpeedTestPage(Page):
    key, icon, title = "speed", "wifi", "Velocidade da internet"
    subtitle = ("Mede o ping, o download e o upload da sua conexão usando servidores do Cloudflare. "
                "Para medir só a internet, pause downloads e streaming durante o teste.")
    base_url = DEFAULT_BASE
    durations = (10.0, 8.0)   # segundos de download e upload

    def __init__(self, master, app):
        super().__init__(master, app)
        t = self.t
        ensure_styles(t)
        self.cancel = threading.Event()
        self.busy = False
        self.state: dict = {}
        sf = ScrollFrame(self.body, t)
        sf.pack(fill="both", expand=True)
        root = sf.inner
        root.columnconfigure((0, 1, 2), weight=1, uniform="scol")

        # ---- destaque
        hero = card(root, t, 22)
        hero.grid(row=0, column=0, columnspan=3, sticky="ew")
        self.gauge = SpeedGauge(hero, t)
        self.gauge.pack(side="left", padx=(0, t.px(26)))
        right = ttk.Frame(hero, style="Flat.TFrame")
        right.pack(side="left", fill="both", expand=True)
        self.h_kicker = ttk.Label(right, text="", style="Card.Small.TLabel")
        self.h_kicker.pack(anchor="w")
        self.h_title = ttk.Label(right, text="", style="Card.H2.TLabel")
        self.h_title.pack(anchor="w")
        self.h_desc = ttk.Label(right, text="", style="Card.Muted.TLabel", wraplength=t.px(520), justify="left")
        self.h_desc.pack(anchor="w", pady=(t.px(6), t.px(14)))
        right.bind("<Configure>", lambda e: self.h_desc.config(wraplength=max(t.px(260), e.width - t.px(10))))
        btns = ttk.Frame(right, style="Flat.TFrame")
        btns.pack(anchor="w")
        self.btn_start = ttk.Button(btns, text="Iniciar teste", style="Big.Primary.TButton", command=self.start)
        self.btn_start.pack(side="left")
        self.btn_stop = ttk.Button(btns, text="Cancelar", command=self.stop)
        tiles = ttk.Frame(right, style="Flat.TFrame")
        tiles.pack(fill="x", pady=(t.px(20), 0))
        tiles.columnconfigure((0, 1, 2), weight=1, uniform="tile")
        self.tiles = {}
        for i, (key, title, unit, draw) in enumerate((
                ("ping", "Ping", "ms", lambda cv, x, y, s, col: draw_icon(cv, "clock", x, y, s, col, 2.0)),
                ("down", "Download", "Mbps", lambda cv, x, y, s, col: draw_arrow(cv, x, y, s, col, up=False)),
                ("up", "Upload", "Mbps", lambda cv, x, y, s, col: draw_arrow(cv, x, y, s, col, up=True)))):
            f = ttk.Frame(tiles, style="Soft.TFrame", padding=(t.px(14), t.px(12)))
            f.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else t.px(6), 0 if i == 2 else t.px(6)))
            top = ttk.Frame(f, style="Soft.TFrame")
            top.pack(fill="x")
            soft_icon(top, t, "", 26, bg_key="surface2", soft=t.c["surface"], draw=draw).pack(side="left")
            ttk.Label(top, text=title, style="Soft.Muted.TLabel").pack(side="left", padx=(t.px(8), 0))
            row = ttk.Frame(f, style="Soft.TFrame")
            row.pack(fill="x", pady=(t.px(8), 0))
            f.big = ttk.Label(row, text="—", style="Soft.KPI.TLabel")
            f.big.pack(side="left")
            ttk.Label(row, text=unit, style="Soft.Muted.TLabel").pack(side="left", padx=(t.px(5), 0),
                                                                      pady=(t.px(8), 0))
            f.small = ttk.Label(f, text="", style="Soft.Small.TLabel")
            f.small.pack(anchor="w")
            self.tiles[key] = f
        self.lbl_info = ttk.Label(right, text="", style="Card.Small.TLabel", justify="left", wraplength=t.px(500))
        self.lbl_info.pack(anchor="w", pady=(t.px(12), 0))
        tiles.bind("<Configure>", lambda e: self.lbl_info.config(wraplength=max(t.px(260), e.width)))

        # ---- interpretação + histórico
        self.uses = card(root, t, 20)
        self.uses.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(t.px(16), 0), padx=(0, t.px(8)))
        self.hist = card(root, t, 20)
        self.hist.grid(row=1, column=2, sticky="nsew", pady=(t.px(16), 0), padx=(t.px(8), 0))
        ttk.Label(root, style="Small.TLabel", justify="left", wraplength=t.px(900), text=(
            "O resultado varia com o horário, o Wi-Fi e outros aparelhos usando a rede. Para saber a velocidade "
            "contratada, teste com o computador ligado por cabo ao roteador. Em conexões rápidas o teste pode "
            "usar algumas centenas de MB de dados.")).grid(row=2, column=0, columnspan=3, sticky="w",
                                                          pady=(t.px(14), t.px(4)))
        self.render_idle()

    # ------------------------------------------------------------ histórico / desenho
    def history(self) -> list:
        h = self.app.settings.get("speed_history") or []
        return [e for e in h if isinstance(e, dict) and "down" in e]

    def _set_tile(self, key, value, small="", live=False):
        f = self.tiles[key]
        if value is None:
            f.big.config(text="—", style="Soft.KPI.TLabel")
        else:
            f.big.config(text=fmt_num(value) if key == "ping" else fmt_mbps(value),
                         style="Soft.Live.TLabel" if live else "Soft.KPI.TLabel")
        f.small.config(text=small)

    def _info_text(self, meta):
        if not meta:
            return ""
        parts = []
        if meta.get("isp"):
            parts.append(f"Provedor: {meta['isp']}")
        elif meta.get("asn"):
            parts.append(f"Rede: AS{meta['asn']}")
        if meta.get("ip"):
            parts.append(f"IP: {meta['ip']}")
        loc = ", ".join(x for x in (meta.get("city"), meta.get("country")) if x)
        if loc:
            parts.append(f"Local: {loc}")
        if meta.get("colo"):
            parts.append(f"Servidor: {meta['colo']}")
        return "  ·  ".join(parts)

    def render_idle(self):
        h = self.history()
        last = h[-1] if h else None
        if last:
            self.show_result(last, h[-2] if len(h) > 1 else None, fresh=False)
        else:
            self.gauge.set(0, "—", "Mbps", "PRONTO", instant=True)
            self.h_kicker.config(text="")
            self.h_title.config(text="Qual é a velocidade da sua internet?")
            self.h_desc.config(text="O teste leva cerca de 20 segundos: mede o tempo de resposta (ping), a "
                                    "velocidade para baixar (download) e para enviar (upload).")
            for k in self.tiles:
                self._set_tile(k, None)
            self.lbl_info.config(text="")
            self.render_uses(None)
        self.render_history()

    def show_result(self, e, prev, fresh=True):
        self.gauge.set(e["down"], label="DOWNLOAD")
        self.h_kicker.config(text="RESULTADO DO TESTE" if fresh else f"ÚLTIMO TESTE · {e.get('when', '—')}")
        down, up = e["down"], e.get("up", 0)
        verdict = ("Conexão muito rápida" if down >= 300 else "Conexão rápida" if down >= 100 else
                   "Conexão boa" if down >= 25 else "Conexão razoável" if down >= 10 else "Conexão lenta")
        self.h_title.config(text=f"{verdict}: {fmt_mbps(down)} Mbps para baixar")
        desc = f"Envio de {fmt_mbps(up)} Mbps e ping de {e.get('ping', 0):.0f} ms."
        if prev and prev.get("down"):
            pct = (down - prev["down"]) / prev["down"] * 100
            desc += (" Download igual ao teste anterior." if abs(pct) < 5 else
                     f" Download {abs(pct):.0f}% {'maior' if pct > 0 else 'menor'} que no teste anterior "
                     f"({fmt_mbps(prev['down'])} Mbps).")
        self.h_desc.config(text=desc)
        self._set_tile("ping", e.get("ping"), f"variação (jitter) {fmt_num(e.get('jitter', 0), 1)} ms")
        self._set_tile("down", down, self._delta_text(down, prev and prev.get("down")))
        self._set_tile("up", up, self._delta_text(up, prev and prev.get("up")))
        self.lbl_info.config(text=self._info_text(e.get("meta")))
        self.render_uses(e)

    @staticmethod
    def _delta_text(v, old):
        if not old:
            return ""
        pct = (v - old) / old * 100
        return "igual ao anterior" if abs(pct) < 5 else f"{'+' if pct > 0 else '−'}{abs(pct):.0f}% vs. anterior"

    def render_uses(self, e):
        t = self.t
        for w in self.uses.winfo_children():
            w.destroy()
        ttk.Label(self.uses, text="O que dá para fazer com essa conexão", style="Card.H3.TLabel").pack(anchor="w")
        if not e:
            ttk.Label(self.uses, text="Depois do teste você vê aqui se a conexão aguenta streaming em 4K, "
                                      "chamadas de vídeo e jogos on-line, e quanto tempo leva para baixar um jogo.",
                      style="Card.Muted.TLabel", wraplength=t.px(560), justify="left").pack(anchor="w",
                                                                                             pady=(t.px(8), 0))
            return
        icons = {"Streaming em 4K": "monitor", "Chamadas de vídeo": "wifi", "Jogos on-line": "bolt",
                 "Baixar um jogo de 50 GB": "download", "Enviar 1 GB para a nuvem": "database"}
        for title, status, desc in interpret(e["down"], e.get("up", 0), e.get("ping", 0), e.get("jitter", 0)):
            ttk.Frame(self.uses, style="Sep.TFrame", height=1).pack(fill="x", pady=t.px(9))
            row = ttk.Frame(self.uses, style="Flat.TFrame")
            row.pack(fill="x")
            col = {"ok": "success", "warn": "warning", "bad": "danger"}[status]
            soft_icon(row, t, icons.get(title, "info"), 34, fg=t.c[col], soft=t.c[col + "_soft"]).pack(
                side="left", anchor="n")
            style, label = STATUS_BADGE[status]
            ttk.Label(row, text=label, style=style).pack(side="right", anchor="n", pady=(t.px(2), 0))
            mid = ttk.Frame(row, style="Flat.TFrame")
            mid.pack(side="left", fill="x", expand=True, padx=t.px(12))
            ttk.Label(mid, text=title, style="Card.Bold.TLabel").pack(anchor="w")
            lbl = ttk.Label(mid, text=desc, style="Card.Small.TLabel", wraplength=t.px(460), justify="left")
            lbl.pack(anchor="w")
            mid.bind("<Configure>", lambda ev, lbl=lbl: lbl.config(wraplength=max(t.px(200), ev.width - 4)))

    def render_history(self):
        t = self.t
        for w in self.hist.winfo_children():
            w.destroy()
        ttk.Label(self.hist, text="Histórico", style="Card.H3.TLabel").grid(row=0, column=0, columnspan=4,
                                                                           sticky="w", pady=(0, t.px(8)))
        h = list(reversed(self.history()))[:8]
        if not h:
            ttk.Label(self.hist, text="Os resultados ficam salvos aqui para você acompanhar a sua conexão.",
                      style="Card.Muted.TLabel", wraplength=t.px(260), justify="left").grid(
                row=1, column=0, columnspan=4, sticky="w")
            return
        for j, head in enumerate(("Data", "↓ Mbps", "↑ Mbps", "Ping")):
            ttk.Label(self.hist, text=head, style="Card.Small.TLabel").grid(row=1, column=j, sticky="w" if j == 0
                                                                            else "e", padx=(0 if j == 0 else
                                                                                            t.px(8), 0))
        ttk.Frame(self.hist, style="Sep.TFrame", height=1).grid(row=2, column=0, columnspan=4, sticky="ew",
                                                                pady=t.px(4))
        for i, e in enumerate(h, 3):
            when = e.get("when") or "—"
            if len(when) == 16:  # dd/mm/aaaa HH:MM -> dd/mm HH:MM
                when = when[:5] + when[10:]
            ttk.Label(self.hist, text=when, style="Card.Small.TLabel").grid(row=i, column=0, sticky="w",
                                                                           pady=t.px(3))
            for j, v in enumerate((fmt_mbps(e["down"]), fmt_mbps(e.get("up", 0)), f"{e.get('ping', 0):.0f} ms"), 1):
                ttk.Label(self.hist, text=v, style="Card.Bold.TLabel" if j == 1 else "Card.TLabel").grid(
                    row=i, column=j, sticky="e", padx=(t.px(8), 0))
        self.hist.columnconfigure(0, weight=1)

    # ------------------------------------------------------------ execução
    def busy_now(self):
        return self.busy

    def start(self):
        if self.busy:
            return
        self.busy = True
        self.cancel.clear()
        self.state = st = {"phase": "ping", "frac": 0.0, "live": 0.0}
        self.app.set_nav_busy(self.key, True)
        self.btn_start.pack_forget()
        self.btn_stop.config(state="normal")
        self.btn_stop.pack(side="left")
        self.h_kicker.config(text="TESTE EM ANDAMENTO")
        self.h_title.config(text="Conectando ao servidor…")
        self.h_desc.config(text="Não feche esta página até o fim do teste.")
        for k in self.tiles:
            self._set_tile(k, None)
        self.lbl_info.config(text="")
        self.render_uses(None)
        self.gauge.set(0, "0", "ms", "PING", instant=True)
        tester = SpeedTester(self.base_url, self.cancel)
        down_s, up_s = self.durations

        def meta_job():
            st["meta"] = tester.meta()

        def job():
            try:
                def prog(f, v):
                    st["frac"], st["live"] = f, v
                ping, jitter = tester.latency(20, prog)
                st.update(ping=ping, jitter=jitter, phase="down", frac=0.0, live=0.0)
                threading.Thread(target=meta_job, daemon=True).start()
                st["down"] = tester.download(down_s, 6, prog)
                st.update(phase="up", frac=0.0, live=0.0)
                st["up"] = tester.upload(up_s, 4, prog)
            except Cancelled:
                st["cancelled"] = True
            except Exception as e:  # noqa: BLE001
                st["error"] = e
            finally:
                st["done"] = True

        threading.Thread(target=job, daemon=True).start()
        self.after(100, self.poll)

    def stop(self):
        self.cancel.set()
        self.btn_stop.config(state="disabled")

    def poll(self):
        st = self.state
        ph = st.get("phase")
        live = st.get("live", 0.0)
        if ph == "ping":
            self.h_title.config(text="Medindo o tempo de resposta…")
            if live:
                self.gauge.set(0, fmt_num(live), "ms", "PING")
                self._set_tile("ping", live, "medindo…", live=True)
        elif ph == "down":
            self.h_title.config(text="Medindo a velocidade de download…")
            self._set_tile("ping", st["ping"], f"variação (jitter) {fmt_num(st['jitter'], 1)} ms")
            self.gauge.set(live, label="DOWNLOAD")
            self._set_tile("down", live, "medindo…", live=True)
        elif ph == "up":
            self.h_title.config(text="Medindo a velocidade de upload…")
            if "down" in st:
                self._set_tile("down", st["down"], "")
            self.gauge.set(live, label="UPLOAD")
            self._set_tile("up", live, "medindo…", live=True)
        if not st.get("done"):
            self.after(100, self.poll)
            return
        self.finish()

    def finish(self):
        st = self.state
        self.busy = False
        self.app.set_nav_busy(self.key, False)
        self.btn_stop.pack_forget()
        self.btn_start.pack(side="left")
        if st.get("cancelled") or self.cancel.is_set():
            self.render_idle()
            self.app.toast("Teste de velocidade cancelado.", kind="info")
            return
        if st.get("error") or "up" not in st:
            err = st.get("error")
            self.render_idle()
            self.gauge.set(0, "—", "Mbps", "SEM CONEXÃO")
            for k in self.tiles:
                self._set_tile(k, None)
            self.lbl_info.config(text="")
            self.render_uses(None)
            self.btn_start.config(text="Tentar de novo")
            self.h_kicker.config(text="NÃO FOI POSSÍVEL TESTAR")
            self.h_title.config(text="Sem conexão com o servidor de teste")
            self.h_desc.config(text="Verifique se o computador está conectado à internet e se nenhum firewall ou "
                                    f"proxy bloqueia o acesso a speed.cloudflare.com.\n\nDetalhe: {err}")
            log(f"Teste de velocidade: erro {err}")
            return
        hist = self.history()
        prev = hist[-1] if hist else None
        e = {"when": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), "ts": time.time(),
             "down": round(st["down"], 2), "up": round(st["up"], 2), "ping": round(st["ping"], 1),
             "jitter": round(st["jitter"], 1), "meta": st.get("meta") or {}}
        hist.append(e)
        self.app.settings.set("speed_history", hist[-HISTORY_MAX:])
        self.show_result(e, prev, fresh=True)
        self.render_history()
        self.btn_start.config(text="Testar de novo")
        log(f"Teste de velocidade: {e['down']} / {e['up']} Mbps, ping {e['ping']} ms")
        self.app.toast(f"Download {fmt_mbps(e['down'])} Mbps · Upload {fmt_mbps(e['up'])} Mbps")
