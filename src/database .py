"""
database.py
===========
SQLite persistence layer for
SIH "AI World Models for Predictive Cyber Defence".

All database operations are here.  No SQL appears in main.py.

Tables
------
  analyses        – one row per uploaded/analysed file
  network_states  – 10-second window states (44 features as JSON)
  forecasts       – K-step autoregressive predictions
  explanations    – feature ablation sensitivity results
  alerts          – email alert history

Architecture
------------
  Temporal Transformer
      ↓
  5-step forecast  +  explainability  +  risk
      ↓
  email_alert.py  →  alerts table
      ↓
  database.py  (persist everything)
      ↓
  FastAPI  →  Frontend

Security
--------
  - No credentials, secrets, or raw CSV content are stored.
  - database/cyber_defence.db is excluded from Git.
  - Each function opens its own connection (safe for FastAPI concurrency).
  - Parameterised SQL throughout — no string interpolation of user data.

Usage
-----
  from database import init_db, create_analysis, save_forecast, ...
  init_db()   # called once at FastAPI startup
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

log = logging.getLogger("database")

# ============================================================
# Database path
# ============================================================

ROOT    = Path(__file__).resolve().parent.parent
DB_DIR  = ROOT / "database"
DB_PATH = DB_DIR / "cyber_defence.db"

# SQLite busy timeout in milliseconds (helps with concurrent requests)
SQLITE_TIMEOUT_MS = 10_000


# ============================================================
# Connection context manager
# ============================================================

@contextmanager
def _get_conn() -> Generator[sqlite3.Connection, None, None]:
    """
    Yield a sqlite3 connection with foreign keys enabled.
    Opens and closes per-call — safe for concurrent FastAPI requests.
    """
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(DB_PATH),
        timeout      = SQLITE_TIMEOUT_MS / 1000,
        check_same_thread = False,
    )
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")  # better concurrency
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# Schema
# ============================================================

_DDL = """
-- ── analyses ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analyses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id     TEXT    NOT NULL UNIQUE,
    filename        TEXT    NOT NULL,
    upload_time     TEXT    NOT NULL,
    analysis_time   TEXT,
    status          TEXT    NOT NULL DEFAULT 'pending',
    total_records   INTEGER,
    total_windows   INTEGER,
    start_time      TEXT,
    end_time        TEXT,
    file_type       TEXT,
    has_ground_truth INTEGER DEFAULT 0,
    metrics_json    TEXT,
    error_message   TEXT
);

-- ── network_states ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS network_states (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id     TEXT    NOT NULL,
    window_index    INTEGER NOT NULL,
    window_start    TEXT,
    window_end      TEXT,
    record_count    INTEGER,
    state_json      TEXT    NOT NULL,
    FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id)
);

-- ── forecasts ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS forecasts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id         TEXT    NOT NULL,
    step                INTEGER NOT NULL,
    forecast_window     TEXT,
    attack_probability  REAL,
    risk_level          TEXT,
    predicted_stage     TEXT,
    stage_confidence    REAL,
    mitre_technique     TEXT,
    predicted_state_json TEXT,
    created_at          TEXT    NOT NULL,
    FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id)
);

-- ── explanations ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS explanations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id     TEXT    NOT NULL,
    forecast_step   INTEGER NOT NULL DEFAULT 1,
    feature_name    TEXT    NOT NULL,
    sensitivity     REAL    NOT NULL,
    rank            INTEGER NOT NULL,
    created_at      TEXT    NOT NULL,
    FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id)
);

-- ── alerts ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id         TEXT    NOT NULL,
    forecast_step       INTEGER NOT NULL DEFAULT 1,
    risk_level          TEXT    NOT NULL,
    attack_probability  REAL,
    predicted_stage     TEXT,
    receiver_email      TEXT,
    sent_at             TEXT    NOT NULL,
    status              TEXT    NOT NULL,
    error_message       TEXT,
    FOREIGN KEY (analysis_id) REFERENCES analyses(analysis_id)
);
"""

# Performance indexes
_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_analyses_analysis_id
    ON analyses(analysis_id);
CREATE INDEX IF NOT EXISTS idx_network_states_analysis_id
    ON network_states(analysis_id);
CREATE INDEX IF NOT EXISTS idx_forecasts_analysis_id
    ON forecasts(analysis_id);
CREATE INDEX IF NOT EXISTS idx_explanations_analysis_id
    ON explanations(analysis_id);
CREATE INDEX IF NOT EXISTS idx_alerts_analysis_id
    ON alerts(analysis_id);
"""


