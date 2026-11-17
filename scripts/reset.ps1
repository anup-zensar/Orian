# Re-seeds the demo database (NFR-06). Stop the API first if it is running, or use Admin -> Demo controls -> Reset.
. (Join-Path $PSScriptRoot "_common.ps1")
Assert-Venv
Push-Location $script:Backend
try { Invoke-Native $script:VenvPython @("-c", "from app.seed.loader import reset_and_seed; reset_and_seed(); print('Demo data reset')") }
finally { Pop-Location }
