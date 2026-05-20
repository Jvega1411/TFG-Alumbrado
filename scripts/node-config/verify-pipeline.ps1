# verify-pipeline.ps1 - Verificacion completa del pipeline end-to-end desde Lenovo.
# Ejecutar manualmente en Lenovo. No modifica red, firewall, servicios ni BD.

param(
    [string]$Root = "",
    [string]$MqttHost = "",
    [int]$MqttPort = 1883,
    [string]$ApiUrl = "http://127.0.0.1:8000/",
    [string]$RpiHost = "10.0.0.1",
    [int]$MaxDataAgeSeconds = 420,
    [int]$MaxIngestAgeSeconds = 90,
    [int]$LivenessSampleWaitSeconds = 0,
    [switch]$SkipNetwork
)

$ErrorActionPreference = "Stop"
if (-not $Root) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
$ok = $true
$python = Join-Path $Root ".venv\Scripts\python.exe"

function Check {
    param([string]$Label, [scriptblock]$Test)
    try {
        $result = & $Test
        if ($result) { Write-Host "OK   $Label" }
        else         { Write-Host "FAIL $Label"; $script:ok = $false }
    } catch {
        Write-Host "ERR  $Label - $($_.Exception.Message)"
        $script:ok = $false
    }
}

function Get-AlumbradoPythonProcess {
    param([string]$Pattern)
    Get-CimInstance Win32_Process -Filter "name = 'python.exe' or name = 'pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*$Pattern*" }
}

