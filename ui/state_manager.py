from __future__ import annotations
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from typing import Any, Dict
import streamlit as st


def ensure_defaults() -> None:
    if "solver" not in st.session_state:
        st.session_state.solver = "greedy"
    if "otp_tolerance" not in st.session_state:
        st.session_state.otp_tolerance = 0
    if "state_payload" not in st.session_state:
        st.session_state.state_payload = default_payload()


def default_payload() -> Dict[str, Any]:
    return {
        "sections": [
            {"id": "S1", "headway_seconds": 120, "traverse_seconds": 300},
            {"id": "S2", "headway_seconds": 120, "traverse_seconds": 240}
        ],
        "trains": [
            {"id": "T1", "priority": 2, "planned_departure": 0,   "route_sections": ["S1", "S2"]},
            {"id": "T2", "priority": 3, "planned_departure": 60,  "route_sections": ["S1", "S2"]},
            {"id": "T3", "priority": 1, "planned_departure": 120, "route_sections": ["S1", "S2"]}
        ]
    }


def get_state_payload() -> Dict[str, Any]:
    return st.session_state.get("state_payload", default_payload())


def set_state_payload(p: Dict[str, Any]) -> None:
    st.session_state.state_payload = p
