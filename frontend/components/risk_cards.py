"""
components/risk_cards.py — High-risk device summary cards.

Renders a compact card for each device with a coloured risk indicator,
current/predicted stage badges, and a quick-action button row.
"""

from __future__ import annotations

import streamlit as st

from frontend.utils.constants import RISK_COLORS, RISK_BG_COLORS, STAGE_COLORS, STAGE_ICONS
from frontend.services.mock_predictions import DeviceRisk


def _risk_pill(level: str) -> str:
    color = RISK_COLORS.get(level, "#3b82f6")
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}55;'
        f'border-radius:12px;padding:2px 10px;font-size:0.72rem;font-weight:700">'
        f'{level}</span>'
    )


def _stage_pill(stage: str) -> str:
    color = STAGE_COLORS.get(stage, "#3b82f6")
    icon  = STAGE_ICONS.get(stage, "")
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}44;'
        f'border-radius:10px;padding:2px 8px;font-size:0.72rem">{icon} {stage}</span>'
    )


def device_risk_card(device: DeviceRisk, key_prefix: str = "") -> dict[str, bool]:
    """
    Render a single device risk card.
    Returns a dict of button states: {'investigate': bool, 'isolate': bool, 'dismiss': bool}
    """
    risk_color = RISK_COLORS.get(device.risk_level, "#3b82f6")
    bg_color   = RISK_BG_COLORS.get(device.risk_level, "#0f172a")
    pct        = int(device.risk_score * 100)

    st.markdown(
        f"""
<div style="
    background:{bg_color};
    border: 1px solid {risk_color}44;
    border-left: 4px solid {risk_color};
    border-radius:10px;
    padding:14px 18px;
    margin-bottom:10px;
">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <div>
      <span style="color:#f1f5f9;font-size:1rem;font-weight:700">{device.device_name}</span>
      <span style="color:#64748b;font-size:0.8rem;margin-left:8px">{device.ip}</span>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <span style="color:{risk_color};font-size:1.4rem;font-weight:800">{pct}%</span>
      {_risk_pill(device.risk_level)}
    </div>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px">
    <span style="color:#94a3b8;font-size:0.78rem">Current:</span>
    {_stage_pill(device.current_stage)}
    <span style="color:#64748b;font-size:0.78rem">→ Predicted:</span>
    {_stage_pill(device.predicted_stage)}
  </div>
  <div style="color:#94a3b8;font-size:0.78rem;margin-top:6px">
    ⚡ {device.recommended_action}
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    key = f"{key_prefix}_{device.device_name.replace('-','_')}"
    col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
    investigate = col1.button("🔍 Investigate",     key=f"inv_{key}")
    isolate     = col2.button("🔒 Sim. Isolate",    key=f"iso_{key}")
    dismiss     = col3.button("✕ Dismiss",           key=f"dis_{key}")

    return {"investigate": investigate, "isolate": isolate, "dismiss": dismiss}


def risk_summary_strip(devices: list[DeviceRisk]) -> None:
    """
    Compact horizontal strip showing risk counts by level.
    """
    from collections import Counter
    counts = Counter(d.risk_level for d in devices)

    cols = st.columns(4)
    for col, level in zip(cols, ["CRITICAL", "HIGH", "MEDIUM", "LOW"]):
        c = counts.get(level, 0)
        color = RISK_COLORS[level]
        col.markdown(
            f'<div style="text-align:center;background:#1e293b;border-radius:8px;'
            f'padding:10px;border:1px solid {color}33">'
            f'<div style="color:{color};font-size:1.5rem;font-weight:800">{c}</div>'
            f'<div style="color:#64748b;font-size:0.72rem;text-transform:uppercase">{level}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
