@echo off
setlocal
pushd "%~dp0..\frontend"

where py >nul 2>&1
if %errorlevel% equ 0 (
    set "COSTFLOW_PYTHON=py -3"
) else (
    set "COSTFLOW_PYTHON=python"
)

echo CostFlow estara disponible en http://localhost:8000
echo Cierra esta ventana para detener el servidor.
start "" http://localhost:8000
%COSTFLOW_PYTHON% -m http.server 8000

popd
endlocal
