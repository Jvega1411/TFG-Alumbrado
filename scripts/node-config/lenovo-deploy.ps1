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

$ErrorActionPreference = "Stop"
$dest = "C:\alumbrado-gateway"
$repo = "https://github.com/Jvega1411/TFG-Alumbrado.git"
# Alternativa SSH (si tienes clave SSH configurada en Lenovo):
# $repo = "git@github.com:Jvega1411/TFG-Alumbrado.git"

if (Test-Path $dest) {
    Write-Host "[SKIP] $dest ya existe. Haciendo git pull en vez de clone."
    Set-Location $dest
    git pull origin main
} else {
    Write-Host "[CLONE] Clonando desde $repo ..."
    git clone $repo $dest
    Set-Location $dest
}

if (-not (Test-Path "$dest\.venv")) {
    Write-Host "[VENV] Creando entorno virtual..."
    python -m venv .venv
} else {
    Write-Host "[SKIP] .venv ya existe."
}

Write-Host "[PIP] Instalando dependencias..."
& "$dest\.venv\Scripts\pip.exe" install --upgrade pip -q
& "$dest\.venv\Scripts\pip.exe" install -r constraints.txt -q

New-Item -ItemType Directory -Force -Path "$dest\data" | Out-Null
New-Item -ItemType Directory -Force -Path "$dest\logs" | Out-Null

Write-Host ""
Write-Host "OK  Repo listo en $dest"
Write-Host ">>> Siguiente: copiar lenovo-env-template.env a .env y editarlo"
Write-Host "    Copy-Item scripts\node-config\lenovo-env-template.env .env"
Write-Host "    notepad .env"
