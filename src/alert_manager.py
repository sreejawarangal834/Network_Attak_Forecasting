"""
alert_manager.py
================
Email alert / risk escalation manager for
SIH "AI World Models for Predictive Cyber Defence".

Responsibilities
----------------
- Calculate risk level from model predictions
- Detect meaningful risk escalation
- Suppress duplicate / cooldown alerts (in-memory state)
- Format professional HTML + plain-text security alert emails
- Send emails via SMTP (Gmail STARTTLS by default)
- Keep all credentials in environment variables / .env file

Credentials
-----------
Never hardcode credentials here.
Set the following in your local .env file:

    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USERNAME=your_email@gmail.com
    SMTP_PASSWORD=your_gmail_app_password   ← Gmail App Password, NOT login password
    ALERT_RECIPIENT=defender@example.com
    ALERTS_ENABLED=true
    ALERT_COOLDOWN_SECONDS=300

IMPORTANT DISCLAIMER
--------------------
This alert system is based on a predictive model operating on simulated
telemetry.  Alerts represent model forecasts, not confirmed real-world
attacks.  All alerts should be validated by a security operator.

Do NOT take automated remediation actions (blocking, account deletion,
connection termination) based solely on these alerts.
"""

from __future__ import annotations

import logging
import os
import smtplib
import time
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

# Load .env if python-dotenv is available (soft dependency)
try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).resolve().parent.parent / ".env"
    if _env_file.exists():
        load_dotenv(dotenv_path=_env_file, override=False)
except ImportError:
    pass   # python-dotenv not installed; rely on environment variables

log = logging.getLogger("alert_manager")

# ============================================================
# Risk level constants
# ============================================================

RISK_LOW      = "LOW"
RISK_MEDIUM   = "MEDIUM"
RISK_HIGH     = "HIGH"
RISK_CRITICAL = "CRITICAL"
RISK_NONE     = "NONE"       # Benign with low probability

# Stage order used to detect escalation (higher index = more severe)
_STAGE_SEVERITY: dict[str, int] = {
    "Benign":            0,
    "Reconnaissance":    1,
    "BruteForce":        2,
    "LateralMovement":   3,
    "CommandAndControl": 4,
}

_RISK_ORDER: dict[str, int] = {
    RISK_NONE:     0,
    RISK_LOW:      1,
    RISK_MEDIUM:   2,
    RISK_HIGH:     3,
    RISK_CRITICAL: 4,
}

# ============================================================
# Defensive recommendations per stage
# ============================================================

DEFENDER_RECOMMENDATIONS: dict[str, str] = {
    "Benign": (
        "No immediate defensive action indicated by the model."
    ),
    "Reconnaissance": (
        "Investigate unusual scanning activity, source IP diversity, and "
        "suspicious port-scan patterns. Consider reviewing firewall logs "
        "for connection attempts to uncommon destination ports."
    ),
    "BruteForce": (
        "Investigate repeated authentication failures and suspicious login "
        "attempts. Consider reviewing SSH/RDP/FTP access logs for "
        "credential-stuffing or password-spray patterns."
    ),
    "LateralMovement": (
        "Investigate unusual internal remote-service connections and "
        "authentication activity between hosts. Review SMB, RDP, and "
        "WinRM traffic for lateral movement indicators."
    ),
    "CommandAndControl": (
        "Investigate suspicious outbound communications and potential C2 "
        "beaconing activity. Review DNS queries, HTTP/HTTPS egress traffic, "
        "and connections to unusual external IP addresses."
    ),
}

# ============================================================
# Risk calculation
# ============================================================

def calculate_risk_level(
    attack_probability: float,
    predicted_stage:    str,
) -> str:
    """
    Map (attack_probability, predicted_stage) -> risk level string.

    Rules
    -----
    - Benign stage is always NONE regardless of probability.
      (A numerical artefact should not trigger a Benign alert.)
    - For non-Benign stages, use attack_probability thresholds:
        < 0.50  -> LOW
        < 0.75  -> MEDIUM
        < 0.90  -> HIGH
        >= 0.90 -> CRITICAL
    """
    if predicted_stage == "Benign":
        return RISK_NONE

    if attack_probability < 0.50:
        return RISK_LOW
    elif attack_probability < 0.75:
        return RISK_MEDIUM
    elif attack_probability < 0.90:
        return RISK_HIGH
    else:
        return RISK_CRITICAL


