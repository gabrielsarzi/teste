# ==================================================================
#  Restaurar programas (LimpaOne) - reinstala via winget os programas
#  escolhidos apos a reinstalacao do Windows.
#  Rode no Terminal/PowerShell COMO ADMINISTRADOR.
# ==================================================================
$ErrorActionPreference = 'Continue'

$apps = @(
  @{ id = 'Git.Git';                          nome = 'Git' }
  @{ id = 'GitHub.cli';                       nome = 'GitHub CLI' }
  @{ id = 'OpenJS.NodeJS.LTS';                nome = 'Node.js 24'; ver = '24.22.1' }
  @{ id = 'Python.Python.3.14';               nome = 'Python 3.14' }
  @{ id = 'Microsoft.OpenJDK.17';             nome = 'Java 17 (Microsoft OpenJDK)' }
  @{ id = 'Microsoft.DotNet.SDK.8';           nome = '.NET 8 SDK' }
  @{ id = 'Microsoft.DotNet.DesktopRuntime.8'; nome = '.NET Desktop Runtime 8' }
  @{ id = 'Microsoft.VCRedist.2015+.x64';     nome = 'Visual C++ Redistributable x64' }
  @{ id = 'Microsoft.VCRedist.2015+.x86';     nome = 'Visual C++ Redistributable x86' }
  @{ id = 'Microsoft.msmpi';                  nome = 'Microsoft MPI' }
  @{ id = 'Cloudflare.cloudflared';           nome = 'cloudflared' }
  @{ id = 'Gyan.FFmpeg';                      nome = 'FFmpeg' }
  @{ id = 'Anthropic.ClaudeCode';             nome = 'Claude Code' }
  @{ id = 'Microsoft.Office';                 nome = 'Microsoft 365 (Office)' }
)

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Write-Host 'Abra o Terminal como ADMINISTRADOR e rode de novo (botao direito no Iniciar > Terminal (Administrador)).' -ForegroundColor Yellow
  return
}
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  Write-Host 'winget nao encontrado. Instale o "Instalador de Aplicativo" pela Microsoft Store e rode de novo.' -ForegroundColor Yellow
  Start-Process 'ms-windows-store://pdp/?productid=9NBLGGH4NNS1'
  return
}

$log = Join-Path ([Environment]::GetFolderPath('Desktop')) 'restaurar-programas-relatorio.txt'
Set-Content -Path $log -Value ('Restaurar programas - ' + (Get-Date))
$ok = @(); $fail = @()
$i = 0
foreach ($a in $apps) {
  $i++
  Write-Host ''
  Write-Host ('[' + $i + '/' + $apps.Count + '] ' + $a.nome + ' ...') -ForegroundColor Cyan
  $wa = @('install', '--id', $a.id, '-e', '--source', 'winget', '--silent',
            '--accept-package-agreements', '--accept-source-agreements', '--disable-interactivity')
  if ($a.ver) { $wa += @('--version', $a.ver) }
  & winget @wa
  $code = $LASTEXITCODE
  # 0 = instalado; -1978335189 (0x8A15002B) = ja instalado / sem atualizacao
  if ($code -eq 0 -or $code -eq -1978335189 -or $code -eq -1978335135) { $ok += $a.nome; Add-Content $log ('OK    ' + $a.nome) }
  else { $fail += ($a.nome + ' (codigo ' + $code + ')'); Add-Content $log ('ERRO  ' + $a.nome + ' codigo ' + $code) }
}

# JAVA_HOME para builds Android/Gradle
$jdk = Get-ChildItem 'C:\Program Files\Microsoft' -Directory -Filter 'jdk-17*' -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
if ($jdk) {
  [Environment]::SetEnvironmentVariable('JAVA_HOME', $jdk.FullName, 'Machine')
  Add-Content $log ('JAVA_HOME = ' + $jdk.FullName)
  Write-Host ('JAVA_HOME definido: ' + $jdk.FullName) -ForegroundColor Green
}

Write-Host ''
Write-Host '==============================================================' -ForegroundColor Green
Write-Host (' Instalados/ja presentes: ' + $ok.Count + ' de ' + $apps.Count) -ForegroundColor Green
if ($fail.Count -gt 0) {
  Write-Host ' Com erro (tente de novo depois, ou instale manualmente):' -ForegroundColor Yellow
  $fail | ForEach-Object { Write-Host ('   - ' + $_) -ForegroundColor Yellow }
}
Write-Host ' Relatorio: restaurar-programas-relatorio.txt (Area de Trabalho)'
Write-Host ' FECHE E ABRA o Terminal (ou reinicie) para os comandos novos (git, node, python, java, claude) funcionarem.'
Write-Host '==============================================================' -ForegroundColor Green
