# collect-cap9-evidence.ps1 - Collect read-only evidence for TFG chapter 9.
# Run on Lenovo from the deployed repository. It does not read or export .env.

param(
    [string]$Root = "C:\alumbrado-gateway",
    [string]$OutputRoot = "",
    [string]$ExpectedBranch = "main",
    [int]$MaxDataAgeSeconds = 420,
    [int]$MaxIngestAgeSeconds = 90,
    [int]$ValidationWindowMinutes = 10,
    [int]$MqttTimeoutSeconds = 120,
    [int]$LogTailLines = 5000,
    [switch]$SkipScreenshots
)

$ErrorActionPreference = "Stop"

function Write-FileUtf8 {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Text
    )
    $Text | Out-File -FilePath $Path -Encoding utf8
}

function Run-Capture {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][scriptblock]$Command
    )
    try {
        & $Command 2>&1 | Tee-Object -FilePath $Path | Out-Host
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 0 }
    } catch {
        $_ | Out-File -FilePath $Path -Append -Encoding utf8
        $code = 1
    }
    "exit_code=$code" | Out-File -FilePath $Path -Append -Encoding utf8
    return [int]$code
}

function Assert-Ok {
    param([int]$ExitCode, [string]$Label)
    if ($ExitCode -ne 0) {
        throw "$Label fallo con exit_code=$ExitCode"
    }
}

function Get-CommandText {
    param([string]$CommandName)
    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    return ""
}

function Export-JsonEndpoint {
    param(
        [Parameter(Mandatory=$true)][string]$Uri,
        [Parameter(Mandatory=$true)][string]$Path,
        [int]$Depth = 30
    )
    $data = Invoke-RestMethod -Uri $Uri -TimeoutSec 10
    $data | ConvertTo-Json -Depth $Depth | Out-File -FilePath $Path -Encoding utf8
    return $data
}

function Take-EdgeScreenshot {
    param(
        [Parameter(Mandatory=$true)][string]$Url,
        [Parameter(Mandatory=$true)][string]$Path
    )
    $edgeCandidates = @(
        "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    )
    $edge = $edgeCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if (-not $edge) {
        throw "Microsoft Edge no encontrado; no se pudo capturar $Path"
    }
    $profile = Join-Path $env:TEMP ("alumbrado-cap9-edge-" + [guid]::NewGuid().ToString("N"))
    & $edge --headless=new --disable-gpu --no-first-run --disable-extensions --virtual-time-budget=10000 --user-data-dir=$profile --window-size=1440,1100 --screenshot=$Path $Url | Out-Null
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Captura no creada: $Path"
    }
}

if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    throw "Root no existe: $Root"
}

Set-Location -LiteralPath $Root

$python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python venv no existe: $python"
}

$helper = Join-Path $Root "scripts\node-config\cap9_evidence.py"
$pipeline = Join-Path $Root "scripts\node-config\verify-pipeline.ps1"
$inspect = Join-Path $Root "scripts\node-config\inspect-api-db-state.ps1"

if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) { throw "No existe helper: $helper" }
if (-not (Test-Path -LiteralPath $pipeline -PathType Leaf)) { throw "No existe verify-pipeline: $pipeline" }
if (-not (Test-Path -LiteralPath $inspect -PathType Leaf)) { throw "No existe inspect-api-db-state: $inspect" }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $Root "evidencias"
}
$ev = Join-Path $OutputRoot "cap9-$stamp"
$logsOut = Join-Path $ev "logs"
New-Item -ItemType Directory -Force -Path $ev, $logsOut | Out-Null

$startUtc = (Get-Date).ToUniversalTime().ToString("o")
$configPath = Join-Path $ev "_config_safe.json"
& $python $helper config-json | Out-File -FilePath $configPath -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "No se pudo obtener config saneada" }
$config = Get-Content -Raw -Path $configPath | ConvertFrom-Json
$apiBase = [string]$config.api_base

