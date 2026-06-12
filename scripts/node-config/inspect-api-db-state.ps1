# inspect-api-db-state.ps1 - Comparar SQLite directo contra API read-only.
# Ejecutar en Lenovo. No modifica BD, red, servicios ni PLC.

param(
    [string]$Root = "C:\alumbrado-gateway",
    [string]$ApiBase = "http://127.0.0.1:8000",
    [int]$Limit = 30
)

$ErrorActionPreference = "Stop"
$py = Join-Path $Root ".venv\Scripts\python.exe"
$pipelineChecks = Join-Path $Root "scripts\node-config\pipeline_checks.py"

function Invoke-AlumbradoPython {
    param(
        [string]$Script,
        [string[]]$Arguments = @()
    )
    $oldPythonPath = $env:PYTHONPATH
    try {
        if ($oldPythonPath) {
            $env:PYTHONPATH = "$Root;$oldPythonPath"
        } else {
            $env:PYTHONPATH = $Root
        }
        & $py $Script @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Python salio con codigo $LASTEXITCODE"
        }
    } finally {
        $env:PYTHONPATH = $oldPythonPath
    }
}

if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    throw "No existe Root: $Root"
}
if (-not (Test-Path -LiteralPath $py -PathType Leaf)) {
    throw "No existe Python venv: $py"
}

Set-Location -LiteralPath $Root

Write-Host "=== Config efectiva desde $Root ==="
Invoke-AlumbradoPython -Script $pipelineChecks -Arguments @("inspect-config")

Write-Host ""
Write-Host "=== Ultimos ciclos en SQLite ==="
Invoke-AlumbradoPython -Script $pipelineChecks -Arguments @("recent-cycles", "--limit", "$Limit")

Write-Host ""
Write-Host "=== API /api/estado ==="
$estado = Invoke-RestMethod -Uri "$ApiBase/api/estado" -TimeoutSec 5
$estado | Select-Object id,timestamp,fins_ok,secciones_status,modfunalu | Format-List

Write-Host "=== API /api/ciclos/{id}/vector_salidas_logicas ==="
$vector = Invoke-RestMethod -Uri "$ApiBase/api/ciclos/$($estado.id)/vector_salidas_logicas" -TimeoutSec 5
Write-Host "source_range=$($vector.source_range) raw_words=$($vector.raw_words.Count) bits=$($vector.bits.Count)"

Write-Host "=== API /api/ciclos/{id}/contexto_plc_raw ==="
$contexto = Invoke-RestMethod -Uri "$ApiBase/api/ciclos/$($estado.id)/contexto_plc_raw" -TimeoutSec 5
Write-Host "ranges=$($contexto.ranges.Count)"

Write-Host "=== API /api/dashboard/resumen secciones ==="
$resumen = Invoke-RestMethod -Uri "$ApiBase/api/dashboard/resumen" -TimeoutSec 5
$resumen.secciones | Format-List

Write-Host "=== API /api/secciones/actual resumen ==="
$seccionesResponse = Invoke-WebRequest -Uri "$ApiBase/api/secciones/actual" -UseBasicParsing -TimeoutSec 5
$secciones = [array]($seccionesResponse.Content | ConvertFrom-Json)
$manual = @($secciones | Where-Object { $_.manual_activo }).Count
$automatico = @($secciones | Where-Object { $_.automatico_calculado }).Count
$interna = @($secciones | Where-Object { $_.salida_interna }).Count
Write-Host "total=$($secciones.Count) manual_activo=$manual automatico_calculado=$automatico salida_interna=$interna"
if ($manual -gt 0) {
    Write-Host "Secciones manual_activo=true:"
    $secciones | Where-Object { $_.manual_activo } | Select-Object seccion_id,timestamp,ciclo_id,manual_activo | Format-Table -AutoSize
}
