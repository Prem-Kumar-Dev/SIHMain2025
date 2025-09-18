# AI Integration: End-to-End Steps (Windows)

This guide takes you from the current baseline to full AI (GNN) integration with clear, Windows PowerShell-friendly commands.

## 0) Prerequisites
- Windows PowerShell 5.1 or PowerShell 7+
- Python 3.10–3.11 recommended
- From repo root:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```

## 1) Start API + UI
- One-click script (recommended):
  ```powershell
  ./scripts/run_all.ps1 -HostApi 127.0.0.1 -PortApi 8000 -UiPort 8501 -OpenBrowser -UseNewWindows
  ```
- Manual (separate terminals):
  ```powershell
  # Terminal A
  uvicorn src.api:app --host 127.0.0.1 --port 8000

  # Terminal B
  $env:API_BASE = "http://127.0.0.1:8000"
  streamlit run ui/app.py --server.port 8501
  ```
- Open http://localhost:8501 → Live Dashboard → “Refresh Live Data”.

## 2) MLP Predictor (optional)
If you have an MLP weights file (e.g., `data\delay_model.pt`):
- Point API/UI to weights (current shell):
  ```powershell
  $env:PREDICTIVE_MODEL_PATH = "C:\\path\\to\\delay_model.pt"
  ```
- Or via one-click flag:
  ```powershell
  ./scripts/run_all.ps1 -HostApi 127.0.0.1 -PortApi 8000 -UiPort 8501 -PredictiveModelPath "C:\\path\\to\\delay_model.pt" -OpenBrowser -UseNewWindows
  ```
- In UI: set “Model” to `mlp` (or `auto`). `/predict` returns `model_used` for transparency.

## 3) Install PyTorch Geometric (for GNN)
Use `docs/INSTALL_PYG_WINDOWS.md` (CPU-only example below; align versions with your Torch build):
```powershell
pip install torch==2.3.1+cpu torchvision==0.18.1+cpu torchaudio==2.3.1+cpu -f https://download.pytorch.org/whl/cpu
pip install pyg-lib torch-scatter torch-sparse torch-cluster torch-spline-conv torch-geometric -f https://data.pyg.org/whl/torch-2.3.1+cpu.html
```

## 4) Generate training data
Export varied scenarios to a folder (e.g., `data\training_scenarios`). Quick count:
```powershell
Get-ChildItem data\training_scenarios\*.json | Measure-Object | Select-Object Count
```
If you prefer CSV-based training, see `src/ai_core/predictive_engine/generate_training_data.py`.

## 5) Train the GNN (skeleton)
We ship a scaffold you can extend.
- Command:
  ```powershell
  .\.venv\Scripts\python.exe -m src.ai_core.predictive_engine.gnn.train_gnn --data-dir data\training_scenarios --out data\gnn_delay_predictor.pt
  ```
- Implement TODOs in:
  - `src/ai_core/predictive_engine/gnn/model_gnn.py` (define HetGNN forward)
  - `src/ai_core/predictive_engine/gnn/train_gnn.py` (loss/optimizer/epochs)

## 6) Use GNN in API
- `/predict` supports `?model=baseline|mlp|gnn|auto`.
- Point to trained weights:
  ```powershell
  $env:PREDICTIVE_MODEL_PATH = "C:\\abs\\path\\gnn_delay_predictor.pt"
  ```
- Start via one-click after setting env, or pass `-PredictiveModelPath`.
- The API safely falls back (MLP → GNN → Baseline) if a model isn’t available.

## 7) UI Demo Flow
- Live Dashboard → choose “Model”: `auto|baseline|mlp|gnn` → “Refresh Live Data”.
- Gantt always renders (conflicts resolved or schedule fallback).
- Movement chart reuses resolved schedule when available.

## 8) Benchmarking (recommended)
- Hold out a test set; compute MAE/RMSE for MLP vs GNN.
- Add metrics to `train_gnn.py` and save to a CSV for tracking.

## 9) Troubleshooting
- Timeouts on heavy scenarios: UI client timeout is 120s; use `solver=greedy` for demos.
- Blank Gantt: fixed to fallback to `/schedule` when no conflicts.
- Env var scope: set in same PowerShell session or use `-PredictiveModelPath` in the launcher.

---
Next: finalize HetGNN, complete training loop, benchmark vs MLP, and switch `auto` to prefer the better model by metrics.
