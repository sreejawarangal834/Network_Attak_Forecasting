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

    print(f"[startup] model loaded  : {MODEL_FILE.name}  ({state.n_params:,} params)")
    print(f"[startup] dataset loaded: {DATA_FILE.name}  ({len(state.X_test)} test samples)")
    print(f"[startup] device        : {DEVICE}")

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
        "current_state":  current_state,
        "forecast":       forecast,
        "explainability": explainability,
        "metrics":        metrics,
        "windows":        windows_out,
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
