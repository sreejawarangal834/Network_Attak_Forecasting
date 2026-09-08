"""
state_builder.py — Network State Builder.

Computes the feature vector S_t (network state at time t) from raw traffic data.
This module is intentionally decoupled from the World Model so that the same
state representation can be fed to any downstream model (LSTM, Transformer, GNN).

Future integration point:
  world_model.predict(S_t) → S_t+1, S_t+2, ...
"""

from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd


# ── State feature names (ordered, canonical) ─────────────────────────────────
STATE_FEATURES = [
    "active_flows",
    "packets_per_sec",
    "unique_src_ips",
    "unique_dst_ips",
    "unique_ports",
    "avg_packet_size",
    "syn_rate",
    "ack_rate",
    "rst_rate",
    "fin_rate",
    "avg_ttl",
    "ttl_std",
    "byte_rate",
    "dst_port_entropy",
]


def _entropy(series: pd.Series) -> float:
    """Shannon entropy of a categorical series (bits)."""
    counts = series.value_counts(normalize=True)
    if len(counts) == 0:
        return 0.0
    return float(-np.sum(counts * np.log2(counts + 1e-9)))


def build_state_from_window(window: pd.DataFrame, window_seconds: float = 60.0) -> dict:
    """
    Compute the network state feature vector from a time window of traffic.

    Parameters
    ----------
    window         : DataFrame slice (one time window of packets)
    window_seconds : Duration of the window in seconds (used for rate features)

    Returns
    -------
    State dict {feature_name: value}
    """
    if window is None or len(window) == 0:
        return {f: 0.0 for f in STATE_FEATURES}

    n = len(window)

    state = {
        "active_flows":     int(window["src_ip"].nunique()) * int(window["dst_ip"].nunique())
                            if "src_ip" in window.columns and "dst_ip" in window.columns else 0,

        "packets_per_sec":  round(n / max(window_seconds, 1e-3), 2),

        "unique_src_ips":   int(window["src_ip"].nunique())  if "src_ip"   in window.columns else 0,
        "unique_dst_ips":   int(window["dst_ip"].nunique())  if "dst_ip"   in window.columns else 0,
        "unique_ports":     int(window["dst_port"].nunique()) if "dst_port" in window.columns else 0,

        "avg_packet_size":  round(float(window["packet_size"].mean()), 2)
                            if "packet_size" in window.columns else 0.0,

        "syn_rate":         round(float(window["syn"].sum()) / max(window_seconds, 1e-3), 4)
                            if "syn" in window.columns else 0.0,

        "ack_rate":         round(float(window["ack"].sum()) / max(window_seconds, 1e-3), 4)
                            if "ack" in window.columns else 0.0,

        "rst_rate":         round(float(window["rst"].sum()) / max(window_seconds, 1e-3), 4)
                            if "rst" in window.columns else 0.0,

        "fin_rate":         round(float(window["fin"].sum()) / max(window_seconds, 1e-3), 4)
                            if "fin" in window.columns else 0.0,

        "avg_ttl":          round(float(window["ttl"].mean()), 2)
                            if "ttl" in window.columns else 64.0,

        "ttl_std":          round(float(window["ttl"].std()), 2)
                            if "ttl" in window.columns else 0.0,

        "byte_rate":        round(float(window["packet_size"].sum()) / max(window_seconds, 1e-3), 2)
                            if "packet_size" in window.columns else 0.0,

        "dst_port_entropy": round(_entropy(window["dst_port"]), 3)
                            if "dst_port" in window.columns else 0.0,
    }
    return state


def build_state_sequence(
    df: pd.DataFrame,
    n_windows: int = 10,
    window_size: int = 500,
) -> list[dict]:
    """
    Produce a sequence of state snapshots [S_t-n, ..., S_t] from a DataFrame.
    Used to populate the S_t → S_t+1 timeline visualization.

    Parameters
    ----------
    df          : Full traffic DataFrame
    n_windows   : How many time windows to generate
    window_size : Number of rows per window

    Returns
    -------
    List of state dicts, earliest first.
    """
    total = len(df)
    states = []
    step = max(total // n_windows, window_size)

    for i in range(n_windows):
        start = max(0, total - (n_windows - i) * step)
        end   = start + window_size
        window = df.iloc[start:min(end, total)]
        state  = build_state_from_window(window)
        # Attach a label for display
        state["window_index"] = i
        state["label"]        = f"T-{n_windows - i - 1}" if i < n_windows - 1 else "T (now)"
        states.append(state)

    return states


def get_current_state(df: pd.DataFrame, tail_n: int = 3000) -> dict:
    """
    Compute the current state from the most recent `tail_n` rows of traffic.
    This is the S_t fed into the World Model at inference time.
    """
    window = df.tail(tail_n)
    # Estimate window duration from timestamps if available
    if "timestamp" in df.columns:
        ts = pd.to_datetime(window["timestamp"], errors="coerce").dropna()
        if len(ts) >= 2:
            duration = (ts.max() - ts.min()).total_seconds()
        else:
            duration = 60.0
    else:
        duration = 60.0

    return build_state_from_window(window, window_seconds=max(duration, 1.0))
