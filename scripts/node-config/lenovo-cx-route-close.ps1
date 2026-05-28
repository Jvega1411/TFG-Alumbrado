# lenovo-cx-route-close.ps1 - Close LEGACY CX Programmer NAT diagnostic route.
# Ejecutar manualmente en Lenovo como administrador.

param(
    [string]$PlcPrefix = "192.168.250.0/24",
    [string]$RpiGateway = "10.0.0.1"
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
        throw "Ejecutar PowerShell como administrador."
    }
}

Assert-Admin

$routes = @(Get-NetRoute -DestinationPrefix $PlcPrefix -NextHop $RpiGateway -ErrorAction SilentlyContinue)
if ($routes.Count -eq 0) {
    Write-Host "[SKIP] No existe ruta temporal: $PlcPrefix via $RpiGateway"
} else {
    $routes | Remove-NetRoute -Confirm:$false
    Write-Host "OK  Ruta temporal eliminada: $PlcPrefix via $RpiGateway"
}

Write-Host ""
Write-Host "Rutas restantes hacia ${PlcPrefix}:"
Get-NetRoute -DestinationPrefix $PlcPrefix -ErrorAction SilentlyContinue | Format-Table -AutoSize
