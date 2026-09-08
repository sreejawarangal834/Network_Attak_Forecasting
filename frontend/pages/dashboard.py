"""
pages/dashboard.py — SOC Dashboard

Real-time feel dashboard with:
  - Live status strip
  - Four headline KPIs
  - Risk timeline + attack forecast chart
  - At-risk devices (HIGH/CRITICAL only)
  - Security alerts (newest first)
  - Component status strip

Alert logic:
  Network Telemetry → Risk Assessment → Identify High-Risk Devices
       ↓ (HIGH/CRITICAL only)                    ↓
  Affected Device Alert               Admin / SOC Security Alert
"""

from __future__ import annotations

import datetime
import time

import pandas as pd
import streamlit as st

from frontend.components.alert_cards import render_alert_feed
from frontend.components.attack_path import render_attack_pipeline
from frontend.components.charts import (
    risk_timeline_chart,
    stage_forecast_chart,
    traffic_volume_chart,
)
from frontend.components.metrics import demo_badge, section_header
from frontend.services.mock_predictions import PredictionResult
from frontend.utils.constants import RISK_COLORS, STAGE_COLORS, STAGE_ICONS


# ── Live status strip ─────────────────────────────────────────────────────────

def _live_status_strip(df: pd.DataFrame | None) -> None:
    n_records  = f"{len(df):,}" if df is not None else "—"
    now_str    = datetime.datetime.now().strftime("%H:%M:%S")
    refresh_n  = st.session_state.get("refresh_count", 0)

    st.markdown(f"""
<div style="
    background:#0b1526;
    border:1px solid #1a2540;
    border-radius:8px;
    padding:10px 20px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    margin-bottom:16px;
">
  <div style="display:flex;align-items:center;gap:20px">
    <div style="display:flex;align-items:center;gap:6px">
      <span style="color:#22c55e;font-size:0.6rem">●</span>
      <span style="color:#4ade80;font-size:0.82rem;font-weight:700">LIVE DEMO</span>
    </div>
    <div style="color:#475569;font-size:0.78rem">
      Network Status: <span style="color:#94a3b8">Monitoring</span>
    </div>
    <div style="color:#475569;font-size:0.78rem">
      Last Update: <span style="color:#94a3b8;font-family:monospace">{now_str}</span>
    </div>
    <div style="color:#374151;font-size:0.75rem">
      {n_records} events · Simulated telemetry
    </div>
  </div>
  <div style="color:#1e3a5f;font-size:0.72rem">
    Refresh #{refresh_n}
  </div>
</div>
""", unsafe_allow_html=True)


# ── KPI row ───────────────────────────────────────────────────────────────────

def _kpi_card(label: str, value: str, sub: str, border: str, value_color: str) -> str:
    return f"""
<div style="background:#0b1526;border:1px solid {border}33;
     border-top:3px solid {border};border-radius:8px;padding:14px 18px">
  <div style="color:#4b5563;font-size:0.68rem;text-transform:uppercase;
              letter-spacing:0.08em;font-weight:600">{label}</div>
  <div style="color:{value_color};font-size:1.7rem;font-weight:800;
              line-height:1.1;margin-top:4px">{value}</div>
  <div style="color:#374151;font-size:0.72rem;margin-top:4px">{sub}</div>
</div>
"""


def _top_kpis(pred: PredictionResult, df: pd.DataFrame | None) -> None:
    n_high_risk = sum(1 for d in pred.risky_devices if d.risk_score >= 0.65)
    n_alerts    = len(pred.security_alerts)
    infil_prob  = pred.overall_risk
    risk_color  = RISK_COLORS.get(pred.risk_level, "#ef4444")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(_kpi_card(
            "Overall Network Risk",
            f"{pred.overall_risk:.0%}",
            pred.risk_level,
            risk_color, risk_color,
        ), unsafe_allow_html=True)

    with c2:
        st.markdown(_kpi_card(
            "High-Risk Devices",
            str(n_high_risk),
            "Require immediate attention",
            "#ef4444", "#ef4444",
        ), unsafe_allow_html=True)

    with c3:
        st.markdown(_kpi_card(
            "Active Alerts",
            str(n_alerts),
            "Critical & High severity",
            "#7c3aed", "#a78bfa",
        ), unsafe_allow_html=True)

    with c4:
        st.markdown(_kpi_card(
            "Infiltration Probability",
            f"{infil_prob:.0%}",
            f"Stage: {pred.current_stage}",
            "#f59e0b", "#fbbf24",
        ), unsafe_allow_html=True)


