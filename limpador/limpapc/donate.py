"""Página "Apoie o projeto".

>>> CONFIGURE AQUI <<<  Preencha os dados abaixo e gere uma nova versão:
  - PIX: chave, nome do recebedor (até 25 letras, sem acento) e cidade (até 15 letras, sem acento).
    O app gera o QR Code e o "PIX copia e cola" no padrão oficial do Banco Central (BR Code).
  - LINKS: botões para páginas de doação (LivePix, Ko-fi, Buy Me a Coffee, Apoia.se, GitHub Sponsors…).
Enquanto estiver vazio, a página mostra outras formas de ajudar (compartilhar, avaliar, reportar erros).
"""
from __future__ import annotations

import tkinter as tk
import unicodedata
from tkinter import ttk

from . import APP_NAME, HOMEPAGE
from .pages import Page
from .utils import open_uri
from .widgets import Icon, ScrollFrame, card

DONATION = {
    "pix_key": "",          # ex.: "seuemail@exemplo.com", CPF/CNPJ, celular (+5511999999999) ou chave aleatória
    "pix_name": "",         # ex.: "GABRIEL SARZI"
    "pix_city": "",         # ex.: "SAO PAULO"
    "links": [              # ex.: ("Apoiar no LivePix", "https://livepix.gg/seunome")
    ],
}


