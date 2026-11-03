"""Mapa do disco: tamanho de cada pasta (estilo TreeSize) e espaço por tipo de arquivo."""
from __future__ import annotations

import heapq
import os
import time

from .scanners import _ALWAYS_SKIP_NAMES, _ALWAYS_SKIP_PATHS, is_excluded
from .utils import _is_junction, norm

CATEGORIES = [
    ("Vídeos", {"mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v", "mpg", "mpeg", "3gp", "ts", "vob"}),
    ("Imagens", {"jpg", "jpeg", "png", "gif", "bmp", "tif", "tiff", "webp", "heic", "heif", "raw", "cr2", "nef",
                 "arw", "dng", "psd", "svg", "ico", "avif"}),
    ("Músicas e áudio", {"mp3", "wav", "flac", "aac", "ogg", "m4a", "wma", "opus", "aiff", "mid"}),
    ("Documentos", {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp", "txt", "rtf",
                    "csv", "md", "epub", "pages", "numbers", "key"}),
    ("Compactados", {"zip", "rar", "7z", "tar", "gz", "bz2", "xz", "tgz", "zst", "cab", "lz", "lzma"}),
    ("Instaladores e ISOs", {"exe", "msi", "msix", "appx", "iso", "img", "dmg", "deb", "rpm",
                                         "appimage", "apk", "pkg", "vhd", "vhdx", "vmdk", "vdi", "qcow2"}),
    ("Programas e sistema", {"dll", "sys", "so", "dylib", "pak", "bin", "dat", "db", "sqlite", "jar",
                             "pyc", "node", "ocx", "lib", "a", "o"}),
]
OTHER = "Outros"
CATEGORY_NAMES = [c for c, _ in CATEGORIES] + [OTHER]
_EXT_MAP = {ext: name for name, exts in CATEGORIES for ext in exts}
TOP_FILES = 40   # maiores arquivos guardados por pasta (para exibir)


class Node:
    __slots__ = ("name", "path", "size", "files", "dirs", "children", "top_files", "mtime", "parent", "hidden_files")

    def __init__(self, name, path, parent=None):
        self.name = name
        self.path = path
        self.parent = parent
        self.size = 0
        self.files = 0          # arquivos dentro (recursivo)
        self.dirs = 0
        self.children: list[Node] = []
        self.top_files: list[tuple] = []   # (tamanho, nome, mtime)
        self.hidden_files = 0              # arquivos não listados individualmente
        self.mtime = 0.0


def category_of(name: str) -> str:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return _EXT_MAP.get(ext, OTHER)


def analyze(root: str, cancel, progress):
    """Percorre `root` e devolve (nó raiz, {categoria: bytes}, {categoria: arquivos})."""
    root = os.path.abspath(root)
    top = Node(root, root)
    order = [top]
    stack = [top]
    cats = {c: 0 for c in CATEGORY_NAMES}
    cat_count = {c: 0 for c in CATEGORY_NAMES}
    seen = set()
    count = 0
    last = 0.0
    while stack:
        if cancel.is_set():
            break
        node = stack.pop()
        nd = norm(node.path)
        if nd in seen:
            continue
        seen.add(nd)
        heap: list = []
        try:
            it = os.scandir(node.path)
        except OSError:
            continue
        with it:
            for e in it:
                try:
                    if e.is_symlink() or _is_junction(e):
                        continue
                    if e.is_dir(follow_symlinks=False):
                        low = e.name.lower()
                        if low in _ALWAYS_SKIP_NAMES or norm(e.path) in _ALWAYS_SKIP_PATHS or is_excluded(e.path):
                            continue
                        child = Node(e.name, e.path, node)
                        node.children.append(child)
                        order.append(child)
                        stack.append(child)
                    else:
                        st = e.stat(follow_symlinks=False)
                        sz = st.st_size
                        node.size += sz
                        node.files += 1
                        node.mtime = max(node.mtime, st.st_mtime)
                        cat = category_of(e.name)
                        cats[cat] += sz
                        cat_count[cat] += 1
                        item = (sz, e.name, st.st_mtime)
                        if len(heap) < TOP_FILES:
                            heapq.heappush(heap, item)
                        else:
                            heapq.heappushpop(heap, item)
                        count += 1
                        if time.monotonic() - last > 0.25:
                            last = time.monotonic()
                            progress(f"{count:,} arquivos analisados… {node.path}".replace(",", "."))
                except OSError:
                    continue
        node.hidden_files = node.files - len(heap)
        node.top_files = sorted(heap, reverse=True)
    # soma de baixo para cima: filhos aparecem depois dos pais em `order`
    for node in reversed(order):
        if node.parent is not None:
            p = node.parent
            p.size += node.size
            p.files += node.files
            p.dirs += 1 + node.dirs
            p.mtime = max(p.mtime, node.mtime)
    for node in order:
        node.children.sort(key=lambda n: n.size, reverse=True)
    progress(f"{count:,} arquivos em {len(order):,} pastas analisados.".replace(",", "."))
    return top, cats, cat_count


def remove_size(node: Node, size: int, files: int = 1):
    """Atualiza os totais dos ancestrais depois de apagar algo."""
    while node is not None:
        node.size = max(0, node.size - size)
        node.files = max(0, node.files - files)
        node = node.parent
