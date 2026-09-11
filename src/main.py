"""
main.py
=======
FastAPI REST API for the AI World Model for Predictive Cyber Defence.
SIH project — exposes the existing CPU-only TemporalWorldModel via HTTP.

Run
---
From project root:
    python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
    uvicorn src.main:app --reload          (development, auto-reload)

Docs
----
    http://127.0.0.1:8000/docs    (Swagger UI)
    http://127.0.0.1:8000/redoc   (ReDoc)

IMPORTANT
---------
- CPU-only.  No CUDA required.
- The trained checkpoint models/world_model.pt is loaded read-only at startup.
- The dataset data/simulated/fused_train_val_test.npz is loaded read-only.
- No retraining occurs.
- Rollout is fully autoregressive — ground-truth future states are never
  used as model inputs.
- MITRE ATT&CK mapping is a prototype stage-to-technique mapping.
  The model does not directly detect specific ATT&CK techniques.
- CORS is open (*) for local development; restrict in production.
"""

from __future__ import annotations

import os
import sys
import uuid
import shutil
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

warnings.filterwarnings("ignore")

# ── resolve src/ on the Python path so sibling imports work ───────────────
_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# ── Load .env early so alert_manager picks up vars at import time ─────────
try:
    from dotenv import load_dotenv as _load_dotenv
    _dotenv = _SRC.parent / ".env"
    if _dotenv.exists():
        _load_dotenv(dotenv_path=_dotenv, override=False)
except ImportError:
    pass

from model import load_model, autoregressive_rollout, inverse_transform
from mitre_mapping import get_mitre_mapping, all_stages
from explain_prediction import explain_prediction
from alert_manager import (
    AlertStateManager, calculate_risk_level, is_escalation,
    format_alert_email, send_alert_email, send_test_email,
    get_smtp_config, is_smtp_configured, alerts_enabled,
)
from upload_validator import validate_upload, MAX_FILE_BYTES
from telemetry_pipeline import (
    process_uploaded_csv, FEATURE_COLUMNS as PIPELINE_FEATURE_COLUMNS,
    SEQUENCE_LENGTH as PIPELINE_SEQ_LEN,
)
from db import init_db, persist_run, list_runs, get_run, get_run_forecast, restore_all_runs

# ============================================================
# Paths
# ============================================================

ROOT       = _SRC.parent
MODEL_FILE = ROOT / "models" / "world_model.pt"
DATA_FILE  = ROOT / "data" / "simulated" / "fused_train_val_test.npz"
RESULTS    = ROOT / "results"
COMPARISON_FILE = RESULTS / "model_comparison.csv"
UPLOAD_DIR = ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DEVICE        = torch.device("cpu")
ROLLOUT_STEPS = 5
TOP_FEATURES  = 10

# In-memory analysis store  {analysis_id: dict}
_analysis_store: dict[str, dict] = {}

# ============================================================
# Application state (loaded once at startup)
# ============================================================

class AppState:
    model       = None
    ckpt        = None
    X_test      = None
    y_attack    = None
    y_stage     = None
    scaler_mean = None
    scaler_scale= None
    feature_cols: list[str] = []
    stage_names:  list[str] = []
    n_params:     int = 0
    alert_mgr:  Optional[AlertStateManager] = None


state = AppState()


# ============================================================
# Lifespan — load model + data once on startup
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Load model ─────────────────────────────────────────────
    if not MODEL_FILE.exists():
        raise RuntimeError(
            f"Checkpoint not found: {MODEL_FILE}\n"
            "Place models/world_model.pt in the project root before starting."
        )
    if not DATA_FILE.exists():
        raise RuntimeError(
            f"Dataset not found: {DATA_FILE}\n"
            "Place data/simulated/fused_train_val_test.npz before starting."
        )

    npz = np.load(DATA_FILE, allow_pickle=True)
    state.X_test       = npz["X_test"]
    state.y_attack     = npz["y_attack_test"]
    state.y_stage      = npz["y_stage_test"]
    state.scaler_mean  = npz["scaler_mean"]
    state.scaler_scale = npz["scaler_scale"]
    state.feature_cols = [str(c) for c in npz["feature_columns"]]
    state.stage_names  = [str(s) for s in npz["stage_names"]]

    state.model, state.ckpt = load_model(
        MODEL_FILE, DEVICE, num_stages=len(state.stage_names)
    )
    state.n_params = sum(p.numel() for p in state.model.parameters())

    # Initialise alert manager with configured cooldown
    cooldown = int(os.environ.get("ALERT_COOLDOWN_SECONDS", "300"))
    state.alert_mgr = AlertStateManager(cooldown_seconds=cooldown)

    # ── Initialise SQLite database ─────────────────────────────
    init_db()
    restored = restore_all_runs(_analysis_store)

    print(f"[startup] model loaded  : {MODEL_FILE.name}  ({state.n_params:,} params)")
    print(f"[startup] dataset loaded: {DATA_FILE.name}  ({len(state.X_test)} test samples)")
    print(f"[startup] device        : {DEVICE}")
    if restored:
        print(f"[startup] restored {restored} run(s) from SQLite into memory store")

    yield   # application runs here

    print("[shutdown] API stopping.")


# ============================================================
# FastAPI application
# ============================================================

app = FastAPI(
    title       = "AI World Model for Predictive Cyber Defence API",
    description = (
        "This API exposes a CPU-only Temporal Transformer World Model for "
        "predictive cyber defence. It forecasts future network attack stages "
        "using autoregressive temporal state prediction.\n\n"
        "**Key properties**\n"
        "- Trained checkpoint is loaded read-only; no retraining occurs.\n"
        "- Rollout is fully autoregressive — predicted states are fed back; "
        "ground-truth future states are never used as model inputs.\n"
        "- MITRE ATT&CK mapping is a **prototype stage-to-technique mapping**. "
        "The model does not directly detect specific ATT&CK techniques "
        "from raw telemetry.\n"
        "- Explainability uses **feature ablation sensitivity** — "
        "sensitivity scores indicate prediction influence and do not "
        "establish causation.\n"
        "- CORS is open for local development; restrict `allow_origins` in production."
    ),
    version     = "1.0.0",
    lifespan    = lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],   # restrict to specific origins in production
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ============================================================
# Helper: validate sample index
# ============================================================

