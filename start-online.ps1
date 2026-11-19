# HorizonView · enlace publico FIJO, gratis y sin interstitial.
# Usa la IPv6 publica del equipo + dns gratuito sslip.io + Caddy con CA local confiable.
# No requiere cuenta, token ni servicios en la nube. El enlace sigue activo mientras el equipo este encendido.

$ErrorActionPreference = 'Stop'
$app = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $env:TEMP 'horizonview_online'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# 1) IPv6 global estable del equipo (prefijo /64 anunciado por el router).
$ip = Get-NetIPAddress -AddressFamily IPv6 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notlike 'fe80*' -and
        $_.IPAddress -ne '::1' -and
        $_.PrefixLength -eq 64 -and
        $_.PrefixOrigin -eq 'RouterAdvertisement'
    } | Sort-Object SuffixOrigin -Descending | Select-Object -First 1
if (-not $ip) { throw 'No hay una IPv6 publica global disponible.' }
$ipv6 = $ip.IPAddress

# sslip.io: doble dos puntos -> '--', resto de ':' -> '-'
$dashed = $ipv6 -replace '::', '--' -replace ':', '-'
$hostName = "horizonviewnjtp.$dashed.sslip.io"
$url = "https://$hostName/"
Write-Host "IPv6 publica detectada: $ipv6"

# 2) Servidor local de la aplicacion.
$listen = Get-NetTCPConnection -LocalPort 8770 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listen) {
    Write-Host "Servidor local ya activo (PID $($listen.OwningProcess))."
} else {
    $py = Get-Command python -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
    if (-not $py) { throw 'No se encontro Python 3.' }
    if ($py.Name -eq 'py.exe') {
        $proc = Start-Process -FilePath 'py' -ArgumentList @('-3', 'src/server.py') -WorkingDirectory $app -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'server.out.log') -RedirectStandardError (Join-Path $logDir 'server.err.log')
    } else {
        $proc = Start-Process -FilePath 'python' -ArgumentList 'src/server.py' -WorkingDirectory $app -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'server.out.log') -RedirectStandardError (Join-Path $logDir 'server.err.log')
    }
    Write-Host "Servidor local iniciado (PID $($proc.Id))."
    Start-Sleep -Seconds 2
}

# 3) Configuracion del proxy HTTPS con nombre fijo.
$caddyfile = @"
# Generado automaticamente por start-online.ps1
$hostName {
    tls internal
    encode gzip
    reverse_proxy 127.0.0.1:8770
}
"@
Set-Content -Path (Join-Path $app 'Caddyfile') -Value $caddyfile -Encoding UTF8

# 4) Caddy: reiniciar solo el proceso de este proyecto.
Get-CimInstance Win32_Process -Filter "Name = 'caddy.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'HorizonView' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
$caddyExe = Join-Path $app 'tools\caddy.exe'
if (-not (Test-Path $caddyExe)) { throw 'Falta tools\caddy.exe.' }
$caddy = Start-Process -FilePath $caddyExe -ArgumentList @('run', '--config', 'Caddyfile', '--adapter', 'caddyfile') -WorkingDirectory $app -PassThru -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'caddy.out.log') -RedirectStandardError (Join-Path $logDir 'caddy.err.log')
Write-Host "Proxy HTTPS iniciado (PID $($caddy.Id))."

# 5) Confiar en la CA local de Caddy para este usuario (sin pedir admin).
$rootCa = Join-Path $env:APPDATA 'Caddy\pki\authorities\local\root.crt'
if (Test-Path $rootCa) {
    $trusted = Get-ChildItem Cert:\CurrentUser\Root -ErrorAction SilentlyContinue | Where-Object { $_.Subject -match 'Caddy Local Authority' }
    if (-not $trusted) {
        certutil -user -addstore Root "$rootCa" | Out-Null
        Write-Host 'Certificado raiz local instalado en el usuario.'
    }
}

# 6) Comprobar y guardar el enlace fijo.
$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 700
    try {
        $r = Invoke-WebRequest -Uri ($url + 'api/health') -TimeoutSec 5 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
}
if (-not $ok) { throw 'El enlace fijo no respondio; revisa los logs en ' + $logDir }

$urlFile = Join-Path $app 'URL_Online.txt'
Set-Content -Path $urlFile -Value $url -Encoding UTF8
Write-Host ''
Write-Host '============================================================'
Write-Host "  ENLACE FIJO: $url"
Write-Host '============================================================'
Write-Host ''
Write-Host "Guardado en $urlFile"
Write-Host 'Gratis, sin cuenta y sin interstitial. El certificado es de una CA local confiable en este equipo.'
Write-Host 'Sigue disponible mientras el equipo este encendido. Puedes cerrar esta ventana.'
try { Start-Process $url } catch { }
