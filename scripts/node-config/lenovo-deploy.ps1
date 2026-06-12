# lenovo-deploy.ps1 — Clonar repo y preparar entorno Python en Lenovo
# Ejecutar como administrador desde PowerShell
# Prerequisito: git y python 3.11+ instalados y en PATH
#
# Autenticacion GitHub (HTTPS — recomendado en Windows corporativo):
#   1. Crear PAT en github.com -> Settings -> Developer Settings ->
#      Personal Access Tokens -> Tokens (classic) -> Generate new token
#      Scope minimo: [x] repo
#   2. Al ejecutar git clone, Windows pedira usuario y contrasena:
#      Usuario: Jvega1411
#      Contrasena: <pegar el PAT>
#      Windows Credential Manager lo guarda para futuros pulls.

param(
    [string]$Branch = "main",
    [string]$ExpectedCommit = ""
)

$ErrorActionPreference = "Stop"
$dest = "C:\alumbrado-gateway"
$repo = "https://github.com/Jvega1411/TFG-Alumbrado.git"
# Alternativa SSH (si tienes clave SSH configurada en Lenovo):
# $repo = "git@github.com:Jvega1411/TFG-Alumbrado.git"

function Invoke-Git {
    param([Parameter(Mandatory=$true)][string[]]$Arguments)
    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Get-GitOutput {
    param([Parameter(Mandatory=$true)][string[]]$Arguments)
    $output = & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
    return ($output -join "`n").Trim()
}

function Invoke-Native {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [string[]]$Arguments = @()
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

if (Test-Path $dest) {
    Write-Host "[GIT] $dest ya existe. Actualizando branch $Branch."
    Set-Location $dest
    Invoke-Git -Arguments @("fetch", "origin")
    Invoke-Git -Arguments @("checkout", $Branch)
    Invoke-Git -Arguments @("pull", "--ff-only", "origin", $Branch)
} else {
    Write-Host "[CLONE] Clonando branch $Branch desde $repo ..."
    Invoke-Git -Arguments @("clone", "--branch", $Branch, $repo, $dest)
    Set-Location $dest
}

$deployedBranch = Get-GitOutput -Arguments @("rev-parse", "--abbrev-ref", "HEAD")
$deployedCommit = Get-GitOutput -Arguments @("rev-parse", "HEAD")
Write-Host "[GIT] Branch desplegado: $deployedBranch"
Write-Host "[GIT] Commit desplegado: $deployedCommit"

if ($ExpectedCommit -and $deployedCommit.ToLowerInvariant() -ne $ExpectedCommit.Trim().ToLowerInvariant()) {
    throw "Commit desplegado no coincide. Esperado: $ExpectedCommit. Actual: $deployedCommit"
}

if (-not (Test-Path "$dest\.venv")) {
    Write-Host "[VENV] Creando entorno virtual..."
    Invoke-Native -FilePath "python" -Arguments @("-m", "venv", ".venv")
} else {
    Write-Host "[SKIP] .venv ya existe."
}

$pip = "$dest\.venv\Scripts\pip.exe"
if (-not (Test-Path -LiteralPath $pip -PathType Leaf)) {
    throw "No existe pip en el entorno virtual esperado: $pip"
}

Write-Host "[PIP] Instalando dependencias..."
Invoke-Native -FilePath $pip -Arguments @("install", "--upgrade", "pip", "-q")
Invoke-Native -FilePath $pip -Arguments @("install", "-r", "constraints.txt", "-q")

New-Item -ItemType Directory -Force -Path "$dest\data" | Out-Null
New-Item -ItemType Directory -Force -Path "$dest\logs" | Out-Null

$dbPath = "$dest\data\bd_estados.db"
if (Test-Path -LiteralPath $dbPath) {
    Write-Warning "Existe $dbPath. V3 no migra SQLite V2 con create_all(). Antes de arrancar, hacer backup/clean break o una migracion autorizada."
}

Write-Host ""
Write-Host "OK  Repo listo en $dest"
Write-Host ">>> Siguiente: copiar lenovo-env-template.env a .env y editarlo"
Write-Host "    Copy-Item scripts\node-config\lenovo-env-template.env .env"
Write-Host "    notepad .env"
