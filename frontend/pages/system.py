"""
pages/system.py — System Status

Shows the health of each component in the processing pipeline.
Frontend/data components are marked Active.
ML/model components are marked as Not Connected / Demo Mode.
"""

from __future__ import annotations

import datetime
import platform

import streamlit as st

from frontend.components.metrics import section_header
from frontend.services.mock_predictions import PredictionResult
from frontend.utils.constants import SIMULATED_DATA_PATH


# ── Component definitions ─────────────────────────────────────────────────────

_COMPONENTS = [
    {
        "name":        "Data Pipeline",
        "description": "Ingests traffic data from CSV / upload. Normalises schema.",
        "status":      "active",
        "module":      "frontend/services/data_loader.py",
        "notes":       "Supports simulated CSV and CIC-IDS2018 flow format. PCAP pending.",
    },
    {
        "name":        "Feature Extraction",
        "description": "Extracts packet-level features (SYN rate, TTL variance, etc.).",
        "status":      "active",
        "module":      "frontend/services/state_builder.py",
        "notes":       "14 state features computed per time window.",
    },
    {
        "name":        "Network State Builder",
        "description": "Aggregates features into state vector S_t.",
        "status":      "active",
        "module":      "frontend/services/state_builder.py",
        "notes":       "Builds historical sequence S_t-n → S_t for the model.",
    },
    {
        "name":        "World Model",
        "description": "LSTM / Transformer that predicts S_t+1 … S_t+n from S_t.",
        "status":      "demo",
        "module":      "model/world_model.py  (not yet created)",
        "notes":       "Integration point: replace mock_predictions.get_mock_prediction().",
    },
    {
        "name":        "Prediction Engine",
        "description": "Derives risk score, stage classification, and attack forecast.",
        "status":      "demo",
        "module":      "model/predictor.py  (not yet created)",
        "notes":       "Currently returns PredictionResult from mock_predictions.py.",
    },
    {
        "name":        "Alert Engine",
        "description": "Evaluates risk thresholds and routes alerts to correct devices.",
        "status":      "active",
        "module":      "frontend/pages/alerts.py",
        "notes":       "Targeted alerts — only HIGH/CRITICAL devices alerted.",
    },
    {
        "name":        "Explainability Engine",
        "description": "Computes SHAP / attention weights for model decisions.",
        "status":      "demo",
        "module":      "model/explainer.py  (not yet created)",
        "notes":       "Currently returns mock feature importance values.",
    },
]

_STATUS_CONFIG = {
    "active": {"label": "Active",         "color": "#22c55e", "icon": "●", "bg": "#052e16"},
    "demo":   {"label": "Demo Mode",      "color": "#f59e0b", "icon": "○", "bg": "#422006"},
    "error":  {"label": "Error",          "color": "#ef4444", "icon": "✕", "bg": "#450a0a"},
    "off":    {"label": "Not Connected",  "color": "#475569", "icon": "○", "bg": "#0f172a"},
}


