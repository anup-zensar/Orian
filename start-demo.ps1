# Starts the Orion M5 demo from this folder (clean M5 checkout, branch demo/m5).
#   API : http://127.0.0.1:8000 (docs at /docs)   Web: http://127.0.0.1:5174
# -Reset  : delete the demo database first (fresh seed on start).
# Only processes listening on 8000/5174 that are python/node are stopped - never anything else
# (port 5173 belongs to another local app and is never touched).
param([switch]$Reset)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = "C:\Users\AK121426\Desktop\Orian\backend\.venv\Scripts\python.exe"

foreach ($port in 8000, 5174) {
    $conns = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -in @("python", "node")) {
            Write-Host "Stopping $($proc.ProcessName) (PID $($proc.Id)) on port $port"
            Stop-Process -Id $proc.Id -Force
        }
    }
}
Start-Sleep -Milliseconds 800
if ($Reset -and (Test-Path "$root\backend\orion.db")) { Remove-Item "$root\backend\orion.db" -Force; Write-Host "Demo database reset" }

Start-Process powershell -WindowStyle Minimized -ArgumentList @(
    "-NoExit", "-Command",
    "`$host.UI.RawUI.WindowTitle='Orion API :8000'; Set-Location '$root\backend'; `$env:MOCK_DELAY_MS='400'; & '$py' -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
)
Start-Process powershell -WindowStyle Minimized -ArgumentList @(
    "-NoExit", "-Command",
    "`$host.UI.RawUI.WindowTitle='Orion Web :5174'; Set-Location '$root\frontend'; npx.cmd vite preview --port 5174 --strictPort"
)

$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $api = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2
        $web = Invoke-WebRequest -Uri "http://127.0.0.1:5174/" -UseBasicParsing -TimeoutSec 2
        if ($api.status -eq "ok" -and $web.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
}
if ($ok) { Write-Host "Orion demo is running: http://127.0.0.1:5174  (API docs: http://127.0.0.1:8000/docs)" }
else { Write-Warning "Servers did not become ready - check the two minimized 'Orion' windows." }
