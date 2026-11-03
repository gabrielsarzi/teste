"""Verificação de novas versões no GitHub Releases."""
from __future__ import annotations

import json
import re
import urllib.request

from . import GITHUB_REPO, __version__


def _ver(s: str) -> tuple:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", s or "")
    return tuple(int(x or 0) for x in m.groups()) if m else (0,)


def check_for_update(timeout=6):
    """Retorna (versão, url da página, url do instalador) se houver versão mais nova; senão None."""
    req = urllib.request.Request(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                                 headers={"Accept": "application/vnd.github+json",
                                          "User-Agent": f"LimpaOne/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    latest = data.get("tag_name", "")
    if _ver(latest) <= _ver(__version__):
        return None
    setup = next((a["browser_download_url"] for a in data.get("assets", [])
                  if a.get("name", "").lower().endswith("setup.exe")), None)
    return re.sub(r"^[^\d]*", "", latest), data.get("html_url"), setup
