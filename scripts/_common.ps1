# Shared helpers for the Orion PowerShell scripts (Windows equivalent of the Makefile, PLAN.md A-02).
$script:Root = Split-Path -Parent $PSScriptRoot
$script:Backend = Join-Path $script:Root "backend"
$script:Frontend = Join-Path $script:Root "frontend"
$script:VenvPython = Join-Path $script:Backend ".venv\Scripts\python.exe"

function Invoke-Native {
    # Runs a native command and stops the script when it fails.
    param([Parameter(Mandatory = $true)][string]$Exe, [string[]]$Arguments = @())
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "'$Exe $($Arguments -join ' ')' failed with exit code $LASTEXITCODE" }
}

function Assert-Venv {
    if (-not (Test-Path $script:VenvPython)) { throw "backend\.venv not found - run scripts\setup.ps1 first" }
}
