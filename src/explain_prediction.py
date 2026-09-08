"""
explain_prediction.py
=====================
Feature-attribution explainability for the World Model.
SIH "AI World Models for Predictive Cyber Defence".

Method: Feature Ablation / Permutation Sensitivity
---------------------------------------------------
For a selected prediction:
1. Run the model on the original sequence -> baseline output.
2. For each of the 44 input features, replace that feature's values
   across ALL 5 time-steps with the training-set mean (i.e. 0 in
   standardised space) — a neutral value that removes the feature's
   information without introducing out-of-distribution noise.
3. Re-run the model on the ablated sequence.
4. Compute importance = |baseline_output - ablated_output|.
5. Rank features by descending importance.

IMPORTANT WORDING
-----------------
This method measures *prediction sensitivity* — how much the model's
output changes when a feature's information is removed.
It does NOT establish causal relationships between features and attacks.
Use wording such as "features with highest prediction sensitivity"
rather than "features that caused the attack".

Outputs
-------
results/feature_importance.csv   — feature, importance, rank

Run standalone
--------------
    python src/explain_prediction.py
    python src/explain_prediction.py --sample 100 --target stage
    python src/explain_prediction.py --sample 50  --target attack
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import torch

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import load_model, autoregressive_rollout
from mitre_mapping import format_mitre

# ============================================================
# Paths
# ============================================================

ROOT        = Path(__file__).resolve().parent.parent
DATA_FILE   = ROOT / "data" / "simulated" / "fused_train_val_test.npz"
MODEL_FILE  = ROOT / "models" / "world_model.pt"
RESULTS     = ROOT / "results"
RESULTS.mkdir(exist_ok=True)
IMPORTANCE_FILE = RESULTS / "feature_importance.csv"

DEVICE = torch.device("cpu")

# ============================================================
# Core explainability function
# ============================================================

def explain_prediction(
    model:        "TemporalWorldModel",   # noqa: F821
    sequence:     np.ndarray,
    feature_cols: list[str],
    stage_names:  list[str],
    target:       str = "stage",
    ablation_val: float = 0.0,
) -> pd.DataFrame:
    """
    Feature ablation sensitivity analysis.

    Parameters
    ----------
    model        : trained TemporalWorldModel in eval mode
    sequence     : (seq_len, n_features) standardised input — NOT modified
    feature_cols : list of feature names (length n_features)
    stage_names  : list of stage names
    target       : "stage" or "attack"
    ablation_val : value to substitute (0.0 = standardised mean)

    Returns
    -------
    DataFrame with columns: feature, importance, rank
    Sorted descending by importance.
    """
    model.eval()
    n_features = sequence.shape[1]
    seq_t      = sequence.copy().astype(np.float32)

    def _run(seq: np.ndarray) -> float:
        x = torch.tensor(seq, dtype=torch.float32, device=DEVICE).unsqueeze(0)
        with torch.no_grad():
            state_pred, attack_logit, stage_logits = model(x)
        if target == "attack":
            return float(torch.sigmoid(attack_logit).item())
        else:
            probs    = torch.softmax(stage_logits, dim=-1).squeeze(0).cpu().numpy()
            stage_id = int(np.argmax(probs))
            return float(probs[stage_id])

    baseline = _run(seq_t)

    importances = []
    for feat_idx in range(n_features):
        ablated = seq_t.copy()
        ablated[:, feat_idx] = ablation_val        # zero across all timesteps
        ablated_score = _run(ablated)
        importances.append(abs(baseline - ablated_score))

    df = pd.DataFrame({
        "feature":    feature_cols,
        "importance": importances,
    })
    df = df.sort_values("importance", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    return df


# ============================================================
# CLI & main
# ============================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Feature-attribution explainability for World Model"
    )
    p.add_argument("--sample", type=int, default=-1,
                   help="Index into X_test (default: -1)")
    p.add_argument("--target", choices=["stage", "attack"], default="stage",
                   help="Prediction target to explain (default: stage)")
    p.add_argument("--top", type=int, default=10,
                   help="Number of top features to print (default: 10)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    sep  = "=" * 60

    # ── Load data ──────────────────────────────────────────────
    npz          = np.load(DATA_FILE, allow_pickle=True)
    X_test       = npz["X_test"]
    y_stage_test = npz["y_stage_test"]
    feature_cols = [str(c) for c in npz["feature_columns"]]
    stage_names  = [str(s) for s in npz["stage_names"]]

    resolved = args.sample if args.sample >= 0 else len(X_test) + args.sample
    sequence = X_test[resolved]                            # (5, 44)
    current_stage = stage_names[int(y_stage_test[resolved])]

    # ── Load model ─────────────────────────────────────────────
    model, _ = load_model(MODEL_FILE, DEVICE, num_stages=len(stage_names))

    # ── Get baseline prediction ────────────────────────────────
    x = torch.tensor(sequence.astype(np.float32),
                     dtype=torch.float32, device=DEVICE).unsqueeze(0)
    with torch.no_grad():
        _, attack_logit, stage_logits = model(x)

    atk_prob    = float(torch.sigmoid(attack_logit).item())
    stage_probs = torch.softmax(stage_logits, dim=-1).squeeze(0).cpu().numpy()
    pred_stage  = stage_names[int(np.argmax(stage_probs))]
    pred_conf   = float(stage_probs[np.argmax(stage_probs)])

    print(f"\n{sep}")
    print("  WORLD MODEL — FEATURE SENSITIVITY ANALYSIS")
    print(sep)
    print(f"  Sample index    : {resolved}")
    print(f"  Target          : {args.target}")
    print(f"  Current stage   : {current_stage}")
    print(f"  Predicted stage : {pred_stage}  (conf={pred_conf:.4f})")
    print(f"  Attack prob     : {atk_prob:.4f}")
    print(f"  MITRE ATT&CK    : {format_mitre(pred_stage)}")
    print(sep)

    # ── Compute feature importance ─────────────────────────────
    importance_df = explain_prediction(
        model        = model,
        sequence     = sequence,
        feature_cols = feature_cols,
        stage_names  = stage_names,
        target       = args.target,
    )

    top_n = args.top
    print(f"\nTop {top_n} features with highest prediction sensitivity")
    print(f"(target: {args.target})")
    print(f"Method: Feature ablation — replace feature with standardised")
    print(f"        mean (0.0) across all 5 time-steps; measure |Δoutput|.")
    print(f"NOTE:   Sensitivity ≠ causation.\n")

    header = f"{'Rank':<6} {'Feature':<30} {'Sensitivity':>12}"
    print(header)
    print("-" * len(header))
    for _, row in importance_df.head(top_n).iterrows():
        print(f"{int(row['rank']):<6} {row['feature']:<30} {row['importance']:>12.6f}")

    # ── Save ───────────────────────────────────────────────────
    importance_df.to_csv(IMPORTANCE_FILE, index=False)
    print(f"\nFull importance table saved -> {IMPORTANCE_FILE}")
    print(sep)


if __name__ == "__main__":
    main()
