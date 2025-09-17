param(
    [string]$HostApi = "127.0.0.1",
    [int]$PortApi = 8000,
    [int]$UiPort = 8501,
    [switch]$SkipTrainModel,
    [switch]$RunDemo,
    [switch]$OpenBrowser,
    [switch]$UseNewWindows
)

$ErrorActionPreference = "Stop"

# Default switches if not provided
if (-not $PSBoundParameters.ContainsKey('OpenBrowser')) { $OpenBrowser = $true }
if (-not $PSBoundParameters.ContainsKey('UseNewWindows')) { $UseNewWindows = $true }

Write-Host "[RunAll] Starting setup..."

# Resolve paths
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
$venvDir = Join-Path $root '.venv'
$venvPython = Join-Path $venvDir 'Scripts\python.exe'
$venvPip = Join-Path $venvDir 'Scripts\pip.exe'
$requirements = Join-Path $root 'requirements.txt'
$modelPath = Join-Path $root 'data\delay_model.pt'
$trainScript = Join-Path $root 'scripts\train_delay_model.ps1'
$demoScript = Join-Path $root 'scripts\run_collision_demo.ps1'

# 1) Ensure venv
if (-not (Test-Path $venvPython)) {
    Write-Host "[RunAll] Creating virtual environment at $venvDir"
    Push-Location $root
    try {
        python -m venv .venv
    } finally {
        Pop-Location
    }
}

# 2) Install requirements
if (Test-Path $requirements) {
    Write-Host "[RunAll] Installing requirements..."
    & $venvPip install -r $requirements
} else {
    Write-Warning "[RunAll] requirements.txt not found at $requirements"
}

# 3) Ensure delay model exists (train if missing)
if (-not $SkipTrainModel) {
    if (-not (Test-Path $modelPath)) {
        if (Test-Path $trainScript) {
            Write-Host "[RunAll] No model found. Training delay model..."
            & $trainScript
        } else {
            Write-Warning "[RunAll] Model not found and train script missing: $trainScript"
        }
    } else {
        Write-Host "[RunAll] Found model at $modelPath"
    }
} else {
    Write-Host "[RunAll] Skipping model training as requested."
}

# 4) Start API server
$apiCmd = "Set-Location '$root'; .\.venv\Scripts\Activate.ps1; uvicorn src.api:app --host $HostApi --port $PortApi --reload"
if ($UseNewWindows) {
    Write-Host "[RunAll] Starting API in a new PowerShell window..."
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit","-Command", $apiCmd | Out-Null
} else {
    Write-Host "[RunAll] Starting API in background process..."
    Start-Process -FilePath $venvPython -ArgumentList "-m","uvicorn","src.api:app","--host",$HostApi,"--port",$PortApi,"--reload" -WindowStyle Hidden | Out-Null
}

# 5) Wait for API readiness
$apiBase = "http://$HostApi`:$PortApi"
Write-Host "[RunAll] Waiting for API at $apiBase ..."
$ready = $false
for ($i=0; $i -lt 60; $i++) {
    try {
        $resp = Invoke-WebRequest "$apiBase/" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        if ($resp.StatusCode -in 200, 307, 308) { $ready = $true; break }
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $ready) {
    Write-Warning "[RunAll] API did not respond in time; continuing anyway."
} else {
    Write-Host "[RunAll] API is up."
}

# 6) Start Streamlit UI (set API_BASE for the process)
# If requested UI port is in use, try next few ports
function Test-PortFree {
    param([int]$Port)
    try { (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop) | Out-Null; return $false } catch { return $true }
}
if (-not (Test-PortFree -Port $UiPort)) {
    $orig = $UiPort
    for ($p = $UiPort + 1; $p -le $orig + 10; $p++) {
        if (Test-PortFree -Port $p) { Write-Warning "[RunAll] UI port $UiPort is busy; switching to $p"; $UiPort = $p; break }
    }
}

# Build a child command that sets env vars, activates venv, and runs Streamlit
# Escape literal braces for format string with double braces
$uiCmd = '& {{ $env:API_BASE=''{0}''; $env:PYTHONPATH=''{1}''; Set-Location ''{1}''; .\.venv\Scripts\Activate.ps1; streamlit run ui/app.py --server.port {2} }}'
$uiCmd = $uiCmd -f $apiBase, $root, $UiPort
if ($UseNewWindows) {
    Write-Host "[RunAll] Starting UI in a new PowerShell window..."
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit","-Command", $uiCmd | Out-Null
} else {
    Write-Host "[RunAll] Starting UI in background process..."
    $env:API_BASE = $apiBase
    $env:PYTHONPATH = $root
    Start-Process -FilePath $venvPython -ArgumentList "-m","streamlit","run","ui/app.py","--server.port",$UiPort -WindowStyle Hidden | Out-Null
}

# 7) Open browser tabs
if ($OpenBrowser) {
    Write-Host "[RunAll] Opening browser tabs..."
    Start-Process "$apiBase/docs" | Out-Null
    Start-Process "http://localhost:$UiPort" | Out-Null
}

# 8) Optional: run collision demo
if ($RunDemo) {
    if (Test-Path $demoScript) {
        Write-Host "[RunAll] Running collision demo..."
        & $demoScript -ApiBase $apiBase
    } else {
        Write-Warning "[RunAll] Demo script not found at $demoScript"
    }
}

Write-Host "[RunAll] Done. API at $apiBase, UI at http://localhost:$UiPort"
