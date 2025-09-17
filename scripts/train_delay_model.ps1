param(
  [string]$Csv = ".\data\training_data.csv",
  [string]$Out = ".\data\delay_model.pt",
  [int]$Hidden = 64,
  [int]$Epochs = 20,
  [double]$Lr = 0.001
)

if (-not (Test-Path $Csv)) {
  Write-Error "Training CSV not found: $Csv"
  exit 1
}

$py = "python"
if (Test-Path ".\.venv\Scripts\python.exe") { $py = ".\.venv\Scripts\python.exe" }

& $py -m src.ai_core.predictive_engine.gnn.train_torch --csv $Csv --out $Out --hidden $Hidden --epochs $Epochs --lr $Lr
