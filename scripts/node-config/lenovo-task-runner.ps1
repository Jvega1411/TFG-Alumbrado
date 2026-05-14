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
& $py @pythonArgs 1>> $stdout 2>> $stderr
$exitCode = $LASTEXITCODE
"===== EXIT $name $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') code $exitCode =====" | Out-File -FilePath $stdout -Append -Encoding utf8
exit $exitCode
