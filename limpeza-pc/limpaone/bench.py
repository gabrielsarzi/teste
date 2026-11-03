"""Testes de desempenho do PC: processador, memória e disco (sem dependências externas).

Cada teste é uma função que roda em segundo plano, verifica `cancel` (threading.Event) com frequência
e informa o andamento por `progress(fração 0..1, texto)`.

Nota geral
----------
Cada resultado vira uma pontuação: ``valor / valor_do_PC_de_referência * 1000``.
O PC de referência (``REFERENCE``) representa um desktop intermediário típico de 2020–2022:
processador de 6 núcleos/12 threads (classe Core i5-10400 / Ryzen 5 3600), memória DDR4 em dois canais e
SSD SATA. Ele vale 1000 pontos em cada teste. Os valores foram calibrados de forma aproximada a partir de
medições com este mesmo código (Python 3.12) e de proporções conhecidas entre essas máquinas, então a nota
serve para comparar computadores entre si e o mesmo PC ao longo do tempo — não é um benchmark científico.

A nota geral é a média geométrica ponderada das notas (uma nota muito alta não esconde outra muito baixa).
"""
from __future__ import annotations

import ctypes
import glob
import hashlib
import math
import mmap
import os
import random
import shutil
import tempfile
import threading
import time
import zlib
from concurrent.futures import ThreadPoolExecutor

from .utils import IS_WIN

# --------------------------------------------------------------------------- referência (= 1000 pontos)
REFERENCE = {
    "cpu1": 110.0,      # operações/s em 1 núcleo (1 op = BLAKE2b de 1 MiB + compressão/descompressão de 256 KiB)
    "cpuN": 650.0,      # operações/s usando todos os núcleos (≈ 6 núcleos + Hyper-Threading)
    "mem": 9000.0,      # MB/s de cópia de memória
    "disk_read": 500.0,   # MB/s leitura sequencial (SSD SATA)
    "disk_write": 450.0,  # MB/s escrita sequencial (SSD SATA, com fsync)
    "disk_iops": 8000.0,  # leituras aleatórias de 4 KiB por segundo, uma por vez (fila 1)
}
WEIGHTS = {"cpu1": 0.22, "cpuN": 0.25, "mem": 0.13, "disk_read": 0.12, "disk_write": 0.10, "disk_iops": 0.18}

LEVELS = [  # (nota mínima, nome, cor do tema, o que significa no dia a dia)
    (1600, "Excelente", "success",
     "Sobra desempenho: jogos pesados, edição de vídeo em 4K, máquinas virtuais e várias tarefas ao mesmo "
     "tempo sem engasgos."),
    (1000, "Muito bom", "success",
     "Roda bem jogos atuais em qualidade média/alta, edição de fotos e vídeos em Full HD e programação. "
     "Escritório e navegação ficam instantâneos."),
    (600, "Bom", "accent",
     "Ótimo para escritório, navegação com muitas abas, aulas e reuniões on-line. Jogos leves e edição "
     "simples funcionam; tarefas pesadas demoram mais."),
    (0, "Básico", "warning",
     "Adequado para navegar, e-mail, documentos e vídeos. Jogos e edição de vídeo ficam lentos. Um SSD e "
     "mais memória costumam ser os upgrades que mais ajudam."),
]

CHUNK = 4 << 20          # bloco de leitura/escrita sequencial (4 MiB)
RAND_BLOCK = 4096        # leitura aleatória (4 KiB)
TMP_PREFIX = "limpaone_bench_"


def score_of(key, value) -> int:
    ref = REFERENCE.get(key)
    if not ref or not value:
        return 0
    return int(round(value / ref * 1000))


def overall_score(results: dict) -> int:
    """Média geométrica ponderada das notas disponíveis."""
    tot_w, acc = 0.0, 0.0
    for k, w in WEIGHTS.items():
        s = score_of(k, results.get(k))
        if s > 0:
            acc += w * math.log(s)
            tot_w += w
    return int(round(math.exp(acc / tot_w))) if tot_w else 0


def level_of(score: int):
    for lim, name, color, desc in LEVELS:
        if score >= lim:
            return name, color, desc
    return LEVELS[-1][1:]


