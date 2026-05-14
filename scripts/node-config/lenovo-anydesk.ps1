# lenovo-anydesk.ps1 — Descargar e instalar AnyDesk (acceso remoto)
# Ejecutar como administrador.
# AnyDesk: gratuito para uso personal/no comercial (TFG incluido), sin port forwarding,
# recomendado por el departamento. URL de descarga estable (siempre ultima version).

$ErrorActionPreference = "Stop"
$installer = "$env:TEMP\AnyDeskSetup.exe"
$anydesk   = "C:\Program Files (x86)\AnyDesk\AnyDesk.exe"

Write-Host "[DOWN] Descargando AnyDesk..."
Invoke-WebRequest -Uri "https://download.anydesk.com/AnyDesk.exe" -OutFile $installer -UseBasicParsing

Write-Host "[INST] Instalando en silencio..."
Start-Process -FilePath $installer `
    -ArgumentList "--install `"C:\Program Files (x86)\AnyDesk`" --silent --create-desktop-icon" `
    -Wait

Remove-Item $installer -Force -ErrorAction SilentlyContinue

# Esperar a que el servicio arranque
$timeout = 15
$elapsed = 0
while ($elapsed -lt $timeout) {
    $svc = Get-Service -Name "AnyDesk" -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -eq "Running") { break }
    Start-Sleep -Seconds 1; $elapsed++
}

Write-Host ""
Write-Host "OK  AnyDesk instalado."
Write-Host ""

# Mostrar el ID asignado
if (Test-Path $anydesk) {
    $id = & $anydesk --get-id 2>$null
    if ($id) { Write-Host "ID AnyDesk de este equipo: $id" }
}

Write-Host ""
Write-Host "Pasos post-instalacion:"
Write-Host "  1. Abrir AnyDesk desde el escritorio"
Write-Host "  2. Ir a  Ajustes -> Seguridad -> Habilitar acceso no supervisado"
Write-Host "  3. Establecer una contrasena de acceso desatendido"
Write-Host "  4. Anotar el ID (mostrado arriba o en la pantalla principal) y la contrasena"
Write-Host "  5. Descargar el cliente AnyDesk en el equipo remoto (gratis) y conectar con ese ID"
Write-Host "     Descarga cliente: https://anydesk.com/es/downloads"
