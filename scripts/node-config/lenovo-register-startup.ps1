# lenovo-register-startup.ps1 — Registrar subscriber y API como tareas de Windows
# Ejecutar como administrador. Las tareas arrancan al iniciar sesion.

$ErrorActionPreference = "Stop"
$root = "C:\alumbrado-gateway"
$py   = "$root\.venv\Scripts\python.exe"
$user = $env:USERNAME

function Register-AlumbradoTask {
    param(
        [string]$TaskName,
        [string]$Exe,
        [string]$Args,
        [string]$WorkDir,
        [string]$StdOut
    )

    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "[UPDATE] Tarea '$TaskName' ya existe — actualizando."
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    $action  = New-ScheduledTaskAction -Execute $Exe -Argument $Args -WorkingDirectory $WorkDir
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -StartWhenAvailable

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action   $action `
        -Trigger  $trigger `
        -Settings $settings `
        -RunLevel Highest `
        -Force | Out-Null

    Write-Host "OK  Tarea '$TaskName' registrada."
}

New-Item -ItemType Directory -Force -Path "$root\logs" | Out-Null

Register-AlumbradoTask `
    -TaskName "AlumbradoSubscriber" `
    -Exe      $py `
    -Args     "-m subscriber.listener" `
    -WorkDir  $root `
    -StdOut   "$root\logs\subscriber.log"

Register-AlumbradoTask `
    -TaskName "AlumbradoAPI" `
    -Exe      $py `
    -Args     "main.py" `
    -WorkDir  $root `
    -StdOut   "$root\logs\api.log"

Write-Host ""
Write-Host "Tareas registradas. Para arrancar ahora sin reiniciar:"
Write-Host "  Start-ScheduledTask -TaskName 'AlumbradoSubscriber'"
Write-Host "  Start-ScheduledTask -TaskName 'AlumbradoAPI'"
Write-Host ""
Write-Host "Para ver estado:"
Write-Host "  Get-ScheduledTask -TaskName 'Alumbrado*' | Select-Object TaskName, State"
