"""
evaluate_rollout.py
===================
Multi-step autoregressive rollout evaluation for
SIH "AI World Models for Predictive Cyber Defence".

For each of up to 100 representative test sequences (selected with
seed=42, distributed across true target stages) a full 5-step
autoregressive rollout is performed.  At every horizon (+1 … +5)
the predicted attack label and attack stage are compared against
the ground-truth values from the test set.

AUTOREGRESSIVE GUARANTEE
-------------------------
After the first prediction (horizon +1), the model's own predicted
state is fed back as input for +2, +3, +4, +5.
Ground-truth future states X_test[i+1], X_test[i+2], … are NEVER
used as model inputs.  They are only used for metric computation
AFTER all predictions are complete.

Outputs
-------
results/rollout_metrics.csv           — per-horizon aggregate metrics
results/rollout_predictions.csv       — per-sample per-horizon predictions
results/predicted_stage_transitions.csv
results/representative_trajectories.csv

Run
---
    python src/evaluate_rollout.py
"""

from __future__ import annotations

import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

import torch

from sklearn.metrics import (
    accuracy_score, precision_score,
    recall_score, f1_score,
)

# ── local imports ──────────────────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from model import load_model, autoregressive_rollout, inverse_transform
from mitre_mapping import get_mitre_mapping, format_mitre

warnings.filterwarnings("ignore")

# ============================================================
# Paths
# ============================================================

ROOT       = Path(__file__).resolve().parent.parent
DATA_FILE  = ROOT / "data" / "simulated" / "fused_train_val_test.npz"
MODEL_FILE = ROOT / "models" / "world_model.pt"
RESULTS    = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

METRICS_FILE      = RESULTS / "rollout_metrics.csv"
PREDS_FILE        = RESULTS / "rollout_predictions.csv"
TRANSITIONS_FILE  = RESULTS / "predicted_stage_transitions.csv"
REPR_TRAJ_FILE    = RESULTS / "representative_trajectories.csv"

# ============================================================
# Config
# ============================================================

DEVICE        = torch.device("cpu")
ROLLOUT_STEPS = 5
MAX_SAMPLES   = 100
SEED          = 42

# ============================================================
# Load data
# ============================================================

print("=" * 60)
print("  LOADING DATA")
print("=" * 60)

npz          = np.load(DATA_FILE, allow_pickle=True)
X_test       = npz["X_test"]           # (654, 5, 44)
y_attack_test= npz["y_attack_test"]    # (654,)
y_stage_test = npz["y_stage_test"]     # (654,)
scaler_mean  = npz["scaler_mean"]      # (44,)
scaler_scale = npz["scaler_scale"]     # (44,)
feature_cols = [str(c) for c in npz["feature_columns"]]
stage_names  = [str(s) for s in npz["stage_names"]]

n_test = len(X_test)
print(f"X_test         : {X_test.shape}")
print(f"y_attack_test  : {y_attack_test.shape}")
print(f"y_stage_test   : {y_stage_test.shape}")
print(f"Stage names    : {stage_names}")
print(f"Test samples   : {n_test}")

# ============================================================
# Load model
# ============================================================

print("\n" + "=" * 60)
print("  LOADING MODEL")
print("=" * 60)

model, ckpt = load_model(MODEL_FILE, DEVICE, num_stages=len(stage_names))
n_params = sum(p.numel() for p in model.parameters())
print(f"Loaded  : {MODEL_FILE.name}")
print(f"Params  : {n_params:,}")
print(f"Device  : {DEVICE}")

# ============================================================
# Select up to MAX_SAMPLES test sequences
# Distributed across true target stages so every stage is
# represented where possible.  Selection is deterministic.
# ============================================================

print("\n" + "=" * 60)
print("  SELECTING TEST SEQUENCES")
print("=" * 60)

rng = np.random.default_rng(SEED)

# For horizon +k we need X_test[i] as seed and y_*[i+k] as truth.
# The maximum valid seed index is therefore n_test - ROLLOUT_STEPS - 1.
max_seed_idx = n_test - ROLLOUT_STEPS - 1