def daily_use(results: dict) -> list[tuple[str, str, str, str]]:
    """Avaliação por tipo de uso: lista de (ícone, título, situação ok|warn|bad, explicação)."""
    sc = {k: score_of(k, results.get(k)) for k in REFERENCE}
    cpu1, cpun, mem = sc["cpu1"], sc["cpuN"], sc["mem"]
    disk = min([v for v in (sc["disk_read"], sc["disk_iops"]) if v] or [0])

    def grade(v, good, ok):
        return "ok" if v >= good else "warn" if v >= ok else "bad"

    out = []
    office = min(cpu1, disk or cpu1)
    out.append(("file", "Escritório, navegação e aulas", grade(office, 450, 200),
                "Abre programas e páginas rapidamente." if office >= 450 else
                "Funciona, mas abrir programas e muitas abas pode demorar." if office >= 200 else
                "Deve parecer lento; feche programas em segundo plano e considere um SSD."))
    games = min(cpu1, cpun) if cpun else cpu1
    out.append(("bolt", "Jogos", grade(games, 900, 500),
                "Processador dá conta de jogos atuais (o resultado final também depende da placa de vídeo)."
                if games >= 900 else
                "Jogos leves e competitivos rodam bem; títulos pesados exigem qualidade menor." if games >= 500 else
                "Indicado só para jogos leves ou antigos."))
    edit = min(cpun or cpu1, mem or cpun or cpu1)
    out.append(("pie", "Edição de fotos e vídeos", grade(edit, 1000, 550),
                "Edição em Full HD fluida e exportações rápidas." if edit >= 1000 else
                "Fotos sem problemas; vídeos editam bem, mas exportar leva tempo." if edit >= 550 else
                "Edição de vídeo vai ser lenta; para fotos, prefira arquivos menores."))
    if disk:
        out.append(("drive", "Inicialização e carregamentos", grade(disk, 700, 150),
                    "Disco rápido: o sistema liga e os programas abrem em poucos segundos." if disk >= 700 else
                    "Disco razoável; carregamentos longos podem ocorrer." if disk >= 150 else
                    "Disco lento (provavelmente HD mecânico). Trocar por um SSD é o upgrade mais perceptível."))
    return out


# =========================================================================== processador
def _cpu_data():
    rnd = random.Random(1234)
    words = [bytes(rnd.choice(b"abcdefghijklmnopqrstuvwxyz") for _ in range(rnd.randint(2, 10)))
             for _ in range(2000)]
    text = b" ".join(rnd.choice(words) for _ in range(60000))[:256 * 1024]
    return os.urandom(1 << 20), text


_DATA = None


def _cpu_op(data):
    """Uma 'operação': BLAKE2b de 1 MiB + compressão e descompressão de 256 KiB (tudo libera o GIL).

    BLAKE2b (e não SHA-256) porque não tem aceleração por hardware: SHA-256 fica até 5x mais rápido em
    processadores com instruções SHA, o que distorceria a comparação entre máquinas.
    """
    blob, text = data
    hashlib.blake2b(blob).digest()
    z = zlib.compress(text, 6)
    zlib.decompress(z)


def cpu_test(seconds=4.0, threads=1, cancel=None, progress=None) -> float:
    """Retorna operações por segundo."""
    global _DATA
    if _DATA is None:
        _DATA = _cpu_data()
    data = _DATA
    _cpu_op(data)  # aquecimento
    cancel = cancel or threading.Event()
    counts = [0] * threads
    start = time.perf_counter()
    deadline = start + seconds

    def worker(i):
        n = 0
        while not cancel.is_set() and time.perf_counter() < deadline:
            _cpu_op(data)
            n += 1
            counts[i] = n
        return n

    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = [ex.submit(worker, i) for i in range(threads)]
        while not all(f.done() for f in futs):
            el = time.perf_counter() - start
            if progress:
                progress(min(1.0, el / seconds), sum(counts) / max(el, 1e-6))
            time.sleep(0.1)
        total = sum(f.result() for f in futs)
    el = time.perf_counter() - start
    return total / el if el > 0 else 0.0


