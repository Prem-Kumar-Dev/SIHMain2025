param(
    [string]$ApiBase = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

Write-Host "[Demo] Using API: $ApiBase"

# Load scenario
$scenarioPath = Join-Path $PSScriptRoot "..\data\scenarios\collision_heavy.json"
$scenario = Get-Content $scenarioPath -Raw | ConvertFrom-Json

# Predict
Write-Host "[Demo] Calling /predict ..."
$pred = Invoke-RestMethod -Method Post -Uri "$ApiBase/predict" -ContentType "application/json" -Body ($scenario | ConvertTo-Json -Depth 6)

$conflicts = $pred.conflicts
if ($null -eq $conflicts) { $conflicts = @() }
Write-Host ("[Demo] Predicted conflicts: {0}" -f ($conflicts | Measure-Object).Count)

# Resolve
Write-Host "[Demo] Calling /resolve ..."
$res = Invoke-RestMethod -Method Post -Uri "$ApiBase/resolve" -ContentType "application/json" -Body ($scenario | ConvertTo-Json -Depth 6)

$kpis = $res.kpis
$sch = $res.schedule

Write-Host "[Demo] Schedule items: " ($sch | Measure-Object).Count
if ($kpis) {
    if ($kpis.on_time_percentage) { Write-Host ("[Demo] On-time %: {0}" -f $kpis.on_time_percentage) }
    if ($kpis.avg_delay_minutes) { Write-Host ("[Demo] Avg delay (min): {0}" -f $kpis.avg_delay_minutes) }
}

# Verify headway per section
$sections = @{}
foreach ($s in $scenario.sections) { $sections[$s.id] = $s.headway_seconds }

$bySection = @{}
foreach ($item in $sch) {
    $sec = $item.section_id
    if (-not $sec) { continue }
    if (-not $bySection.ContainsKey($sec)) { $bySection[$sec] = @() }
    $bySection[$sec] += ,$item
}

foreach ($sec in $bySection.Keys) {
    $items = $bySection[$sec] | Sort-Object -Property entry_time
    for ($i=1; $i -lt $items.Count; $i++) {
        $prev = $items[$i-1]
        $curr = $items[$i]
        $gap = ($curr.entry_time - $prev.exit_time)
        $need = $sections[$sec]
        if ($gap -lt $need) {
            Write-Host ("[Demo][WARN] Headway violated on {0}: gap={1}, need>={2}" -f $sec, $gap, $need) -ForegroundColor Yellow
        }
    }
}

Write-Host "[Demo] Done."