# ============================================================
# Public: initialise
# ============================================================

def init_db() -> None:
    """
    Create database/cyber_defence.db and all tables if they do not exist.
    Safe to call repeatedly — never drops data.
    """
    DB_DIR.mkdir(parents=True, exist_ok=True)
    with _get_conn() as conn:
        conn.executescript(_DDL)
        conn.executescript(_INDEXES)
    log.info("[db] Initialised: %s", DB_PATH)
    print(f"[db] Database ready: {DB_PATH}")


# ============================================================
# Helpers
# ============================================================

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _json(obj: Any) -> str:
    return json.dumps(obj, default=str)


# ============================================================
# analyses
# ============================================================

def create_analysis(
    analysis_id:  str,
    filename:     str,
    upload_time:  Optional[str] = None,
) -> None:
    """Insert a new analysis row with status='pending'."""
    sql = """
        INSERT OR IGNORE INTO analyses
            (analysis_id, filename, upload_time, status)
        VALUES (?, ?, ?, 'pending')
    """
    with _get_conn() as conn:
        conn.execute(sql, (analysis_id, filename, upload_time or _now()))


def update_analysis_status(
    analysis_id:   str,
    status:        str,
    analysis_time: Optional[str]  = None,
    total_records: Optional[int]  = None,
    total_windows: Optional[int]  = None,
    start_time:    Optional[str]  = None,
    end_time:      Optional[str]  = None,
    file_type:     Optional[str]  = None,
    has_ground_truth: bool        = False,
    metrics:       Optional[dict] = None,
    error_message: Optional[str]  = None,
) -> None:
    """Update analysis row after processing completes (or fails)."""
    sql = """
        UPDATE analyses SET
            status           = ?,
            analysis_time    = ?,
            total_records    = ?,
            total_windows    = ?,
            start_time       = ?,
            end_time         = ?,
            file_type        = ?,
            has_ground_truth = ?,
            metrics_json     = ?,
            error_message    = ?
        WHERE analysis_id = ?
    """
    with _get_conn() as conn:
        conn.execute(sql, (
            status,
            analysis_time or _now(),
            total_records,
            total_windows,
            start_time,
            end_time,
            file_type,
            1 if has_ground_truth else 0,
            _json(metrics) if metrics else None,
            error_message,
            analysis_id,
        ))


def get_analysis(analysis_id: str) -> Optional[dict]:
    """Return analysis row as dict, or None if not found."""
    sql = "SELECT * FROM analyses WHERE analysis_id = ?"
    with _get_conn() as conn:
        row = conn.execute(sql, (analysis_id,)).fetchone()
    if row is None:
        return None
    d = dict(row)
    if d.get("metrics_json"):
        try:
            d["metrics"] = json.loads(d["metrics_json"])
        except Exception:
            d["metrics"] = None
    return d


def list_analyses(limit: int = 100) -> list[dict]:
    """Return lightweight list of recent analyses."""
    sql = """
        SELECT analysis_id, filename, upload_time, analysis_time,
               status, total_records, total_windows, file_type,
               has_ground_truth
        FROM analyses
        ORDER BY id DESC
        LIMIT ?
    """
    with _get_conn() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return [dict(r) for r in rows]


# ============================================================
# network_states
# ============================================================