# =========================================================================== memória
def memory_test(seconds=3.0, size_mb=256, cancel=None, progress=None) -> float:
    """Largura de banda de cópia (MB/s): lê o buffer de origem e escreve o de destino."""
    cancel = cancel or threading.Event()
    size = size_mb << 20
    try:
        src = bytearray(os.urandom(1 << 20)) * size_mb
        dst = bytearray(size)
    except MemoryError:
        size_mb = 64
        size = size_mb << 20
        src = bytearray(size)
        dst = bytearray(size)
    ms, md = memoryview(src), memoryview(dst)
    md[:] = ms  # aquecimento (aloca as páginas de verdade)
    copied = 0
    start = time.perf_counter()
    while not cancel.is_set():
        md[:] = ms
        copied += size  # convenção: MB copiados por segundo (cada MB é lido e escrito)
        el = time.perf_counter() - start
        if progress:
            progress(min(1.0, el / seconds), copied / el / 1e6)
        if el >= seconds:
            break
    el = time.perf_counter() - start
    ms.release()
    md.release()
    return copied / el / 1e6 if el > 0 else 0.0


# =========================================================================== disco
def system_temp_dir() -> str:
    """Pasta temporária na unidade do sistema."""
    if IS_WIN:
        sysdrive = os.environ.get("SystemDrive", "C:") + "\\"
        t = tempfile.gettempdir()
        if os.path.splitdrive(t)[0].lower() == sysdrive[:2].lower():
            return t
        return os.path.join(sysdrive, "Windows", "Temp")
    return "/var/tmp" if os.access("/var/tmp", os.W_OK) else tempfile.gettempdir()


def cleanup_stale(directory: str) -> None:
    """Apaga arquivos de teste deixados por uma execução interrompida à força."""
    for p in glob.glob(os.path.join(directory, TMP_PREFIX + "*.tmp")):
        try:
            os.remove(p)
        except OSError:
            pass


def pick_size(directory: str) -> int:
    """512 MiB a 1 GiB conforme o espaço livre; 0 se não houver espaço suficiente."""
    try:
        free = shutil.disk_usage(directory).free
    except OSError:
        return 0
    if free > 8 << 30:
        return 1 << 30
    if free > 3 << 30:
        return 768 << 20
    if free > 1536 << 20:
        return 512 << 20
    return 0


