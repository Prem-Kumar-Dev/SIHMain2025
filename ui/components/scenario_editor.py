import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from typing import Any, Dict
import json
import streamlit as st


def editor(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    text = st.text_area(name, json.dumps(payload, indent=2), height=280)
    try:
        parsed = json.loads(text)
        return parsed
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        return payload
