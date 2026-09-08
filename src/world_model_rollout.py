"""
world_model_rollout.py
======================
Multi-step autoregressive World Model rollout for
SIH "AI World Models for Predictive Cyber Defence".

Loads the trained TemporalWorldModel from models/world_model.pt,
seeds the rollout with the last sequence in X_test (or a selected
sample), then predicts 5 future network states entirely from its
own previous outputs — no ground-truth future states are used.

Outputs
-------
data/simulated/forecast_trajectory.csv  — per-step attack/stage forecast
data/simulated/forecast_states.csv      — per-step predicted feature vectors
                                          (inverse-transformed to original scale)

Run
---
    python src/world_model_rollout.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import torch

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import load_model, autoregressive_rollout, inverse_transform
from mitre_mapping import get_mitre_mapping, format_mitre

# ============================================================
# Paths
# ============================================================

ROOT       = Path(__file__).resolve().parent.parent
DATA_FILE  = ROOT / "data" / "simulated" / "fused_train_val_test.npz"
MODEL_FILE = ROOT / "models" / "world_model.pt"
TRAJ_FILE  = ROOT / "data" / "simulated" / "forecast_trajectory.csv"
STATE_FILE = ROOT / "data" / "simulated" / "forecast_states.csv"

# ============================================================
# Config
# ============================================================

DEVICE        = torch.device("cpu")
ROLLOUT_STEPS = 5


# ============================================================
# Main
# ============================================================

def main() -> None:
    sep = "=" * 60

    # ── 1. Load data ───────────────────────────────────────────
    print(f"\n{sep}")
    print("  LOADING DATA")
    print(sep)

    assert DATA_FILE.exists(), f"NPZ not found: {DATA_FILE}"
    npz = np.load(DATA_FILE, allow_pickle=True)

    assert "scaler_mean"  in npz.files, "scaler_mean missing from NPZ"
    assert "scaler_scale" in npz.files, "scaler_scale missing from NPZ"

    X_test       = npz["X_test"]
    scaler_mean  = npz["scaler_mean"]
    scaler_scale = npz["scaler_scale"]
    feature_cols = [str(c) for c in npz["feature_columns"]]
    stage_names  = [str(s) for s in npz["stage_names"]]

    print(f"X_test shape       : {X_test.shape}")
    print(f"scaler_mean shape  : {scaler_mean.shape}")
    print(f"scaler_scale shape : {scaler_scale.shape}")
    print(f"Feature columns    : {len(feature_cols)}")
    print(f"Stage names        : {stage_names}")

    initial_sequence = X_test[-1]
    assert initial_sequence.shape == (5, 44), \
        f"Unexpected shape: {initial_sequence.shape}"
    print(f"\nInitial sequence shape : {initial_sequence.shape}  [OK]")

    # ── 2. Load model ──────────────────────────────────────────
    print(f"\n{sep}")
    print("  LOADING MODEL")
    print(sep)

    assert MODEL_FILE.exists(), f"Checkpoint not found: {MODEL_FILE}"
    model, ckpt = load_model(MODEL_FILE, DEVICE, num_stages=len(stage_names))
    n_params = sum(p.numel() for p in model.parameters())

    print(f"Architecture loaded from checkpoint metadata")
    print(f"  input_features  : {ckpt['input_features']}")
    print(f"  sequence_length : {ckpt['sequence_length']}")
    print(f"  d_model         : {ckpt['d_model']}")
    print(f"  nhead           : {ckpt['nhead']}")
    print(f"  num_layers      : {ckpt['num_layers']}")
    print(f"  dim_feedforward : {ckpt['dim_feedforward']}")
    print(f"  dropout         : {ckpt['dropout']}")
    print(f"  Total parameters: {n_params:,}")
    print(f"  Device          : {DEVICE}")
    print(f"  Model state     : eval()")

    # ── 3. Rollout ─────────────────────────────────────────────
    print(f"\n{sep}")
    print("  MULTI-STEP WORLD MODEL FORECAST")
    print(sep)
    print(f"Initial sequence shape : {initial_sequence.shape}")
    print(f"Device                 : {DEVICE}")
    print(f"Rollout steps          : {ROLLOUT_STEPS}")
    print(f"Ground truth used      : NO (fully autoregressive)")
    print(sep)

    trajectory = autoregressive_rollout(
        model            = model,
        initial_sequence = initial_sequence,
        steps            = ROLLOUT_STEPS,
        stage_names      = stage_names,
        device           = DEVICE,
    )

    assert len(trajectory) == ROLLOUT_STEPS

    # ── 4. Print trajectory ────────────────────────────────────
    for entry in trajectory:
        print(f"\nStep +{entry['step']}")
        print(f"  Stage             : {entry['stage_name']}")
        print(f"  Attack Probability: {entry['attack_prob']:.4f}")
        print(f"  Stage Confidence  : {entry['stage_confidence']:.4f}")
        print(f"  MITRE ATT&CK      : {format_mitre(entry['stage_name'])}")

    print(f"\n{sep}")

    # ── 5. Inverse-transform states ────────────────────────────
    scaled_arr = np.array([e["predicted_state_scaled"] for e in trajectory])
    orig_arr   = inverse_transform(scaled_arr, scaler_mean, scaler_scale)

    # ── 6. Save forecast_trajectory.csv ───────────────────────
    traj_rows = []
    for entry in trajectory:
        m = get_mitre_mapping(entry["stage_name"])
        traj_rows.append({
            "step":               entry["step"],
            "attack_probability": round(entry["attack_prob"], 6),
            "stage":              entry["stage_name"],
            "stage_confidence":   round(entry["stage_confidence"], 6),
            "mitre_attack_id":    m["mitre_attack_id"] or "None",
            "mitre_attack_name":  m["mitre_attack_name"] or "None",
        })
    traj_df = pd.DataFrame(traj_rows)
    traj_df.to_csv(TRAJ_FILE, index=False)
    print(f"Saved trajectory  -> {TRAJ_FILE}")

    # ── 7. Save forecast_states.csv ───────────────────────────
    state_rows = []
    for i, entry in enumerate(trajectory):
        row = {"step": entry["step"]}
        for j, col in enumerate(feature_cols):
            row[col] = round(float(orig_arr[i, j]), 6)
        state_rows.append(row)
    state_df = pd.DataFrame(state_rows)
    state_df.to_csv(STATE_FILE, index=False)
    print(f"Saved states      -> {STATE_FILE}")

    # ── 8. Verify ──────────────────────────────────────────────
    print(f"\n{sep}")
    print("  VERIFICATION")
    print(sep)

    tl = pd.read_csv(TRAJ_FILE)
    sl = pd.read_csv(STATE_FILE)

    assert list(tl.columns) == ["step", "attack_probability", "stage",
                                  "stage_confidence", "mitre_attack_id",
                                  "mitre_attack_name"]
    assert list(sl.columns) == ["step"] + feature_cols
    assert len(tl) == ROLLOUT_STEPS
    assert len(sl) == ROLLOUT_STEPS

    print(f"forecast_trajectory.csv : {len(tl)} rows, {len(tl.columns)} cols  [OK]")
    print(f"forecast_states.csv     : {len(sl)} rows, {len(sl.columns)} cols  [OK]")
    print(f"Rollout steps           : {len(trajectory)}  [OK]")
    print(f"Device                  : {DEVICE}  [OK]")
    print(f"Ground truth used       : NO  [OK]")

    print(f"\n{sep}")
    print("  FORECAST TRAJECTORY SUMMARY")
    print(sep)
    print(traj_df.to_string(index=False))

    print(f"\n{sep}")
    print("  ROLLOUT COMPLETE")
    print(sep)


if __name__ == "__main__":
    main()
