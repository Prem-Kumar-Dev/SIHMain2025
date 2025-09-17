from __future__ import annotations
from typing import Dict, Any, Tuple


def build_hetero_graph(state: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """Placeholder hetero graph builder.

    Returns a simple dict form and a node index map per train id for downstream use.
    Replace with PyTorch Geometric/DGL graph construction later.
    """
    trains = state.get("trains", [])
    sections = state.get("sections", [])
    train_idx: Dict[str, int] = {}
    for i, t in enumerate(trains):
        if isinstance(t.get("id"), str):
            train_idx[t["id"]] = i
    graph = {
        "num_trains": len(trains),
        "num_sections": len(sections),
        # Edge lists would go here
    }
    return graph, train_idx
