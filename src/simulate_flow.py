import numpy as np
import pandas as pd
from pathlib import Path

# ============================================================
# Simulated Flow Telemetry Generator
# ============================================================

PROJECT = Path(r"D:\Network_Attak_Forecasting")
OUT_DIR = PROJECT / "data" / "simulated"

OUT_DIR.mkdir(parents=True, exist_ok=True)

PACKET_FILE = OUT_DIR / "simulated_packets.csv"
FLOW_FILE = OUT_DIR / "simulated_flow.csv"

RANDOM_SEED = 42
N_RECORDS = 50000

rng = np.random.default_rng(RANDOM_SEED)


# ------------------------------------------------------------
# 1. Use existing packet timeline if available
# ------------------------------------------------------------

if PACKET_FILE.exists():

    packet_ts = pd.read_csv(
        PACKET_FILE,
        usecols=["timestamp"]
    )

    timestamps = pd.to_datetime(
        packet_ts["timestamp"],
        format="mixed"
    )

    n = len(timestamps)

else:

    increments_ms = rng.integers(
        1,
        1500,
        size=N_RECORDS
    )

    timestamps = (
        pd.Timestamp("2026-09-01 10:00:00")
        + pd.to_timedelta(
            np.cumsum(increments_ms),
            unit="ms"
        )
    )

    n = N_RECORDS


# ------------------------------------------------------------
# 2. Attack progression
# ------------------------------------------------------------

t = np.arange(n) / n

stages = np.select(
    [
        t < 0.30,
        t < 0.45,
        t < 0.60,
        t < 0.75
    ],
    [
        "Benign",
        "Reconnaissance",
        "BruteForce",
        "LateralMovement"
    ],
    default="CommandAndControl"
)


# ------------------------------------------------------------
# 3. Add small amount of stage noise
# ------------------------------------------------------------

stage_order = [
    "Benign",
    "Reconnaissance",
    "BruteForce",
    "LateralMovement",
    "CommandAndControl"
]

noise_mask = rng.random(n) < 0.06

for i in np.where(noise_mask)[0]:

    current_index = stage_order.index(
        stages[i]
    )

    lo = max(
        0,
        current_index - 1
    )

    hi = min(
        len(stage_order),
        current_index + 2
    )

    stages[i] = rng.choice(
        stage_order[lo:hi]
    )


# ------------------------------------------------------------
# 4. Attack intensity
# ------------------------------------------------------------

intensity_map = {

    "Benign": 0.15,

    "Reconnaissance": 0.40,

    "BruteForce": 0.65,

    "LateralMovement": 0.78,

    "CommandAndControl": 0.58
}

intensity = np.array(
    [
        intensity_map[s]
        for s in stages
    ]
)

intensity = np.clip(
    intensity + rng.normal(0, 0.08, n),
    0.02,
    1.0
)


# ------------------------------------------------------------
# 5. Protocol
# ------------------------------------------------------------

protocol = rng.choice(
    [
        "TCP",
        "UDP",
        "ICMP"
    ],
    size=n,
    p=[
        0.68,
        0.22,
        0.10
    ]
)


# ------------------------------------------------------------
# 6. Flow characteristics
# ------------------------------------------------------------

duration_ms = np.clip(
    rng.lognormal(
        np.log(120 + 450 * intensity),
        0.65
    ),
    1,
    60000
)

fwd_packets = np.maximum(
    1,
    rng.poisson(
        3 + 9 * intensity
    )
)

bwd_packets = np.maximum(
    0,
    rng.poisson(
        2 + 7 * (1 - 0.3 * intensity)
    )
)


# ------------------------------------------------------------
# 7. Packet lengths
# ------------------------------------------------------------

fwd_pkt_len = np.clip(
    rng.normal(
        420 - 80 * intensity,
        90,
        n
    ),
    40,
    1500
)

bwd_pkt_len = np.clip(
    rng.normal(
        380 + 100 * intensity,
        100,
        n
    ),
    40,
    1500
)


# ------------------------------------------------------------
# 8. Bytes and packet counts
# ------------------------------------------------------------

fwd_bytes = np.maximum(
    40,
    fwd_packets * fwd_pkt_len
)

bwd_bytes = np.maximum(
    0,
    bwd_packets * bwd_pkt_len
)

total_packets = (
    fwd_packets +
    bwd_packets
)

total_bytes = (
    fwd_bytes +
    bwd_bytes
)


# ------------------------------------------------------------
# 9. Flow rates
# ------------------------------------------------------------

duration_s = (
    duration_ms / 1000.0
)

flow_bytes_per_sec = (
    total_bytes /
    np.maximum(duration_s, 0.001)
)

flow_packets_per_sec = (
    total_packets /
    np.maximum(duration_s, 0.001)
)


# ------------------------------------------------------------
# 10. Inter-arrival-time features
# ------------------------------------------------------------

flow_iat_mean = np.maximum(
    0.05,
    duration_s /
    np.maximum(
        total_packets - 1,
        1
    )
)

flow_iat_std = np.maximum(
    0.01,
    flow_iat_mean *
    rng.uniform(
        0.2,
        0.8,
        n
    )
)


# ------------------------------------------------------------
# 11. Packet-length statistics
# ------------------------------------------------------------

packet_length_mean = (
    total_bytes /
    np.maximum(
        total_packets,
        1
    )
)

packet_length_std = np.clip(
    rng.normal(
        90 + 80 * intensity,
        25,
        n
    ),
    5,
    400
)


