import numpy as np
from pathlib import Path
from sklearn.preprocessing import StandardScaler


# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(r"D:\Network_Attak_Forecasting")

INPUT_FILE = (
    BASE_DIR
    / "data"
    / "simulated"
    / "fused_sequences.npz"
)

OUTPUT_FILE = (
    BASE_DIR
    / "data"
    / "simulated"
    / "fused_train_val_test.npz"
)


# ============================================================
# Configuration
# ============================================================

TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15


# ============================================================
# Load sequences
# ============================================================

print("Loading sequences...")

data = np.load(
    INPUT_FILE,
    allow_pickle=True
)

X = data["X"]
y_state = data["y_state"]
y_attack = data["y_attack"]
y_stage = data["y_stage"]

feature_columns = data["feature_columns"]
stage_names = data["stage_names"]

print("X:", X.shape)
print("y_state:", y_state.shape)
print("y_attack:", y_attack.shape)
print("y_stage:", y_stage.shape)


# ============================================================
# Chronological split
# ============================================================

n = len(X)

train_end = int(n * TRAIN_RATIO)
val_end = train_end + int(n * VAL_RATIO)

print("\nSplit indices:")
print("Train:", 0, "->", train_end)
print("Validation:", train_end, "->", val_end)
print("Test:", val_end, "->", n)


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


# ============================================================
# Feature scaling
# ============================================================

print("\nFitting StandardScaler on TRAIN only...")

num_features = X_train.shape[-1]

scaler = StandardScaler()

# Flatten train sequences:
# (samples, timesteps, features)
# ->
# (samples * timesteps, features)

X_train_flat = X_train.reshape(
    -1,
    num_features
)

scaler.fit(X_train_flat)


# ============================================================
# Apply scaler
# ============================================================

def scale_sequences(X, scaler):
    original_shape = X.shape

    X_flat = X.reshape(
        -1,
        original_shape[-1]
    )

    X_scaled = scaler.transform(X_flat)

    return X_scaled.reshape(
        original_shape
    ).astype(np.float32)


X_train_scaled = scale_sequences(
    X_train,
    scaler
)

X_val_scaled = scale_sequences(
    X_val,
    scaler
)

X_test_scaled = scale_sequences(
    X_test,
    scaler
)


# ============================================================
# Scale next-state targets using same scaler
# ============================================================

y_state_train_scaled = scaler.transform(
    y_state_train
).astype(np.float32)

y_state_val_scaled = scaler.transform(
    y_state_val
).astype(np.float32)

y_state_test_scaled = scaler.transform(
    y_state_test
).astype(np.float32)


# ============================================================
# Save
# ============================================================

np.savez_compressed(
    OUTPUT_FILE,

    X_train=X_train_scaled,
    X_val=X_val_scaled,
    X_test=X_test_scaled,

    y_state_train=y_state_train_scaled,
    y_state_val=y_state_val_scaled,
    y_state_test=y_state_test_scaled,

    y_attack_train=y_attack_train,
    y_attack_val=y_attack_val,
    y_attack_test=y_attack_test,

    y_stage_train=y_stage_train,
    y_stage_val=y_stage_val,
    y_stage_test=y_stage_test,

    feature_columns=feature_columns,
    stage_names=stage_names,

    # Scaler parameters — fitted on TRAIN only.
    # Used for inverse-transforming World Model rollout predictions
    # back to the original feature scale.
    scaler_mean=scaler.mean_.astype(np.float32),
    scaler_scale=scaler.scale_.astype(np.float32),
)


# ============================================================
# Report
# ============================================================

print("\n========================================")
print("CHRONOLOGICAL SPLIT COMPLETE")
print("========================================")

print("\nTrain:")
print("X:", X_train_scaled.shape)
print("State target:", y_state_train_scaled.shape)

print("\nValidation:")
print("X:", X_val_scaled.shape)
print("State target:", y_state_val_scaled.shape)

print("\nTest:")
print("X:", X_test_scaled.shape)
print("State target:", y_state_test_scaled.shape)


print("\nAttack distribution:")

print("\nTRAIN")
print(
    dict(
        zip(
            *np.unique(
                y_attack_train,
                return_counts=True
            )
        )
    )
)

print("\nVALIDATION")
print(
    dict(
        zip(
            *np.unique(
                y_attack_val,
                return_counts=True
            )
        )
    )
)

print("\nTEST")
print(
    dict(
        zip(
            *np.unique(
                y_attack_test,
                return_counts=True
            )
        )
    )
)


print("\nStage distribution:")

for name, y in [
    ("TRAIN", y_stage_train),
    ("VALIDATION", y_stage_val),
    ("TEST", y_stage_test)
]:

    unique, counts = np.unique(
        y,
        return_counts=True
    )

    print(f"\n{name}")

    for stage_id, count in zip(
        unique,
        counts
    ):
        print(
            f"{stage_names[stage_id]:20s}: {count}"
        )


print("\nSaved:")
print(OUTPUT_FILE)

# ============================================================
# Verify scaler parameters in saved file
# ============================================================

print("\n========================================")
print("SCALER PARAMETER VERIFICATION")
print("========================================")

saved = np.load(OUTPUT_FILE, allow_pickle=True)

print("\nAll keys in NPZ:")
for key in sorted(saved.files):
    arr = saved[key]
    print(f"  {key:<22} shape={arr.shape}  dtype={arr.dtype}")

print(f"\nscaler_mean  shape: {saved['scaler_mean'].shape}")
print(f"scaler_scale shape: {saved['scaler_scale'].shape}")

print("\nFirst 5 scaler_mean values:")
print(saved["scaler_mean"][:5])

print("\nFirst 5 scaler_scale values:")
print(saved["scaler_scale"][:5])