def _resolve_sample(sample_id: int) -> int:
    """
    Validate and return a non-negative index into X_test.
    Raises HTTPException 400/404 on invalid input.
    """
    n = len(state.X_test)
    if sample_id < 0:
        raise HTTPException(
            status_code=400,
            detail=f"sample_id must be non-negative. Received: {sample_id}.",
        )
    if sample_id >= n:
        raise HTTPException(
            status_code=404,
            detail=f"Sample index out of range. Valid range: 0-{n - 1}.",
        )
    return sample_id


# ============================================================
# Pydantic response models
# ============================================================

class HealthResponse(BaseModel):
    status:      str
    model:       str
    device:      str
    input_shape: list[int]

class ModelInfoResponse(BaseModel):
    model_type:              str
    device:                  str
    sequence_length:         int
    num_features:            int
    num_stages:              int
    parameters:              int
    autoregressive_horizon:  int

class SamplesResponse(BaseModel):
    num_test_samples: int
    sequence_length:  int
    num_features:     int
    stages:           list[str]

class PredictionResponse(BaseModel):
    sample_id:          int
    current_true_stage: str
    attack_probability: float
    attack_detected:    bool
    predicted_stage:    str
    stage_confidence:   float
    mitre_attack_id:    Optional[str]
    mitre_attack_name:  Optional[str]

class ForecastStep(BaseModel):
    step:               int
    stage:              str
    attack_probability: float
    attack_detected:    bool
    stage_confidence:   float
    mitre_attack_id:    Optional[str]
    mitre_attack_name:  Optional[str]

class ForecastResponse(BaseModel):
    sample_id:          int
    horizon:            int
    ground_truth_used:  bool
    forecast:           list[ForecastStep]

class ForecastStateStep(BaseModel):
    step:     int
    features: dict[str, float]

class ForecastStatesResponse(BaseModel):
    sample_id: int
    states:    list[ForecastStateStep]

class ExplainFeature(BaseModel):
    rank:        int
    feature:     str
    sensitivity: float = Field(..., description="Absolute change in model output when feature is ablated")

class ExplainResponse(BaseModel):
    sample_id:  int
    method:     str
    warning:    str
    features:   list[ExplainFeature]

class ComparisonRow(BaseModel):
    Model:             str
    Temporal_History:  str
    Attack_Accuracy:   str
    Attack_Precision:  str
    Attack_Recall:     str
    Attack_F1:         str
    Stage_Accuracy:    str
    Stage_Macro_F1:    str

# ── Alert Pydantic models ─────────────────────────────────────────────────

class AlertStatusResponse(BaseModel):
    enabled:              bool
    configured:           bool
    recipient_configured: bool
    smtp_configured:      bool

class AlertTestResponse(BaseModel):
    success: bool
    message: str

class AlertEvaluateResponse(BaseModel):
    sample_id:          int
    risk_level:         str
    attack_probability: float
    predicted_stage:    str
    mitre_attack_id:    Optional[str]
    mitre_attack_name:  Optional[str]
    escalation_detected:bool
    email_sent:         bool
    reason:             str


# ============================================================
# Endpoints
# ============================================================

# ── GET /health ───────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health() -> HealthResponse:
    """
    Returns API health status.
    Returns HTTP 500 if the model failed to load.
    """
    if state.model is None:
        raise HTTPException(status_code=500, detail="Model not loaded.")
    return HealthResponse(
        status      = "healthy",
        model       = "Temporal Transformer World Model",
        device      = str(DEVICE),
        input_shape = [5, 44],
    )


# ── GET /model/info ───────────────────────────────────────────────────────

@app.get("/model/info", response_model=ModelInfoResponse, tags=["Model"])
def model_info() -> ModelInfoResponse:
    """Returns architecture and configuration details of the loaded model."""
    ckpt = state.ckpt
    return ModelInfoResponse(
        model_type             = "Temporal Transformer",
        device                 = str(DEVICE),
        sequence_length        = int(ckpt["sequence_length"]),
        num_features           = int(ckpt["input_features"]),
        num_stages             = len(state.stage_names),
        parameters             = state.n_params,
        autoregressive_horizon = ROLLOUT_STEPS,
    )


# ── GET /samples ──────────────────────────────────────────────────────────

@app.get("/samples", response_model=SamplesResponse, tags=["Dataset"])
def samples() -> SamplesResponse:
    """Returns basic dataset information (no raw data returned)."""
    return SamplesResponse(
        num_test_samples = len(state.X_test),
        sequence_length  = int(state.X_test.shape[1]),
        num_features     = int(state.X_test.shape[2]),
        stages           = state.stage_names,
    )


# ── GET /predict/{sample_id} ──────────────────────────────────────────────

@app.get("/predict/{sample_id}", response_model=PredictionResponse, tags=["Inference"])
def predict(sample_id: int) -> PredictionResponse:
    """
    Single-step prediction for X_test[sample_id].

    The model is run on the 5-window sequence.  The current_true_stage
    is provided as reference context only — it is NOT fed into the model.
    """
    idx = _resolve_sample(sample_id)

    sequence = state.X_test[idx].astype(np.float32)        # (5, 44)
    current_true_stage = state.stage_names[int(state.y_stage[idx])]

    x = torch.tensor(sequence, dtype=torch.float32, device=DEVICE).unsqueeze(0)
    with torch.no_grad():
        _, attack_logit, stage_logits = state.model(x)

    attack_prob = round(float(torch.sigmoid(attack_logit).item()), 4)
    stage_probs = torch.softmax(stage_logits, dim=-1).squeeze(0).cpu().numpy()
    stage_id    = int(np.argmax(stage_probs))
    stage_conf  = round(float(stage_probs[stage_id]), 4)
    pred_stage  = state.stage_names[stage_id]
    mitre       = get_mitre_mapping(pred_stage)

    return PredictionResponse(
        sample_id          = idx,
        current_true_stage = current_true_stage,
        attack_probability = attack_prob,
        attack_detected    = attack_prob >= 0.5,
        predicted_stage    = pred_stage,
        stage_confidence   = stage_conf,
        mitre_attack_id    = mitre["mitre_attack_id"],
        mitre_attack_name  = mitre["mitre_attack_name"],
    )