def is_escalation(
    previous_risk:    Optional[str],
    current_risk:     str,
    previous_stage:   Optional[str],
    current_stage:    str,
) -> tuple[bool, str]:
    """
    Determine whether the current assessment represents a meaningful
    escalation compared to the previous one.

    Returns (escalated: bool, reason: str).

    Escalation is detected when:
    1. Risk level increases (e.g. MEDIUM -> HIGH), OR
    2. Attack stage advances along the kill-chain even at the same
       risk level (e.g. Recon -> BruteForce), OR
    3. No previous state exists (first evaluation).

    Non-escalation (suppressed) when:
    - Risk level decreases or stays the same AND stage stays the same.
    - Stage is Benign (RISK_NONE).
    """
    if current_risk == RISK_NONE:
        return False, "Predicted stage is Benign; no escalation."

    if previous_risk is None or previous_stage is None:
        return True, "First evaluation — initial alert."

    prev_r = _RISK_ORDER.get(previous_risk, 0)
    curr_r = _RISK_ORDER.get(current_risk, 0)

    if curr_r > prev_r:
        return True, f"Risk level escalated: {previous_risk} -> {current_risk}"

    prev_s = _STAGE_SEVERITY.get(previous_stage, 0)
    curr_s = _STAGE_SEVERITY.get(current_stage, 0)

    if curr_s > prev_s:
        return True, f"Attack stage advanced: {previous_stage} -> {current_stage}"

    return False, f"No escalation ({previous_risk} -> {current_risk}, {previous_stage} -> {current_stage})"


# ============================================================
# In-memory alert state (per-sample)
# ============================================================

@dataclass
class _SampleAlertState:
    last_risk:       Optional[str]  = None
    last_stage:      Optional[str]  = None
    last_alert_time: Optional[float] = None   # epoch seconds


class AlertStateManager:
    """
    Simple in-memory duplicate-alert suppressor.

    Tracks the last alert issued per sample_id and enforces a
    per-sample cooldown period.

    NOTE: This is in-process memory only.  If the API is restarted
    or multiple instances are run, state is lost.  Use a Redis /
    database backend for production multi-instance deployments.
    """

    def __init__(self, cooldown_seconds: int = 300) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._state: dict[int, _SampleAlertState] = {}

    def should_send(
        self,
        sample_id:     int,
        risk_level:    str,
        predicted_stage: str,
    ) -> tuple[bool, str]:
        """
        Returns (send: bool, reason: str).

        Suppresses if:
        - Within cooldown period AND no escalation detected.
        """
        s = self._state.get(sample_id, _SampleAlertState())

        escalated, esc_reason = is_escalation(
            previous_risk   = s.last_risk,
            current_risk    = risk_level,
            previous_stage  = s.last_stage,
            current_stage   = predicted_stage,
        )

        if not escalated:
            return False, esc_reason

        # Escalation detected — check cooldown
        now = time.time()
        if s.last_alert_time is not None:
            elapsed = now - s.last_alert_time
            if elapsed < self.cooldown_seconds:
                remaining = int(self.cooldown_seconds - elapsed)
                return (
                    False,
                    f"Alert suppressed by cooldown ({remaining}s remaining). "
                    f"Escalation: {esc_reason}",
                )

        return True, esc_reason

    def record_alert(
        self,
        sample_id:       int,
        risk_level:      str,
        predicted_stage: str,
    ) -> None:
        """Record that an alert was sent for this sample."""
        self._state[sample_id] = _SampleAlertState(
            last_risk       = risk_level,
            last_stage      = predicted_stage,
            last_alert_time = time.time(),
        )


