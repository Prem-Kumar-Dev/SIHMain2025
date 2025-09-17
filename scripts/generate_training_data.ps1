param(
  [string]$Base = ".\data\base_state.json",
  [string]$Out = ".\data\training_data.csv",
  [int]$N = 500,
  [int]$Seed = -1
)

if (-not (Test-Path $Base)) {
  Write-Error "Base state JSON not found: $Base"
  exit 1
}

$py = "python"
if (Test-Path ".\.venv\Scripts\python.exe") { $py = ".\.venv\Scripts\python.exe" }

if ($Seed -ge 0) {
  & $py -m src.ai_core.predictive_engine.generate_training_data --base $Base --out $Out --n $N --seed $Seed
} else {
  & $py -m src.ai_core.predictive_engine.generate_training_data --base $Base --out $Out --n $N
}
