#!/usr/bin/env python3
"""
Hub de Projetos - servidor local (somente 127.0.0.1).

Nao expoe nada na internet. Le e grava arquivos JSON/Markdown dentro de ./data.
Nenhuma dependencia externa: usa apenas a biblioteca padrao do Python 3.

Uso:
    python server.py
    (ou de um duplo-clique em Iniciar.bat)
"""

import json
import os
import re
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
HOST = "127.0.0.1"
PORT = int(os.environ.get("HUB_PORT", "4577"))

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

DEFAULT_COLUMNS = [
    {"id": "agora", "title": "Agora", "color": "#ef4444", "cards": []},
    {"id": "depois", "title": "Depois", "color": "#f59e0b", "cards": []},
    {"id": "inspiracao", "title": "Inspiracao", "color": "#8b5cf6", "cards": []},
    {"id": "erros", "title": "Erros pra ver", "color": "#ec4899", "cards": []},
    {"id": "feito", "title": "Feito", "color": "#22c55e", "cards": []},
]


# --------------------------------------------------------------------------- #
# Utilidades de arquivo
# --------------------------------------------------------------------------- #
def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def slugify(name: str) -> str:
    base = name.strip().lower()
    base = re.sub(r"[àáâãäå]", "a", base)
    base = re.sub(r"[èéêë]", "e", base)
    base = re.sub(r"[ìíîï]", "i", base)
    base = re.sub(r"[òóôõö]", "o", base)
    base = re.sub(r"[ùúûü]", "u", base)
    base = re.sub(r"[ç]", "c", base)
    base = re.sub(r"[^a-z0-9]+", "-", base)
    base = base.strip("-")
    return base or "projeto"


def safe_slug(slug: str):
    return slug if SLUG_RE.match(slug or "") else None


def projects_file() -> Path:
    return DATA / "projects.json"


def load_projects():
    return read_json(projects_file(), {"projects": []})


def save_projects(state) -> None:
    write_json(projects_file(), state)