function Test-TcpListen {
    param([string]$Address, [int]$Port)
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        return [bool]($listeners | Where-Object {
            $_.LocalAddress -eq $Address -or
            $_.LocalAddress -eq "0.0.0.0" -or
            $_.LocalAddress -eq "::" -or
            $_.LocalAddress -eq "::0"
        })
    }
    return [bool](netstat -ano | Select-String ([regex]::Escape("$Address`:$Port")) | Select-String "LISTEN")
}

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
        & $python $tmp.FullName @Arguments
        $script:LastPythonExitCode = $LASTEXITCODE
    } finally {
        $env:PYTHONPATH = $oldPythonPath
        Remove-Item -LiteralPath $tmp.FullName -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "=== Pipeline alumbrado - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="
Write-Host "Root: $Root"
Write-Host ""

Check "Directorio de despliegue existe" {
    Test-Path -LiteralPath $Root -PathType Container
}

Check "Python venv existe" {
    Test-Path -LiteralPath $python -PathType Leaf
}

Check "Configuracion efectiva MQTT/BD valida" {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { return $false }
    $code = @'
from config.settings import Config
Config.validate_mqtt()
Config._validate_db()
print(f"MQTT={Config.MQTT_BROKER_HOST}:{Config.MQTT_BROKER_PORT} topic={Config.MQTT_TOPIC}")
print(f"DB={Config.DB_ESTADOS_URL}")
'@
    $output = Invoke-AlumbradoPython -Code $code
    $output | ForEach-Object { Write-Host "     $_" }
    return $script:LastPythonExitCode -eq 0
}

if (-not $MqttHost) {
    if (Test-Path -LiteralPath $python -PathType Leaf) {
        $code = 'from config.settings import Config; print(Config.MQTT_BROKER_HOST)'
        $mqttOutput = Invoke-AlumbradoPython -Code $code
        if ($mqttOutput) {
            $MqttHost = $mqttOutput.Trim()
        }
    }
}
if (-not $MqttHost) {
    $MqttHost = "10.0.0.2"
}

Check "Mosquitto Running" {
    $svc = Get-Service mosquitto -ErrorAction Stop
    $svc.Status -eq "Running"
}

Check "Mosquitto escucha en ${MqttHost}:${MqttPort}" {
    Test-TcpListen -Address $MqttHost -Port $MqttPort
}

Check "Subscriber Python activo" {
    [bool](Get-AlumbradoPythonProcess -Pattern "subscriber.listener")
}

Check "API Python activa" {
    [bool](Get-AlumbradoPythonProcess -Pattern "main.py")
}

Check "Tarea AlumbradoSubscriber registrada" {
    [bool](Get-ScheduledTask -TaskName "AlumbradoSubscriber" -ErrorAction SilentlyContinue)
}

Check "Tarea AlumbradoAPI registrada" {
    [bool](Get-ScheduledTask -TaskName "AlumbradoAPI" -ErrorAction SilentlyContinue)
}

Check "API responde HTTP" {
    $r = Invoke-WebRequest -Uri $ApiUrl -UseBasicParsing -TimeoutSec 5
    $r.StatusCode -eq 200
}

Check "BD recibe ciclos nuevos y estado legible" {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { return $false }
    $code = @'
import sys
import time
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from config.settings import Config

max_age_seconds = int(sys.argv[1])
max_ingest_age_seconds = int(sys.argv[2])
sample_wait_seconds = int(sys.argv[3])


def parse_ts(raw):
    ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def latest(conn):
    row = conn.execute(text(
        "select id,timestamp,fins_ok,fins_error,secciones_status,secciones_error "
        "from ciclo order by id desc limit 1"
    )).mappings().first()
    if row is None:
        raise SystemExit("tabla ciclo vacia")
    ts = parse_ts(row["timestamp"])
    age = (datetime.now(timezone.utc) - ts).total_seconds()
    return row, ts, age


if sample_wait_seconds <= 0:
    acquisition_wait = int(max(10, round(Config.ACQUISITION_INTERVAL_S * 3)))
    heartbeat_wait = int(round(Config.HEARTBEAT_INTERVAL_S * 1.25))
    sample_wait_seconds = max(acquisition_wait, heartbeat_wait)
    sample_wait_seconds = min(sample_wait_seconds, max_ingest_age_seconds)

engine = create_engine(Config.DB_ESTADOS_URL)
with engine.connect() as conn:
    tables = {r[0] for r in conn.execute(text("select name from sqlite_master where type='table'"))}
    if "ciclo" not in tables:
        raise SystemExit("tabla ciclo no existe")
    count = conn.execute(text("select count(*) from ciclo")).scalar_one()
    if count < 1:
        raise SystemExit("tabla ciclo vacia")

    first, first_ts, first_age = latest(conn)
    print(
        f"sample1 id={first['id']} ts={first['timestamp']} age_s={first_age:.0f} "
        f"wait_s={sample_wait_seconds}"
    )
    if first_age < -120:
        raise SystemExit(f"timestamp futuro en BD: age_s={first_age:.0f}")
    if first_age > max_age_seconds:
        raise SystemExit(f"datos obsoletos: {first_age:.0f}s > {max_age_seconds} s")

    time.sleep(sample_wait_seconds)
    second, second_ts, second_age = latest(conn)
    print(
        f"sample2 id={second['id']} ts={second['timestamp']} age_s={second_age:.0f} "
        f"fins_ok={second['fins_ok']} secciones_status={second['secciones_status']}"
    )
    if second_age < -120:
        raise SystemExit(f"timestamp futuro en BD: age_s={second_age:.0f}")
    if second_age > max_ingest_age_seconds:
        raise SystemExit(
            f"ingesta sin datos frescos: {second_age:.0f}s > {max_ingest_age_seconds} s"
        )
    if int(second["id"]) <= int(first["id"]):
        raise SystemExit(
            f"ingesta no avanza: id inicial={first['id']} id final={second['id']}"
        )
    if second_ts <= first_ts:
        raise SystemExit(
            f"timestamp no avanza: ts inicial={first['timestamp']} ts final={second['timestamp']}"
        )
    if not second["fins_ok"]:
        raise SystemExit(f"ultimo ciclo FINS fallo: {second['fins_error']}")
    if second["secciones_status"] != "ok":
        raise SystemExit(
            f"secciones no ok: {second['secciones_status']} {second['secciones_error']}"
        )
'@
    $output = Invoke-AlumbradoPython -Code $code -Arguments @(
        "$MaxDataAgeSeconds",
        "$MaxIngestAgeSeconds",
        "$LivenessSampleWaitSeconds"
    )
    $output | ForEach-Object { Write-Host "     $_" }
    return $script:LastPythonExitCode -eq 0
}

if ($SkipNetwork) {
    Write-Host "SKIP Enlace RPi ($RpiHost) responde ping - SkipNetwork activo"
} else {
    Check "Enlace RPi ($RpiHost) responde ping" {
        if (Get-Command Test-NetConnection -ErrorAction SilentlyContinue) {
            return (Test-NetConnection -ComputerName $RpiHost -InformationLevel Quiet -WarningAction SilentlyContinue)
        }
        return (ping -n 1 -w 2000 $RpiHost | Select-String "TTL=")
    }
}

Check "AnyDesk servicio activo" {
    $svc = Get-Service -Name "AnyDesk" -ErrorAction SilentlyContinue
    $svc -and $svc.Status -eq "Running"
}

Write-Host ""
if ($ok) {
    Write-Host "PIPELINE OK - todos los checks superados."
    exit 0
}

Write-Host "PIPELINE DEGRADADO - revisar los items marcados FAIL/ERR."
exit 1
