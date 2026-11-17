# Creates backend\.venv with the newest supported Python (3.15 preferred, 3.14 fallback - PLAN.md A-01)
# and installs backend + frontend dependencies.
. (Join-Path $PSScriptRoot "_common.ps1")

$installed = (& py -0p) -join "`n"
if ($installed -match "-V:3\.15") { $version = "3.15" }
elseif ($installed -match "-V:3\.14") {
    $version = "3.14"
    Write-Warning "Python 3.15 not found - using 3.14. Install Python 3.15 (latest stable) via your approved software channel, then re-run this script."
}
else { throw "Python 3.15 (preferred) or 3.14 is required (checked with 'py -0p')." }

Push-Location $script:Backend
try {
    if (Test-Path ".venv") {
        $current = (& .\.venv\Scripts\python.exe -c "import sys;print(f'{sys.version_info[0]}.{sys.version_info[1]}')")
        if ($current -ne $version) {
            Write-Host "Re-creating .venv ($current -> $version)"
            Remove-Item -Recurse -Force ".venv"
        }
    }
    if (-not (Test-Path ".venv")) { Invoke-Native "py" @("-$version", "-m", "venv", ".venv") }
    Invoke-Native ".\.venv\Scripts\python.exe" @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Native ".\.venv\Scripts\python.exe" @("-m", "pip", "install", "-r", "requirements-dev.txt", "-c", "constraints.txt")
}
finally { Pop-Location }

Push-Location $script:Frontend
try { Invoke-Native "npm.cmd" @("ci") }
finally { Pop-Location }

Write-Host "Setup complete (Python $version). Start the demo with scripts\dev.ps1"
