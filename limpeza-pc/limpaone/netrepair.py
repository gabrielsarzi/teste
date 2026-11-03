"""Reparo da configuração de rede do Windows ("Código 56" e afins).

Versão do app (mais conservadora que o pacote corrigir-wifi/): primeiro DIAGNOSTICA. Só mexe em algo se encontrar
um problema real (componente de rede cujo arquivo não existe mais, ou placa com erro). Nunca instala drivers,
nunca remove componentes que funcionam e só faz o reset completo (netcfg -d) se houver componente quebrado ou
placa com Código 56. Faz backup do registro de rede e gera relatório na Área de Trabalho.
"""
import os
import tempfile

from .utils import IS_WIN, log

SCRIPT = r'''@echo off
rem ==================================================================
rem  REPARAR REDE (LimpaOne) - diagnostica e so corrige o que estiver quebrado
rem   1. backup do registro de rede
rem   2. procura componentes de rede cujo arquivo nao existe mais
rem   3. remove SO os quebrados (nao-Microsoft) e limpa as ligacoes deles
rem   4. reativa servicos de rede do Windows que estiverem DESATIVADOS
rem   5. reset da pilha de rede SO se houver problema
rem   6. reinstala placas com erro (nunca as desativadas pelo usuario)
rem   7. se ainda houver erro: reparo de arquivos do sistema (SFC)
rem  NAO instala drivers. Relatorio e backup ficam na Area de Trabalho.
rem ==================================================================
set "LIMPA_BAT=%~f0"
%SystemRoot%\System32\net.exe session >nul 2>&1
if not errorlevel 1 goto admin
echo Pedindo permissao de administrador...
%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -Command "Start-Process -FilePath $env:LIMPA_BAT -Verb RunAs"
exit /b
:admin
set "LIMPA_BAT=%~f0"
%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText($env:LIMPA_BAT); $i=$s.LastIndexOf('#__PS_START__'); Invoke-Expression $s.Substring($i+13)"
echo.
pause
exit /b
#__PS_START__
$ErrorActionPreference = 'Continue'
$desk = [Environment]::GetFolderPath('Desktop')
$log = Join-Path $desk 'reparar-rede-relatorio.txt'
$bk = Join-Path $desk ('backup-rede-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force -Path $bk | Out-Null
Set-Content -Path $log -Value ('=== Reparar rede (LimpaOne) ' + (Get-Date) + ' ===')
function L([string]$t) { Add-Content -Path $log -Value $t; Write-Host $t }
function T([string]$t) { L ''; L ('==== ' + $t); Write-Host '' }
L ('Windows: ' + [Environment]::OSVersion.VersionString)

$CS = 'HKLM:\SYSTEM\CurrentControlSet'
$NET = '{4d36e972-e325-11ce-bfc1-08002be10318}'
$CLASSES = @('{4d36e973-e325-11ce-bfc1-08002be10318}', '{4d36e974-e325-11ce-bfc1-08002be10318}', '{4d36e975-e325-11ce-bfc1-08002be10318}')
$SYS = [Environment]::SystemDirectory
$msBroken = $false

function Resolve-Dll([string]$d) {
  if (-not $d) { return $null }
  $d = [Environment]::ExpandEnvironmentVariables($d.Trim().Trim('"'))
  if (-not [IO.Path]::IsPathRooted($d)) { $d = Join-Path $SYS $d }
  return $d
}

function Resolve-Img([string]$p) {
  if (-not $p) { return $null }
  $p = $p.Trim().Trim('"')
  $i = $p.ToLower().IndexOf('.sys')
  if ($i -lt 0) { return $null }
  $p = $p.Substring(0, $i + 4)
  if ($p.StartsWith('\SystemRoot\', 'OrdinalIgnoreCase')) { $p = $env:SystemRoot + $p.Substring(11) }
  elseif ($p.StartsWith('system32\', 'OrdinalIgnoreCase')) { $p = $env:SystemRoot + '\' + $p }
  elseif ($p.StartsWith('\??\')) { $p = $p.Substring(4) }
  return [Environment]::ExpandEnvironmentVariables($p)
}

function Net-Status {
  Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object { $_.PNPClass -eq 'Net' } | ForEach-Object {
    L ('  ' + $_.Name + ' - codigo ' + $_.ConfigManagerErrorCode)
  }
}

# ================================================================ 1
T '[1] Backup do registro de rede'
L ('  pasta: ' + $bk)
$exp = @{
  'network'       = 'HKLM\SYSTEM\CurrentControlSet\Control\Network'
  'class-adapter' = 'HKLM\SYSTEM\CurrentControlSet\Control\Class\' + $NET
  'class-client'  = 'HKLM\SYSTEM\CurrentControlSet\Control\Class\' + $CLASSES[0]
  'class-service' = 'HKLM\SYSTEM\CurrentControlSet\Control\Class\' + $CLASSES[1]
  'class-proto'   = 'HKLM\SYSTEM\CurrentControlSet\Control\Class\' + $CLASSES[2]
}
foreach ($k in $exp.Keys) {
  reg export $exp[$k] (Join-Path $bk ($k + '.reg')) /y 2>&1 | Out-Null
  L ('  ' + $k + ': codigo ' + $LASTEXITCODE)
}
L '  Situacao inicial das placas:'
Net-Status

# ================================================================ 2
T '[2] Componentes de rede (clientes, servicos, protocolos)'
$broken = @()
foreach ($c in $CLASSES) {
  foreach ($key in (Get-ChildItem -Path "$CS\Control\Class\$c" -ErrorAction SilentlyContinue)) {
    $p = Get-ItemProperty -Path $key.PSPath -ErrorAction SilentlyContinue
    if (-not $p -or -not $p.ComponentId) { continue }
    $ndi = Get-ItemProperty -Path (Join-Path $key.PSPath 'Ndi') -ErrorAction SilentlyContinue
    $prob = @()
    if ($ndi -and $ndi.ComponentDll) {
      $dll = Resolve-Dll ([string]$ndi.ComponentDll)
      if (-not (Test-Path -LiteralPath $dll)) { $prob += ('DLL ausente: ' + $ndi.ComponentDll) }
    }
    if ($ndi -and $ndi.Service) {
      $sp = Get-ItemProperty -Path "$CS\Services\$($ndi.Service)" -ErrorAction SilentlyContinue
      if (-not $sp) { $prob += ('servico inexistente: ' + $ndi.Service) }
      else {
        $img = Resolve-Img ([string]$sp.ImagePath)
        if ($img -and -not (Test-Path -LiteralPath $img)) { $prob += ('driver ausente: ' + $img) }
      }
    }
    $line = '  ' + $p.ComponentId + '  [' + $key.PSChildName + ']'
    if ($prob.Count -gt 0) {
      L ($line + '  >>> PROBLEMA: ' + ($prob -join '; '))
      $broken += [pscustomobject]@{ Id = [string]$p.ComponentId; Path = $key.PSPath; Cls = $c; Inst = [string]$p.NetCfgInstanceId; Svc = [string]$ndi.Service }
    } else { L $line }
  }
}

T '[3] Removendo componentes quebrados que NAO sao da Microsoft'
$badSvc = @()
$fixed = 0
if ($broken.Count -eq 0) { L '  nenhum componente quebrado nas classes' }
foreach ($b in $broken) {
  if ($b.Id.ToLower().StartsWith('ms_')) { $msBroken = $true; L ('  ' + $b.Id + ': e da Microsoft - NAO removido (o SFC no final tenta reparar)'); continue }
  if ($b.Svc) { reg export ('HKLM\SYSTEM\CurrentControlSet\Services\' + $b.Svc) (Join-Path $bk ('servico-' + $b.Svc + '.reg')) /y 2>&1 | Out-Null }
  $fixed++
  Remove-Item -Path $b.Path -Recurse -Force -ErrorAction SilentlyContinue
  L ('  removido (Class): ' + $b.Id)
  if ($b.Inst) {
    $nk = "$CS\Control\Network\$($b.Cls)\$($b.Inst)"
    if (Test-Path $nk) { Remove-Item -Path $nk -Recurse -Force -ErrorAction SilentlyContinue; L ('  removido (Network): ' + $b.Id) }
  }
  if ($b.Svc) { $badSvc += $b.Svc; sc.exe delete $b.Svc 2>&1 | Out-Null; L ('  servico marcado para exclusao: ' + $b.Svc) }
}

L '  Entradas orfas em Control\Network:'
foreach ($c in $CLASSES) {
  foreach ($key in (Get-ChildItem -Path "$CS\Control\Network\$c" -ErrorAction SilentlyContinue)) {
    $p = Get-ItemProperty -Path $key.PSPath -ErrorAction SilentlyContinue
    if (-not $p -or -not $p.ComponentId) { continue }
    $id = [string]$p.ComponentId
    $ndi = Get-ItemProperty -Path (Join-Path $key.PSPath 'Ndi') -ErrorAction SilentlyContinue
    $missing = $false
    if ($ndi -and $ndi.ComponentDll) { $missing = -not (Test-Path -LiteralPath (Resolve-Dll ([string]$ndi.ComponentDll))) }
    # so remove se o arquivo do componente REALMENTE nao existe mais (nunca pelo nome do fabricante)
    if ($missing -and -not $id.ToLower().StartsWith('ms_')) {
      $fixed++
      Remove-Item -Path $key.PSPath -Recurse -Force -ErrorAction SilentlyContinue
      L ('  removido orfao: ' + $id + ' (' + $key.PSChildName + ')')
      if ($ndi -and $ndi.Service) { $badSvc += [string]$ndi.Service }
    } elseif ($missing) { $msBroken = $true; L ('  ATENCAO: ' + $id + ' da Microsoft com DLL ausente: ' + $ndi.ComponentDll) }
  }
}

# ================================================================ 3
T '[4] Ligacoes (UpperBind) e filtros invalidos das placas'
$badSvc = @($badSvc | Select-Object -Unique)
foreach ($key in (Get-ChildItem -Path "$CS\Control\Class\$NET" -ErrorAction SilentlyContinue)) {
  $lk = Join-Path $key.PSPath 'Linkage'
  $lp = Get-ItemProperty -Path $lk -ErrorAction SilentlyContinue
  if ($lp -and $lp.UpperBind) {
    $old = @($lp.UpperBind)
    $new = @($old | Where-Object { $badSvc -notcontains $_ })
    if ($new.Count -ne $old.Count) {
      Set-ItemProperty -Path $lk -Name 'UpperBind' -Value ([string[]]$new)
      L ('  ' + $key.PSChildName + ': UpperBind limpo')
    }
  }
}
$tp = Get-ItemProperty -Path "$CS\Control\Class\$NET" -ErrorAction SilentlyContinue
foreach ($v in @('UpperFilters', 'LowerFilters')) {
  if ($tp -and $tp.$v) {
    $old = @($tp.$v)
    $new = @($old | Where-Object { Test-Path "$CS\Services\$_" })
    if ($new.Count -ne $old.Count) {
      Set-ItemProperty -Path "$CS\Control\Class\$NET" -Name $v -Value ([string[]]$new)
      L ('  filtro de classe ' + $v + ' limpo')
    }
  }
}
L '  ok'

# ================================================================ 4
T '[5] Servicos de rede do Windows'
$svcs = [ordered]@{ 'NetSetupSvc' = 'Manual'; 'WlanSvc' = 'Automatic'; 'Dhcp' = 'Automatic'; 'Dnscache' = 'Automatic';
  'NlaSvc' = 'Automatic'; 'netprofm' = 'Manual'; 'Wcmsvc' = 'Automatic'; 'DeviceInstall' = 'Manual'; 'BFE' = 'Automatic';
  'nsi' = 'Automatic'; 'RmSvc' = 'Manual'; 'iphlpsvc' = 'Automatic'; 'bthserv' = 'Manual' }
foreach ($n in $svcs.Keys) {
  $s = Get-Service -Name $n -ErrorAction SilentlyContinue
  if (-not $s) { continue }
  if ($s.StartType -eq 'Disabled') {
    sc.exe config $n start= $(if ($svcs[$n] -eq 'Automatic') { 'auto' } else { 'demand' }) 2>&1 | Out-Null
    L ('  ' + $n + ': estava DESATIVADO -> reativado')
  } else { L ('  ' + $n + ': ' + $s.StartType + ' / ' + $s.Status) }
}

# ================================================================ 5
T '[6] Reset da pilha de rede'
ipconfig /flushdns 2>&1 | Out-Null; L '  cache de DNS limpo'
$err56 = @(Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object { $_.PNPClass -eq 'Net' -and $_.ConfigManagerErrorCode -eq 56 })
if ($fixed -gt 0 -or $err56.Count -gt 0) {
  L '  problema confirmado (componente quebrado ou Codigo 56): resetando a pilha de rede'
  L '  (isso apaga IPs fixos, VPNs e adaptadores virtuais - o backup do registro esta na pasta acima)'
  netsh winsock reset 2>&1 | Out-Null; L ('  winsock reset: ' + $LASTEXITCODE)
  netsh int ip reset 2>&1 | Out-Null; L ('  ip reset: ' + $LASTEXITCODE)
  netsh int ipv6 reset 2>&1 | Out-Null; L ('  ipv6 reset: ' + $LASTEXITCODE)
  $o = (netcfg -d 2>&1 | Out-String); L '  netcfg -d:'; L $o
} else { L '  nenhum componente quebrado nem Codigo 56: reset completo NAO foi necessario' }

# ================================================================ 7
T '[7] Reinstalando placas com problema'
# 22 = desativada pelo usuario, 45 = nao conectada: essas NUNCA sao removidas
$bad = Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object { $_.PNPClass -eq 'Net' -and @(0, 22, 45) -notcontains $_.ConfigManagerErrorCode }
foreach ($d in $bad) {
  L ('  ' + $d.Name + ' - codigo ' + $d.ConfigManagerErrorCode + ' - removendo para reinstalar')
  pnputil /remove-device "$($d.PNPDeviceID)" 2>&1 | Out-Null
}
pnputil /scan-devices 2>&1 | Out-Null
Start-Sleep -Seconds 10
L '  Situacao agora:'
Net-Status
$still = @(Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object { $_.PNPClass -eq 'Net' -and @(0, 22, 45) -notcontains $_.ConfigManagerErrorCode })

# ================================================================ 8
T '[8] Componentes de rede instalados (netcfg -s n)'
L ((netcfg -s n 2>&1) | Out-String)
L 'Linhas relevantes do setupapi.dev.log:'
$sl = Join-Path $env:windir 'INF\setupapi.dev.log'
if (Test-Path $sl) {
  Select-String -Path $sl -Pattern 'B852', '8007007e', 'netsetup', 'NetCfg' -ErrorAction SilentlyContinue | Select-Object -Last 30 | ForEach-Object { L ('  ' + $_.Line) }
}

if ($msBroken -or $still.Count -gt 0) {
  T '[9] Reparo de arquivos do sistema (SFC) - pode levar de 10 a 20 minutos'
  L '  Nao feche esta janela...'
  $sfc = (sfc /scannow 2>&1 | Out-String) -replace "`0", ''
  L (($sfc -split "`n" | Where-Object { $_.Trim() } | Select-Object -Last 4) -join ' | ')
} else { T '[9] SFC nao foi necessario' }

L ''
L '=============================================================='
L ' PRONTO. Relatorio: reparar-rede-relatorio.txt (Area de Trabalho)'
L (' Backup do registro: ' + $bk)
L ' REINICIE o computador para concluir.'
L '=============================================================='
$r = Read-Host 'Reiniciar agora? (S/N)'
if ($r -match '^[sS]') { Restart-Computer -Force }
'''


def run_network_repair() -> str:
    """Grava o script em um .bat temporário e o executa (ele mesmo pede permissão de administrador)."""
    if not IS_WIN:
        return "O reparo de rede está disponível apenas no Windows."
    # pasta nova e exclusiva (não um nome fixo no TEMP que outro processo poderia preparar antes)
    path = os.path.join(tempfile.mkdtemp(prefix="LimpaOne-rede-"), "reparar-rede.bat")
    with open(path, "w", encoding="ascii", errors="replace", newline="\r\n") as f:
        f.write(SCRIPT)
    log("FERRAMENTA reparar rede")
    os.startfile(path)  # type: ignore[attr-defined]
    return ""
