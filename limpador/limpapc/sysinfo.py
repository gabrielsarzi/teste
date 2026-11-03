"""Ficha técnica do computador: sistema, processador, placa-mãe, RAM, vídeo, discos, rede, bateria e
temperaturas.

No Windows tudo vem de um único script PowerShell que devolve JSON (rápido e em segundo plano). No Linux usa
/proc, /sys, lscpu e lsblk. O resultado é normalizado em um dicionário comum e convertido em "cards"
(usados pela interface, pelo resumo em texto e pelo relatório HTML).
"""
from __future__ import annotations

import datetime
import html
import json
import os
import platform
import re
import shutil
import socket

from . import APP_NAME, __version__
from .drivers import as_list, parse_date, parse_json, run_ps_file, s, to_int
from .utils import IS_LINUX, IS_WIN, fmt_size
from .winutil import run

# =================================================================== coleta no Windows
WIN_SCRIPT = r"""
function N($v) {
  if ($null -eq $v) { return $null }
  if ($v -is [byte[]]) {
    if ($v.Length -ge 8) { return [BitConverter]::ToInt64($v, 0) }
    if ($v.Length -ge 4) { return [int64][BitConverter]::ToUInt32($v, 0) }
    return $null
  }
  try { return [int64]$v } catch { return $null }
}
function T($a) {
  if ($null -eq $a) { return $null }
  $c = @($a | Where-Object { $_ -ne 0 } | ForEach-Object { [char][int]$_ })
  if ($c.Count -eq 0) { return $null }
  return (-join $c).Trim()
}
$r = [ordered]@{ platform = 'windows' }

# ---- sistema
$os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction SilentlyContinue
$cs = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction SilentlyContinue
$cv = Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion' -ErrorAction SilentlyContinue
$up = $null
if ($os.LastBootUpTime -is [datetime]) { $up = [int64]((Get-Date) - $os.LastBootUpTime).TotalSeconds }
$r.os = [ordered]@{
  caption = $os.Caption; version = $os.Version; build = $os.BuildNumber; ubr = $cv.UBR
  display = $cv.DisplayVersion; release = $cv.ReleaseId; arch = $os.OSArchitecture
  installDate = (D $os.InstallDate); lastBoot = (D $os.LastBootUpTime 'yyyy-MM-ddTHH:mm:ss'); uptime = $up
  computer = $env:COMPUTERNAME; user = $env:USERNAME; firmware = $env:firmware_type
  maker = $cs.Manufacturer; model = $cs.Model; pcType = $cs.PCSystemType; totalMem = $cs.TotalPhysicalMemory
}
try {
  $lic = Get-CimInstance -ClassName SoftwareLicensingProduct -Filter 'ApplicationID=''55c92734-d682-4d71-983e-d6ec3f16059f'' and PartialProductKey is not null' -ErrorAction Stop |
    Select-Object -First 1
  if ($lic) { $r.os.license = [int]$lic.LicenseStatus }
} catch { }

# ---- processador
$r.cpu = @(Get-CimInstance -ClassName Win32_Processor -ErrorAction SilentlyContinue | ForEach-Object {
  [ordered]@{ name = $_.Name; maker = $_.Manufacturer; cores = $_.NumberOfCores; threads = $_.NumberOfLogicalProcessors
    maxMHz = $_.MaxClockSpeed; curMHz = $_.CurrentClockSpeed; socket = $_.SocketDesignation
    l2 = $_.L2CacheSize; l3 = $_.L3CacheSize; load = $_.LoadPercentage; virt = $_.VirtualizationFirmwareEnabled }
})

# ---- placa-mãe e BIOS
$bb = Get-CimInstance -ClassName Win32_BaseBoard -ErrorAction SilentlyContinue | Select-Object -First 1
$bi = Get-CimInstance -ClassName Win32_BIOS -ErrorAction SilentlyContinue | Select-Object -First 1
$r.board = [ordered]@{ maker = $bb.Manufacturer; product = $bb.Product; version = $bb.Version }
$r.bios = [ordered]@{ maker = $bi.Manufacturer; version = $bi.SMBIOSBIOSVersion; date = (D $bi.ReleaseDate) }

# ---- memória
$arr = @(Get-CimInstance -ClassName Win32_PhysicalMemoryArray -ErrorAction SilentlyContinue | Where-Object { $_.Use -eq 3 -or $null -eq $_.Use })
$slots = 0; $maxKB = 0
foreach ($a in $arr) { $slots += [int]$a.MemoryDevices; $m = (N $a.MaxCapacityEx); if (-not $m) { $m = (N $a.MaxCapacity) }; if ($m) { $maxKB += $m } }
$r.ram = [ordered]@{
  slots = $slots; maxKB = $maxKB
  modules = @(Get-CimInstance -ClassName Win32_PhysicalMemory -ErrorAction SilentlyContinue | ForEach-Object {
    [ordered]@{ size = (N $_.Capacity); speed = $_.Speed; conf = $_.ConfiguredClockSpeed; maker = $_.Manufacturer
      part = $_.PartNumber; slot = $_.DeviceLocator; bank = $_.BankLabel; type = $_.SMBIOSMemoryType; ff = $_.FormFactor }
  })
}

# ---- vídeo
$vram = @{}
Get-ChildItem -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}' -ErrorAction SilentlyContinue | ForEach-Object {
  $p = Get-ItemProperty -Path $_.PSPath -ErrorAction SilentlyContinue
  if ($p -and $p.DriverDesc) {
    $v = (N $p.'HardwareInformation.qwMemorySize')
    if (-not $v) { $v = (N $p.'HardwareInformation.MemorySize') }
    if ($v) { $vram[[string]$p.DriverDesc] = $v }
  }
}
$r.gpu = @(Get-CimInstance -ClassName Win32_VideoController -ErrorAction SilentlyContinue | ForEach-Object {
  $mem = $vram[[string]$_.Name]
  if (-not $mem) { $mem = (N $_.AdapterRAM) }
  [ordered]@{ name = $_.Name; vram = $mem; driver = $_.DriverVersion; driverDate = (D $_.DriverDate)
    w = $_.CurrentHorizontalResolution; h = $_.CurrentVerticalResolution; hz = $_.CurrentRefreshRate
    proc = $_.VideoProcessor; status = $_.ConfigManagerErrorCode }
})
$r.monitors = @(Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID -ErrorAction SilentlyContinue | ForEach-Object {
  [ordered]@{ name = (T $_.UserFriendlyName); maker = (T $_.ManufacturerName); year = $_.YearOfManufacture }
})

# ---- discos
$disks = @()
try { $disks = @(Get-PhysicalDisk -ErrorAction Stop) } catch { $disks = @() }
if ($disks.Count -gt 0) {
  $r.disks = @($disks | ForEach-Object {
    $d = $_
    $rel = $null
    try { $rel = $d | Get-StorageReliabilityCounter -ErrorAction Stop } catch { }
    $letters = @()
    try { $letters = @(Get-Partition -DiskNumber ([int]$d.DeviceId) -ErrorAction Stop | Where-Object { $_.DriveLetter } | ForEach-Object { [string]$_.DriveLetter }) } catch { }
    [ordered]@{ model = $d.FriendlyName; media = [string]$d.MediaType; bus = [string]$d.BusType; size = (N $d.Size)
      health = [string]$d.HealthStatus; op = [string]($d.OperationalStatus -join ', '); spindle = $d.SpindleSpeed
      letters = ($letters -join ' '); temp = $rel.Temperature; tempMax = $rel.TemperatureMax; wear = $rel.Wear
      hours = $rel.PowerOnHours; readErr = $rel.ReadErrorsUncorrected; writeErr = $rel.WriteErrorsUncorrected }
  })
} else {
  $r.disks = @(Get-CimInstance -ClassName Win32_DiskDrive -ErrorAction SilentlyContinue | ForEach-Object {
    [ordered]@{ model = $_.Model; media = [string]$_.MediaType; bus = $_.InterfaceType; size = (N $_.Size); health = $_.Status }
  })
}

# ---- rede
$ad = @{}
foreach ($a in @(Get-CimInstance -ClassName Win32_NetworkAdapter -ErrorAction SilentlyContinue)) { $ad[[string]$a.Index] = $a }
$r.net = @(Get-CimInstance -ClassName Win32_NetworkAdapterConfiguration -Filter 'IPEnabled=TRUE' -ErrorAction SilentlyContinue | ForEach-Object {
  $a = $ad[[string]$_.Index]
  [ordered]@{ name = $_.Description; conn = $a.NetConnectionID; speed = (N $a.Speed); physical = $a.PhysicalAdapter
    ip = (@($_.IPAddress) -join ', '); gw = (@($_.DefaultIPGateway) -join ', '); dns = (@($_.DNSServerSearchOrder) -join ', ')
    dhcp = $_.DHCPEnabled }
})

# ---- bateria
$bat = @(Get-CimInstance -ClassName Win32_Battery -ErrorAction SilentlyContinue)
$r.battery = @()
if ($bat.Count -gt 0) {
  $design = @(Get-CimInstance -Namespace root\wmi -ClassName BatteryStaticData -ErrorAction SilentlyContinue)
  $full = @(Get-CimInstance -Namespace root\wmi -ClassName BatteryFullChargedCapacity -ErrorAction SilentlyContinue)
  $cyc = @(Get-CimInstance -Namespace root\wmi -ClassName BatteryCycleCount -ErrorAction SilentlyContinue)
  $rep = @()
  if ($design.Count -eq 0 -or -not $design[0].DesignedCapacity) {
    $f = Join-Path $env:TEMP ('limpapc_bat_' + [guid]::NewGuid().ToString('N') + '.xml')
    try {
      & powercfg.exe /batteryreport /xml /output $f 2>&1 | Out-Null
      if (Test-Path -LiteralPath $f) {
        [xml]$x = Get-Content -LiteralPath $f -Raw -Encoding UTF8
        $rep = @($x.BatteryReport.Batteries.Battery)
      }
    } catch { }
    Remove-Item -LiteralPath $f -Force -ErrorAction SilentlyContinue
  }
  for ($i = 0; $i -lt $bat.Count; $i++) {
    $b = $bat[$i]
    $o = [ordered]@{ name = $b.Name; charge = $b.EstimatedChargeRemaining; status = $b.BatteryStatus; runtime = $b.EstimatedRunTime
      design = $null; full = $null; cycles = $null; maker = $null; chem = $null }
    if ($i -lt $design.Count) { $o.design = $design[$i].DesignedCapacity; $o.maker = $design[$i].ManufactureName }
    if ($i -lt $full.Count) { $o.full = $full[$i].FullChargedCapacity }
    if ($i -lt $cyc.Count) { $o.cycles = $cyc[$i].CycleCount }
    if ($i -lt $rep.Count) {
      $e = $rep[$i]
      if (-not $o.design) { $o.design = (N $e.DesignCapacity) }
      if (-not $o.full) { $o.full = (N $e.FullChargeCapacity) }
      if (-not $o.cycles) { $o.cycles = (N $e.CycleCount) }
      if (-not $o.maker) { $o.maker = [string]$e.Manufacturer }
      $o.chem = [string]$e.Chemistry
    }
    $r.battery += ,$o
  }
}

# ---- temperaturas (nem todo PC expõe; normalmente exige administrador)
$r.temps = @(Get-CimInstance -Namespace root\wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | ForEach-Object {
  [ordered]@{ name = $_.InstanceName; c = [math]::Round(($_.CurrentTemperature / 10.0) - 273.15, 1) }
})

$r | ConvertTo-Json -Depth 6 -Compress
"""

