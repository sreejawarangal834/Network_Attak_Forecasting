"""
components/attack_path.py — Attack progression visualisations.

Renders the Benign → Recon → BruteForce → … pipeline as HTML/CSS
so it looks good in a browser without external JS.
"""

from __future__ import annotations

import streamlit as st

from frontend.utils.constants import ATTACK_STAGES, STAGE_COLORS, STAGE_ICONS, STAGE_DESCRIPTIONS


def render_attack_pipeline(
    current_stage: str,
    predicted_stage: str,
    compact: bool = False,
) -> None:
    """
    Render the full attack progression pipeline with current and predicted stages highlighted.

    Parameters
    ----------
    current_stage   : The stage the system is currently in
    predicted_stage : The stage the model forecasts next
    compact         : If True, render a condensed horizontal strip (for Dashboard)
    """
    steps = []
    for stage in ATTACK_STAGES:
        color   = STAGE_COLORS[stage]
        icon    = STAGE_ICONS[stage]
        is_curr = stage == current_stage
        is_pred = stage == predicted_stage

        if is_curr:
            bg    = color
            txt   = "#000000" if stage == "Benign" else "#ffffff"
            label = "CURRENT"
            scale = "1.08"
            shadow = f"0 0 12px {color}88"
        elif is_pred:
            bg    = f"{color}33"
            txt   = color
            label = "PREDICTED"
            scale = "1.0"
            shadow = f"0 0 8px {color}44"
        else:
            bg    = "#1e293b"
            txt   = "#475569"
            label = ""
            scale = "1.0"
            shadow = "none"

        steps.append((stage, icon, color, bg, txt, label, scale, shadow))

    if compact:
        _render_compact(steps)
    else:
        _render_full(steps)


def _render_full(steps: list) -> None:
    """Full-size horizontal pipeline."""
    html_parts = ['<div style="display:flex;align-items:center;gap:0;overflow-x:auto;padding:8px 0">']

    for i, (stage, icon, color, bg, txt, label, scale, shadow) in enumerate(steps):
        # Arrow between stages
        if i > 0:
            html_parts.append(
                f'<div style="color:#334155;font-size:1.4rem;flex-shrink:0;margin:0 4px">▶</div>'
            )

        badge = (
            f'<div style="font-size:0.6rem;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.08em;color:{color};margin-bottom:2px">{label}</div>'
            if label else '<div style="font-size:0.6rem;margin-bottom:2px">&nbsp;</div>'
        )

        html_parts.append(f"""
<div style="
    flex-shrink:0;
    background:{bg};
    border:2px solid {color}{'ff' if label else '33'};
    border-radius:10px;
    padding:12px 16px;
    text-align:center;
    min-width:130px;
    transform:scale({scale});
    box-shadow:{shadow};
    transition:all 0.2s;
">
  {badge}
  <div style="font-size:1.6rem">{icon}</div>
  <div style="color:{'#f1f5f9' if label else '#475569'};font-size:0.82rem;
              font-weight:{'700' if label else '400'};margin-top:4px">{stage}</div>
</div>
        """)

    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def _render_compact(steps: list) -> None:
    """Compact inline strip for Dashboard."""
    html_parts = ['<div style="display:flex;align-items:center;gap:2px;flex-wrap:wrap">']
    for i, (stage, icon, color, bg, txt, label, scale, shadow) in enumerate(steps):
        if i > 0:
            html_parts.append('<span style="color:#334155;margin:0 2px">›</span>')
        weight = "700" if label else "400"
        opacity = "1" if label else "0.45"
        html_parts.append(
            f'<span style="color:{color};font-size:0.82rem;font-weight:{weight};'
            f'opacity:{opacity}">{icon} {stage}</span>'
        )
    html_parts.append("</div>")
    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_stage_detail_cards() -> None:
    """
    Render individual info cards for each attack stage with description.
    Used on the Attack Stages page.
    """
    for i, stage in enumerate(ATTACK_STAGES):
        color = STAGE_COLORS[stage]
        icon  = STAGE_ICONS[stage]
        desc  = STAGE_DESCRIPTIONS[stage]

        st.markdown(
            f"""
<div style="
    background:#1e293b;
    border-left:4px solid {color};
    border-radius:8px;
    padding:12px 16px;
    margin-bottom:8px;
    display:flex;
    align-items:flex-start;
    gap:12px;
">
  <div style="font-size:1.6rem;flex-shrink:0">{icon}</div>
  <div>
    <div style="color:#f1f5f9;font-weight:700;font-size:0.95rem">{stage}</div>
    <div style="color:#94a3b8;font-size:0.82rem;margin-top:2px">{desc}</div>
  </div>
  <div style="margin-left:auto;color:#334155;font-size:0.75rem;flex-shrink:0">
    Stage {i}
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )


def render_mitre_placeholder(stage: str) -> None:
    """
    Placeholder MITRE ATT&CK mapping card.
    The actual technique IDs will be configured when the mapping table is populated.
    """
    color = STAGE_COLORS.get(stage, "#3b82f6")
    st.markdown(
        f"""
<div style="background:#1e293b;border:1px dashed #334155;border-radius:8px;
     padding:14px 18px;margin-top:8px">
  <div style="color:#f59e0b;font-size:0.75rem;font-weight:700;margin-bottom:8px">
    🗺️ MITRE ATT&amp;CK Mapping — {stage}
    <span style="color:#64748b;font-weight:400;margin-left:8px">
      (Configuration placeholder — techniques not yet mapped)
    </span>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px">
    {"".join(_mitre_stub_card(stage, i) for i in range(3))}
  </div>
  <div style="color:#475569;font-size:0.75rem;margin-top:10px">
    ℹ️ To configure: edit <code>services/mitre_mapping.py</code> (not yet created)
    and populate the technique ID → stage mapping dict.
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _mitre_stub_card(stage: str, idx: int) -> str:
    return f"""
<div style="background:#0f172a;border-radius:6px;padding:8px 10px">
  <div style="color:#475569;font-size:0.72rem">T1XXX.00{idx+1}</div>
  <div style="color:#64748b;font-size:0.78rem">Technique name TBD</div>
  <div style="color:#334155;font-size:0.7rem">{stage}</div>
</div>
    """