def save_network_state(
    analysis_id:  str,
    window_index: int,
    window_start: str,
    record_count: int,
    features:     dict[str, float],
    window_end:   Optional[str] = None,
) -> None:
    """Persist one 10-second network-state window."""
    sql = """
        INSERT INTO network_states
            (analysis_id, window_index, window_start, window_end,
             record_count, state_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    with _get_conn() as conn:
        conn.execute(sql, (
            analysis_id,
            window_index,
            window_start,
            window_end,
            record_count,
            _json(features),
        ))


def save_network_states_bulk(
    analysis_id: str,
    windows:     list[dict],
) -> None:
    """
    Persist all windows in one transaction.
    Each window dict must have:  window_index, window_start,
                                  record_count, features
    """
    sql = """
        INSERT INTO network_states
            (analysis_id, window_index, window_start, window_end,
             record_count, state_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    rows = [
        (
            analysis_id,
            w["window_index"],
            w.get("window_start", ""),
            w.get("window_end"),
            w.get("record_count", 0),
            _json(w.get("features", {})),
        )
        for w in windows
    ]
    with _get_conn() as conn:
        conn.executemany(sql, rows)


def get_network_states(analysis_id: str) -> list[dict]:
    """Return all network-state windows for an analysis."""
    sql = """
        SELECT window_index, window_start, window_end,
               record_count, state_json
        FROM network_states
        WHERE analysis_id = ?
        ORDER BY window_index
    """
    with _get_conn() as conn:
        rows = conn.execute(sql, (analysis_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["features"] = json.loads(d.pop("state_json", "{}"))
        except Exception:
            d["features"] = {}
        out.append(d)
    return out


# ============================================================
# forecasts
# ============================================================

def save_forecast(
    analysis_id:        str,
    step:               int,
    attack_probability: float,
    risk_level:         str,
    predicted_stage:    str,
    stage_confidence:   float,
    mitre_technique:    Optional[str]  = None,
    predicted_state:    Optional[dict] = None,
    forecast_window:    Optional[str]  = None,
) -> None:
    """Persist one autoregressive forecast step."""
    sql = """
        INSERT INTO forecasts
            (analysis_id, step, forecast_window, attack_probability,
             risk_level, predicted_stage, stage_confidence,
             mitre_technique, predicted_state_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with _get_conn() as conn:
        conn.execute(sql, (
            analysis_id,
            step,
            forecast_window,
            round(float(attack_probability), 6),
            risk_level,
            predicted_stage,
            round(float(stage_confidence), 6),
            mitre_technique,
            _json(predicted_state) if predicted_state else None,
            _now(),
        ))


def save_forecasts_bulk(
    analysis_id: str,
    forecast:    list[dict],
) -> None:
    """
    Persist all K forecast steps in one transaction.
    Each dict must have: step, attack_probability, risk, stage,
                          stage_confidence, mitre_attack_id,
                          mitre_attack_name
    """
    sql = """
        INSERT INTO forecasts
            (analysis_id, step, attack_probability, risk_level,
             predicted_stage, stage_confidence, mitre_technique, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    mitre_str = lambda f: (
        f"{f.get('mitre_attack_id')} - {f.get('mitre_attack_name')}"
        if f.get("mitre_attack_id") else None
    )
    rows = [
        (
            analysis_id,
            f["step"],
            round(float(f["attack_probability"]), 6),
            f["risk"],
            f["stage"],
            round(float(f["stage_confidence"]), 6),
            mitre_str(f),
            _now(),
        )
        for f in forecast
    ]
    with _get_conn() as conn:
        conn.executemany(sql, rows)


def get_forecasts(analysis_id: str) -> list[dict]:
    """Return all forecast steps for an analysis, ordered by step."""
    sql = """
        SELECT step, forecast_window, attack_probability, risk_level,
               predicted_stage, stage_confidence, mitre_technique, created_at
        FROM forecasts
        WHERE analysis_id = ?
        ORDER BY step
    """
    with _get_conn() as conn:
        rows = conn.execute(sql, (analysis_id,)).fetchall()
    return [dict(r) for r in rows]


# ============================================================
# explanations
# ============================================================

def save_explanations_bulk(
    analysis_id:  str,
    features:     list[dict],
    forecast_step: int = 1,
) -> None:
    """
    Persist feature ablation sensitivity results.
    Each dict must have: feature, sensitivity (and optionally rank).
    """
    sql = """
        INSERT INTO explanations
            (analysis_id, forecast_step, feature_name,
             sensitivity, rank, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    now = _now()
    rows = [
        (
            analysis_id,
            forecast_step,
            f["feature"],
            round(float(f["sensitivity"]), 8),
            i + 1,
            now,
        )
        for i, f in enumerate(features)
    ]
    with _get_conn() as conn:
        conn.executemany(sql, rows)


def get_explanations(
    analysis_id:  str,
    forecast_step: int = 1,
) -> list[dict]:
    """Return explainability results for an analysis step."""
    sql = """
        SELECT feature_name, sensitivity, rank, created_at
        FROM explanations
        WHERE analysis_id = ? AND forecast_step = ?
        ORDER BY rank
    """
    with _get_conn() as conn:
        rows = conn.execute(sql, (analysis_id, forecast_step)).fetchall()
    return [dict(r) for r in rows]


# ============================================================
# alerts
# ============================================================

def save_alert(
    analysis_id:        str,
    risk_level:         str,
    attack_probability: float,
    predicted_stage:    str,
    status:             str,
    receiver_email:     Optional[str] = None,
    forecast_step:      int           = 1,
    error_message:      Optional[str] = None,
) -> None:
    """
    Record the outcome of an email alert attempt.
    status must be one of: 'sent', 'failed', 'skipped', 'disabled'.
    Passwords and secrets are NEVER stored here.
    """
    sql = """
        INSERT INTO alerts
            (analysis_id, forecast_step, risk_level, attack_probability,
             predicted_stage, receiver_email, sent_at, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with _get_conn() as conn:
        conn.execute(sql, (
            analysis_id,
            forecast_step,
            risk_level,
            round(float(attack_probability), 6),
            predicted_stage,
            receiver_email,
            _now(),
            status,
            error_message,
        ))


def get_alerts(analysis_id: str) -> list[dict]:
    """Return alert history for an analysis."""
    sql = """
        SELECT forecast_step, risk_level, attack_probability,
               predicted_stage, receiver_email, sent_at, status, error_message
        FROM alerts
        WHERE analysis_id = ?
        ORDER BY id
    """
    with _get_conn() as conn:
        rows = conn.execute(sql, (analysis_id,)).fetchall()
    return [dict(r) for r in rows]


# ============================================================
# Convenience: persist a complete analysis result in one call
# ============================================================

def persist_analysis_result(
    analysis_id:  str,
    result:       dict,
    alert_status: Optional[str] = None,
    alert_error:  Optional[str] = None,
) -> None:
    """
    Atomically persist all outputs of _run_analysis().

    Uses a single database connection / transaction so either
    everything is saved or nothing is (on failure the caller should
    mark the analysis as 'failed').

    Parameters
    ----------
    result       : dict returned by _run_analysis()
    alert_status : 'sent' | 'failed' | 'skipped' | 'disabled' | None
    alert_error  : SMTP error message if status=='failed'
    """
    inp  = result["input"]
    cs   = result["current_state"]
    now  = _now()

    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(DB_PATH),
        timeout           = SQLITE_TIMEOUT_MS / 1000,
        check_same_thread = False,
    )
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("BEGIN")

        # ── 1. Create / update analysis row ───────────────────
        conn.execute(
            """
            INSERT OR IGNORE INTO analyses
                (analysis_id, filename, upload_time, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (analysis_id, inp["filename"], now),
        )
        conn.execute(
            """
            UPDATE analyses SET
                status           = 'completed',
                analysis_time    = ?,
                total_records    = ?,
                total_windows    = ?,
                start_time       = ?,
                end_time         = ?,
                file_type        = ?,
                has_ground_truth = ?,
                metrics_json     = ?
            WHERE analysis_id = ?
            """,
            (
                now,
                inp["records"],
                inp["time_windows"],
                inp["ts_start"],
                inp["ts_end"],
                inp["file_type"],
                0,                         # has_ground_truth updated below
                _json(result.get("metrics")) if result.get("metrics") else None,
                analysis_id,
            ),
        )

        # ── 2. Network states ──────────────────────────────────
        state_rows = [
            (
                analysis_id,
                w["window_index"],
                w.get("window_start", ""),
                None,
                w.get("record_count", 0),
                _json(w.get("features", {})),
            )
            for w in result.get("windows", [])
        ]
        if state_rows:
            conn.executemany(
                """
                INSERT INTO network_states
                    (analysis_id, window_index, window_start, window_end,
                     record_count, state_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                state_rows,
            )

        # ── 3. Forecasts ───────────────────────────────────────
        def _mitre(f: dict) -> Optional[str]:
            mid  = f.get("mitre_attack_id")
            name = f.get("mitre_attack_name")
            return f"{mid} - {name}" if mid else None

        fc_rows = [
            (
                analysis_id,
                f["step"],
                round(float(f["attack_probability"]), 6),
                f["risk"],
                f["stage"],
                round(float(f["stage_confidence"]), 6),
                _mitre(f),
                now,
            )
            for f in result.get("forecast", [])
        ]
        if fc_rows:
            conn.executemany(
                """
                INSERT INTO forecasts
                    (analysis_id, step, attack_probability, risk_level,
                     predicted_stage, stage_confidence, mitre_technique,
                     created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                fc_rows,
            )

        # ── 4. Explanations ────────────────────────────────────
        exp_rows = [
            (
                analysis_id,
                1,   # forecast_step 1 (latest sequence)
                e["feature"],
                round(float(e["sensitivity"]), 8),
                i + 1,
                now,
            )
            for i, e in enumerate(result.get("explainability", []))
        ]
        if exp_rows:
            conn.executemany(
                """
                INSERT INTO explanations
                    (analysis_id, forecast_step, feature_name,
                     sensitivity, rank, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                exp_rows,
            )

        # ── 5. Alert record ────────────────────────────────────
        if alert_status is not None:
            import os
            receiver = os.environ.get(
                "ALERT_RECEIVER_EMAIL",
                os.environ.get("ALERT_RECIPIENT", ""),
            )
            conn.execute(
                """
                INSERT INTO alerts
                    (analysis_id, forecast_step, risk_level,
                     attack_probability, predicted_stage,
                     receiver_email, sent_at, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    1,
                    cs["risk"],
                    cs["attack_probability"],
                    cs["stage"],
                    receiver,
                    now,
                    alert_status,
                    alert_error,
                ),
            )

        conn.commit()
        log.info("[db] Persisted analysis %s", analysis_id)

    except Exception as exc:
        conn.rollback()
        log.error("[db] Persist failed for %s: %s", analysis_id, exc)
        raise
    finally:
        conn.close()


def mark_analysis_failed(
    analysis_id:   str,
    error_message: str,
) -> None:
    """Mark an analysis as failed with a safe error message."""
    sql = """
        UPDATE analyses SET
            status        = 'failed',
            analysis_time = ?,
            error_message = ?
        WHERE analysis_id = ?
    """
    try:
        with _get_conn() as conn:
            conn.execute(sql, (_now(), error_message[:500], analysis_id))
    except Exception as exc:
        log.error("[db] Could not mark analysis %s as failed: %s", analysis_id, exc)


# ============================================================
# Quick self-test when run directly
# ============================================================

if __name__ == "__main__":
    import tempfile, os

    print("Running database self-test ...")
    # Use a temp DB so real data is not touched
    _orig = DB_PATH
    tmp   = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    # Monkey-patch for test
    import database as _self
    _self.DB_PATH = Path(tmp.name)

    try:
        init_db()
        create_analysis("test-001", "test.csv")
        update_analysis_status(
            "test-001", "completed",
            total_records=200, total_windows=6,
            start_time="2026-09-01 10:00:00",
            end_time  ="2026-09-01 10:01:00",
            file_type ="packet",
        )
        save_network_states_bulk("test-001", [{
            "window_index": 0, "window_start": "2026-09-01 10:00:00",
            "record_count": 34,
            "features": {"packet_count": 34.0, "flow_count": 34.0},
        }])
        save_forecasts_bulk("test-001", [{
            "step": 1, "attack_probability": 0.92, "risk": "CRITICAL",
            "stage": "Reconnaissance", "stage_confidence": 0.87,
            "mitre_attack_id": "T1595", "mitre_attack_name": "Active Scanning",
        }])
        save_explanations_bulk("test-001", [
            {"feature": "flow_count",              "sensitivity": 0.0158},
            {"feature": "packet_unique_protocols", "sensitivity": 0.0236},
        ])
        save_alert("test-001", "CRITICAL", 0.92, "Reconnaissance",
                   "sent", "defender@example.com")

        a = get_analysis("test-001")
        assert a and a["status"] == "completed", "analysis not found"
        assert len(get_network_states("test-001")) == 1
        assert len(get_forecasts("test-001"))      == 1
        assert len(get_explanations("test-001"))   == 2
        assert len(get_alerts("test-001"))         == 1

        print("All self-tests passed.")
    finally:
        _self.DB_PATH = _orig
        os.unlink(tmp.name)
