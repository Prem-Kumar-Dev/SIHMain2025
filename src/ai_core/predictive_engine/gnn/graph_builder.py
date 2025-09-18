from __future__ import annotations
"""Lightweight graph & feature construction used by the (proto) GNN path.

The real heterogeneous graph (with section/train bipartite nodes and temporal
edges) can be introduced later. For now we expose a uniform dictionary shape
that downstream code can treat as a graph-like object. This keeps the API stable
and makes it trivial to swap in a PyG `HeteroData` object when those deps are
available.

Returned structure:
  graph = {
      'num_trains': int,
      'num_sections': int,
      'feature_names': List[str],
      'x': List[List[float]],   # per-train feature matrix (row aligned to train_idx)
      'adjacency': Optional[...] (reserved),
  }

Currently we only derive simple local features which mirror a subset of the
feature_engineering outputs so we do not have to import heavy modules here.
When/if full feature parity is required, we can pass pre-computed feature
vectors into this builder or call the richer feature pipeline.
"""
from typing import Dict, Any, Tuple, List

_BASIC_FEATURES = [
    "priority",                 # train priority (lower = higher priority?)
    "planned_departure",        # scheduled departure seconds
    "current_delay_minutes",    # observed current delay (minutes)
    "route_length",             # number of sections in its route
]


def _extract_train_features(t: Dict[str, Any]) -> List[float]:
    route = t.get("route_sections") or []
    return [
        float(t.get("priority", 0) or 0),
        float(t.get("planned_departure", 0) or 0),
        float(t.get("current_delay_minutes", 0.0) or 0.0),
        float(len(route)),
    ]


def build_hetero_graph(state: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    trains = state.get("trains", []) or []
    sections = state.get("sections", []) or []
    train_idx: Dict[str, int] = {}
    features: List[List[float]] = []
    for i, t in enumerate(trains):
        tid = t.get("id")
        if isinstance(tid, str):
            train_idx[tid] = i
            features.append(_extract_train_features(t))
    graph: Dict[str, Any] = {
        "num_trains": len(train_idx),
        "num_sections": len(sections),
        "feature_names": list(_BASIC_FEATURES),
        "x": features,  # shape [N, F]
        # future: add adjacency / edge index lists
    }
    return graph, train_idx
