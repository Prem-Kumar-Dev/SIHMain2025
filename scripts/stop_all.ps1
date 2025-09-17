param(
    [int]$PortApi = 8000,
    [int]$UiPort = 8501
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host "[StopAll] Attempting to stop servers..."

# Try to kill uvicorn by port
$uvicornPids = (Get-NetTCPConnection -LocalPort $PortApi -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $_.OwningProcess } | Select-Object -Unique)
foreach ($pid in $uvicornPids) {
    try { Stop-Process -Id $pid -Force -ErrorAction Stop; Write-Host "[StopAll] Killed API PID $pid" } catch {}
}

# Try to kill streamlit by port
$uiPids = (Get-NetTCPConnection -LocalPort $UiPort -State Listen -ErrorAction SilentlyContinue | ForEach-Object { $_.OwningProcess } | Select-Object -Unique)
foreach ($pid in $uiPids) {
    try { Stop-Process -Id $pid -Force -ErrorAction Stop; Write-Host "[StopAll] Killed UI PID $pid" } catch {}
}

# Fallback: kill by name patterns
Get-Process -Name python,python3,uvicorn,streamlit -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -match 'uvicorn' -or $_.Path -match 'streamlit' } | ForEach-Object { try { Stop-Process -Id $_.Id -Force } catch {} }

Write-Host "[StopAll] Done."
