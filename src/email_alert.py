"""
email_alert.py
==============
Lightweight email alert module for
SIH "AI World Models for Predictive Cyber Defence".

Sends a security alert email when the predicted risk level is HIGH or CRITICAL.
Uses only Python standard-library modules (smtplib, email, os).

Credentials — environment variables
------------------------------------
SMTP_EMAIL            : Gmail address used to SEND the alert
SMTP_PASSWORD         : Gmail App Password (NOT your normal login password)
ALERT_RECEIVER_EMAIL  : Address that RECEIVES the alert
SMTP_HOST             : SMTP server  (default: smtp.gmail.com)
SMTP_PORT             : SMTP port    (default: 587)

PowerShell setup (current session only — never commit these):
    $env:SMTP_EMAIL           = "sender@gmail.com"
    $env:SMTP_PASSWORD        = "xxxx xxxx xxxx xxxx"
    $env:ALERT_RECEIVER_EMAIL = "defender@example.com"

Remove from session:
    Remove-Item Env:SMTP_EMAIL
    Remove-Item Env:SMTP_PASSWORD
    Remove-Item Env:ALERT_RECEIVER_EMAIL

IMPORTANT
---------
- Only HIGH and CRITICAL risk levels trigger an email.
- LOW and MEDIUM are silently skipped.
- Missing credentials print a warning; prediction continues normally.
- SMTP failures print a warning; prediction continues normally.
- Passwords are NEVER printed or logged.
- This module does NOT recalculate risk — it receives the already-computed
  risk level from predict.py / alert_manager.py.
"""

from __future__ import annotations

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

# ── Load .env file automatically ─────────────────────────────────────────────
# Looks for .env in the project root (one level above src/).
# Falls back silently if python-dotenv is not installed or .env doesn't exist.
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=_env_path, override=False)
except ImportError:
    pass  # python-dotenv not installed — rely on OS environment variables

# ============================================================
# Risk levels that trigger an alert (imported from alert_manager
# to avoid duplicating the thresholds)
# ============================================================

try:
    from alert_manager import RISK_HIGH, RISK_CRITICAL, DEFENDER_RECOMMENDATIONS
except ImportError:
    # Fallback if running standalone
    RISK_HIGH      = "HIGH"
    RISK_CRITICAL  = "CRITICAL"
    DEFENDER_RECOMMENDATIONS: dict[str, str] = {
        "Benign":            "No immediate defensive action indicated.",
        "Reconnaissance":    "Investigate scanning activity, unusual source diversity, and targeted ports.",
        "BruteForce":        "Investigate repeated authentication failures and suspicious login attempts.",
        "LateralMovement":   "Inspect internal remote-service activity and authentication behaviour.",
        "CommandAndControl": "Investigate suspicious outbound communications and unusual application-layer protocols.",
    }

ALERT_RISK_LEVELS = {RISK_HIGH, RISK_CRITICAL}

# ============================================================
# SMTP configuration reader
# ============================================================

def _get_config() -> dict:
    """Read credentials from environment variables. Never returns password in logs."""
    return {
        "host":     os.environ.get("SMTP_HOST",  "smtp.gmail.com"),
        "port":     int(os.environ.get("SMTP_PORT", "587")),
        "sender":   os.environ.get("SMTP_EMAIL",           "").strip(),
        "password": os.environ.get("SMTP_PASSWORD",        "").strip(),
        "receiver": os.environ.get("ALERT_RECEIVER_EMAIL", "").strip(),
    }


def is_configured() -> bool:
    """Return True if all required credentials are present."""
    cfg = _get_config()
    return bool(cfg["sender"] and cfg["password"] and cfg["receiver"])


# ============================================================
# Email content builder
# ============================================================

