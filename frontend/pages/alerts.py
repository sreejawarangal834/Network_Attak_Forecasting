"""
pages/alerts.py — Alerts & Response

Two-section layout:
  A. At-Risk Devices — targeted device-level alerts only for high-risk hosts
  B. Admin/SOC Security Alerts — centralised alert feed

IMPORTANT: All action buttons (Investigate, Sim. Isolate, Dismiss) only
simulate UI state changes. No real network isolation or firewall rules are applied.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.components.alert_cards import render_alert_card
from frontend.components.device_table import render_device_table
from frontend.components.metrics import demo_badge, info_metric_card, section_header
from frontend.components.risk_cards import device_risk_card, risk_summary_strip
from frontend.services.mock_predictions import PredictionResult
from frontend.utils.constants import RISK_COLORS


# ── Simulated action handling ─────────────────────────────────────────────────

def _handle_action(action: str, device_name: str) -> None:
    """Log a simulated action to session state for display feedback."""
    log = st.session_state.setdefault("action_log", [])
    log.insert(0, f"[SIMULATED] {action} → {device_name}")
    if len(log) > 20:
        log.pop()


def _action_log_panel() -> None:
    log = st.session_state.get("action_log", [])
    if not log:
        return
    with st.expander(f"📋 Simulated Action Log ({len(log)} entries)", expanded=False):
        for entry in log:
            st.markdown(
                f'<div style="background:#1e293b;border-left:2px solid #3b82f6;'
                f'border-radius:4px;padding:4px 10px;margin-bottom:3px;'
                f'color:#94a3b8;font-size:0.78rem">{entry}</div>',
                unsafe_allow_html=True,
            )
        if st.button("Clear Log", key="clear_action_log"):
            st.session_state["action_log"] = []
            st.rerun()


# ── Section A — At-Risk Devices ───────────────────────────────────────────────

def _section_at_risk_devices(pred: PredictionResult) -> None:
    section_header(
        "A. At-Risk Devices",
        "Only devices above risk threshold receive alerts. Low-risk devices are not shown.",
    )

    # Filter to high-risk and above
    high_risk = [d for d in pred.risky_devices if d.risk_score >= 0.65]
    medium    = [d for d in pred.risky_devices if 0.40 <= d.risk_score < 0.65]
    low       = [d for d in pred.risky_devices if d.risk_score < 0.40]

    # Risk summary strip
    risk_summary_strip(pred.risky_devices)
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Alert policy note
    st.markdown(
        '<div style="background:#1e293b;border-left:3px solid #f59e0b;border-radius:5px;'
        'padding:8px 14px;font-size:0.8rem;color:#fbbf24;margin-bottom:12px">'
        '⚡ <b>Alert Policy:</b> Device-level alerts are sent only to HIGH and CRITICAL risk '
        'devices. Medium-risk devices are monitored. Low-risk devices receive no alerts.</div>',
        unsafe_allow_html=True,
    )

    # High / Critical devices
    if high_risk:
        st.markdown("**🔴 HIGH / CRITICAL Risk Devices — Alerts Active**")
        for d in high_risk:
            actions = device_risk_card(d, key_prefix="alerts_page")
            if actions["investigate"]:
                _handle_action("Investigate", d.device_name)
                st.info(f"🔍 [SIMULATED] Launched investigation on {d.device_name}")
            if actions["isolate"]:
                _handle_action("Simulate Isolation", d.device_name)
                st.warning(
                    f"🔒 [SIMULATED] Isolation order sent for {d.device_name}. "
                    "**No real network changes were made.**"
                )
            if actions["dismiss"]:
                _handle_action("Dismiss", d.device_name)
                st.success(f"✕ Alert dismissed for {d.device_name}.")
    else:
        st.success("No devices currently at HIGH or CRITICAL risk.")

    # Medium devices
    if medium:
        with st.expander(f"🟡 MEDIUM Risk Devices — Monitoring ({len(medium)} devices)"):
            for d in medium:
                color = RISK_COLORS["MEDIUM"]
                st.markdown(
                    f'<div style="background:#1e293b;border-left:3px solid {color};'
                    f'border-radius:6px;padding:8px 14px;margin-bottom:6px;'
                    f'display:flex;justify-content:space-between;align-items:center">'
                    f'<div><b style="color:#f1f5f9">{d.device_name}</b> '
                    f'<span style="color:#64748b;font-size:0.78rem">{d.ip}</span></div>'
                    f'<span style="color:{color};font-weight:700">'
                    f'{d.risk_score:.0%} — {d.risk_level}</span></div>',
                    unsafe_allow_html=True,
                )

    # Low risk summary (not individually alerted)
    if low:
        st.markdown(
            f'<div style="color:#4ade80;font-size:0.82rem;margin-top:4px">'
            f'✅ {len(low)} device(s) at LOW risk — no alerts sent.</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # Full table
    section_header("All Devices — Risk Overview")
    render_device_table(pred.risky_devices)


# ── Section B — SOC Security Alerts ──────────────────────────────────────────

def _section_soc_alerts(pred: PredictionResult) -> None:
    section_header(
        "B. Admin / SOC Security Alerts",
        "Centralised alert feed — only high-risk device alerts escalated here",
    )

    # Alert stats strip
    n_crit = sum(1 for a in pred.security_alerts if a.severity == "CRITICAL")
    n_high = sum(1 for a in pred.security_alerts if a.severity == "HIGH")
    n_warn = sum(1 for a in pred.security_alerts if a.severity == "WARNING")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        info_metric_card("Total Alerts",    str(len(pred.security_alerts)), color="#3b82f6")
    with c2:
        info_metric_card("Critical",        str(n_crit), color=RISK_COLORS["CRITICAL"])
    with c3:
        info_metric_card("High",            str(n_high), color=RISK_COLORS["HIGH"])
    with c4:
        info_metric_card("Warning",         str(n_warn), color=RISK_COLORS["MEDIUM"])

    # Filter controls
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    col_sev, col_status = st.columns([1, 1])
    with col_sev:
        sev_filter = st.multiselect(
            "Filter by severity",
            ["CRITICAL", "HIGH", "WARNING", "INFO"],
            default=["CRITICAL", "HIGH"],
            key="alert_sev_filter",
        )
    with col_status:
        status_filter = st.selectbox(
            "Status",
            ["All", "Active", "Investigating", "Dismissed"],
            key="alert_status_filter",
        )

    # Apply filters
    alerts = pred.security_alerts
    if sev_filter:
        alerts = [a for a in alerts if a.severity in sev_filter]
    if status_filter != "All":
        alerts = [a for a in alerts if a.status == status_filter]

    if not alerts:
        st.info("No alerts match the selected filters.")
        return

    for alert in alerts:
        actions = render_alert_card(alert, key_prefix="soc")
        if actions["investigate"]:
            _handle_action("Investigate", alert.device)
            st.info(f"🔍 [SIMULATED] Investigation workflow triggered for {alert.device}.")
        if actions["isolate"]:
            _handle_action("Simulate Isolation", alert.device)
            st.warning(
                f"🔒 [SIMULATED] Isolation command sent for **{alert.device}**. "
                "**This is a simulation — no real network changes were made.**"
            )
        if actions["dismiss"]:
            _handle_action("Dismiss", alert.device)
            st.success(f"✕ Alert {alert.alert_id} dismissed.")


# ── Public render function ────────────────────────────────────────────────────

def render(pred: PredictionResult, df: pd.DataFrame | None = None) -> None:
    st.markdown(
        '<h2 style="color:#f1f5f9;margin-bottom:0">🚨 Alerts &amp; Response</h2>'
        '<p style="color:#64748b;margin-top:2px">'
        'Targeted device alerts and centralised SOC alert management</p>',
        unsafe_allow_html=True,
    )

    demo_badge()

    st.markdown(
        '<div style="background:#1e2d40;border-left:3px solid #3b82f6;border-radius:5px;'
        'padding:8px 14px;font-size:0.8rem;color:#93c5fd;margin-bottom:12px">'
        'ℹ️ <b>Important:</b> Alert actions (Investigate, Simulate Isolation, Dismiss) '
        'only update UI state. No real firewall rules, host isolation, or network '
        'changes are performed in this demo.</div>',
        unsafe_allow_html=True,
    )

    _section_at_risk_devices(pred)
    _section_soc_alerts(pred)

    _action_log_panel()