# ── Attack forecast banner ────────────────────────────────────────────────────

def _attack_forecast_banner(pred: PredictionResult) -> None:
    curr_color = STAGE_COLORS.get(pred.current_stage, "#3b82f6")
    pred_color = STAGE_COLORS.get(pred.predicted_stage, "#ef4444")
    curr_icon  = STAGE_ICONS.get(pred.current_stage, "")
    pred_icon  = STAGE_ICONS.get(pred.predicted_stage, "")

    st.markdown(f"""
<div style="background:#0b1526;border:1px solid #1a2540;border-radius:8px;
     padding:14px 20px;display:flex;align-items:center;
     justify-content:space-between;margin-bottom:4px">
  <div style="display:flex;align-items:center;gap:20px">
    <div style="color:#374151;font-size:0.72rem;font-weight:600;
                text-transform:uppercase;letter-spacing:0.08em">Attack Forecast</div>
    <div style="display:flex;align-items:center;gap:10px">
      <div style="background:{curr_color}18;border:1px solid {curr_color}44;
           border-radius:6px;padding:6px 14px;text-align:center">
        <div style="color:#4b5563;font-size:0.62rem;text-transform:uppercase">Current Stage</div>
        <div style="color:{curr_color};font-weight:700;font-size:0.9rem;margin-top:2px">
          {curr_icon} {pred.current_stage}
        </div>
      </div>
      <div style="color:#1e3a5f;font-size:1.4rem;font-weight:300">→</div>
      <div style="background:{pred_color}18;border:1px solid {pred_color}55;
           border-radius:6px;padding:6px 14px;text-align:center">
        <div style="color:#4b5563;font-size:0.62rem;text-transform:uppercase">Predicted Next</div>
        <div style="color:{pred_color};font-weight:700;font-size:0.9rem;margin-top:2px">
          {pred_icon} {pred.predicted_stage}
        </div>
      </div>
    </div>
  </div>
  <div style="color:#374151;font-size:0.72rem">
    Forecast horizon: {pred.forecast_horizon} steps
    <span style="color:#1e293b;margin:0 6px">·</span>
    <span style="color:#f59e0b">DEMO — mock prediction</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Charts row ────────────────────────────────────────────────────────────────

def _charts_row(pred: PredictionResult, df: pd.DataFrame | None) -> None:
    col_l, col_r = st.columns([1.4, 1])

    with col_l:
        hours  = [f"{h:02d}:00" for h in range(0, 24, 2)]
        risk_v = [0.12, 0.10, 0.09, 0.11, 0.18, 0.32, 0.48, 0.61,
                  0.72, 0.80, 0.85, 0.87]
        fig = risk_timeline_chart(hours, risk_v)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_r:
        if df is not None:
            fig2 = traffic_volume_chart(df.head(10000))
        else:
            fig2 = stage_forecast_chart(pred.future_probabilities)
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})


# ── At-risk devices panel ─────────────────────────────────────────────────────
# ONLY shows HIGH/CRITICAL devices — alert logic enforced here

def _at_risk_devices_panel(pred: PredictionResult) -> None:
    high_risk = [d for d in pred.risky_devices if d.risk_score >= 0.65]

    section_header(
        "At-Risk Devices",
        "Alert sent only to HIGH / CRITICAL devices — low-risk devices not shown",
    )

    if not high_risk:
        st.markdown(
            '<div style="background:#052e16;border-radius:6px;padding:10px 14px;'
            'color:#4ade80;font-size:0.85rem">✅ No devices at HIGH or CRITICAL risk.</div>',
            unsafe_allow_html=True,
        )
        return

    for d in high_risk:
        risk_color = RISK_COLORS.get(d.risk_level, "#ef4444")
        pct        = int(d.risk_score * 100)
        stage_color = STAGE_COLORS.get(d.current_stage, "#3b82f6")
        pred_color  = STAGE_COLORS.get(d.predicted_stage, "#ef4444")

        st.markdown(f"""
<div style="background:#0b1526;border:1px solid {risk_color}33;
     border-left:3px solid {risk_color};border-radius:7px;
     padding:10px 16px;margin-bottom:6px;
     display:flex;align-items:center;justify-content:space-between">
  <div style="display:flex;align-items:center;gap:14px">
    <div>
      <span style="color:#f1f5f9;font-weight:700">{d.device_name}</span>
      <span style="color:#374151;font-size:0.75rem;margin-left:6px;
                   font-family:monospace">{d.ip}</span>
    </div>
    <div style="display:flex;align-items:center;gap:6px">
      <span style="background:{stage_color}18;color:{stage_color};
            border:1px solid {stage_color}44;border-radius:5px;
            padding:1px 8px;font-size:0.72rem">
        {STAGE_ICONS.get(d.current_stage,'')} {d.current_stage}
      </span>
      <span style="color:#1e3a5f">→</span>
      <span style="background:{pred_color}18;color:{pred_color};
            border:1px solid {pred_color}44;border-radius:5px;
            padding:1px 8px;font-size:0.72rem">
        {STAGE_ICONS.get(d.predicted_stage,'')} {d.predicted_stage}
      </span>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    <span style="color:{risk_color};font-size:1.2rem;font-weight:800">{pct}%</span>
    <span style="background:{risk_color}18;color:{risk_color};
          border:1px solid {risk_color}44;border-radius:10px;
          padding:2px 10px;font-size:0.7rem;font-weight:700">{d.risk_level}</span>
    <span style="background:#111827;color:#64748b;border:1px solid #1e293b;
          border-radius:5px;padding:2px 8px;font-size:0.7rem">
      ⚡ Device Alert Active
    </span>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Alert logic diagram ───────────────────────────────────────────────────────

def _alert_flow_note() -> None:
    st.markdown("""
<div style="background:#0a0f1e;border:1px solid #1a2540;border-radius:8px;
     padding:12px 18px;margin-bottom:12px;font-size:0.75rem;color:#374151">
  <span style="color:#334155;font-weight:600">Alert Routing:</span>
  &nbsp; Network Telemetry
  <span style="color:#1e3a5f">→</span> Risk Assessment
  <span style="color:#1e3a5f">→</span> Identify High-Risk Devices
  <span style="color:#1e3a5f">→</span>
  <span style="color:#ef4444">Device Alert</span>
  <span style="color:#1e3a5f"> + </span>
  <span style="color:#7c3aed">Admin / SOC Alert</span>
  &nbsp;·&nbsp;
  <span style="color:#1e293b">Low-risk devices: no alert</span>
</div>
""", unsafe_allow_html=True)


# ── Component status strip ────────────────────────────────────────────────────

def _system_status_strip() -> None:
    components = [
        ("Data Pipeline",      True),
        ("Feature Extraction", True),
        ("State Builder",      True),
        ("World Model",        False),
        ("Prediction Engine",  False),
        ("Alert Engine",       True),
        ("Explainability",     False),
    ]
    cols = st.columns(len(components))
    for col, (name, active) in zip(cols, components):
        color = "#22c55e" if active else "#1e3a5f"
        label = "Active" if active else "Demo"
        col.markdown(
            f'<div style="text-align:center;background:#0b1526;border-radius:6px;'
            f'padding:8px 4px;border:1px solid #1a2540">'
            f'<div style="color:{color};font-size:0.7rem">{"●" if active else "○"}</div>'
            f'<div style="color:#374151;font-size:0.62rem;margin-top:2px">{name}</div>'
            f'<div style="color:{color};font-size:0.6rem">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Public render ─────────────────────────────────────────────────────────────

def render(pred: PredictionResult, df: pd.DataFrame | None = None) -> None:

    # Live status strip
    _live_status_strip(df)

    # KPI row
    _top_kpis(pred, df)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Attack forecast banner
    _attack_forecast_banner(pred)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Charts
    _charts_row(pred, df)

    st.divider()

    # At-risk devices + alerts side by side
    col_dev, col_alerts = st.columns([1.05, 1])

    with col_dev:
        _alert_flow_note()
        _at_risk_devices_panel(pred)

    with col_alerts:
        section_header(
            "Security Alerts",
            "Admin / SOC feed — High-risk device events only",
        )
        render_alert_feed(pred.security_alerts)
        if pred.security_alerts:
            st.markdown(
                '<div style="text-align:right;margin-top:6px">'
                '<span style="color:#3b82f6;font-size:0.75rem;cursor:pointer">'
                '→ Full alert management on Alerts page</span></div>',
                unsafe_allow_html=True,
            )

    st.divider()

    section_header("System Component Status")
    _system_status_strip()
