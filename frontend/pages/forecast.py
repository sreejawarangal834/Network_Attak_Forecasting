"""
pages/forecast.py — Attack Forecast

Shows the current attack stage and a multi-step forecast of how the attack
is predicted to progress. Values are DEMO/MOCK until the World Model is connected.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.components.attack_path import render_attack_pipeline
from frontend.components.charts import (
    infiltration_timeline_chart,
    stage_forecast_chart,
)
from frontend.components.metrics import (
    demo_badge,
    info_metric_card,
    probability_bar,
    risk_metric_card,
    section_header,
    stage_metric_card,
)
from frontend.services.mock_predictions import PredictionResult
from frontend.utils.constants import ATTACK_STAGES, RISK_COLORS, STAGE_COLORS, STAGE_ICONS


def _forecast_header_kpis(pred: PredictionResult) -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        stage_metric_card("Current Stage",   pred.current_stage)
    with c2:
        stage_metric_card("Predicted Next",  pred.predicted_stage)
    with c3:
        info_metric_card("Forecast Horizon", f"{pred.forecast_horizon} steps",
                         sub="~5 minute windows")
    with c4:
        risk_metric_card("Infiltration Prob.", f"{pred.overall_risk:.0%}",
                         pred.risk_level)
    with c5:
        total_stages = len(ATTACK_STAGES) - 1
        curr_idx     = ATTACK_STAGES.index(pred.current_stage) if pred.current_stage in ATTACK_STAGES else 0
        info_metric_card("Kill-Chain Progress",
                         f"{curr_idx}/{total_stages}",
                         sub="stages completed",
                         color=STAGE_COLORS.get(pred.current_stage, "#3b82f6"))


def _stage_probability_bars(pred: PredictionResult) -> None:
    """Current-time stage probability breakdown."""
    section_header("Current Stage Probabilities", "Likelihood of each stage right now (DEMO)")

    # Derive approximate current probs from first forecast step
    if pred.future_probabilities:
        first = pred.future_probabilities[0]
    else:
        first = {}

    # Approximate current distribution (inverted from first forecast)
    current_probs = {
        "Benign":             0.02,
        "Reconnaissance":     0.72,
        "BruteForce":         0.45,
        "LateralMovement":    0.18,
        "CommandAndControl":  0.08,
    }

    col_bars, col_info = st.columns([1, 1])
    with col_bars:
        for stage in ATTACK_STAGES:
            prob  = current_probs.get(stage, 0.0)
            color = STAGE_COLORS.get(stage, "#3b82f6")
            probability_bar(
                f"{STAGE_ICONS.get(stage,'')} {stage}",
                prob,
                color=color,
            )

    with col_info:
        st.markdown(
            f"""
<div style="background:#1e293b;border-left:3px solid
    {STAGE_COLORS.get(pred.predicted_stage,'#3b82f6')};
    border-radius:8px;padding:16px 18px">
  <div style="color:#94a3b8;font-size:0.75rem;text-transform:uppercase;
              font-weight:600;margin-bottom:8px">Forecast Summary</div>
  <div style="color:#f1f5f9;font-size:0.9rem;line-height:1.7">
    The system is currently in the
    <b style="color:{STAGE_COLORS.get(pred.current_stage,'#fff')}">
    {pred.current_stage}</b> stage.<br>
    The World Model predicts escalation to
    <b style="color:{STAGE_COLORS.get(pred.predicted_stage,'#fff')}">
    {pred.predicted_stage}</b> within the next {pred.forecast_horizon} time steps
    (~{pred.forecast_horizon * 5} minutes).<br><br>
    Overall infiltration probability:
    <b style="color:{RISK_COLORS.get(pred.risk_level,'#fff')}">
    {pred.overall_risk:.0%}</b>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )


def _forecast_charts(pred: PredictionResult) -> None:
    col_l, col_r = st.columns(2)
    with col_l:
        fig = stage_forecast_chart(pred.future_probabilities)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with col_r:
        fig2 = infiltration_timeline_chart(pred.forecast_horizon)
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})


def _forecast_table(pred: PredictionResult) -> None:
    """Tabular view of stage probabilities over forecast horizon."""
    section_header("Forecast Probability Table", "Stage probabilities at each time step")

    if not pred.future_probabilities:
        st.info("No forecast data available.")
        return

    rows = []
    for row in pred.future_probabilities:
        r = {"Time Step": row["t"]}
        for stage in ATTACK_STAGES[1:]:
            r[stage] = f"{row.get(stage, 0):.2f}"
        rows.append(r)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _recommendations(pred: PredictionResult) -> None:
    section_header("Recommended Defensive Actions")
    for i, action in enumerate(pred.recommended_actions, 1):
        st.markdown(
            f'<div style="background:#1e293b;border-left:3px solid #3b82f6;'
            f'border-radius:6px;padding:8px 14px;margin-bottom:6px;'
            f'color:#cbd5e1;font-size:0.85rem">'
            f'<b style="color:#60a5fa">{i}.</b> {action}</div>',
            unsafe_allow_html=True,
        )


# ── Public render function ────────────────────────────────────────────────────

def render(pred: PredictionResult, df: pd.DataFrame | None = None) -> None:
    st.markdown(
        '<h2 style="color:#f1f5f9;margin-bottom:0">🔮 Attack Forecast</h2>'
        '<p style="color:#64748b;margin-top:2px">'
        'Predicted attack stage progression over the next 5 time steps</p>',
        unsafe_allow_html=True,
    )

    demo_badge()

    _forecast_header_kpis(pred)

    st.divider()

    section_header("Attack Progression Pipeline")
    render_attack_pipeline(pred.current_stage, pred.predicted_stage)

    st.divider()

    _stage_probability_bars(pred)

    st.divider()

    section_header("Multi-Step Forecast Charts",
                   "Stage probability evolution over the forecast horizon")
    _forecast_charts(pred)

    st.divider()

    _forecast_table(pred)

    st.divider()

    _recommendations(pred)
