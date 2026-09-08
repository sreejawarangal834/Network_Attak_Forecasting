"""
pages/network_state.py — Network State Visualisation

Shows the current network state feature vector S_t and a historical
sequence S_t-n → … → S_t → (placeholder future states S_t+1 … S_t+3).

The state sequence section is a placeholder for World Model predictions.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.components.charts import network_state_radar, state_sequence_chart
from frontend.components.metrics import (
    demo_badge,
    info_metric_card,
    section_header,
)
from frontend.services.mock_predictions import PredictionResult
from frontend.services.state_builder import (
    STATE_FEATURES,
    build_state_sequence,
    get_current_state,
)
from frontend.utils.constants import COLOR_TEXT_MUTED


def _state_feature_grid(state: dict) -> None:
    """Render all state features as metric cards in a 4-column grid."""
    display = [
        ("Active Flows",       "active_flows",       "flows"),
        ("Packets / sec",      "packets_per_sec",     "pkt/s"),
        ("Unique Src IPs",     "unique_src_ips",      "hosts"),
        ("Unique Dst IPs",     "unique_dst_ips",      "hosts"),
        ("Unique Dst Ports",   "unique_ports",        "ports"),
        ("Avg Packet Size",    "avg_packet_size",     "bytes"),
        ("SYN Rate",           "syn_rate",            "pkt/s"),
        ("ACK Rate",           "ack_rate",            "pkt/s"),
        ("RST Rate",           "rst_rate",            "pkt/s"),
        ("FIN Rate",           "fin_rate",            "pkt/s"),
        ("Avg TTL",            "avg_ttl",             "hops"),
        ("TTL Std Dev",        "ttl_std",             "hops"),
    ]

    cols = st.columns(4)
    for i, (label, key, unit) in enumerate(display):
        val = state.get(key, 0)
        formatted = f"{val:,.1f} {unit}" if isinstance(val, float) else f"{val:,} {unit}"
        with cols[i % 4]:
            info_metric_card(label, formatted)


def _future_state_placeholder() -> None:
    """
    Placeholder for World Model predicted future states.
    Will be replaced with real predictions once the model is integrated.
    """
    st.markdown(
        '<div style="background:#1e2d40;border:2px dashed #1d4ed8;border-radius:10px;'
        'padding:20px 24px;margin-top:4px">'
        '<div style="color:#60a5fa;font-weight:700;font-size:0.9rem;margin-bottom:8px">'
        '🔮 Future State Forecast — World Model Placeholder</div>'
        '<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">'
        + "".join(_future_state_card(t) for t in range(4))
        + '</div>'
        '<div style="color:#475569;font-size:0.75rem;margin-top:12px">'
        '⚙️ This section will display S_t+1 → S_t+2 → S_t+3 predictions '
        'from the World Model (LSTM/Transformer) once the ML backend is connected.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _future_state_card(t: int) -> str:
    if t == 0:
        label = "S_t (now)"
        bg    = "#1e3a5f"
        color = "#60a5fa"
    else:
        label = f"S_t+{t}"
        bg    = "#1e293b"
        color = "#475569"
    arrow = '<span style="color:#334155;font-size:1.2rem;margin:0 4px">→</span>' if t > 0 else ""
    return f"""
{arrow}
<div style="background:{bg};border:1px solid {color}44;border-radius:8px;
     padding:12px 16px;text-align:center;min-width:110px">
  <div style="color:{color};font-weight:700;font-size:0.85rem">{label}</div>
  <div style="color:#334155;font-size:0.72rem;margin-top:4px">
    {'Current state' if t == 0 else 'Model prediction'}
  </div>
  <div style="color:#1d3557;font-size:0.7rem;margin-top:6px">
    {'Calculated' if t == 0 else '⚙️ Pending model'}
  </div>
