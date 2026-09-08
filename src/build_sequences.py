import pandas as pd
import numpy as np
from pathlib import Path


INPUT = Path("data/simulated/network_states.csv")
OUTPUT = Path("data/simulated/sequences.npz")

SEQUENCE_LENGTH = 5


# ------------------------------------------------------------
# Load network states
# ------------------------------------------------------------

df = pd.read_csv(INPUT)

df["window_start"] = pd.to_datetime(
    df["window_start"],
    format="mixed"
)

df = df.sort_values("window_start").reset_index(drop=True)

print(f"Loaded {len(df):,} network states")


# ------------------------------------------------------------
# Features used by the World Model
# ------------------------------------------------------------

FEATURE_COLUMNS = [
    "total_packets",
    "total_bytes",
    "unique_src_ips",
    "unique_dst_ips",
    "unique_dst_ports",
    "unique_src_ports",
    "mean_packet_size",
    "packet_size_std",
    "packet_size_min",
    "packet_size_max",
    "mean_ttl",
    "ttl_std",
    "mean_tcp_window",
    "tcp_window_std",
    "syn_count",
    "ack_count",
    "rst_count",
    "fin_count",
]


X = df[FEATURE_COLUMNS].values.astype(np.float32)

# Binary attack label
y_attack = df["label"].values.astype(np.int64)

# Attack/stage label
y_stage = df["attack_type"].values


# ------------------------------------------------------------
# Create sliding-window sequences
# ------------------------------------------------------------

X_sequences = []
Y_next_state = []
Y_attack = []
Y_stage = []


for i in range(SEQUENCE_LENGTH, len(df)):

    # Previous 5 network states
    sequence = X[
        i - SEQUENCE_LENGTH:i
    ]

    # Next network state
    next_state = X[i]

    # Attack status of next state
    next_attack = y_attack[i]

    # Attack type of next state
    next_stage = y_stage[i]

    X_sequences.append(sequence)
    Y_next_state.append(next_state)
    Y_attack.append(next_attack)
    Y_stage.append(next_stage)


X_sequences = np.array(
    X_sequences,
    dtype=np.float32
)

Y_next_state = np.array(
    Y_next_state,
    dtype=np.float32
)

Y_attack = np.array(
    Y_attack,
    dtype=np.int64
)

Y_stage = np.array(
    Y_stage
)


# ------------------------------------------------------------
# Save
# ------------------------------------------------------------

OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True
)

np.savez_compressed(
    OUTPUT,
    X=X_sequences,
    y_state=Y_next_state,
    y_attack=Y_attack,
    y_stage=Y_stage,
    feature_columns=np.array(FEATURE_COLUMNS)
)


# ------------------------------------------------------------
# Report
# ------------------------------------------------------------

print()
print("=" * 60)
print("SEQUENCE GENERATION COMPLETE")
print("=" * 60)

print(f"Sequence length : {SEQUENCE_LENGTH}")
print(f"Features/state  : {len(FEATURE_COLUMNS)}")

print(f"X shape         : {X_sequences.shape}")
print(f"Next state      : {Y_next_state.shape}")
print(f"Attack labels   : {Y_attack.shape}")

print()
print("Attack distribution of prediction targets:")

unique, counts = np.unique(
    Y_stage,
    return_counts=True
)

for name, count in zip(unique, counts):
    print(f"{name:20s} {count:,}")

print()
print(f"Output: {OUTPUT}")

print("=" * 60)