"""Recuperação de arquivos.

1. Lixeira: lista e restaura itens para o local original (Windows $Recycle.Bin e Lixeira freedesktop).
2. Recuperação profunda NTFS: lê a MFT diretamente do disco e encontra registros de arquivos apagados
   cujos dados ainda não foram sobrescritos.
3. Busca por assinatura ("carving"): varre o disco bruto procurando fotos, vídeos, PDFs e ZIP/Office —
   útil em pendrives e cartões de memória FAT32/exFAT.

Observação importante: em SSDs o comando TRIM costuma zerar os blocos apagados em pouco tempo; nesses
casos a recuperação profunda geralmente não é possível (o programa detecta e avisa).
"""
from __future__ import annotations

import ctypes
import datetime
import glob
import os
import shutil
import struct
import time
import urllib.parse

from .utils import IS_MAC, IS_WIN, Item, fmt_date, fmt_size, home, log

u16 = lambda b, o: struct.unpack_from("<H", b, o)[0]  # noqa: E731
u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]  # noqa: E731
u64 = lambda b, o: struct.unpack_from("<Q", b, o)[0]  # noqa: E731


def _filetime(ft: int) -> float:
    return ft / 10_000_000 - 11644473600 if ft else 0.0


def _unique_path(path: str) -> str:
    if not os.path.lexists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.lexists(f"{base} (recuperado {i}){ext}"):
        i += 1
    return f"{base} (recuperado {i}){ext}"


# =================================================================== 1. LIXEIRA
def _win_recycle_dirs() -> list[str]:
    from .utils import fixed_drives
    out = []
    drives = list(fixed_drives())
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            root = f"{chr(65 + i)}:\\"
            if bitmask & (1 << i) and ctypes.windll.kernel32.GetDriveTypeW(root) == 2 and root not in drives:
                drives.append(root)
    except Exception:  # noqa: BLE001
        pass
    for d in drives:
        base = os.path.join(d, "$Recycle.Bin")
        try:
            for e in os.scandir(base):
                if e.name.upper().startswith("S-1-") and e.is_dir():
                    try:
                        os.listdir(e.path)   # só as pastas do usuário atual são legíveis
                        out.append(e.path)
                    except OSError:
                        pass
        except OSError:
            pass
    return out


def _parse_win_info(data: bytes):
    """Formato dos arquivos $I (Vista+): versão, tamanho, data de exclusão, caminho original."""
    if len(data) < 24:
        return None
    ver, size, ft = struct.unpack_from("<qqq", data, 0)
    if ver == 1:
        name = data[24:24 + 520].decode("utf-16-le", "ignore").split("\0", 1)[0]
    elif ver == 2 and len(data) >= 28:
        n = u32(data, 24)
        name = data[28:28 + n * 2].decode("utf-16-le", "ignore").rstrip("\0")
    else:
        return None
    return name, size, _filetime(ft)


def _freedesktop_trash_dirs() -> list[str]:
    from .system import _linux_trash_dirs
    return _linux_trash_dirs()


def list_trash(cancel=None, progress=lambda s: None) -> list[Item]:
    progress("Lendo a Lixeira…")
    items: list[Item] = []

    def add(name, orig, size, when, data):
        folder = os.path.dirname(orig) if orig else "—"
        items.append(Item(path=data["stored"], size=size,
                          values=(name, fmt_size(size), fmt_date(when), folder),
                          raw=(name.lower(), size, when, folder.lower()), kind="trash", data=data))

    if IS_WIN:
        for d in _win_recycle_dirs():
            for info in glob.glob(os.path.join(d, "$I*")):
                try:
                    with open(info, "rb") as f:
                        parsed = _parse_win_info(f.read())
                except OSError:
                    continue
                if not parsed:
                    continue
                orig, size, when = parsed
                stored = os.path.join(d, "$R" + os.path.basename(info)[2:])
                if not os.path.lexists(stored):
                    continue
                if os.path.isdir(stored):
                    from .utils import entry_size
                    size = entry_size(stored)[0]
                add(os.path.basename(orig), orig, size, when, {"stored": stored, "info": info, "orig": orig})
    elif IS_MAC:
        t = os.path.expanduser("~/.Trash")
        for e in (os.scandir(t) if os.path.isdir(t) else []):
            from .utils import entry_size
            st = e.stat(follow_symlinks=False)
            add(e.name, "", entry_size(e.path)[0], st.st_mtime,
                {"stored": e.path, "info": None, "orig": os.path.join(home(), "Desktop", e.name)})
    else:
        from .utils import entry_size
        for d in _freedesktop_trash_dirs():
            files_dir, info_dir = os.path.join(d, "files"), os.path.join(d, "info")
            for info in glob.glob(os.path.join(info_dir, "*.trashinfo")):
                name = os.path.basename(info)[:-10]
                stored = os.path.join(files_dir, name)
                if not os.path.lexists(stored):
                    continue
                orig, when = "", 0.0
                try:
                    with open(info, encoding="utf-8", errors="replace") as f:
                        for line in f:
                            if line.startswith("Path="):
                                orig = urllib.parse.unquote(line[5:].strip())
                                if not os.path.isabs(orig):   # lixeira de outra unidade: caminho relativo
                                    orig = os.path.join(os.path.dirname(os.path.dirname(d)), orig)
                            elif line.startswith("DeletionDate="):
                                try:
                                    when = datetime.datetime.fromisoformat(line[13:].strip()).timestamp()
                                except ValueError:
                                    pass
                except OSError:
                    continue
                add(os.path.basename(orig) or name, orig, entry_size(stored)[0], when,
                    {"stored": stored, "info": info, "orig": orig or os.path.join(home(), name)})
    items.sort(key=lambda i: i.raw[2], reverse=True)
    progress(f"{len(items)} item(ns) na Lixeira.")
    return items


