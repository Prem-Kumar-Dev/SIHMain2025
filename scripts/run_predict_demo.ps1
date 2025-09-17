param(
  [string]$ApiBase = "http://localhost:8000",
  [string]$ScenarioPath = "scenario_predict_demo.json"
)

# Sample small scenario payload with current_delay_minutes fields
$payload = @{
  sections = @(
    @{ id = "S1"; headway_seconds = 120; traverse_seconds = 100 },
    @{ id = "S2"; headway_seconds = 120; traverse_seconds = 120 }
  );
  trains = @(
    @{ id = "A"; priority = 1; planned_departure = 0; route_sections = @("S1","S2"); current_delay_minutes = 2 },
    @{ id = "B"; priority = 2; planned_departure = 30; route_sections = @("S1"); current_delay_minutes = 0 }
  )
} | ConvertTo-Json -Depth 6

Write-Host "Calling /predict at $ApiBase"
try {
  $res = Invoke-RestMethod -Uri "$ApiBase/predict" -Method Post -Body $payload -ContentType 'application/json'
  $res | ConvertTo-Json -Depth 6
} catch {
  Write-Error $_
  exit 1
}
