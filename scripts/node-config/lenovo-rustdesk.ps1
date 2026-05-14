# lenovo-rustdesk.ps1 — Descargar e instalar RustDesk (acceso remoto gratuito)
# Ejecutar como administrador.
# RustDesk: open-source, sin licencias, funciona en Windows 11 Home, no requiere port forwarding.

$ErrorActionPreference = "Stop"
$installer = "$env:TEMP\rustdesk-installer.exe"

Write-Host "[GET] Consultando ultima version de RustDesk..."
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/rustdesk/rustdesk/releases/latest"
$asset   = $release.assets | Where-Object { $_.name -like "*x86_64.exe" -and $_.name -notlike "*-sciter*" } | Select-Object -First 1

if (-not $asset) {
    Write-Error "No se encontro el instalador en GitHub Releases. Descarga manualmente desde https://rustdesk.com/es/"
    exit 1
}

Write-Host "[DOWN] Descargando $($asset.name) ($([math]::Round($asset.size/1MB,1)) MB)..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $installer -UseBasicParsing

Write-Host "[INST] Ejecutando instalador..."
Start-Process -FilePath $installer -ArgumentList "--silent-install" -Wait

Remove-Item $installer -Force

Write-Host ""
Write-Host "OK  RustDesk instalado."
Write-Host ""
Write-Host "Pasos post-instalacion:"
Write-Host "  1. Abrir RustDesk desde el escritorio o menu Inicio"
Write-Host "  2. Ir a  [···] -> Seguridad -> Establecer contrasena permanente"
Write-Host "  3. Anotar el ID (ej. 123 456 789) y la contrasena"
Write-Host "  4. Compartir ID + contrasena con quien necesite acceso"
Write-Host "  5. El cliente RustDesk es gratuito en cualquier plataforma: https://rustdesk.com/es/"
