# final-tfg-export-and-stop.ps1 - Final TFG evidence export and shutdown helper.
# Run on Lenovo from C:\alumbrado-gateway. It does not read .env or real secrets.

param(
    [string]$Root = "C:\alumbrado-gateway",
    [string]$ApiUrl = "http://127.0.0.1:8010/",
    [switch]$SkipScreenshots,
    [switch]$SkipStop
)

$ErrorActionPreference = "Continue"

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "=== $Title ==="
}

function Save-CommandOutput {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][scriptblock]$Command
    )
    try {
        & $Command 2>&1 | Out-File -FilePath $Path -Encoding utf8
    } catch {
        "ERROR: $($_.Exception.Message)" | Out-File -FilePath $Path -Encoding utf8
    }
}

function Copy-IfExists {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination,
        [switch]$Recurse
    )
    if (Test-Path -LiteralPath $Source) {
        Copy-Item -LiteralPath $Source -Destination $Destination -Force -Recurse:$Recurse -ErrorAction Continue
    }
}

if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    throw "Root not found: $Root"
}

Set-Location -LiteralPath $Root

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$exportRoot = Join-Path $Root "exports"
$export = Join-Path $exportRoot "final-$ts"
New-Item -ItemType Directory -Force -Path $export | Out-Null

$transcript = Join-Path $export "run_transcript.txt"
try {
    Start-Transcript -Path $transcript -Force | Out-Null
} catch {
    Write-Host "WARN transcript not available: $($_.Exception.Message)"
}

Write-Section "Export root"
Write-Host $export

Write-Section "Git evidence"
Save-CommandOutput "$export\git_branch.txt" { git rev-parse --abbrev-ref HEAD }
Save-CommandOutput "$export\git_commit.txt" { git rev-parse HEAD }
Save-CommandOutput "$export\git_log.txt" { git log --oneline -8 }
Save-CommandOutput "$export\git_status.txt" { git status --short --branch }

Write-Section "Runtime evidence before stop"
Save-CommandOutput "$export\python_processes_before.txt" {
    Get-CimInstance Win32_Process -Filter "name = 'python.exe' or name = 'pythonw.exe'" |
        Select-Object ProcessId, CommandLine
}
Save-CommandOutput "$export\tasks_state_before.txt" {
    Get-ScheduledTask -TaskName "AlumbradoSubscriber","AlumbradoAPI" -ErrorAction SilentlyContinue |
        Select-Object TaskName, State
}
Save-CommandOutput "$export\tasks_info_before.txt" {
    Get-ScheduledTaskInfo -TaskName "AlumbradoSubscriber","AlumbradoAPI" -ErrorAction SilentlyContinue |
        Select-Object TaskName, LastRunTime, LastTaskResult, NextRunTime, NumberOfMissedRuns
}
Save-CommandOutput "$export\listening_ports_before.txt" {
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Select-Object LocalAddress, LocalPort, State, OwningProcess
}

Write-Section "Database and logs export"
Copy-IfExists "$Root\data\bd_estados.db" "$export\bd_estados_v3.db"
Copy-IfExists "$Root\data\bd_estados.db-wal" "$export\bd_estados_v3.db-wal"
Copy-IfExists "$Root\data\bd_estados.db-shm" "$export\bd_estados_v3.db-shm"
Copy-IfExists "$Root\data\backup" "$export\backup" -Recurse
Copy-IfExists "$Root\data\bd_estados - copia.db" "$export\bd_estados_copia_previa.db"
Copy-IfExists "$Root\logs" "$export\logs" -Recurse

Save-CommandOutput "$export\data_listing.txt" {
    Get-ChildItem "$Root\data" -Recurse -ErrorAction SilentlyContinue |
        Select-Object FullName, Length, LastWriteTime
}

Write-Section "HTTP evidence"
Save-CommandOutput "$export\curl_root.txt" {
    curl.exe -v --max-time 5 $ApiUrl
}
$estadoUrl = ($ApiUrl.TrimEnd("/") + "/api/estado")
Save-CommandOutput "$export\curl_estado.txt" {
    curl.exe -v --max-time 5 $estadoUrl
}

if (-not $SkipScreenshots) {
    Write-Section "Screenshots"
    $edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if (Test-Path -LiteralPath $edge -PathType Leaf) {
        $edgeProfile = Join-Path $env:TEMP "alumbrado-edge-final-$ts"
        & $edge --headless=new --disable-gpu --no-first-run --disable-extensions --user-data-dir=$edgeProfile --window-size=1440,1100 --screenshot="$export\dashboard_v3_desktop.png" $ApiUrl
        & $edge --headless=new --disable-gpu --no-first-run --disable-extensions --user-data-dir=$edgeProfile --window-size=390,844 --screenshot="$export\dashboard_v3_mobile.png" $ApiUrl
    } else {
        "Edge not found at $edge" | Out-File "$export\screenshots_skipped.txt" -Encoding utf8
    }
}

Write-Section "Final note"
@"
Estado final TFG - $ts

Commit:
$(git rev-parse HEAD 2>$null)

Resumen:
- V3 consolidado en main.
- Clean break SQLite ejecutado antes de este cierre.
- BD V2 respaldada en data\backup\v2-* si existe.
- BD V3 activa exportada como bd_estados_v3.db si existe.
- API web probada contra $ApiUrl durante la exportacion.
- Sistema read-only; este script no ejecuta escrituras PLC.

Limitaciones:
- Si /api/estado devuelve 404 Sin datos, la API esta viva pero la BD V3 no tiene ciclos.
- Si el puerto operativo final no es 8000, queda documentado por curl/listening_ports.
"@ | Out-File "$export\notes_final.txt" -Encoding utf8

if (-not $SkipStop) {
    Write-Section "Stop tasks and gateway Python processes"
    Stop-ScheduledTask -TaskName "AlumbradoSubscriber" -ErrorAction SilentlyContinue
    Stop-ScheduledTask -TaskName "AlumbradoAPI" -ErrorAction SilentlyContinue

    Get-CimInstance Win32_Process -Filter "name = 'python.exe' or name = 'pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and (
                $_.CommandLine -like "*alumbrado-gateway*" -or
                $_.CommandLine -like "*subscriber.listener*" -or
                $_.CommandLine -like "*main.py*"
            )
        } |
        ForEach-Object {
            try {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
                Write-Host "Stopped PID $($_.ProcessId)"
            } catch {
                Write-Host "WARN could not stop PID $($_.ProcessId): $($_.Exception.Message)"
            }
        }
}

Write-Section "Runtime evidence after stop"
Save-CommandOutput "$export\python_processes_after.txt" {
    Get-CimInstance Win32_Process -Filter "name = 'python.exe' or name = 'pythonw.exe'" |
        Select-Object ProcessId, CommandLine
}
Save-CommandOutput "$export\tasks_state_after.txt" {
    Get-ScheduledTask -TaskName "AlumbradoSubscriber","AlumbradoAPI" -ErrorAction SilentlyContinue |
        Select-Object TaskName, State
}
Save-CommandOutput "$export\export_listing.txt" {
    Get-ChildItem $export -Recurse -ErrorAction SilentlyContinue |
        Select-Object FullName, Length, LastWriteTime
}

try {
    Stop-Transcript | Out-Null
} catch {}

Write-Host ""
Write-Host "FINAL_EXPORT=$export"