MEM_TYPES = {20: "DDR", 21: "DDR2", 22: "DDR2", 24: "DDR3", 26: "DDR4", 27: "LPDDR", 28: "LPDDR2",
             29: "LPDDR3", 30: "LPDDR4", 34: "DDR5", 35: "LPDDR5"}
FORM_FACTORS = {8: "DIMM", 12: "SODIMM", 13: "SRIMM"}
MEDIA = {"0": "", "3": "HDD", "4": "SSD", "5": "SCM", "unspecified": "", "hdd": "HDD", "ssd": "SSD", "scm": "SCM"}
BUS = {"1": "SCSI", "2": "ATAPI", "3": "ATA", "6": "Fibre Channel", "7": "USB", "8": "RAID", "9": "iSCSI",
       "10": "SAS", "11": "SATA", "12": "SD", "13": "MMC", "15": "Virtual", "16": "Storage Spaces", "17": "NVMe"}
HEALTH = {"0": "Healthy", "1": "Warning", "2": "Unhealthy", "5": "Unknown"}
PC_TYPES = {1: "Desktop", 2: "Notebook", 3: "Workstation", 4: "Servidor", 5: "Servidor", 8: "Tablet / 2 em 1"}
LICENSE = {0: "Não ativado", 1: "Ativado", 2: "Período de carência", 3: "Período de carência",
           4: "Não original", 5: "Notificação", 6: "Período de carência estendido"}
