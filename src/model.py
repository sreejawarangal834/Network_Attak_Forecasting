"""
model.py
========
Shared TemporalWorldModel definition and loader.
Imported by world_model_rollout.py, evaluate_rollout.py, and predict.py
so the architecture is defined exactly once.
"""

from __future__ import annotations

import torch
import torch.nn as nn
from pathlib import Path


# ============================================================
# Architecture
# ============================================================

class TemporalWorldModel(nn.Module):
    """
    Transformer-based world model for network-state forecasting.

    Architecture (matches trained checkpoint in models/world_model.pt):
        input_projection : Linear(input_features -> d_model)
        pos_embedding    : learnable Parameter (1, seq_len, d_model)
        transformer      : TransformerEncoder
                             2 x TransformerEncoderLayer
                             d_model=64, nhead=4, dim_feedforward=128
                             dropout=0.1, activation="gelu"
                             batch_first=True, norm_first=True
        norm             : LayerNorm(d_model)
        state_head       : Linear(64->64) -> GELU -> Linear(64->44)
        attack_head      : Linear(64->32) -> GELU -> Linear(32->1)
        stage_head       : Linear(64->32) -> GELU -> Linear(32->5)
    """

    def __init__(
        self,
        input_features:  int   = 44,
        sequence_length: int   = 5,
        d_model:         int   = 64,
        nhead:           int   = 4,
        num_layers:      int   = 2,
        dim_feedforward: int   = 128,
        dropout:         float = 0.1,
        num_stages:      int   = 5,
    ) -> None:
        super().__init__()

        self.input_projection = nn.Linear(input_features, d_model)

        self.pos_embedding = nn.Parameter(
            torch.zeros(1, sequence_length, d_model)
        )

        encoder_layer = nn.TransformerEncoderLayer(
            d_model         = d_model,
            nhead           = nhead,
            dim_feedforward = dim_feedforward,
            dropout         = dropout,
            activation      = "gelu",
            batch_first     = True,
            norm_first      = True,
        )
        self.transformer = nn.TransformerEncoder(
            encoder_layer,
            num_layers = num_layers,
        )

        self.norm = nn.LayerNorm(d_model)

        self.state_head = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.Linear(d_model, input_features),
        )
        self.attack_head = nn.Sequential(
            nn.Linear(d_model, 32),
            nn.GELU(),
            nn.Linear(32, 1),
        )
        self.stage_head = nn.Sequential(
            nn.Linear(d_model, 32),
            nn.GELU(),
            nn.Linear(32, num_stages),
        )

    def forward(
        self,
        x: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        x : (batch, seq_len, input_features)
        Returns
        -------
        state_pred   : (batch, input_features)
        attack_logit : (batch, 1)
        stage_logits : (batch, num_stages)
        """
        x    = self.input_projection(x) + self.pos_embedding
        x    = self.transformer(x)
        x    = self.norm(x)
        last = x[:, -1, :]
        return self.state_head(last), self.attack_head(last), self.stage_head(last)


# ============================================================
# Loader helper
# ============================================================

def load_model(
    checkpoint_path: Path,
    device: torch.device,
    num_stages: int = 5,
) -> tuple[TemporalWorldModel, dict]:
    """
    Load TemporalWorldModel from a checkpoint.

    Returns (model_in_eval_mode, ckpt_dict).
    Architecture hyper-parameters are read from the checkpoint itself
    so there is no risk of mismatch.
    """
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)

    model = TemporalWorldModel(
        input_features  = int(ckpt["input_features"]),
        sequence_length = int(ckpt["sequence_length"]),
        d_model         = int(ckpt["d_model"]),
        nhead           = int(ckpt["nhead"]),
        num_layers      = int(ckpt["num_layers"]),
        dim_feedforward = int(ckpt["dim_feedforward"]),
        dropout         = float(ckpt["dropout"]),
        num_stages      = num_stages,
    ).to(device)

    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    return model, ckpt


# ============================================================
# Shared rollout kernel (used by all scripts)
# ============================================================

import numpy as np


def autoregressive_rollout(
    model:            TemporalWorldModel,
    initial_sequence: np.ndarray,
    steps:            int,
    stage_names:      list[str],
    device:           torch.device,
) -> list[dict]:
    """
    Run a fully autoregressive rollout.

    Parameters
    ----------
    initial_sequence : (seq_len, features) — standardised
    steps            : number of future windows to predict

    Returns
    -------
    list of dicts, one per step:
        step, predicted_state_scaled, attack_prob,
        stage_id, stage_name, stage_confidence
    """
    model.eval()
    window  = initial_sequence.copy().astype(np.float32)
    results = []

    with torch.no_grad():
        for step in range(1, steps + 1):
            x = torch.tensor(
                window, dtype=torch.float32, device=device
            ).unsqueeze(0)

            state_pred, attack_logit, stage_logits = model(x)

            pred_state  = state_pred.squeeze(0).cpu().numpy()
            attack_prob = float(torch.sigmoid(attack_logit).item())
            stage_probs = torch.softmax(stage_logits, dim=-1).squeeze(0).cpu().numpy()
            stage_id    = int(np.argmax(stage_probs))
            stage_conf  = float(stage_probs[stage_id])

            results.append({
                "step":                   step,
                "predicted_state_scaled": pred_state,
                "attack_prob":            attack_prob,
                "stage_id":               stage_id,
                "stage_name":             stage_names[stage_id],
                "stage_confidence":       stage_conf,
            })

            # Slide window — append predicted state, drop oldest
            window = np.concatenate(
                [window[1:], pred_state[np.newaxis, :]], axis=0
            )

    return results


def inverse_transform(
    arr:   np.ndarray,
    mean:  np.ndarray,
    scale: np.ndarray,
) -> np.ndarray:
    """Reverse StandardScaler: accepts (44,) or (N, 44)."""
    return arr * scale + mean
