"""Destruidor de arquivos e limpeza do espaço livre (funciona em qualquer sistema).

Destruir = sobrescrever todo o conteúdo (1, 3 ou 7 passagens), gravar no disco (fsync), reduzir o
arquivo a zero bytes, renomear várias vezes com nomes aleatórios (apaga o nome original das tabelas
do sistema de arquivos) e por fim apagar.

Limite físico: em SSDs, pendrives e cartões o controlador espalha as gravações (wear leveling) e o
TRIM descarta blocos, então NENHUM programa consegue garantir que a célula física antiga foi
sobrescrita. Em HDs a sobrescrita é eficaz.
"""
from __future__ import annotations

import os
import random
import shutil
import stat
import string
import tempfile
import time

from .utils import _is_junction, is_link_like, is_protected, log, remove_link

CHUNK = 1024 * 1024
METHODS = {
    "zeros": ("1 passagem (zeros)", ["zeros"]),
    "random3": ("3 passagens (aleatório)", ["random", "random", "random"]),
    "seven": ("7 passagens", ["zeros", "ones", "random", "0x55", "0xaa", "random", "zeros"]),
}


class Cancelled(Exception):
    pass


def _pattern_block(kind: str, rnd: random.Random) -> bytes:
    if kind == "zeros":
        return bytes(CHUNK)
    if kind == "ones":
        return b"\xff" * CHUNK
    if kind == "0x55":
        return b"\x55" * CHUNK
    if kind == "0xaa":
        return b"\xaa" * CHUNK
    return rnd.randbytes(CHUNK)


def collect(paths) -> tuple[list[str], list[str], int]:
    """Arquivos a destruir, pastas (de baixo para cima) e total de bytes.

    NUNCA entra em links simbólicos nem em junctions do Windows (que o os.walk segue): esses entram na
    lista de arquivos e são só removidos — o conteúdo do destino não é tocado."""
    files, dirs, total = [], [], 0
    for p in paths:
        if is_link_like(p) or not os.path.isdir(p):
            if os.path.lexists(p):
                files.append(p)
                if not is_link_like(p):
                    try:
                        total += os.path.getsize(p)
                    except OSError:
                        pass
            continue
        order: list[str] = []
        stack = [p]
        while stack:
            d = stack.pop()
            order.append(d)
            try:
                with os.scandir(d) as it:
                    entries = list(it)
            except OSError:
                continue
            for e in entries:
                try:
                    if e.is_symlink() or _is_junction(e) or is_link_like(e.path):
                        files.append(e.path)        # link: apaga só o link
                    elif e.is_dir(follow_symlinks=False):
                        stack.append(e.path)
                    else:
                        files.append(e.path)
                        total += e.stat(follow_symlinks=False).st_size
                except OSError:
                    pass
        dirs.extend(reversed(order))      # mais fundas primeiro
    return files, dirs, total


def _random_name(n: int) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.SystemRandom().choice(alphabet) for _ in range(max(8, n)))


def _scramble_name(path: str, rounds: int = 3) -> str:
    """Renomeia algumas vezes com nomes aleatórios do mesmo tamanho; devolve o caminho final."""
    folder, name = os.path.split(path)
    cur = path
    for _ in range(rounds):
        for _try in range(5):
            new = os.path.join(folder, _random_name(len(name)))
            if not os.path.exists(new):
                try:
                    os.replace(cur, new)
                    cur = new
                except OSError:
                    pass
                break
    return cur


def _make_writable(path):
    try:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        pass


def overwrite_file(path: str, passes: list[str], on_bytes=lambda n: None, cancel=None) -> None:
    """Sobrescreve o conteúdo do arquivo no lugar, passagem por passagem, com fsync após cada uma."""
    size = os.path.getsize(path)
    if size == 0:
        return
    rnd = random.Random(os.urandom(16))
    with open(path, "r+b", buffering=0) as f:
        for kind in passes:
            f.seek(0)
            block = None if kind == "random" else _pattern_block(kind, rnd)
            left = size
            while left > 0:
                if cancel is not None and cancel.is_set():
                    raise Cancelled()
                n = min(CHUNK, left)
                data = _pattern_block("random", rnd) if block is None else block
                f.write(memoryview(data)[:n])
                left -= n
                on_bytes(n)
            f.flush()
            os.fsync(f.fileno())


def shred_file(path: str, method: str = "random3", on_bytes=lambda n: None, cancel=None) -> None:
    """Destrói um arquivo. Links simbólicos são só removidos (o alvo NÃO é tocado)."""
    if is_protected(path):
        raise PermissionError("caminho protegido do sistema — não será destruído")
    if is_link_like(path):
        remove_link(path)
        return
    try:
        if os.lstat(path).st_nlink > 1:
            # hardlink: o mesmo conteúdo tem outro nome em outro lugar — sobrescrever destruiria aquele também.
            os.remove(path)
            return
    except OSError:
        pass
    passes = METHODS[method][1]
    if not os.access(path, os.W_OK):
        _make_writable(path)
    cancelled = False
    try:
        overwrite_file(path, passes, on_bytes, cancel)
    except Cancelled:
        cancelled = True      # o arquivo já está danificado: termina de apagá-lo mesmo assim
    with open(path, "r+b") as f:
        f.truncate(0)
        f.flush()
        os.fsync(f.fileno())
    os.remove(_scramble_name(path))
    if cancelled:
        raise Cancelled()


