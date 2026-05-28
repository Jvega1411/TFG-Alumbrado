# lenovo-cx-proxyarp-close.ps1 - Remove temporary Lenovo OT maintenance IP.
# Run manually on the Lenovo as Administrator.

param(
    [string]$InterfaceAlias = "Ethernet 2",
    [string]$MaintenanceIP = "192.168.250.221",
    [string]$RpiLinkIP = "10.0.0.1",
    [switch]$RemovePersistent
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
        throw "Run PowerShell as Administrator."
    }
}

Assert-Admin

$removed = 0
$activeAddresses = @(Get-NetIPAddress -InterfaceAlias $InterfaceAlias -IPAddress $MaintenanceIP -AddressFamily IPv4 -PolicyStore ActiveStore -ErrorAction SilentlyContinue)
if ($activeAddresses.Count -eq 0) {
    Write-Host "[SKIP] No $MaintenanceIP in ActiveStore"
} else {
    $activeAddresses | Remove-NetIPAddress -Confirm:$false
    $removed += $activeAddresses.Count
    Write-Host "OK  Removed $MaintenanceIP from ActiveStore"
}

$persistentAddresses = @(Get-NetIPAddress -InterfaceAlias $InterfaceAlias -IPAddress $MaintenanceIP -AddressFamily IPv4 -PolicyStore PersistentStore -ErrorAction SilentlyContinue)
if ($persistentAddresses.Count -eq 0) {
    Write-Host "[SKIP] No $MaintenanceIP in PersistentStore"
} elseif ($RemovePersistent) {
    $persistentAddresses | Remove-NetIPAddress -Confirm:$false
    $removed += $persistentAddresses.Count
    Write-Host "OK  Removed $MaintenanceIP from PersistentStore"
} else {
    Write-Warning "Persistent $MaintenanceIP still exists. Rerun with -RemovePersistent only if this stale maintenance IP should be removed."
}

if ($removed -eq 0) {
    Write-Host "[SKIP] Maintenance IP was already absent: $MaintenanceIP"
}

Write-Host ""
Write-Host "Remaining IPv4 addresses on ${InterfaceAlias}:"
Get-NetIPAddress -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 |
    Format-Table InterfaceAlias,IPAddress,PrefixLength,AddressState,PolicyStore -AutoSize
Write-Host ""
Write-Host "Routes still related to 192.168.250 on ${InterfaceAlias}:"
Get-NetRoute -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.DestinationPrefix -like "192.168.250.*" } |
    Format-Table DestinationPrefix,NextHop,RouteMetric,PolicyStore -AutoSize
Write-Host ""
Test-NetConnection $RpiLinkIP -Port 22
