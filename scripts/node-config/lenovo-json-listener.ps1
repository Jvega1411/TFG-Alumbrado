# lenovo-json-listener.ps1 - Ver JSON MQTT recibido desde la RPi en consola.
# Ejecutar en Lenovo desde la raiz del repo. No escribe en BD ni modifica red.

param(
    [string]$Root = "C:\alumbrado-gateway"
)

$ErrorActionPreference = "Stop"
$py = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $py -PathType Leaf)) {
    throw "No existe Python venv: $py"
}

Set-Location -LiteralPath $Root
Write-Host "Escuchando JSON MQTT. Cerrar con Ctrl+C."
Write-Host ""
& $py -m subscriber.json_listener