def shred_paths(paths, method="random3", cancel=None, progress=lambda s: None):
    """Destrói arquivos e pastas. Retorna (feitos, erros[(caminho, msg)], bytes)."""
    passes = len(METHODS[method][1])
    done, errors = [], []
    for p in paths:
        if is_protected(p):
            errors.append((p, "caminho protegido do sistema"))
    targets = [p for p in paths if not is_protected(p)]
    files, dirs, total = collect(targets)
    work = max(1, total * passes)
    state = {"done": 0, "t": 0.0}
    name = {"cur": ""}

    def on_bytes(n):
        state["done"] += n
        now = time.monotonic()
        if now - state["t"] > 0.15:
            state["t"] = now
            progress((state["done"] / work, f"Destruindo {name['cur']}…"))

    failed_dirs = set()
    for fp in files:
        if cancel is not None and cancel.is_set():
            break
        name["cur"] = os.path.basename(fp)
        try:
            shred_file(fp, method, on_bytes, cancel)
            done.append(fp)
        except Cancelled:
            done.append(fp)
            break
        except Exception as e:  # noqa: BLE001
            errors.append((fp, str(e)))
            failed_dirs.add(os.path.dirname(fp))
    if not (cancel is not None and cancel.is_set()):
        for d in dirs:
            try:
                final = _scramble_name(d, 1)
                os.rmdir(final)
                done.append(d)
            except OSError as e:
                if not any(fd == d or fd.startswith(d + os.sep) for fd in failed_dirs):
                    errors.append((d, str(e)))
    for p in done:
        log(f"DESTRUÍDO ({METHODS[method][0]}) {p}")
    progress((1.0, f"{len(done)} item(ns) destruído(s)."))
    return done, errors, total


# =================================================================== espaço livre
GB = 1024 ** 3
FILE_LIMIT = GB          # arquivos de no máximo 1 GB (FAT32 não aceita arquivos > 4 GB)


def free_space_folder(target: str) -> str:
    """Pasta onde os arquivos temporários serão criados para a unidade/pasta escolhida.
    No Windows, na unidade do sistema usa a pasta TEMP (gravar na raiz C:\\ pode exigir administrador).
    Nos outros sistemas usa a própria pasta escolhida."""
    if os.name == "nt":
        tmp = tempfile.gettempdir()
        drive = os.path.splitdrive(os.path.abspath(target))[0].lower()
        if drive and drive == os.path.splitdrive(tmp)[0].lower():
            return tmp
    return target


def wipe_free_space(target: str, cancel=None, progress=lambda s: None, max_bytes: int | None = None,
                    margin: int = 2 * GB) -> int:
    """Enche o espaço livre com zeros (deixando `margin` bytes livres), depois apaga tudo.

    `max_bytes` limita quanto será escrito (útil para testes). Retorna bytes escritos."""
    base = free_space_folder(target)
    work = os.path.join(base, f"LimpaOne-espaco-livre-{_random_name(6)}")
    os.makedirs(work)
    free = shutil.disk_usage(base).free
    goal = max(0, free - margin)
    if max_bytes is not None:
        goal = min(goal, max_bytes)
    zero = bytes(4 * CHUNK)
    written, n_file, last = 0, 0, 0.0
    try:
        while written < goal:
            if cancel is not None and cancel.is_set():
                break
            n_file += 1
            path = os.path.join(work, f"zeros-{n_file:04d}.tmp")
            in_file = 0
            with open(path, "wb", buffering=0) as f:
                while written < goal and in_file < FILE_LIMIT:
                    if cancel is not None and cancel.is_set():
                        break
                    n = min(len(zero), goal - written, FILE_LIMIT - in_file)
                    try:
                        f.write(memoryview(zero)[:n])
                    except OSError:          # disco cheio antes do previsto
                        goal = written
                        break
                    written += n
                    in_file += n
                    if written % (64 * CHUNK) < n:
                        # confere a margem de segurança de vez em quando (outros programas gravam também)
                        if shutil.disk_usage(base).free <= margin:
                            goal = written
                    now = time.monotonic()
                    if now - last > 0.2:
                        last = now
                        progress((written / goal if goal else 1.0,
                                  f"Sobrescrevendo espaço livre… {written / GB:.2f} de {goal / GB:.2f} GB"))
                try:
                    f.flush()
                    os.fsync(f.fileno())
                except OSError:
                    pass
    finally:
        progress((1.0, "Apagando arquivos temporários…"))
        shutil.rmtree(work, ignore_errors=True)
    log(f"ESPAÇO LIVRE SOBRESCRITO em {base}: {written} bytes")
    progress((1.0, "Concluído."))
    return written
