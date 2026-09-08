"""
components/charts.py — Reusable Plotly chart builders.

Every chart returns a go.Figure so the caller can st.plotly_chart() it
with their preferred sizing options.
"""

from __future__ import annotations

from typing import Any
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from frontend.utils.constants import (
    ATTACK_STAGES, STAGE_COLORS, RISK_COLORS, PROTOCOL_COLORS,
    COLOR_BG_CARD, COLOR_TEXT_MUTED, COLOR_PRIMARY,
)

# ── Shared Plotly theme ───────────────────────────────────────────────────────

_LAYOUT_DEFAULTS = dict(
    paper_bgcolor=COLOR_BG_CARD,
    plot_bgcolor=COLOR_BG_CARD,
    font=dict(color="#cbd5e1", family="Inter, system-ui, sans-serif", size=12),
    margin=dict(l=10, r=10, t=36, b=10),
    legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0),
)


def _apply_defaults(fig: go.Figure, title: str = "") -> go.Figure:
    fig.update_layout(title=dict(text=title, font=dict(size=13, color="#94a3b8")),
                      **_LAYOUT_DEFAULTS)
    fig.update_xaxes(gridcolor="#1e293b", zeroline=False, tickfont=dict(size=11))
    fig.update_yaxes(gridcolor="#1e293b", zeroline=False, tickfont=dict(size=11))
    return fig


# ── Risk Timeline ─────────────────────────────────────────────────────────────

