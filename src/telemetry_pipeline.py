"""
telemetry_pipeline.py
=====================
CSV → 44-feature network-state pipeline for uploaded telemetry.
SIH "AI World Models for Predictive Cyber Defence".

Converts an uploaded packet or flow CSV into the SAME 44-feature
representation used by the trained Temporal Transformer, using:
  - the same aggregation logic as build_fused_states.py
  - the same feature ordering as recorded in fused_train_val_test.npz
  - the SAME scaler (mean/scale from training data — never refit)

Pipeline
--------
CSV file
  → detect type (packet / flow)
  → timestamp parse + sort
  → 10-second floor windows
  → packet aggregations  (19 features)
  → flow aggregations    (19 features)
  → derived features     (5 features)
  → merge → 44 features in canonical order
  → standardise with training scaler
  → build sliding sequences of length 5
  → return for Transformer inference
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ============================================================
# Canonical 44-feature order
# (Must match feature_columns in fused_train_val_test.npz)
# ============================================================

FEATURE_COLUMNS: list[str] = [
    # Packet features (19)
    "packet_count",
    "packet_total_bytes",
    "packet_mean_size",
    "packet_std_size",
    "packet_min_size",
    "packet_max_size",
    "packet_mean_ttl",
    "packet_std_ttl",
    "packet_mean_tcp_window",
    "packet_std_tcp_window",
    "packet_syn_count",
    "packet_ack_count",
    "packet_rst_count",
    "packet_fin_count",
    "packet_unique_src_ips",
    "packet_unique_dst_ips",
    "packet_unique_src_ports",
    "packet_unique_dst_ports",
    "packet_unique_protocols",
    # Flow features (19)
    "flow_count",
    "flow_total_bytes",
    "flow_mean_duration",
    "flow_std_duration",
    "flow_total_fwd_packets",
    "flow_total_bwd_packets",
    "flow_mean_bytes_per_sec",
    "flow_mean_packets_per_sec",
    "flow_mean_iat",
    "flow_std_iat",
    "flow_mean_packet_length",
    "flow_std_packet_length",
    "flow_mean_fwd_pps",
    "flow_mean_bwd_pps",
    "flow_mean_down_up_ratio",
    "flow_syn_count",
    "flow_ack_count",
    "flow_rst_count",
    "flow_fin_count",
    "flow_unique_protocols",
    # Derived fusion features (5)
    "packet_to_flow_ratio",
    "bytes_per_packet",
    "bytes_per_flow",
    "syn_to_packet_ratio",
    "ack_to_packet_ratio",
]

WINDOW_SECONDS = 10
SEQUENCE_LENGTH = 5

# ============================================================
# Pipeline result dataclass
# ============================================================

class EntityInfo:
    """
    Represents a unique network entity (endpoint) found in the uploaded telemetry.

    Only populated when src_ip / dst_ip columns are present. Each entity
    corresponds to a distinct IP address observed as a SOURCE in the traffic.
    The risk/stage fields are populated from the NETWORK-LEVEL model inference
    (not per-entity inference) and are clearly labelled as network-scope.
    """

    def __init__(
        self,
        entity_id:       str,               # e.g. "192.168.1.10"
        record_count:    int,               # rows in the raw upload where this IP appears
        first_seen:      str,               # ISO timestamp
        last_seen:       str,               # ISO timestamp
        unique_dst_ips:  list[str],         # destination IPs this entity communicated with
        unique_dst_ports: list[int],        # destination ports
        protocols:       list[str],         # unique protocols used
    ) -> None:
        self.entity_id        = entity_id
        self.record_count     = record_count
        self.first_seen       = first_seen
        self.last_seen        = last_seen
        self.unique_dst_ips   = unique_dst_ips
        self.unique_dst_ports = unique_dst_ports
        self.protocols        = protocols


class PipelineResult:
    """Holds everything produced by process_uploaded_csv()."""

    def __init__(
        self,
        states_df:       pd.DataFrame,
        states_scaled:   np.ndarray,
        sequences:       np.ndarray,
        feature_columns: list[str],
        scaler_mean:     np.ndarray,
        scaler_scale:    np.ndarray,
        file_type:       str,
        n_records:       int,
        time_windows:    int,
        ts_start:        str,
        ts_end:          str,
        has_labels:      bool,
        label_col:       Optional[str],
        window_labels:   Optional[list],
        entities:        Optional[list],    # list[EntityInfo] | None
        has_entity_ids:  bool,              # True iff src_ip/dst_ip were present
        prediction_scope: str,             # "network-level" | "entity-level"
    ) -> None:
        self.states_df        = states_df         # (T, 44+) DataFrame
        self.states_scaled    = states_scaled     # (T, 44) float32
        self.sequences        = sequences         # (N, 5, 44) float32
        self.feature_columns  = feature_columns
        self.scaler_mean      = scaler_mean
        self.scaler_scale     = scaler_scale
        self.file_type        = file_type
        self.n_records        = n_records
        self.time_windows     = time_windows
        self.ts_start         = ts_start
        self.ts_end           = ts_end
        self.has_labels       = has_labels
        self.label_col        = label_col
        self.window_labels    = window_labels     # per-window ground-truth (or None)
        self.entities         = entities          # list[EntityInfo] or None
        self.has_entity_ids   = has_entity_ids
        self.prediction_scope = prediction_scope  # always "network-level" for current model


# ============================================================
# Main entry point
# ============================================================

def process_uploaded_csv(
    file_path:    Path,
    scaler_mean:  np.ndarray,
    scaler_scale: np.ndarray,
    file_type:    str = "auto",
) -> PipelineResult:
    """
    Convert an uploaded CSV into standardised 5×44 sequences.

    Parameters
    ----------
    file_path    : path to the saved CSV upload
    scaler_mean  : (44,) training-set feature means — never refit
    scaler_scale : (44,) training-set feature std   — never refit
    file_type    : "packet" | "flow" | "auto" (detect from columns)

    Returns
    -------
    PipelineResult

    Raises
    ------
    ValueError : insufficient temporal windows or feature mismatch
    """
    df = pd.read_csv(file_path, low_memory=False)
    n_records = len(df)

    # Normalise column names to lowercase
    df.columns = [c.lower().strip() for c in df.columns]

    # Auto-detect type
    if file_type == "auto":
        file_type = _detect_type(df.columns.tolist())

    # Parse timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed",
                                     errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    if len(df) == 0:
        raise ValueError("No rows with valid timestamps remain after parsing.")

    ts_start = str(df["timestamp"].min())
    ts_end   = str(df["timestamp"].max())

    # Detect labels
    has_labels = False
    label_col  = None
    for lc in ["label", "attack_type", "attack_stage"]:
        if lc in df.columns:
            has_labels = True
            label_col  = lc
            break

    # ── Build 10-second windows ────────────────────────────────
    df["window_start"] = df["timestamp"].dt.floor(f"{WINDOW_SECONDS}s")

    if file_type == "packet":
        states_df = _aggregate_packet(df)
    elif file_type == "flow":
        states_df = _aggregate_flow(df)
    else:
        raise ValueError(
            f"Cannot process file_type='{file_type}'. "
            "Upload a packet or flow CSV compatible with the training pipeline."
        )

    states_df = states_df.sort_values("window_start").reset_index(drop=True)
    time_windows = len(states_df)

    if time_windows < SEQUENCE_LENGTH:
        raise ValueError(
            f"Only {time_windows} temporal windows generated; "
            f"at least {SEQUENCE_LENGTH} are required for forecasting. "
            "Upload a longer traffic capture."
        )

    # ── Extract label per window ───────────────────────────────
    window_labels = None
    if has_labels:
        wl = (
            df.sort_values("timestamp")
            .groupby("window_start")
            .last()[[label_col]]
            .reset_index()
        )
        merged = states_df[["window_start"]].merge(wl, on="window_start", how="left")
        window_labels = merged[label_col].tolist()

    # ── Enforce canonical 44-feature order ────────────────────
    for col in FEATURE_COLUMNS:
        if col not in states_df.columns:
            states_df[col] = 0.0

    X_raw = states_df[FEATURE_COLUMNS].values.astype(np.float32)

    # ── Standardise using training scaler — never refit ───────
    safe_scale       = np.where(scaler_scale == 0, 1.0, scaler_scale)
    states_scaled    = ((X_raw - scaler_mean) / safe_scale).astype(np.float32)

    # ── Build sliding sequences ────────────────────────────────
    sequences = np.stack([
        states_scaled[i - SEQUENCE_LENGTH: i]
        for i in range(SEQUENCE_LENGTH, len(states_scaled) + 1)
    ]).astype(np.float32)

    # ── Extract entity identifiers ─────────────────────────────
    # Only when both src_ip and dst_ip columns are present in the raw data.
    # We never manufacture identifiers — if columns are absent we set
    # has_entity_ids=False and entities=None and label everything
    # "NETWORK-LEVEL PREDICTION".
    entities, has_entity_ids = _extract_entities(df)

    # The current model was trained on network-level aggregated states and
    # does not support entity-specific inference.  We always label the
    # prediction scope accordingly.
    prediction_scope = "network-level"

    return PipelineResult(
        states_df        = states_df,
        states_scaled    = states_scaled,
        sequences        = sequences,
        feature_columns  = FEATURE_COLUMNS,
        scaler_mean      = scaler_mean,
        scaler_scale     = scaler_scale,
        file_type        = file_type,
        n_records        = n_records,
        time_windows     = time_windows,
        ts_start         = ts_start,
        ts_end           = ts_end,
        has_labels       = has_labels,
        label_col        = label_col,
        window_labels    = window_labels,
        entities         = entities,
        has_entity_ids   = has_entity_ids,
        prediction_scope = prediction_scope,
    )


# ============================================================
# Entity extraction
# ============================================================

MAX_ENTITIES = 200          # cap to avoid huge payloads for very large uploads
MAX_DST_SHOW = 10           # max destination IPs/ports per entity


def _extract_entities(
    df: pd.DataFrame,
) -> tuple[Optional[list], bool]:
    """
    Extract unique source-IP entities from raw telemetry rows.

    Returns (entities, has_entity_ids).

    Rules
    -----
    - Only runs when BOTH 'src_ip' and 'dst_ip' columns are present.
    - Groups by src_ip; collects temporal coverage, destination diversity,
      protocol diversity, and record count.
    - Caps output at MAX_ENTITIES entries (sorted by record_count desc).
    - Returns (None, False) if the columns are absent — never manufactures IDs.
    """
    if "src_ip" not in df.columns or "dst_ip" not in df.columns:
        return None, False

    # Drop rows where src_ip is null / empty
    ent_df = df[df["src_ip"].notna() & (df["src_ip"].astype(str).str.strip() != "")].copy()
    if len(ent_df) == 0:
        return None, False

    ent_df["src_ip"] = ent_df["src_ip"].astype(str).str.strip()
    ent_df["dst_ip"] = ent_df["dst_ip"].astype(str).str.strip()

    entities: list[EntityInfo] = []

    grouped = ent_df.groupby("src_ip", sort=False)
    summary = (
        grouped
        .agg(
            record_count = ("timestamp", "count"),
            first_seen   = ("timestamp", "min"),
            last_seen    = ("timestamp", "max"),
        )
        .reset_index()
        .sort_values("record_count", ascending=False)
        .head(MAX_ENTITIES)
    )

    for _, row in summary.iterrows():
        ip    = str(row["src_ip"])
        grp   = ent_df[ent_df["src_ip"] == ip]

        dst_ips = (
            grp["dst_ip"].dropna().astype(str).str.strip()
            .value_counts().head(MAX_DST_SHOW).index.tolist()
        )

        dst_ports: list[int] = []
        if "dst_port" in grp.columns:
            raw_ports = (
                pd.to_numeric(grp["dst_port"], errors="coerce")
                .dropna().astype(int)
                .value_counts().head(MAX_DST_SHOW).index.tolist()
            )
            dst_ports = [int(p) for p in raw_ports]

        protocols: list[str] = []
        if "protocol" in grp.columns:
            protocols = (
                grp["protocol"].dropna().astype(str).str.strip()
                .unique().tolist()[:10]
            )

        entities.append(EntityInfo(
            entity_id        = ip,
            record_count     = int(row["record_count"]),
            first_seen       = str(row["first_seen"]),
            last_seen        = str(row["last_seen"]),
            unique_dst_ips   = dst_ips,
            unique_dst_ports = dst_ports,
            protocols        = protocols,
        ))

    if not entities:
        return None, False

    return entities, True


# ============================================================
# Packet aggregation
# (mirrors build_fused_states.py packet_features block)
# ============================================================

def _aggregate_packet(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw packet records into 10-second window states."""

    # Ensure numeric columns
    for col in ["packet_size", "ttl", "tcp_window", "syn", "ack", "rst", "fin",
                "src_port", "dst_port"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    pkt = (
        df.groupby("window_start")
        .agg(
            packet_count            = ("packet_size",  "count"),
            packet_total_bytes      = ("packet_size",  "sum"),
            packet_mean_size        = ("packet_size",  "mean"),
            packet_std_size         = ("packet_size",  "std"),
            packet_min_size         = ("packet_size",  "min"),
            packet_max_size         = ("packet_size",  "max"),
            packet_mean_ttl         = ("ttl",          "mean"),
            packet_std_ttl          = ("ttl",          "std"),
            packet_mean_tcp_window  = ("tcp_window",   "mean"),
            packet_std_tcp_window   = ("tcp_window",   "std"),
            packet_syn_count        = ("syn",          "sum"),
            packet_ack_count        = ("ack",          "sum"),
            packet_rst_count        = ("rst",          "sum"),
            packet_fin_count        = ("fin",          "sum"),
            packet_unique_src_ips   = ("src_ip",       "nunique"),
            packet_unique_dst_ips   = ("dst_ip",       "nunique"),
            packet_unique_src_ports = ("src_port",     "nunique"),
            packet_unique_dst_ports = ("dst_port",     "nunique"),
            packet_unique_protocols = ("protocol",     "nunique"),
        )
        .reset_index()
    )

    # Flow columns — fill with neutral values since this is packet-only
    for col in [
        "flow_count", "flow_total_bytes", "flow_mean_duration", "flow_std_duration",
        "flow_total_fwd_packets", "flow_total_bwd_packets",
        "flow_mean_bytes_per_sec", "flow_mean_packets_per_sec",
        "flow_mean_iat", "flow_std_iat", "flow_mean_packet_length",
        "flow_std_packet_length", "flow_mean_fwd_pps", "flow_mean_bwd_pps",
        "flow_mean_down_up_ratio", "flow_syn_count", "flow_ack_count",
        "flow_rst_count", "flow_fin_count", "flow_unique_protocols",
    ]:
        pkt[col] = 0.0

    # flow_count = packet_count when only packet data available
    pkt["flow_count"] = pkt["packet_count"]

    return _add_derived(pkt)


# ============================================================
# Flow aggregation
# (mirrors build_fused_states.py flow_features block)
# ============================================================

def _aggregate_flow(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate flow records into 10-second window states."""

    # Ensure numeric flow columns
    flow_num_cols = [
        "flow_duration", "total_fwd_packets", "total_bwd_packets",
        "fwd_bytes", "bwd_bytes", "total_bytes",
        "flow_bytes_per_sec", "flow_packets_per_sec",
        "flow_iat_mean", "flow_iat_std",
        "packet_length_mean", "packet_length_std",
        "fwd_packets_per_sec", "bwd_packets_per_sec",
        "down_up_ratio", "syn_flag_count", "ack_flag_count",
        "rst_flag_count", "fin_flag_count",
    ]
    for col in flow_num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    flow = (
        df.groupby("window_start")
        .agg(
            flow_count              = ("flow_duration",      "count"),
            flow_total_bytes        = ("total_bytes",        "sum"),
            flow_mean_duration      = ("flow_duration",      "mean"),
            flow_std_duration       = ("flow_duration",      "std"),
            flow_total_fwd_packets  = ("total_fwd_packets",  "sum"),
            flow_total_bwd_packets  = ("total_bwd_packets",  "sum"),
            flow_mean_bytes_per_sec = ("flow_bytes_per_sec", "mean"),
            flow_mean_packets_per_sec=("flow_packets_per_sec","mean"),
            flow_mean_iat           = ("flow_iat_mean",      "mean"),
            flow_std_iat            = ("flow_iat_std",       "mean"),
            flow_mean_packet_length = ("packet_length_mean", "mean"),
            flow_std_packet_length  = ("packet_length_std",  "mean"),
            flow_mean_fwd_pps       = ("fwd_packets_per_sec","mean"),
            flow_mean_bwd_pps       = ("bwd_packets_per_sec","mean"),
            flow_mean_down_up_ratio = ("down_up_ratio",      "mean"),
            flow_syn_count          = ("syn_flag_count",     "sum"),
            flow_ack_count          = ("ack_flag_count",     "sum"),
            flow_rst_count          = ("rst_flag_count",     "sum"),
            flow_fin_count          = ("fin_flag_count",     "sum"),
            flow_unique_protocols   = ("protocol",           "nunique"),
        )
        .reset_index()
    )

    # Packet columns — approximate from flow data
    flow["packet_count"]           = flow["flow_total_fwd_packets"] + flow["flow_total_bwd_packets"]
    flow["packet_total_bytes"]     = flow["flow_total_bytes"]
    flow["packet_mean_size"]       = flow["flow_mean_packet_length"]
    flow["packet_std_size"]        = flow["flow_std_packet_length"]
    flow["packet_min_size"]        = 0.0
    flow["packet_max_size"]        = 0.0
    flow["packet_mean_ttl"]        = 64.0
    flow["packet_std_ttl"]         = 0.0
    flow["packet_mean_tcp_window"] = 0.0
    flow["packet_std_tcp_window"]  = 0.0
    flow["packet_syn_count"]       = flow["flow_syn_count"]
    flow["packet_ack_count"]       = flow["flow_ack_count"]
    flow["packet_rst_count"]       = flow["flow_rst_count"]
    flow["packet_fin_count"]       = flow["flow_fin_count"]
    flow["packet_unique_protocols"]= flow["flow_unique_protocols"]

    # IP/port diversity: approximate from flow count
    flow["packet_unique_src_ips"]   = np.maximum(1, flow["flow_count"] // 3)
    flow["packet_unique_dst_ips"]   = np.maximum(1, flow["flow_count"] // 5)
    flow["packet_unique_src_ports"] = flow["flow_count"]
    flow["packet_unique_dst_ports"] = np.maximum(1, flow["flow_count"] // 4)

    return _add_derived(flow)


# ============================================================
# Derived features
# (mirrors build_fused_states.py derived-fusion block)
# ============================================================

def _add_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["packet_to_flow_ratio"] = (
        df["packet_count"] / df["flow_count"].replace(0, np.nan)
    )
    df["bytes_per_packet"] = (
        df["packet_total_bytes"] / df["packet_count"].replace(0, np.nan)
    )
    df["bytes_per_flow"] = (
        df["flow_total_bytes"] / df["flow_count"].replace(0, np.nan)
    )
    df["syn_to_packet_ratio"] = (
        df["packet_syn_count"] / df["packet_count"].replace(0, np.nan)
    )
    df["ack_to_packet_ratio"] = (
        df["packet_ack_count"] / df["packet_count"].replace(0, np.nan)
    )

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = (
        df[numeric_cols]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0)
    )
    return df


# ============================================================
# Type detection
# ============================================================

def _detect_type(columns: list[str]) -> str:
    flow_score   = sum(1 for c in ["flow_duration", "total_bytes",
                                    "flow_iat_mean", "syn_flag_count"]
                       if c in columns)
    packet_score = sum(1 for c in ["packet_size", "ttl",
                                    "tcp_window", "syn"]
                       if c in columns)
    if flow_score >= 2:
        return "flow"
    if packet_score >= 2:
        return "packet"
    return "unknown"
