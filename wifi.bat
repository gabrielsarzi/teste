@echo off
rem ==================================================================
rem  Corrigir Wi-Fi (LimpaOne) - repara a configuracao de rede do
rem  Windows quando os adaptadores ficam com "Codigo 56".
rem  Faz backup de tudo antes, na Area de Trabalho.
rem ==================================================================
net session >nul 2>&1
if not errorlevel 1 goto admin
echo Pedindo permissao de administrador...
powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
exit /b
:admin
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText('%~f0'); $i=$s.LastIndexOf('#__PS_START__'); Invoke-Expression $s.Substring($i+13)"
echo.
pause
exit /b
#__PS_START__
$ErrorActionPreference = 'Continue'
$desk = [Environment]::GetFolderPath('Desktop')
$log = Join-Path $desk 'corrigir-wifi-relatorio.txt'
$bk = Join-Path $desk ('backup-rede-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force -Path $bk | Out-Null
Set-Content -Path $log -Value ('=== Corrigir Wi-Fi (LimpaOne) ' + (Get-Date) + ' ===')
function L([string]$t) { Add-Content -Path $log -Value $t; Write-Host $t }
L ('Windows: ' + [Environment]::OSVersion.VersionString)

$CS = 'HKLM:\SYSTEM\CurrentControlSet'
$NET = '{4d36e972-e325-11ce-bfc1-08002be10318}'
$CLASSES = @('{4d36e973-e325-11ce-bfc1-08002be10318}', '{4d36e974-e325-11ce-bfc1-08002be10318}', '{4d36e975-e325-11ce-bfc1-08002be10318}')
$SYS = [Environment]::SystemDirectory

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

# ---------------------------------------------------------------- 1. backup
L ''
L ('[1] Backup do registro de rede em: ' + $bk)
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

# ---------------------------------------------------------------- 2. componentes quebrados
L ''
L '[2] Verificando componentes de rede (clientes, servicos, protocolos)'
$broken = @()
foreach ($c in $CLASSES) {
  foreach ($key in (Get-ChildItem -Path "$CS\Control\Class\$c" -ErrorAction SilentlyContinue)) {
    $p = Get-ItemProperty -Path $key.PSPath -ErrorAction SilentlyContinue
    if (-not $p -or -not $p.ComponentId) { continue }
    $ndi = Get-ItemProperty -Path (Join-Path $key.PSPath 'Ndi') -ErrorAction SilentlyContinue
    $prob = @()
    if ($ndi -and $ndi.ComponentDll) {
      $dll = [string]$ndi.ComponentDll
      if (-not [IO.Path]::IsPathRooted($dll)) { $dll = Join-Path $SYS $dll }
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

# ---------------------------------------------------------------- 3. remover os quebrados (nao Microsoft)
L ''
L '[3] Removendo componentes quebrados que NAO sao da Microsoft'
$badSvc = @('VMnetBridge')
if ($broken.Count -eq 0) { L '  nenhum componente quebrado encontrado nas classes' }
foreach ($b in $broken) {
  if ($b.Id.ToLower().StartsWith('ms_')) { L ('  ' + $b.Id + ': e da Microsoft - NAO removido (apenas relatado)'); continue }
  Remove-Item -Path $b.Path -Recurse -Force -ErrorAction SilentlyContinue
  L ('  removido (Class): ' + $b.Id)
  if ($b.Inst) {
    $nk = "$CS\Control\Network\$($b.Cls)\$($b.Inst)"
    if (Test-Path $nk) { Remove-Item -Path $nk -Recurse -Force -ErrorAction SilentlyContinue; L ('  removido (Network): ' + $b.Id) }
  }
  if ($b.Svc) { $badSvc += $b.Svc; sc.exe delete $b.Svc 2>&1 | Out-Null; L ('  servico marcado para exclusao: ' + $b.Svc) }
}

# ---------------------------------------------------------------- 4. orfaos em Control\Network
L ''
L '[4] Procurando entradas orfas em Control\Network'
foreach ($c in $CLASSES) {
  foreach ($key in (Get-ChildItem -Path "$CS\Control\Network\$c" -ErrorAction SilentlyContinue)) {
    $p = Get-ItemProperty -Path $key.PSPath -ErrorAction SilentlyContinue
    if (-not $p -or -not $p.ComponentId) { continue }
    $id = [string]$p.ComponentId
    $ndi = Get-ItemProperty -Path (Join-Path $key.PSPath 'Ndi') -ErrorAction SilentlyContinue
    $missing = $false
    if ($ndi -and $ndi.ComponentDll) { $missing = -not (Test-Path -LiteralPath (Join-Path $SYS ([string]$ndi.ComponentDll))) }
    $isVm = $id.ToLower().Contains('vmware') -or $id.ToLower().Contains('vmnet')
    if (($missing -or $isVm) -and -not $id.ToLower().StartsWith('ms_')) {
      Remove-Item -Path $key.PSPath -Recurse -Force -ErrorAction SilentlyContinue
      L ('  removido orfao: ' + $id + ' (' + $key.PSChildName + ')')
      if ($ndi -and $ndi.Service) { $badSvc += [string]$ndi.Service }
    } elseif ($missing) { L ('  ATENCAO: ' + $id + ' da Microsoft com DLL ausente: ' + $ndi.ComponentDll) }
  }
}

# ---------------------------------------------------------------- 5. ligacoes e filtros das placas
L ''
L '[5] Limpando ligacoes (UpperBind) e filtros invalidos das placas de rede'
$badSvc = $badSvc | Select-Object -Unique
L ('  servicos removidos/ignorados: ' + ($badSvc -join ', '))
foreach ($key in (Get-ChildItem -Path "$CS\Control\Class\$NET" -ErrorAction SilentlyContinue)) {
  $lk = Join-Path $key.PSPath 'Linkage'
  $lp = Get-ItemProperty -Path $lk -ErrorAction SilentlyContinue
  if ($lp -and $lp.UpperBind) {
    $old = @($lp.UpperBind)
    $new = @($old | Where-Object { ($badSvc -notcontains $_) -and ($_ -notlike 'VMnet*') })
    if ($new.Count -ne $old.Count) {
      Set-ItemProperty -Path $lk -Name 'UpperBind' -Value ([string[]]$new)
      L ('  ' + $key.PSChildName + ': UpperBind limpo (' + (($old | Where-Object { $new -notcontains $_ }) -join ', ') + ')')
    }
  }
}
foreach ($target in @("$CS\Control\Class\$NET")) {
  $tp = Get-ItemProperty -Path $target -ErrorAction SilentlyContinue
  foreach ($v in @('UpperFilters', 'LowerFilters')) {
    if ($tp -and $tp.$v) {
      $old = @($tp.$v)
      $new = @($old | Where-Object { Test-Path "$CS\Services\$_" })
      if ($new.Count -ne $old.Count) {
        Set-ItemProperty -Path $target -Name $v -Value ([string[]]$new)
        L ('  filtro de classe ' + $v + ' limpo: ' + (($old | Where-Object { $new -notcontains $_ }) -join ', '))
      }
    }
  }
}
if (Test-Path "$CS\Services\VMnetBridge") {
  Remove-Item -Path "$CS\Services\VMnetBridge" -Recurse -Force -ErrorAction SilentlyContinue
  L '  chave do servico VMnetBridge removida'
}

# ---------------------------------------------------------------- 6. reset de rede
L ''
L '[6] Reset da pilha de rede'
netsh winsock reset 2>&1 | Out-Null; L ('  winsock reset: codigo ' + $LASTEXITCODE)
netsh int ip reset 2>&1 | Out-Null; L ('  ip reset: codigo ' + $LASTEXITCODE)
$o = (netcfg -d 2>&1 | Out-String); L '  netcfg -d:'; L $o

# ---------------------------------------------------------------- 7. reinstalar placas
L ''
L '[7] Reinstalando placas com problema'
$bad = Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object { $_.PNPClass -eq 'Net' -and $_.ConfigManagerErrorCode -ne 0 }
foreach ($d in $bad) {
  L ('  ' + $d.Name + ' - codigo ' + $d.ConfigManagerErrorCode + ' - removendo para reinstalar')
  pnputil /remove-device "$($d.PNPDeviceID)" 2>&1 | Out-Null
}
pnputil /scan-devices 2>&1 | Out-Null
Start-Sleep -Seconds 8
L ''
L '[8] Situacao das placas agora'
Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object { $_.PNPClass -eq 'Net' } | ForEach-Object {
  L ('  ' + $_.Name + ' - codigo ' + $_.ConfigManagerErrorCode)
}

# ---------------------------------------------------------------- 9. diagnostico extra
L ''
L '[9] Componentes de rede instalados (netcfg -s n)'
L ((netcfg -s n 2>&1) | Out-String)
L '[10] Ultimas linhas relevantes do setupapi.dev.log'
$sl = Join-Path $env:windir 'INF\setupapi.dev.log'
if (Test-Path $sl) {
  Select-String -Path $sl -Pattern 'B852', '8007007e', 'netsetup', 'NetCfg' -ErrorAction SilentlyContinue | Select-Object -Last 40 | ForEach-Object { L ('  ' + $_.Line) }
}

L ''
L '=============================================================='
L ' PRONTO. Relatorio salvo em: corrigir-wifi-relatorio.txt (Area de Trabalho)'
L (' Backup do registro em: ' + $bk)
L ' REINICIE o computador agora para concluir.'
L '=============================================================='
$r = Read-Host 'Reiniciar agora? (S/N)'
if ($r -match '^[sS]') { Restart-Computer -Force }