MAKERS = {"80ad": "SK hynix", "80ce": "Samsung", "802c": "Micron", "859b": "Crucial", "0198": "Kingston",
          "04cd": "G.Skill", "029e": "Corsair", "0420": "ADATA", "8551": "Qimonda", "04cb": "ADATA",
          "0b03": "Kingston", "00ce": "Samsung", "00ad": "SK hynix", "002c": "Micron"}


def _clean(v) -> str:
    """Remove textos vazios/genéricos que os fabricantes deixam no firmware."""
    t = s(v)
    if t.lower() in ("to be filled by o.e.m.", "default string", "system product name", "system manufacturer",
                     "not specified", "none", "unknown", "o.e.m.", "undefined", "0", "123456789", "base board"):
        return ""
    return re.sub(r"\s+", " ", t)


def _maker(v) -> str:
    t = _clean(v)
    key = t.lower().replace("0x", "")[:4]
    return MAKERS.get(key, t) if re.fullmatch(r"[0-9a-fA-F]{4,}", t.replace("0x", "")) else t


def normalize_windows(raw: dict) -> dict:
    """Converte o JSON do script do Windows no formato comum."""
    raw = raw if isinstance(raw, dict) else {}
    o = raw.get("os") if isinstance(raw.get("os"), dict) else {}
    build = s(o.get("build"))
    if build and o.get("ubr") not in (None, ""):
        build = f"{build}.{to_int(o.get('ubr'))}"
    caption = s(o.get("caption")).replace("Microsoft ", "")
    if caption.startswith("Windows 10") and to_int(o.get("build")) >= 22000:
        caption = caption.replace("Windows 10", "Windows 11")   # algumas edições ainda se chamam "10"
    lic = o.get("license")
    info = {
        "platform": "windows",
        "os": {"name": caption or "Windows", "edition_version": s(o.get("display")) or s(o.get("release")),
               "build": build, "arch": s(o.get("arch")), "install": parse_date(o.get("installDate")),
               "uptime": to_int(o.get("uptime"), -1), "computer": s(o.get("computer")), "user": s(o.get("user")),
               "firmware": s(o.get("firmware")), "maker": _clean(o.get("maker")), "model": _clean(o.get("model")),
               "pc_type": PC_TYPES.get(to_int(o.get("pcType")), ""),
               "activation": LICENSE.get(to_int(lic, -1), "") if lic is not None else "",
               "kernel": s(o.get("version"))},
        "cpu": [], "ram": {}, "gpu": [], "monitors": [], "disks": [], "net": [], "battery": [], "temps": [],
    }
    for c in as_list(raw.get("cpu")):
        if isinstance(c, dict):
            info["cpu"].append({"name": re.sub(r"\s+", " ", s(c.get("name"))) or "Processador",
                                "cores": to_int(c.get("cores")), "threads": to_int(c.get("threads")),
                                "max_mhz": to_int(c.get("maxMHz")), "cur_mhz": to_int(c.get("curMHz")),
                                "socket": _clean(c.get("socket")), "l2_kb": to_int(c.get("l2")),
                                "l3_kb": to_int(c.get("l3")), "load": to_int(c.get("load"), -1),
                                "virt": c.get("virt") if isinstance(c.get("virt"), bool) else None})
    b, bi = raw.get("board") or {}, raw.get("bios") or {}
    info["board"] = {"maker": _clean(b.get("maker")), "product": _clean(b.get("product")),
                     "version": _clean(b.get("version"))}
    info["bios"] = {"maker": _clean(bi.get("maker")), "version": _clean(bi.get("version")),
                    "date": parse_date(bi.get("date"))}
    r = raw.get("ram") if isinstance(raw.get("ram"), dict) else {}
    mods = []
    for m in as_list(r.get("modules")):
        if not isinstance(m, dict):
            continue
        mods.append({"size": to_int(m.get("size")), "speed": to_int(m.get("conf")) or to_int(m.get("speed")),
                     "rated": to_int(m.get("speed")), "maker": _maker(m.get("maker")), "part": _clean(m.get("part")),
                     "slot": _clean(m.get("slot")) or _clean(m.get("bank")),
                     "type": MEM_TYPES.get(to_int(m.get("type")), ""), "ff": FORM_FACTORS.get(to_int(m.get("ff")), "")})
    total = to_int(o.get("totalMem"))
    info["ram"] = {"total": sum(m["size"] for m in mods) or total, "usable": total, "modules": mods,
                   "slots": to_int(r.get("slots")), "max": to_int(r.get("maxKB")) * 1024}
    for g in as_list(raw.get("gpu")):
        if isinstance(g, dict):
            info["gpu"].append({"name": s(g.get("name")) or "Placa de vídeo", "vram": to_int(g.get("vram")),
                                "driver": s(g.get("driver")), "driver_date": parse_date(g.get("driverDate")),
                                "w": to_int(g.get("w")), "h": to_int(g.get("h")), "hz": to_int(g.get("hz"))})
    for m in as_list(raw.get("monitors")):
        if isinstance(m, dict) and (s(m.get("name")) or s(m.get("maker"))):
            info["monitors"].append({"name": s(m.get("name")) or "Monitor", "maker": s(m.get("maker")),
                                     "year": to_int(m.get("year"))})
    for d in as_list(raw.get("disks")):
        if not isinstance(d, dict):
            continue
        bus = BUS.get(s(d.get("bus")), s(d.get("bus")))
        media = MEDIA.get(s(d.get("media")).lower(), s(d.get("media")))
        if media.lower().startswith("fixed") or media.lower().startswith("external") or media.lower().startswith("removable"):
            media = ""
        if not media and to_int(d.get("spindle")) > 0:
            media = "HDD"
        kind = "NVMe" if bus.lower() == "nvme" else media
        health = HEALTH.get(s(d.get("health")), s(d.get("health")))
        info["disks"].append({
            "model": s(d.get("model")) or "Disco", "kind": kind, "bus": bus, "size": to_int(d.get("size")),
            "health": {"healthy": "ok", "ok": "ok", "warning": "warn", "pred fail": "bad", "degraded": "warn",
                       "unhealthy": "bad"}.get(health.lower(), ""),
            "health_raw": health, "letters": "  ".join(f"{x}:" for x in s(d.get("letters")).split() if x.isalpha()),
            "temp": to_int(d.get("temp"), -1) if d.get("temp") not in (None, 0, "0") else -1,
            "temp_max": to_int(d.get("tempMax"), -1) if d.get("tempMax") not in (None, 0, "0") else -1,
            "wear": to_int(d.get("wear"), -1) if d.get("wear") is not None else -1,
            "hours": to_int(d.get("hours"), -1) if d.get("hours") is not None else -1,
            "errors": to_int(d.get("readErr")) + to_int(d.get("writeErr"))})
    for n in as_list(raw.get("net")):
        if isinstance(n, dict):
            info["net"].append({"name": s(n.get("conn")) or s(n.get("name")), "desc": s(n.get("name")),
                                "speed": to_int(n.get("speed")), "ip": s(n.get("ip")), "gw": s(n.get("gw")),
                                "dns": s(n.get("dns")), "dhcp": n.get("dhcp") if isinstance(n.get("dhcp"), bool) else None,
                                "virtual": n.get("physical") is False})
    for bt in as_list(raw.get("battery")):
        if isinstance(bt, dict):
            st = to_int(bt.get("status"))
            info["battery"].append({
                "name": s(bt.get("name")) or "Bateria", "maker": s(bt.get("maker")), "chem": s(bt.get("chem")),
                "design": to_int(bt.get("design")), "full": to_int(bt.get("full")),
                "cycles": to_int(bt.get("cycles"), -1) if bt.get("cycles") not in (None, "") else -1,
                "charge": to_int(bt.get("charge"), -1) if bt.get("charge") is not None else -1,
                "plugged": st in (2, 6, 7, 8, 9) if st else None, "unit": "mWh"})
    for t in as_list(raw.get("temps")):
        if isinstance(t, dict):
            try:
                c = float(t.get("c"))
            except (TypeError, ValueError):
                continue
            if -20 < c < 130:
                name = s(t.get("name")).split("\\")[-1].replace("_0", "") or "Zona térmica"
                info["temps"].append({"name": f"Zona térmica ({name})", "c": c})
    return info


