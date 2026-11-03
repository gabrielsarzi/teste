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
        except (OSError, ValueError):
            pass
        if not self.get("roots"):
            self["roots"] = [home()]

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