# ── GET /forecast/{sample_id} ─────────────────────────────────────────────

@app.get("/forecast/{sample_id}", response_model=ForecastResponse, tags=["Inference"])
def forecast(sample_id: int) -> ForecastResponse:
    """
    5-step fully autoregressive rollout starting from X_test[sample_id].

    At each step the model's own predicted state is fed back as input —
    ground-truth future states are never used.
    """
    idx = _resolve_sample(sample_id)

    trajectory = autoregressive_rollout(
        model            = state.model,
        initial_sequence = state.X_test[idx],
        steps            = ROLLOUT_STEPS,
        stage_names      = state.stage_names,
        device           = DEVICE,
    )

    steps_out = []
    for entry in trajectory:
        mitre = get_mitre_mapping(entry["stage_name"])
        steps_out.append(ForecastStep(
            step               = entry["step"],
            stage              = entry["stage_name"],
            attack_probability = round(entry["attack_prob"], 4),
            attack_detected    = entry["attack_prob"] >= 0.5,
            stage_confidence   = round(entry["stage_confidence"], 4),
            mitre_attack_id    = mitre["mitre_attack_id"],
            mitre_attack_name  = mitre["mitre_attack_name"],
        ))

    return ForecastResponse(
        sample_id         = idx,
        horizon           = ROLLOUT_STEPS,
        ground_truth_used = False,
        forecast          = steps_out,
    )


# ── GET /forecast/{sample_id}/states ──────────────────────────────────────

@app.get(
    "/forecast/{sample_id}/states",
    response_model=ForecastStatesResponse,
    tags=["Inference"],
)
def forecast_states(sample_id: int) -> ForecastStatesResponse:
    """
    Returns the 44 predicted network-state features for each of the
    5 autoregressive rollout steps, inverse-transformed back to the
    original (non-standardised) feature scale.
    """
    idx = _resolve_sample(sample_id)

    trajectory = autoregressive_rollout(
        model            = state.model,
        initial_sequence = state.X_test[idx],
        steps            = ROLLOUT_STEPS,
        stage_names      = state.stage_names,
        device           = DEVICE,
    )

    scaled_arr = np.array([e["predicted_state_scaled"] for e in trajectory])
    orig_arr   = inverse_transform(scaled_arr, state.scaler_mean, state.scaler_scale)

    state_steps = []
    for i, entry in enumerate(trajectory):
        features = {
            col: round(float(orig_arr[i, j]), 4)
            for j, col in enumerate(state.feature_cols)
        }
        state_steps.append(ForecastStateStep(step=entry["step"], features=features))

    return ForecastStatesResponse(sample_id=idx, states=state_steps)


# ── GET /explain/{sample_id} ──────────────────────────────────────────────

@app.get("/explain/{sample_id}", response_model=ExplainResponse, tags=["Explainability"])
def explain(sample_id: int) -> ExplainResponse:
    """
    Feature ablation sensitivity analysis for X_test[sample_id].

    Each feature is zeroed across all 5 time-steps; the absolute change in
    the top stage probability is recorded as the sensitivity score.

    WARNING: Sensitivity ≠ causation.  These scores indicate how much the
    model's prediction changes when a feature's information is removed;
    they do not establish that the feature *caused* the attack.
    """
    idx = _resolve_sample(sample_id)
    sequence = state.X_test[idx]

    importance_df = explain_prediction(
        model        = state.model,
        sequence     = sequence,
        feature_cols = state.feature_cols,
        stage_names  = state.stage_names,
        target       = "stage",
    )

    top = importance_df.head(TOP_FEATURES)
    features_out = [
        ExplainFeature(
            rank        = int(row["rank"]),
            feature     = str(row["feature"]),
            sensitivity = round(float(row["importance"]), 6),
        )
        for _, row in top.iterrows()
    ]

    return ExplainResponse(
        sample_id = idx,
        method    = "feature_ablation_sensitivity",
        warning   = (
            "Sensitivity indicates prediction influence and does not "
            "establish causation."
        ),
        features  = features_out,
    )


# ── GET /model/comparison ─────────────────────────────────────────────────

@app.get("/model/comparison", tags=["Model"])
def model_comparison() -> list[dict]:
    """
    Returns model comparison data from results/model_comparison.csv.
    Returns HTTP 404 if the file has not been generated yet.
    """
    if not COMPARISON_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "results/model_comparison.csv not found. "
                "Run the evaluation pipeline first."
            ),
        )
    import pandas as pd
    df = pd.read_csv(COMPARISON_FILE)
    return df.fillna("N/A").to_dict(orient="records")


# ── GET /alerts/status ────────────────────────────────────────────────────

@app.get("/alerts/status", response_model=AlertStatusResponse, tags=["Alerts"])
def alert_status() -> AlertStatusResponse:
    """
    Returns the current alert / email configuration status.
    Never returns SMTP credentials.
    """
    cfg = get_smtp_config()
    return AlertStatusResponse(
        enabled              = cfg["enabled"],
        configured           = is_smtp_configured(),
        recipient_configured = bool(cfg["recipient"]),
        smtp_configured      = bool(cfg["username"] and cfg["password"]),
    )


# ── POST /alerts/test ─────────────────────────────────────────────────────

@app.post("/alerts/test", response_model=AlertTestResponse, tags=["Alerts"])
def alert_test() -> AlertTestResponse:
    """
    Sends a test email to verify SMTP configuration.
    The email is clearly labelled as a test and is NOT a security alert.
    Returns HTTP 503 if email sending fails.
    """
    success, message = send_test_email()
    if not success:
        # Distinguish between "disabled" (200) and "configuration error" (503)
        cfg = get_smtp_config()
        if not cfg["enabled"]:
            return AlertTestResponse(success=False, message=message)
        raise HTTPException(status_code=503, detail=message)
    return AlertTestResponse(success=True, message=message)


