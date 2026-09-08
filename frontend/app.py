"""
app.py — CyberGuard: Predictive Cyber Defence
Main Streamlit entry point.

Run: streamlit run frontend/app.py

Navigation is fully custom HTML/CSS — no radio buttons anywhere.
Active page is tracked in st.session_state["active_page"].
"""

from __future__ import annotations

import sys
import time
import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from frontend.services.data_loader import load_default_simulated
from frontend.services.mock_predictions import get_mock_prediction
from frontend.pages import (
    dashboard, upload, network_state, forecast,
    attack_stages, alerts, explainability, performance, system,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CyberGuard — Predictive Cyber Defence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Navigation structure ──────────────────────────────────────────────────────
# (page_id, display_label, icon, section)
NAV_ITEMS = [
    ("Dashboard",         "Dashboard",         "▣", "MAIN"),
    ("Network State",     "Network State",     "◫", "MAIN"),
    ("Attack Forecast",   "Attack Forecast",   "◇", "MAIN"),
    ("Alerts",            "Alerts",            "⚠", "SECURITY"),
    ("At-Risk Devices",   "At-Risk Devices",   "◉", "SECURITY"),
    ("Attack Stages",     "Attack Stages",     "⚔", "SECURITY"),
    ("Explainability",    "Explainability",    "◈", "ANALYTICS"),
    ("Model Performance", "Model Performance", "▥", "ANALYTICS"),
    ("Data Sources",      "Data Sources",      "⚙", "SYSTEM"),
    ("System Status",     "System Status",     "◌", "SYSTEM"),
]

DEFAULT_PAGE = "Dashboard"


# ── Global CSS ────────────────────────────────────────────────────────────────
def _inject_css() -> None:
    st.markdown("""
<style>
/* ═══ Reset & base ═══════════════════════════════════════════════════════ */
[data-testid="stAppViewContainer"]          { background:#0a0f1e; }
[data-testid="stSidebar"]                   { background:#060d1a; border-right:1px solid #1a2540; }
[data-testid="stSidebar"] > div:first-child { padding-top:0 !important; }
[data-testid="block-container"]             { padding-top:0 !important; padding-bottom:2rem; }
section[data-testid="stSidebar"] .block-container { padding:0 !important; }

/* ═══ Hide ALL default Streamlit nav chrome ══════════════════════════════ */
[data-testid="stSidebarNav"],
[data-testid="stSidebarNavItems"],
[data-testid="stSidebarNavSeparator"],
header[data-testid="stHeader"],
#MainMenu, footer,
[data-testid="stToolbar"]                   { display:none !important; }

/* ═══ Kill radio buttons everywhere ══════════════════════════════════════ */
[data-testid="stRadio"],
.stRadio, div[role="radiogroup"]            { display:none !important; }

/* ═══ Nav buttons — full-width, ghost style ══════════════════════════════ */
.nav-btn > button {
    width:100% !important;
    text-align:left !important;
    background:transparent !important;
    border:none !important;
    border-radius:6px !important;
    padding:7px 12px 7px 16px !important;
    color:#64748b !important;
    font-size:0.82rem !important;
    font-weight:500 !important;
    cursor:pointer !important;
    transition:background 0.15s, color 0.15s !important;
    box-shadow:none !important;
    margin:1px 0 !important;
}
.nav-btn > button:hover {
    background:#0f1e38 !important;
    color:#94a3b8 !important;
}
.nav-btn-active > button {
    background:#0d1f3c !important;
    color:#f1f5f9 !important;
    border-left:3px solid #3b82f6 !important;
    padding-left:13px !important;
    font-weight:600 !important;
}

/* ═══ Metrics ════════════════════════════════════════════════════════════ */
[data-testid="stMetric"]      { background:#111827; border-radius:8px; padding:10px 14px; }
[data-testid="stMetricLabel"] { color:#64748b !important; font-size:0.7rem !important;
                                 text-transform:uppercase; letter-spacing:0.06em; }
[data-testid="stMetricValue"] { color:#f1f5f9 !important; font-size:1.3rem !important; }

/* ═══ Buttons ════════════════════════════════════════════════════════════ */
[data-testid="stButton"] > button {
    background:#111827 !important; color:#94a3b8 !important;
    border:1px solid #1e293b !important; border-radius:6px !important;
    font-size:0.8rem !important;
}
[data-testid="stButton"] > button:hover {
    border-color:#3b82f6 !important; color:#f1f5f9 !important;
}
button[kind="primary"] {
    background:#1d4ed8 !important; border-color:#1d4ed8 !important;
    color:#fff !important;
}

/* ═══ Misc ═══════════════════════════════════════════════════════════════ */
hr                              { border-color:#1a2540 !important; margin:0.8rem 0 !important; }
[data-testid="stExpander"]      { background:#111827; border:1px solid #1e293b !important;
                                   border-radius:8px; }
[data-testid="stDataFrame"]     { background:#111827; }
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div {
    background:#111827 !important; border-color:#1e293b !important;
    color:#f1f5f9 !important;
}
[data-testid="stFileUploader"]  { background:#111827; border:1px dashed #1e293b;
                                   border-radius:8px; }
::-webkit-scrollbar             { width:5px; height:5px; }
::-webkit-scrollbar-track       { background:#060d1a; }
::-webkit-scrollbar-thumb       { background:#1e293b; border-radius:3px; }

/* ═══ Top bar ════════════════════════════════════════════════════════════ */
.top-bar {
    background:#060d1a;
    border-bottom:1px solid #1a2540;
    padding:8px 24px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    margin-bottom:16px;
    border-radius:0 0 4px 4px;
}
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────
def _init_session() -> None:
    if "active_page" not in st.session_state:
        st.session_state["active_page"] = DEFAULT_PAGE
    if "df" not in st.session_state:
        df = load_default_simulated()
        st.session_state["df"]          = df
        st.session_state["source_type"] = "simulated"
    if "action_log" not in st.session_state:
        st.session_state["action_log"] = []
    if "live_refresh" not in st.session_state:
        st.session_state["live_refresh"] = False
    if "refresh_interval" not in st.session_state:
        st.session_state["refresh_interval"] = 10
    if "last_refresh" not in st.session_state:
        st.session_state["last_refresh"] = time.time()
    if "refresh_count" not in st.session_state:
        st.session_state["refresh_count"] = 0


# ── Custom sidebar ────────────────────────────────────────────────────────────
def _render_sidebar() -> None:
    with st.sidebar:
        # ── Brand header ──────────────────────────────────────────────────
        st.markdown("""
<div style="padding:20px 16px 12px 16px;border-bottom:1px solid #1a2540;">
  <div style="display:flex;align-items:center;gap:8px">
    <span style="font-size:1.5rem">🛡️</span>
    <div>
      <div style="color:#3b82f6;font-size:1rem;font-weight:800;
                  letter-spacing:0.04em;line-height:1">CYBERGUARD</div>
      <div style="color:#64748b;font-size:0.68rem;margin-top:1px">
        Predictive Defence System</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

        # ── Navigation items ──────────────────────────────────────────────
        sections_done = set()
        for page_id, label, icon, section in NAV_ITEMS:
            # Section header
            if section not in sections_done:
                st.markdown(
                    f'<div style="color:#334155;font-size:0.62rem;font-weight:700;'
                    f'text-transform:uppercase;letter-spacing:0.12em;'
                    f'padding:14px 16px 4px 16px">{section}</div>',
                    unsafe_allow_html=True,
                )
                sections_done.add(section)

            is_active = st.session_state["active_page"] == page_id
            btn_class = "nav-btn-active" if is_active else "nav-btn"

            st.markdown(f'<div class="{btn_class}">', unsafe_allow_html=True)
            if st.button(f"  {icon}  {label}", key=f"nav_{page_id}",
                         use_container_width=True):
                st.session_state["active_page"] = page_id
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        # ── Divider ────────────────────────────────────────────────────────
        st.markdown(
            '<div style="height:1px;background:#1a2540;margin:16px 0"></div>',
            unsafe_allow_html=True,
        )

        # ── System status footer ───────────────────────────────────────────
        df = st.session_state.get("df")
        n_records = f"{len(df):,}" if df is not None else "—"

        st.markdown(f"""
<div style="padding:0 16px 20px 16px">
  <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">
    <span style="color:#22c55e;font-size:0.6rem">●</span>
    <span style="color:#4ade80;font-size:0.78rem;font-weight:600">SYSTEM ONLINE</span>
  </div>
  <div style="color:#4b5563;font-size:0.72rem">{n_records} events loaded</div>
  <div style="color:#374151;font-size:0.68rem;margin-top:2px">Demo Environment</div>
</div>
""", unsafe_allow_html=True)


# ── Top status bar ────────────────────────────────────────────────────────────
def _render_top_bar() -> None:
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    page    = st.session_state.get("active_page", DEFAULT_PAGE)
    count   = st.session_state.get("refresh_count", 0)

    st.markdown(f"""
<div style="
    background:#060d1a;
    border-bottom:1px solid #1a2540;
    padding:8px 20px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    margin-bottom:16px;
">
  <!-- Left: brand + page name -->
  <div style="display:flex;align-items:center;gap:12px">
    <span style="color:#3b82f6;font-size:0.85rem;font-weight:800;
                 letter-spacing:0.05em">CYBERGUARD</span>
    <span style="color:#1e293b;font-size:0.8rem">|</span>
    <span style="color:#64748b;font-size:0.8rem">Predictive Cyber Defence</span>
    <span style="color:#1e293b;font-size:0.8rem">|</span>
    <span style="color:#94a3b8;font-size:0.8rem">{page}</span>
  </div>

  <!-- Right: live badge + timestamp + user -->
  <div style="display:flex;align-items:center;gap:16px">
    <div style="display:flex;align-items:center;gap:5px">
      <span style="color:#22c55e;font-size:0.55rem;animation:none">●</span>
      <span style="color:#4ade80;font-size:0.75rem;font-weight:600">LIVE DEMO</span>
      <span style="color:#374151;font-size:0.72rem">· Simulated telemetry</span>
    </div>
    <div style="color:#475569;font-size:0.72rem">
      Last update: <span style="color:#94a3b8;font-family:monospace">{now_str}</span>
    </div>
    <div style="background:#111827;border:1px solid #1e293b;border-radius:4px;
                padding:2px 10px;color:#64748b;font-size:0.72rem">
      Admin
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Live refresh controls ─────────────────────────────────────────────────────
def _render_refresh_controls() -> None:
    """
    Lightweight refresh panel shown only on the Dashboard page.
    Architecture: when live_refresh is ON and the interval has elapsed,
    st.rerun() triggers a new render cycle which re-calls get_mock_prediction()
    (or eventually the real model). No threads, no infinite loops.
    """
    if st.session_state.get("active_page") != "Dashboard":
        return

    with st.sidebar:
        st.markdown(
            '<div style="height:1px;background:#1a2540;margin-bottom:8px"></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="color:#334155;font-size:0.62rem;font-weight:700;'
            'text-transform:uppercase;letter-spacing:0.12em;'
            'padding:0 16px 4px 16px">LIVE DEMO</div>',
            unsafe_allow_html=True,
        )

        col_toggle, col_label = st.columns([1, 2])
        is_on = st.session_state["live_refresh"]
        with col_toggle:
            new_state = st.toggle("", value=is_on, key="refresh_toggle",
                                  label_visibility="collapsed")
        with col_label:
            dot   = "🟢" if new_state else "⚪"
            label = "ON" if new_state else "OFF"
            st.markdown(
                f'<div style="padding-top:6px;color:{"#4ade80" if new_state else "#475569"};'
                f'font-size:0.78rem;font-weight:600">{dot} {label}</div>',
                unsafe_allow_html=True,
            )

        if new_state != is_on:
            st.session_state["live_refresh"] = new_state
            st.session_state["last_refresh"] = time.time()

        if new_state:
            interval = st.select_slider(
                "Refresh interval",
                options=[5, 10, 15, 30, 60],
                value=st.session_state["refresh_interval"],
                key="refresh_slider",
                format_func=lambda x: f"{x}s",
            )
            st.session_state["refresh_interval"] = interval

            elapsed = time.time() - st.session_state["last_refresh"]
            remaining = max(0, interval - int(elapsed))
            st.markdown(
                f'<div style="color:#374151;font-size:0.7rem;padding:0 0 4px 0">'
                f'Next refresh in <b style="color:#64748b">{remaining}s</b></div>',
                unsafe_allow_html=True,
            )


# ── Refresh trigger ───────────────────────────────────────────────────────────
def _maybe_refresh() -> None:
    """
    If live refresh is enabled and the interval has elapsed, trigger a rerun.
    Called once per render cycle, after the page content is drawn.
    This is the correct pattern — no threads, no sleep().
    """
    if not st.session_state.get("live_refresh"):
        return
    if st.session_state.get("active_page") != "Dashboard":
        return

    interval = st.session_state.get("refresh_interval", 10)
    elapsed  = time.time() - st.session_state.get("last_refresh", 0)

    if elapsed >= interval:
        st.session_state["last_refresh"]   = time.time()
        st.session_state["refresh_count"] += 1
        time.sleep(0.05)   # tiny yield so browser receives the current frame
        st.rerun()


# ── Page router ───────────────────────────────────────────────────────────────
def _route(page_id: str, pred, df) -> None:
    if page_id == "Dashboard":
        dashboard.render(pred, df)
    elif page_id == "Data Sources":
        upload.render()
    elif page_id == "Network State":
        network_state.render(pred, df)
    elif page_id == "Attack Forecast":
        forecast.render(pred, df)
    elif page_id == "Attack Stages":
        attack_stages.render(pred, df)
    elif page_id in ("Alerts", "At-Risk Devices"):
        alerts.render(pred, df)
    elif page_id == "Explainability":
        explainability.render(pred, df)
    elif page_id == "Model Performance":
        performance.render(pred, df)
    elif page_id == "System Status":
        system.render(pred, df)
    else:
        st.error(f"Unknown page: {page_id}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    _inject_css()
    _init_session()
    _render_sidebar()
    _render_refresh_controls()
    _render_top_bar()

    df      = st.session_state.get("df")
    pred    = get_mock_prediction(df)
    page_id = st.session_state.get("active_page", DEFAULT_PAGE)

    _route(page_id, pred, df)
    _maybe_refresh()


if __name__ == "__main__":
    main()