def _component_card(comp: dict) -> None:
    cfg   = _STATUS_CONFIG.get(comp["status"], _STATUS_CONFIG["off"])
    color = cfg["color"]
    bg    = cfg["bg"]
    label = cfg["label"]
    icon  = cfg["icon"]

    st.markdown(
        f"""
<div style="background:{bg};border:1px solid {color}33;border-left:4px solid {color};
     border-radius:8px;padding:14px 18px;margin-bottom:8px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div>
      <span style="color:#f1f5f9;font-weight:700;font-size:0.95rem">{comp['name']}</span>
      <span style="color:{color};font-size:0.75rem;margin-left:10px;
                   background:{color}22;border-radius:10px;padding:1px 8px">
        {icon} {label}
      </span>
    </div>
    <code style="color:#64748b;font-size:0.72rem">{comp['module']}</code>
  </div>
  <div style="color:#94a3b8;font-size:0.82rem;margin-top:6px">{comp['description']}</div>
  <div style="color:#64748b;font-size:0.75rem;margin-top:4px">ℹ️ {comp['notes']}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _pipeline_flow() -> None:
    """Visual pipeline flow diagram."""
    steps = [
        ("📡 Input Traffic",      "active"),
        ("⚙️ Data Processing",    "active"),
        ("🔬 State Builder",      "active"),
        ("🧠 World Model",        "demo"),
        ("🎯 Prediction Engine",  "demo"),
        ("💡 Explainability",     "demo"),
        ("🚨 Alert Engine",       "active"),
    ]

    html = ['<div style="display:flex;align-items:center;gap:0;flex-wrap:wrap;margin:8px 0">']
    for i, (name, status) in enumerate(steps):
        cfg   = _STATUS_CONFIG.get(status, _STATUS_CONFIG["off"])
        color = cfg["color"]
        bg    = cfg["bg"]
        if i > 0:
            html.append('<span style="color:#334155;font-size:1.2rem;margin:0 4px">→</span>')
        html.append(
            f'<div style="background:{bg};border:1px solid {color}33;border-radius:8px;'
            f'padding:8px 12px;text-align:center;min-width:100px">'
            f'<div style="font-size:0.82rem;color:#f1f5f9">{name}</div>'
            f'<div style="color:{color};font-size:0.68rem;margin-top:2px">{cfg["label"]}</div>'
            f'</div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def _environment_info(df_loaded: bool) -> None:
    section_header("Environment Information")

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data_status = "✅ Loaded" if df_loaded else "⚠️ Not loaded"
    default_data = "✅ Available" if SIMULATED_DATA_PATH.exists() else "❌ Not found"

    info = {
        "Platform":               platform.system() + " " + platform.release(),
        "Python":                 platform.python_version(),
        "Simulated Dataset":      default_data,
        "Session Data":           data_status,
        "Timestamp":              now,
        "App Mode":               "DEMO — ML backend not connected",
    }

    col_a, col_b = st.columns(2)
    for i, (k, v) in enumerate(info.items()):
        col = col_a if i % 2 == 0 else col_b
        with col:
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;'
                f'background:#1e293b;border-radius:5px;padding:6px 12px;margin-bottom:4px">'
                f'<span style="color:#64748b;font-size:0.8rem">{k}</span>'
                f'<span style="color:#f1f5f9;font-size:0.8rem">{v}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _integration_guide() -> None:
    section_header("ML Backend Integration Guide",
                   "Steps to connect the real World Model")
    steps = [
        ("1", "Train the World Model",
         "Train LSTM/Transformer on feature sequences in `model/world_model.py`."),
        ("2", "Implement `predict(S_t) → PredictionResult`",
         "Replace `get_mock_prediction()` in `services/mock_predictions.py` "
         "with a real call to `world_model.predict()`."),
        ("3", "Connect SHAP / Attention Weights",
         "Populate `contributing_features` in PredictionResult with real SHAP values "
         "or model attention weights."),
        ("4", "Add MITRE ATT&CK Mapping",
         "Create `services/mitre_mapping.py` and configure "
         "stage → technique ID mappings."),
        ("5", "Update System Page",
         "Change component status in `pages/system.py` from `demo` to `active`."),
    ]
    for num, title, detail in steps:
        st.markdown(
            f'<div style="display:flex;gap:12px;background:#1e293b;border-radius:8px;'
            f'padding:12px 16px;margin-bottom:6px;align-items:flex-start">'
            f'<div style="background:#1d4ed8;color:#fff;border-radius:50%;width:24px;'
            f'height:24px;display:flex;align-items:center;justify-content:center;'
            f'font-size:0.75rem;font-weight:700;flex-shrink:0">{num}</div>'
            f'<div><div style="color:#f1f5f9;font-weight:600;font-size:0.9rem">{title}</div>'
            f'<div style="color:#94a3b8;font-size:0.8rem;margin-top:2px">{detail}</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )


# ── Public render function ────────────────────────────────────────────────────

def render(pred: PredictionResult, df=None) -> None:
    st.markdown(
        '<h2 style="color:#f1f5f9;margin-bottom:0">⚙️ System Status</h2>'
        '<p style="color:#64748b;margin-top:2px">'
        'Component health and integration status</p>',
        unsafe_allow_html=True,
    )

    # Overall status banner
    n_active = sum(1 for c in _COMPONENTS if c["status"] == "active")
    n_demo   = sum(1 for c in _COMPONENTS if c["status"] == "demo")
    st.markdown(
        f'<div style="background:#1e293b;border-radius:8px;padding:10px 16px;'
        f'display:flex;gap:24px;margin-bottom:12px">'
        f'<span style="color:#22c55e">● {n_active} Active</span>'
        f'<span style="color:#f59e0b">○ {n_demo} Demo / Not Connected</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    section_header("Pipeline Architecture")
    _pipeline_flow()

    st.divider()

    section_header("Component Status")
    for comp in _COMPONENTS:
        _component_card(comp)

    st.divider()

    _environment_info(df is not None)

    st.divider()

    _integration_guide()
