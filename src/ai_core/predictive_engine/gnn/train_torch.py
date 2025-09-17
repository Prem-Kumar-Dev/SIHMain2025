from __future__ import annotations
import argparse
import csv
from pathlib import Path
from typing import List, Dict, Tuple

import math

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
except Exception as e:  # pragma: no cover
    raise RuntimeError("PyTorch is required to train the model. Please install torch.")

from .model_torch import DelayMLP


def read_csv(path: Path) -> Tuple[List[str], List[List[float]], List[float]]:
    with path.open("r", newline="") as f:
        r = csv.DictReader(f)
        rows = list(r)
    # feature columns are all except 'train_id' and 'target_lateness_s'
    cols = [c for c in r.fieldnames if c not in ("train_id", "target_lateness_s")]  # type: ignore[arg-type]
    X: List[List[float]] = []
    y: List[float] = []
    for row in rows:
        X.append([float(row.get(c, 0) or 0) for c in cols])
        # convert seconds target to minutes for regression stability
        y.append(float(row.get("target_lateness_s", 0) or 0) / 60.0)
    return cols, X, y


def compute_norm(X: List[List[float]]) -> Tuple[List[float], List[float]]:
    if not X:
        return [], []
    d = len(X[0])
    mean = [0.0] * d
    std = [0.0] * d
    n = float(len(X))
    for row in X:
        for i, v in enumerate(row):
            mean[i] += v
    mean = [m / n for m in mean]
    for row in X:
        for i, v in enumerate(row):
            std[i] += (v - mean[i]) ** 2
    std = [math.sqrt(s / max(1.0, n - 1.0)) for s in std]
    # avoid zeros
    std = [s if s > 1e-6 else 1.0 for s in std]
    return mean, std


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, required=True, help="Path to training_data.csv")
    p.add_argument("--out", type=Path, default=Path("delay_model.pt"), help="Output model path (.pt)")
    p.add_argument("--hidden", type=int, default=64)
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--lr", type=float, default=1e-3)
    args = p.parse_args()

    feat_order, X, y = read_csv(args.csv)
    mu, sd = compute_norm(X)
    # standardize
    Xn = [[(v - mu[i]) / sd[i] for i, v in enumerate(row)] for row in X]

    device = torch.device("cpu")
    model = DelayMLP(in_dim=len(feat_order), hidden=args.hidden).to(device)
    opt = optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.MSELoss()

    x = torch.tensor(Xn, dtype=torch.float32, device=device)
    t = torch.tensor(y, dtype=torch.float32, device=device)

    model.train()
    for epoch in range(args.epochs):
        opt.zero_grad()
        yhat = model(x)
        loss = loss_fn(yhat, t)
        loss.backward()
        opt.step()
        # print loss occasionally
        if (epoch + 1) % max(1, args.epochs // 5) == 0:
            print(f"epoch {epoch+1}/{args.epochs} - loss={loss.item():.4f}")

    # save checkpoint
    ckpt = {
        "state_dict": model.state_dict(),
        "meta": {
            "feature_order": feat_order,
            "feature_mean": mu,
            "feature_std": sd,
            "hidden": args.hidden,
        },
    }
    torch.save(ckpt, args.out)
    print(f"Saved model to {args.out}")


if __name__ == "__main__":
    main()
