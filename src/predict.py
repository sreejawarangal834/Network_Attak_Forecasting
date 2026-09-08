"""
predict.py
==========
Clean inference entry point for
SIH "AI World Models for Predictive Cyber Defence".

Loads the trained World Model and runs a 5-step autoregressive rollout
from a selected test sequence.  No ground-truth future states are used.

Usage
-----
    python src/predict.py               # uses X_test[-1]
    python src/predict.py --sample 100  # uses X_test[100]
    python src/predict.py --sample -5   # uses X_test[-5]

Output
------
Prints the forecasted trajectory to stdout.
Does NOT overwrite any model or dataset files.
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
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

# ============================================================
# Reproducibility
# ============================================================

import random
random.seed(42)
np.random.seed(42)
torch.manual_seed(42)

DEVICE        = torch.device("cpu")
ROLLOUT_STEPS = 5

# ============================================================
# CLI
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="World Model 5-step autoregressive forecast (CPU)"
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Index into X_test (supports negative indexing). "
             "Default: X_test[-1]",
    )
    return parser.parse_args()


# ============================================================
# Main
# ============================================================

def main() -> None:
    args   = parse_args()
    sep    = "=" * 60

    # ── Load data ──────────────────────────────────────────────
    assert DATA_FILE.exists(), f"NPZ not found: {DATA_FILE}"
    npz          = np.load(DATA_FILE, allow_pickle=True)
    X_test       = npz["X_test"]
    y_stage_test = npz["y_stage_test"]
    scaler_mean  = npz["scaler_mean"]
    scaler_scale = npz["scaler_scale"]
    feature_cols = [str(c) for c in npz["feature_columns"]]
    stage_names  = [str(s) for s in npz["stage_names"]]

    # ── Select sample ──────────────────────────────────────────
    sample_idx = args.sample if args.sample is not None else -1

    # Resolve negative index
    resolved = sample_idx if sample_idx >= 0 else len(X_test) + sample_idx
    if not (0 <= resolved < len(X_test)):
        print(f"ERROR: sample index {sample_idx} out of range "
              f"[0, {len(X_test)-1}]", file=sys.stderr)
        sys.exit(1)

    initial_sequence = X_test[resolved]                    # (5, 44)
    assert initial_sequence.shape == (5, 44)

    current_stage = stage_names[int(y_stage_test[resolved])]

    # ── Load model ─────────────────────────────────────────────
    assert MODEL_FILE.exists(), f"Checkpoint not found: {MODEL_FILE}"
    model, _ = load_model(MODEL_FILE, DEVICE, num_stages=len(stage_names))

    # ── Run rollout ────────────────────────────────────────────
    trajectory = autoregressive_rollout(
        model            = model,
        initial_sequence = initial_sequence,
        steps            = ROLLOUT_STEPS,
        stage_names      = stage_names,
        device           = DEVICE,
    )

    # ── Inverse-transform predicted states ─────────────────────
    scaled_states = np.array(
        [e["predicted_state_scaled"] for e in trajectory]
    )
    orig_states = inverse_transform(scaled_states, scaler_mean, scaler_scale)

    # ── Print report ───────────────────────────────────────────
    print(f"\n{sep}")
    print("  WORLD MODEL — 5-STEP AUTOREGRESSIVE FORECAST")
    print(sep)
    print(f"  Device               : {DEVICE}")
    print(f"  Sample index         : {resolved}  (X_test[{sample_idx}])")
    print(f"  Initial sequence     : {initial_sequence.shape}")
    print(f"  Current true stage   : {current_stage}")
    print(f"  Ground truth used    : NO (fully autoregressive)")
    print(sep)

    for entry in trajectory:
        h          = entry["step"]
        stage      = entry["stage_name"]
        atk_prob   = entry["attack_prob"]
        confidence = entry["stage_confidence"]
        mitre_str  = format_mitre(stage)

        print(f"\nStep +{h}")
        print(f"  Predicted stage      : {stage}")
        print(f"  Attack probability   : {atk_prob:.4f}  "
              f"({'ATTACK' if atk_prob >= 0.5 else 'BENIGN'})")
        print(f"  Stage confidence     : {confidence:.4f}")
        print(f"  MITRE ATT&CK         : {mitre_str}")

    print(f"\n{sep}")
    print("  NOTE: Predicted attack stage mapped to a representative")
    print("  MITRE ATT&CK technique. The model does not directly detect")
    print("  specific ATT&CK techniques from raw telemetry.")
    print(sep)


if __name__ == "__main__":
    main()
