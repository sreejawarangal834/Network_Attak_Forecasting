"""
components/alert_cards.py — Security alert card renderer.

Renders SOC-style alert cards for the Alerts & Response page.
Button actions simulate UI state only — no real network operations.
"""

from __future__ import annotations

import streamlit as st

from frontend.utils.constants import RISK_COLORS, STAGE_COLORS, STAGE_ICONS
from frontend.services.mock_predictions import SecurityAlert

# Severity → colour mapping
_SEV_COLORS = {
    "CRITICAL": "#7c3aed",
    "HIGH":     "#ef4444",
    "WARNING":  "#f59e0b",
    "INFO":     "#3b82f6",
}

_SEV_ICONS = {
    "CRITICAL": "🚨",
    "HIGH":     "⚠️",
    "WARNING":  "🔶",
    "INFO":     "ℹ️",
}


def render_alert_card(alert: SecurityAlert, key_prefix: str = "") -> dict[str, bool]:
    """
    Render a full SOC alert card.
    Returns {'investigate': bool, 'isolate': bool, 'dismiss': bool}.

    NOTE: Buttons simulate UI state only.
    No real network changes are made.
    """
    sev_color  = _SEV_COLORS.get(alert.severity, "#3b82f6")
    sev_icon   = _SEV_ICONS.get(alert.severity, "ℹ️")
    stage_color = STAGE_COLORS.get(alert.current_stage, "#3b82f6")
    pred_color  = STAGE_COLORS.get(alert.predicted_stage, "#3b82f6")
    pct         = int(alert.risk_probability * 100)

    # Build explanation bullets
    bullets_html = "".join(
        f'<li style="margin-bottom:3px">{e}</li>' for e in alert.explanation
    )
    actions_html = "".join(
        f'<li style="margin-bottom:3px">{a}</li>' for a in alert.recommended_actions
    )

    st.markdown(
        f"""
<div style="
    background:#0f172a;
    border: 1px solid {sev_color}55;
    border-left: 5px solid {sev_color};
    border-radius:10px;
    padding:16px 20px;
    margin-bottom:14px;
">
  <!-- Header row -->
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
    <div>
      <span style="color:{sev_color};font-size:0.85rem;font-weight:800;
                   text-transform:uppercase;letter-spacing:0.06em">
        {sev_icon} {alert.severity} SECURITY ALERT
      </span>
      <span style="color:#475569;font-size:0.75rem;margin-left:12px">{alert.alert_id}</span>
    </div>
    <span style="color:#64748b;font-size:0.75rem">{alert.timestamp}</span>
  </div>

  <!-- Device + risk row -->
  <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:10px">
    <div>
      <span style="color:#94a3b8;font-size:0.75rem">Device</span>
      <div style="color:#f1f5f9;font-weight:700;font-size:1rem">{alert.device}</div>
    </div>
    <div>
      <span style="color:#94a3b8;font-size:0.75rem">Source IP</span>
      <div style="color:#f1f5f9;font-family:monospace">{alert.src_ip}</div>
    </div>
    <div>
      <span style="color:#94a3b8;font-size:0.75rem">Target IP</span>
      <div style="color:#f1f5f9;font-family:monospace">{alert.target_ip}</div>
    </div>
    <div>
      <span style="color:#94a3b8;font-size:0.75rem">Risk</span>
      <div style="color:{sev_color};font-size:1.2rem;font-weight:800">{pct}%</div>
    </div>
  </div>

  <!-- Stage pills -->
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
    <span style="color:#94a3b8;font-size:0.78rem">Stage:</span>
    <span style="background:{stage_color}22;color:{stage_color};border:1px solid {stage_color}44;
                 border-radius:10px;padding:2px 10px;font-size:0.78rem">
      {STAGE_ICONS.get(alert.current_stage,'')} {alert.current_stage}
    </span>
    <span style="color:#475569">→</span>
    <span style="background:{pred_color}22;color:{pred_color};border:1px solid {pred_color}44;
                 border-radius:10px;padding:2px 10px;font-size:0.78rem">
      {STAGE_ICONS.get(alert.predicted_stage,'')} {alert.predicted_stage}
    </span>
  </div>

  <!-- Two-column detail -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
    <div>
      <div style="color:#94a3b8;font-size:0.75rem;font-weight:600;
                  text-transform:uppercase;margin-bottom:4px">Indicators</div>
      <ul style="color:#cbd5e1;font-size:0.82rem;margin:0;padding-left:16px">
        {bullets_html}
      </ul>
    </div>
    <div>
      <div style="color:#94a3b8;font-size:0.75rem;font-weight:600;
                  text-transform:uppercase;margin-bottom:4px">Recommended Actions</div>
      <ul style="color:#cbd5e1;font-size:0.82rem;margin:0;padding-left:16px">
        {actions_html}
      </ul>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    key = f"{key_prefix}_{alert.alert_id}"
    col1, col2, col3, col4 = st.columns([1, 1, 1, 4])
    investigate = col1.button("🔍 Investigate",   key=f"inv_{key}")
    isolate     = col2.button("🔒 Sim. Isolate",  key=f"iso_{key}",
                               help="Simulates network isolation — no real action taken.")
    dismiss     = col3.button("✕ Dismiss",         key=f"dis_{key}")

    return {"investigate": investigate, "isolate": isolate, "dismiss": dismiss}


def render_alert_feed(alerts: list[SecurityAlert]) -> None:
    """
    Render a compact scrollable alert feed (used on Dashboard).
    """
    if not alerts:
        st.info("No active alerts.")
        return

    for alert in alerts[:5]:   # show latest 5 on dashboard
        sev_color = _SEV_COLORS.get(alert.severity, "#3b82f6")
        sev_icon  = _SEV_ICONS.get(alert.severity, "ℹ️")
        pct       = int(alert.risk_probability * 100)

        st.markdown(
            f"""
<div style="background:#1e293b;border-left:3px solid {sev_color};border-radius:6px;
     padding:8px 12px;margin-bottom:6px;display:flex;
     justify-content:space-between;align-items:center">
  <div>
    <span style="color:{sev_color};font-size:0.78rem;font-weight:700">
      {sev_icon} {alert.severity}
    </span>
    <span style="color:#f1f5f9;font-size:0.85rem;margin-left:8px;font-weight:600">
      {alert.device}
    </span>
    <span style="color:#64748b;font-size:0.78rem;margin-left:6px">
      {alert.current_stage} → {alert.predicted_stage}
    </span>
  </div>
  <div style="text-align:right">
    <div style="color:{sev_color};font-weight:700">{pct}%</div>
    <div style="color:#475569;font-size:0.7rem">{alert.timestamp[-8:]}</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )
