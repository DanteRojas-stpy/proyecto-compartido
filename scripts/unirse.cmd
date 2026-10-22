@echo off
rem Doble clic aqui (o escribe scripts\unirse.cmd) para preparar tu computadora.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0unirse.ps1" %*
pause
