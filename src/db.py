"""
db.py
=====
SQLite persistence layer for
SIH "AI World Models for Predictive Cyber Defence".

All database operations live here.  No SQL appears in main.py.

Database file
-------------
  data/cyber_defence.db   (created automatically on first run)

Tables
------
  prediction_runs   – one row per analysis (uploaded file or sample)
  forecast_steps    – five forecast rows per run
  run_explanations  – top-N feature sensitivity rows per run
  run_files         – telemetry file metadata per run

Architecture
------------
  FastAPI (main.py)
      ↓  persist_run()
  db.py  →  data/cyber_defence.db
      ↑  list_runs() / get_run() / get_run_forecast()
  GET /runs  /runs/{run_id}  /runs/{run_id}/forecast

Security
--------
  - Passwords, SMTP credentials, API keys and raw CSV payload
    are NEVER stored.
  - Parameterised SQL throughout — no f-string interpolation of
    user-supplied values.
  - DB file is excluded from Git via .gitignore.
  - Each function opens and closes its own connection (safe for
    concurrent FastAPI requests via WAL journal mode).

Backward compatibility
----------------------
  - The existing _analysis_store dict in main.py is preserved.
  - All existing /analysis/* endpoints remain unchanged.
  - This module only *adds* persistence; it never removes data
    from the in-memory store.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

log = logging.getLogger("db")

# ── Database path ─────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parent.parent   # project root
DB_DIR  = ROOT / "data"
DB_PATH = DB_DIR / "cyber_defence.db"

SQLITE_TIMEOUT_S = 10.0   # seconds

# ── Connection context manager ────────────────────────────────────────────────

@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    """
    Yield a WAL-mode sqlite3 connection.
    Commits on clean exit, rolls back on exception.
    Thread-safe for FastAPI (new connection per call + WAL).
    """
    DB_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), timeout=SQLITE_TIMEOUT_S,
                          check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA journal_mode = WAL")
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

# ── DDL ───────────────────────────────────────────────────────────────────────

_DDL = """
-- ── prediction_runs ─────────────────────────────────────────────────────────
-- One row per analysis (uploaded telemetry or sample-based).
CREATE TABLE IF NOT EXISTS prediction_runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT    NOT NULL UNIQUE,   -- analysis_id / uuid hex
    created_at          TEXT    NOT NULL,
    source_type         TEXT    NOT NULL,          -- 'uploaded' | 'sample'
    filename            TEXT,                      -- null for sample runs
    status              TEXT    NOT NULL DEFAULT 'completed',
    -- Current-state prediction
    attack_probability  REAL    NOT NULL,
    risk_level          TEXT    NOT NULL,
    predicted_stage     TEXT    NOT NULL,
    stage_confidence    REAL    NOT NULL,
    mitre_id            TEXT,
    mitre_technique     TEXT,
    -- Telemetry metadata
    file_type           TEXT,                      -- 'packet' | 'flow'
    total_records       INTEGER,
    total_windows       INTEGER,
    ts_start            TEXT,
    ts_end              TEXT,
    -- Optional ground-truth eval metrics (JSON blob)
    metrics_json        TEXT
);

-- ── forecast_steps ───────────────────────────────────────────────────────────
-- Five autoregressive forecast steps per run.
CREATE TABLE IF NOT EXISTS forecast_steps (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT    NOT NULL,
    step                INTEGER NOT NULL,          -- 1..5
    attack_probability  REAL    NOT NULL,
    risk_level          TEXT    NOT NULL,
    predicted_stage     TEXT    NOT NULL,
    stage_confidence    REAL    NOT NULL,
    mitre_id            TEXT,
    mitre_technique     TEXT,
    FOREIGN KEY (run_id) REFERENCES prediction_runs(run_id)
        ON DELETE CASCADE
);

-- ── run_explanations ─────────────────────────────────────────────────────────
-- Feature ablation sensitivity results per run.
CREATE TABLE IF NOT EXISTS run_explanations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT    NOT NULL,
    rank            INTEGER NOT NULL,
    feature_name    TEXT    NOT NULL,
    sensitivity     REAL    NOT NULL,
    FOREIGN KEY (run_id) REFERENCES prediction_runs(run_id)
        ON DELETE CASCADE
);

-- ── run_files ────────────────────────────────────────────────────────────────
-- Telemetry file metadata (no raw content, no credentials).
CREATE TABLE IF NOT EXISTS run_files (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT    NOT NULL UNIQUE,
    filename            TEXT    NOT NULL,
    uploaded_at         TEXT    NOT NULL,
    row_count           INTEGER,
    processing_status   TEXT    NOT NULL DEFAULT 'completed',
    error_message       TEXT,
    FOREIGN KEY (run_id) REFERENCES prediction_runs(run_id)
        ON DELETE CASCADE
);
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_runs_run_id
    ON prediction_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_runs_created_at
    ON prediction_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fc_run_id
    ON forecast_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_exp_run_id
    ON run_explanations(run_id);