# ============================================================
# SMTP configuration (from environment)
# ============================================================

def get_smtp_config() -> dict:
    """
    Read SMTP settings from environment variables.
    Returns a dict; never returns the password in logs.
    """
    return {
        "host":      os.environ.get("SMTP_HOST",     "smtp.gmail.com"),
        "port":      int(os.environ.get("SMTP_PORT", "587")),
        "username":  os.environ.get("SMTP_USERNAME",  ""),
        "password":  os.environ.get("SMTP_PASSWORD",  ""),
        "recipient": os.environ.get("ALERT_RECIPIENT", ""),
        "enabled":   os.environ.get("ALERTS_ENABLED", "false").lower() == "true",
        "cooldown":  int(os.environ.get("ALERT_COOLDOWN_SECONDS", "300")),
    }


def is_smtp_configured() -> bool:
    cfg = get_smtp_config()
    return bool(cfg["username"] and cfg["password"] and cfg["recipient"])


def alerts_enabled() -> bool:
    return get_smtp_config()["enabled"]


# ============================================================
# Email formatting
# ============================================================

def _stage_arrow(stages: list[str]) -> str:
    """Format a list of stages as 'A → B → C'."""
    return " → ".join(stages)


def _html_risk_color(risk: str) -> str:
    return {
        RISK_CRITICAL: "#c0392b",
        RISK_HIGH:     "#e67e22",
        RISK_MEDIUM:   "#f1c40f",
        RISK_LOW:      "#27ae60",
        RISK_NONE:     "#7f8c8d",
    }.get(risk, "#333333")