# ── POST /alerts/evaluate/{sample_id} ────────────────────────────────────

@app.post(
    "/alerts/evaluate/{sample_id}",
    response_model=AlertEvaluateResponse,
    tags=["Alerts"],
)
def alert_evaluate(sample_id: int) -> AlertEvaluateResponse:
    """
    1. Loads X_test[sample_id].
    2. Runs the World Model (single-step prediction + 5-step rollout).
    3. Calculates risk level.
    4. Determines whether escalation occurred.
    5. If escalation detected AND alerts enabled AND not in cooldown → sends email.
    6. Returns the alert decision as JSON.

    Emails are sent only on meaningful escalation and respect the cooldown
    period to prevent flooding.  Ground-truth future states are never used.
    """
    idx = _resolve_sample(sample_id)

    # ── Single-step prediction ─────────────────────────────────
    sequence = state.X_test[idx].astype(np.float32)
    current_true_stage = state.stage_names[int(state.y_stage[idx])]

    x = torch.tensor(sequence, dtype=torch.float32, device=DEVICE).unsqueeze(0)
    with torch.no_grad():
        _, attack_logit, stage_logits = state.model(x)

    attack_prob = round(float(torch.sigmoid(attack_logit).item()), 4)
    stage_probs = torch.softmax(stage_logits, dim=-1).squeeze(0).cpu().numpy()
    stage_id    = int(np.argmax(stage_probs))
    stage_conf  = round(float(stage_probs[stage_id]), 4)
    pred_stage  = state.stage_names[stage_id]
    mitre       = get_mitre_mapping(pred_stage)
    risk_level  = calculate_risk_level(attack_prob, pred_stage)

    # ── Escalation check ──────────────────────────────────────
    send, reason = state.alert_mgr.should_send(
        sample_id     = idx,
        risk_level    = risk_level,
        predicted_stage = pred_stage,
    )

    email_sent = False

    if send:
        # ── 5-step rollout for trajectory + top features ───────
        trajectory = autoregressive_rollout(
            model            = state.model,
            initial_sequence = state.X_test[idx],
            steps            = ROLLOUT_STEPS,
            stage_names      = state.stage_names,
            device           = DEVICE,
        )
        traj_stages = [e["stage_name"] for e in trajectory]

        importance_df = explain_prediction(
            model        = state.model,
            sequence     = state.X_test[idx],
            feature_cols = state.feature_cols,
            stage_names  = state.stage_names,
            target       = "stage",
        )
        top_features = importance_df.head(5)["feature"].tolist()

        subject, html_body, plain_body = format_alert_email(
            sample_id          = idx,
            risk_level         = risk_level,
            attack_probability = attack_prob,
            current_stage      = current_true_stage,
            predicted_stage    = pred_stage,
            stage_confidence   = stage_conf,
            forecast_horizon   = ROLLOUT_STEPS,
            mitre_id           = mitre["mitre_attack_id"],
            mitre_name         = mitre["mitre_attack_name"],
            trajectory         = traj_stages,
            top_features       = top_features,
            escalation_reason  = reason,
        )

        ok, send_msg = send_alert_email(subject, html_body, plain_body)
        email_sent = ok

        if ok:
            state.alert_mgr.record_alert(idx, risk_level, pred_stage)
            reason = send_msg
        else:
            reason = send_msg   # e.g. "Alerts are disabled." or SMTP error

    return AlertEvaluateResponse(
        sample_id           = idx,
        risk_level          = risk_level,
        attack_probability  = attack_prob,
        predicted_stage     = pred_stage,
        mitre_attack_id     = mitre["mitre_attack_id"],
        mitre_attack_name   = mitre["mitre_attack_name"],
        escalation_detected = send,
        email_sent          = email_sent,
        reason              = reason,
    )

# ============================================================
# Upload / Analysis Pydantic models
# ============================================================

class UploadResponse(BaseModel):
    upload_id:   str
    filename:    str
    size_bytes:  int
    file_type:   Optional[str]
    rows:        int
    status:      str
    message:     str
    has_labels:  bool

class AnalysisInput(BaseModel):
    filename:     str
    records:      int
    time_windows: int
    ts_start:     str
    ts_end:       str
    file_type:    str

class CurrentState(BaseModel):
    stage:              str
    attack_probability: float
    risk:               str
    stage_confidence:   float
    mitre_attack_id:    Optional[str]
    mitre_attack_name:  Optional[str]

class ForecastStepUpload(BaseModel):
    step:               int
    attack_probability: float
    risk:               str
    stage:              str
    stage_confidence:   float
    mitre_attack_id:    Optional[str]
    mitre_attack_name:  Optional[str]

class ExplainFeatureUpload(BaseModel):
    feature:     str
    sensitivity: float

class EvalMetrics(BaseModel):
    attack_accuracy:  Optional[float]
    attack_precision: Optional[float]
    attack_recall:    Optional[float]
    attack_f1:        Optional[float]

class AnalysisResponse(BaseModel):
    analysis_id:    str
    status:         str
    input:          AnalysisInput
    current_state:  CurrentState
    forecast:       list[ForecastStepUpload]
    explainability: list[ExplainFeatureUpload]
    metrics:        Optional[EvalMetrics]

class WindowStateOut(BaseModel):
    window_index:  int
    window_start:  str
    record_count:  int
    features:      dict[str, float]

class StatesResponse(BaseModel):
    analysis_id:  str
    time_windows: int
    states:       list[WindowStateOut]


# ============================================================
# Helper: build entity summary from pipeline entities
# ============================================================