# ------------------------------------------------------------------ PIX (BR Code / EMV)
def _crc16(data: bytes) -> str:
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def _field(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def _ascii(s: str, n: int) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.upper()[:n]


def pix_payload(key: str, name: str, city: str, amount: float | None = None, txid: str = "***") -> str:
    """Gera o "PIX copia e cola" (BR Code estático)."""
    acc = _field("00", "br.gov.bcb.pix") + _field("01", key.strip())
    p = _field("00", "01") + _field("26", acc) + _field("52", "0000") + _field("53", "986")
    if amount:
        p += _field("54", f"{amount:.2f}")
    p += _field("58", "BR") + _field("59", _ascii(name, 25)) + _field("60", _ascii(city, 15))
    p += _field("62", _field("05", txid))
    p += "6304"
    return p + _crc16(p.encode("utf-8"))


def pix_configured() -> bool:
    return bool(DONATION["pix_key"] and DONATION["pix_name"] and DONATION["pix_city"])


def _qr_matrix(text: str):
    try:
        import qrcode  # type: ignore
    except ImportError:
        return None
    q = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(text)
    q.make(fit=True)
    return q.get_matrix()


class DonatePage(Page):
    key, icon, title = "donate", "heart", "Apoie o projeto"
    subtitle = f"O {APP_NAME} é gratuito, sem anúncios e de código aberto. Se ele te ajudou, considere apoiar."

    def __init__(self, master, app):
        super().__init__(master, app)
        t, c = self.t, self.t.c
        sf = ScrollFrame(self.body, t)
        sf.pack(fill="both", expand=True)
        root = sf.inner

        hero = card(root, t, 26, fill="x")
        Icon(hero, "heart", t.px(40), c["danger"], c["surface"], 2.0).pack(side="left", padx=(0, t.px(20)))
        txt = ttk.Frame(hero, style="Flat.TFrame")
        txt.pack(side="left", fill="x", expand=True)
        ttk.Label(txt, text="Obrigado por usar o " + APP_NAME + "!", style="Card.H2.TLabel").pack(anchor="w")
        ttk.Label(txt, text="Cada doação ajuda a manter o projeto vivo: novas funções, correções rápidas, "
                            "certificado de assinatura digital (que tira o alerta azul do Windows) e o site no ar. "
                            "Qualquer valor faz diferença.", style="Card.Muted.TLabel",
                  wraplength=t.px(700), justify="left").pack(anchor="w", pady=(t.px(6), 0))

        row = ttk.Frame(root)
        row.pack(fill="x", pady=(t.px(16), 0))
        if pix_configured():
            self._pix_card(row)
        if DONATION["links"]:
            lk = card(row, t, 22)
            lk.pack(side="left", fill="both", expand=True, padx=(t.px(16) if pix_configured() else 0, 0))
            ttk.Label(lk, text="Outras formas de doar", style="Card.H3.TLabel").pack(anchor="w")
            for label, url in DONATION["links"]:
                ttk.Button(lk, text=label, style="Primary.TButton", command=lambda u=url: open_uri(u)).pack(
                    anchor="w", pady=(t.px(10), 0))

        help_ = card(root, t, 22, fill="x", pady=(t.px(16), 0))
        ttk.Label(help_, text="Também dá para ajudar sem gastar nada", style="Card.H3.TLabel").pack(anchor="w")
        tips = [("copy", "Indique o " + APP_NAME + " para amigos e família — principalmente quem vai formatar o PC."),
                ("check", "Deixe uma estrela ⭐ no projeto no GitHub — isso ajuda outras pessoas a encontrarem."),
                ("info", "Encontrou um erro ou tem uma ideia? Conte pra gente na página de problemas (Issues).")]
        for ic, text in tips:
            r = ttk.Frame(help_, style="Flat.TFrame")
            r.pack(fill="x", pady=(t.px(10), 0))
            Icon(r, ic, t.px(18), c["accent"], c["surface"]).pack(side="left")
            ttk.Label(r, text=text, style="Card.TLabel").pack(side="left", padx=t.px(10))
        b = ttk.Frame(help_, style="Flat.TFrame")
        b.pack(anchor="w", pady=(t.px(14), 0))
        ttk.Button(b, text="Abrir o projeto no GitHub", command=lambda: open_uri(HOMEPAGE)).pack(side="left")
        ttk.Button(b, text="Reportar um problema", command=lambda: open_uri(HOMEPAGE + "/issues")).pack(
            side="left", padx=t.px(8))

    def _pix_card(self, row):
        t, c = self.t, self.t.c
        payload = pix_payload(DONATION["pix_key"], DONATION["pix_name"], DONATION["pix_city"])
        pc = card(row, t, 22)
        pc.pack(side="left", fill="both")
        ttk.Label(pc, text="Doe com PIX", style="Card.H3.TLabel").pack(anchor="w")
        ttk.Label(pc, text="Aponte a câmera do app do seu banco:", style="Card.Muted.TLabel").pack(anchor="w",
                                                                                                 pady=(t.px(2), 0))
        m = _qr_matrix(payload)
        if m:
            n = len(m)
            cell = max(3, t.px(220) // n)
            size = cell * (n + 4)
            cv = tk.Canvas(pc, width=size, height=size, bg="#ffffff", highlightthickness=0)
            cv.pack(pady=t.px(12))
            for y, line in enumerate(m):
                for x, on in enumerate(line):
                    if on:
                        cv.create_rectangle((x + 2) * cell, (y + 2) * cell, (x + 3) * cell, (y + 3) * cell,
                                            fill="#000000", outline="")
        ttk.Label(pc, text=f"Chave: {DONATION['pix_key']}", style="Card.Bold.TLabel").pack(anchor="w")
        ttk.Label(pc, text=f"{DONATION['pix_name']}", style="Card.Small.TLabel").pack(anchor="w")
        b = ttk.Frame(pc, style="Flat.TFrame")
        b.pack(anchor="w", pady=(t.px(12), 0))
        ttk.Button(b, text="Copiar PIX copia e cola", style="Primary.TButton",
                   command=lambda: self._copy(payload, "Código PIX copiado! Cole no app do banco.")).pack(side="left")
        ttk.Button(b, text="Copiar chave", command=lambda: self._copy(DONATION["pix_key"], "Chave PIX copiada!")).pack(
            side="left", padx=t.px(8))

    def _copy(self, text, msg):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.app.toast(msg)