def format_alert_email(
    sample_id:          int,
    risk_level:         str,
    attack_probability: float,
    current_stage:      str,
    predicted_stage:    str,
    stage_confidence:   float,
    forecast_horizon:   int,
    mitre_id:           Optional[str],
    mitre_name:         Optional[str],
    trajectory:         list[str],
    top_features:       list[str],
    escalation_reason:  str,
) -> tuple[str, str, str]:
    """
    Build (subject, html_body, plain_body) for an alert email.

    Parameters
    ----------
    trajectory   : list of predicted stage names for each rollout step
    top_features : list of top feature names by sensitivity
    """
    ts          = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    mitre_str   = f"{mitre_id} — {mitre_name}" if mitre_id else "None"
    prob_pct    = f"{attack_probability * 100:.2f}%"
    rec         = DEFENDER_RECOMMENDATIONS.get(predicted_stage, "Review model output.")
    risk_color  = _html_risk_color(risk_level)

    # ── Subject ────────────────────────────────────────────────
    subject = (
        f"[AI CYBER DEFENCE] {risk_level} RISK — "
        f"Predicted {predicted_stage} Activity"
    )

    # ── HTML body ──────────────────────────────────────────────
    traj_html = "".join(
        f"<li style='margin:4px 0'>{s}</li>" for s in trajectory
    )
    feat_html = "".join(
        f"<li style='margin:4px 0'>{i+1}. {f}</li>"
        for i, f in enumerate(top_features)
    )

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f4f4f4;margin:0;padding:0">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:30px 0">
<tr><td align="center">
<table width="620" cellpadding="0" cellspacing="0"
       style="background:#ffffff;border-radius:8px;overflow:hidden;
              box-shadow:0 2px 8px rgba(0,0,0,0.12)">

  <!-- Header -->
  <tr>
    <td style="background:{risk_color};padding:24px 32px">
      <h1 style="color:#ffffff;margin:0;font-size:22px;letter-spacing:1px">
        AI WORLD MODEL — PREDICTIVE CYBER DEFENCE ALERT
      </h1>
      <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:13px">
        Generated: {ts} &nbsp;|&nbsp; Sample ID: {sample_id}
      </p>
    </td>
  </tr>

  <!-- Risk banner -->
  <tr>
    <td style="padding:20px 32px 10px">
      <table width="100%" cellpadding="10" cellspacing="0"
             style="background:{risk_color};border-radius:6px">
        <tr>
          <td align="center">
            <span style="color:#fff;font-size:28px;font-weight:bold;
                          letter-spacing:2px">{risk_level} RISK</span>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- Details -->
  <tr>
    <td style="padding:10px 32px 20px">
      <table width="100%" cellpadding="8" cellspacing="0"
             style="border-collapse:collapse">

        <tr style="background:#f9f9f9">
          <td style="font-weight:bold;width:45%;border-bottom:1px solid #eee">
            Attack Probability</td>
          <td style="color:{risk_color};font-weight:bold;border-bottom:1px solid #eee">
            {prob_pct}</td>
        </tr>
        <tr>
          <td style="font-weight:bold;border-bottom:1px solid #eee">
            Current Stage</td>
          <td style="border-bottom:1px solid #eee">{current_stage}</td>
        </tr>
        <tr style="background:#f9f9f9">
          <td style="font-weight:bold;border-bottom:1px solid #eee">
            Predicted Stage</td>
          <td style="color:{risk_color};font-weight:bold;border-bottom:1px solid #eee">
            {predicted_stage}</td>
        </tr>
        <tr>
          <td style="font-weight:bold;border-bottom:1px solid #eee">
            Stage Confidence</td>
          <td style="border-bottom:1px solid #eee">
            {stage_confidence * 100:.2f}%</td>
        </tr>
        <tr style="background:#f9f9f9">
          <td style="font-weight:bold;border-bottom:1px solid #eee">
            Forecast Horizon</td>
          <td style="border-bottom:1px solid #eee">+{forecast_horizon} steps</td>
        </tr>
        <tr>
          <td style="font-weight:bold;border-bottom:1px solid #eee">
            MITRE ATT&amp;CK</td>
          <td style="border-bottom:1px solid #eee">{mitre_str}</td>
        </tr>
        <tr style="background:#f9f9f9">
          <td style="font-weight:bold">Escalation Reason</td>
          <td>{escalation_reason}</td>
        </tr>

      </table>
    </td>
  </tr>

  <!-- Trajectory -->
  <tr>
    <td style="padding:0 32px 20px">
      <h3 style="color:#333;margin:0 0 10px;font-size:15px">
        Predicted Attack Trajectory (5-step forecast)
      </h3>
      <ul style="margin:0;padding-left:20px;color:#555;font-size:14px">
        {traj_html}
      </ul>
    </td>
  </tr>

  <!-- Top features -->
  <tr>
    <td style="padding:0 32px 20px">
      <h3 style="color:#333;margin:0 0 10px;font-size:15px">
        Prediction-Sensitive Telemetry Features
      </h3>
      <p style="color:#888;font-size:12px;margin:0 0 8px">
        Features whose removal most changes the model output.
        Sensitivity &#8800; causation.
      </p>
      <ul style="margin:0;padding-left:20px;color:#555;font-size:14px">
        {feat_html}
      </ul>
    </td>
  </tr>

  <!-- Recommendation -->
  <tr>
    <td style="padding:0 32px 20px">
      <h3 style="color:#333;margin:0 0 10px;font-size:15px">
        Recommended Defender Action
      </h3>
      <p style="color:#555;font-size:14px;margin:0;
                background:#fef9e7;border-left:4px solid {risk_color};
                padding:10px 14px;border-radius:0 4px 4px 0">
        {rec}
      </p>
    </td>
  </tr>

  <!-- Disclaimer -->
  <tr>
    <td style="background:#f8f8f8;padding:16px 32px;
               border-top:1px solid #ececec">
      <p style="color:#888;font-size:12px;margin:0;line-height:1.6">
        <strong>IMPORTANT:</strong> This alert was generated by the AI World
        Model based on temporal network-state forecasting of simulated telemetry.
        It is a <em>predictive model output</em> and must be validated by the
        security operator before any defensive action is taken.
        This system does not take automated remediation actions.
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    # ── Plain-text body ────────────────────────────────────────
    feat_plain = "\n".join(
        f"  {i+1}. {f}" for i, f in enumerate(top_features)
    )
    traj_plain = "\n".join(f"  Step +{i+1}: {s}" for i, s in enumerate(trajectory))

    plain = f"""AI WORLD MODEL — PREDICTIVE CYBER DEFENCE ALERT
{"=" * 56}
Generated      : {ts}
Sample ID      : {sample_id}

RISK LEVEL     : {risk_level}
{"=" * 56}

Attack Probability : {prob_pct}
Current Stage      : {current_stage}
Predicted Stage    : {predicted_stage}
Stage Confidence   : {stage_confidence * 100:.2f}%
Forecast Horizon   : +{forecast_horizon} steps
MITRE ATT&CK       : {mitre_str}
Escalation Reason  : {escalation_reason}

PREDICTED ATTACK TRAJECTORY
{traj_plain}

PREDICTION-SENSITIVE TELEMETRY FEATURES
(Sensitivity != causation)
{feat_plain}

RECOMMENDED DEFENDER ACTION
{rec}

{"=" * 56}
IMPORTANT: This alert was generated by the AI World Model based on
temporal network-state forecasting of simulated telemetry.
This is a predictive model output and should be validated by the
security operator. No automated remediation actions are taken.
{"=" * 56}
"""

    return subject, html, plain


