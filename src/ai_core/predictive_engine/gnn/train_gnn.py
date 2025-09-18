from __future__ import annotations
"""Lightweight training loop for the prototype HetGNNDelayPredictor.

We avoid torch-geometric dependencies and treat each scenario JSON file as a
collection of per-train feature vectors (from `graph_builder`). Because we lack
true labels in historical JSON states, we synthesize a target proxy:

  target_delay_minutes = current_delay_minutes (already in state) or 0.

This provides a self-supervised style fit that at least calibrates the model to
reproduce existing observed delay magnitudes; later we can swap with real
ground-truth arrival lateness labels.

Output is a checkpoint file loadable by `HetGNNDelayPredictor`.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

try:  # pragma: no cover - optional dependency environment
    import torch  # type: ignore
    from torch import nn  # type: ignore
    from torch.utils.data import DataLoader, Dataset  # type: ignore
except Exception as e:  # pragma: no cover
    torch = None  # type: ignore
    nn = None  # type: ignore
    DataLoader = None  # type: ignore
    Dataset = object  # type: ignore

from .graph_builder import build_hetero_graph
from .model_gnn import _TrainFeatureMLP  # reuse same architecture


class ScenarioDataset(Dataset):  # type: ignore[misc]
    def __init__(self, folder: Path):
        self.items = sorted([p for p in folder.glob("*.json")])

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        return json.loads(Path(self.items[idx]).read_text())


def collate(batch: List[Dict[str, Any]]):  # single-item batches expected
    return batch[0]


def train(args: argparse.Namespace) -> None:
    if torch is None or nn is None:
        raise RuntimeError("torch not available. Please install torch to train GNN model.")
    data_dir = Path(args.data_dir)
    out_path = Path(args.out)
    ds = ScenarioDataset(data_dir)
    if len(ds) == 0:
        raise RuntimeError(f"No JSON scenario files found in {data_dir}")
    dl = DataLoader(ds, batch_size=1, shuffle=True, collate_fn=collate)

    model: _TrainFeatureMLP | None = None
    opt = None
    loss_fn = nn.MSELoss()
    feature_names: List[str] | None = None

    for epoch in range(args.epochs):
        for batch in dl:
            graph, idx = build_hetero_graph(batch)
            feats = graph.get("x") or []
            if not feats:
                continue
            # Build targets: align to insertion order of idx keys
            ordered_tids = list(idx.keys())
            # Pull current_delay_minutes from original batch by id
            delay_lookup = {}
            for tr in (batch.get("trains") or []):
                tid = tr.get("id")
                if isinstance(tid, str):
                    delay_lookup[tid] = float(tr.get("current_delay_minutes", 0.0) or 0.0)
            targets = [delay_lookup.get(tid, 0.0) for tid in ordered_tids]

            x = torch.tensor(feats, dtype=torch.float32)  # type: ignore
            y = torch.tensor(targets, dtype=torch.float32)  # type: ignore
            if model is None:
                feature_names = graph.get("feature_names") or []
                model = _TrainFeatureMLP(in_dim=x.shape[1], hidden=args.hidden)  # type: ignore
                opt = torch.optim.Adam(model.parameters(), lr=args.lr)  # type: ignore
            assert model is not None and opt is not None
            model.train()
            opt.zero_grad()
            yhat = model(x)
            loss = loss_fn(yhat, y)
            loss.backward()
            opt.step()
        if (epoch + 1) % max(1, args.epochs // 5) == 0:
            print(f"epoch {epoch+1}/{args.epochs} loss={loss.item():.4f}")

    # Save checkpoint
    if model is None:
        raise RuntimeError("Model failed to initialize during training")
    ckpt = {
        "state_dict": model.state_dict(),
        "meta": {
            "feature_names": feature_names or [],
            "hidden": args.hidden,
        },
    }
    torch.save(ckpt, out_path)  # type: ignore
    print(f"Saved GNN prototype weights to {out_path}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", required=True, help="Folder containing scenario JSON files")
    p.add_argument("--out", required=True, help="Output checkpoint path (.pt)")
    p.add_argument("--hidden", type=int, default=64)
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--lr", type=float, default=1e-3)
    args = p.parse_args()
    train(args)


if __name__ == "__main__":
    main()
