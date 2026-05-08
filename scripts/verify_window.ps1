$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$Python = Join-Path $RepoRoot "venv\Scripts\python.exe"
$Verifier = Join-Path $RepoRoot "scripts\verify_window.py"

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Error "Project venv python was not found: $Python"
}

Push-Location $RepoRoot
try {
    & $Python $Verifier @args
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
