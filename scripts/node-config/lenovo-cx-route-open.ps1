# lenovo-cx-route-open.ps1 - Ruta temporal Lenovo -> red PLC para CX Programmer.
# Ejecutar manualmente en Lenovo como administrador. No usa -Persistent.

param(
    [string]$PlcPrefix = "192.168.250.0/24",
    [string]$RpiGateway = "10.0.0.1",
    [int]$RouteMetric = 5,
    [string]$InterfaceAlias = ""
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

$routeParams = @{
    DestinationPrefix = $PlcPrefix
    NextHop = $RpiGateway
    RouteMetric = $RouteMetric
    PolicyStore = "ActiveStore"
}

if ($InterfaceAlias) {
    $iface = Get-NetIPInterface -AddressFamily IPv4 -InterfaceAlias $InterfaceAlias -ErrorAction Stop |
        Select-Object -First 1
    $routeParams.InterfaceIndex = $iface.InterfaceIndex
} else {
    $gatewayRoute = Find-NetRoute -RemoteIPAddress $RpiGateway -ErrorAction Stop |
        Select-Object -First 1
    if (-not $gatewayRoute -or -not $gatewayRoute.InterfaceIndex) {
        throw "No se pudo resolver la interfaz hacia $RpiGateway. Repetir con -InterfaceAlias."
    }
    $routeParams.InterfaceIndex = $gatewayRoute.InterfaceIndex
}

$existing = Get-NetRoute -DestinationPrefix $PlcPrefix -NextHop $RpiGateway -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[SKIP] Ruta ya existe: $PlcPrefix via $RpiGateway"
} else {
    New-NetRoute @routeParams | Out-Null
    Write-Host "OK  Ruta temporal creada: $PlcPrefix via $RpiGateway ifIndex $($routeParams.InterfaceIndex)"
}

Write-Host ""
Write-Host "Verificacion local de ruta:"
Get-NetRoute -DestinationPrefix $PlcPrefix | Format-Table -AutoSize
Write-Host ""
Write-Host "Cerrar al terminar:"
Write-Host "  .\scripts\node-config\lenovo-cx-route-close.ps1"