# ============================================================
# SMTP sender
# ============================================================

def send_alert_email(
    subject:    str,
    html_body:  str,
    plain_body: str,
) -> tuple[bool, str]:
    """
    Send a multipart HTML/plain-text email via SMTP STARTTLS.

    Returns (success: bool, message: str).
    Never logs the SMTP password.
    """
    cfg = get_smtp_config()

    if not cfg["enabled"]:
        log.info("Alert email not sent — ALERTS_ENABLED=false")
        return False, "Alerts are disabled."

    if not cfg["username"] or not cfg["password"]:
        log.warning("Alert email not sent — SMTP credentials not configured")
        return False, "SMTP credentials not configured (SMTP_USERNAME / SMTP_PASSWORD)."

    if not cfg["recipient"]:
        log.warning("Alert email not sent — ALERT_RECIPIENT not configured")
        return False, "ALERT_RECIPIENT not configured."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = cfg["username"]
    msg["To"]      = cfg["recipient"]
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body,  "html",  "utf-8"))

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["username"], cfg["recipient"], msg.as_string())

        log.info("Alert email sent successfully to %s", cfg["recipient"])
        return True, f"Alert email sent to {cfg['recipient']}."

    except smtplib.SMTPAuthenticationError:
        log.error("SMTP authentication failed. Check SMTP_USERNAME/SMTP_PASSWORD.")
        return False, (
            "SMTP authentication failed. "
            "For Gmail, use an App Password, not your normal account password."
        )
    except smtplib.SMTPException as exc:
        log.error("SMTP error: %s", exc)
        return False, f"SMTP error: {exc}"
    except OSError as exc:
        log.error("Network error sending email: %s", exc)
        return False, f"Network error: {exc}"


# ============================================================
# Test email helper
# ============================================================

def send_test_email() -> tuple[bool, str]:
    """Send a clearly-labelled test email to verify SMTP configuration."""
    cfg = get_smtp_config()
    ts  = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    subject = "[AI CYBER DEFENCE] Test Alert"

    html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;padding:30px">
<h2 style="color:#2980b9">AI World Model — Test Alert</h2>
<p>This is a <strong>test alert</strong> from the Predictive Cyber Defence API.</p>
<p>Email configuration is working correctly.</p>
<p style="color:#888;font-size:12px">Sent: {ts}</p>
<hr>
<p style="color:#aaa;font-size:11px">
  This is NOT a real security alert. Generated for configuration verification only.
</p>
</body></html>"""

    plain = f"""AI World Model — Test Alert
{"=" * 40}
This is a test alert from the Predictive Cyber Defence API.
Email configuration is working correctly.
Sent: {ts}

This is NOT a real security alert.
Generated for configuration verification only.
"""

    return send_alert_email(subject, html, plain)
