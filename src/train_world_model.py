"""
train_world_model.py
====================
Trains the TemporalWorldModel on the fused temporal sequences and saves
the checkpoint to models/world_model.pt.

This script reproduces the original Colab training locally on CPU.
The architecture and hyper-parameters are identical to the trained model
whose results are documented in README.md.

Run
---
    python src/train_world_model.py

The script will:
  1. Load data/simulated/fused_train_val_test.npz
  2. Train for up to MAX_EPOCHS with early stopping
  3. Save the best checkpoint to models/world_model.pt

Training on CPU takes approximately 3-8 minutes for this dataset size.
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

warnings.filterwarnings("ignore")

_SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(_SRC))
from model import TemporalWorldModel

# ============================================================
# Paths
# ============================================================

ROOT       = _SRC.parent
DATA_FILE  = ROOT / "data" / "simulated" / "fused_train_val_test.npz"
MODEL_DIR  = ROOT / "models"
MODEL_FILE = MODEL_DIR / "world_model.pt"

MODEL_DIR.mkdir(exist_ok=True)

# ============================================================
# Hyper-parameters  (match the original Colab training)
# ============================================================

INPUT_FEATURES  = 44
SEQUENCE_LENGTH = 5
D_MODEL         = 64
NHEAD           = 4
NUM_LAYERS      = 2
DIM_FEEDFORWARD = 128
DROPOUT         = 0.1

BATCH_SIZE      = 64
LR              = 3e-4
MAX_EPOCHS      = 60
PATIENCE        = 8          # early stopping patience
SEED            = 42

# Loss weights
W_STATE   = 1.0
W_ATTACK  = 0.5
W_STAGE   = 0.5

# ============================================================
# Reproducibility
# ============================================================

torch.manual_seed(SEED)
np.random.seed(SEED)

DEVICE = torch.device("cpu")

# ============================================================
# Load data
# ============================================================

print("Loading data ...")
npz = np.load(DATA_FILE, allow_pickle=True)

X_train       = torch.tensor(npz["X_train"],       dtype=torch.float32)
X_val         = torch.tensor(npz["X_val"],         dtype=torch.float32)
y_state_train = torch.tensor(npz["y_state_train"], dtype=torch.float32)
y_state_val   = torch.tensor(npz["y_state_val"],   dtype=torch.float32)
y_attack_train= torch.tensor(npz["y_attack_train"],dtype=torch.float32)
y_attack_val  = torch.tensor(npz["y_attack_val"],  dtype=torch.float32)
y_stage_train = torch.tensor(npz["y_stage_train"], dtype=torch.long)
y_stage_val   = torch.tensor(npz["y_stage_val"],   dtype=torch.long)
stage_names   = [str(s) for s in npz["stage_names"]]

print(f"  X_train : {X_train.shape}")
print(f"  X_val   : {X_val.shape}")
print(f"  Stages  : {stage_names}")

train_ds = TensorDataset(X_train, y_state_train, y_attack_train, y_stage_train)
val_ds   = TensorDataset(X_val,   y_state_val,   y_attack_val,   y_stage_val)

train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,
                          drop_last=False)
val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False)

# ============================================================
# Model
# ============================================================

model = TemporalWorldModel(
    input_features  = INPUT_FEATURES,
    sequence_length = SEQUENCE_LENGTH,
    d_model         = D_MODEL,
    nhead           = NHEAD,
    num_layers      = NUM_LAYERS,
    dim_feedforward = DIM_FEEDFORWARD,
    dropout         = DROPOUT,
    num_stages      = len(stage_names),
).to(DEVICE)

n_params = sum(p.numel() for p in model.parameters())
print(f"\nModel: {n_params:,} trainable parameters")

optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
    optimizer, T_max=MAX_EPOCHS, eta_min=1e-5)

mse_loss = nn.MSELoss()
bce_loss = nn.BCEWithLogitsLoss()
ce_loss  = nn.CrossEntropyLoss()

# ============================================================
# Training loop
# ============================================================

best_val_loss  = float("inf")
patience_count = 0
t0             = time.time()

print(f"\nTraining for up to {MAX_EPOCHS} epochs (patience={PATIENCE}) ...")
print(f"{'Epoch':>6}  {'Train Loss':>11}  {'Val Loss':>10}  "
      f"{'Val Atk Acc':>11}  {'Val Stg Acc':>11}  {'Time':>6}")
print("-" * 70)

for epoch in range(1, MAX_EPOCHS + 1):
    # ── Train ──────────────────────────────────────────────────
    model.train()
    train_loss = 0.0
    for xb, ys, ya, yg in train_loader:
        xb, ys, ya, yg = xb.to(DEVICE), ys.to(DEVICE), ya.to(DEVICE), yg.to(DEVICE)
        optimizer.zero_grad()
        sp, al, sl = model(xb)
        loss = (W_STATE  * mse_loss(sp, ys)
              + W_ATTACK * bce_loss(al.squeeze(1), ya)
              + W_STAGE  * ce_loss(sl, yg))
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        train_loss += loss.item() * len(xb)
    train_loss /= len(train_ds)

    # ── Validate ───────────────────────────────────────────────
    model.eval()
    val_loss = 0.0
    correct_atk = correct_stg = 0
    with torch.no_grad():
        for xb, ys, ya, yg in val_loader:
            xb, ys, ya, yg = xb.to(DEVICE), ys.to(DEVICE), ya.to(DEVICE), yg.to(DEVICE)
            sp, al, sl = model(xb)
            loss = (W_STATE  * mse_loss(sp, ys)
                  + W_ATTACK * bce_loss(al.squeeze(1), ya)
                  + W_STAGE  * ce_loss(sl, yg))
            val_loss    += loss.item() * len(xb)
            correct_atk += ((torch.sigmoid(al.squeeze(1)) >= 0.5).long()
                            == ya.long()).sum().item()
            correct_stg += (sl.argmax(1) == yg).sum().item()
    val_loss    /= len(val_ds)
    atk_acc      = correct_atk / len(val_ds)
    stg_acc      = correct_stg / len(val_ds)

    scheduler.step()
    elapsed = time.time() - t0

    marker = ""
    if val_loss < best_val_loss:
        best_val_loss  = val_loss
        patience_count = 0
        # Save checkpoint
        torch.save({
            "model_state_dict": model.state_dict(),
            "input_features":   INPUT_FEATURES,
            "sequence_length":  SEQUENCE_LENGTH,
            "d_model":          D_MODEL,
            "nhead":            NHEAD,
            "num_layers":       NUM_LAYERS,
            "dim_feedforward":  DIM_FEEDFORWARD,
            "dropout":          DROPOUT,
            "stage_names":      stage_names,
        }, MODEL_FILE)
        marker = "  ← best"
    else:
        patience_count += 1

    print(f"{epoch:>6}  {train_loss:>11.4f}  {val_loss:>10.4f}  "
          f"{atk_acc:>11.4f}  {stg_acc:>11.4f}  {elapsed:>5.0f}s{marker}")

    if patience_count >= PATIENCE:
        print(f"\nEarly stopping at epoch {epoch} (patience={PATIENCE})")
        break

# ============================================================
# Final report
# ============================================================

print("\n" + "=" * 60)
print(f"  Training complete")
print(f"  Best validation loss : {best_val_loss:.4f}")
print(f"  Checkpoint saved     : {MODEL_FILE}")
print(f"  Total time           : {time.time() - t0:.0f}s")
print("=" * 60)
