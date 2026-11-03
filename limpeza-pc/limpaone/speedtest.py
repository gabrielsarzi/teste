"""Teste de velocidade da internet usando os servidores públicos do Cloudflare (speed.cloudflare.com).

Só usa a biblioteca padrão (http.client + threads). A URL base é parametrizável (`SpeedTester(base=...)`)
para testes com um servidor local que implemente as mesmas rotas:
    GET  /__down?bytes=N   devolve N bytes
    POST /__up             aceita o corpo e responde 200
    GET  /meta             (opcional) JSON com clientIp, asOrganization, city, country, colo

Medição
- Latência: 20 requisições minúsculas (/__down?bytes=0) numa conexão já aberta; o tempo de processamento
  informado pelo servidor (cabeçalho Server-Timing) é descontado. Ping = mediana; jitter = média da
  diferença entre amostras consecutivas.
- Download/Upload: várias conexões em paralelo transferindo blocos de tamanho crescente durante um tempo
  fixo. A velocidade final despreza o primeiro 1,5 s (abertura das conexões e “slow start” do TCP).
"""
from __future__ import annotations

import http.client
import json
import os
import re
import ssl
import statistics
import threading
import time
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://speed.cloudflare.com"
UA = "LimpaOne-SpeedTest/1.0"
META_HEADERS = {"asn", "city", "colo", "country", "region"}


class Cancelled(Exception):
    pass