def _build_entity_summary(
    pipe,
    network_risk:  str,
    attack_prob:   float,
    pred_stage:    str,
    stage_conf:    float,
    mitre:         dict,
    forecast:      list,
) -> Optional[dict]:
    """
    Build the entity summary dict for storage in _analysis_store.

    Since the model is network-level only, every entity receives the same
    network-level risk/stage values.  The summary clearly labels this as
    NETWORK-LEVEL PREDICTION when no entity IDs are present, or provides
    individual device rows when src_ip/dst_ip columns were found.

    Returns None only when there is truly no entity data and not even a
    network-level summary to show (should never happen).
    """
    # Build the forecast trajectory list (for frontend display)
    trajectory = [
        {
            "step":               f["step"],
            "stage":              f["stage"],
            "attack_probability": f["attack_probability"],
            "stage_confidence":   f["stage_confidence"],
            "risk":               f["risk"],
            "mitre_attack_id":    f["mitre_attack_id"],
            "mitre_attack_name":  f["mitre_attack_name"],
        }
        for f in forecast
    ]

    # Highest predicted risk across the forecast
    risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    highest_risk = max(
        [f["risk"] for f in forecast] + [network_risk],
        key=lambda r: risk_order.get(r, -1),
    )

    if not pipe.has_entity_ids or not pipe.entities:
        # No valid IP columns → network-level prediction only
        return {
            "has_entity_ids":   False,
            "prediction_scope": "network-level",
            "total_entities":   0,
            "entities":         [],
            "network_prediction": {
                "attack_probability": attack_prob,
                "risk":               network_risk,
                "highest_risk":       highest_risk,
                "predicted_stage":    pred_stage,
                "stage_confidence":   stage_conf,
                "mitre_attack_id":    mitre["mitre_attack_id"],
                "mitre_attack_name":  mitre["mitre_attack_name"],
                "trajectory":         trajectory,
            },
        }

    # We have entity IDs — build per-entity rows.
    # The risk/stage/probability values are the network-level model outputs
    # applied uniformly; we do NOT manufacture per-entity model predictions.
    normal_threshold   = 0.30
    suspicious_threshold = 0.50

    entities_out = []
    for ent in pipe.entities:
        entities_out.append({
            "entity_id":          ent.entity_id,
            "record_count":       ent.record_count,
            "first_seen":         ent.first_seen,
            "last_seen":          ent.last_seen,
            "unique_dst_ips":     ent.unique_dst_ips,
            "unique_dst_ports":   ent.unique_dst_ports,
            "protocols":          ent.protocols,
            # Network-level inference values (same for all entities from
            # this upload — clearly labelled as network-scope).
            "attack_probability": attack_prob,
            "risk":               network_risk,
            "highest_risk":       highest_risk,
            "predicted_stage":    pred_stage,
            "stage_confidence":   stage_conf,
            "mitre_attack_id":    mitre["mitre_attack_id"],
            "mitre_attack_name":  mitre["mitre_attack_name"],
            "trajectory":         trajectory,
            "prediction_scope":   "network-level",
        })

    # Aggregate device counts using the network-level thresholds
    if attack_prob < normal_threshold:
        normal_count     = len(entities_out)
        suspicious_count = 0
        high_risk_count  = 0
    elif attack_prob < suspicious_threshold:
        normal_count     = 0
        suspicious_count = len(entities_out)
        high_risk_count  = 0
    else:
        normal_count     = 0
        suspicious_count = 0
        high_risk_count  = len(entities_out)

    return {
        "has_entity_ids":   True,
        "prediction_scope": "network-level",
        "total_entities":   len(entities_out),
        "normal_count":     normal_count,
        "suspicious_count": suspicious_count,
        "high_risk_count":  high_risk_count,
        "entities":         entities_out,
        "network_prediction": {
            "attack_probability": attack_prob,
            "risk":               network_risk,
            "highest_risk":       highest_risk,
            "predicted_stage":    pred_stage,
            "stage_confidence":   stage_conf,
            "mitre_attack_id":    mitre["mitre_attack_id"],
            "mitre_attack_name":  mitre["mitre_attack_name"],
            "trajectory":         trajectory,
        },
    }


# ============================================================
# Helper: run full analysis from a pipeline result
# ============================================================

