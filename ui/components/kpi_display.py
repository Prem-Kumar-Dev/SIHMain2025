import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from typing import Any, Dict
import streamlit as st


def render_kpis(kpis: Dict[str, Any]) -> None:
    if not isinstance(kpis, dict):
        st.warning("KPIs unavailable")
        return
    # Simple grid of key metrics if present
    cols = st.columns(3)
    def metric(c, label, key):
        if key in kpis:
            c.metric(label, kpis.get(key))
    metric(cols[0], "OTP (end)", "otp_end")
    metric(cols[1], "OTP@0 (end)", "otp0_end")
    metric(cols[2], "Avg Lateness (s)", "avg_lateness")
    st.json(kpis)
