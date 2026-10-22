# Prepara esta computadora para trabajar en el proyecto compartido.
# Se puede ejecutar las veces que haga falta: lo que ya está listo, lo salta.
#
# Uso (desde la carpeta del proyecto):  scripts\unirse.cmd
# o directo en PowerShell:              powershell -ExecutionPolicy Bypass -File scripts\unirse.ps1

param(
    [ValidateSet("", "codex", "antigravity", "claude")]
    [string]$Agente = ""
)

$ErrorActionPreference = "Stop"
$Repo = "DanteRojas-stpy/proyecto-compartido"
$Raiz = Split-Path -Parent $PSScriptRoot

function Paso($texto) { Write-Host "`n==> $texto" -ForegroundColor Cyan }
function Ok($texto)   { Write-Host "    OK  $texto" -ForegroundColor Green }
function Aviso($texto){ Write-Host "    !!  $texto" -ForegroundColor Yellow }

function Actualizar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

function Existe($comando) { [bool](Get-Command $comando -ErrorAction SilentlyContinue) }

function Instalar-Winget($id, $comando) {
    if (Existe $comando) { Ok "$comando ya está instalado"; return }
    Write-Host "    Instalando $id ..."
    winget install --id $id -e --source winget --accept-package-agreements --accept-source-agreements --silent
    Actualizar-Path
    if (Existe $comando) { Ok "$comando instalado" } else { throw "No se pudo instalar $id. Cierra la terminal, ábrela de nuevo y vuelve a ejecutar este script." }
}

Actualizar-Path

# 1. Herramientas básicas
Paso "Revisando Git y GitHub CLI"
Instalar-Winget "Git.Git" "git"
Instalar-Winget "GitHub.cli" "gh"

# 2. Sesión de GitHub (la autoriza la persona en el navegador)
Paso "Revisando sesión de GitHub"
gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
    Aviso "Se abrirá el navegador: pega el código que aparece aquí y autoriza con TU cuenta."
    gh auth login --hostname github.com --web --git-protocol https
}
gh auth setup-git
$usuario = gh api user --jq .login
Ok "Sesión iniciada como $usuario"

gh repo view $Repo --json name *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Tu cuenta ($usuario) no tiene acceso a $Repo. Acepta la invitación en https://github.com/$Repo/invitations o pídele a Dante que te invite."
}
Ok "Tienes acceso a $Repo"

# 3. Nombre y correo para los commits
Paso "Revisando nombre y correo en Git"
if (-not (git config --global user.name)) {
    $nombre = Read-Host "    Tu nombre completo (para firmar tus cambios)"
    git config --global user.name $nombre
}
if (-not (git config --global user.email)) {
    $id = gh api user --jq .id
    git config --global user.email "$id+$usuario@users.noreply.github.com"
}
git config --global pull.rebase false
git config --global init.defaultBranch main
Ok ("Firmas como: " + (git config --global user.name))

# 4. Proyecto al día
Paso "Actualizando el proyecto"
Set-Location $Raiz
git fetch --prune origin
$rama = git branch --show-current
if ($rama -eq "main") { git pull --ff-only origin main }
Ok "Proyecto en $Raiz (rama: $rama)"

# 5. Entorno de Python
Paso "Preparando Python"
if (-not (Existe "python") -and -not (Existe "py")) { Instalar-Winget "Python.Python.3.12" "python" }
$venvPython = Join-Path $Raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    if (Existe "py") { py -3 -m venv .venv } else { python -m venv .venv }
}
& $venvPython -m pip install --quiet --upgrade pip
& $venvPython -m pip install --quiet -r requirements.txt
Ok "Entorno Python listo en .venv"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Aviso "Se creó el archivo .env. Pide la clave de la API a Dante y pégala ahí (nunca se sube a GitHub)."
}

# 6. Asistente de IA
Paso "Revisando tu asistente de IA"
if ($Agente -eq "") {
    $op = Read-Host "    ¿Con cuál trabajas? 1 = Codex, 2 = Antigravity, 3 = Claude Code, Enter = ninguno"
    $Agente = @{ "1" = "codex"; "2" = "antigravity"; "3" = "claude" }[$op]
}
switch ($Agente) {
    "codex" {
        if (Existe "codex") { Ok "Codex ya está instalado" }
        else {
            Instalar-Winget "OpenJS.NodeJS.LTS" "npm"
            npm install -g @openai/codex
            Actualizar-Path
            Ok "Codex instalado"
        }
        Aviso "Para empezar: escribe  codex  dentro de esta carpeta."
    }
    "antigravity" {
        if (Existe "agy") { Ok "Antigravity CLI ya está instalado" }
        else {
            $script = (Invoke-WebRequest -UseBasicParsing -Uri "https://antigravity.google/cli/install.ps1").Content
            if ($script -is [byte[]]) { $script = [Text.Encoding]::UTF8.GetString($script) }
            & ([scriptblock]::Create($script))
            Actualizar-Path
            Ok "Antigravity CLI instalado"
        }
        Aviso "Para empezar: escribe  agy  dentro de esta carpeta (la primera vez elige Google OAuth)."
    }
    "claude" {
        if (Existe "claude") { Ok "Claude Code ya está instalado" }
        else { Aviso "Instala Claude Code desde https://claude.com/claude-code" }
        Aviso "Para empezar: escribe  claude  dentro de esta carpeta."
    }
    default { Aviso "Sin asistente elegido. Puedes volver a ejecutar este script cuando quieras." }
}

Paso "Listo"
Write-Host "    Reglas del equipo: AGENTS.md   |   Plan: docs\PLAN.md"
Write-Host "    Para cada tarea: crea una rama  $($usuario.ToLower())/nombre-tarea  y entrega con Pull Request."
