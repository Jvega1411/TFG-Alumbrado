# lenovo-task-runner.ps1 - Wrapper de Task Scheduler con logs stdout/stderr.

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("subscriber", "api")]
    [string]$Role
)

$ErrorActionPreference = "Stop"
$root = "C:\alumbrado-gateway"
$py = "$root\.venv\Scripts\python.exe"
$logs = "$root\logs"

New-Item -ItemType Directory -Force -Path $logs | Out-Null
Set-Location -LiteralPath $root

$schemaCheck = "$root\scripts\node-config\pipeline_checks.py"
& $py $schemaCheck schema-v3
if ($LASTEXITCODE -ne 0) {
    throw "Esquema BD no compatible con V3. Hacer backup/clean break o migracion autorizada antes de arrancar."
}

switch ($Role) {
    "subscriber" {
        $name = "AlumbradoSubscriber"
        $stdout = "$logs\subscriber.log"
        $stderr = "$logs\subscriber-err.log"
        $pythonArgs = @("-m", "subscriber.listener")
    }
    "api" {
        $name = "AlumbradoAPI"
        $stdout = "$logs\api.log"
        $stderr = "$logs\api-err.log"
        $pythonArgs = @("main.py")
    }
}

"===== START $name $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') =====" | Out-File -FilePath $stdout -Append -Encoding utf8
$previousErrorActionPreference = $ErrorActionPreference
try {
    # Uvicorn writes normal INFO logs to stderr. In Windows PowerShell with
    # ErrorActionPreference=Stop, native stderr is promoted to NativeCommandError.
    $ErrorActionPreference = "Continue"
    & $py @pythonArgs 1>> $stdout 2>> $stderr
    $exitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
"===== EXIT $name $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') code $exitCode =====" | Out-File -FilePath $stdout -Append -Encoding utf8
exit $exitCode