class _Reader:
    """Leitura que evita o cache do sistema.

    Windows: CreateFileW + FILE_FLAG_NO_BUFFERING, buffer alinhado de VirtualAlloc.
    Linux:   O_DIRECT com buffer de mmap anônimo (alinhado à página).
    Se a leitura direta não for suportada (ex.: alguns sistemas de arquivos, rede ou tmpfs) cai para leitura
    comum depois de pedir ao sistema que descarte o cache do arquivo (posix_fadvise DONTNEED no Linux). Nesse
    caso `direct` fica False e a página avisa que o resultado pode estar inflado pelo cache.
    """

    def __init__(self, path, bufsize):
        self.path, self.bufsize, self.direct = path, bufsize, False
        self.fd = self.handle = self.addr = None
        self.buf = None
        if IS_WIN:
            self._open_win()
        else:
            self._open_posix()

    # ---- Windows
    def _open_win(self):
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateFileW.restype = wintypes.HANDLE
        k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        k32.VirtualAlloc.restype = ctypes.c_void_p
        k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
        k32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
        k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                 ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        k32.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wintypes.DWORD]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.k32, self.wt = k32, wintypes
        GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING = 0x80000000, 0x1, 3
        FILE_FLAG_NO_BUFFERING, FILE_FLAG_SEQUENTIAL_SCAN = 0x20000000, 0x08000000
        h = k32.CreateFileW(self.path, GENERIC_READ, FILE_SHARE_READ | 0x2 | 0x4, None, OPEN_EXISTING,
                            FILE_FLAG_NO_BUFFERING | FILE_FLAG_SEQUENTIAL_SCAN, None)
        if h and h != ctypes.c_void_p(-1).value:
            addr = k32.VirtualAlloc(None, self.bufsize, 0x1000 | 0x2000, 0x04)  # COMMIT|RESERVE, READWRITE
            if addr:
                self.handle, self.addr, self.direct = h, addr, True
                return
            k32.CloseHandle(h)
        self.fd = os.open(self.path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        self.buf = bytearray(self.bufsize)

    # ---- Linux / outros
    def _open_posix(self):
        self.buf = mmap.mmap(-1, self.bufsize)  # alinhado à página, exigência do O_DIRECT
        if hasattr(os, "O_DIRECT"):
            try:
                fd = os.open(self.path, os.O_RDONLY | os.O_DIRECT)
                try:
                    os.preadv(fd, [memoryview(self.buf)[:RAND_BLOCK]], 0)  # testa se o FS aceita
                    self.fd, self.direct = fd, True
                    return
                except OSError:
                    os.close(fd)
            except OSError:
                pass
        self.fd = os.open(self.path, os.O_RDONLY)
        if hasattr(os, "posix_fadvise"):
            try:
                os.posix_fadvise(self.fd, 0, 0, os.POSIX_FADV_DONTNEED)
            except OSError:
                pass

    def read_at(self, offset, n) -> int:
        """Lê n bytes (múltiplo de 4096) na posição offset; retorna bytes lidos."""
        if self.handle is not None:
            k32 = self.k32
            got = self.wt.DWORD(0)
            if not k32.SetFilePointerEx(self.handle, offset, None, 0):
                raise OSError(ctypes.get_last_error(), "SetFilePointerEx falhou")
            if not k32.ReadFile(self.handle, ctypes.c_void_p(self.addr), n, ctypes.byref(got), None):
                raise OSError(ctypes.get_last_error(), "ReadFile falhou")
            return got.value
        if hasattr(os, "preadv"):
            return os.preadv(self.fd, [memoryview(self.buf)[:n]], offset)
        os.lseek(self.fd, offset, 0)
        return len(os.read(self.fd, n))

    def close(self):
        try:
            if self.handle is not None:
                self.k32.CloseHandle(self.handle)
                self.handle = None
            if self.addr:
                self.k32.VirtualFree(ctypes.c_void_p(self.addr), 0, 0x8000)  # MEM_RELEASE
                self.addr = None
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            if isinstance(self.buf, mmap.mmap):
                self.buf.close()
        except (OSError, BufferError):
            pass


def disk_test(directory=None, cancel=None, progress=None, size=None, max_write_s=14.0, max_read_s=12.0,
              rand_s=5.0) -> dict:
    """Escrita e leitura sequenciais e leitura aleatória de 4 KiB num arquivo temporário.

    `progress(fase, fração, valor_atual)` com fase em write|read|rand. O arquivo é SEMPRE apagado.
    Retorna {disk_write, disk_read (MB/s), disk_iops, direct, size, dir} ou {"error": texto}.
    """
    cancel = cancel or threading.Event()
    directory = directory or system_temp_dir()
    prog = progress or (lambda *a: None)
    cleanup_stale(directory)
    size = size or pick_size(directory)
    if not size:
        return {"error": "Pouco espaço livre na unidade do sistema para o teste de disco (precisa de 1,5 GB)."}
    fd_w, path = tempfile.mkstemp(prefix=TMP_PREFIX, suffix=".tmp", dir=directory)
    out = {"dir": directory}
    reader = None
    try:
        # ---------------- escrita sequencial (blocos com conteúdo variado, fsync no final)
        block = bytearray(os.urandom(CHUNK))
        written, start = 0, time.perf_counter()
        while written < size and not cancel.is_set():
            block[:8] = written.to_bytes(8, "little")   # evita deduplicação/compressão de blocos iguais
            os.write(fd_w, block)
            written += CHUNK
            el = time.perf_counter() - start
            prog("write", written / size, written / el / 1e6 if el else 0)
            if el > max_write_s:   # disco lento: para mais cedo e mede o que deu
                break
        os.fsync(fd_w)
        el = time.perf_counter() - start
        if cancel.is_set():
            return {"cancelled": True}
        out["disk_write"] = written / el / 1e6 if el else 0.0
        out["size"] = written
        if hasattr(os, "posix_fadvise"):
            try:
                os.posix_fadvise(fd_w, 0, 0, os.POSIX_FADV_DONTNEED)
            except OSError:
                pass
        os.close(fd_w)
        fd_w = None

        # ---------------- leitura sequencial
        reader = _Reader(path, CHUNK)
        out["direct"] = reader.direct
        if not IS_WIN:
            # No Linux o arquivo pode sumir do diretório já: o descritor aberto continua válido e o
            # espaço é liberado sozinho quando ele for fechado (mesmo se o programa for encerrado à força).
            try:
                os.remove(path)
            except OSError:
                pass
        pos, start = 0, time.perf_counter()
        while pos < written and not cancel.is_set():
            n = reader.read_at(pos, CHUNK)
            if n <= 0:
                break
            pos += n
            el = time.perf_counter() - start
            prog("read", pos / written, pos / el / 1e6 if el else 0)
            if el > max_read_s:
                break
        el = time.perf_counter() - start
        if cancel.is_set():
            return {"cancelled": True}
        out["disk_read"] = pos / el / 1e6 if el else 0.0

        # ---------------- leitura aleatória 4 KiB (fila 1)
        blocks = written // RAND_BLOCK
        rnd = random.Random()
        n, start = 0, time.perf_counter()
        while not cancel.is_set():
            reader.read_at(rnd.randrange(blocks) * RAND_BLOCK, RAND_BLOCK)
            n += 1
            if n % 64 == 0:
                el = time.perf_counter() - start
                prog("rand", el / rand_s, n / el)
                if el >= rand_s:
                    break
        el = time.perf_counter() - start
        if cancel.is_set():
            return {"cancelled": True}
        out["disk_iops"] = n / el if el else 0.0
        return out
    finally:
        if fd_w is not None:
            try:
                os.close(fd_w)
            except OSError:
                pass
        if reader:
            reader.close()
        for _ in range(5):  # no Windows o antivírus pode segurar o arquivo por um instante
            try:
                if os.path.exists(path):
                    os.remove(path)
                break
            except OSError:
                time.sleep(0.2)


# =========================================================================== execução completa
STAGES = [  # chave, título, peso aproximado de tempo (para a barra de progresso geral)
    ("cpu1", "Processador (1 núcleo)", 4),
    ("cpuN", "Processador (todos os núcleos)", 5),
    ("mem", "Memória", 3),
    ("disk", "Disco", 25),
]


def run_all(state: dict, cancel: threading.Event, disk_dir=None, quick=1.0):
    """Roda todos os testes atualizando `state` (lido pela interface via after()).

    state: stage, stage_frac, live (valor parcial), results (dict), error, done.
    `quick` < 1 encurta os testes (usado nos testes de desenvolvimento).
    """
    res = state.setdefault("results", {})
    threads = os.cpu_count() or 1
    state["threads"] = threads

    def upd(stage, frac, live):
        state["stage"], state["stage_frac"], state["live"] = stage, max(0.0, min(1.0, frac)), live

    try:
        upd("cpu1", 0, 0)
        res["cpu1"] = cpu_test(4.0 * quick, 1, cancel, lambda f, v: upd("cpu1", f, v))
        if cancel.is_set():
            return
        upd("cpuN", 0, 0)
        res["cpuN"] = cpu_test(5.0 * quick, threads, cancel, lambda f, v: upd("cpuN", f, v))
        if cancel.is_set():
            return
        upd("mem", 0, 0)
        res["mem"] = memory_test(3.0 * quick, 256, cancel, lambda f, v: upd("mem", f, v))
        if cancel.is_set():
            return

        def dprog(phase, f, v):
            key = {"write": "disk_write", "read": "disk_read", "rand": "disk_iops"}[phase]
            base = {"write": 0, "read": 0.45, "rand": 0.8}[phase]
            span = {"write": 0.45, "read": 0.35, "rand": 0.2}[phase]
            state["disk_phase"] = key
            upd("disk", base + span * min(1.0, f), v)

        upd("disk", 0, 0)
        d = disk_test(disk_dir, cancel, dprog, size=state.get("disk_size"),
                      max_write_s=14.0 * quick, max_read_s=12.0 * quick, rand_s=5.0 * quick)
        if "error" in d:
            state["disk_error"] = d["error"]
        else:
            for k in ("disk_write", "disk_read", "disk_iops", "direct", "size"):
                if k in d:
                    res[k] = d[k]
    except Exception as e:  # noqa: BLE001
        state["error"] = str(e)
    finally:
        state["done"] = True
