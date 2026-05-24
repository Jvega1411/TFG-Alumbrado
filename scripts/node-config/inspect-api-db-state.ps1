# inspect-api-db-state.ps1 - Comparar SQLite directo contra API read-only.
# Ejecutar en Lenovo. No modifica BD, red, servicios ni PLC.

param(
    [string]$Root = "C:\alumbrado-gateway",
    [string]$ApiBase = "http://127.0.0.1:8000",
    [int]$Limit = 30
)

$ErrorActionPreference = "Stop"
$py = Join-Path $Root ".venv\Scripts\python.exe"

function Invoke-AlumbradoPython {
    param(
        [string]$Code,
        [string[]]$Arguments = @()
    )
    $tmp = New-TemporaryFile
    $oldPythonPath = $env:PYTHONPATH
    try {
        Set-Content -LiteralPath $tmp.FullName -Value $Code -Encoding utf8
        if ($oldPythonPath) {
            $env:PYTHONPATH = "$Root;$oldPythonPath"
        } else {
            $env:PYTHONPATH = $Root
        }
        & $py $tmp.FullName @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Python salio con codigo $LASTEXITCODE"
        }
    } finally {
        $env:PYTHONPATH = $oldPythonPath
        Remove-Item -LiteralPath $tmp.FullName -Force -ErrorAction SilentlyContinue
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
Invoke-AlumbradoPython -Code @'
from config.settings import Config
print("DB_ESTADOS_URL=", Config.DB_ESTADOS_URL)
print("MQTT_BROKER=", f"{Config.MQTT_BROKER_HOST}:{Config.MQTT_BROKER_PORT}")
print("MQTT_TOPIC=", Config.MQTT_TOPIC)
print("API=", f"{Config.API_HOST}:{Config.API_PORT}")
'@

Write-Host ""
Write-Host "=== Ultimos ciclos en SQLite ==="
Invoke-AlumbradoPython -Code @'
import sys
from sqlalchemy import create_engine, text
from config.settings import Config

limit = int(sys.argv[1])
engine = create_engine(Config.DB_ESTADOS_URL)
with engine.connect() as conn:
    rows = conn.execute(text("""
        select
            c.id,
            c.timestamp,
            c.fins_ok,
            c.secciones_status,
            coalesce(sum(case when s.manual_activo then 1 else 0 end), 0) as manual_activo,
            coalesce(sum(case when s.automatico_calculado then 1 else 0 end), 0) as automatico_calculado,
            coalesce(sum(case when s.salida_interna then 1 else 0 end), 0) as salida_interna,
            coalesce(sum(case when s.salida_wr then 1 else 0 end), 0) as salida_wr
        from ciclo c
        left join seccion_estado s on s.ciclo_id = c.id
        group by c.id, c.timestamp, c.fins_ok, c.secciones_status
        order by c.id desc
        limit :limit
    """), {"limit": limit}).mappings().all()
    print("id | timestamp | fins_ok | sec_status | manual_activo | automatico_calculado | salida_interna | salida_wr")
    for row in rows:
        print(
            f"{row['id']} | {row['timestamp']} | {row['fins_ok']} | "
            f"{row['secciones_status']} | {row['manual_activo']} | "
            f"{row['automatico_calculado']} | {row['salida_interna']} | {row['salida_wr']}"
        )
'@ -Arguments @("$Limit")

Write-Host ""
Write-Host "=== API /api/estado ==="
$estado = Invoke-RestMethod -Uri "$ApiBase/api/estado" -TimeoutSec 5
$estado | Select-Object id,timestamp,fins_ok,secciones_status,modfunalu | Format-List

Write-Host "=== API /api/dashboard/resumen secciones ==="
$resumen = Invoke-RestMethod -Uri "$ApiBase/api/dashboard/resumen" -TimeoutSec 5
$resumen.secciones | Format-List

Write-Host "=== API /api/secciones/actual resumen ==="
$seccionesResponse = Invoke-WebRequest -Uri "$ApiBase/api/secciones/actual" -UseBasicParsing -TimeoutSec 5
$secciones = [array]($seccionesResponse.Content | ConvertFrom-Json)
$manual = @($secciones | Where-Object { $_.manual_activo }).Count
$automatico = @($secciones | Where-Object { $_.automatico_calculado }).Count
$interna = @($secciones | Where-Object { $_.salida_interna }).Count
$wr = @($secciones | Where-Object { $_.salida_wr }).Count
Write-Host "total=$($secciones.Count) manual_activo=$manual automatico_calculado=$automatico salida_interna=$interna salida_wr=$wr"
if ($manual -gt 0) {
    Write-Host "Secciones manual_activo=true:"
    $secciones | Where-Object { $_.manual_activo } | Select-Object seccion_id,timestamp,ciclo_id,manual_activo | Format-Table -AutoSize
}
