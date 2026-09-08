import pandas as pd
import numpy as np
from pathlib import Path

# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(r"D:\Network_Attak_Forecasting")

FLOW_FILE = BASE_DIR / "data" / "simulated" / "simulated_flow.csv"
PACKET_FILE = BASE_DIR / "data" / "simulated" / "simulated_packets.csv"

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "simulated"
    / "fused_network_states.csv"
)

WINDOW_SECONDS = 10


# ============================================================
# Load data
# ============================================================

print("Loading flow telemetry...")
flow = pd.read_csv(FLOW_FILE)

print("Loading packet telemetry...")
packet = pd.read_csv(PACKET_FILE)

print("Flow shape:", flow.shape)
print("Packet shape:", packet.shape)


# ============================================================
# Timestamp conversion
# ============================================================

flow["timestamp"] = pd.to_datetime(
    flow["timestamp"],
    format="mixed"
)

packet["timestamp"] = pd.to_datetime(
    packet["timestamp"],
    format="mixed"
)

flow = flow.sort_values("timestamp").reset_index(drop=True)
packet = packet.sort_values("timestamp").reset_index(drop=True)


# ============================================================
# Create common 10-second windows
# ============================================================

flow["window_start"] = (
    flow["timestamp"].dt.floor(f"{WINDOW_SECONDS}s")
)

packet["window_start"] = (
    packet["timestamp"].dt.floor(f"{WINDOW_SECONDS}s")
)


# ============================================================
# PACKET-LEVEL FEATURES
# ============================================================

packet_features = (
    packet
    .groupby("window_start")
    .agg(
        packet_count=("packet_size", "count"),

        packet_total_bytes=("packet_size", "sum"),
        packet_mean_size=("packet_size", "mean"),
        packet_std_size=("packet_size", "std"),

        packet_min_size=("packet_size", "min"),
        packet_max_size=("packet_size", "max"),

        packet_mean_ttl=("ttl", "mean"),
        packet_std_ttl=("ttl", "std"),

        packet_mean_tcp_window=("tcp_window", "mean"),
        packet_std_tcp_window=("tcp_window", "std"),

        packet_syn_count=("syn", "sum"),
        packet_ack_count=("ack", "sum"),
        packet_rst_count=("rst", "sum"),
        packet_fin_count=("fin", "sum"),

        packet_unique_src_ips=("src_ip", "nunique"),
        packet_unique_dst_ips=("dst_ip", "nunique"),

        packet_unique_src_ports=("src_port", "nunique"),
        packet_unique_dst_ports=("dst_port", "nunique"),

        packet_unique_protocols=("protocol", "nunique"),
    )
    .reset_index()
)


# ============================================================
# FLOW-LEVEL FEATURES
# ============================================================

flow_features = (
    flow
    .groupby("window_start")
    .agg(
        flow_count=("flow_duration", "count"),

        flow_total_bytes=("total_bytes", "sum"),

        flow_mean_duration=("flow_duration", "mean"),
        flow_std_duration=("flow_duration", "std"),

        flow_total_fwd_packets=("total_fwd_packets", "sum"),
        flow_total_bwd_packets=("total_bwd_packets", "sum"),

        flow_mean_bytes_per_sec=("flow_bytes_per_sec", "mean"),
        flow_mean_packets_per_sec=("flow_packets_per_sec", "mean"),

        flow_mean_iat=("flow_iat_mean", "mean"),
        flow_std_iat=("flow_iat_std", "mean"),

        flow_mean_packet_length=("packet_length_mean", "mean"),
        flow_std_packet_length=("packet_length_std", "mean"),

        flow_mean_fwd_pps=("fwd_packets_per_sec", "mean"),
        flow_mean_bwd_pps=("bwd_packets_per_sec", "mean"),

        flow_mean_down_up_ratio=("down_up_ratio", "mean"),

        flow_syn_count=("syn_flag_count", "sum"),
        flow_ack_count=("ack_flag_count", "sum"),
        flow_rst_count=("rst_flag_count", "sum"),
        flow_fin_count=("fin_flag_count", "sum"),

        flow_unique_protocols=("protocol", "nunique"),
    )
    .reset_index()
)


# ============================================================
# Merge flow + packet states
# ============================================================

states = pd.merge(
    packet_features,
    flow_features,
    on="window_start",
    how="outer"
)


# ============================================================
# Fill missing numerical values
# ============================================================

numeric_columns = states.select_dtypes(
    include=[np.number]
).columns

states[numeric_columns] = (
    states[numeric_columns]
    .replace([np.inf, -np.inf], np.nan)
    .fillna(0)
)


# ============================================================
# Derived fusion features
# ============================================================

states["packet_to_flow_ratio"] = (
    states["packet_count"]
    / states["flow_count"].replace(0, np.nan)
)

states["bytes_per_packet"] = (
    states["packet_total_bytes"]
    / states["packet_count"].replace(0, np.nan)
)

states["bytes_per_flow"] = (
    states["flow_total_bytes"]
    / states["flow_count"].replace(0, np.nan)
)

states["syn_to_packet_ratio"] = (
    states["packet_syn_count"]
    / states["packet_count"].replace(0, np.nan)
)

states["ack_to_packet_ratio"] = (
    states["packet_ack_count"]
    / states["packet_count"].replace(0, np.nan)
)

states = states.replace(
    [np.inf, -np.inf],
    np.nan
).fillna(0)


# ============================================================
# Determine temporal attack stage
# ============================================================

# Use the LAST observed stage in each window.
# This gives us a temporal state label rather than mixing
# future observations into the current state.

stage_per_window = (
    flow
    .sort_values("timestamp")
    .groupby("window_start")
    .tail(1)[
        ["window_start", "attack_stage", "label"]
    ]
)

states = pd.merge(
    states,
    stage_per_window,
    on="window_start",
    how="left"
)


# ============================================================
# Sort chronologically
# ============================================================

states = states.sort_values(
    "window_start"
).reset_index(drop=True)


# ============================================================
# Save
# ============================================================

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

states.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# Report
# ============================================================

print("\n========================================")
print("FUSED NETWORK STATES CREATED")
print("========================================")

print("Output:", OUTPUT_FILE)
print("Shape:", states.shape)

print("\nTime range:")
print(states["window_start"].min())
print("->")
print(states["window_start"].max())

print("\nNumber of temporal states:")
print(len(states))

print("\nFeature count:")
print(len(states.columns))

print("\nAttack stages:")
print(states["attack_stage"].value_counts())

print("\nMissing values:")
print(states.isnull().sum().sum())

print("\nFirst 5 states:")
print(states.head().to_string())