class SpeedTester:
    def __init__(self, base=DEFAULT_BASE, cancel=None, timeout=15):
        u = urllib.parse.urlsplit(base)
        self.scheme, self.host, self.port = u.scheme, u.hostname, u.port
        self.prefix = u.path.rstrip("/")
        self.cancel = cancel or threading.Event()
        self.timeout = timeout
        self.ctx = ssl.create_default_context() if self.scheme == "https" else None
        self.live = 0.0           # Mbps instantâneo (lido pela interface)
        self.headers_meta = {}

    # ------------------------------------------------------------ conexão (respeita proxy do sistema)
    def _conn(self):
        proxy = None
        try:
            if not urllib.request.proxy_bypass(self.host):
                proxy = urllib.request.getproxies().get(self.scheme)
        except Exception:  # noqa: BLE001
            proxy = None
        if self.scheme == "https":
            if proxy:
                p = urllib.parse.urlsplit(proxy if "://" in proxy else "http://" + proxy)
                c = http.client.HTTPSConnection(p.hostname, p.port or 8080, timeout=self.timeout, context=self.ctx)
                c.set_tunnel(self.host, self.port or 443)
                return c
            return http.client.HTTPSConnection(self.host, self.port or 443, timeout=self.timeout, context=self.ctx)
        if proxy:
            p = urllib.parse.urlsplit(proxy if "://" in proxy else "http://" + proxy)
            c = http.client.HTTPConnection(p.hostname, p.port or 8080, timeout=self.timeout)
            c._lp_absolute = True
            return c
        return http.client.HTTPConnection(self.host, self.port or 80, timeout=self.timeout)

    def _path(self, conn, path):
        if getattr(conn, "_lp_absolute", False):  # proxy HTTP simples precisa da URL completa
            port = f":{self.port}" if self.port else ""
            return f"http://{self.host}{port}{self.prefix}{path}"
        return self.prefix + path

    def _check(self):
        if self.cancel.is_set():
            raise Cancelled()

    # ------------------------------------------------------------ informações do provedor
    def meta(self) -> dict:
        """Provedor, IP, cidade… (vazio se o servidor não informar)."""
        info = {}
        conn = self._conn()
        try:
            conn.request("GET", self._path(conn, "/meta"), headers={"User-Agent": UA})
            r = conn.getresponse()
            body = r.read()
            if r.status == 200:
                d = json.loads(body.decode("utf-8", "replace"))
                info = {"ip": d.get("clientIp"), "isp": d.get("asOrganization"), "city": d.get("city"),
                        "region": d.get("region"), "country": d.get("country"), "colo": d.get("colo"),
                        "asn": d.get("asn")}
        except (OSError, ValueError, http.client.HTTPException):
            pass
        finally:
            conn.close()
        # /meta pode ser recusado; os mesmos dados vêm nos cabeçalhos de /__down
        h = self.headers_meta
        for k in ("ip", "city", "country", "colo", "asn"):
            if not info.get(k):
                info[k] = h.get("cf-meta-" + k) or h.get(k)
        return {k: v for k, v in info.items() if v}

    # ------------------------------------------------------------ latência
    def latency(self, samples=20, progress=None) -> tuple[float, float]:
        """Retorna (ping_ms, jitter_ms)."""
        conn = self._conn()
        times = []
        try:
            for i in range(samples + 1):
                self._check()
                t0 = time.perf_counter()
                conn.request("GET", self._path(conn, "/__down?bytes=0"), headers={"User-Agent": UA})
                r = conn.getresponse()
                r.read()
                dt = (time.perf_counter() - t0) * 1000
                if r.status >= 400:
                    raise OSError(f"O servidor respondeu {r.status} {r.reason}")
                if i == 0:  # a primeira inclui DNS/TCP/TLS: só aquece a conexão
                    self.headers_meta = {k.lower(): v for k, v in r.getheaders()
                                         if k.lower().startswith("cf-meta") or k.lower() in META_HEADERS}
                    continue
                durs = [float(x) for x in re.findall(r"dur=([\d.]+)", r.getheader("Server-Timing", "") or "")]
                if durs:  # tempo gasto dentro do servidor não é latência de rede
                    dt = max(0.1, dt - max(durs))
                times.append(dt)
                if progress:
                    progress(i / samples, statistics.median(times))
        finally:
            conn.close()
        ping = statistics.median(times)
        jitter = statistics.mean(abs(a - b) for a, b in zip(times, times[1:])) if len(times) > 1 else 0.0
        return ping, jitter

    # ------------------------------------------------------------ transferência
    def _measure(self, worker, duration, streams, progress):
        total = [0]
        lock = threading.Lock()
        stop = threading.Event()
        errors = []

        def add(n):
            with lock:
                total[0] += n

        def run():
            try:
                worker(add, stop)
            except Cancelled:
                pass
            except (OSError, http.client.HTTPException) as e:
                errors.append(e)

        ths = [threading.Thread(target=run, daemon=True) for _ in range(streams)]
        start = time.perf_counter()
        for t in ths:
            t.start()
        warm = 1.5
        base_b, base_t = None, None
        samples = []  # (t, bytes) para velocidade instantânea
        while True:
            time.sleep(0.1)
            now = time.perf_counter() - start
            b = total[0]
            samples.append((now, b))
            while len(samples) > 2 and samples[0][0] < now - 1.0:
                samples.pop(0)
            t0, b0 = samples[0]
            self.live = (b - b0) * 8 / (now - t0) / 1e6 if now > t0 else 0.0
            if base_b is None and now >= warm:
                base_b, base_t = b, now
            if progress:
                progress(min(1.0, now / duration), self.live)
            if self.cancel.is_set() or now >= duration or not any(t.is_alive() for t in ths):
                break
        stop.set()
        end_b, end_t = total[0], time.perf_counter() - start
        for t in ths:
            t.join(timeout=3)
        self._check()
        if base_b is None or end_t - base_t < 0.5:  # transferência muito curta: usa tudo
            base_b, base_t = 0, 0.0
        if end_b == 0 and errors:
            raise errors[0]
        return (end_b - base_b) * 8 / (end_t - base_t) / 1e6 if end_t > base_t else 0.0

    def download(self, duration=10.0, streams=6, progress=None) -> float:
        """Mbps de download."""
        def worker(add, stop):
            size = 1 << 20
            conn = self._conn()
            try:
                while not stop.is_set():
                    self._check()
                    t0 = time.perf_counter()
                    conn.request("GET", self._path(conn, f"/__down?bytes={size}"), headers={"User-Agent": UA})
                    r = conn.getresponse()
                    if r.status >= 400:
                        r.read()
                        raise OSError(f"O servidor respondeu {r.status} {r.reason}")
                    while True:
                        chunk = r.read(65536)
                        if not chunk:
                            break
                        add(len(chunk))
                        if stop.is_set() or self.cancel.is_set():
                            return  # fecha a conexão no meio da resposta
                    if time.perf_counter() - t0 < 1.0:
                        size = min(size * 2, 100 << 20)
            finally:
                conn.close()
        return self._measure(worker, duration, streams, progress)

    def upload(self, duration=8.0, streams=4, progress=None) -> float:
        """Mbps de upload."""
        chunk = os.urandom(65536)

        def worker(add, stop):
            size = 1 << 20
            conn = self._conn()
            try:
                while not stop.is_set():
                    self._check()
                    t0 = time.perf_counter()
                    conn.putrequest("POST", self._path(conn, "/__up"), skip_accept_encoding=True)
                    conn.putheader("User-Agent", UA)
                    conn.putheader("Content-Type", "application/octet-stream")
                    conn.putheader("Content-Length", str(size))
                    conn.endheaders()
                    sent = 0
                    while sent < size:
                        n = min(len(chunk), size - sent)
                        conn.send(chunk[:n] if n < len(chunk) else chunk)
                        sent += n
                        add(n)
                        if stop.is_set() or self.cancel.is_set():
                            return
                    r = conn.getresponse()
                    r.read()
                    if r.status >= 400:
                        raise OSError(f"O servidor respondeu {r.status} {r.reason}")
                    if time.perf_counter() - t0 < 1.0:
                        size = min(size * 2, 50 << 20)
            finally:
                conn.close()
        return self._measure(worker, duration, streams, progress)


