param(
    [string]$PythonExe = "",
    [string]$NodeExe = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe",
    [string]$NodeModules = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules",
    [int]$Port = 18775,
    [switch]$Restart
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
if (-not $PythonExe) { $PythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe' }
foreach ($requiredPath in @($PythonExe, $NodeExe, $NodeModules)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) { throw "No existe: $requiredPath. Indica la ruta del entorno." }
}
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'CostFlow\comparativos'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$tokenPath = Join-Path $runtimeRoot 'servicio.token'
if (-not (Test-Path -LiteralPath $tokenPath)) {
    ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')) | Set-Content -LiteralPath $tokenPath -NoNewline
}
$tokenValue = (Get-Content -LiteralPath $tokenPath -Raw).Trim()
if ($Restart -and (Test-Path -LiteralPath (Join-Path $runtimeRoot 'servicio.pid'))) {
    $previousPid = [int](Get-Content -LiteralPath (Join-Path $runtimeRoot 'servicio.pid'))
    $previous = Get-CimInstance Win32_Process -Filter "ProcessId=$previousPid"
    if ($previous) {
        if ($previous.CommandLine -notlike '*app.comparativo.servicio*') { throw 'El PID guardado no pertenece al generador.' }
        Stop-Process -Id $previousPid
    }
}
try {
    $health = Invoke-RestMethod "http://127.0.0.1:$Port/health" -Headers @{'X-CostFlow-Token'=$tokenValue} -TimeoutSec 2
    if ($health.estado -eq 'disponible') { Write-Output 'El generador ya está disponible.'; return }
} catch {}
$modulesLink = Join-Path $runtimeRoot 'node_modules'
if (-not (Test-Path -LiteralPath $modulesLink)) {
    New-Item -ItemType Junction -Path $modulesLink -Target $NodeModules | Out-Null
}
$workerPath = Join-Path $runtimeRoot 'calcular_formulas.mjs'
Copy-Item -LiteralPath (Join-Path $projectRoot 'app\comparativo\calcular_formulas.mjs') -Destination $workerPath
$outputRoot = Join-Path $runtimeRoot 'salidas'
$serviceArgs = @('-X','utf8','-m','app.comparativo.servicio','--bind','0.0.0.0','--port',"$Port",
    '--token-file',('"'+$tokenPath+'"'),'--salida',('"'+$outputRoot+'"'),
    '--node',('"'+$NodeExe+'"'),'--worker',('"'+$workerPath+'"'))
$service = Start-Process -FilePath $PythonExe -ArgumentList $serviceArgs -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $runtimeRoot 'servicio.stdout.log') -RedirectStandardError (Join-Path $runtimeRoot 'servicio.stderr.log')
$service.Id | Set-Content -LiteralPath (Join-Path $runtimeRoot 'servicio.pid')
Write-Output "Generador iniciado en el puerto $Port. Las salidas se guardan en $outputRoot."
