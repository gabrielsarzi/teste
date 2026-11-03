"""Drivers: lista dispositivos e seus drivers, procura atualizações no Windows Update oficial
(COM Microsoft.Update.Session), instala as escolhidas e faz backup com pnputil.

Tudo degrada com segurança fora do Windows (no Linux lista os módulos do kernel de cada dispositivo PCI/USB).
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import tempfile

from .utils import IS_LINUX, IS_WIN, log
from .winutil import PS_PREFIX, NotWindows, run, run_ps_elevated

# funções PowerShell comuns aos scripts (datas CIM -> texto ISO; números de registro)
PS_FUNCS = r"""
function D($v, $f = 'yyyy-MM-dd') {
  if ($v -is [datetime]) { return $v.ToString($f) }
  if ($v -is [string] -and $v.Length -ge 8) { return $v }
  return $null
}
"""

OLD_YEARS = 3


# =================================================================== utilitários
def run_ps_file(script: str, timeout=180) -> tuple[int, str, str]:
    """Executa um script PowerShell gravado em arquivo .ps1 temporário (evita problemas de aspas e de
    tamanho da linha de comando). Retorna (código, stdout, stderr)."""
    if not IS_WIN:
        return 1, "", "disponível apenas no Windows"
    tmp = tempfile.mkdtemp(prefix="limpapc_")
    ps1 = os.path.join(tmp, "script.ps1")
    try:
        with open(ps1, "w", encoding="utf-8-sig") as f:
            f.write(PS_PREFIX + "\n" + PS_FUNCS + "\n" + script)
        return run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", ps1],
                   timeout=timeout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def parse_json(text: str):
    """Converte a saída do PowerShell em objeto Python (ignora lixo antes/depois do JSON)."""
    text = (text or "").strip().lstrip("﻿")
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        a, b = text.find(open_c), text.rfind(close_c)
        if a != -1 and b > a:
            try:
                return json.loads(text[a:b + 1])
            except ValueError:
                continue
    return None


def as_list(v) -> list:
    """O ConvertTo-Json devolve um objeto solto quando a lista tem um item só, e nada quando está vazia."""
    if v is None:
        return []
    if isinstance(v, list):
        return [x for x in v if x is not None]
    return [v]


def s(v) -> str:
    """Texto limpo (None -> '')."""
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(s(x) for x in v if x not in (None, ""))
    return str(v).strip()


def to_int(v, default=0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        return default


_DATE_MS = re.compile(r"/Date\((-?\d+)")


def parse_date(v) -> datetime.date | None:
    """Aceita 'yyyy-MM-dd', 'yyyy-MM-ddTHH:mm:ss', '/Date(ms)/' (JSON do PS 5.1) e '20230115000000.000000-000'
    (formato WMI/DMTF)."""
    if not v:
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(v).date()
        except (OverflowError, OSError, ValueError):
            return None
    txt = str(v).strip()
    m = _DATE_MS.search(txt)
    try:
        if m:
            return (datetime.datetime(1970, 1, 1) + datetime.timedelta(milliseconds=int(m.group(1)))).date()
        if re.match(r"^\d{14}", txt):
            return datetime.date(int(txt[:4]), int(txt[4:6]), int(txt[6:8]))
        if re.match(r"^\d{4}-\d{2}-\d{2}", txt):
            return datetime.date(int(txt[:4]), int(txt[5:7]), int(txt[8:10]))
        if re.match(r"^\d{1,2}/\d{1,2}/\d{4}", txt):  # m/d/aaaa (formato dos INF)
            mo, d, y = txt.split()[0].split("/")
            return datetime.date(int(y), int(mo), int(d))
    except (ValueError, OverflowError):
        return None
    return None


def fmt_d(d: datetime.date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


# =================================================================== códigos de erro do Gerenciador de Dispositivos
CM_ERRORS = {
    1: "não está configurado corretamente",
    3: "driver corrompido ou falta de memória",
    9: "firmware informou recursos inválidos",
    10: "o dispositivo não pode ser iniciado",
    12: "recursos insuficientes (conflito)",
    14: "reinicie o computador para funcionar",
    16: "o Windows não identificou todos os recursos",
    18: "reinstale os drivers",
    19: "configuração do registro corrompida",
    21: "o Windows está removendo o dispositivo",
    22: "desativado",
    24: "ausente ou sem todos os drivers",
    28: "driver não instalado",
    29: "desativado pelo firmware (BIOS)",
    31: "o Windows não conseguiu carregar o driver",
    32: "serviço do driver desativado",
    33: "não foi possível determinar os recursos",
    34: "precisa de configuração manual",
    35: "firmware (BIOS) sem as informações necessárias",
    36: "conflito de interrupção (IRQ)",
    37: "o driver retornou uma falha",
    38: "driver ainda carregado de uma instância anterior",
    39: "driver corrompido ou ausente",
    40: "chave de serviço do registro inválida",
    41: "driver carregado, mas o dispositivo não foi encontrado",
    42: "dispositivo duplicado",
    43: "o dispositivo relatou um problema e foi parado",
    44: "um aplicativo ou serviço desligou o dispositivo",
    45: "não está conectado",
    46: "o Windows está desligando",
    47: "preparado para remoção segura",
    48: "driver bloqueado por incompatibilidade",
    49: "registro do sistema muito grande",
    50: "propriedades do dispositivo não puderam ser aplicadas",
    51: "aguardando outro dispositivo iniciar",
    52: "assinatura digital do driver não verificada",
    53: "reservado pelo depurador do kernel",
    54: "falhou e está sendo reiniciado",
    56: "configuração de rede incompleta",
}
IGNORED_ERRORS = {45, 47}          # desconectados / remoção segura: não são problema

CLASS_NAMES = {
    "display": "Vídeo", "net": "Rede", "media": "Som e vídeo", "audioendpoint": "Saída de áudio",
    "system": "Sistema", "usb": "USB", "hdc": "Armazenamento", "scsiadapter": "Armazenamento",
    "diskdrive": "Disco", "cdrom": "Leitor de CD/DVD", "bluetooth": "Bluetooth", "hidclass": "Entrada (HID)",
    "mouse": "Mouse", "keyboard": "Teclado", "monitor": "Monitor", "printer": "Impressora", "camera": "Câmera",
    "image": "Câmera / scanner", "battery": "Bateria", "processor": "Processador", "volume": "Volume",
    "volumesnapshot": "Instantâneo", "softwaredevice": "Software", "softwarecomponent": "Componente",
    "extension": "Extensão", "securitydevices": "Segurança (TPM)", "firmware": "Firmware", "sensor": "Sensor",
    "biometric": "Biometria", "computer": "Computador", "ports": "Portas", "smartcardreader": "Leitor de cartão",
    "sdhost": "Leitor de cartão SD", "wpd": "Dispositivo portátil", "printqueue": "Fila de impressão",
    "legacydriver": "Driver legado", "net client": "Rede", "nettrans": "Rede", "netservice": "Rede",
    "ucm": "USB-C", "usbdevice": "USB", "mtd": "Memória", "infrared": "Infravermelho", "modem": "Modem",
    "multifunction": "Multifunção", "1394": "FireWire", "kernel": "Kernel (Linux)", "unknown": "Desconhecido",
}
NOISE_CLASSES = {"volume", "volumesnapshot", "softwaredevice", "legacydriver", "computer", "printqueue",
                 "audioendpoint", "net client", "nettrans", "netservice"}


def class_name(c) -> str:
    c = s(c)
    return CLASS_NAMES.get(c.lower(), c.title() if c.isupper() else c) or "Outros"


def is_microsoft(provider) -> bool:
    return "microsoft" in s(provider).lower()


def driver_status(d: dict, today: datetime.date | None = None) -> tuple[str, str, int]:
    """Retorna (texto da situação, tag de cor, posição para ordenar: menor = mais urgente)."""
    today = today or datetime.date.today()
    code = to_int(d.get("e"))
    if d.get("nodrv"):
        return "Sem driver carregado (normal para pontes e controladores)", "muted", 2
    if code and code not in IGNORED_ERRORS:
        if code == 22:
            return "Desativado", "muted", 2
        return f"Com problema: {CM_ERRORS.get(code, 'erro desconhecido')} (código {code})", "danger", 0
    date = parse_date(d.get("d"))
    if date and not is_microsoft(d.get("p")) and (today - date).days > OLD_YEARS * 365:
        return f"Antigo (driver de {date.year})", "warn", 1
    if date and is_microsoft(d.get("p")):
        return "OK · driver do Windows", "", 3
    return "OK", "", 3


def is_noise(d: dict) -> bool:
    cls = s(d.get("c")).lower()
    if to_int(d.get("e")) not in (0, *IGNORED_ERRORS):
        return False
    return cls in NOISE_CLASSES or (cls == "system" and is_microsoft(d.get("p")))


def normalize_drivers(raw, show_all=False, today=None) -> list[dict]:
    """Converte o JSON do script (lista de dispositivos) em linhas prontas para a tabela."""
    rows = []
    seen = set()
    for d in as_list(raw):
        if not isinstance(d, dict):
            continue
        name = s(d.get("n")) or s(d.get("id")) or "Dispositivo desconhecido"
        key = (s(d.get("id")) or name).lower()
        if key in seen:
            continue
        seen.add(key)
        if not show_all and is_noise(d):
            continue
        status, tag, rank = driver_status(d, today)
        date = parse_date(d.get("d"))
        maker = s(d.get("m")) or s(d.get("p")) or "—"
        rows.append({
            "name": name, "maker": maker, "provider": s(d.get("p")), "version": s(d.get("v")) or "—",
            "date": date, "date_txt": fmt_d(date), "cls": class_name(d.get("c")), "status": status, "tag": tag,
            "rank": rank, "id": s(d.get("id")), "inf": s(d.get("i")), "hwid": s(d.get("hw")),
            "code": to_int(d.get("e")),
        })
    rows.sort(key=lambda r: (r["rank"], r["cls"].lower(), r["name"].lower()))
    return rows


# =================================================================== listagem
LIST_SCRIPT = r"""
$err = @{}
foreach ($e in @(Get-CimInstance -ClassName Win32_PnPEntity -ErrorAction SilentlyContinue)) {
  if ($e.DeviceID) { $err[$e.DeviceID] = $e }
}
$seen = @{}
$out = New-Object System.Collections.ArrayList
foreach ($d in @(Get-CimInstance -ClassName Win32_PnPSignedDriver -ErrorAction SilentlyContinue)) {
  if (-not $d.DeviceName) { continue }
  $code = 0
  if ($d.DeviceID) {
    $seen[$d.DeviceID] = 1
    $e = $err[$d.DeviceID]
    if ($e) { $code = [int]$e.ConfigManagerErrorCode }
  }
  [void]$out.Add([pscustomobject]@{
    n = $d.DeviceName; m = $d.Manufacturer; p = $d.DriverProviderName; v = $d.DriverVersion
    d = (D $d.DriverDate); c = $d.DeviceClass; i = $d.InfName; id = $d.DeviceID; hw = $d.HardWareID; e = $code
  })
}
foreach ($e in $err.Values) {
  $code = [int]$e.ConfigManagerErrorCode
  if ($code -ne 0 -and -not $seen.ContainsKey($e.DeviceID)) {
    $nm = $e.Name
    if (-not $nm) { $nm = $e.DeviceID }
    [void]$out.Add([pscustomobject]@{
      n = $nm; m = $e.Manufacturer; p = $null; v = $null; d = $null; c = $e.PNPClass; i = $null
      id = $e.DeviceID; hw = $null; e = $code
    })
  }
}
ConvertTo-Json -InputObject @($out) -Depth 3 -Compress
"""


def _linux_devices() -> list[dict]:
    """Dispositivos PCI/USB e o módulo do kernel que os controla (equivalente simples aos drivers)."""
    names = {}
    if shutil.which("lspci"):
        rc, out, _ = run(["lspci", "-mm", "-D"], timeout=20)
        for ln in out.splitlines():
            parts = re.findall(r'"([^"]*)"', ln)
            if len(parts) >= 3:
                names[ln.split()[0]] = (parts[2], parts[1], parts[0])
    devs = []
    base = "/sys/bus/pci/devices"
    for dev in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        path = os.path.join(base, dev)
        drv = os.path.join(path, "driver")
        module = os.path.basename(os.path.realpath(drv)) if os.path.exists(drv) else ""
        nm, maker, cls = names.get(dev, ("", "", ""))
        if not nm:
            pci_cls = PCI_CLASSES.get(_read(os.path.join(path, "class"))[2:4].lower(), ("Dispositivo", "system"))
            nm = f"{pci_cls[0]} PCI ({dev.split(':', 1)[-1]})"
            cls = pci_cls[1]
            vid = _read(os.path.join(path, "vendor")).lower()
            maker = PCI_VENDORS.get(vid, vid)
        version = _read(f"/sys/module/{module}/version") if module else ""
        devs.append({"n": nm, "m": maker, "p": "Kernel Linux" if module else "",
                     "v": f"{module} {version}".strip() if module else "—", "d": None, "c": cls or "kernel",
                     "id": f"PCI {dev}", "i": module, "e": 0, "nodrv": not module})
    return devs


PCI_VENDORS = {"0x8086": "Intel", "0x1022": "AMD", "0x1002": "AMD", "0x10de": "NVIDIA", "0x10ec": "Realtek",
               "0x14e4": "Broadcom", "0x168c": "Qualcomm Atheros", "0x1af4": "Red Hat (VirtIO)", "0x15ad": "VMware",
               "0x80ee": "VirtualBox", "0x1b36": "Red Hat (QEMU)", "0x144d": "Samsung", "0x1987": "Phison",
               "0x15b7": "SanDisk / WD", "0x1179": "Toshiba / Kioxia", "0x8087": "Intel", "0x1217": "O2 Micro"}
PCI_CLASSES = {"00": ("Dispositivo", "system"), "01": ("Controlador de armazenamento", "hdc"),
               "02": ("Controlador de rede", "net"), "03": ("Placa de vídeo", "display"),
               "04": ("Controlador multimídia", "media"), "05": ("Controlador de memória", "system"),
               "06": ("Ponte", "system"), "07": ("Controlador de comunicação", "ports"),
               "08": ("Periférico do sistema", "system"), "0c": ("Controlador de barramento", "usb"),
               "0d": ("Controlador sem fio", "net"), "10": ("Criptografia", "securitydevices"),
               "11": ("Processamento de sinal", "system"), "ff": ("Dispositivo", "system")}


def _read(p) -> str:
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return ""


def list_drivers(show_all=False) -> list[dict]:
    if IS_WIN:
        rc, out, err = run_ps_file(LIST_SCRIPT, timeout=240)
        data = parse_json(out)
        if data is None:
            raise RuntimeError("Não foi possível ler a lista de drivers do Windows."
                               + (f"\n\nDetalhes: {err.strip()[:300]}" if err.strip() else ""))
        return normalize_drivers(data, show_all)
    if IS_LINUX:
        return normalize_drivers(_linux_devices(), show_all=True)
    return []


# =================================================================== Windows Update (oficial)
WU_ERRORS = {
    "8024402C": "sem conexão com a internet (ou proxy bloqueando)",
    "80072EFD": "sem conexão com a internet",
    "80072EE7": "sem conexão com a internet (falha de DNS)",
    "80072EE2": "o servidor do Windows Update demorou demais para responder",
    "8024401C": "o servidor do Windows Update demorou demais para responder",
    "80070422": "o serviço Windows Update está desativado",
    "8024001E": "o serviço Windows Update está sendo desligado",
    "80240438": "não foi possível falar com o Windows Update",
    "8024002E": "o acesso ao Windows Update está bloqueado por política do sistema",
    "80240024": "nenhuma atualização disponível",
    "80070005": "acesso negado",
}

SEARCH_SCRIPT = r"""
$res = [ordered]@{ error = $null; hresult = $null; updates = @() }
try {
  $s = New-Object -ComObject Microsoft.Update.Session
  $s.ClientApplicationID = 'LimpaPC'
  $q = $s.CreateUpdateSearcher()
  $q.ServerSelection = 2
  $q.Online = $true
  $sr = $q.Search('IsInstalled=0 and Type=''Driver'' and IsHidden=0')
  $list = New-Object System.Collections.ArrayList
  foreach ($u in $sr.Updates) {
    $rb = 0
    try { $rb = [int]$u.InstallationBehavior.RebootBehavior } catch { }
    [void]$list.Add([pscustomobject]@{
      id = $u.Identity.UpdateID; title = $u.Title; model = $u.DriverModel; mfr = $u.DriverManufacturer
      cls = $u.DriverClass; date = (D $u.DriverVerDate); hw = $u.DriverHardwareID
      size = [int64]$u.MaxDownloadSize; reboot = $rb
    })
  }
  $res.updates = @($list)
} catch {
  $ex = $_.Exception
  while ($ex.InnerException) { $ex = $ex.InnerException }
  $res.error = $ex.Message
  $res.hresult = ('{0:X8}' -f $ex.HResult)
}
$res | ConvertTo-Json -Depth 4 -Compress
"""

INSTALL_SCRIPT = r"""
$res = [ordered]@{ ok = $false; reboot = $false; error = $null; hresult = $null; items = @() }
try {
  $s = New-Object -ComObject Microsoft.Update.Session
  $s.ClientApplicationID = 'LimpaPC'
  $q = $s.CreateUpdateSearcher()
  $q.ServerSelection = 2
  $q.Online = $true
  $sr = $q.Search('IsInstalled=0 and Type=''Driver'' and IsHidden=0')
  $coll = New-Object -ComObject Microsoft.Update.UpdateColl
  foreach ($u in $sr.Updates) {
    if ($ids -contains $u.Identity.UpdateID) {
      if (-not $u.EulaAccepted) { try { $u.AcceptEula() } catch { } }
      [void]$coll.Add($u)
    }
  }
  if ($coll.Count -eq 0) {
    $res.error = 'As atualizações escolhidas não estão mais disponíveis no Windows Update.'
  } else {
    $dl = $s.CreateUpdateDownloader()
    $dl.Updates = $coll
    [void]$dl.Download()
    $ready = New-Object -ComObject Microsoft.Update.UpdateColl
    $items = New-Object System.Collections.ArrayList
    foreach ($u in $coll) {
      if ($u.IsDownloaded) { [void]$ready.Add($u) }
      else { [void]$items.Add([pscustomobject]@{ id = $u.Identity.UpdateID; title = $u.Title; code = 4; hresult = 'download' }) }
    }
    if ($ready.Count -gt 0) {
      $inst = $s.CreateUpdateInstaller()
      try { $inst.ForceQuiet = $true } catch { }
      $inst.Updates = $ready
      $ir = $inst.Install()
      $res.reboot = [bool]$ir.RebootRequired
      for ($i = 0; $i -lt $ready.Count; $i++) {
        $r = $ir.GetUpdateResult($i)
        [void]$items.Add([pscustomobject]@{ id = $ready.Item($i).Identity.UpdateID; title = $ready.Item($i).Title
          code = [int]$r.ResultCode; hresult = ('{0:X8}' -f $r.HResult) })
      }
    }
    $res.items = @($items)
    $res.ok = $true
  }
} catch {
  $ex = $_.Exception
  while ($ex.InnerException) { $ex = $ex.InnerException }
  $res.error = $ex.Message
  $res.hresult = ('{0:X8}' -f $ex.HResult)
}
$res | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -Path $out
"""

_VER_RE = re.compile(r"(\d+(?:\.\d+){1,3})\s*\)?\s*$")


def wu_error_text(msg, hresult) -> str:
    h = s(hresult).upper().replace("0X", "")[-8:]
    friendly = WU_ERRORS.get(h)
    if friendly:
        return f"{friendly[0].upper()}{friendly[1:]} (código 0x{h})."
    return (s(msg) or "Erro desconhecido") + (f" (código 0x{h})" if h else "")


def normalize_updates(raw) -> dict:
    """Converte o resultado da busca no Windows Update. Retorna {'error': str|None, 'updates': [...]}."""
    if not isinstance(raw, dict):
        return {"error": "Resposta inesperada do Windows Update.", "updates": []}
    if raw.get("error"):
        return {"error": wu_error_text(raw.get("error"), raw.get("hresult")), "updates": []}
    ups = []
    seen = set()
    for u in as_list(raw.get("updates")):
        if not isinstance(u, dict) or not s(u.get("id")) or s(u.get("id")) in seen:
            continue
        seen.add(s(u.get("id")))
        title = s(u.get("title")) or s(u.get("model")) or "Driver"
        m = _VER_RE.search(title)
        date = parse_date(u.get("date"))
        ups.append({"id": s(u.get("id")), "title": title, "model": s(u.get("model")) or title,
                    "maker": s(u.get("mfr")) or "—", "cls": class_name(u.get("cls")) if u.get("cls") else "Driver",
                    "version": m.group(1) if m else "—", "date": date, "date_txt": fmt_d(date),
                    "hwid": s(u.get("hw")), "size": max(0, to_int(u.get("size"))),
                    "reboot": to_int(u.get("reboot")) > 0})
    return {"error": None, "updates": ups}


def search_updates() -> dict:
    """Procura drivers não instalados no Windows Update (pode levar alguns minutos)."""
    if not IS_WIN:
        raise NotWindows("A busca de drivers no Windows Update só funciona no Windows.")
    rc, out, err = run_ps_file(SEARCH_SCRIPT, timeout=900)
    data = parse_json(out)
    if data is None:
        if rc == 124:
            return {"error": "O Windows Update demorou demais para responder. Tente de novo mais tarde.",
                    "updates": []}
        return {"error": "Não foi possível consultar o Windows Update." + (f"\n\n{err.strip()[:300]}" if err.strip()
                                                                          else ""), "updates": []}
    return normalize_updates(data)


RESULT_CODES = {0: "não iniciado", 1: "em andamento", 2: "instalado", 3: "instalado com avisos",
                4: "falhou", 5: "cancelado"}


def normalize_install(rc, data) -> dict:
    """Resultado da instalação: {'ok': [ids], 'failed': [(título, motivo)], 'reboot': bool, 'error': str|None}."""
    if rc == -1 and not data:
        return {"ok": [], "failed": [], "reboot": False,
                "error": "A permissão de administrador foi recusada. Nada foi instalado."}
    if not isinstance(data, dict):
        return {"ok": [], "failed": [], "reboot": False,
                "error": "A instalação não retornou resultado (código {}).".format(rc)}
    if data.get("error"):
        return {"ok": [], "failed": [], "reboot": bool(data.get("reboot")),
                "error": wu_error_text(data.get("error"), data.get("hresult"))}
    ok, failed = [], []
    for it in as_list(data.get("items")):
        if not isinstance(it, dict):
            continue
        code = to_int(it.get("code"), -1)
        if code in (2, 3):
            ok.append(s(it.get("id")))
        else:
            why = "falha no download" if s(it.get("hresult")) == "download" else \
                wu_error_text(RESULT_CODES.get(code, "falhou"), it.get("hresult"))
            failed.append((s(it.get("title")) or s(it.get("id")), why))
    return {"ok": ok, "failed": failed, "reboot": bool(data.get("reboot")), "error": None}


def install_updates(ids: list[str]) -> dict:
    """Baixa e instala (como administrador) as atualizações de driver escolhidas, pelo próprio Windows Update."""
    if not IS_WIN:
        raise NotWindows("A instalação de drivers só funciona no Windows.")
    safe = [i for i in ids if re.fullmatch(r"[0-9A-Fa-f-]{36}", i or "")]
    if not safe:
        return {"ok": [], "failed": [], "reboot": False, "error": "Nenhuma atualização válida escolhida."}
    head = PS_FUNCS + "$ids = @(" + ",".join(f"'{i}'" for i in safe) + ")\n"
    rc, data = run_ps_elevated(head + INSTALL_SCRIPT, timeout=3600)
    res = normalize_install(rc, data)
    log(f"DRIVERS instalados: {len(res['ok'])}, falhas: {len(res['failed'])}, reiniciar: {res['reboot']}")
    return res


# =================================================================== backup
BACKUP_SCRIPT = r"""
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$txt = (& pnputil.exe /export-driver * $dest 2>&1 | Out-String)
$code = $LASTEXITCODE
$n = @(Get-ChildItem -LiteralPath $dest -Recurse -Filter *.inf -ErrorAction SilentlyContinue).Count
$how = 'pnputil'
if ($n -eq 0) {
  try { Export-WindowsDriver -Online -Destination $dest -ErrorAction Stop | Out-Null; $how = 'dism' } catch { $txt += $_.Exception.Message }
  $n = @(Get-ChildItem -LiteralPath $dest -Recurse -Filter *.inf -ErrorAction SilentlyContinue).Count
}
[ordered]@{ code = $code; count = $n; how = $how; output = $txt } | ConvertTo-Json -Depth 3 | Set-Content -Encoding UTF8 -Path $out
"""


def backup_drivers(dest: str) -> dict:
    """Exporta todos os drivers de terceiros (pnputil /export-driver *) para a pasta. Pede administrador."""
    if not IS_WIN:
        raise NotWindows("O backup de drivers só funciona no Windows.")
    head = "$dest = '" + dest.replace("'", "''") + "'\n"
    rc, data = run_ps_elevated(head + BACKUP_SCRIPT, timeout=1800)
    if rc == -1 and not data:
        return {"ok": False, "count": 0, "error": "A permissão de administrador foi recusada."}
    data = data if isinstance(data, dict) else {}
    n = to_int(data.get("count"))
    log(f"BACKUP DE DRIVERS em {dest}: {n} drivers ({data.get('how')})")
    if n:
        return {"ok": True, "count": n, "error": None}
    out = s(data.get("output"))[-400:]
    return {"ok": False, "count": 0, "error": "Nenhum driver foi exportado." + (f"\n\n{out}" if out else "")}