# ------------------------------------------------------------
# 12. Packet rates
# ------------------------------------------------------------

fwd_packets_per_sec = (
    fwd_packets /
    np.maximum(
        duration_s,
        0.001
    )
)

bwd_packets_per_sec = (
    bwd_packets /
    np.maximum(
        duration_s,
        0.001
    )
)

down_up_ratio = (
    bwd_packets /
    np.maximum(
        fwd_packets,
        1
    )
)


# ------------------------------------------------------------
# 13. TCP flags
# ------------------------------------------------------------

tcp = (
    protocol == "TCP"
).astype(float)

syn = (
    rng.binomial(
        2,
        np.clip(
            0.08 + 0.35 * intensity,
            0.02,
            0.85
        )
    )
    * tcp
)

ack = (
    rng.binomial(
        np.maximum(
            total_packets,
            1
        ),
        np.clip(
            0.35 +
            0.25 * (1 - intensity),
            0.05,
            0.90
        )
    )
    * tcp
)

rst = (
    rng.binomial(
        2,
        np.clip(
            0.03 + 0.12 * intensity,
            0.01,
            0.45
        )
    )
    * tcp
)

fin = (
    rng.binomial(
        2,
        np.clip(
            0.04 + 0.04 * (1 - intensity),
            0.01,
            0.20
        )
    )
    * tcp
)


# ------------------------------------------------------------
# 14. Ports
# ------------------------------------------------------------

common_ports = np.array([
    22,
    23,
    53,
    80,
    443,
    445,
    3389,
    8080
])

dst_port = rng.choice(
    common_ports,
    size=n
)

src_port = rng.integers(
    1024,
    65535,
    size=n
)


# ------------------------------------------------------------
# 15. Stage-specific destination ports
# ------------------------------------------------------------

stage_port_probs = {

    "Reconnaissance": np.array([
        0.05,
        0.03,
        0.08,
        0.30,
        0.20,
        0.18,
        0.10,
        0.06
    ]),

    "BruteForce": np.array([
        0.30,
        0.05,
        0.03,
        0.15,
        0.12,
        0.18,
        0.12,
        0.05
    ])
}

for stage, probs in stage_port_probs.items():

    mask = (
        stages == stage
    )

    if mask.any():

        dst_port[mask] = rng.choice(
            common_ports,
            size=mask.sum(),
            p=probs / probs.sum()
        )


# ------------------------------------------------------------
# 16. IP addresses
# ------------------------------------------------------------

src_id = rng.integers(
    1,
    251,
    n
)

dst_id = rng.integers(
    1,
    51,
    n
)

src_ip = np.array([
    f"10.0.{x // 256}.{x % 256}"
    for x in src_id
])

dst_ip = np.array([
    f"192.168.{x // 256}.{x % 256}"
    for x in dst_id
])


# ------------------------------------------------------------
# 17. Create dataframe
# ------------------------------------------------------------

df = pd.DataFrame({

    "timestamp": timestamps,

    "src_ip": src_ip,

    "dst_ip": dst_ip,

    "src_port": src_port,

    "dst_port": dst_port,

    "protocol": protocol,

    "flow_duration": duration_ms,

    "total_fwd_packets": fwd_packets,

    "total_bwd_packets": bwd_packets,

    "fwd_bytes": np.round(
        fwd_bytes,
        2
    ),

    "bwd_bytes": np.round(
        bwd_bytes,
        2
    ),

    "total_bytes": np.round(
        total_bytes,
        2
    ),

    "flow_bytes_per_sec": np.round(
        flow_bytes_per_sec,
        2
    ),

    "flow_packets_per_sec": np.round(
        flow_packets_per_sec,
        2
    ),

    "flow_iat_mean": np.round(
        flow_iat_mean,
        6
    ),

    "flow_iat_std": np.round(
        flow_iat_std,
        6
    ),

    "packet_length_mean": np.round(
        packet_length_mean,
        2
    ),

    "packet_length_std": np.round(
        packet_length_std,
        2
    ),

    "fwd_packets_per_sec": np.round(
        fwd_packets_per_sec,
        2
    ),

    "bwd_packets_per_sec": np.round(
        bwd_packets_per_sec,
        2
    ),

    "down_up_ratio": np.round(
        down_up_ratio,
        4
    ),

    "syn_flag_count": syn.astype(int),

    "ack_flag_count": ack.astype(int),

    "rst_flag_count": rst.astype(int),

    "fin_flag_count": fin.astype(int),

    "attack_stage": stages,

    "label": (
        stages != "Benign"
    ).astype(int)
})


# ------------------------------------------------------------
# 18. Save
# ------------------------------------------------------------

df.to_csv(
    FLOW_FILE,
    index=False
)


# ------------------------------------------------------------
# 19. Verification
# ------------------------------------------------------------

print("=" * 60)
print("SIMULATED FLOW DATASET CREATED")
print("=" * 60)

print(
    f"Output : {FLOW_FILE}"
)

print(
    f"Shape  : {df.shape}"
)

print(
    f"Start  : {df['timestamp'].min()}"
)

print(
    f"End    : {df['timestamp'].max()}"
)

print("\nStage distribution:")

print(
    df["attack_stage"]
    .value_counts()
    .sort_index()
)

print("\nColumns:")

print(
    df.columns.tolist()
)

print("\nFirst 5 rows:")

print(
    df.head().to_string(
        index=False
    )
)