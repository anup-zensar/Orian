# Milestone definition of done: backend tests + lint, frontend type-check/build + lint.
. (Join-Path $PSScriptRoot "_common.ps1")
Assert-Venv

Push-Location $script:Backend
try {
    Invoke-Native $script:VenvPython @("-m", "pytest", "-q")
    Invoke-Native ".\.venv\Scripts\ruff.exe" @("check", ".")
    Invoke-Native ".\.venv\Scripts\black.exe" @("--check", ".")
}
finally { Pop-Location }

Push-Location $script:Frontend
try {
    Invoke-Native "npm.cmd" @("run", "build")
    Invoke-Native "npm.cmd" @("run", "lint")
}
finally { Pop-Location }
Write-Host "All checks passed."
