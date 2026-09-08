"""
upload_validator.py
===================
File and schema validation for uploaded CSV telemetry files.
SIH "AI World Models for Predictive Cyber Defence".

Validates:
  A. File extension     — .csv only
  B. File size          — configurable max (default 50 MB)
  C. CSV readability    — detects malformed CSV
  D. Empty file         — rejects files with no data rows
  E. Required columns   — checks for columns needed to build the 44 features
  F. Timestamp column   — must be parseable as datetime
  G. Numeric columns    — key numeric columns must be parseable
  H. Minimum rows       — at least MIN_ROWS records to form ≥5 windows

Returns structured ValidationResult objects with clear error messages.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

# ============================================================
# Configuration
# ============================================================

MAX_FILE_BYTES: int = 50 * 1024 * 1024   # 50 MB — configurable
MIN_ROWS:       int = 50                  # minimum records to attempt windowing
ALLOWED_EXTENSIONS = {".csv"}

# ============================================================
# Packet telemetry required columns
# (needed by build_fused_states packet aggregation)
# ============================================================

PACKET_REQUIRED_COLS = [
    "timestamp",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "protocol",
    "packet_size",
    "ttl",
    "tcp_window",
    "syn",
    "ack",
    "rst",
    "fin",
]

# ============================================================
# Flow telemetry required columns
# (needed by build_fused_states flow aggregation)
# ============================================================

FLOW_REQUIRED_COLS = [
    "timestamp",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "protocol",
    "flow_duration",
    "total_fwd_packets",
    "total_bwd_packets",
    "fwd_bytes",
    "bwd_bytes",
    "total_bytes",
    "flow_bytes_per_sec",
    "flow_packets_per_sec",
    "flow_iat_mean",
    "flow_iat_std",
    "packet_length_mean",
    "packet_length_std",
    "fwd_packets_per_sec",
    "bwd_packets_per_sec",
    "down_up_ratio",
    "syn_flag_count",
    "ack_flag_count",
    "rst_flag_count",
    "fin_flag_count",
]

# Numeric columns that must be numeric
PACKET_NUMERIC_COLS = [
    "packet_size", "ttl", "tcp_window",
    "syn", "ack", "rst", "fin",
    "src_port", "dst_port",
]

FLOW_NUMERIC_COLS = [
    "flow_duration", "total_fwd_packets", "total_bwd_packets",
    "fwd_bytes", "bwd_bytes", "total_bytes",
    "flow_bytes_per_sec", "flow_packets_per_sec",
    "flow_iat_mean", "flow_iat_std",
    "packet_length_mean", "packet_length_std",
    "fwd_packets_per_sec", "bwd_packets_per_sec",
    "down_up_ratio", "syn_flag_count", "ack_flag_count",
    "rst_flag_count", "fin_flag_count",
]

# Optional ground-truth columns (presence triggers evaluation mode)
LABEL_COLS = ["label", "attack_type", "attack_stage"]

# ============================================================
# Data structures
# ============================================================

@dataclass
class ValidationError:
    field:   str
    message: str


@dataclass
class ValidationResult:
    valid:       bool
    file_type:   Optional[str]        = None   # "packet" | "flow" | "unknown"
    rows:        int                  = 0
    columns:     list[str]            = field(default_factory=list)
    has_labels:  bool                 = False
    label_col:   Optional[str]        = None
    errors:      list[ValidationError] = field(default_factory=list)
    warnings:    list[str]            = field(default_factory=list)

    def add_error(self, field_name: str, msg: str) -> None:
        self.errors.append(ValidationError(field=field_name, message=msg))
        self.valid = False

    def to_dict(self) -> dict:
        return {
            "valid":      self.valid,
            "file_type":  self.file_type,
            "rows":       self.rows,
            "columns":    self.columns,
            "has_labels": self.has_labels,
            "errors":     [{"field": e.field, "message": e.message}
                           for e in self.errors],
            "warnings":   self.warnings,
        }


# ============================================================
# Public API
# ============================================================

def validate_upload(
    file_path: Path,
    max_bytes: int = MAX_FILE_BYTES,
) -> ValidationResult:
    """
    Full validation pipeline for an uploaded CSV file.

    Parameters
    ----------
    file_path : path to the saved upload
    max_bytes : maximum allowed file size in bytes

    Returns
    -------
    ValidationResult — .valid is True only if all checks pass.
    """
    result = ValidationResult(valid=True)

    # ── A. Extension ──────────────────────────────────────────
    suffix = Path(file_path).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        result.add_error(
            "file_extension",
            f"Unsupported file type '{suffix}'. "
            "Only .csv files are accepted. "
            "PCAP upload is not currently supported; "
            "upload a compatible CSV telemetry file.",
        )
        return result

    # ── B. File size ──────────────────────────────────────────
    size = Path(file_path).stat().st_size
    if size == 0:
        result.add_error("file_size", "Uploaded file is empty.")
        return result
    if size > max_bytes:
        result.add_error(
            "file_size",
            f"File size {size:,} bytes exceeds maximum "
            f"{max_bytes:,} bytes ({max_bytes // 1024 // 1024} MB).",
        )
        return result

    # ── C. CSV readability ────────────────────────────────────
    try:
        df = pd.read_csv(file_path, nrows=5)
    except Exception as exc:
        result.add_error("csv_parse", f"Cannot parse CSV: {exc}")
        return result

    # ── D. Empty rows ─────────────────────────────────────────
    if len(df) == 0:
        result.add_error("rows", "CSV file has no data rows (header only).")
        return result

    # Read full file for remaining checks
    try:
        df = pd.read_csv(file_path, low_memory=False)
    except Exception as exc:
        result.add_error("csv_parse", f"Cannot fully parse CSV: {exc}")
        return result

    result.rows    = len(df)
    result.columns = list(df.columns)
    cols_lower     = {c.lower(): c for c in df.columns}

    # ── Detect file type ──────────────────────────────────────
    pkt_present  = _cols_present(PACKET_REQUIRED_COLS, cols_lower)
    flow_present = _cols_present(FLOW_REQUIRED_COLS,   cols_lower)

    if flow_present >= len(FLOW_REQUIRED_COLS) - 2:
        result.file_type = "flow"
        required = FLOW_REQUIRED_COLS
        numeric  = FLOW_NUMERIC_COLS
    elif pkt_present >= len(PACKET_REQUIRED_COLS) - 2:
        result.file_type = "packet"
        required = PACKET_REQUIRED_COLS
        numeric  = PACKET_NUMERIC_COLS
    else:
        result.file_type = "unknown"
        # Report what was missing
        missing_pkt  = [c for c in PACKET_REQUIRED_COLS if c not in cols_lower]
        missing_flow = [c for c in FLOW_REQUIRED_COLS   if c not in cols_lower]
        result.add_error(
            "schema",
            "CSV does not match packet or flow telemetry schema. "
            f"Missing packet columns: {missing_pkt[:5]}. "
            f"Missing flow columns: {missing_flow[:5]}. "
            "Upload a simulated_packets.csv or simulated_flow.csv "
            "compatible file.",
        )
        return result

    # ── E. Required columns ───────────────────────────────────
    missing = [c for c in required if c not in cols_lower]
    if missing:
        result.add_error(
            "required_columns",
            f"Missing required columns: {missing}",
        )

    # ── F. Timestamp ──────────────────────────────────────────
    ts_col = cols_lower.get("timestamp")
    if ts_col is None:
        result.add_error(
            "timestamp",
            "Required 'timestamp' column is missing.",
        )
    else:
        try:
            sample_ts = pd.to_datetime(df[ts_col].dropna().head(10),
                                       format="mixed", errors="coerce")
            n_bad = sample_ts.isna().sum()
            if n_bad > 5:
                result.add_error(
                    "timestamp",
                    f"Timestamp column '{ts_col}' has many unparseable values.",
                )
        except Exception as exc:
            result.add_error("timestamp", f"Cannot parse timestamp column: {exc}")

    # ── G. Numeric columns ────────────────────────────────────
    for col in numeric:
        actual = cols_lower.get(col)
        if actual is None:
            continue
        try:
            pd.to_numeric(df[actual].dropna().head(100), errors="raise")
        except Exception:
            result.add_error(
                col,
                f"Column '{actual}' contains non-numeric values.",
            )

    # ── H. Minimum rows ───────────────────────────────────────
    if result.rows < MIN_ROWS:
        result.add_error(
            "rows",
            f"File has only {result.rows} rows; "
            f"at least {MIN_ROWS} records are required to form "
            "5 temporal windows for forecasting.",
        )

    # ── Optional: detect label columns ────────────────────────
    for lc in LABEL_COLS:
        if lc in cols_lower:
            result.has_labels = True
            result.label_col  = cols_lower[lc]
            break

    return result


def validate_bytes(
    content: bytes,
    filename: str,
    max_bytes: int = MAX_FILE_BYTES,
) -> ValidationResult:
    """
    Validate uploaded file content directly from bytes
    (before saving to disk).  Fast pre-screen.
    """
    result = ValidationResult(valid=True)
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        result.add_error(
            "file_extension",
            f"Unsupported file type '{suffix}'. Only .csv files are accepted. "
            "PCAP upload is not currently supported.",
        )
        return result

    if len(content) == 0:
        result.add_error("file_size", "Uploaded file is empty.")
        return result

    if len(content) > max_bytes:
        result.add_error(
            "file_size",
            f"File size {len(content):,} bytes exceeds "
            f"maximum {max_bytes:,} bytes.",
        )
        return result

    try:
        pd.read_csv(io.BytesIO(content), nrows=3)
    except Exception as exc:
        result.add_error("csv_parse", f"Cannot parse CSV: {exc}")

    return result


# ============================================================
# Internal helpers
# ============================================================

def _cols_present(required: list[str], available: dict) -> int:
    """Return count of required columns found in available (case-insensitive)."""
    return sum(1 for c in required if c in available)
