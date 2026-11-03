"""Configurações persistentes do usuário (JSON na pasta de dados do app)."""
from __future__ import annotations

import json
import os

from .utils import app_data_dir, home

DEFAULTS = {
    "theme": "auto",            # auto | light | dark
    "to_trash": True,           # enviar arquivos apagados para a Lixeira
    "roots": None,              # None = pasta do usuário
    "exclusions": [],           # pastas nunca analisadas
    "check_updates": True,
    "last_scan": None,          # resumo da última análise completa
}


class Settings(dict):
    def __init__(self):
        super().__init__(DEFAULTS)
        self.path = os.path.join(app_data_dir(), "config.json")
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.update(data)
            else:
                raise ValueError("formato inválido")
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            # arquivo corrompido: guarda uma cópia para não perder (ex.: lista de exclusões) e segue com o padrão
            try:
                os.replace(self.path, self.path + ".corrompido")
            except OSError:
                pass
        self._sanitize()
        if not self.get("roots"):
            self["roots"] = [home()]

    def _sanitize(self):
        """Garante os tipos certos: um valor estranho no arquivo nunca pode derrubar o app nem ampliar a análise."""
        def str_list(v):
            return [x for x in v if isinstance(x, str) and x.strip()] if isinstance(v, list) else None
        if self.get("theme") not in ("auto", "light", "dark"):
            self["theme"] = "auto"
        for k in ("to_trash", "check_updates"):
            if not isinstance(self.get(k), bool):
                self[k] = DEFAULTS[k]
        self["exclusions"] = str_list(self.get("exclusions")) or []
        self["auto_clean_skip"] = str_list(self.get("auto_clean_skip")) or []
        roots = str_list(self.get("roots"))
        self["roots"] = roots if roots else [home()]
        ls = self.get("last_scan")
        if ls is not None and not (isinstance(ls, dict) and all(isinstance(v, (int, float, str)) for v in ls.values())):
            self["last_scan"] = None

    def save(self):
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dict(self), f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            pass

    def set(self, key, value):
        self[key] = value
        self.save()
