"""
components/metrics.py — Reusable metric card helpers.

Every metric display in the app calls one of these functions so the
visual style is consistent and only maintained in one place.
"""

from __future__ import annotations

import streamlit as st

from frontend.utils.constants import (
    RISK_COLORS, STAGE_COLORS, STAGE_ICONS, COLOR_TEXT_MUTED, DEMO_BADGE
)


# ── Styled metric card via st.markdown ───────────────────────────────────────

def _card_html(
    label: str,
    value: str,
    sub: str = "",
    border_color: str = "#3b82f6",
    value_color: str = "#f1f5f9",
) -> str:
    """Return an HTML string for a styled metric card."""
    sub_html = f'<div style="color:{COLOR_TEXT_MUTED};font-size:0.78rem;margin-top:4px">{sub}</div>' if sub else ""
    return f"""
<div style="
    background:#1e293b;
    border-left: 4px solid {border_color};
    border-radius:8px;
    padding:14px 18px;
    margin-bottom:4px;
">
  <div style="color:{COLOR_TEXT_MUTED};font-size:0.75rem;text-transform:uppercase;
              letter-spacing:0.08em;font-weight:600">{label}</div>
  <div style="color:{value_color};font-size:1.6rem;font-weight:700;
              line-height:1.2;margin-top:4px">{value}</div>
  {sub_html}
</div>
"""


def risk_metric_card(label: str, value: str, risk_level: str, sub: str = "") -> None:
    """Metric card coloured by risk level."""
    color = RISK_COLORS.get(risk_level, "#3b82f6")
    st.markdown(_card_html(label, value, sub, border_color=color, value_color=color),
                unsafe_allow_html=True)


def stage_metric_card(label: str, stage: str, sub: str = "") -> None:
    """Metric card coloured by attack stage."""
    icon  = STAGE_ICONS.get(stage, "")
    color = STAGE_COLORS.get(stage, "#3b82f6")
    st.markdown(_card_html(label, f"{icon} {stage}", sub, border_color=color, value_color=color),
                unsafe_allow_html=True)


def info_metric_card(label: str, value: str, sub: str = "", color: str = "#3b82f6") -> None:
    """Generic blue info metric card."""
    st.markdown(_card_html(label, value, sub, border_color=color, value_color="#f1f5f9"),
                unsafe_allow_html=True)


def probability_bar(label: str, value: float, color: str = "#ef4444") -> None:
    """
    A labelled progress bar for a 0-1 probability value.
    Uses st.progress for the bar and st.markdown for the label row.
    """
    pct = int(value * 100)
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;'
        f'font-size:0.85rem;color:#cbd5e1;margin-bottom:2px">'
        f'<span>{label}</span>'
        f'<span style="color:{color};font-weight:700">{pct}%</span></div>',
        unsafe_allow_html=True,
    )
    st.progress(value)


def demo_badge() -> None:
    """Render a small orange DEMO watermark banner."""
    st.markdown(
        f'<div style="background:#422006;border-left:3px solid #f97316;'
        f'border-radius:4px;padding:6px 12px;font-size:0.78rem;color:#fdba74;'
        f'margin-bottom:12px">{DEMO_BADGE}</div>',
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    """Consistent section heading with optional subtitle."""
    st.markdown(
        f'<h3 style="color:#f1f5f9;margin-bottom:2px">{title}</h3>'
        + (f'<p style="color:{COLOR_TEXT_MUTED};font-size:0.85rem;margin-top:0">{subtitle}</p>'
           if subtitle else ""),
        unsafe_allow_html=True,
    )


def status_badge(text: str, color: str = "#22c55e") -> str:
    """Return inline HTML for a coloured status pill."""
    return (
        f'<span style="background:{color}22;color:{color};border:1px solid {color}55;'
        f'border-radius:12px;padding:2px 10px;font-size:0.75rem;font-weight:600">'
        f'{text}</span>'
    )


def kpi_row(items: list[tuple[str, str, str]]) -> None:
    """
    Render a horizontal row of simple KPI tiles.
    items: list of (label, value, sub) tuples.
    """
    cols = st.columns(len(items))
    for col, (label, value, sub) in zip(cols, items):
        with col:
            info_metric_card(label, value, sub)