def collect_windows() -> dict:
    rc, out, err = run_ps_file(WIN_SCRIPT, timeout=150)
    data = parse_json(out)
    if not isinstance(data, dict):
        raise RuntimeError("Não foi possível ler as informações do Windows."
                           + (f"\n\nDetalhes: {err.strip()[:300]}" if err.strip() else ""))
    return normalize_windows(data)


# =================================================================== coleta no Linux
def _read(p, default="") -> str:
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return default


def _os_release() -> dict:
    out = {}
    for ln in _read("/etc/os-release").splitlines():
        if "=" in ln:
            k, v = ln.split("=", 1)
            out[k] = v.strip().strip('"')
    return out


def _lscpu() -> dict:
    out = {}
    if shutil.which("lscpu"):
        rc, txt, _ = run(["lscpu"], timeout=15)
        for ln in txt.splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                out[k.strip()] = v.strip()
    return out


VIRTUAL_IF = ("lo", "ifb", "veth", "docker", "br-", "virbr", "tun", "tap")


def collect_linux() -> dict:
    rel = _os_release()
    try:
        uptime = int(float(_read("/proc/uptime", "0").split()[0]))
    except (ValueError, IndexError):
        uptime = -1
    dmi = lambda k: _clean(_read(f"/sys/class/dmi/id/{k}"))  # noqa: E731
    chassis = to_int(dmi("chassis_type"))
    info = {
        "platform": "linux",
        "os": {"name": rel.get("PRETTY_NAME") or f"Linux {platform.release()}", "edition_version": rel.get("VERSION_ID", ""),
               "build": platform.release(), "arch": platform.machine(), "install": None, "uptime": uptime,
               "computer": socket.gethostname(), "user": os.environ.get("USER", ""),
               "firmware": "UEFI" if os.path.isdir("/sys/firmware/efi") else ("BIOS" if os.path.isdir("/sys/class/dmi") else ""),
               "maker": dmi("sys_vendor"), "model": dmi("product_name"),
               "pc_type": "Notebook" if chassis in (8, 9, 10, 14, 31, 32) else "Desktop" if chassis in (3, 4, 6, 7) else "",
               "activation": "", "kernel": platform.release()},
        "board": {"maker": dmi("board_vendor"), "product": dmi("board_name"), "version": dmi("board_version")},
        "bios": {"maker": dmi("bios_vendor"), "version": dmi("bios_version"), "date": parse_date(_us_date(dmi("bios_date")))},
        "cpu": [], "gpu": [], "monitors": [], "disks": [], "net": [], "battery": [], "temps": [],
    }
    # processador
    lc = _lscpu()
    model = lc.get("Model name", "")
    if not model:
        for ln in _read("/proc/cpuinfo").splitlines():
            if ln.lower().startswith("model name"):
                model = ln.split(":", 1)[1].strip()
                break
    threads = os.cpu_count() or 0
    cores = to_int(lc.get("Core(s) per socket")) * max(1, to_int(lc.get("Socket(s)"), 1)) or threads
    max_mhz = to_int(lc.get("CPU max MHz")) or to_int(_read("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq")) // 1000
    cur = to_int(_read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")) // 1000
    info["cpu"].append({"name": model or platform.processor() or "Processador", "cores": cores, "threads": threads,
                        "max_mhz": max_mhz, "cur_mhz": cur, "socket": "", "l2_kb": _kb(lc.get("L2 cache")),
                        "l3_kb": _kb(lc.get("L3 cache")), "load": -1,
                        "virt": True if lc.get("Virtualization") else None})
    # memória (os pentes exigem root/dmidecode)
    total = 0
    for ln in _read("/proc/meminfo").splitlines():
        if ln.startswith("MemTotal:"):
            total = to_int(ln.split()[1]) * 1024
    info["ram"] = {"total": total, "usable": total, "modules": [], "slots": 0, "max": 0}
    # vídeo
    if shutil.which("lspci"):
        rc, txt, _ = run(["lspci", "-mm"], timeout=15)
        for ln in txt.splitlines():
            parts = re.findall(r'"([^"]*)"', ln)
            if len(parts) >= 3 and re.search(r"VGA|3D|Display", parts[0]):
                info["gpu"].append({"name": f"{parts[1]} {parts[2]}".strip(), "vram": 0, "driver": "",
                                    "driver_date": None, "w": 0, "h": 0, "hz": 0})
    # discos
    if shutil.which("lsblk"):
        rc, txt, _ = run(["lsblk", "-J", "-b", "-d", "-o", "NAME,MODEL,SIZE,ROTA,TRAN,TYPE"], timeout=15)
        data = parse_json(txt) or {}
        for d in as_list(data.get("blockdevices") if isinstance(data, dict) else None):
            if not isinstance(d, dict) or s(d.get("type")) != "disk" or s(d.get("name")).startswith(("loop", "ram", "zram")) \
                    or to_int(d.get("size")) < 1 << 30:
                continue
            name = s(d.get("name"))
            rota = d.get("rota")
            rota = rota in (True, "1", 1)
            tran = s(d.get("tran")).upper()
            kind = "NVMe" if name.startswith("nvme") or tran == "NVME" else ("HDD" if rota else "SSD")
            info["disks"].append({"model": s(d.get("model")) or f"/dev/{name}", "kind": kind,
                                  "bus": tran or ("Virtual" if name.startswith("vd") else ""),
                                  "size": to_int(d.get("size")), "health": "", "health_raw": "",
                                  "letters": f"/dev/{name}" if s(d.get("model")) else "",
                                  "temp": -1, "temp_max": -1, "wear": -1, "hours": -1, "errors": 0})
    # rede
    if shutil.which("ip"):
        rc, txt, _ = run(["ip", "-j", "addr"], timeout=10)
        for a in as_list(parse_json(txt)):
            if not isinstance(a, dict) or s(a.get("ifname")).startswith(VIRTUAL_IF):
                continue
            ips = [s(x.get("local")) for x in as_list(a.get("addr_info")) if isinstance(x, dict) and x.get("local")]
            info["net"].append({"name": s(a.get("ifname")), "desc": "", "speed": 0, "ip": ", ".join(ips), "gw": "",
                                "dns": "", "dhcp": None, "virtual": False})
    else:
        for n in sorted(os.listdir("/sys/class/net")) if os.path.isdir("/sys/class/net") else []:
            if not n.startswith(VIRTUAL_IF):
                spd = to_int(_read(f"/sys/class/net/{n}/speed"))
                info["net"].append({"name": n, "desc": "", "speed": spd * 1_000_000 if spd > 0 else 0, "ip": "",
                                    "gw": "", "dns": "", "dhcp": None, "virtual": False})
    # bateria
    ps = "/sys/class/power_supply"
    for b in sorted(os.listdir(ps)) if os.path.isdir(ps) else []:
        p = os.path.join(ps, b)
        if _read(os.path.join(p, "type")) != "Battery":
            continue
        unit, pre = ("mWh", "energy") if os.path.exists(os.path.join(p, "energy_full")) else ("mAh", "charge")
        info["battery"].append({
            "name": _read(os.path.join(p, "model_name")) or b, "maker": _read(os.path.join(p, "manufacturer")),
            "chem": _read(os.path.join(p, "technology")),
            "design": to_int(_read(os.path.join(p, f"{pre}_full_design"))) // 1000,
            "full": to_int(_read(os.path.join(p, f"{pre}_full"))) // 1000,
            "cycles": to_int(_read(os.path.join(p, "cycle_count"), "-1"), -1),
            "charge": to_int(_read(os.path.join(p, "capacity"), "-1"), -1),
            "plugged": _read(os.path.join(p, "status")) in ("Charging", "Full", "Not charging"), "unit": unit})
    # temperaturas
    tz = "/sys/class/thermal"
    for z in sorted(os.listdir(tz)) if os.path.isdir(tz) else []:
        if z.startswith("thermal_zone"):
            v = to_int(_read(os.path.join(tz, z, "temp")), -999999)
            if v > -999999:
                c = v / 1000.0
                if -20 < c < 130:
                    info["temps"].append({"name": _read(os.path.join(tz, z, "type")) or z, "c": round(c, 1)})
    return info


def _kb(v) -> int:
    """'512 KiB (8 instances)' / '16 MiB' -> KB."""
    m = re.match(r"([\d.,]+)\s*([KMG])", s(v), re.I)
    if not m:
        return 0
    n = float(m.group(1).replace(",", "."))
    return int(n * {"K": 1, "M": 1024, "G": 1024 * 1024}[m.group(2).upper()])


def _us_date(v) -> str:
    """'03/15/2021' -> '2021-03-15'."""
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", s(v))
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else s(v)


def collect() -> dict:
    """Coleta a ficha do computador (lento: chame em segundo plano)."""
    if IS_WIN:
        info = collect_windows()
    elif IS_LINUX:
        info = collect_linux()
    else:
        info = {"platform": platform.system().lower(), "os": {"name": f"{platform.system()} {platform.release()}",
                "arch": platform.machine(), "computer": socket.gethostname(), "uptime": -1},
                "cpu": [{"name": platform.processor() or "Processador", "threads": os.cpu_count() or 0}]}
    info["collected"] = datetime.datetime.now()
    return info


# =================================================================== formatação
def gb(n) -> str:
    """Tamanho "redondo" para RAM/VRAM: 16 GB, 512 MB, 7,8 GB."""
    t = fmt_size(n)
    return t.replace(",0 ", " ")


def ghz(mhz) -> str:
    return f"{mhz / 1000:.2f} GHz".replace(".", ",") if mhz else ""


def fmt_uptime(sec) -> str:
    if sec is None or sec < 0:
        return ""
    d, rem = divmod(int(sec), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d} dia{'s' if d > 1 else ''} e {h} h"
    if h:
        return f"{h} h e {m} min"
    return f"{m} min"


def fmt_d(d) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def battery_health(b) -> int:
    """Saúde da bateria em % (capacidade atual / capacidade de fábrica), ou -1 se desconhecida."""
    if b.get("design", 0) > 0 and b.get("full", 0) > 0:
        return max(1, min(100, round(b["full"] * 100 / b["design"])))
    return -1


def _rows(*pairs):
    return [(k, s(v)) for k, v in pairs if s(v)]


def build_cards(info: dict) -> list[dict]:
    """Transforma a ficha em cards: {key, title, icon, badge:(texto, tom), rows:[(rótulo, valor)],
    blocks:[{title, sub, badge, rows, meter:(fração, tom, texto)}], note}. Tom: ok|warn|bad|info."""
    cards = []
    o = info.get("os") or {}
    # ---- sistema
    ver = " · ".join(x for x in (o.get("edition_version"), f"build {o['build']}" if o.get("build") else "") if x)
    act = o.get("activation", "")
    cards.append({"key": "os", "title": "Sistema operacional", "icon": "monitor",
                  "badge": (act, "ok" if act == "Ativado" else "warn") if act else None,
                  "rows": _rows(("Sistema", o.get("name")), ("Versão", ver), ("Arquitetura", o.get("arch")),
                                ("Nome do PC", o.get("computer")), ("Usuário", o.get("user")),
                                ("Ligado há", fmt_uptime(o.get("uptime"))),
                                ("Instalado em", fmt_d(o.get("install"))),
                                ("Firmware", {"Legacy": "BIOS (legado)"}.get(o.get("firmware", ""), o.get("firmware")))),
                  "blocks": [], "note": ""})
    # ---- processador
    blocks = []
    rows = []
    cpus = info.get("cpu") or []
    for i, c in enumerate(cpus):
        cache = " · ".join(x for x in (f"L2 {gb(c['l2_kb'] * 1024)}" if c.get("l2_kb") else "",
                                        f"L3 {gb(c['l3_kb'] * 1024)}" if c.get("l3_kb") else "") if x)
        r = _rows(("Modelo", c.get("name")),
                  ("Núcleos", f"{c['cores']} núcleos · {c['threads']} threads" if c.get("cores") else
                   (f"{c['threads']} threads" if c.get("threads") else "")),
                  ("Velocidade", f"até {ghz(c.get('max_mhz'))}" if c.get("max_mhz") else ""),
                  ("Agora", ghz(c.get("cur_mhz")) + (f" · {c['load']}% em uso" if c.get("load", -1) >= 0 else "")
                   if c.get("cur_mhz") else ""),
                  ("Cache", cache), ("Soquete", c.get("socket")),
                  ("Virtualização", {True: "Ativada", False: "Desativada no BIOS"}.get(c.get("virt"), "")))
        if len(cpus) > 1:
            blocks.append({"title": f"Processador {i + 1}", "rows": r})
        else:
            rows = r
    cards.append({"key": "cpu", "title": "Processador", "icon": "chip", "badge": None, "rows": rows, "blocks": blocks,
                  "note": ""})
    # ---- placa-mãe
    b, bi = info.get("board") or {}, info.get("bios") or {}
    pc = " ".join(x for x in (o.get("maker"), o.get("model")) if x)
    cards.append({"key": "board", "title": "Placa-mãe e BIOS", "icon": "layers", "badge": None,
                  "rows": _rows(("Computador", pc), ("Tipo", o.get("pc_type")), ("Fabricante", b.get("maker")),
                                ("Modelo", " ".join(x for x in (b.get("product"), b.get("version")) if x)),
                                ("BIOS", " · ".join(x for x in (bi.get("maker"), bi.get("version")) if x)),
                                ("Data do BIOS", fmt_d(bi.get("date")))),
                  "blocks": [], "note": "" if (b.get("maker") or pc) else "Informações da placa-mãe indisponíveis."})
    # ---- memória
    ram = info.get("ram") or {}
    mods = ram.get("modules") or []
    blocks = []
    for m in mods:
        sub = " · ".join(x for x in (m.get("type"), f"{m['speed']} MT/s" if m.get("speed") else "", m.get("ff"))
                         if x)
        blocks.append({"title": f"{gb(m['size'])}  —  {m.get('slot') or 'pente'}", "sub": sub,
                       "rows": _rows(("Fabricante", m.get("maker")), ("Modelo", m.get("part")))})
    slots = ram.get("slots", 0)
    used = len(mods)
    note = ""
    if not mods:
        note = ("Detalhes de cada pente exigem permissão de administrador (dmidecode)." if info.get("platform") == "linux"
                else "Detalhes de cada pente não disponíveis.")
    rows = _rows(("Total", gb(ram.get("total"))),
                 ("Utilizável", gb(ram["usable"]) if ram.get("usable") and abs(ram["usable"] - ram.get("total", 0))
                  > 64 << 20 else ""),
                 ("Tipo", mods[0].get("type") if mods else ""),
                 ("Slots", f"{used} de {slots} ocupados" + (" · dá para expandir" if 0 < used < slots else "")
                  if slots else ""),
                 ("Máximo suportado", gb(ram["max"]) if ram.get("max", 0) >= 1 << 30 else ""))
    cards.append({"key": "ram", "title": "Memória RAM", "icon": "database",
                  "badge": (f"{used} pente{'s' if used != 1 else ''}", "info") if used else None,
                  "rows": rows, "blocks": blocks, "note": note})
    # ---- vídeo
    blocks = []
    for g in info.get("gpu") or []:
        res = f"{g['w']} × {g['h']}" + (f" a {g['hz']} Hz" if g.get("hz") else "") if g.get("w") else ""
        blocks.append({"title": g["name"], "sub": gb(g["vram"]) + " de memória" if g.get("vram", 0) >= 64 << 20 else "",
                       "rows": _rows(("Driver", " · ".join(x for x in (g.get("driver"), fmt_d(g.get("driver_date")))
                                                           if x)), ("Resolução", res))})
    mons = [" ".join(x for x in (m.get("maker") if m.get("maker") and m.get("maker") not in m.get("name", "") else "",
                                 m.get("name")) if x) for m in info.get("monitors") or []]
    cards.append({"key": "gpu", "title": "Placa de vídeo", "icon": "monitor", "badge": None,
                  "rows": _rows(("Monitores", ", ".join(mons))), "blocks": blocks,
                  "note": "" if blocks else "Nenhuma placa de vídeo identificada."})
    # ---- discos
    blocks = []
    worst = ""
    for d in info.get("disks") or []:
        h = d.get("health")
        badge = {"ok": ("Saudável", "ok"), "warn": ("Atenção", "warn"), "bad": ("Com defeito", "bad")}.get(h)
        if h == "bad" or (h == "warn" and worst != "bad"):
            worst = h
        extra = []
        if d.get("temp", -1) > 0:
            extra.append(("Temperatura", f"{d['temp']} °C" + (f" (máx. {d['temp_max']} °C)" if d.get("temp_max", -1) > 0
                                                              else "")))
        if d.get("hours", -1) > 0:
            extra.append(("Tempo de uso", f"{d['hours']:,} horas".replace(",", ".")))
        if d.get("errors"):
            extra.append(("Erros de leitura/gravação", str(d["errors"])))
        meter = None
        if d.get("wear", -1) >= 0 and d.get("kind") in ("SSD", "NVMe"):
            life = max(0, 100 - d["wear"])
            meter = (life / 100, "ok" if life > 50 else "warn" if life > 15 else "bad", f"Vida útil restante: {life}%")
        bus = d.get("bus") if d.get("bus") and d.get("bus") != d.get("kind") else ""
        kind = f"{d['kind']} ({bus})" if d.get("kind") and bus else (d.get("kind") or bus)
        blocks.append({"title": d["model"], "sub": " · ".join(x for x in (fmt_size(d.get("size")) if d.get("size")
                                                                           else "", kind, d.get("letters")) if x),
                       "badge": badge, "rows": extra, "meter": meter})
    cards.append({"key": "disks", "title": "Discos", "icon": "drive",
                  "badge": {"bad": ("Disco com defeito!", "bad"), "warn": ("Atenção", "warn")}.get(worst),
                  "rows": [], "blocks": blocks,
                  "note": ("" if not blocks else
                           "Temperatura e desgaste aparecem quando o disco informa (pode exigir administrador)."
                           if info.get("platform") == "windows" and not any(d.get("temp", -1) > 0 for d in info["disks"])
                           else "") if blocks else "Nenhum disco encontrado."})
    # ---- rede
    blocks = []
    for n in info.get("net") or []:
        spd = n.get("speed", 0)
        spd_t = (f"{spd / 1e9:g} Gbps".replace(".", ",") if spd >= 1e9 else f"{spd / 1e6:g} Mbps".replace(".", ",")) \
            if 0 < spd < 1e12 else ""
        ip = n.get("ip", "")
        ipv4 = ", ".join(x for x in ip.split(", ") if "." in x and ":" not in x) or ip
        blocks.append({"title": n["name"], "sub": " · ".join(x for x in (n.get("desc") if n.get("desc") != n["name"]
                                                                         else "", spd_t) if x),
                       "rows": _rows(("IP", ipv4), ("Gateway", n.get("gw")), ("DNS", n.get("dns")))})
    cards.append({"key": "net", "title": "Rede", "icon": "wifi", "badge": None, "rows": [], "blocks": blocks,
                  "note": "" if blocks else "Nenhum adaptador de rede conectado."})
    # ---- bateria
    blocks = []
    for bt in info.get("battery") or []:
        hp = battery_health(bt)
        meter = (hp / 100, "ok" if hp >= 80 else "warn" if hp >= 50 else "bad", f"Saúde: {hp}%") if hp > 0 else None
        unit = bt.get("unit", "mWh")
        blocks.append({"title": " ".join(x for x in (bt.get("maker"), bt.get("name")) if x) or "Bateria",
                       "sub": " · ".join(x for x in (f"{bt['charge']}% de carga" if bt.get("charge", -1) >= 0 else "",
                                                     {True: "na tomada", False: "na bateria"}.get(bt.get("plugged"), ""),
                                                     bt.get("chem")) if x),
                       "rows": _rows(("Capacidade de fábrica", f"{bt['design']:,} {unit}".replace(",", ".")
                                      if bt.get("design") else ""),
                                     ("Capacidade atual", f"{bt['full']:,} {unit}".replace(",", ".") if bt.get("full")
                                      else ""),
                                     ("Ciclos de carga", str(bt["cycles"]) if bt.get("cycles", -1) > 0 else "")),
                       "meter": meter})
    if blocks:
        hp = battery_health(info["battery"][0])
        cards.append({"key": "battery", "title": "Bateria", "icon": "bolt",
                      "badge": (f"Saúde {hp}%", "ok" if hp >= 80 else "warn" if hp >= 50 else "bad") if hp > 0 else None,
                      "rows": [], "blocks": blocks,
                      "note": "" if hp > 0 else "A bateria não informou a capacidade de fábrica."})
    else:
        cards.append({"key": "battery", "title": "Bateria", "icon": "bolt", "badge": None, "rows": [], "blocks": [],
                      "note": "Nenhuma bateria encontrada (computador de mesa ou bateria não detectada)."})
    # ---- temperaturas
    temps = list(info.get("temps") or [])
    for d in info.get("disks") or []:
        if d.get("temp", -1) > 0:
            temps.append({"name": f"Disco: {d['model']}", "c": d["temp"]})
    rows = [(t["name"], f"{t['c']:.0f} °C") for t in temps[:8]]
    hot = max((t["c"] for t in temps), default=0)
    cards.append({"key": "temps", "title": "Temperaturas", "icon": "gauge",
                  "badge": (f"{hot:.0f} °C", "bad" if hot >= 85 else "warn" if hot >= 70 else "ok") if temps else None,
                  "rows": rows, "blocks": [],
                  "note": "" if temps else ("Este computador não informa temperaturas pelo sistema. Para ver a "
                                            "temperatura do processador e da placa de vídeo, use o programa do "
                                            "fabricante (ex.: da placa-mãe ou do notebook).")})
    return cards


def hero(info: dict) -> dict:
    """Resumo para o topo da página."""
    o = info.get("os") or {}
    cpu = (info.get("cpu") or [{}])[0]
    gpus = info.get("gpu") or []
    disks = info.get("disks") or []
    pc = " ".join(x for x in (o.get("maker"), o.get("model")) if x)
    return {
        "title": o.get("computer") or "Meu computador",
        "sub": " · ".join(x for x in (pc, o.get("name")) if x),
        "chips": [("chip", "Processador", _short_cpu(cpu.get("name", ""))),
                  ("database", "Memória", gb((info.get("ram") or {}).get("total", 0)) if (info.get("ram") or {}).get("total")
                   else "—"),
                  ("drive", "Armazenamento", fmt_size(sum(d.get("size", 0) for d in disks)) if disks else "—"),
                  ("monitor", "Vídeo", _short_gpu(gpus) or "—")],
    }


def _short_cpu(name: str) -> str:
    n = re.sub(r"\((R|TM|tm|r)\)|®|™|\bCPU\b|\bProcessor\b|\d+-Core|with Radeon.*|@.*", "", name or "")
    n = re.sub(r"\s+", " ", n).strip()
    return n or "—"


def _short_gpu(gpus) -> str:
    names = [g["name"] for g in gpus if g.get("name")]
    # prefere a placa dedicada (NVIDIA/AMD Radeon RX) quando houver integrada + dedicada
    names.sort(key=lambda x: 0 if re.search(r"nvidia|geforce|rtx|gtx|radeon rx|arc a", x, re.I) else 1)
    return re.sub(r"\((R|TM)\)", "", names[0]).strip() if names else ""


# =================================================================== exportação
def summary_text(info: dict) -> str:
    h = hero(info)
    lines = [f"{h['title']} — {h['sub']}", f"Gerado pelo {APP_NAME} em "
             f"{info.get('collected', datetime.datetime.now()):%d/%m/%Y %H:%M}", ""]
    for c in build_cards(info):
        head = c["title"].upper() + (f"  [{c['badge'][0]}]" if c.get("badge") else "")
        lines.append(head)
        for k, v in c["rows"]:
            lines.append(f"  {k}: {v}")
        for b in c["blocks"]:
            t = b["title"] + (f" ({b['sub']})" if b.get("sub") else "")
            if b.get("badge"):
                t += f" [{b['badge'][0]}]"
            lines.append(f"  • {t}")
            if b.get("meter"):
                lines.append(f"      {b['meter'][2]}")
            for k, v in b.get("rows", []):
                lines.append(f"      {k}: {v}")
        if c.get("note") and not c["rows"] and not c["blocks"]:
            lines.append(f"  {c['note']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


_TONE = {"ok": ("#16a34a", "#dcfce7"), "warn": ("#b45309", "#fef3c7"), "bad": ("#dc2626", "#fee2e2"),
         "info": ("#5b5bf0", "#e8e8fe")}


def report_html(info: dict) -> str:
    e = html.escape
    h = hero(info)
    when = info.get("collected", datetime.datetime.now())

    def badge(bd):
        if not bd:
            return ""
        fg, bg = _TONE.get(bd[1], _TONE["info"])
        return f'<span class="badge" style="color:{fg};background:{bg}">{e(bd[0])}</span>'

    def rows(rs):
        if not rs:
            return ""
        return "<dl>" + "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in rs) + "</dl>"

    parts = []
    for c in build_cards(info):
        body = rows(c["rows"])
        for b in c["blocks"]:
            meter = ""
            if b.get("meter"):
                frac, tone, txt = b["meter"]
                meter = (f'<div class="meter"><div style="width:{frac * 100:.0f}%;background:{_TONE[tone][0]}"></div>'
                         f'</div><div class="mtxt">{e(txt)}</div>')
            body += (f'<div class="block"><div class="bh"><b>{e(b["title"])}</b>{badge(b.get("badge"))}</div>'
                     + (f'<div class="sub">{e(b["sub"])}</div>' if b.get("sub") else "") + meter + rows(b.get("rows"))
                     + "</div>")
        if c.get("note"):
            body += f'<p class="note">{e(c["note"])}</p>'
        parts.append(f'<section class="card"><h2>{e(c["title"])}{badge(c.get("badge"))}</h2>{body}</section>')
    chips = "".join(f'<div class="chip"><span>{e(lbl)}</span><b>{e(val)}</b></div>' for _, lbl, val in h["chips"])
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ficha do computador — {e(h['title'])}</title>
<style>
:root{{--bg:#f3f5fa;--card:#fff;--text:#0f172a;--muted:#64748b;--border:#e3e8f1;--accent:#5b5bf0}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0b1020;--card:#141a2e;--text:#e6e9f2;--muted:#9aa3bd;--border:#26304f;--accent:#7070ff}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 "Segoe UI",system-ui,-apple-system,sans-serif}}
.wrap{{max-width:1100px;margin:0 auto;padding:32px 20px}}
header{{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:24px 26px;margin-bottom:18px}}
header h1{{margin:0;font-size:24px}}header p{{margin:4px 0 16px;color:var(--muted)}}
.chips{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}}
.chip{{border:1px solid var(--border);border-radius:10px;padding:10px 12px}}.chip span{{display:block;color:var(--muted);font-size:12px}}
.grid{{columns:2 420px;column-gap:18px}}
.card{{break-inside:avoid;background:var(--card);border:1px solid var(--border);border-radius:14px;padding:18px 20px;margin:0 0 18px}}
h2{{font-size:16px;margin:0 0 10px;display:flex;align-items:center;gap:10px}}
.badge{{font-size:12px;font-weight:600;padding:2px 9px;border-radius:999px;margin-left:auto}}
dl{{display:grid;grid-template-columns:minmax(110px,auto) 1fr;gap:4px 14px;margin:6px 0 0}}dt{{color:var(--muted)}}dd{{margin:0;font-weight:600;word-break:break-word}}
.block{{border:1px solid var(--border);border-radius:10px;padding:10px 12px;margin-top:10px}}.bh{{display:flex;align-items:center;gap:8px}}
.sub{{color:var(--muted);font-size:13px}}.note{{color:var(--muted);font-size:13px;margin:10px 0 0}}
.meter{{height:6px;background:var(--border);border-radius:6px;margin:8px 0 2px;overflow:hidden}}.meter div{{height:100%}}
.mtxt{{font-size:12px;color:var(--muted)}}footer{{color:var(--muted);font-size:12px;text-align:center;margin-top:10px}}
@media print{{body{{background:#fff}}.card,header{{border-color:#ccc}}}}
</style></head><body><div class="wrap">
<header><h1>{e(h['title'])}</h1><p>{e(h['sub'])}</p><div class="chips">{chips}</div></header>
<div class="grid">{''.join(parts)}</div>
<footer>Relatório gerado pelo {e(APP_NAME)} {e(__version__)} em {when:%d/%m/%Y às %H:%M}.</footer>
</div></body></html>
"""


def to_jsonable(info: dict) -> str:
    """Para depuração: a ficha normalizada em JSON."""
    return json.dumps(info, default=str, ensure_ascii=False, indent=2)
