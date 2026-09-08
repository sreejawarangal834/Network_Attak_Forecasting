"""
pages/performance.py — Model Performance

Compares World Model vs Logistic Regression baseline on key metrics.
ALL VALUES ARE DEMO/MOCK — no model has been trained yet.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.components.charts import model_comparison_chart, per_stage_accuracy_chart
from frontend.components.metrics import demo_badge, info_metric_card, section_header
from frontend.services.mock_predictions import get_mock_model_performance


def _headline_kpis(perf: dict) -> None:
    wm = perf["world_model"]
    lr = perf["logistic_regression"]

    st.markdown("#### World Model (DEMO)")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        info_metric_card("Precision",        f"{wm['precision']:.3f}",  color="#3b82f6")
    with c2:
        info_metric_card("Recall",           f"{wm['recall']:.3f}",     color="#3b82f6")
    with c3:
        info_metric_card("F1 Score",         f"{wm['f1_score']:.3f}",   color="#3b82f6")
    with c4:
        info_metric_card("AUC-ROC",          f"{wm['auc_roc']:.3f}",    color="#3b82f6")
    with c5:
        info_metric_card("Stage Accuracy",   f"{wm['stage_accuracy']:.0%}", color="#3b82f6")

    st.markdown("#### Logistic Regression Baseline (DEMO)")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        info_metric_card("Precision",        f"{lr['precision']:.3f}",  color="#6b7280")
    with c2:
        info_metric_card("Recall",           f"{lr['recall']:.3f}",     color="#6b7280")
    with c3:
        info_metric_card("F1 Score",         f"{lr['f1_score']:.3f}",   color="#6b7280")
    with c4:
        info_metric_card("AUC-ROC",          f"{lr['auc_roc']:.3f}",    color="#6b7280")
    with c5:
        info_metric_card("Stage Accuracy",   f"{lr['stage_accuracy']:.0%}", color="#6b7280")


def _delta_table(perf: dict) -> None:
    """Show absolute improvement of WM over LR baseline."""
    section_header("Improvement over Baseline (DEMO)")
    wm = perf["world_model"]
    lr = perf["logistic_regression"]
    metrics = ["precision", "recall", "f1_score", "auc_roc", "stage_accuracy"]
    labels  = ["Precision", "Recall", "F1 Score", "AUC-ROC", "Stage Accuracy"]

    rows = []
    for m, label in zip(metrics, labels):
        wm_val = wm[m]
        lr_val = lr[m]
        delta  = wm_val - lr_val
        rows.append({
            "Metric":              label,
            "World Model":         f"{wm_val:.3f}",
            "Logistic Regression": f"{lr_val:.3f}",
            "Improvement":         f"+{delta:.3f}",
            "Relative Gain":       f"+{delta/lr_val*100:.1f}%",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _confusion_matrix_placeholder() -> None:
    section_header("Confusion Matrix (Placeholder)")
    st.markdown(
        '<div style="background:#1e2d40;border:2px dashed #1d4ed8;border-radius:8px;'
        'padding:18px 22px">'
        '<div style="color:#60a5fa;font-weight:700;margin-bottom:6px">'
        '⚙️ Confusion Matrix — Not Yet Generated</div>'
        '<div style="color:#64748b;font-size:0.85rem">'
        'The confusion matrix will be computed after the World Model is trained '
        'and evaluated on a held-out test set. It will show true/false positives '
        'and negatives per attack stage class.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _roc_placeholder() -> None:
    section_header("ROC Curve (Placeholder)")
    st.markdown(
        '<div style="background:#1e2d40;border:2px dashed #1d4ed8;border-radius:8px;'
        'padding:18px 22px">'
        '<div style="color:#60a5fa;font-weight:700;margin-bottom:6px">'
        '⚙️ ROC Curve — Not Yet Generated</div>'
        '<div style="color:#64748b;font-size:0.85rem">'
        'Per-class ROC curves (one-vs-rest) will be plotted here after model training.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ── Public render function ────────────────────────────────────────────────────

def render(*_) -> None:
    st.markdown(
        '<h2 style="color:#f1f5f9;margin-bottom:0">📊 Model Performance</h2>'
        '<p style="color:#64748b;margin-top:2px">'
        'World Model vs Logistic Regression baseline — placeholder metrics</p>',
        unsafe_allow_html=True,
    )

    demo_badge()

    st.warning(
        "⚠️ All metrics on this page are **DEMO placeholder values**. "
        "No model has been trained. These values illustrate the target comparison "
        "interface for when the World Model is integrated.",
        icon="⚠️",
    )

    perf = get_mock_model_performance()

    _headline_kpis(perf)

    st.divider()

    section_header("Metric Comparison Chart")
    fig = model_comparison_chart(perf)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.divider()

    section_header("Per-Stage Detection Accuracy")
    fig2 = per_stage_accuracy_chart(perf["per_stage"])
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    st.divider()

    _delta_table(perf)

    st.divider()

    col_cm, col_roc = st.columns(2)
    with col_cm:
        _confusion_matrix_placeholder()
    with col_roc:
        _roc_placeholder()
