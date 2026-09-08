"""
data_loader.py — Unified data ingestion layer.

The frontend calls load_traffic_data() regardless of the source type.
When the real ML backend is connected, only this file needs to change.

Supported sources (current):
  - simulated  : CSV produced by generate_data.py
  - cicids      : CIC-IDS2018 flow CSV (schema mapped at load time)
  - pcap        : placeholder — not yet implemented

Returns a normalised pandas DataFrame with a guaranteed column set.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from frontend.utils.constants import SIMULATED_DATA_PATH

# ── Guaranteed output columns after normalisation ─────────────────────────────
REQUIRED_COLS = [
    "timestamp", "src_ip", "dst_ip", "src_port", "dst_port",
    "protocol", "packet_size", "ttl", "tcp_window",
    "syn", "ack", "rst", "fin", "attack_type", "label",
]


# ── Column maps for non-simulated sources ─────────────────────────────────────
CICIDS_COL_MAP = {
    # CIC-IDS2018 column name  →  our canonical name
    "Timestamp":               "timestamp",
    "Src IP":                  "src_ip",
    "Dst IP":                  "dst_ip",
    "Src Port":                "src_port",
    "Dst Port":                "dst_port",
    "Protocol":                "protocol",
    "Fwd Packet Length Mean":  "packet_size",
    "TTL":                     "ttl",
    "Init_Win_bytes_forward":  "tcp_window",
    "SYN Flag Count":          "syn",
    "ACK Flag Count":          "ack",
    "RST Flag Count":          "rst",
    "FIN Flag Count":          "fin",
    "Label":                   "attack_type",
}


def _fill_missing_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Add any missing required columns with sensible defaults."""
    defaults = {
        "ttl": 64, "tcp_window": 65535,
        "syn": 0, "ack": 0, "rst": 0, "fin": 0,
        "packet_size": 512, "label": 0,
        "attack_type": "Unknown",
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
    return df


def _normalise_simulated(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return _fill_missing_cols(df)


def _normalise_cicids(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.rename(columns=CICIDS_COL_MAP, inplace=True)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if "attack_type" in df.columns:
        df["label"] = (df["attack_type"].str.strip().str.upper() != "BENIGN").astype(int)
    return _fill_missing_cols(df)


# ── Public API ─────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_default_simulated() -> Optional[pd.DataFrame]:
    """Load the bundled simulated dataset (auto-loaded on app start)."""
    if SIMULATED_DATA_PATH.exists():
        df = pd.read_csv(SIMULATED_DATA_PATH)
        return _normalise_simulated(df)
    return None


def load_traffic_data(
    source_type: str,
    uploaded_file=None,
) -> tuple[Optional[pd.DataFrame], str]:
    """
    Main ingestion entry point.

    Parameters
    ----------
    source_type : str
        One of 'simulated', 'cicids', 'pcap'
    uploaded_file :
        A Streamlit UploadedFile object (or None to use the bundled file).

    Returns
    -------
    (df, message)  — df is None on failure; message describes what happened.
    """
    try:
        if source_type == "pcap":
            return None, "⚠️ PCAP ingestion is not yet implemented. Upload a CSV instead."

        if uploaded_file is not None:
            raw = pd.read_csv(io.StringIO(uploaded_file.read().decode("utf-8", errors="replace")))
        elif source_type == "simulated":
            if not SIMULATED_DATA_PATH.exists():
                return None, f"Default dataset not found at {SIMULATED_DATA_PATH}. Run generate_data.py first."
            raw = pd.read_csv(SIMULATED_DATA_PATH)
        else:
            return None, "No file uploaded. Please upload a CSV file."

        if source_type == "simulated":
            df = _normalise_simulated(raw)
        elif source_type == "cicids":
            df = _normalise_cicids(raw)
        else:
            df = _normalise_simulated(raw)   # fallback

        n = len(df)
        return df, f"✅ Loaded {n:,} records successfully."

    except Exception as exc:  # noqa: BLE001
        return None, f"❌ Failed to load data: {exc}"


def get_summary_stats(df: pd.DataFrame) -> dict:
    """
    Compute summary statistics shown on the Upload page.
    Safe to call on any normalised DataFrame.
    """
    stats: dict = {}

    stats["total_records"]    = len(df)
    stats["unique_src_ips"]   = df["src_ip"].nunique()  if "src_ip"  in df.columns else 0
    stats["unique_dst_ips"]   = df["dst_ip"].nunique()  if "dst_ip"  in df.columns else 0

    if "protocol" in df.columns:
        stats["protocol_dist"] = df["protocol"].value_counts().to_dict()
    else:
        stats["protocol_dist"] = {}

    if "attack_type" in df.columns:
        stats["label_dist"] = df["attack_type"].value_counts().to_dict()
    else:
        stats["label_dist"] = {}

    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce").dropna()
        if len(ts):
            stats["time_start"] = ts.min()
            stats["time_end"]   = ts.max()
            stats["duration_s"] = (ts.max() - ts.min()).total_seconds()
        else:
            stats["time_start"] = stats["time_end"] = stats["duration_s"] = None
    else:
        stats["time_start"] = stats["time_end"] = stats["duration_s"] = None

    if "packet_size" in df.columns:
        stats["avg_packet_size"] = float(df["packet_size"].mean())
        stats["max_packet_size"] = float(df["packet_size"].max())
        stats["min_packet_size"] = float(df["packet_size"].min())
    else:
        stats["avg_packet_size"] = stats["max_packet_size"] = stats["min_packet_size"] = 0.0

    stats["attack_ratio"] = float(df["label"].mean()) if "label" in df.columns else 0.0

    return stats