def _run_analysis(
    analysis_id:  str,
    pipe,               # PipelineResult
    upload_path:  Path,
) -> dict:
    """
    Core analysis: inference + rollout + explainability + optional metrics.
    Returns a dict stored in _analysis_store.
    """
    import pandas as pd
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score
    )

    # Latest sequence = last 5 windows
    init_seq = pipe.sequences[-1]   # (5, 44)

    # ── Single-step prediction ─────────────────────────────────
    x = torch.tensor(
        init_seq.astype(np.float32), dtype=torch.float32, device=DEVICE
    ).unsqueeze(0)
    with torch.no_grad():
        _, attack_logit, stage_logits = state.model(x)

    attack_prob = round(float(torch.sigmoid(attack_logit).item()), 4)
    sp          = torch.softmax(stage_logits, dim=-1).squeeze(0).cpu().numpy()
    stage_id    = int(np.argmax(sp))
    stage_conf  = round(float(sp[stage_id]), 4)
    pred_stage  = state.stage_names[stage_id]
    mitre       = get_mitre_mapping(pred_stage)
    risk        = calculate_risk_level(attack_prob, pred_stage)

    current_state = {
        "stage":              pred_stage,
        "attack_probability": attack_prob,
        "risk":               risk,
        "stage_confidence":   stage_conf,
        "mitre_attack_id":    mitre["mitre_attack_id"],
        "mitre_attack_name":  mitre["mitre_attack_name"],
    }

    # ── Autoregressive rollout ─────────────────────────────────
    traj = autoregressive_rollout(
        model            = state.model,
        initial_sequence = init_seq,
        steps            = ROLLOUT_STEPS,
        stage_names      = state.stage_names,
        device           = DEVICE,
    )
    forecast = []
    for entry in traj:
        m = get_mitre_mapping(entry["stage_name"])
        forecast.append({
            "step":               entry["step"],
            "attack_probability": round(entry["attack_prob"], 4),
            "risk":               calculate_risk_level(entry["attack_prob"],
                                                       entry["stage_name"]),
            "stage":              entry["stage_name"],
            "stage_confidence":   round(entry["stage_confidence"], 4),
            "mitre_attack_id":    m["mitre_attack_id"],
            "mitre_attack_name":  m["mitre_attack_name"],
        })

    # ── Explainability ─────────────────────────────────────────
    imp_df = explain_prediction(
        model        = state.model,
        sequence     = init_seq,
        feature_cols = state.feature_cols,
        stage_names  = state.stage_names,
        target       = "stage",
    )
    explainability = [
        {"feature": str(r["feature"]), "sensitivity": round(float(r["importance"]), 6)}
        for _, r in imp_df.head(TOP_FEATURES).iterrows()
    ]

    # ── Evaluation metrics (only when labels present) ──────────
    metrics = None
    if pipe.has_labels and pipe.window_labels:
        # Build per-sequence true labels (align with pipe.sequences)
        labels_arr = pipe.window_labels
        n_seq = len(pipe.sequences)

        pred_attacks = []
        true_attacks = []

        for i in range(n_seq):
            seq  = pipe.sequences[i]
            true_idx = PIPELINE_SEQ_LEN + i   # window after the sequence
            if true_idx >= len(labels_arr):
                break

            xi = torch.tensor(
                seq.astype(np.float32), dtype=torch.float32, device=DEVICE
            ).unsqueeze(0)
            with torch.no_grad():
                _, al, _ = state.model(xi)
            pred_attacks.append(int(torch.sigmoid(al).item() >= 0.5))

            lbl = labels_arr[true_idx]
            if isinstance(lbl, str):
                true_attacks.append(0 if lbl.lower() in ("benign", "0") else 1)
            else:
                try:
                    true_attacks.append(int(float(str(lbl))) > 0)
                except Exception:
                    true_attacks.append(0)

        if len(pred_attacks) >= 2:
            metrics = {
                "attack_accuracy":  round(accuracy_score(true_attacks, pred_attacks), 4),
                "attack_precision": round(precision_score(true_attacks, pred_attacks,
                                                           zero_division=0), 4),
                "attack_recall":    round(recall_score(true_attacks, pred_attacks,
                                                        zero_division=0), 4),
                "attack_f1":        round(f1_score(true_attacks, pred_attacks,
                                                    zero_division=0), 4),
            }

    # ── Build window-state summaries ───────────────────────────
    windows_out = []
    for wi, row in pipe.states_df.iterrows():
        windows_out.append({
            "window_index":  int(wi),
            "window_start":  str(row.get("window_start", "")),
            "record_count":  int(row.get("packet_count", row.get("flow_count", 0))),
            "features":      {
                col: round(float(pipe.states_df.iloc[wi][col]), 4)
                for col in PIPELINE_FEATURE_COLUMNS
                if col in pipe.states_df.columns
            },
        })

    # ── Entity summary (from preserved IP identifiers) ─────────
    # The current model is network-level only.  Entities are extracted
    # from raw telemetry IP columns for user visibility; the risk/stage
    # values are the network-level inference result applied to all entities
    # — not per-entity model predictions.
    entity_summary = _build_entity_summary(
        pipe         = pipe,
        network_risk = risk,
        attack_prob  = attack_prob,
        pred_stage   = pred_stage,
        stage_conf   = stage_conf,
        mitre        = mitre,
        forecast     = forecast,
    )

    result = {
        "analysis_id":  analysis_id,
        "status":       "completed",
        "upload_path":  str(upload_path),
        "input": {
            "filename":     upload_path.name,
            "records":      pipe.n_records,
            "time_windows": pipe.time_windows,
            "ts_start":     pipe.ts_start,
            "ts_end":       pipe.ts_end,
            "file_type":    pipe.file_type,
        },
        "current_state":   current_state,
        "forecast":        forecast,
        "explainability":  explainability,
        "metrics":         metrics,
        "windows":         windows_out,
        "entity_summary":  entity_summary,   # new — may be None
    }

    return result


# ============================================================
# Upload & Analysis endpoints
# ============================================================

# ── POST /upload ──────────────────────────────────────────────────────────

@app.post("/upload", response_model=UploadResponse, tags=["Upload"])
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    """
    Upload a CSV telemetry file for analysis.

    Accepts:
    - Packet telemetry CSV (simulated_packets.csv compatible)
    - Flow telemetry CSV   (simulated_flow.csv compatible)

    PCAP upload is not currently supported.
    Returns an upload_id to use with POST /analyze/{upload_id}.
    """
    # ── Sanitise filename ──────────────────────────────────────
    raw_name  = Path(file.filename or "upload.csv").name
    safe_name = "".join(
        c for c in raw_name if c.isalnum() or c in "._- "
    ).strip() or "upload.csv"

    # ── Read content ───────────────────────────────────────────
    content = await file.read()

    # ── Quick in-memory validation ────────────────────────────
    from upload_validator import validate_bytes
    quick = validate_bytes(content, safe_name, max_bytes=MAX_FILE_BYTES)
    if not quick.valid:
        err = quick.errors[0]
        if "size" in err.field and "exceeds" in err.message:
            status_code = 413
        else:
            status_code = 400
        raise HTTPException(
            status_code=status_code,
            detail={"field": err.field, "message": err.message},
        )

    # ── Save to unique path ────────────────────────────────────
    upload_id   = uuid.uuid4().hex
    dest        = UPLOAD_DIR / f"{upload_id}_{safe_name}"
    dest.write_bytes(content)

    # ── Full validation ────────────────────────────────────────
    result = validate_upload(dest, max_bytes=MAX_FILE_BYTES)
    if not result.valid:
        dest.unlink(missing_ok=True)
        errors = [{"field": e.field, "message": e.message}
                  for e in result.errors]
        raise HTTPException(status_code=422, detail=errors)

    return UploadResponse(
        upload_id  = upload_id,
        filename   = safe_name,
        size_bytes = len(content),
        file_type  = result.file_type,
        rows       = result.rows,
        status     = "validated",
        message    = "File uploaded successfully. Use POST /analyze/{upload_id} to run analysis.",
        has_labels = result.has_labels,
    )


# ── POST /analyze/{upload_id} ─────────────────────────────────────────────