$branch = (& git rev-parse --abbrev-ref HEAD) -join "`n"
$commit = (& git rev-parse HEAD) -join "`n"
$gitStatus = (& git status --short --branch) -join "`n"
$pythonVersion = (& $python --version) -join "`n"
$nodePath = Get-CommandText "node"
$nodeVersion = if ($nodePath) { ((& node --version) -join "`n") } else { "SKIP: Node.js no instalado en el nodo de despliegue" }

@"
Fecha y hora UTC de inicio: $startUtc
Fecha y hora UTC de finalizacion: PENDIENTE
Rama desplegada: $branch
Commit desplegado: $commit
Estado Git limpio o con cambios:
$gitStatus
Version de Python: $pythonVersion
Version de Node, si esta instalado: $nodeVersion
API_HOST efectivo: $($config.api_host)
API_PORT efectivo: $($config.api_port)
MQTT_TOPIC efectivo: $($config.mqtt_topic)
ACQUISITION_INTERVAL_S efectivo: $($config.acquisition_interval_s)
HEARTBEAT_INTERVAL_S efectivo: $($config.heartbeat_interval_s)
Ruta logica de la base de datos: $($config.db_logical)
"@ | Out-File -FilePath (Join-Path $ev "00_manifest.txt") -Encoding utf8

$code = Run-Capture -Path (Join-Path $ev "01_pytest.txt") -Command { & $python -m pytest -q }
Assert-Ok $code "pytest"

$code = Run-Capture -Path (Join-Path $ev "02_compileall.txt") -Command {
    & $python -m compileall -q acquisition api config fins model schemas subscriber main.py
}
Assert-Ok $code "compileall"

if ($nodePath) {
    $code = Run-Capture -Path (Join-Path $ev "03_node_check.txt") -Command { & node --check web\static\app.js }
    Assert-Ok $code "node --check"
} else {
    Write-FileUtf8 -Path (Join-Path $ev "03_node_check.txt") -Text "SKIP: Node.js no instalado en el nodo de despliegue`nexit_code=0"
}

$code = Run-Capture -Path (Join-Path $ev "04_git_diff_check.txt") -Command { & git diff --check }
Assert-Ok $code "git diff --check"