def restore_trash_item(it: Item) -> str:
    """Devolve o item ao local original. Retorna o caminho final."""
    orig = it.data["orig"]
    os.makedirs(os.path.dirname(orig), exist_ok=True)
    dest = _unique_path(orig)
    shutil.move(it.data["stored"], dest)
    if it.data.get("info"):
        try:
            os.remove(it.data["info"])
        except OSError:
            pass
    log(f"RESTAURADO DA LIXEIRA {dest}")
    return dest


# =================================================================== volumes brutos
class RawVolume:
    """Leitura alinhada de um volume bruto (\\\\.\\C:) ou de um arquivo de imagem."""
    ALIGN = 4096

    def __init__(self, path: str):
        self.path = path
        self.f = open(path, "rb", buffering=0)
        self.size = self._size()

    def _size(self) -> int:
        try:
            self.f.seek(0, os.SEEK_END)
            n = self.f.tell()
            if n > 0:
                return n
        except OSError:
            pass
        if IS_WIN and self.path.startswith("\\\\.\\"):
            try:
                return shutil.disk_usage(self.path[4:] + "\\").total
            except OSError:
                pass
        return 0

    def read(self, offset: int, size: int) -> bytes:
        a = offset - offset % self.ALIGN
        end = offset + size
        b = -(-end // self.ALIGN) * self.ALIGN
        if self.size:
            b = min(b, -(-self.size // 512) * 512)
        if b <= a:
            return b""
        self.f.seek(a)
        data = self.f.read(b - a) or b""
        return data[offset - a: offset - a + size]

    def close(self):
        try:
            self.f.close()
        except OSError:
            pass


def detect_fs(vol: RawVolume) -> str:
    bs = vol.read(0, 512)
    if bs[3:11] == b"NTFS    ":
        return "NTFS"
    if bs[3:11] == b"EXFAT   ":
        return "exFAT"
    if bs[0x52:0x57] == b"FAT32":
        return "FAT32"
    if bs[0x36:0x39] == b"FAT":
        return "FAT"
    return "desconhecido"


def list_volumes() -> list[tuple[str, str, str]]:
    """[(rótulo exibido, caminho bruto, raiz de montagem)]"""
    out = []
    if IS_WIN:
        k32 = ctypes.windll.kernel32
        bitmask = k32.GetLogicalDrives()
        for i in range(26):
            if not bitmask & (1 << i):
                continue
            root = f"{chr(65 + i)}:\\"
            dtype = k32.GetDriveTypeW(root)
            if dtype not in (2, 3):
                continue
            label = ctypes.create_unicode_buffer(261)
            fsname = ctypes.create_unicode_buffer(261)
            ok = k32.GetVolumeInformationW(root, label, 261, None, None, None, fsname, 261)
            kind = "Removível" if dtype == 2 else "Disco local"
            text = f"{root[:2]}  {label.value or kind}  ({fsname.value if ok else '?'})"
            out.append((text, f"\\\\.\\{root[:2]}", root))
    else:
        try:
            with open("/proc/mounts", encoding="utf-8") as f:
                for line in f:
                    dev, mp, fs = line.split()[:3]
                    if dev.startswith("/dev/") and fs in ("ntfs", "ntfs3", "fuseblk", "vfat", "exfat"):
                        out.append((f"{mp}  ({dev}, {fs})", dev, mp))
        except OSError:
            pass
    return out


def is_ssd(drive_root: str) -> bool | None:
    """True/False se for possível descobrir; None se desconhecido."""
    if not IS_WIN:
        return None
    try:
        import subprocess
        letter = drive_root[0]
        ps = (f"$d=(Get-Partition -DriveLetter {letter} | Get-Disk).Number; "
              f"(Get-PhysicalDisk | Where-Object DeviceId -eq $d).MediaType")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                           timeout=20, creationflags=0x08000000)
        out = r.stdout.strip().upper()
        return True if "SSD" in out else False if "HDD" in out else None
    except Exception:  # noqa: BLE001
        return None


# =================================================================== 2. NTFS
def _decode_runs(data: bytes, off: int):
    """Decodifica a lista de execuções (runlist) NTFS → [(lcn ou None, quantidade de clusters)]."""
    runs = []
    lcn = 0
    while off < len(data):
        h = data[off]
        if h == 0:
            break
        ln, lo = h & 0x0F, h >> 4
        off += 1
        if ln == 0 or off + ln + lo > len(data):
            break
        count = int.from_bytes(data[off:off + ln], "little")
        off += ln
        if lo:
            delta = int.from_bytes(data[off:off + lo], "little", signed=True)
            lcn += delta
            runs.append((lcn, count))
        else:
            runs.append((None, count))   # trecho esparso
        off += lo
    return runs


def _fixup(rec: bytes):
    if rec[:4] != b"FILE":
        return None
    usa_ofs, usa_cnt = u16(rec, 4), u16(rec, 6)
    if usa_cnt < 2 or usa_ofs + usa_cnt * 2 > len(rec):
        return None
    b = bytearray(rec)
    stride = len(rec) // (usa_cnt - 1)
    usn = b[usa_ofs:usa_ofs + 2]
    for i in range(1, usa_cnt):
        pos = i * stride - 2
        if b[pos:pos + 2] != usn:
            return None
        b[pos:pos + 2] = b[usa_ofs + 2 * i: usa_ofs + 2 * i + 2]
    return bytes(b)


def _attrs(rec: bytes):
    off = u16(rec, 0x14)
    while off + 16 <= len(rec):
        atype = u32(rec, off)
        if atype == 0xFFFFFFFF:
            break
        alen = u32(rec, off + 4)
        if alen < 16 or off + alen > len(rec):
            break
        a = {"type": atype, "nonres": rec[off + 8], "name_len": rec[off + 9], "off": off, "len": alen}
        if a["nonres"]:
            a["real_size"] = u64(rec, off + 0x30)
            a["runs"] = _decode_runs(rec[off:off + alen], u16(rec, off + 0x20))
            a["start_vcn"] = u64(rec, off + 0x10)
        else:
            vlen, voff = u32(rec, off + 0x10), u16(rec, off + 0x14)
            a["value"] = rec[off + voff: off + voff + vlen]
        yield a
        off += alen


class DeletedFile:
    __slots__ = ("recno", "name", "parent", "parent_seq", "size", "mtime", "resident", "runs", "chance",
                 "path", "used_frac")

    def __init__(self):
        self.resident = None
        self.runs = []
        self.chance = ""
        self.path = ""
        self.used_frac = 0.0


class Ntfs:
    def __init__(self, vol: RawVolume):
        self.vol = vol
        bs = vol.read(0, 512)
        if bs[3:11] != b"NTFS    ":
            raise ValueError("a unidade não está formatada em NTFS")
        self.bps = u16(bs, 0x0B)
        self.cluster = self.bps * bs[0x0D]
        self.mft_lcn = u64(bs, 0x30)
        cpr = struct.unpack_from("<b", bs, 0x40)[0]
        self.rec_size = cpr * self.cluster if cpr > 0 else 1 << -cpr
        self.total_clusters = u64(bs, 0x28) * self.bps // self.cluster
        rec0 = _fixup(vol.read(self.mft_lcn * self.cluster, self.rec_size))
        if not rec0:
            raise ValueError("não foi possível ler a tabela de arquivos (MFT)")
        data = next((a for a in _attrs(rec0) if a["type"] == 0x80 and a["nonres"] and not a["name_len"]), None)
        if not data:
            raise ValueError("MFT inválida")
        self.mft_runs = data["runs"]
        self.n_records = data["real_size"] // self.rec_size
        self.bitmap = self._read_bitmap()

    def _read_record(self, recno: int):
        """Lê um registro pelo número, seguindo os fragmentos da MFT."""
        target = recno
        for lcn, count in self.mft_runs:
            n = count * self.cluster // self.rec_size
            if target < n:
                if lcn is None:
                    return None
                return _fixup(self.vol.read(lcn * self.cluster + target * self.rec_size, self.rec_size))
            target -= n
        return None

    def _read_bitmap(self) -> bytes:
        rec = self._read_record(6)  # $Bitmap
        if not rec:
            return b""
        a = next((a for a in _attrs(rec) if a["type"] == 0x80 and not a["name_len"]), None)
        if not a:
            return b""
        if not a["nonres"]:
            return a["value"]
        return self.read_runs(a["runs"], a["real_size"])

    def read_runs(self, runs, size, out=None, chunk=4 * 1024 * 1024):
        """Lê os dados de uma lista de execuções. Se `out` (arquivo) for dado, grava nele."""
        parts = [] if out is None else None
        remaining = size
        nonzero = False
        for lcn, count in runs:
            if remaining <= 0:
                break
            length = min(count * self.cluster, remaining)
            pos = 0
            while pos < length:
                n = min(chunk, length - pos)
                data = bytes(n) if lcn is None else self.vol.read(lcn * self.cluster + pos, n)
                if len(data) < n:
                    data += bytes(n - len(data))
                if not nonzero and data.strip(b"\0"):
                    nonzero = True
                if out is None:
                    parts.append(data)
                else:
                    out.write(data)
                pos += n
            remaining -= length
        self.last_nonzero = nonzero
        return b"".join(parts) if parts is not None else None

    def _used_fraction(self, runs) -> float:
        if not self.bitmap:
            return 0.0
        total = used = 0
        bm = self.bitmap
        for lcn, count in runs:
            if lcn is None:
                continue
            total += count
            a, b = lcn >> 3, (lcn + count + 7) >> 3
            bits = int.from_bytes(bm[a:b], "little") >> (lcn - a * 8)
            used += bin(bits & ((1 << count) - 1)).count("1")
        return min(1.0, used / total) if total else 0.0

    def scan_deleted(self, drive_label: str, cancel, progress) -> list[DeletedFile]:
        dirs: dict[int, tuple] = {}
        found: list[DeletedFile] = []
        recno = 0
        batch = 1024
        last = 0.0
        for lcn, count in self.mft_runs:
            n_in_run = count * self.cluster // self.rec_size
            if lcn is None:
                recno += n_in_run
                continue
            base = lcn * self.cluster
            i = 0
            while i < n_in_run and recno < self.n_records:
                if cancel.is_set():
                    return []
                k = min(batch, n_in_run - i, self.n_records - recno)
                blob = self.vol.read(base + i * self.rec_size, k * self.rec_size)
                for j in range(k):
                    raw = blob[j * self.rec_size:(j + 1) * self.rec_size]
                    self._handle(recno + j, raw, dirs, found)
                recno += k
                i += k
                if time.monotonic() - last > 0.2:
                    last = time.monotonic()
                    progress(f"Lendo a tabela de arquivos… {recno * 100 // max(1, self.n_records)}%  ·  "
                             f"{len(found)} apagados encontrados")
        progress("Calculando chances de recuperação…")
        for f in found:
            f.path = self._path(f.parent, dirs, drive_label)
            if f.resident is not None:
                f.chance = "Excelente"
            else:
                f.used_frac = self._used_fraction(f.runs)
                f.chance = "Boa" if f.used_frac == 0 else "Parcial" if f.used_frac < 0.5 else "Baixa"
        return found

    def _handle(self, recno, raw, dirs, found):
        if raw[:4] != b"FILE":
            return
        flags = u16(raw, 0x16)
        in_use, is_dir = flags & 1, flags & 2
        if in_use and not is_dir:
            return
        if u64(raw, 0x20) & 0xFFFFFFFFFFFF:   # registro de extensão
            return
        rec = _fixup(raw)
        if not rec:
            return
        name, parent, pseq, ns_best = None, 0, 0, 99
        data_attr = None
        mtime = 0.0
        for a in _attrs(rec):
            t = a["type"]
            if t == 0x30 and not a["nonres"]:
                v = a["value"]
                if len(v) < 0x42:
                    continue
                nlen, ns = v[0x40], v[0x41]
                rank = {1: 0, 3: 0, 0: 1, 2: 2}.get(ns, 3)
                if rank < ns_best:
                    ns_best = rank
                    name = v[0x42:0x42 + nlen * 2].decode("utf-16-le", "replace")
                    ref = u64(v, 0)
                    parent, pseq = ref & 0xFFFFFFFFFFFF, ref >> 48
            elif t == 0x10 and not a["nonres"] and len(a["value"]) >= 16:
                mtime = _filetime(u64(a["value"], 8))
            elif t == 0x80 and not a["name_len"] and data_attr is None:
                data_attr = a
        if not name:
            return
        if is_dir:
            dirs[recno] = (name, parent)
            return
        if recno < 24 or data_attr is None:
            return
        f = DeletedFile()
        f.recno, f.name, f.parent, f.parent_seq, f.mtime = recno, name, parent, pseq, mtime
        if data_attr["nonres"]:
            if data_attr.get("start_vcn"):
                return   # dados começam em outro registro (arquivo muito fragmentado)
            f.size = data_attr["real_size"]
            f.runs = data_attr["runs"]
        else:
            f.resident = data_attr["value"]
            f.size = len(f.resident)
        if f.size <= 0:
            return
        found.append(f)

    @staticmethod
    def _path(parent, dirs, label):
        parts = []
        seen = set()
        cur = parent
        while cur != 5 and cur not in seen and len(parts) < 64:
            seen.add(cur)
            d = dirs.get(cur)
            if not d:
                parts.append("(pasta desconhecida)")
                break
            parts.append(d[0])
            cur = d[1]
        return label.rstrip("\\/") + "\\" + "\\".join(reversed(parts)) if parts else label

    def recover(self, f: DeletedFile, dest_dir: str) -> tuple[str, bool]:
        """Grava o arquivo em dest_dir. Retorna (caminho, conteúdo_parece_válido)."""
        safe = "".join(ch if ch not in '<>:"/\\|?*' else "_" for ch in f.name) or f"arquivo_{f.recno}"
        dest = _unique_path(os.path.join(dest_dir, safe))
        with open(dest, "wb") as out:
            if f.resident is not None:
                out.write(f.resident[:f.size])
                ok = bool(f.resident.strip(b"\0"))
            else:
                self.read_runs(f.runs, f.size, out=out)
                ok = self.last_nonzero
        if f.mtime:
            try:
                os.utime(dest, (f.mtime, f.mtime))
            except OSError:
                pass
        log(f"RECUPERADO (NTFS) {f.path}\\{f.name} -> {dest}")
        return dest, ok


# =================================================================== 3. BUSCA POR ASSINATURA
_SIGS = {
    "jpg": (b"\xFF\xD8\xFF", "Fotos JPG"),
    "png": (b"\x89PNG\r\n\x1a\n", "Imagens PNG"),
    "pdf": (b"%PDF-", "PDF"),
    "zip": (b"PK\x03\x04", "ZIP / Word / Excel / PowerPoint"),
    "mp4": (b"ftyp", "Vídeos MP4 / MOV"),   # aparece no byte 4
}
CARVE_KINDS = {k: v[1] for k, v in _SIGS.items()}
_MAX = {"jpg": 60 << 20, "png": 60 << 20, "pdf": 200 << 20, "zip": 500 << 20, "mp4": 8 << 30}


class _Reader:
    def __init__(self, vol: RawVolume):
        self.vol = vol
        self.cache_off = -1
        self.cache = b""

    def read(self, off, n):
        if self.cache_off <= off and off + n <= self.cache_off + len(self.cache):
            s = off - self.cache_off
            return self.cache[s:s + n]
        if n > 1 << 20:
            return self.vol.read(off, n)
        self.cache_off = off
        self.cache = self.vol.read(off, max(n, 1 << 20))
        return self.cache[:n]


def _len_jpg(r: _Reader, start, limit):
    pos = start + 2
    while pos < limit:
        hdr = r.read(pos, 4)
        if len(hdr) < 4 or hdr[0] != 0xFF:
            return None
        marker = hdr[1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        seg = (hdr[2] << 8) | hdr[3]
        if marker == 0xDA:   # início dos dados: procurar FFD9
            pos += 2 + seg
            while pos < limit:
                block = r.read(pos, 1 << 20)
                if not block:
                    return None
                i = 0
                while True:
                    i = block.find(b"\xFF", i)
                    if i < 0 or i + 1 >= len(block):
                        break
                    nxt = block[i + 1]
                    if nxt == 0xD9:
                        return pos + i + 2 - start
                    i += 1
                pos += len(block) - 1
            return None
        if seg < 2:
            return None
        pos += 2 + seg
    return None


def _len_png(r: _Reader, start, limit):
    pos = start + 8
    while pos < limit:
        h = r.read(pos, 8)
        if len(h) < 8:
            return None
        ln = struct.unpack(">I", h[:4])[0]
        typ = h[4:8]
        if not typ.isalpha():
            return None
        pos += 12 + ln
        if typ == b"IEND":
            return pos - start
    return None


def _len_mp4(r: _Reader, start, limit):
    pos = start
    seen = set()
    valid = {b"ftyp", b"moov", b"mdat", b"free", b"skip", b"wide", b"uuid", b"meta", b"pdin", b"moof",
             b"mfra", b"sidx", b"udta", b"styp", b"prft"}
    while pos < limit:
        h = r.read(pos, 16)
        if len(h) < 8:
            break
        size = struct.unpack(">I", h[:4])[0]
        typ = h[4:8]
        if typ not in valid:
            break
        if size == 1:
            size = struct.unpack(">Q", h[8:16])[0]
        if size < 8:
            break
        seen.add(typ)
        pos += size
    if b"moov" in seen and b"mdat" in seen:
        return pos - start
    return None


def _len_search_end(r: _Reader, start, limit, end_marker, extra=0, last=False):
    pos = start
    found = None
    while pos < limit:
        block = r.read(pos, min(4 << 20, limit - pos))
        if not block:
            break
        i = block.rfind(end_marker) if last else block.find(end_marker)
        if i >= 0:
            found = pos + i + len(end_marker) + extra
            if not last:
                break
        pos += len(block) - len(end_marker)
        if len(block) < (4 << 20):
            break
    return (found - start) if found else None


def carve(vol: RawVolume, dest_dir: str, kinds, cancel, progress, min_size=8 * 1024) -> dict:
    """Varre o volume inteiro procurando arquivos pelas assinaturas. Retorna contagem por tipo."""
    r = _Reader(vol)
    total = vol.size or 0
    counts = {k: 0 for k in kinds}
    block = 8 << 20
    pos = 0
    last = 0.0
    skip_until = 0
    while True:
        if (total and pos >= total) or cancel.is_set():
            break
        data = vol.read(pos, block)
        if not data:
            break
        hits = []
        for k in kinds:
            sig = _SIGS[k][0]
            i = data.find(sig)
            while i >= 0:
                start = pos + i - (4 if k == "mp4" else 0)
                if start >= 0 and start % 512 == 0 and start >= skip_until:
                    hits.append((start, k))
                i = data.find(sig, i + 1)
        for start, k in sorted(hits):
            if cancel.is_set() or start < skip_until:
                continue
            limit = min(total or start + _MAX[k], start + _MAX[k])
            if k == "jpg":
                ln = _len_jpg(r, start, limit)
            elif k == "png":
                ln = _len_png(r, start, limit)
            elif k == "mp4":
                ln = _len_mp4(r, start, limit)
            elif k == "pdf":
                ln = _len_search_end(r, start, min(limit, start + (60 << 20)), b"%%EOF", extra=1, last=True)
            else:
                ln = _len_search_end(r, start, limit, b"PK\x05\x06", extra=18)
                if ln:
                    tail = r.read(start + ln - 2, 2)
                    ln += struct.unpack("<H", tail)[0] if len(tail) == 2 else 0
            if not ln or ln < min_size:
                continue
            counts[k] += 1
            ext = {"mp4": "mp4", "zip": "zip"}.get(k, k)
            name = os.path.join(dest_dir, f"{k}_{counts[k]:05d}.{ext}")
            with open(name, "wb") as out:
                off = 0
                while off < ln:
                    n = min(8 << 20, ln - off)
                    out.write(vol.read(start + off, n))
                    off += n
            skip_until = start + ln
        pos += block
        if time.monotonic() - last > 0.3:
            last = time.monotonic()
            pct = f"{pos * 100 // total}%" if total else fmt_size(pos)
            progress(f"Varrendo o disco… {pct}  ·  {sum(counts.values())} arquivos recuperados")
    log(f"BUSCA POR ASSINATURA {vol.path}: {counts}")
    return counts
