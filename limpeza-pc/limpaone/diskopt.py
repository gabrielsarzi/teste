"""Otimização de discos (Windows): lista volumes com tipo de mídia, análise de fragmentação e
Optimize-Volume (TRIM em SSD, desfragmentação em HD — nunca desfragmenta SSD)."""
from __future__ import annotations

from .utils import IS_WIN, log
from .winutil import ps_json, run_ps_elevated

_LIST_PS = r"""
$disks = @{}
Get-PhysicalDisk | ForEach-Object { $disks[[string]$_.DeviceId] = $_ }
Get-Partition | Where-Object { $_.DriveLetter } | ForEach-Object {
  $p = $_
  $v = Get-Volume -DriveLetter $p.DriveLetter
  $d = $disks[[string]$p.DiskNumber]
  if ($v -and $v.Size -gt 0) {
    [pscustomobject]@{
      Letter = [string]$p.DriveLetter; Label = [string]$v.FileSystemLabel; FS = [string]$v.FileSystem
      Size = [int64]$v.Size; Free = [int64]$v.SizeRemaining; DriveType = [string]$v.DriveType
      Media = [string]$d.MediaType; Bus = [string]$d.BusType; Model = [string]$d.FriendlyName
      Spindle = [string]$d.SpindleSpeed
    }
  }
}
"""

# últimas otimizações registradas pelo próprio Windows (evento 258 do "Otimizador de armazenamento")
_LAST_PS = r"""
$seen = @{}
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Microsoft-Windows-Defrag'; Id=258} `
  -MaxEvents 300 | ForEach-Object {
  $txt = ($_.Properties | ForEach-Object { [string]$_.Value }) -join ' '
  if ($txt -match '\(([A-Za-z]):\)' -or $_.Message -match '\(([A-Za-z]):\)') {
    $L = $Matches[1].ToUpper()
    if (-not $seen.ContainsKey($L)) {
      $seen[$L] = 1
      [pscustomobject]@{ Letter = $L; Time = ([DateTimeOffset]$_.TimeCreated).ToUnixTimeSeconds() }
    }
  }
}
"""


def media_kind(media: str, spindle: str = "") -> str:
    """'SSD', 'HD' ou '?' a partir do MediaType do Get-PhysicalDisk (texto ou número)."""
    m = str(media or "").strip().upper()
    if m in ("SSD", "4", "SCM", "5"):
        return "SSD"
    if m in ("HDD", "3"):
        return "HD"
    sp = str(spindle or "").strip()
    if sp == "0":
        return "SSD"
    return "?"


def list_volumes() -> list[dict]:
    """[{letter, label, fs, size, free, kind ('SSD'|'HD'|'?'), bus, model, removable, last}]"""
    if not IS_WIN:
        return []
    vols = []
    for r in ps_json(_LIST_PS, timeout=90):
        letter = str(r.get("Letter") or "").strip()[:1].upper()
        if not letter:
            continue
        dt = str(r.get("DriveType") or "")
        if dt in ("CD-ROM", "5", "Network", "4"):
            continue
        vols.append({"letter": letter, "label": r.get("Label") or "", "fs": r.get("FS") or "",
                     "size": int(r.get("Size") or 0), "free": int(r.get("Free") or 0),
                     "kind": media_kind(r.get("Media"), r.get("Spindle")), "bus": str(r.get("Bus") or ""),
                     "model": str(r.get("Model") or "").strip(), "removable": dt in ("Removable", "2"),
                     "last": None, "frag": None, "frag_msg": ""})
    last = {str(r.get("Letter") or "").upper(): r.get("Time") for r in ps_json(_LAST_PS, timeout=60)}
    for v in vols:
        t = last.get(v["letter"])
        v["last"] = float(t) if isinstance(t, (int, float)) else None
    vols.sort(key=lambda v: v["letter"])
    return vols


