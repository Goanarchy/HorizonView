# HorizonView · arranque ESTABLE
# Enlace HTTPS fijo y gratis con Tailscale Funnel (plan personal gratuito).
# Si Tailscale no esta instalado o no ha iniciado sesion, usa el tunel
# rapido de Cloudflare como respaldo automatico. Sin certificados ni puertos.
$ErrorActionPreference = 'Stop'
$app = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $env:TEMP 'horizonview_estable'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Use-CloudflareFallback([string]$reason) {
    Write-Host "No se pudo activar el enlace fijo: $reason"
    Write-Host 'Usando el tunel rapido de Cloudflare como respaldo...'
    $fallback = Join-Path $app 'start-mobile.ps1'
    if (Test-Path $fallback) { & $fallback; exit }
    throw 'Falta start-mobile.ps1 para el respaldo.'
}

$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) { $pyCmd = Get-Command py -ErrorAction SilentlyContinue }
if (-not $pyCmd) { throw 'No se encontro Python 3.' }

# 1) Servidor local.
$listen = Get-NetTCPConnection -LocalPort 8770 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listen) {
    Write-Host "Servidor local ya activo (PID $($listen.OwningProcess))."
} else {
    $serverOut = Join-Path $logDir 'server.out.log'
    $serverErr = Join-Path $logDir 'server.err.log'
    if ($pyCmd.Name -eq 'py.exe') {
        $proc = Start-Process -FilePath 'py' -ArgumentList @('-3', 'src/server.py') -WorkingDirectory $app -PassThru -WindowStyle Hidden -RedirectStandardOutput $serverOut -RedirectStandardError $serverErr
    } else {
        $proc = Start-Process -FilePath 'python' -ArgumentList 'src/server.py' -WorkingDirectory $app -PassThru -WindowStyle Hidden -RedirectStandardOutput $serverOut -RedirectStandardError $serverErr
    }
    Write-Host "Servidor local iniciado (PID $($proc.Id))."
    Start-Sleep -Seconds 2
}

# 2) Localizar Tailscale (gratis en el plan personal).
$ts = $null
$tsCmd = Get-Command tailscale -ErrorAction SilentlyContinue
if ($tsCmd) { $ts = $tsCmd.Source }
if (-not $ts) {
    $known = 'C:\Program Files\Tailscale\tailscale.exe'
    if (Test-Path $known) { $ts = $known }
}
if (-not $ts) {
    Write-Host 'Tailscale no esta instalado. Es gratis: https://tailscale.com/download/windows'
    Write-Host 'Instalalo e inicia sesion para obtener un enlace FIJO; mientras tanto usamos Cloudflare.'
    Use-CloudflareFallback 'Tailscale no detectado'
}

# 3) Comprobar que haya sesion iniciada en Tailscale.
$statusRaw = & $ts status --json 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $statusRaw -notmatch '"Self"') {
    Write-Host 'Tailscale detectado, pero sin sesion iniciada.'
    Write-Host 'Ejecuta: tailscale login   (cuenta personal gratuita)'
    Use-CloudflareFallback 'Tailscale sin iniciar sesion'
}

# 4) Activar Funnel hacia el puerto local 8770.
$funnelRaw = & $ts funnel --bg 8770 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    if ($funnelRaw -match 'unknown flag|flag provided but not defined|not defined') {
        $fOut = Join-Path $logDir 'funnel.out.log'
        $fErr = Join-Path $logDir 'funnel.err.log'
        Start-Process -FilePath $ts -ArgumentList @('funnel', '8770') -WorkingDirectory $app -PassThru -WindowStyle Hidden -RedirectStandardOutput $fOut -RedirectStandardError $fErr | Out-Null
        Start-Sleep -Seconds 3
    } else {
        Write-Host "tailscale funnel --bg 8770 devolvio: $($funnelRaw.Trim())"
    }
}

# 5) Obtener la URL publica estable.
$url = $null
for ($i = 0; $i -lt 40; $i++) {
    $fstatus = & $ts funnel status 2>&1 | Out-String
    $m = [regex]::Match($fstatus, 'https://[a-z0-9-]+(?:\.[a-z0-9-]+)*\.ts\.net')
    if ($m.Success) { $url = $m.Value.TrimEnd('/') + '/'; break }
    Start-Sleep -Milliseconds 800
}
if (-not $url) {
    try {
        $j = $statusRaw | ConvertFrom-Json
        if ($j.Self.DNSName) { $url = 'https://' + $j.Self.DNSName.TrimEnd('.') + '/' }
    } catch { }
}
if (-not $url) { Use-CloudflareFallback 'no se obtuvo la URL de Tailscale Funnel' }

# 6) Verificar HTTPS de extremo a extremo.
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 1000
    try {
        $r = Invoke-WebRequest -Uri ($url + 'api/health') -TimeoutSec 8 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
}
if (-not $ok) { Use-CloudflareFallback 'la URL de Tailscale no respondio' }

# 7) Guardar enlace y regenerar QR local.
$urlFile = Join-Path $app 'URL_Movil.txt'
[System.IO.File]::WriteAllText($urlFile, $url, (New-Object System.Text.UTF8Encoding($false)))
$qr = Join-Path $app 'assets\qr-movil.png'
$env:HV_QR_URL = $url
$env:HV_QR_OUT = $qr
try {
    if ($pyCmd.Name -eq 'py.exe') {
        & py -3 -c "import os,qrcode; qrcode.make(os.environ['HV_QR_URL']).save(os.environ['HV_QR_OUT'])" 2>$null
    } else {
        & python -c "import os,qrcode; qrcode.make(os.environ['HV_QR_URL']).save(os.environ['HV_QR_OUT'])" 2>$null
    }
    if (Test-Path $qr) { Write-Host 'QR generado: assets\qr-movil.png' }
} catch {
    Write-Host 'QR no disponible (el enlace funciona igual).'
}

Write-Host ''
Write-Host '============================================================'
Write-Host "  ENLACE FIJO PARA CELULAR: $url"
Write-Host '============================================================'
Write-Host ''
Write-Host 'Este enlace NO cambia entre reinicios mientras uses la misma cuenta de Tailscale.'
Write-Host 'Certificado publico valido: abre en Android o iPhone sin avisos de seguridad.'
Write-Host "Para detener el publico: tailscale funnel off"
try { Start-Process $url } catch { }
