import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# Configuration
# ============================================================

BASE_DIR = Path(r"D:\Network_Attak_Forecasting")

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "simulated"
    / "fused_network_states.csv"
)

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "simulated"
    / "fused_sequences.npz"
)

SEQUENCE_LENGTH = 5


# ============================================================
# Load fused states
# ============================================================

print("Loading fused network states...")

df = pd.read_csv(INPUT_FILE)

df["window_start"] = pd.to_datetime(
    df["window_start"],
    format="mixed"
)

df = df.sort_values(
    "window_start"
).reset_index(drop=True)

print("Input shape:", df.shape)


# ============================================================
# Define target stage encoding
# ============================================================

STAGE_MAP = {
    "Benign": 0,
    "Reconnaissance": 1,
    "BruteForce": 2,
    "LateralMovement": 3,
    "CommandAndControl": 4
}

df["stage_id"] = df["attack_stage"].map(STAGE_MAP)


# ============================================================
# Select model features
# ============================================================

# These are telemetry features only.
# Timestamp, attack_stage, label and stage_id are excluded
# to prevent target leakage.

EXCLUDED_COLUMNS = {
    "window_start",
    "attack_stage",
    "label",
    "stage_id"
}

FEATURE_COLUMNS = [
    c for c in df.columns
    if c not in EXCLUDED_COLUMNS
]


print("\nNumber of input features:", len(FEATURE_COLUMNS))

print("\nInput features:")
for i, col in enumerate(FEATURE_COLUMNS):
    print(f"{i:02d}: {col}")


# ============================================================
# Convert to numpy
# ============================================================

X_states = df[FEATURE_COLUMNS].astype(np.float32).values

y_stage_all = df["stage_id"].astype(np.int64).values

y_attack_all = df["label"].astype(np.float32).values


# ============================================================
# Build sequences
# ============================================================

X = []
y_state = []
y_attack = []
y_stage = []

num_states = len(df)

for i in range(SEQUENCE_LENGTH, num_states):

    # Historical states
    sequence = X_states[
        i - SEQUENCE_LENGTH:i
    ]

    # Future state at t+1
    future_state = X_states[i]

    # Future attack label
    future_attack = y_attack_all[i]

    # Future attack stage
    future_stage = y_stage_all[i]

    X.append(sequence)
    y_state.append(future_state)
    y_attack.append(future_attack)
    y_stage.append(future_stage)


# ============================================================
# Convert arrays
# ============================================================

X = np.asarray(X, dtype=np.float32)

y_state = np.asarray(
    y_state,
    dtype=np.float32
)

y_attack = np.asarray(
    y_attack,
    dtype=np.float32
)

y_stage = np.asarray(
    y_stage,
    dtype=np.int64
)


# ============================================================
# Save
# ============================================================

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

np.savez_compressed(
    OUTPUT_FILE,
    X=X,
    y_state=y_state,
    y_attack=y_attack,
    y_stage=y_stage,
    feature_columns=np.asarray(FEATURE_COLUMNS),
    stage_names=np.asarray(
        list(STAGE_MAP.keys())
    )
)


# ============================================================
# Report
# ============================================================

print("\n========================================")
print("SEQUENCES CREATED")
print("========================================")

print("Output:", OUTPUT_FILE)

print("\nX shape:")
print(X.shape)

print("\ny_state shape:")
print(y_state.shape)

print("\ny_attack shape:")
print(y_attack.shape)

print("\ny_stage shape:")
print(y_stage.shape)

print("\nStage distribution:")

unique, counts = np.unique(
    y_stage,
    return_counts=True
)

reverse_map = {
    v: k for k, v in STAGE_MAP.items()
}

for stage_id, count in zip(unique, counts):
    print(
        f"{reverse_map[stage_id]:20s}: {count}"
    )

print("\nAttack distribution:")

unique, counts = np.unique(
    y_attack,
    return_counts=True
)

for value, count in zip(unique, counts):
    print(
        f"label {int(value)}: {count}"
    )

print("\nFirst sequence:")
print(X[0])

print("\nFirst target stage:")
print(
    reverse_map[int(y_stage[0])]
)

print("\nFirst target attack:")
print(
    int(y_attack[0])
)

print("\nFeature count:")
print(len(FEATURE_COLUMNS))

print("\nSequence length:")
print(SEQUENCE_LENGTH)