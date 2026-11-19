# HorizonView · arranque MOVIL
# Publica la app con un tunel HTTPS de Cloudflare: certificado publico valido,
# sin cuenta, sin abrir puertos y sin instalar certificados. Funciona en
# cualquier Android o iPhone y permite usar el GPS del telefono.
$ErrorActionPreference = 'Stop'
$app = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $env:TEMP 'horizonview_movil'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) { $pyCmd = Get-Command py -ErrorAction SilentlyContinue }
if (-not $pyCmd) { throw 'No se encontro Python 3.' }

# 1) Servidor local de la aplicacion.
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

# 2) Cerrar solo los tuneles rapidos creados por este proyecto.
$cf = Join-Path $app 'tools\cloudflared.exe'
if (-not (Test-Path $cf)) { throw 'Falta tools\cloudflared.exe.' }
Get-CimInstance Win32_Process -Filter "Name = 'cloudflared.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ExecutablePath -eq $cf } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# 3) Levantar el tunel. El log contiene la URL publica asignada.
$tunOut = Join-Path $logDir 'tunnel.out.log'
$tunErr = Join-Path $logDir 'tunnel.err.log'
$tunnel = Start-Process -FilePath $cf `
    -ArgumentList @('tunnel', '--no-autoupdate', '--url', 'http://127.0.0.1:8770') `
    -WorkingDirectory $app -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput $tunOut -RedirectStandardError $tunErr
Write-Host "Tunel iniciado (PID $($tunnel.Id)). Esperando URL publica..."

$url = $null
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Milliseconds 700
    $text = ''
    foreach ($f in @($tunOut, $tunErr)) {
        if (Test-Path $f) { $text += (Get-Content $f -Raw -ErrorAction SilentlyContinue) }
    }
    $m = [regex]::Match($text, 'https://[a-z0-9-]+\.trycloudflare\.com')
    if ($m.Success) { $url = $m.Value.TrimEnd('/') + '/'; break }
}
if (-not $url) { throw 'No se obtuvo la URL del tunel. Revisa los logs en ' + $logDir }

# 4) Esperar a que el tunel responda de verdad. El nombre nuevo tarda unos
# segundos en propagarse; se limpia el cache DNS para no arrastrar un fallo
# negativo de los primeros intentos.
ipconfig /flushdns | Out-Null
$ok = $false
for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Milliseconds 1000
    try {
        $r = Invoke-WebRequest -Uri ($url + 'api/health') -TimeoutSec 8 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
}
if (-not $ok) { throw 'El tunel no respondio; revisa los logs en ' + $logDir }

# 5) Guardar enlace y generar QR local (sin servicios externos).
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
Write-Host "  ENLACE PARA CELULAR: $url"
Write-Host '============================================================'
Write-Host ''
Write-Host 'Abre este enlace en el telefono o escanea assets\qr-movil.png.'
Write-Host 'Certificado publico valido: funciona en Android y iPhone sin avisos.'
Write-Host 'El enlace cambia cada vez que se ejecuta este script; el anterior deja de funcionar.'
Write-Host 'El tunel sigue activo aunque cierres esta ventana.'
try { Start-Process $url } catch { }
