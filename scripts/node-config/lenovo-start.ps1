# lenovo-start.ps1 — Arrancar subscriber MQTT y FastAPI en background
# Uso: .\scripts\node-config\lenovo-start.ps1
# Los procesos escriben logs en C:\alumbrado-gateway\logs\

$root  = "C:\alumbrado-gateway"
$py    = "$root\.venv\Scripts\python.exe"
$logS  = "$root\logs\subscriber.log"
$logA  = "$root\logs\api.log"

Set-Location $root
New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null

Write-Host "[CHECK] Esquema SQLite V3..."
& $py scripts\node-config\pipeline_checks.py schema-v3
if ($LASTEXITCODE -ne 0) {
    throw "Esquema BD no compatible con V3. Hacer backup/clean break o migracion autorizada antes de arrancar."
}

Write-Host "[START] Subscriber MQTT..."
Start-Process -FilePath $py `
    -ArgumentList "-m subscriber.listener" `
    -WorkingDirectory $root `
    -RedirectStandardOutput $logS `
    -RedirectStandardError  "$root\logs\subscriber-err.log" `
    -WindowStyle Hidden

Start-Sleep -Seconds 2

Write-Host "[START] FastAPI (main.py)..."
Start-Process -FilePath $py `
    -ArgumentList "main.py" `
    -WorkingDirectory $root `
    -RedirectStandardOutput $logA `
    -RedirectStandardError  "$root\logs\api-err.log" `
    -WindowStyle Hidden

Start-Sleep -Seconds 3

Write-Host "[CHECK] Procesos activos:"
Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, CPU, StartTime

Write-Host ""
Write-Host "Logs:"
Write-Host "  Subscriber : $logS"
Write-Host "  API        : $logA"
Write-Host "Dashboard   : http://localhost:8000"
