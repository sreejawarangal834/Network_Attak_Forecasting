"""
tests/test_pipeline.py
======================
Pytest tests for upload validation and telemetry pipeline.
Run from project root:  pytest tests/ -v
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ── ensure src/ is importable ─────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from upload_validator import (
    validate_upload, validate_bytes,
    PACKET_REQUIRED_COLS, FLOW_REQUIRED_COLS,
    MAX_FILE_BYTES,
)
from telemetry_pipeline import (
    process_uploaded_csv, FEATURE_COLUMNS, SEQUENCE_LENGTH,
)
from alert_manager import calculate_risk_level
from mitre_mapping import get_mitre_mapping, format_mitre

# ============================================================
# Fixtures — synthetic data
# ============================================================

NPZ_PATH = Path("data/simulated/fused_train_val_test.npz")

@pytest.fixture(scope="session")
def scaler():
    d = np.load(NPZ_PATH, allow_pickle=True)
    return d["scaler_mean"], d["scaler_scale"]

@pytest.fixture
def valid_packet_csv(tmp_path) -> Path:
    """200 rows spread across ~60 seconds → 6 windows, enough for 5-window sequences."""
    rng = np.random.default_rng(0)
    n   = 200
    # 300ms spacing → 60 s total → 6 windows of 10 s each
    ts  = pd.date_range("2026-09-01 10:00:00", periods=n, freq="300ms")
    df  = pd.DataFrame({
        "timestamp":   ts.astype(str),
        "src_ip":     ["10.0.1.1"] * n,
        "dst_ip":     ["10.0.2.1"] * n,
        "src_port":   rng.integers(1024, 65535, n),
        "dst_port":   rng.integers(80, 8080, n),
        "protocol":   ["TCP"] * n,
        "packet_size":  rng.integers(60, 1400, n),
        "ttl":          rng.integers(50, 128, n),
        "tcp_window":   rng.integers(8192, 65535, n),
        "syn":  rng.integers(0, 2, n),
        "ack":  rng.integers(0, 2, n),
        "rst":  rng.integers(0, 2, n),
        "fin":  rng.integers(0, 2, n),
        "attack_type": ["Benign"] * n,
        "label":       [0] * n,
    })
    p = tmp_path / "packets.csv"
    df.to_csv(p, index=False)
    return p


@pytest.fixture
def valid_flow_csv(tmp_path) -> Path:
    """200 rows spread across ~60 seconds → 6 windows."""
    rng = np.random.default_rng(1)
    n   = 200
    ts  = pd.date_range("2026-09-01 10:00:00", periods=n, freq="300ms")
    df  = pd.DataFrame({
        "timestamp":          ts.astype(str),
        "src_ip":            ["10.0.1.1"] * n,
        "dst_ip":            ["10.0.2.1"] * n,
        "src_port":          rng.integers(1024, 65535, n),
        "dst_port":          rng.integers(80, 8080, n),
        "protocol":          ["TCP"] * n,
        "flow_duration":     rng.uniform(10, 3000, n),
        "total_fwd_packets": rng.integers(1, 20, n),
        "total_bwd_packets": rng.integers(0, 15, n),
        "fwd_bytes":         rng.uniform(100, 50000, n),
        "bwd_bytes":         rng.uniform(0, 40000, n),
        "total_bytes":       rng.uniform(200, 90000, n),
        "flow_bytes_per_sec":   rng.uniform(100, 100000, n),
        "flow_packets_per_sec": rng.uniform(1, 200, n),
        "flow_iat_mean":     rng.uniform(0.01, 1.0, n),
        "flow_iat_std":      rng.uniform(0.005, 0.5, n),
        "packet_length_mean":rng.uniform(60, 1400, n),
        "packet_length_std": rng.uniform(5, 300, n),
        "fwd_packets_per_sec":  rng.uniform(1, 100, n),
        "bwd_packets_per_sec":  rng.uniform(0, 80, n),
        "down_up_ratio":     rng.uniform(0, 5, n),
        "syn_flag_count":    rng.integers(0, 5, n),
        "ack_flag_count":    rng.integers(0, 20, n),
        "rst_flag_count":    rng.integers(0, 3, n),
        "fin_flag_count":    rng.integers(0, 3, n),
        "attack_stage":      ["Benign"] * n,
        "label":             [0] * n,
    })
    p = tmp_path / "flows.csv"
    df.to_csv(p, index=False)
    return p


# ============================================================
# 1. Valid CSV
# ============================================================

def test_valid_packet_csv(valid_packet_csv):
    result = validate_upload(valid_packet_csv)
    assert result.valid, result.errors
    assert result.file_type == "packet"
    assert result.rows >= 50


def test_valid_flow_csv(valid_flow_csv):
    result = validate_upload(valid_flow_csv)
    assert result.valid, result.errors
    assert result.file_type == "flow"


# ============================================================
# 2. Empty CSV
# ============================================================

def test_empty_csv(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_bytes(b"")
    result = validate_upload(p)
    assert not result.valid
    assert any("empty" in e.message.lower() for e in result.errors)


# ============================================================
# 3. Missing required column
# ============================================================

def test_missing_column(tmp_path):
    df = pd.DataFrame({"timestamp": ["2026-01-01"], "x": [1]})
    p  = tmp_path / "bad.csv"
    df.to_csv(p, index=False)
    result = validate_upload(p)
    assert not result.valid


# ============================================================
# 4. Invalid timestamp
# ============================================================

def test_invalid_timestamp(tmp_path, valid_packet_csv):
    df  = pd.read_csv(valid_packet_csv)
    df["timestamp"] = "not_a_date"
    p   = tmp_path / "bad_ts.csv"
    df.to_csv(p, index=False)
    result = validate_upload(p)
    assert not result.valid or any(
        "timestamp" in e.field for e in result.errors
    )


# ============================================================
# 5. Insufficient temporal windows
# ============================================================

def test_insufficient_windows(tmp_path, scaler, valid_packet_csv):
    # All records in a single 10-second window → only 1 window
    df = pd.read_csv(valid_packet_csv)
    df["timestamp"] = "2026-09-01 10:00:00"
    p  = tmp_path / "single_window.csv"
    df.to_csv(p, index=False)
    m, s = scaler
    with pytest.raises(ValueError, match="[Ww]indow"):
        process_uploaded_csv(p, m, s)


# ============================================================
# 6. Invalid numeric values
# ============================================================

def test_invalid_numeric(tmp_path, valid_packet_csv):
    df = pd.read_csv(valid_packet_csv)
    df["packet_size"] = "not_a_number"
    p  = tmp_path / "bad_num.csv"
    df.to_csv(p, index=False)
    result = validate_upload(p)
    assert not result.valid


# ============================================================
# 7. 10-second window creation
# ============================================================

def test_window_creation(scaler, valid_packet_csv):
    m, s = scaler
    pipe = process_uploaded_csv(valid_packet_csv, m, s)
    assert pipe.time_windows >= SEQUENCE_LENGTH
    assert "window_start" in pipe.states_df.columns


# ============================================================
# 8. Correct 44-feature ordering
# ============================================================

def test_feature_ordering(scaler, valid_packet_csv):
    m, s = scaler
    pipe = process_uploaded_csv(valid_packet_csv, m, s)
    assert pipe.feature_columns == FEATURE_COLUMNS
    assert pipe.states_scaled.shape[1] == 44


# ============================================================
# 9. Scaler usage — values are standardised (mean ≈ 0, std ≈ 1 for training data)
# ============================================================

def test_scaler_applied(scaler, valid_packet_csv):
    m, s = scaler
    pipe = process_uploaded_csv(valid_packet_csv, m, s)
    # Check scaler was NOT refit — mean/scale must match training NPZ
    assert np.allclose(pipe.scaler_mean,  m)
    assert np.allclose(pipe.scaler_scale, s)


# ============================================================
# 10. 5-step autoregressive forecast shape
# ============================================================

def test_sequence_shape(scaler, valid_packet_csv):
    m, s = scaler
    pipe = process_uploaded_csv(valid_packet_csv, m, s)
    assert pipe.sequences.shape[1] == SEQUENCE_LENGTH
    assert pipe.sequences.shape[2] == 44
    assert pipe.sequences.dtype   == np.float32


# ============================================================
# 11. Risk level calculation
# ============================================================

@pytest.mark.parametrize("stage,prob,expected", [
    ("Benign",            0.95, "NONE"),
    ("Reconnaissance",    0.45, "LOW"),
    ("BruteForce",        0.62, "MEDIUM"),
    ("LateralMovement",   0.82, "HIGH"),
    ("CommandAndControl", 0.97, "CRITICAL"),
])
def test_risk_levels(stage, prob, expected):
    assert calculate_risk_level(prob, stage) == expected


# ============================================================
# 12. MITRE mapping
# ============================================================

def test_mitre_mapping():
    assert get_mitre_mapping("Reconnaissance")["mitre_attack_id"]   == "T1595"
    assert get_mitre_mapping("BruteForce")["mitre_attack_id"]       == "T1110"
    assert get_mitre_mapping("LateralMovement")["mitre_attack_id"]  == "T1021"
    assert get_mitre_mapping("CommandAndControl")["mitre_attack_id"]== "T1071"
    assert get_mitre_mapping("Benign")["mitre_attack_id"]           is None


def test_format_mitre():
    assert format_mitre("Reconnaissance") == "T1595 - Active Scanning"
    assert format_mitre("Benign")         == "None"


# ============================================================
# 13. Label detection
# ============================================================

def test_label_detection(valid_packet_csv):
    result = validate_upload(valid_packet_csv)
    assert result.has_labels
    assert result.label_col in ("label", "attack_type")


# ============================================================
# 14. No-label forecast mode
# ============================================================

def test_no_label_forecast(tmp_path, scaler):
    """CSV without label columns → has_labels=False, pipeline still works."""
    rng = np.random.default_rng(2)
    n   = 200
    # 300ms spacing → 60 s → 6 windows
    ts  = pd.date_range("2026-09-01 10:00:00", periods=n, freq="300ms")
    df  = pd.DataFrame({
        "timestamp":  ts.astype(str),
        "src_ip":    ["10.0.1.1"] * n,
        "dst_ip":    ["10.0.2.1"] * n,
        "src_port":  rng.integers(1024, 65535, n),
        "dst_port":  rng.integers(80, 8080, n),
        "protocol":  ["TCP"] * n,
        "packet_size":  rng.integers(60, 1400, n),
        "ttl":          rng.integers(50, 128, n),
        "tcp_window":   rng.integers(8192, 65535, n),
        "syn": rng.integers(0, 2, n),
        "ack": rng.integers(0, 2, n),
        "rst": rng.integers(0, 2, n),
        "fin": rng.integers(0, 2, n),
    })
    p = tmp_path / "no_labels.csv"
    df.to_csv(p, index=False)
    m, s = scaler
    pipe = process_uploaded_csv(p, m, s)
    assert not pipe.has_labels
    assert pipe.sequences.shape[2] == 44


# ============================================================
# 15. File too large
# ============================================================

def test_file_too_large(tmp_path):
    p = tmp_path / "big.csv"
    p.write_bytes(b"a" * (MAX_FILE_BYTES + 1))
    result = validate_upload(p, max_bytes=MAX_FILE_BYTES)
    assert not result.valid
    assert any("size" in e.field for e in result.errors)


# ============================================================
# 16. Unsupported file type
# ============================================================

def test_unsupported_extension():
    result = validate_bytes(b"dummy content", "traffic.pcap")
    assert not result.valid
    assert "PCAP" in result.errors[0].message


# ============================================================
# 17. validate_bytes quick check
# ============================================================

def test_validate_bytes_ok():
    content = b"timestamp,packet_size\n2026-01-01,64\n"
    result  = validate_bytes(content, "test.csv")
    assert result.valid   # passes quick screen (full schema check is in validate_upload)
