param(
    [int]$Port = 8000,
    [string]$ApiHost = 'localhost',
    [string]$Solver = 'milp',
    [int]$OtpTolerance = 300,
    [string]$ScenarioName = 'csv-late',
    [string]$OutDir = '.' ,
    [switch]$StartServer
)

$ErrorActionPreference = 'Stop'

function Resolve-VenvPython {
    $venvPy = Join-Path $PSScriptRoot '..' | Join-Path -ChildPath '.venv\Scripts\python.exe'
    if (Test-Path $venvPy) { return (Resolve-Path $venvPy).Path }
    # fallback to python in PATH
    return 'python'
}

function Start-ApiServer {
    param([int]$Port)
    $py = Resolve-VenvPython
    $cmd = "$py -m uvicorn src.api:app --host 0.0.0.0 --port $Port"
    Write-Host "Starting API server: $cmd"
    Start-Process -WindowStyle Normal -FilePath 'powershell.exe' -ArgumentList '-NoExit','-NoLogo','-NoProfile','-Command', $cmd | Out-Null
}

function Wait-ApiReady {
    param([string]$Base, [int]$MaxAttempts = 30)
    for ($i = 0; $i -lt $MaxAttempts; $i++) {
        try {
            Invoke-WebRequest -Uri "$Base/docs" -UseBasicParsing -TimeoutSec 3 | Out-Null
            Write-Host "API is ready at $Base" -ForegroundColor Green
            return
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    throw "API at $Base did not become ready in time"
}

function Run-DemoRequests {
    param([string]$Base, [string]$Solver, [int]$OtpTolerance, [string]$ScenarioName, [string]$OutDir)
    $body = @'
{
  "sections": [{ "id": "S1", "headway_seconds": 0, "traverse_seconds": 10 }],
  "trains": [
    { "id": "A", "priority": 1, "planned_departure": 0, "route_sections": ["S1"], "due_time": 5 },
    { "id": "B", "priority": 1, "planned_departure": 0, "route_sections": ["S1"], "due_time": 100 }
  ]
}
'@
    $headers = @{ 'Content-Type' = 'application/json' }

    Write-Host "Calling /kpis with otp_tolerance=$OtpTolerance" -ForegroundColor Cyan
    $kpis = Invoke-RestMethod -Uri "$Base/kpis?solver=$Solver&otp_tolerance=$OtpTolerance" -Method Post -Headers $headers -Body $body
    $kpis | ConvertTo-Json -Depth 8 | Out-Host

    Write-Host "Saving scenario: $ScenarioName" -ForegroundColor Cyan
    $payload = '{"name":"' + $ScenarioName + '","payload":' + $body + '}'
    $scn = Invoke-RestMethod -Uri "$Base/scenarios" -Method Post -Headers $headers -Body $payload
    $sid = $scn.id
    Write-Host ("Scenario id: {0}" -f $sid)

    Write-Host "Running scenario with solver=$Solver, otp_tolerance=$OtpTolerance" -ForegroundColor Cyan
    $run = Invoke-RestMethod -Uri "$Base/scenarios/$sid/run?solver=$Solver&otp_tolerance=$OtpTolerance" -Method Post
    $rid = $run.run_id
    Write-Host ("Run id: {0}" -f $rid)

    # Download lateness CSV
    if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
    $csvPath = Join-Path $OutDir ("scenario_{0}_run_{1}_lateness.csv" -f $sid, $rid)
    Write-Host "Downloading lateness CSV to $csvPath" -ForegroundColor Cyan
    Invoke-WebRequest -Uri "$Base/runs/$rid/lateness.csv" -OutFile $csvPath | Out-Null
    Write-Host "First lines of CSV:" -ForegroundColor Yellow
    Get-Content $csvPath | Select-Object -First 5 | Out-Host
}

$base = "http://${ApiHost}:$Port"

if ($StartServer) {
    Start-ApiServer -Port $Port
    Start-Sleep -Seconds 1
}

Wait-ApiReady -Base $base
Run-DemoRequests -Base $base -Solver $Solver -OtpTolerance $OtpTolerance -ScenarioName $ScenarioName -OutDir $OutDir

Write-Host "Done." -ForegroundColor Green