</div>
"""


def _sequence_section(states: list[dict], df: pd.DataFrame) -> None:
    """
    Historical state feature timeline + future placeholder.
    Let the user pick which feature to visualise.
    """
    section_header(
        "State Feature Timeline  S_t-n → S_t",
        "How key features changed across recent time windows",
    )

    feature_options = {
        "SYN Rate":          "syn_rate",
        "ACK Rate":          "ack_rate",
        "RST Rate":          "rst_rate",
        "Packets / sec":     "packets_per_sec",
        "Unique Src IPs":    "unique_src_ips",
        "Unique Dst Ports":  "unique_ports",
        "Avg Packet Size":   "avg_packet_size",
        "Avg TTL":           "avg_ttl",
    }

    selected_label = st.selectbox(
        "Feature to visualise",
        list(feature_options.keys()),
        index=0,
        key="ns_feature_select",
    )
    feature = feature_options[selected_label]
    fig = state_sequence_chart(states, feature=feature)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ── Public render function ────────────────────────────────────────────────────

def render(pred: PredictionResult, df: pd.DataFrame | None = None) -> None:
    st.markdown(
        '<h2 style="color:#f1f5f9;margin-bottom:0">🔬 Network State</h2>'
        '<p style="color:#64748b;margin-top:2px">'
        'Current network state feature vector S_t derived from traffic data</p>',
        unsafe_allow_html=True,
    )

    # ── Current state ─────────────────────────────────────────────────────────
    section_header("Current State Features (S_t)")

    if df is not None:
        state = get_current_state(df)
        st.caption("Values calculated from the most recent 3,000 packets of the loaded dataset.")
    else:
        state = pred.network_state
        demo_badge()
        st.caption("No dataset loaded — showing mock state values.")

    col_grid, col_radar = st.columns([1.6, 1])
    with col_grid:
        _state_feature_grid(state)
    with col_radar:
        fig = network_state_radar(state)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.divider()

    # ── Historical sequence ───────────────────────────────────────────────────
    if df is not None:
        with st.spinner("Building state sequence…"):
            states = build_state_sequence(df, n_windows=10, window_size=500)
        _sequence_section(states, df)
    else:
        section_header("State Feature Timeline")
        st.info("Upload traffic data on the Traffic Upload page to see the state timeline.")

    st.divider()

    # ── Future state placeholder ──────────────────────────────────────────────
    section_header(
        "Future State Forecast  S_t → S_t+3",
        "World Model predictions (not yet connected)",
    )
    _future_state_placeholder()

    st.divider()

    # ── State feature reference table ─────────────────────────────────────────
    with st.expander("📖 State Feature Reference"):
        feature_info = [
            ("active_flows",       "Estimated concurrent network flows",           "count"),
            ("packets_per_sec",    "Packet arrival rate in the window",             "pkt/s"),
            ("unique_src_ips",     "Number of distinct source addresses",           "count"),
            ("unique_dst_ips",     "Number of distinct destination addresses",      "count"),
            ("unique_ports",       "Distinct destination ports observed",           "count"),
            ("avg_packet_size",    "Mean packet payload length",                    "bytes"),
            ("syn_rate",           "SYN flag packets per second",                   "pkt/s"),
            ("ack_rate",           "ACK flag packets per second",                   "pkt/s"),
            ("rst_rate",           "RST flag packets per second",                   "pkt/s"),
            ("fin_rate",           "FIN flag packets per second",                   "pkt/s"),
            ("avg_ttl",            "Mean time-to-live field value",                 "hops"),
            ("ttl_std",            "Std deviation of TTL (spoofing indicator)",     "hops"),
            ("byte_rate",          "Total bytes transferred per second",            "B/s"),
            ("dst_port_entropy",   "Shannon entropy of destination port distribution","bits"),
        ]
        ref_df = pd.DataFrame(feature_info, columns=["Feature", "Description", "Unit"])
        st.dataframe(ref_df, use_container_width=True, hide_index=True)