CREATE INDEX IF NOT EXISTS idx_files_run_id
    ON run_files(run_id);
"""

# ── Public: initialise ────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Create data/cyber_defence.db and all tables/indexes if they don't exist.
    Safe to call on every startup — never drops data.
    """
    DB_DIR.mkdir(parents=True, exist_ok=True)
    with _conn() as con:
        con.executescript(_DDL)
        con.executescript(_INDEXES)
    log.info("[db] ready: %s", DB_PATH)
    print(f"[db] Database ready: {DB_PATH}")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def _jdump(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    return json.dumps(obj, default=str)

# ── Write: persist a complete analysis result ─────────────────────────────────

def persist_run(
    result:      dict,
    source_type: str = "uploaded",   # 'uploaded' | 'sample'
) -> None:
    """
    Persist one complete analysis result from _run_analysis().

    Inserts into prediction_runs, forecast_steps, run_explanations,
    and run_files atomically (single transaction).  If the run_id
    already exists the call is a no-op (INSERT OR IGNORE).

    Parameters
    ----------
    result      : dict returned by _run_analysis() / stored in _analysis_store
    source_type : 'uploaded' for user-uploaded CSVs, 'sample' for demo runs
    """
    run_id = result["analysis_id"]
    cs     = result["current_state"]
    inp    = result["input"]
    now    = _now()

    mitre_id   = cs.get("mitre_attack_id")
    mitre_name = cs.get("mitre_attack_name")
    mitre_str  = f"{mitre_id} - {mitre_name}" if mitre_id else None

    with _conn() as con:
        # ── 1. prediction_runs ──────────────────────────────────
        con.execute(
            """
            INSERT OR IGNORE INTO prediction_runs (
                run_id, created_at, source_type, filename, status,
                attack_probability, risk_level, predicted_stage,
                stage_confidence, mitre_id, mitre_technique,
                file_type, total_records, total_windows,
                ts_start, ts_end, metrics_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                now,
                source_type,
                inp.get("filename"),
                result.get("status", "completed"),
                float(cs["attack_probability"]),
                cs["risk"],
                cs["stage"],
                float(cs["stage_confidence"]),
                mitre_id,
                mitre_str,
                inp.get("file_type"),
                inp.get("records"),
                inp.get("time_windows"),
                inp.get("ts_start"),
                inp.get("ts_end"),
                _jdump(result.get("metrics")),
            ),
        )

        # ── 2. forecast_steps ───────────────────────────────────
        fc_rows = []
        for f in result.get("forecast", []):
            fid   = f.get("mitre_attack_id")
            fname = f.get("mitre_attack_name")
            fc_rows.append((
                run_id,
                int(f["step"]),
                float(f["attack_probability"]),
                f["risk"],
                f["stage"],
                float(f["stage_confidence"]),
                fid,
                f"{fid} - {fname}" if fid else None,
            ))
        if fc_rows:
            con.executemany(
                """
                INSERT OR IGNORE INTO forecast_steps (
                    run_id, step, attack_probability, risk_level,
                    predicted_stage, stage_confidence, mitre_id, mitre_technique
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                fc_rows,
            )

        # ── 3. run_explanations ─────────────────────────────────
        exp_rows = [
            (run_id, i + 1, e["feature"], float(e["sensitivity"]))
            for i, e in enumerate(result.get("explainability", []))
        ]
        if exp_rows:
            con.executemany(
                """
                INSERT OR IGNORE INTO run_explanations
                    (run_id, rank, feature_name, sensitivity)
                VALUES (?,?,?,?)
                """,
                exp_rows,
            )

        # ── 4. run_files ────────────────────────────────────────
        filename = inp.get("filename")
        if filename and source_type == "uploaded":
            con.execute(
                """
                INSERT OR IGNORE INTO run_files
                    (run_id, filename, uploaded_at, row_count,
                     processing_status)
                VALUES (?,?,?,?,?)
                """,
                (
                    run_id,
                    filename,
                    now,
                    inp.get("records"),
                    result.get("status", "completed"),
                ),
            )

    log.info("[db] persisted run %s (%s)", run_id, source_type)

# ── Read: list recent runs ────────────────────────────────────────────────────

def list_runs(limit: int = 50) -> list[dict]:
    """
    Return a lightweight list of the most recent prediction runs.
    Does NOT include forecast steps or explanations (use get_run for that).
    """
    sql = """
        SELECT
            run_id, created_at, source_type, filename, status,
            attack_probability, risk_level, predicted_stage,
            stage_confidence, mitre_id, mitre_technique,
            file_type, total_records, total_windows,
            ts_start, ts_end
        FROM prediction_runs
        ORDER BY id DESC
        LIMIT ?
    """
    with _conn() as con:
        rows = con.execute(sql, (limit,)).fetchall()
    return [dict(r) for r in rows]

# ── Read: single run ──────────────────────────────────────────────────────────

def get_run(run_id: str) -> Optional[dict]:
    """
    Return one prediction run with its forecast steps and top features.
    Returns None if not found.
    """
    with _conn() as con:
        run_row = con.execute(
            "SELECT * FROM prediction_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if run_row is None:
            return None

        fc_rows = con.execute(
            """
            SELECT step, attack_probability, risk_level,
                   predicted_stage, stage_confidence,
                   mitre_id, mitre_technique
            FROM forecast_steps
            WHERE run_id = ?
            ORDER BY step
            """,
            (run_id,),
        ).fetchall()

        exp_rows = con.execute(
            """
            SELECT rank, feature_name, sensitivity
            FROM run_explanations
            WHERE run_id = ?
            ORDER BY rank
            """,
            (run_id,),
        ).fetchall()

    run = dict(run_row)
    if run.get("metrics_json"):
        try:
            run["metrics"] = json.loads(run.pop("metrics_json"))
        except Exception:
            run.pop("metrics_json", None)
            run["metrics"] = None
    else:
        run.pop("metrics_json", None)
        run["metrics"] = None

    run["forecast"]      = [dict(r) for r in fc_rows]
    run["explainability"] = [dict(r) for r in exp_rows]
    return run

# ── Read: forecast only ───────────────────────────────────────────────────────

def get_run_forecast(run_id: str) -> Optional[list[dict]]:
    """
    Return the forecast steps for one run, or None if the run doesn't exist.
    """
    with _conn() as con:
        exists = con.execute(
            "SELECT 1 FROM prediction_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if not exists:
            return None
        rows = con.execute(
            """
            SELECT step, attack_probability, risk_level,
                   predicted_stage, stage_confidence,
                   mitre_id, mitre_technique
            FROM forecast_steps
            WHERE run_id = ?
            ORDER BY step
            """,
            (run_id,),
        ).fetchall()
    return [dict(r) for r in rows]

# ── Restore: load DB runs into _analysis_store format ────────────────────────

def run_to_analysis_store_dict(run_id: str) -> Optional[dict]:
    """
    Reconstruct the _analysis_store dict shape from a persisted run so
    that GET /analysis/{id}/* endpoints can serve it after a backend restart.

    Returns None if run_id is not in the database.
    The returned dict matches exactly what _run_analysis() produces.
    """
    run = get_run(run_id)
    if run is None:
        return None

    current_state = {
        "stage":              run["predicted_stage"],
        "attack_probability": run["attack_probability"],
        "risk":               run["risk_level"],
        "stage_confidence":   run["stage_confidence"],
        "mitre_attack_id":    run["mitre_id"],
        "mitre_attack_name":  (
            run["mitre_technique"].split(" - ", 1)[1]
            if run.get("mitre_technique") and " - " in run["mitre_technique"]
            else run.get("mitre_technique")
        ),
    }

    forecast = []
    for f in run["forecast"]:
        mitre_name = (
            f["mitre_technique"].split(" - ", 1)[1]
            if f.get("mitre_technique") and " - " in f["mitre_technique"]
            else f.get("mitre_technique")
        )
        forecast.append({
            "step":               f["step"],
            "attack_probability": f["attack_probability"],
            "risk":               f["risk_level"],
            "stage":              f["predicted_stage"],
            "stage_confidence":   f["stage_confidence"],
            "mitre_attack_id":    f["mitre_id"],
            "mitre_attack_name":  mitre_name,
        })

    explainability = [
        {"feature": e["feature_name"], "sensitivity": e["sensitivity"]}
        for e in run["explainability"]
    ]

    return {
        "analysis_id":   run_id,
        "status":        run.get("status", "completed"),
        "upload_path":   "",
        "input": {
            "filename":     run.get("filename") or "",
            "records":      run.get("total_records") or 0,
            "time_windows": run.get("total_windows") or 0,
            "ts_start":     run.get("ts_start") or "",
            "ts_end":       run.get("ts_end") or "",
            "file_type":    run.get("file_type") or "",
        },
        "current_state":   current_state,
        "forecast":        forecast,
        "explainability":  explainability,
        "metrics":         run.get("metrics"),
        "windows":         [],           # window states not stored in this table
        "entity_summary":  None,
    }

# ── Restore all runs into memory store on startup ─────────────────────────────

def restore_all_runs(analysis_store: dict) -> int:
    """
    Load all persisted runs from SQLite into the in-memory _analysis_store.
    Called once at FastAPI startup so existing /analysis/* endpoints work
    immediately after a backend restart.

    Returns the number of runs restored.
    """
    try:
        runs = list_runs(limit=500)
    except Exception as exc:
        log.warning("[db] restore_all_runs skipped: %s", exc)
        return 0

    count = 0
    for r in runs:
        rid = r["run_id"]
        if rid not in analysis_store:
            rebuilt = run_to_analysis_store_dict(rid)
            if rebuilt:
                analysis_store[rid] = rebuilt
                count += 1
    log.info("[db] restored %d runs into memory store", count)
    return count
