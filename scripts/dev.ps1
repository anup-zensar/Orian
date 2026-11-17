# Starts the API (http://127.0.0.1:8000, docs at /docs) and the web app (http://127.0.0.1:5173)
# in two PowerShell windows. Close the windows to stop them.
# If port 5173 is used by another local app: scripts\dev.ps1 -WebPort 5174
param([int]$WebPort = 5173)
. (Join-Path $PSScriptRoot "_common.ps1")
Assert-Venv

Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$($script:Backend)'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
)
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$($script:Frontend)'; npm.cmd run dev -- --port $WebPort"
)
Write-Host "Backend: http://127.0.0.1:8000/docs   Frontend: http://127.0.0.1:$WebPort"
