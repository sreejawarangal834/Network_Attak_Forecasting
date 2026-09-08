"""
components/device_table.py — Sortable device risk table.

Renders a colour-coded st.dataframe table of all devices with risk scores.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.utils.constants import RISK_COLORS, STAGE_ICONS
from frontend.services.mock_predictions import DeviceRisk


def devices_to_df(devices: list[DeviceRisk]) -> pd.DataFrame:
    """Convert a list of DeviceRisk objects to a display-ready DataFrame."""
    rows = []
    for d in devices:
        rows.append({
            "Device":          d.device_name,
            "IP Address":      d.ip,
            "Risk Score":      f"{d.risk_score:.0%}",
            "Risk Level":      d.risk_level,
            "Current Stage":   f"{STAGE_ICONS.get(d.current_stage, '')} {d.current_stage}",
            "Predicted Stage": f"{STAGE_ICONS.get(d.predicted_stage, '')} {d.predicted_stage}",
            "Alert Status":    d.alert_status,
            "Recommended Action": d.recommended_action,
            "_risk_score_raw": d.risk_score,   # hidden, used for sorting
        })
    df = pd.DataFrame(rows)
    return df.sort_values("_risk_score_raw", ascending=False).drop(columns=["_risk_score_raw"])


def render_device_table(devices: list[DeviceRisk]) -> None:
    """
    Render the full device risk table with row highlighting via pandas Styler.
    """
    df = devices_to_df(devices)

    def _row_style(row: pd.Series):
        level = row.get("Risk Level", "LOW")
        color = {
            "CRITICAL": "rgba(124,58,237,0.15)",
            "HIGH":     "rgba(239,68,68,0.12)",
            "MEDIUM":   "rgba(245,158,11,0.10)",
            "LOW":      "rgba(34,197,94,0.06)",
        }.get(level, "")
        return [f"background-color:{color}"] * len(row)

    styled = df.style.apply(_row_style, axis=1)
    st.dataframe(styled, use_container_width=True, height=280)


def render_compact_device_list(devices: list[DeviceRisk]) -> None:
    """
    A compact 3-column grid of device mini-cards for the Dashboard.
    Only shows devices with risk ≥ 0.40 (Medium and above).
    """
    visible = [d for d in devices if d.risk_score >= 0.40]
    if not visible:
        st.info("No devices currently at elevated risk.")
        return

    cols = st.columns(3)
    for i, d in enumerate(visible):
        col = cols[i % 3]
        color = RISK_COLORS.get(d.risk_level, "#3b82f6")
        pct   = int(d.risk_score * 100)
        with col:
            st.markdown(
                f"""
<div style="background:#1e293b;border:1px solid {color}44;border-top:3px solid {color};
     border-radius:8px;padding:12px;margin-bottom:8px">
  <div style="font-weight:700;color:#f1f5f9">{d.device_name}</div>
  <div style="color:#64748b;font-size:0.75rem">{d.ip}</div>
  <div style="display:flex;justify-content:space-between;margin-top:8px;align-items:center">
    <span style="color:{color};font-size:1.2rem;font-weight:800">{pct}%</span>
    <span style="color:{color};font-size:0.72rem;background:{color}22;
          border-radius:10px;padding:1px 8px">{d.risk_level}</span>
  </div>
  <div style="color:#94a3b8;font-size:0.75rem;margin-top:4px">
    {STAGE_ICONS.get(d.current_stage,'')} {d.current_stage}
    → {STAGE_ICONS.get(d.predicted_stage,'')} {d.predicted_stage}
  </div>
</div>
                """,
                unsafe_allow_html=True,
            )