# =========================================================================== interpretação
def interpret(down, up, ping, jitter) -> list[tuple[str, str, str]]:
    """Lista de (título, situação ok|warn|bad, explicação) para usos comuns."""
    out = []
    out.append(("Streaming em 4K", "ok" if down >= 25 else "warn" if down >= 10 else "bad",
                "Netflix/YouTube em 4K sem travar (precisa de ~25 Mbps)." if down >= 25 else
                "Full HD funciona bem; 4K pode baixar a qualidade." if down >= 10 else
                "Prefira qualidade padrão (SD/HD) nos vídeos."))
    calls_ok = up >= 3 and down >= 5 and ping < 150 and jitter < 30
    calls_warn = up >= 1 and down >= 2 and ping < 300
    out.append(("Chamadas de vídeo", "ok" if calls_ok else "warn" if calls_warn else "bad",
                "Videochamadas em HD (Meet, Teams, Zoom, WhatsApp) com boa imagem e áudio." if calls_ok else
                "Funciona, mas a imagem pode cair de qualidade ou o áudio picotar." if calls_warn else
                "Chamadas de vídeo devem travar; use só áudio se possível."))
    game = "ok" if ping < 50 and jitter < 15 else "warn" if ping < 100 and jitter < 30 else "bad"
    out.append(("Jogos on-line", game,
                f"Ping de {ping:.0f} ms: ótimo até para jogos competitivos." if game == "ok" else
                f"Ping de {ping:.0f} ms: jogável, mas pode haver atraso em jogos de tiro e luta." if game == "warn"
                else f"Ping de {ping:.0f} ms (variação {jitter:.0f} ms): espere atraso (“lag”). "
                     "Use cabo em vez de Wi-Fi."))
    if down > 0:
        secs = 50 * 8000 / down  # 50 GB
        out.append(("Baixar um jogo de 50 GB", "ok" if secs < 1800 else "warn" if secs < 4 * 3600 else "bad",
                    f"Leva cerca de {fmt_duration(secs)}."))
    if up > 0:
        secs = 1 * 8000 / up  # 1 GB
        out.append(("Enviar 1 GB para a nuvem", "ok" if secs < 300 else "warn" if secs < 1800 else "bad",
                    f"Leva cerca de {fmt_duration(secs)} (backup de fotos, vídeos)."))
    return out


def fmt_duration(secs: float) -> str:
    secs = int(secs)
    if secs < 60:
        return f"{max(1, secs)} s"
    if secs < 3600:
        return f"{round(secs / 60)} min"
    h, m = divmod(round(secs / 60), 60)
    return f"{h} h {m:02d} min" if m else f"{h} h"


def fmt_mbps(v: float) -> str:
    if v >= 100:
        s = f"{v:.0f}"
    elif v >= 10:
        s = f"{v:.1f}"
    else:
        s = f"{v:.2f}"
    return s.replace(".", ",")
