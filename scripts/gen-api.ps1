# Exports the backend OpenAPI schema and regenerates the typed frontend API (frontend/src/api/schema.d.ts).
. (Join-Path $PSScriptRoot "_common.ps1")
Assert-Venv
Push-Location $script:Backend
try { Invoke-Native $script:VenvPython @("scripts\export_openapi.py") }
finally { Pop-Location }
Push-Location $script:Frontend
try { Invoke-Native "npm.cmd" @("run", "gen:api") }
finally { Pop-Location }