def project_dir(slug: str) -> Path:
    return DATA / slug


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #
class Handler(BaseHTTPRequestHandler):
    server_version = "HubProjetos/1.0"

    # -- helpers -------------------------------------------------------------
    def _send(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: int = 200):
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _error(self, status: int, msg: str):
        self._json({"error": msg}, status)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def log_message(self, fmt, *args):
        # log enxuto no console
        sys.stderr.write("  %s\n" % (fmt % args))

    # -- static --------------------------------------------------------------
    # App de pagina unica: por seguranca so servimos o index.html.
    # Assim ninguem (nem outra pagina local) consegue puxar server.py
    # ou os arquivos de segredos via GET direto.
    def _serve_static(self, path: str):
        if path in ("/", "", "/index.html"):
            target = BASE / "index.html"
            if not target.exists():
                return self._error(404, "index.html nao encontrado")
            return self._send(200, target.read_bytes(), "text/html; charset=utf-8")
        return self._error(404, "nao encontrado")

    # -- routing -------------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if not path.startswith("/api/"):
            return self._serve_static(path)

        parts = [p for p in path.split("/") if p]  # ['api', ...]
        # /api/projects
        if parts == ["api", "projects"]:
            return self._json(load_projects())
        # /api/projects/<slug>/<resource>
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "projects":
            slug = safe_slug(parts[2])
            if not slug:
                return self._error(400, "id invalido")
            resource = parts[3]
            return self._get_resource(slug, resource)
        return self._error(404, "rota nao encontrada")

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if parts == ["api", "projects"]:
            return self._create_project()
        return self._error(404, "rota nao encontrada")

    def do_PUT(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "projects":
            slug = safe_slug(parts[2])
            if not slug:
                return self._error(400, "id invalido")
            return self._put_resource(slug, parts[3])
        return self._error(404, "rota nao encontrada")

    def do_PATCH(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "projects":
            slug = safe_slug(parts[2])
            if not slug:
                return self._error(400, "id invalido")
            return self._patch_project(slug)
        return self._error(404, "rota nao encontrada")

    def do_DELETE(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "projects":
            slug = safe_slug(parts[2])
            if not slug:
                return self._error(400, "id invalido")
            return self._delete_project(slug)
        return self._error(404, "rota nao encontrada")

    # -- resource handlers ---------------------------------------------------
    def _find_project(self, slug):
        state = load_projects()
        for p in state["projects"]:
            if p["id"] == slug:
                return state, p
        return state, None

    def _get_resource(self, slug, resource):
        _, proj = self._find_project(slug)
        if proj is None:
            return self._error(404, "projeto nao encontrado")
        d = project_dir(slug)
        if resource == "board":
            return self._json(read_json(d / "board.json", {"columns": DEFAULT_COLUMNS}))
        if resource == "notes":
            return self._json({"content": read_text(d / "notes.md", "")})
        if resource == "secrets":
            data = read_json(d / "secrets.local.json", {"keys": []})
            return self._json(data)
        return self._error(404, "recurso desconhecido")

    def _put_resource(self, slug, resource):
        state, proj = self._find_project(slug)
        if proj is None:
            return self._error(404, "projeto nao encontrado")
        d = project_dir(slug)
        body = self._read_body()
        if resource == "board":
            write_json(d / "board.json", body)
        elif resource == "notes":
            write_text(d / "notes.md", body.get("content", ""))
        elif resource == "secrets":
            write_json(d / "secrets.local.json", {"keys": body.get("keys", [])})
        else:
            return self._error(404, "recurso desconhecido")
        proj["updatedAt"] = now_iso()
        save_projects(state)
        return self._json({"ok": True, "updatedAt": proj["updatedAt"]})

    def _create_project(self):
        body = self._read_body()
        name = (body.get("name") or "").strip()
        if not name:
            return self._error(400, "nome obrigatorio")
        state = load_projects()
        base_slug = slugify(name)
        slug = base_slug
        i = 2
        existing = {p["id"] for p in state["projects"]}
        while slug in existing:
            slug = f"{base_slug}-{i}"
            i += 1
        proj = {
            "id": slug,
            "name": name,
            "description": body.get("description", ""),
            "repoPath": body.get("repoPath", ""),
            "repoUrl": body.get("repoUrl", ""),
            "color": body.get("color", "#3b82f6"),
            "createdAt": now_iso(),
            "updatedAt": now_iso(),
        }
        state["projects"].append(proj)
        save_projects(state)
        d = project_dir(slug)
        write_json(d / "board.json", {"columns": DEFAULT_COLUMNS})
        write_text(d / "notes.md", f"# {name}\n\n")
        write_json(d / "secrets.example.json",
                   {"keys": [{"id": "exemplo", "label": "Nome da chave",
                              "value": "cole-o-valor-aqui", "notes": ""}]})
        return self._json(proj, 201)

    def _patch_project(self, slug):
        state, proj = self._find_project(slug)
        if proj is None:
            return self._error(404, "projeto nao encontrado")
        body = self._read_body()
        for field in ("name", "description", "repoPath", "repoUrl", "color"):
            if field in body:
                proj[field] = body[field]
        proj["updatedAt"] = now_iso()
        save_projects(state)
        return self._json(proj)

    def _delete_project(self, slug):
        state, proj = self._find_project(slug)
        if proj is None:
            return self._error(404, "projeto nao encontrado")
        state["projects"] = [p for p in state["projects"] if p["id"] != slug]
        save_projects(state)
        # remove a pasta do projeto (inclui secrets locais)
        d = project_dir(slug)
        if d.exists():
            for root, dirs, files in os.walk(d, topdown=False):
                for f in files:
                    os.remove(os.path.join(root, f))
                for dd in dirs:
                    os.rmdir(os.path.join(root, dd))
            os.rmdir(d)
        return self._json({"ok": True})


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    if not projects_file().exists():
        save_projects({"projects": []})
    url = f"http://{HOST}:{PORT}/"
    try:
        httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        print(f"Nao consegui abrir a porta {PORT}: {e}")
        print("Talvez o app ja esteja aberto. Tente fechar a janela antiga.")
        input("Pressione Enter para sair...")
        return
    print("=" * 56)
    print("  Hub de Projetos rodando localmente")
    print(f"  Abra no navegador: {url}")
    print("  (Somente nesta maquina. Nada exposto na internet.)")
    print("  Para encerrar: feche esta janela.")
    print("=" * 56)
    # abre o navegador automaticamente
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