_ANALYSIS_ERRORS = {1: "acesso negado", 2: "não suportado neste volume", 3: "volume sujo (rode o chkdsk)",
                    4: "pouco espaço livre para analisar", 5: "volume corrompido", 6: "sem memória",
                    11: "sistema de arquivos não suportado"}


def analysis_script(letters) -> str:
    ls = ",".join(f"'{x}'" for x in letters if len(x) == 1 and x.isalpha())
    return r"""
$res = @()
foreach ($L in @(%s)) {
  $v = Get-CimInstance Win32_Volume -Filter "DriveLetter='$($L):'"
  if (-not $v) { $res += [pscustomobject]@{Letter=$L; Code=-2; Frag=$null}; continue }
  $r = Invoke-CimMethod -InputObject $v -MethodName DefragAnalysis
  $frag = $null
  if ($r.DefragAnalysis) { $frag = [double]$r.DefragAnalysis.FilePercentFragmentation }
  $res += [pscustomobject]@{Letter=$L; Code=[int]$r.ReturnValue; Frag=$frag; Rec=[bool]$r.DefragRecommended}
}
ConvertTo-Json -InputObject @($res) -Depth 4 | Set-Content -Encoding UTF8 $out
""" % ls


def analyze_fragmentation(letters) -> dict:
    """{letra: (percentual ou None, mensagem)} — pede administrador (UAC) uma vez para todas."""
    if not IS_WIN:
        raise RuntimeError("disponível apenas no Windows")
    rc, data = run_ps_elevated(analysis_script(letters), timeout=3600)
    if rc == -1:
        raise PermissionError("A análise precisa de permissão de administrador.")
    return parse_analysis(data)


def parse_analysis(data) -> dict:
    if isinstance(data, dict):
        data = [data]
    out = {}
    for r in data or []:
        letter = str(r.get("Letter") or "").upper()
        code = r.get("Code")
        frag = r.get("Frag")
        if code == 0 and isinstance(frag, (int, float)):
            msg = "Recomendado otimizar" if r.get("Rec") else "Não precisa"
            out[letter] = (float(frag), msg)
        else:
            out[letter] = (None, _ANALYSIS_ERRORS.get(code, f"falha na análise (código {code})"))
    return out


def optimize_script(vols) -> str:
    """vols: [(letra, tipo)]. SSD -> -ReTrim; nos outros casos o próprio Windows decide o que fazer
    (desfragmentar um disco que na verdade é SSD só gasta a vida útil dele)."""
    lines = ["$res = @()"]
    for letter, kind in vols:
        if not (len(letter) == 1 and letter.isalpha()):
            continue
        flag = " -ReTrim" if kind == "SSD" else ""
        lines.append(
            f"try {{ Optimize-Volume -DriveLetter {letter}{flag} -ErrorAction Stop; "
            f"$res += [pscustomobject]@{{Letter='{letter}'; Ok=$true; Error=''}} }} "
            f"catch {{ $res += [pscustomobject]@{{Letter='{letter}'; Ok=$false; Error=$_.Exception.Message}} }}")
    lines.append("ConvertTo-Json -InputObject @($res) -Depth 3 | Set-Content -Encoding UTF8 $out")
    return "\n".join(lines)


def optimize_volumes(vols) -> dict:
    """{letra: (ok, erro)}"""
    if not IS_WIN:
        raise RuntimeError("disponível apenas no Windows")
    rc, data = run_ps_elevated(optimize_script(vols), timeout=6 * 3600)
    if rc == -1:
        raise PermissionError("Otimizar discos precisa de permissão de administrador.")
    if isinstance(data, dict):
        data = [data]
    out = {}
    for r in data or []:
        out[str(r.get("Letter") or "").upper()] = (bool(r.get("Ok")), str(r.get("Error") or ""))
    for letter, kind in vols:
        out.setdefault(letter, (False, "sem resposta do Windows"))
        if out[letter][0]:
            log(f"DISCO OTIMIZADO {letter}: ({'TRIM' if kind == 'SSD' else 'desfragmentação' if kind == 'HD' else 'automático'})")
    return out
