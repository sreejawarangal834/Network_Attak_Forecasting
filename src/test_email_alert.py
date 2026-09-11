"""
test_email_alert.py
===================
Safe standalone test for the email alert module.
SIH "AI World Models for Predictive Cyber Defence".

Usage
-----
    python src/test_email_alert.py            # checks config, sends test if configured
    python src/test_email_alert.py --dry-run  # checks config only, no email sent

Does NOT automatically send emails on import or startup.
Does NOT print SMTP passwords.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from email_alert import (
    is_configured, should_alert, send_alert, _get_config, ALERT_RISK_LEVELS
)

SEP = "=" * 56


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test email_alert.py configuration and delivery"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Check configuration only; do not send any email."
    )
    args = parser.parse_args()

    print(SEP)
    print("  EMAIL ALERT — CONFIGURATION TEST")
    print(SEP)

    # ── 1. Configuration status ────────────────────────────────
    cfg = _get_config()
    print(f"\nSMTP Host        : {cfg['host']}")
    print(f"SMTP Port        : {cfg['port']}")
    print(f"SMTP_EMAIL       : {cfg['sender']  or '(NOT SET)'}")
    print(f"SMTP_PASSWORD    : {'(SET — not shown)' if cfg['password'] else '(NOT SET)'}")
    print(f"ALERT_RECEIVER   : {cfg['receiver'] or '(NOT SET)'}")
    print(f"\nFully configured : {'YES' if is_configured() else 'NO'}")

    # ── 2. Risk gate check ─────────────────────────────────────
    print(f"\nAlert risk levels: {sorted(ALERT_RISK_LEVELS)}")
    for level, prob in [("LOW", 0.30), ("MEDIUM", 0.65),
                        ("HIGH", 0.82), ("CRITICAL", 0.95)]:
        gate = should_alert(level)
        print(f"  {level:<10} (prob={prob}) -> alert triggered: {gate}")

    # ── 3. Email send test ─────────────────────────────────────
    if args.dry_run:
        print("\n[DRY RUN] Email send skipped (--dry-run).")
        print(SEP)
        return

    if not is_configured():
        print(
            "\nEmail test skipped: SMTP credentials not configured.\n"
            "Set environment variables:\n"
            "  SMTP_EMAIL, SMTP_PASSWORD, ALERT_RECEIVER_EMAIL\n"
            "then re-run this script."
        )
        print(SEP)
        return

    print("\nSending test alert email (CRITICAL risk simulation) ...")

    success = send_alert(
        risk_level         = "CRITICAL",
        attack_probability = 0.9350,
        predicted_stage    = "Reconnaissance",
        stage_confidence   = 0.8712,
        mitre_technique    = "T1595 - Active Scanning",
        top_features       = [
            "packet_unique_protocols",
            "flow_count",
            "packet_std_ttl",
            "packet_unique_src_ports",
            "syn_to_packet_ratio",
        ],
        current_stage      = "Benign",
        sample_id          = 999,
    )

    if success:
        print("Test completed: email sent successfully.")
    else:
        print("Test completed: email was not sent (see message above).")

    print(SEP)


if __name__ == "__main__":
    main()
