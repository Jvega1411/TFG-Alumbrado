# lenovo-cx-proxyarp-open.ps1 - Add temporary Lenovo OT maintenance IP for CX-One.
# Run manually on the Lenovo as Administrator. Uses ActiveStore only.

param(
    [string]$InterfaceAlias = "Ethernet 2",
    [string]$MaintenanceIP = "192.168.250.221",
    [int]$PrefixLength = 24,
    [string]$LinkIP = "10.0.0.2",
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

$iface = Get-NetIPInterface -AddressFamily IPv4 -InterfaceAlias $InterfaceAlias -ErrorAction Stop |
    Select-Object -First 1

$linkAddress = Get-NetIPAddress -InterfaceAlias $InterfaceAlias -IPAddress $LinkIP -AddressFamily IPv4 -ErrorAction SilentlyContinue
if (-not $linkAddress) {
    throw "$InterfaceAlias does not have expected Lenovo-RPi link IP $LinkIP."
}

$defaultRoutes = @(Get-NetRoute -InterfaceAlias $InterfaceAlias -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue)
if ($defaultRoutes.Count -gt 0) {
    throw "$InterfaceAlias has a default route. Refusing to add OT maintenance IP on a gateway interface."
}

$persistent = @(Get-NetIPAddress -InterfaceAlias $InterfaceAlias -IPAddress $MaintenanceIP -AddressFamily IPv4 -PolicyStore PersistentStore -ErrorAction SilentlyContinue)
if ($persistent.Count -gt 0) {
    if (-not $RemovePersistent) {
        throw "Persistent $MaintenanceIP exists on $InterfaceAlias. Rerun with -RemovePersistent only if this stale maintenance IP should be removed."
    }
    $persistent | Remove-NetIPAddress -Confirm:$false
    Write-Host "OK  Removed stale persistent $MaintenanceIP from $InterfaceAlias"
}

$active = @(Get-NetIPAddress -InterfaceAlias $InterfaceAlias -IPAddress $MaintenanceIP -AddressFamily IPv4 -PolicyStore ActiveStore -ErrorAction SilentlyContinue)
if ($active.Count -gt 1) {
    throw "Multiple active $MaintenanceIP entries exist on $InterfaceAlias. Clean them manually before opening maintenance."
}

if ($active.Count -eq 1) {
    $address = $active[0]
    if ($address.PrefixLength -ne $PrefixLength -or $address.SkipAsSource -ne $false -or $address.AddressState -notin @("Preferred", "Tentative")) {
        throw "Active $MaintenanceIP exists on $InterfaceAlias but does not match expected state: /$PrefixLength, SkipAsSource=False, Preferred/Tentative. Current: /$($address.PrefixLength), SkipAsSource=$($address.SkipAsSource), AddressState=$($address.AddressState)."
    }
    Write-Host "[SKIP] Active maintenance IP already exists: $MaintenanceIP on $InterfaceAlias"
} else {
    New-NetIPAddress `
        -InterfaceAlias $InterfaceAlias `
        -IPAddress $MaintenanceIP `
        -PrefixLength $PrefixLength `
        -SkipAsSource $false `
        -PolicyStore ActiveStore | Out-Null
    Write-Host "OK  Added active-only maintenance IP: $MaintenanceIP/$PrefixLength on $InterfaceAlias"
}

Write-Host ""
Write-Host "Verification:"
Get-NetIPAddress -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 |
    Format-Table InterfaceAlias,IPAddress,PrefixLength,SkipAsSource,AddressState,PolicyStore -AutoSize
Write-Host ""
Get-NetRoute -InterfaceAlias $InterfaceAlias -AddressFamily IPv4 |
    Where-Object { $_.DestinationPrefix -like "192.168.250.*" -or $_.DestinationPrefix -eq "10.0.0.0/30" } |
    Format-Table DestinationPrefix,NextHop,RouteMetric,PolicyStore -AutoSize
Write-Host ""
Test-NetConnection $RpiLinkIP -Port 22
Write-Host ""
Write-Host "Expected CX path: direct EtherNet/IP/FINS TCP through $MaintenanceIP -> 192.168.250.1"
Write-Host "Close with: .\scripts\node-config\lenovo-cx-proxyarp-close.ps1"