# Group available indices by their true stage at the SEED position
# (y_stage_test[i] is the true stage the model should predict at +1)
stage_buckets: dict[int, list[int]] = defaultdict(list)
for i in range(max_seed_idx + 1):
    stage_buckets[int(y_stage_test[i])].append(i)

n_stages = len(stage_names)
per_stage = max(1, MAX_SAMPLES // n_stages)

selected: list[int] = []
for sid in range(n_stages):
    bucket = stage_buckets[sid]
    if not bucket:
        print(f"  WARNING: no test samples with true stage '{stage_names[sid]}'")
        continue
    chosen = rng.choice(
        bucket,
        size=min(per_stage, len(bucket)),
        replace=False,
    )
    selected.extend(chosen.tolist())

# Trim and sort
selected = sorted(set(selected))[:MAX_SAMPLES]

print(f"Samples selected : {len(selected)}")
for sid in range(n_stages):
    cnt = sum(1 for i in selected if int(y_stage_test[i]) == sid)
    print(f"  {stage_names[sid]:<22} : {cnt}")

# ============================================================
# Main evaluation loop
# ============================================================

print("\n" + "=" * 60)
print("  RUNNING AUTOREGRESSIVE ROLLOUT EVALUATION")
print("=" * 60)
print("Ground-truth future states are NOT used as model inputs.")

all_preds: list[dict] = []

for sample_idx in selected:
    initial_seq = X_test[sample_idx]                       # (5, 44)

    trajectory = autoregressive_rollout(
        model            = model,
        initial_sequence = initial_seq,
        steps            = ROLLOUT_STEPS,
        stage_names      = stage_names,
        device           = DEVICE,
    )

    for entry in trajectory:
        h = entry["step"]                                  # 1 … 5
        truth_idx = sample_idx + h

        if truth_idx >= n_test:
            continue                                        # edge case guard

        all_preds.append({
            "sample_index":       sample_idx,
            "horizon":            h,
            "true_attack":        int(y_attack_test[truth_idx]),
            "predicted_attack":   int(entry["attack_prob"] >= 0.5),
            "attack_probability": round(entry["attack_prob"], 6),
            "true_stage":         int(y_stage_test[truth_idx]),
            "predicted_stage":    entry["stage_id"],
            "stage_confidence":   round(entry["stage_confidence"], 6),
        })

preds_df = pd.DataFrame(all_preds)
print(f"Total predictions recorded : {len(preds_df)}")

# ============================================================
# Per-horizon metrics
# ============================================================

print("\n" + "=" * 60)
print("  PER-HORIZON METRICS")
print("=" * 60)

metric_rows: list[dict] = []

header = (f"{'Horizon':<8} {'Atk Acc':>8} {'Atk Prec':>9} "
          f"{'Atk Rec':>8} {'Atk F1':>7} {'Stg Acc':>8} {'Stg MF1':>8}")
print(header)
print("-" * len(header))

for h in range(1, ROLLOUT_STEPS + 1):
    sub = preds_df[preds_df["horizon"] == h]
    if len(sub) == 0:
        continue

    ta  = sub["true_attack"].values
    pa  = sub["predicted_attack"].values
    ts  = sub["true_stage"].values
    ps  = sub["predicted_stage"].values

    atk_acc  = accuracy_score(ta, pa)
    atk_prec = precision_score(ta, pa, zero_division=0)
    atk_rec  = recall_score(ta, pa, zero_division=0)
    atk_f1   = f1_score(ta, pa, zero_division=0)
    stg_acc  = accuracy_score(ts, ps)
    stg_mf1  = f1_score(ts, ps, average="macro", zero_division=0,
                         labels=list(range(len(stage_names))))

    print(f"+{h:<7} {atk_acc:>8.4f} {atk_prec:>9.4f} "
          f"{atk_rec:>8.4f} {atk_f1:>7.4f} {stg_acc:>8.4f} {stg_mf1:>8.4f}")

    metric_rows.append({
        "horizon":          h,
        "attack_accuracy":  round(atk_acc,  4),
        "attack_precision": round(atk_prec, 4),
        "attack_recall":    round(atk_rec,  4),
        "attack_f1":        round(atk_f1,   4),
        "stage_accuracy":   round(stg_acc,  4),
        "stage_macro_f1":   round(stg_mf1,  4),
    })

metrics_df = pd.DataFrame(metric_rows)

# ============================================================
# Save rollout_metrics.csv
# ============================================================

metrics_df.to_csv(METRICS_FILE, index=False)
print(f"\nSaved -> {METRICS_FILE}")

# ============================================================
# Save rollout_predictions.csv
# ============================================================

preds_df.to_csv(PREDS_FILE, index=False)
print(f"Saved -> {PREDS_FILE}")

# ============================================================
# Stage transition analysis
# ============================================================

print("\n" + "=" * 60)
print("  STAGE TRANSITION ANALYSIS")
print("=" * 60)

trans_counts: dict[tuple[int, int], int] = defaultdict(int)

for sample_idx in selected:
    sub = preds_df[preds_df["sample_index"] == sample_idx].sort_values("horizon")
    if len(sub) < 2:
        continue
    stages = sub["predicted_stage"].tolist()
    for a, b in zip(stages[:-1], stages[1:]):
        trans_counts[(a, b)] += 1

trans_rows = []
for (from_id, to_id), cnt in sorted(trans_counts.items(), key=lambda x: -x[1]):
    trans_rows.append({
        "from_stage": stage_names[from_id],
        "to_stage":   stage_names[to_id],
        "count":      cnt,
    })

trans_df = pd.DataFrame(trans_rows) if trans_rows else pd.DataFrame(
    columns=["from_stage", "to_stage", "count"])
trans_df.to_csv(TRANSITIONS_FILE, index=False)

print("Top transitions:")
print(trans_df.head(10).to_string(index=False))
print(f"\nSaved -> {TRANSITIONS_FILE}")

# ============================================================
# Representative trajectories — one seed per true stage
# ============================================================

print("\n" + "=" * 60)
print("  REPRESENTATIVE TRAJECTORIES")
print("=" * 60)

repr_rows: list[dict] = []

for sid, sname in enumerate(stage_names):
    bucket = stage_buckets[sid]
    if not bucket:
        print(f"  [{sname}] No test sample available — skipping.")
        continue

    # Pick the first available index deterministically
    start_idx = sorted(bucket)[0]
    init_seq  = X_test[start_idx]
    true_stage_name = stage_names[int(y_stage_test[start_idx])]

    traj = autoregressive_rollout(
        model            = model,
        initial_sequence = init_seq,
        steps            = ROLLOUT_STEPS,
        stage_names      = stage_names,
        device           = DEVICE,
    )

    print(f"\n  Initial stage: {true_stage_name}  (sample {start_idx})")
    for entry in traj:
        m = get_mitre_mapping(entry["stage_name"])
        print(f"    +{entry['step']}  {entry['stage_name']:<22} "
              f"atk={entry['attack_prob']:.4f}  "
              f"conf={entry['stage_confidence']:.4f}  "
              f"MITRE={format_mitre(entry['stage_name'])}")
        repr_rows.append({
            "start_sample":      start_idx,
            "initial_stage":     true_stage_name,
            "horizon":           entry["step"],
            "predicted_stage":   entry["stage_name"],
            "attack_probability":round(entry["attack_prob"], 6),
            "stage_confidence":  round(entry["stage_confidence"], 6),
            "mitre_attack_id":   m["mitre_attack_id"] or "None",
            "mitre_attack_name": m["mitre_attack_name"] or "None",
        })

repr_df = pd.DataFrame(repr_rows)
repr_df.to_csv(REPR_TRAJ_FILE, index=False)
print(f"\nSaved -> {REPR_TRAJ_FILE}")

# ============================================================
# Final summary
# ============================================================

print("\n" + "=" * 60)
print("  EVALUATION COMPLETE")
print("=" * 60)
print(f"Samples evaluated        : {len(selected)}")
print(f"Rollout horizons         : {ROLLOUT_STEPS}")
print(f"Predictions recorded     : {len(preds_df)}")
print(f"\nHorizon metrics summary:")
print(metrics_df.to_string(index=False))
print(f"\nOutput files:")
print(f"  {METRICS_FILE}")
print(f"  {PREDS_FILE}")
print(f"  {TRANSITIONS_FILE}")
print(f"  {REPR_TRAJ_FILE}")