def risk_timeline_chart(time_labels: list[str], risk_values: list[float]) -> go.Figure:
    """
    Line + area chart of overall network risk over time.
    risk_values: 0-1 floats.
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=time_labels, y=risk_values,
        mode="lines+markers",
        line=dict(color="#ef4444", width=2.5),
        fill="tozeroy",
        fillcolor="rgba(239,68,68,0.10)",
        marker=dict(size=5),
        name="Risk Score",
        hovertemplate="%{x}<br>Risk: %{y:.2f}<extra></extra>",
    ))
    # Threshold bands
    fig.add_hline(y=0.65, line=dict(color="#f59e0b", dash="dot", width=1),
                  annotation_text="HIGH", annotation_position="right")
    fig.add_hline(y=0.85, line=dict(color="#7c3aed", dash="dot", width=1),
                  annotation_text="CRITICAL", annotation_position="right")
    fig.update_yaxes(range=[0, 1.05])
    return _apply_defaults(fig, "Network Risk Timeline")


# ── Protocol distribution pie ─────────────────────────────────────────────────

def protocol_pie_chart(proto_counts: dict[str, int]) -> go.Figure:
    labels = list(proto_counts.keys())
    values = list(proto_counts.values())
    colors = [PROTOCOL_COLORS.get(l, "#6b7280") for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.55,
        marker=dict(colors=colors, line=dict(color=COLOR_BG_CARD, width=2)),
        textinfo="label+percent",
        textfont=dict(size=11),
        hovertemplate="%{label}: %{value:,} packets (%{percent})<extra></extra>",
    ))
    return _apply_defaults(fig, "Protocol Distribution")


# ── Attack stage distribution bar ─────────────────────────────────────────────

def attack_distribution_bar(label_counts: dict[str, int]) -> go.Figure:
    stages  = [s for s in ATTACK_STAGES if s in label_counts]
    counts  = [label_counts[s] for s in stages]
    colors  = [STAGE_COLORS.get(s, COLOR_PRIMARY) for s in stages]

    fig = go.Figure(go.Bar(
        x=stages, y=counts,
        marker_color=colors,
        text=counts,
        textposition="outside",
        textfont=dict(size=10),
        hovertemplate="%{x}: %{y:,} packets<extra></extra>",
    ))
    fig.update_layout(showlegend=False)
    return _apply_defaults(fig, "Traffic by Attack Stage")


# ── Stage probability forecast ────────────────────────────────────────────────

def stage_forecast_chart(future_probs: list[dict]) -> go.Figure:
    """
    Grouped line chart of stage probabilities over forecast horizon.
    future_probs: list of dicts with keys 't', then stage names.
    """
    forecast_stages = [s for s in ATTACK_STAGES if s != "Benign"]
    t_labels = [row["t"] for row in future_probs]

    fig = go.Figure()
    for stage in forecast_stages:
        y = [row.get(stage, 0) for row in future_probs]
        fig.add_trace(go.Scatter(
            x=t_labels, y=y,
            name=stage,
            mode="lines+markers",
            line=dict(color=STAGE_COLORS[stage], width=2),
            marker=dict(size=6),
            hovertemplate=f"{stage}<br>%{{x}}: %{{y:.2f}}<extra></extra>",
        ))
    fig.update_yaxes(range=[0, 1.05], tickformat=".0%")
    return _apply_defaults(fig, "Attack Stage Probability Forecast")


# ── Infiltration probability timeline ────────────────────────────────────────

def infiltration_timeline_chart(horizon: int = 5) -> go.Figure:
    """Mock infiltration probability increasing over forecast steps."""
    steps  = [f"T+{i+1}" for i in range(horizon)]
    probs  = [0.45 + i * 0.10 for i in range(horizon)]
    colors = [RISK_COLORS.get("HIGH" if p < 0.85 else "CRITICAL") for p in probs]

    fig = go.Figure(go.Bar(
        x=steps, y=probs,
        marker_color=colors,
        text=[f"{p:.0%}" for p in probs],
        textposition="outside",
        hovertemplate="%{x}: %{y:.2f}<extra></extra>",
    ))
    fig.update_yaxes(range=[0, 1.05], tickformat=".0%")
    return _apply_defaults(fig, "Infiltration Probability over Forecast Horizon")


# ── Feature importance / SHAP bar ────────────────────────────────────────────

def feature_importance_chart(features: list[dict]) -> go.Figure:
    """
    Horizontal bar chart of contributing features.
    features: list of {'feature': str, 'importance': float, ...}
    """
    sorted_f = sorted(features, key=lambda x: x["importance"])
    labels   = [f["feature"] for f in sorted_f]
    values   = [f["importance"] for f in sorted_f]
    colors   = [
        "#ef4444" if v >= 0.25 else "#f59e0b" if v >= 0.12 else "#3b82f6"
        for v in values
    ]

    fig = go.Figure(go.Bar(
        y=labels, x=values,
        orientation="h",
        marker_color=colors,
        text=[f"{v:.2f}" for v in values],
        textposition="outside",
        hovertemplate="%{y}: %{x:.3f}<extra></extra>",
    ))
    fig.update_xaxes(range=[0, max(values) * 1.25])
    fig.update_layout(showlegend=False)
    return _apply_defaults(fig, "Feature Contribution (DEMO — Mock Values)")


# ── Network state radar ───────────────────────────────────────────────────────

def network_state_radar(state: dict) -> go.Figure:
    """
    Radar / spider chart of normalised network state features.
    Normalisation is approximate; values are clamped to [0, 1].
    """
    radar_features = [
        "syn_rate", "ack_rate", "rst_rate", "fin_rate",
        "dst_port_entropy" if "dst_port_entropy" in state else "unique_ports",
        "avg_packet_size",
    ]
    maxima = {
        "syn_rate": 50, "ack_rate": 200, "rst_rate": 30, "fin_rate": 20,
        "dst_port_entropy": 10, "unique_ports": 1000, "avg_packet_size": 1500,
    }

    labels = [f.replace("_", " ").title() for f in radar_features]
    vals   = [min(state.get(f, 0) / maxima.get(f, 1), 1.0) for f in radar_features]
    vals  += vals[:1]           # close the polygon
    labels_closed = labels + labels[:1]

    fig = go.Figure(go.Scatterpolar(
        r=vals, theta=labels_closed,
        fill="toself",
        fillcolor="rgba(239,68,68,0.15)",
        line=dict(color="#ef4444", width=2),
        name="Current State",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor=COLOR_BG_CARD,
            radialaxis=dict(visible=True, range=[0, 1], tickfont=dict(size=9),
                            gridcolor="#334155"),
            angularaxis=dict(gridcolor="#334155"),
        ),
    )
    return _apply_defaults(fig, "Network State Profile")


# ── Model performance comparison ──────────────────────────────────────────────

def model_comparison_chart(perf: dict) -> go.Figure:
    """Grouped bar chart comparing World Model vs Logistic Regression."""
    metrics = ["precision", "recall", "f1_score", "auc_roc"]
    labels  = ["Precision", "Recall", "F1 Score", "AUC-ROC"]
    wm      = [perf["world_model"][m]        for m in metrics]
    lr      = [perf["logistic_regression"][m] for m in metrics]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="World Model (DEMO)", x=labels, y=wm,
                         marker_color="#3b82f6",
                         text=[f"{v:.3f}" for v in wm], textposition="outside"))
    fig.add_trace(go.Bar(name="Logistic Regression (DEMO)", x=labels, y=lr,
                         marker_color="#6b7280",
                         text=[f"{v:.3f}" for v in lr], textposition="outside"))
    fig.update_yaxes(range=[0, 1.15])
    fig.update_layout(barmode="group")
    return _apply_defaults(fig, "Model Performance Comparison (DEMO — Mock Values)")


# ── Per-stage accuracy ────────────────────────────────────────────────────────

def per_stage_accuracy_chart(per_stage: dict) -> go.Figure:
    stages = list(per_stage.keys())
    wm_acc = [per_stage[s]["wm"] for s in stages]
    lr_acc = [per_stage[s]["lr"] for s in stages]

    fig = go.Figure()
    fig.add_trace(go.Bar(name="World Model",         x=stages, y=wm_acc,
                         marker_color="#3b82f6",
                         text=[f"{v:.0%}" for v in wm_acc], textposition="outside"))
    fig.add_trace(go.Bar(name="Logistic Regression", x=stages, y=lr_acc,
                         marker_color="#6b7280",
                         text=[f"{v:.0%}" for v in lr_acc], textposition="outside"))
    fig.update_yaxes(range=[0, 1.15], tickformat=".0%")
    fig.update_layout(barmode="group")
    return _apply_defaults(fig, "Per-Stage Detection Accuracy (DEMO)")


# ── State sequence timeline ───────────────────────────────────────────────────

def state_sequence_chart(states: list[dict], feature: str = "syn_rate") -> go.Figure:
    """
    Line chart showing how a single state feature evolves across time windows.
    """
    labels = [s.get("label", f"T-{i}") for i, s in enumerate(states)]
    values = [s.get(feature, 0) for s in states]

    fig = go.Figure(go.Scatter(
        x=labels, y=values,
        mode="lines+markers+text",
        line=dict(color=COLOR_PRIMARY, width=2),
        marker=dict(size=8, color=COLOR_PRIMARY),
        text=[f"{v:.2f}" for v in values],
        textposition="top center",
        textfont=dict(size=9),
        hovertemplate="%{x}<br>" + feature + ": %{y:.3f}<extra></extra>",
    ))
    friendly = feature.replace("_", " ").title()
    return _apply_defaults(fig, f"State Feature: {friendly}")


# ── Traffic volume over time ──────────────────────────────────────────────────

def traffic_volume_chart(df: pd.DataFrame) -> go.Figure:
    """
    Histogram of packet counts per minute, coloured by attack stage.
    """
    if "timestamp" not in df.columns or "attack_type" not in df.columns:
        fig = go.Figure()
        return _apply_defaults(fig, "Traffic Volume (no timestamp data)")

    df2 = df.copy()
    df2["timestamp"] = pd.to_datetime(df2["timestamp"], errors="coerce")
    df2 = df2.dropna(subset=["timestamp"])
    df2["minute"] = df2["timestamp"].dt.floor("1min")

    grouped = df2.groupby(["minute", "attack_type"]).size().reset_index(name="count")

    fig = go.Figure()
    for stage in ATTACK_STAGES:
        sub = grouped[grouped["attack_type"] == stage]
        if sub.empty:
            continue
        fig.add_trace(go.Bar(
            x=sub["minute"], y=sub["count"],
            name=stage,
            marker_color=STAGE_COLORS.get(stage, COLOR_PRIMARY),
            hovertemplate=f"{stage}<br>%{{x}}<br>%{{y}} packets<extra></extra>",
        ))
    fig.update_layout(barmode="stack")
    return _apply_defaults(fig, "Traffic Volume by Attack Stage")