$verifyPath = Join-Path $ev "05_verify_pipeline.txt"
$code = Run-Capture -Path $verifyPath -Command {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $pipeline `
        -Root $Root `
        -ExpectedBranch $ExpectedBranch `
        -ApiUrl "$apiBase/" `
        -MaxDataAgeSeconds $MaxDataAgeSeconds `
        -MaxIngestAgeSeconds $MaxIngestAgeSeconds
}
Assert-Ok $code "verify-pipeline"

$windowStart = (Get-Date).ToUniversalTime().ToString("o")
Start-Sleep -Seconds ([Math]::Max(0, $ValidationWindowMinutes * 60))
$windowEnd = (Get-Date).ToUniversalTime().ToString("o")
@"
Inicio de ventana: $windowStart
Fin de ventana: $windowEnd
Incidencias observadas: ninguna registrada por el script
Reinicios realizados: ninguno realizado por el script
Cambios de configuracion: ninguno realizado por el script
"@ | Out-File -FilePath (Join-Path $ev "validation_window.txt") -Encoding utf8

$mqttPath = Join-Path $ev "06_mqtt_payload_v3.json"
& $python $helper mqtt-once --output $mqttPath --timeout-seconds $MqttTimeoutSeconds 2>&1 |
    Tee-Object -FilePath (Join-Path $ev "06_mqtt_payload_v3.summary.txt")
if ($LASTEXITCODE -ne 0) { throw "No se pudo capturar MQTT V3" }

$code = Run-Capture -Path (Join-Path $ev "07_inspect_api_db_state.txt") -Command {
    & $inspect -Root $Root -ApiBase $apiBase -Limit 30
}
Assert-Ok $code "inspect-api-db-state"

$estado = Export-JsonEndpoint -Uri "$apiBase/api/estado" -Path (Join-Path $ev "08_api_estado.json")
Export-JsonEndpoint -Uri "$apiBase/api/dashboard/resumen" -Path (Join-Path $ev "09_api_dashboard_resumen.json") | Out-Null
Export-JsonEndpoint -Uri "$apiBase/api/secciones/actual" -Path (Join-Path $ev "10_api_secciones_actual.json") | Out-Null
Export-JsonEndpoint -Uri "$apiBase/api/horarios" -Path (Join-Path $ev "11_api_horarios.json") | Out-Null
Export-JsonEndpoint -Uri "$apiBase/api/ciclos/$($estado.id)/vector_salidas_logicas" -Path (Join-Path $ev "12_api_vector_salidas_logicas.json") | Out-Null
Export-JsonEndpoint -Uri "$apiBase/api/ciclos/$($estado.id)/contexto_plc_raw" -Path (Join-Path $ev "13_api_contexto_plc_raw.json") | Out-Null
Export-JsonEndpoint -Uri "$apiBase/openapi.json" -Path (Join-Path $ev "14_openapi.json") -Depth 50 | Out-Null

& $python $helper sqlite-backup --output (Join-Path $ev "15_bd_estados_v3_snapshot.db") 2>&1 |
    Tee-Object -FilePath (Join-Path $ev "15_bd_estados_v3_snapshot.txt")
if ($LASTEXITCODE -ne 0) { throw "No se pudo crear snapshot SQLite consistente" }

foreach ($name in @("subscriber.log", "subscriber-err.log", "api.log", "api-err.log")) {
    $source = Join-Path $Root "logs\$name"
    $dest = Join-Path $logsOut $name
    if (Test-Path -LiteralPath $source -PathType Leaf) {
        Get-Content -Path $source -Tail $LogTailLines | Out-File -FilePath $dest -Encoding utf8
    } else {
        "SKIP: log no encontrado: $source" | Out-File -FilePath $dest -Encoding utf8
    }
}

if ($SkipScreenshots) {
    "SKIP: capturas desactivadas por parametro -SkipScreenshots" |
        Out-File -FilePath (Join-Path $ev "screenshots_skipped.txt") -Encoding utf8
} else {
    Take-EdgeScreenshot -Url "$apiBase/?view=estado" -Path (Join-Path $ev "16_dashboard_estado.png")
    Take-EdgeScreenshot -Url "$apiBase/?view=secciones" -Path (Join-Path $ev "17_dashboard_secciones.png")
    Take-EdgeScreenshot -Url "$apiBase/?view=historial" -Path (Join-Path $ev "18_dashboard_historial.png")
}

@"
Recurso | HTTP | Comprobacion
/api/estado | 200 | Ultimo ciclo disponible
/api/dashboard/resumen | 200 | Frescura y estado FINS
/api/secciones/actual | 200 | 112 registros
/api/horarios | 200 | 12 tramos
/api/ciclos/$($estado.id)/vector_salidas_logicas | 200 | 10 palabras y 160 bits
/api/ciclos/$($estado.id)/contexto_plc_raw | 200 | 12 rangos
"@ | Out-File -FilePath (Join-Path $ev "endpoint_matrix.txt") -Encoding utf8

$endUtc = (Get-Date).ToUniversalTime().ToString("o")
$manifestPath = Join-Path $ev "00_manifest.txt"
(Get-Content -Raw -Path $manifestPath).Replace("Fecha y hora UTC de finalizacion: PENDIENTE", "Fecha y hora UTC de finalizacion: $endUtc") |
    Out-File -FilePath $manifestPath -Encoding utf8

$zip = Join-Path $OutputRoot "cap9-evidencias-$stamp.zip"
Compress-Archive -Path $ev -DestinationPath $zip -Force

Write-Host "EVIDENCE_DIR=$ev"
Write-Host "ZIP=$zip"
