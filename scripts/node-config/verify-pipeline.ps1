# verify-pipeline.ps1 — Verificacion completa del pipeline end-to-end desde Lenovo
# Ejecutar en cualquier momento para diagnosticar el estado del sistema.

$root = "C:\alumbrado-gateway"
$ok   = $true

function Check { param([string]$label, [scriptblock]$test)
    try {
        $result = & $test
        if ($result) { Write-Host "OK  $label" }
        else         { Write-Host "FAIL $label"; $script:ok = $false }
    } catch {
        Write-Host "ERR $label — $_"
        $script:ok = $false
    }
}

Write-Host "=== Pipeline alumbrado — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===`n"

Check "Mosquitto Running" {
    (Get-Service mosquitto -ErrorAction Stop).Status -eq "Running"
}

Check "Mosquitto escucha en 10.0.0.2:1883" {
    netstat -ano | Select-String "10.0.0.2:1883.*LISTENING"
}

Check "Subscriber Python activo" {
    $procs = Get-Process python -ErrorAction SilentlyContinue
    ($procs | Where-Object { $_.CommandLine -like "*subscriber*" }).Count -gt 0
}

Check "API Python activa" {
    $procs = Get-Process python -ErrorAction SilentlyContinue
    ($procs | Where-Object { $_.CommandLine -like "*main.py*" }).Count -gt 0
}

Check "API responde HTTP" {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/" -UseBasicParsing -TimeoutSec 5
    $r.StatusCode -eq 200
}

Check "BD SQLite existe" {
    Test-Path "$root\data\bd_estados.db"
}

Check "BD tiene al menos 1 ciclo" {
    $db = "$root\data\bd_estados.db"
    $count = (& "$root\.venv\Scripts\python.exe" -c @"
import sqlite3
c = sqlite3.connect(r'$db').cursor()
c.execute('SELECT COUNT(*) FROM ciclo')
print(c.fetchone()[0])
"@).Trim()
    [int]$count -gt 0
}

Check "Enlace RPi (10.0.0.1) responde ping" {
    (Test-NetConnection -ComputerName 10.0.0.1 -WarningAction SilentlyContinue).PingSucceeded
}

Check "RustDesk servicio activo" {
    $svc = Get-Service -Name "RustDesk" -ErrorAction SilentlyContinue
    $svc -and $svc.Status -eq "Running"
}

Write-Host ""
if ($ok) { Write-Host "PIPELINE OK — todos los checks superados." }
else      { Write-Host "PIPELINE DEGRADADO — revisar los items marcados FAIL/ERR." }
