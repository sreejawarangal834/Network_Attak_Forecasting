"""
pages/attack_stages.py — Attack Stages Detail

Full breakdown of the five-stage kill chain with MITRE ATT&CK mapping
placeholders and per-stage detail cards.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.components.attack_path import (
    render_attack_pipeline,
    render_mitre_placeholder,
    render_stage_detail_cards,
)
from frontend.components.metrics import demo_badge, section_header
from frontend.services.mock_predictions import PredictionResult
from frontend.utils.constants import (
    ATTACK_STAGES,
    STAGE_COLORS,
    STAGE_DESCRIPTIONS,
    STAGE_ICONS,
)


def _stage_selector(pred: PredictionResult) -> str:
    """Let the user drill into a specific stage."""
    return st.selectbox(
        "Drill into stage",
        ATTACK_STAGES,
        index=ATTACK_STAGES.index(pred.current_stage),
        key="stage_drill_select",
    )


def _stage_detail_panel(stage: str, pred: PredictionResult) -> None:
    """Expanded detail for the selected stage."""
    color = STAGE_COLORS[stage]
    icon  = STAGE_ICONS[stage]
    desc  = STAGE_DESCRIPTIONS[stage]

    # Is this stage in the current/predicted path?
    curr_idx  = ATTACK_STAGES.index(pred.current_stage)  if pred.current_stage  in ATTACK_STAGES else 0
    pred_idx  = ATTACK_STAGES.index(pred.predicted_stage) if pred.predicted_stage in ATTACK_STAGES else 0
    sel_idx   = ATTACK_STAGES.index(stage)

    if sel_idx < curr_idx:
        status_text  = "✅ Observed / Past"
        status_color = "#22c55e"
    elif sel_idx == curr_idx:
        status_text  = "⚡ ACTIVE — Current Stage"
        status_color = color
    elif sel_idx == pred_idx:
        status_text  = "🔮 PREDICTED — Next Stage"
        status_color = color
    elif sel_idx > pred_idx:
        status_text  = "⏳ Future / Not Yet Reached"
        status_color = "#475569"
    else:
        status_text  = ""
        status_color = "#475569"

    st.markdown(
        f"""
<div style="background:#0f172a;border:2px solid {color}55;border-radius:12px;
     padding:20px 24px;margin-bottom:12px">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
    <span style="font-size:2.2rem">{icon}</span>
    <div>
      <div style="color:#f1f5f9;font-size:1.3rem;font-weight:800">{stage}</div>
      <div style="color:{status_color};font-size:0.82rem;font-weight:600">{status_text}</div>
    </div>
  </div>
  <div style="color:#cbd5e1;font-size:0.9rem;line-height:1.6">{desc}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


_STAGE_INDICATORS = {
    "Benign": [
        "Normal ACK/data traffic pattern",
        "Low SYN rate (< 2/s)",
        "Consistent TTL values",
        "Low port entropy",
    ],
    "Reconnaissance": [
        "High SYN rate with low ACK response",
        "Wide range of destination ports (entropy > 3.5 bits)",
        "ICMP echo bursts to /24 subnet",
        "Rapidly increasing unique destination IPs",
        "External source IP scanning internal range",
    ],
    "BruteForce": [
        "Repeated connections to ports 22, 3389, 21",
        "High RST rate (failed auth attempts)",
        "Short inter-arrival time (automated tool pattern)",
        "Same source IP → same dest IP, varying credentials",
        "TCP window size anomaly",
    ],
    "LateralMovement": [
        "Internal east-west SMB/RDP traffic (ports 445, 139, 3389)",
        "Unusual host-to-host communication pairs",
        "Credential reuse across internal hosts",
        "WMI / PsExec signatures in packet payloads",
        "Elevated packet size for internal flows",
    ],
    "CommandAndControl": [
        "Regular beaconing intervals to external IP",
        "Destination in known C2 threat intelligence feed",
        "Low TTL values (proxy/tunnel hop)",
        "Encrypted payload to non-standard ports",
        "DNS queries to newly registered / DGA domains",
    ],
}

_STAGE_DEFENSIVE_ACTIONS = {
    "Benign":             ["Continue standard monitoring", "Log baseline traffic metrics"],
    "Reconnaissance":     ["Block scanning source IP at perimeter", "Enable honeypot detection",
                           "Alert SOC to probing activity"],
    "BruteForce":         ["Rate-limit auth attempts", "Enforce MFA immediately",
                           "Lock accounts after N failures", "Notify affected host owners"],
    "LateralMovement":    ["Segment affected VLAN", "Revoke compromised credentials",
                           "Enable full packet capture on segment", "Escalate to SOC Tier-2"],
    "CommandAndControl":  ["Isolate beaconing host immediately", "Block C2 IP/domain at firewall",
                           "Preserve forensic image of host", "Escalate to incident response team"],
}


def _indicators_and_actions(stage: str) -> None:
    col_ind, col_act = st.columns(2)

    with col_ind:
        st.markdown(
            '<div style="color:#94a3b8;font-size:0.75rem;font-weight:600;'
            'text-transform:uppercase;margin-bottom:6px">Detection Indicators</div>',
            unsafe_allow_html=True,
        )
        for ind in _STAGE_INDICATORS.get(stage, []):
            st.markdown(
                f'<div style="background:#1e293b;border-radius:5px;padding:6px 12px;'
                f'margin-bottom:4px;color:#cbd5e1;font-size:0.82rem">🔍 {ind}</div>',
                unsafe_allow_html=True,
            )

    with col_act:
        st.markdown(
            '<div style="color:#94a3b8;font-size:0.75rem;font-weight:600;'
            'text-transform:uppercase;margin-bottom:6px">Defensive Actions</div>',
            unsafe_allow_html=True,
        )
        for act in _STAGE_DEFENSIVE_ACTIONS.get(stage, []):
            st.markdown(
                f'<div style="background:#1e293b;border-radius:5px;padding:6px 12px;'
                f'margin-bottom:4px;color:#cbd5e1;font-size:0.82rem">⚡ {act}</div>',
                unsafe_allow_html=True,
            )


# ── Public render function ────────────────────────────────────────────────────

def render(pred: PredictionResult, df: pd.DataFrame | None = None) -> None:
    st.markdown(
        '<h2 style="color:#f1f5f9;margin-bottom:0">⚔️ Attack Stages</h2>'
        '<p style="color:#64748b;margin-top:2px">'
        'Cyber kill-chain stages with indicators and MITRE ATT&amp;CK mapping</p>',
        unsafe_allow_html=True,
    )

    # Pipeline overview
    section_header("Kill-Chain Pipeline Overview")
    render_attack_pipeline(pred.current_stage, pred.predicted_stage)

    st.divider()

    # All-stage reference cards
    section_header("Stage Reference Cards")
    render_stage_detail_cards()

    st.divider()

    # Drill-down panel
    section_header("Stage Deep-Dive")
    selected_stage = _stage_selector(pred)
    _stage_detail_panel(selected_stage, pred)
    _indicators_and_actions(selected_stage)

    st.divider()

    # MITRE mapping placeholder
    section_header(
        "MITRE ATT&CK Mapping",
        "Technique mapping configuration — placeholder until mapping table is populated",
    )
    demo_badge()
    render_mitre_placeholder(selected_stage)
