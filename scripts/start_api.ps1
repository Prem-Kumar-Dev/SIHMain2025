param(
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

$venvPy = Join-Path $PSScriptRoot '..' | Join-Path -ChildPath '.venv\Scripts\python.exe'
if (Test-Path $venvPy) {
    $py = (Resolve-Path $venvPy).Path
} else {
    $py = 'python'
}

$cmd = "$py -m uvicorn src.api:app --host 0.0.0.0 --port $Port"
Write-Host "Starting API server: $cmd"
& powershell -NoExit -NoLogo -NoProfile -Command $cmd