def _build_email(
    risk_level:         str,
    attack_probability: float,
    predicted_stage:    str,
    stage_confidence:   float,
    mitre_technique:    str,
    top_features:       list[str],
    current_stage:      Optional[str] = None,
    sample_id:          Optional[int] = None,
) -> tuple[str, str]:
    """
    Build (subject, body) for a security alert email.

    Parameters
    ----------
    risk_level         : "HIGH" or "CRITICAL"
    attack_probability : float 0-1
    predicted_stage    : e.g. "Reconnaissance"
    stage_confidence   : float 0-1
    mitre_technique    : e.g. "T1595 - Active Scanning" or "None"
    top_features       : list of feature name strings (may be empty)
    current_stage      : observed stage (context only, optional)
    sample_id          : test sample index (context only, optional)

    Returns
    -------
    (subject: str, plain_text_body: str)
    """
    ts       = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    prob_pct = f"{attack_probability * 100:.1f}%"
    rec      = DEFENDER_RECOMMENDATIONS.get(predicted_stage,
                "Review model output and consult security telemetry.")

    subject = f"[CYBER DEFENCE ALERT] {risk_level} Risk Predicted"

    # Features section
    if top_features:
        feat_lines = "\n".join(
            f"  {i+1}. {f}" for i, f in enumerate(top_features)
        )
        feat_section = f"Top Evidence Features:\n{feat_lines}"
    else:
        feat_section = "Explainability evidence: Not available."

    # Optional context lines
    sample_line = f"Sample ID          : {sample_id}\n" if sample_id is not None else ""
    current_line = f"Current Stage      : {current_stage}\n" if current_stage else ""

    sep = "=" * 54

    body = f"""{sep}
AI WORLD MODELS FOR PREDICTIVE CYBER DEFENCE
{sep}
Generated          : {ts}
{sample_line}{current_line}
Risk Level         : {risk_level}
Attack Probability : {prob_pct}
Predicted Stage    : {predicted_stage}
Stage Confidence   : {stage_confidence * 100:.1f}%
MITRE ATT&CK       : {mitre_technique}

{feat_section}

Recommended Action:
  {rec}

{sep}
IMPORTANT:
This is an AI-generated prediction and is not a confirmed attack.
Validate the alert using additional security telemetry before
taking incident-response action.
{sep}
"""
    return subject, body


# ============================================================
# Public API
# ============================================================

def should_alert(risk_level: str) -> bool:
    """Return True only for HIGH or CRITICAL risk."""
    return risk_level in ALERT_RISK_LEVELS


def send_alert(
    risk_level:         str,
    attack_probability: float,
    predicted_stage:    str,
    stage_confidence:   float,
    mitre_technique:    str,
    top_features:       Optional[list[str]] = None,
    current_stage:      Optional[str]       = None,
    sample_id:          Optional[int]       = None,
) -> bool:
    """
    Send a security alert email if risk is HIGH or CRITICAL.

    This function is SAFE to call unconditionally from predict.py —
    it will silently skip if risk is LOW/MEDIUM, if credentials are
    missing, or if SMTP fails.  The calling script always continues.

    Parameters
    ----------
    risk_level         : computed by alert_manager.calculate_risk_level()
    attack_probability : float 0-1 from model output
    predicted_stage    : stage name string
    stage_confidence   : float 0-1
    mitre_technique    : formatted string e.g. "T1595 - Active Scanning"
    top_features       : list of top feature names from explainability
    current_stage      : true/observed stage (context, not used in prediction)
    sample_id          : X_test index (context only)

    Returns
    -------
    True if email was sent, False otherwise.
    """
    # ── 1. Risk gate ───────────────────────────────────────────
    if not should_alert(risk_level):
        return False

    # ── 2. Credential check ───────────────────────────────────
    if not is_configured():
        print(
            "Email alert skipped: SMTP credentials are not configured.\n"
            "Set SMTP_EMAIL, SMTP_PASSWORD, and ALERT_RECEIVER_EMAIL "
            "environment variables to enable alerts."
        )
        return False

    cfg = _get_config()

    # ── 3. Build message ──────────────────────────────────────
    subject, body = _build_email(
        risk_level         = risk_level,
        attack_probability = attack_probability,
        predicted_stage    = predicted_stage,
        stage_confidence   = stage_confidence,
        mitre_technique    = mitre_technique,
        top_features       = top_features or [],
        current_stage      = current_stage,
        sample_id          = sample_id,
    )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = cfg["sender"]
    msg["To"]      = cfg["receiver"]
    msg.set_content(body)

    # ── 4. Send ────────────────────────────────────────────────
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(cfg["sender"], cfg["password"])
            server.send_message(msg)

        print(f"Email alert sent successfully to {cfg['receiver']}.")
        return True

    except smtplib.SMTPAuthenticationError:
        print(
            "Email alert failed: SMTP authentication error. "
            "For Gmail, use an App Password — not your normal account password.\n"
            "Generate one at: https://myaccount.google.com/apppasswords"
        )
    except smtplib.SMTPException as exc:
        # Sanitise: never print credentials, only safe message
        safe_msg = str(exc).split("b'")[-1].rstrip("'") if "b'" in str(exc) else str(exc)
        print(f"Email alert failed: SMTP error — {safe_msg}")
    except OSError as exc:
        print(f"Email alert failed: network error — {exc}")

    return False