@app.post("/analyze/{upload_id}", response_model=AnalysisResponse, tags=["Upload"])
def analyze(upload_id: str) -> AnalysisResponse:
    """
    Run the full analysis pipeline on a previously uploaded CSV.

    Pipeline:
    1. Locate the uploaded file
    2. Validate (again for safety)
    3. Build 10-second network-state windows (44 features)
    4. Standardise using training-set scaler (never refit)
    5. Build 5-window sequences
    6. Run Temporal Transformer inference on the latest sequence
    7. Run 5-step autoregressive forecast
    8. Compute feature sensitivity (explainability)
    9. Compute evaluation metrics if ground-truth labels present

    Returns structured JSON for frontend consumption.
    """
    # Find upload file
    matches = list(UPLOAD_DIR.glob(f"{upload_id}_*"))
    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"Upload ID '{upload_id}' not found. "
                   "Upload a file first with POST /upload.",
        )
    upload_path = matches[0]

    # Check if already analysed
    if upload_id in _analysis_store:
        stored = _analysis_store[upload_id]
        return AnalysisResponse(**_to_analysis_response(stored))

    # ── Run pipeline ───────────────────────────────────────────
    try:
        pipe = process_uploaded_csv(
            file_path    = upload_path,
            scaler_mean  = state.scaler_mean,
            scaler_scale = state.scaler_scale,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline error: {type(exc).__name__}: {exc}",
        )

    # ── Run inference ──────────────────────────────────────────
    try:
        stored = _run_analysis(upload_id, pipe, upload_path)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Inference error: {type(exc).__name__}: {exc}",
        )

    _analysis_store[upload_id] = stored

    # ── Persist to SQLite ──────────────────────────────────────
    try:
        persist_run(stored, source_type="uploaded")
    except Exception as db_exc:
        # DB failure must not break the API response — log and continue
        import logging
        logging.getLogger("main").warning(
            "[db] persist_run failed for %s: %s", upload_id, db_exc
        )

    return AnalysisResponse(**_to_analysis_response(stored))


# ── GET /analysis/{analysis_id} ───────────────────────────────────────────

@app.get("/analysis/{analysis_id}", response_model=AnalysisResponse, tags=["Upload"])
def get_analysis(analysis_id: str) -> AnalysisResponse:
    """Retrieve a previously completed analysis result."""
    if analysis_id not in _analysis_store:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis ID '{analysis_id}' not found.",
        )
    return AnalysisResponse(**_to_analysis_response(_analysis_store[analysis_id]))


# ── GET /analysis/{analysis_id}/forecast ──────────────────────────────────

@app.get("/analysis/{analysis_id}/forecast", tags=["Upload"])
def get_analysis_forecast(analysis_id: str) -> dict:
    """Return only the 5-step forecast from a completed analysis."""
    if analysis_id not in _analysis_store:
        raise HTTPException(status_code=404,
                            detail=f"Analysis ID '{analysis_id}' not found.")
    s = _analysis_store[analysis_id]
    return {
        "analysis_id":    analysis_id,
        "horizon":        ROLLOUT_STEPS,
        "ground_truth_used": False,
        "forecast":       s["forecast"],
    }


# ── GET /analysis/{analysis_id}/states ────────────────────────────────────

@app.get("/analysis/{analysis_id}/states",
         response_model=StatesResponse, tags=["Upload"])
def get_analysis_states(analysis_id: str) -> StatesResponse:
    """Return the 10-second network-state feature vectors for a completed analysis."""
    if analysis_id not in _analysis_store:
        raise HTTPException(status_code=404,
                            detail=f"Analysis ID '{analysis_id}' not found.")
    s = _analysis_store[analysis_id]
    states_out = [WindowStateOut(**w) for w in s["windows"]]
    return StatesResponse(
        analysis_id  = analysis_id,
        time_windows = s["input"]["time_windows"],
        states       = states_out,
    )


# ── GET /analysis/{analysis_id}/explain ──────────────────────────────────

@app.get("/analysis/{analysis_id}/explain", tags=["Upload"])
def get_analysis_explain(analysis_id: str) -> dict:
    """Return feature sensitivity explainability for a completed analysis."""
    if analysis_id not in _analysis_store:
        raise HTTPException(status_code=404,
                            detail=f"Analysis ID '{analysis_id}' not found.")
    s = _analysis_store[analysis_id]
    return {
        "analysis_id": analysis_id,
        "method":      "feature_ablation_sensitivity",
        "warning":     "Sensitivity indicates prediction influence and does not establish causation.",
        "features":    s["explainability"],
    }


# ── GET /analysis/{analysis_id}/entities ─────────────────────────────────

@app.get("/analysis/{analysis_id}/entities", tags=["Upload"])
def get_analysis_entities(analysis_id: str) -> dict:
    """
    Return monitored entities and their current risk from a completed analysis.

    Prediction scope is always "network-level" — the current model was trained
    on network-aggregated states and does not produce per-entity predictions.
    Risk/stage values are the network-level model output applied uniformly.

    When the uploaded file contains src_ip/dst_ip columns, individual device
    identifiers are returned.  When those columns are absent the response
    carries prediction_scope="network-level" and an empty entities list,
    with the aggregated network prediction in the network_prediction field.

    Response shape
    --------------
    {
      "analysis_id":      str,
      "has_entity_ids":   bool,
      "prediction_scope": "network-level",
      "total_entities":   int,
      "normal_count":     int,          # only present when has_entity_ids=True
      "suspicious_count": int,
      "high_risk_count":  int,
      "entities": [
        {
          "entity_id":          str,
          "record_count":       int,
          "first_seen":         str,
          "last_seen":          str,
          "unique_dst_ips":     list[str],
          "unique_dst_ports":   list[int],
          "protocols":          list[str],
          "attack_probability": float,
          "risk":               str,
          "highest_risk":       str,
          "predicted_stage":    str,
          "stage_confidence":   float,
          "mitre_attack_id":    str | null,
          "mitre_attack_name":  str | null,
          "trajectory":         list[ForecastStep],
          "prediction_scope":   "network-level"
        }, ...
      ],
      "network_prediction": { attack_probability, risk, highest_risk,
                              predicted_stage, stage_confidence,
                              mitre_attack_id, mitre_attack_name,
                              trajectory }
    }
    """
    if analysis_id not in _analysis_store:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis ID '{analysis_id}' not found.",
        )
    s = _analysis_store[analysis_id]
    summary = s.get("entity_summary")
    if summary is None:
        # Fallback: build a minimal network-level response from stored current_state
        cs = s["current_state"]
        traj = [
            {
                "step":               f["step"],
                "stage":              f["stage"],
                "attack_probability": f["attack_probability"],
                "stage_confidence":   f["stage_confidence"],
                "risk":               f["risk"],
                "mitre_attack_id":    f["mitre_attack_id"],
                "mitre_attack_name":  f["mitre_attack_name"],
            }
            for f in s["forecast"]
        ]
        risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        highest = max(
            [f["risk"] for f in s["forecast"]] + [cs["risk"]],
            key=lambda r: risk_order.get(r, -1),
        )
        summary = {
            "has_entity_ids":   False,
            "prediction_scope": "network-level",
            "total_entities":   0,
            "entities":         [],
            "network_prediction": {
                "attack_probability": cs["attack_probability"],
                "risk":               cs["risk"],
                "highest_risk":       highest,
                "predicted_stage":    cs["stage"],
                "stage_confidence":   cs["stage_confidence"],
                "mitre_attack_id":    cs["mitre_attack_id"],
                "mitre_attack_name":  cs["mitre_attack_name"],
                "trajectory":         traj,
            },
        }

    return {"analysis_id": analysis_id, **summary}


