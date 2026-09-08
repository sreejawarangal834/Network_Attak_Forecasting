"""
pages/upload.py — Traffic Upload & Analysis

Allows the user to upload a CSV file or use the bundled simulated dataset.
Displays basic statistics once a file is loaded, and exposes the
"Analyze Traffic" trigger that pushes data into session state.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.components.charts import (
    attack_distribution_bar,
    protocol_pie_chart,
    traffic_volume_chart,
)
from frontend.components.metrics import demo_badge, info_metric_card, section_header
from frontend.services.data_loader import get_summary_stats, load_traffic_data
from frontend.utils.constants import DATA_SOURCES, SIMULATED_DATA_PATH


# ── Helper ────────────────────────────────────────────────────────────────────

def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.0f} s"
    if seconds < 3600:
        return f"{seconds/60:.1f} min"
    return f"{seconds/3600:.1f} hr"


def _stats_row(stats: dict) -> None:
    """Top-level summary KPIs."""
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        info_metric_card("Total Records",    f"{stats['total_records']:,}")
    with c2:
        info_metric_card("Unique Src IPs",   str(stats["unique_src_ips"]))
    with c3:
        info_metric_card("Unique Dst IPs",   str(stats["unique_dst_ips"]))
    with c4:
        info_metric_card("Attack Traffic",   f"{stats['attack_ratio']:.1%}",
                         sub="of all records", color="#ef4444")
    with c5:
        info_metric_card("Avg Packet Size",  f"{stats['avg_packet_size']:.0f} B")
    with c6:
        info_metric_card("Duration",         _format_duration(stats.get("duration_s")))


def _time_range_info(stats: dict) -> None:
    t0 = stats.get("time_start")
    t1 = stats.get("time_end")
    if t0 and t1:
        st.markdown(
            f'<div style="background:#1e293b;border-radius:6px;padding:8px 14px;'
            f'font-size:0.82rem;color:#94a3b8">'
            f'🕐 Time range: <b style="color:#f1f5f9">{t0}</b> → '
            f'<b style="color:#f1f5f9">{t1}</b></div>',
            unsafe_allow_html=True,
        )


def _distribution_charts(stats: dict, df: pd.DataFrame) -> None:
    col_proto, col_attack = st.columns(2)

    with col_proto:
        if stats["protocol_dist"]:
            fig = protocol_pie_chart(stats["protocol_dist"])
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_attack:
        if stats["label_dist"]:
            fig = attack_distribution_bar(stats["label_dist"])
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _traffic_volume_section(df: pd.DataFrame) -> None:
    section_header("Traffic Volume Over Time", "Packet count per minute, coloured by attack stage")
    fig = traffic_volume_chart(df.sample(min(20000, len(df)), random_state=42))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _data_preview(df: pd.DataFrame) -> None:
    with st.expander("📋 Raw Data Preview (first 200 rows)"):
        st.dataframe(df.head(200), use_container_width=True)


# ── Public render function ────────────────────────────────────────────────────

def render() -> None:
    """Entry point called by app.py."""

    st.markdown(
        '<h2 style="color:#f1f5f9;margin-bottom:0">📡 Traffic Upload & Analysis</h2>'
        '<p style="color:#64748b;margin-top:2px">Load network traffic data for analysis</p>',
        unsafe_allow_html=True,
    )

    # ── Source selector ───────────────────────────────────────────────────────
    st.markdown("#### Select Data Source")
    source_label = st.selectbox(
        "Input type",
        list(DATA_SOURCES.keys()),
        index=0,
        help="Choose the format of your traffic data.",
    )
    source_type = DATA_SOURCES[source_label]

    # ── Upload widget ─────────────────────────────────────────────────────────
    uploaded_file = None
    if source_type == "pcap":
        st.warning(
            "⚠️ PCAP ingestion is not yet implemented. "
            "Please upload a CSV file and select a CSV source type."
        )
    elif source_type in ("simulated", "cicids"):
        col_upload, col_auto = st.columns([2, 1])
        with col_upload:
            uploaded_file = st.file_uploader(
                "Upload CSV file",
                type=["csv"],
                help="Upload your traffic CSV. Leave blank to use the bundled simulated dataset.",
            )
        with col_auto:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if SIMULATED_DATA_PATH.exists():
                st.markdown(
                    f'<div style="background:#052e16;border-left:3px solid #22c55e;'
                    f'border-radius:4px;padding:8px 12px;font-size:0.8rem;color:#86efac">'
                    f'✅ Default dataset available<br>'
                    f'<span style="color:#4ade80;font-family:monospace;font-size:0.72rem">'
                    f'data/simulated/simulated_packets.csv</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.warning("Default dataset not found. Run `generate_data.py` first.")

    # ── Analyze button ────────────────────────────────────────────────────────
    st.markdown("")
    analyze_clicked = st.button("🔍 Analyze Traffic", type="primary", use_container_width=False)

    if analyze_clicked or st.session_state.get("df") is not None:

        # Load data
        if analyze_clicked:
            with st.spinner("Loading and processing traffic data…"):
                df, msg = load_traffic_data(source_type, uploaded_file)
            st.session_state["df"]          = df
            st.session_state["source_type"] = source_type
            st.session_state["load_msg"]    = msg

        df  = st.session_state.get("df")
        msg = st.session_state.get("load_msg", "")

        # Status message
        if "✅" in msg:
            st.success(msg)
        elif "⚠️" in msg:
            st.warning(msg)
        else:
            st.error(msg)

        if df is None:
            return

        # ── Statistics ────────────────────────────────────────────────────
        st.divider()
        section_header("Dataset Summary")

        if source_type == "simulated":
            demo_badge()
            st.caption(
                "This is **synthetic development data** generated by `generate_data.py`. "
                "It is NOT derived from real network captures or PCAP files."
            )

        stats = get_summary_stats(df)
        _stats_row(stats)
        st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
        _time_range_info(stats)

        st.divider()
        section_header("Distribution Analysis")
        _distribution_charts(stats, df)

        st.divider()
        _traffic_volume_section(df)

        st.divider()
        section_header("Basic Traffic Statistics")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Packet Size**")
            pkt = df["packet_size"] if "packet_size" in df.columns else pd.Series([0])
            st.dataframe(
                pkt.describe().rename("packet_size (bytes)").to_frame(),
                use_container_width=True,
            )
        with col_b:
            st.markdown("**Protocol Breakdown**")
            if "protocol" in df.columns:
                proto_df = (
                    df["protocol"]
                    .value_counts()
                    .rename_axis("Protocol")
                    .reset_index(name="Count")
                )
                proto_df["% of Traffic"] = (proto_df["Count"] / len(df) * 100).map("{:.1f}%".format)
                st.dataframe(proto_df, use_container_width=True)

        _data_preview(df)

        # Notify user that other pages can now use the data
        st.info(
            "💡 Data is loaded into session state. Navigate to **Network State**, "
            "**Attack Forecast**, or other pages to continue analysis."
        )
