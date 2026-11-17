# Dependency vulnerability scan (VAPT hygiene, PLAN.md A-24/A-46): pip-audit over the full transitive pin set
# (backend/constraints.txt) + npm audit (frontend).
. (Join-Path $PSScriptRoot "_common.ps1")
Assert-Venv
Push-Location $script:Backend
try { Invoke-Native ".\.venv\Scripts\pip-audit.exe" @("-r", "constraints.txt") }
finally { Pop-Location }
Push-Location $script:Frontend
try { Invoke-Native "npm.cmd" @("audit") }
finally { Pop-Location }