# ── GET /analysis/{analysis_id}/metrics ──────────────────────────────────

@app.get("/analysis/{analysis_id}/metrics", tags=["Upload"])
def get_analysis_metrics(analysis_id: str) -> dict:
    """Return evaluation metrics for a labelled upload (or forecast-only notice)."""
    if analysis_id not in _analysis_store:
        raise HTTPException(status_code=404,
                            detail=f"Analysis ID '{analysis_id}' not found.")
    s = _analysis_store[analysis_id]
    if s["metrics"] is None:
        return {
            "analysis_id": analysis_id,
            "message": "Ground-truth labels not available; forecast-only mode.",
            "metrics": None,
        }
    return {"analysis_id": analysis_id, "metrics": s["metrics"]}


# ============================================================
# Internal helper: shape stored dict → AnalysisResponse
# ============================================================

def _to_analysis_response(s: dict) -> dict:
    return {
        "analysis_id":   s["analysis_id"],
        "status":        s["status"],
        "input":         s["input"],
        "current_state": s["current_state"],
        "forecast":      s["forecast"],
        "explainability":s["explainability"],
        "metrics":       s.get("metrics"),
    }

# ============================================================
# Prediction Runs — SQLite-backed history endpoints
# ============================================================
# These endpoints read from and write to data/cyber_defence.db via db.py.
# All existing /analysis/* endpoints are unchanged.
# ============================================================

# ── Pydantic response models ──────────────────────────────────────────────

class RunForecastStep(BaseModel):
    step:               int
    attack_probability: float
    risk_level:         str
    predicted_stage:    str
    stage_confidence:   float
    mitre_id:           Optional[str]
    mitre_technique:    Optional[str]

class RunExplainFeature(BaseModel):
    rank:        int
    feature_name: str
    sensitivity: float

class RunSummary(BaseModel):
    """Lightweight row returned by GET /runs."""
    run_id:             str
    created_at:         str
    source_type:        str          # 'uploaded' | 'sample'
    filename:           Optional[str]
    status:             str
    attack_probability: float
    risk_level:         str
    predicted_stage:    str
    stage_confidence:   float
    mitre_id:           Optional[str]
    mitre_technique:    Optional[str]
    file_type:          Optional[str]
    total_records:      Optional[int]
    total_windows:      Optional[int]
    ts_start:           Optional[str]
    ts_end:             Optional[str]

class RunDetail(RunSummary):
    """Full row returned by GET /runs/{run_id}."""
    forecast:       list[RunForecastStep]
    explainability: list[RunExplainFeature]
    metrics:        Optional[dict]


# ── GET /runs ─────────────────────────────────────────────────────────────

@app.get("/runs", response_model=list[RunSummary], tags=["Runs"])
def get_runs(limit: int = 50) -> list[RunSummary]:
    """
    Return the most recent prediction runs stored in SQLite.

    Each run corresponds to one uploaded telemetry analysis.
    Results are ordered newest-first (id DESC).
    The limit parameter caps the number of rows (default 50, max 500).

    This endpoint survives backend restarts — data comes from SQLite,
    not the in-memory _analysis_store.
    """
    limit = min(max(1, limit), 500)
    rows = list_runs(limit=limit)
    return [RunSummary(**r) for r in rows]


# ── GET /runs/{run_id} ────────────────────────────────────────────────────

@app.get("/runs/{run_id}", response_model=RunDetail, tags=["Runs"])
def get_run_detail(run_id: str) -> RunDetail:
    """
    Return the complete prediction result for one run, including
    all 5 forecast steps and the top feature sensitivity scores.

    Returns HTTP 404 when the run_id is not found in SQLite.
    """
    row = get_run(run_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Run '{run_id}' not found in the database.",
        )
    return RunDetail(
        **{k: v for k, v in row.items()
           if k not in ("forecast", "explainability", "metrics")},
        forecast       = [RunForecastStep(**f) for f in row["forecast"]],
        explainability = [RunExplainFeature(**e) for e in row["explainability"]],
        metrics        = row.get("metrics"),
    )


# ── GET /runs/{run_id}/forecast ───────────────────────────────────────────

@app.get("/runs/{run_id}/forecast",
         response_model=list[RunForecastStep], tags=["Runs"])
def get_run_forecast_steps(run_id: str) -> list[RunForecastStep]:
    """
    Return just the 5 autoregressive forecast steps for a stored run.

    Returns HTTP 404 when the run_id is not found in SQLite.
    """
    steps = get_run_forecast(run_id)
    if steps is None:
        raise HTTPException(
            status_code=404,
            detail=f"Run '{run_id}' not found in the database.",
        )
    return [RunForecastStep(**s) for s in steps]
