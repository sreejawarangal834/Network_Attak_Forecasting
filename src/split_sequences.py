import numpy as np
from pathlib import Path


INPUT = Path("data/simulated/sequences.npz")
OUTPUT = Path("data/simulated")


# ------------------------------------------------------------
# Load sequences
# ------------------------------------------------------------

data = np.load(INPUT, allow_pickle=True)

X = data["X"]
y_state = data["y_state"]
y_attack = data["y_attack"]
y_stage = data["y_stage"]

feature_columns = data["feature_columns"]

print("Total sequences:", len(X))


# ------------------------------------------------------------
# Chronological split
# ------------------------------------------------------------

n = len(X)

train_end = int(n * 0.70)
val_end = int(n * 0.85)


X_train = X[:train_end]
X_val = X[train_end:val_end]
X_test = X[val_end:]


y_state_train = y_state[:train_end]
y_state_val = y_state[train_end:val_end]
y_state_test = y_state[val_end:]


y_attack_train = y_attack[:train_end]
y_attack_val = y_attack[train_end:val_end]
y_attack_test = y_attack[val_end:]


y_stage_train = y_stage[:train_end]
y_stage_val = y_stage[train_end:val_end]
y_stage_test = y_stage[val_end:]


# ------------------------------------------------------------
# Save
# ------------------------------------------------------------

np.savez_compressed(
    OUTPUT / "train.npz",
    X=X_train,
    y_state=y_state_train,
    y_attack=y_attack_train,
    y_stage=y_stage_train,
    feature_columns=feature_columns,
)

np.savez_compressed(
    OUTPUT / "validation.npz",
    X=X_val,
    y_state=y_state_val,
    y_attack=y_attack_val,
    y_stage=y_stage_val,
    feature_columns=feature_columns,
)

np.savez_compressed(
    OUTPUT / "test.npz",
    X=X_test,
    y_state=y_state_test,
    y_attack=y_attack_test,
    y_stage=y_stage_test,
    feature_columns=feature_columns,
)


# ------------------------------------------------------------
# Report
# ------------------------------------------------------------

print()
print("=" * 60)
print("CHRONOLOGICAL SPLIT COMPLETE")
print("=" * 60)

print(f"Training   : {len(X_train)} sequences")
print(f"Validation : {len(X_val)} sequences")
print(f"Testing    : {len(X_test)} sequences")

print()
print("Shapes:")
print("Train:", X_train.shape)
print("Val  :", X_val.shape)
print("Test :", X_test.shape)

print()
print("Timeline split:")
print(f"0%   → {train_end/n:.0%}  TRAIN")
print(f"{train_end/n:.0%} → {val_end/n:.0%}  VALIDATION")
print(f"{val_end/n:.0%} → 100% TEST")

print("=" * 60)