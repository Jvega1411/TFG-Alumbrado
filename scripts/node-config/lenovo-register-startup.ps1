# lenovo-register-startup.ps1 - Registrar subscriber y API como tareas de Windows.
# Ejecutar como administrador. Las tareas arrancan al iniciar sesion.

$ErrorActionPreference = "Stop"
$root = "C:\alumbrado-gateway"
$user = $env:USERNAME
$ps = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$runner = "$root\scripts\node-config\lenovo-task-runner.ps1"

function Register-AlumbradoTask {
    param(
        [string]$TaskName,
        [string]$Role,
        [string]$WorkDir,
        [string]$StdOut,
        [string]$StdErr
    )

    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "[UPDATE] Tarea '$TaskName' ya existe; actualizando."
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    $taskArgs = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -Role {1}' -f $runner, $Role
    $action = New-ScheduledTaskAction -Execute $ps -Argument $taskArgs -WorkingDirectory $WorkDir
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -StartWhenAvailable

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -RunLevel Highest `
        -Force | Out-Null

    Write-Host "OK  Tarea '$TaskName' registrada."
    Write-Host "    stdout: $StdOut"
    Write-Host "    stderr: $StdErr"
}

New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null

Register-AlumbradoTask `
    -TaskName "AlumbradoSubscriber" `
    -Role "subscriber" `
    -WorkDir $root `
    -StdOut "$root\logs\subscriber.log" `
    -StdErr "$root\logs\subscriber-err.log"

Register-AlumbradoTask `
    -TaskName "AlumbradoAPI" `
    -Role "api" `
    -WorkDir $root `
    -StdOut "$root\logs\api.log" `
    -StdErr "$root\logs\api-err.log"

Write-Host ""
Write-Host "Tareas registradas. Para arrancar ahora sin reiniciar:"
Write-Host "  Start-ScheduledTask -TaskName 'AlumbradoSubscriber'"
Write-Host "  Start-ScheduledTask -TaskName 'AlumbradoAPI'"
Write-Host ""
Write-Host "Para ver estado:"
Write-Host "  Get-ScheduledTask -TaskName 'Alumbrado*' | Select-Object TaskName, State"
Write-Host "  Get-ScheduledTaskInfo -TaskName 'AlumbradoSubscriber'"
Write-Host "  Get-ScheduledTaskInfo -TaskName 'AlumbradoAPI'"
