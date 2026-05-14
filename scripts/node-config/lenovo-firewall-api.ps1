# lenovo-firewall-api.ps1 — Permitir acceso al dashboard desde red corporativa
# Ejecutar como administrador.
# Solo necesario si API_HOST=0.0.0.0 y quieres acceder desde otros equipos del edificio.

$ErrorActionPreference = "Stop"

$ruleName = "Alumbrado API FastAPI 8000"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[SKIP] Regla '$ruleName' ya existe."
} else {
    New-NetFirewallRule `
        -DisplayName   $ruleName `
        -Direction     Inbound `
        -Protocol      TCP `
        -LocalPort     8000 `
        -RemoteAddress "192.168.2.0/21" `
        -Action        Allow `
        -Profile       Any `
        -Enabled       True | Out-Null
    Write-Host "OK  Regla creada: TCP 8000 inbound desde 192.168.2.0/21"
}

Write-Host ""
Write-Host "Dashboard accesible desde red corporativa en:"
Write-Host "  http://192.168.2.177:8000"
