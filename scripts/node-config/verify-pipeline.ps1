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
$pipelineChecks = Join-Path $Root "scripts\node-config\pipeline_checks.py"

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
        & $python $Script @Arguments
        $script:LastPythonExitCode = $LASTEXITCODE
    } finally {
        $env:PYTHONPATH = $oldPythonPath
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
    $output = Invoke-AlumbradoPython -Script $pipelineChecks -Arguments @("effective-config")
    $output | ForEach-Object { Write-Host "     $_" }
    return $script:LastPythonExitCode -eq 0
}

if (-not $MqttHost) {
    if (Test-Path -LiteralPath $python -PathType Leaf) {
        $mqttOutput = Invoke-AlumbradoPython -Script $pipelineChecks -Arguments @("mqtt-broker-host")
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
    $output = Invoke-AlumbradoPython -Script $pipelineChecks -Arguments @(
        "db-liveness",
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
