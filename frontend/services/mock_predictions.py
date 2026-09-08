"""
mock_predictions.py — Demo prediction outputs.

These values stand in for the real World Model until the ML backend is ready.
The frontend ONLY consumes the PredictionResult dataclass; it never knows
whether the values came from LSTM, Transformer, GNN, or mock data.

When integrating the real model:
  1. Keep the PredictionResult structure identical.
  2. Replace get_mock_prediction() with a call to the real inference pipeline.
  3. The rest of the frontend requires zero changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from frontend.utils.constants import ATTACK_STAGES, risk_level

RNG = np.random.default_rng(99)


# ── Standard prediction contract ──────────────────────────────────────────────

@dataclass
class DeviceRisk:
    device_name:      str
    ip:               str
    risk_score:       float        # 0-1
    risk_level:       str          # LOW / MEDIUM / HIGH / CRITICAL
    current_stage:    str
    predicted_stage:  str
    alert_status:     str          # "Active" | "Monitoring" | "Clear"
    recommended_action: str


@dataclass
class SecurityAlert:
    alert_id:          str
    severity:          str          # INFO / WARNING / HIGH / CRITICAL
    timestamp:         str
    device:            str
    src_ip:            str
    target_ip:         str
    risk_probability:  float
    current_stage:     str
    predicted_stage:   str
    explanation:       list[str]
    recommended_actions: list[str]
    status:            str = "Active"  # Active | Investigating | Dismissed


@dataclass
class PredictionResult:
    """
    Canonical prediction structure consumed by every frontend page.
    The ML backend must return an object matching this shape.
    """
    overall_risk:          float                  = 0.87
    risk_level:            str                    = "HIGH"
    current_stage:         str                    = "Reconnaissance"
    predicted_stage:       str                    = "BruteForce"
    forecast_horizon:      int                    = 5             # time steps
    future_probabilities:  list[dict]             = field(default_factory=list)
    risky_devices:         list[DeviceRisk]       = field(default_factory=list)
    network_state:         dict[str, Any]         = field(default_factory=dict)
    attack_path:           list[str]              = field(default_factory=list)
    contributing_features: list[dict]             = field(default_factory=list)
    recommended_actions:   list[str]              = field(default_factory=list)
    security_alerts:       list[SecurityAlert]    = field(default_factory=list)
    is_demo:               bool                   = True


# ── Mock device pool ──────────────────────────────────────────────────────────

_DEVICES = [
    ("PC-03",      "192.168.1.3",  0.91, "Reconnaissance",    "BruteForce"),
    ("Server-01",  "192.168.1.1",  0.87, "BruteForce",        "LateralMovement"),
    ("PC-07",      "192.168.1.7",  0.68, "Reconnaissance",    "BruteForce"),
    ("PC-12",      "192.168.1.12", 0.45, "Benign",            "Reconnaissance"),
    ("Printer-02", "192.168.1.22", 0.22, "Benign",            "Benign"),
    ("PC-05",      "192.168.1.5",  0.15, "Benign",            "Benign"),
    ("Switch-01",  "192.168.1.254",0.10, "Benign",            "Benign"),
]

_ACTIONS = {
    "CRITICAL": "Isolate host immediately and escalate to SOC.",
    "HIGH":     "Increase logging, block suspicious outbound IPs, notify analyst.",
    "MEDIUM":   "Flag for monitoring and review recent auth logs.",
    "LOW":      "Continue standard monitoring.",
}

_ALERT_EXPLANATIONS = {
    "PC-03": [
        "SYN rate 14× above baseline (port-scan pattern)",
        "Connections to 47 unique destination ports in 60 s",
        "TTL variance indicates spoofed-source packets",
        "ICMP echo-request bursts to /24 subnet",
    ],
    "Server-01": [
        "SSH brute-force: 312 failed login attempts in 90 s",
        "Inbound traffic from known malicious IP 185.220.101.42",
        "RST storm on port 22 — credential stuffing signature",
        "Packet inter-arrival time matches automated tool profile",
    ],
    "PC-07": [
        "Elevated SYN rate to internal SMB ports (445, 139)",
        "Unusual lateral connections to Server-01",
        "DNS queries to newly registered domains",
    ],
}


def _make_devices() -> list[DeviceRisk]:
    devices = []
    for name, ip, score, cur, nxt in _DEVICES:
        rl = risk_level(score)
        alert = "Active" if score >= 0.65 else ("Monitoring" if score >= 0.40 else "Clear")
        devices.append(DeviceRisk(
            device_name=name,
            ip=ip,
            risk_score=score,
            risk_level=rl,
            current_stage=cur,
            predicted_stage=nxt,
            alert_status=alert,
            recommended_action=_ACTIONS[rl],
        ))
    return devices


def _make_alerts(devices: list[DeviceRisk]) -> list[SecurityAlert]:
    alerts = []
    ts_base = pd.Timestamp("2024-01-15 09:42:00")
    high_risk = [d for d in devices if d.risk_score >= 0.65]
    for i, d in enumerate(high_risk):
        alerts.append(SecurityAlert(
            alert_id=f"ALERT-{1000+i}",
            severity="CRITICAL" if d.risk_score >= 0.85 else "HIGH",
            timestamp=str(ts_base - pd.Timedelta(minutes=i * 7)),
            device=d.device_name,
            src_ip=d.ip,
            target_ip="192.168.1.1",
            risk_probability=d.risk_score,
            current_stage=d.current_stage,
            predicted_stage=d.predicted_stage,
            explanation=_ALERT_EXPLANATIONS.get(d.device_name, ["Anomalous traffic pattern detected"]),
            recommended_actions=[
                "Investigate host immediately",
                "Review auth and firewall logs",
                "Consider network isolation",
                "Escalate to SOC Tier-2",
            ],
        ))
    return alerts


def _make_future_probs() -> list[dict]:
    """Stage probabilities over a 5-step forecast horizon."""
    horizon = 5
    stages  = ATTACK_STAGES[1:]  # exclude Benign from forecast chart
    rows = []
    base_probs = {
        "Reconnaissance":    [0.72, 0.55, 0.35, 0.20, 0.12],
        "BruteForce":        [0.45, 0.68, 0.60, 0.40, 0.25],
        "LateralMovement":   [0.18, 0.32, 0.55, 0.65, 0.52],
        "CommandAndControl": [0.08, 0.15, 0.28, 0.48, 0.70],
    }
    for t in range(horizon):
        row = {"t": f"T+{t+1}"}
        for s in stages:
            row[s] = base_probs[s][t]
        rows.append(row)
    return rows


def _make_contributing_features() -> list[dict]:
    return [
        {"feature": "SYN Rate",                "importance": 0.34, "value": "14.2/s",  "baseline": "1.1/s"},
        {"feature": "Unique Destination Ports", "importance": 0.28, "value": "47",      "baseline": "4"},
        {"feature": "Packet Size Variance",     "importance": 0.18, "value": "High",    "baseline": "Low"},
        {"feature": "TTL Variation",            "importance": 0.12, "value": "±32",     "baseline": "±3"},
        {"feature": "RST Rate",                 "importance": 0.09, "value": "6.8/s",   "baseline": "0.2/s"},
        {"feature": "Packet Frequency",         "importance": 0.07, "value": "820/min", "baseline": "120/min"},
        {"feature": "Dst IP Entropy",           "importance": 0.05, "value": "3.9 bits","baseline": "1.2 bits"},
    ]


def _make_network_state(df: pd.DataFrame | None = None) -> dict:
    """Build a network state dict, using real data when available."""
    if df is not None and len(df) > 0:
        # Use last 5-minute window of the dataframe
        sample = df.tail(3000)
        state = {
            "active_flows":   int(sample["src_ip"].nunique() * sample["dst_ip"].nunique()),
            "packets_per_sec": round(len(sample) / 300, 1),
            "unique_src_ips": int(sample["src_ip"].nunique()),
            "unique_dst_ips": int(sample["dst_ip"].nunique()),
            "unique_ports":   int(sample["dst_port"].nunique()) if "dst_port" in sample.columns else 0,
            "avg_packet_size": round(float(sample["packet_size"].mean()), 1) if "packet_size" in sample.columns else 0,
            "syn_rate":        round(float(sample["syn"].mean() * 100), 1) if "syn" in sample.columns else 0,
            "ack_rate":        round(float(sample["ack"].mean() * 100), 1) if "ack" in sample.columns else 0,
            "rst_rate":        round(float(sample["rst"].mean() * 100), 1) if "rst" in sample.columns else 0,
            "fin_rate":        round(float(sample["fin"].mean() * 100), 1) if "fin" in sample.columns else 0,
            "avg_ttl":         round(float(sample["ttl"].mean()), 1) if "ttl" in sample.columns else 0,
            "ttl_std":         round(float(sample["ttl"].std()), 1)  if "ttl" in sample.columns else 0,
        }
    else:
        state = {
            "active_flows": 1247, "packets_per_sec": 820.4,
            "unique_src_ips": 18, "unique_dst_ips": 34,
            "unique_ports": 47, "avg_packet_size": 312.6,
            "syn_rate": 14.2, "ack_rate": 68.5,
            "rst_rate": 6.8, "fin_rate": 2.1,
            "avg_ttl": 61.3, "ttl_std": 12.4,
        }
    return state


# ── Public API ─────────────────────────────────────────────────────────────────

def get_mock_prediction(df: pd.DataFrame | None = None) -> PredictionResult:
    """
    Return a PredictionResult populated with demo values.
    When df is provided, network_state is derived from the real data.
    """
    devices = _make_devices()
    alerts  = _make_alerts(devices)

    return PredictionResult(
        overall_risk         = 0.87,
        risk_level           = "HIGH",
        current_stage        = "Reconnaissance",
        predicted_stage      = "BruteForce",
        forecast_horizon     = 5,
        future_probabilities = _make_future_probs(),
        risky_devices        = devices,
        network_state        = _make_network_state(df),
        attack_path          = ATTACK_STAGES,
        contributing_features= _make_contributing_features(),
        recommended_actions  = [
            "Isolate PC-03 and Server-01 from the network segment",
            "Block outbound connections to 185.220.101.42, 94.102.49.190",
            "Force re-authentication on all internal hosts",
            "Enable full packet capture on affected VLAN",
            "Escalate to SOC Tier-2 analyst",
        ],
        security_alerts      = alerts,
        is_demo              = True,
    )


def get_mock_model_performance() -> dict:
    """
    Mock model performance metrics for the Model Performance page.
    DEMO VALUES — not real experimental results.
    """
    return {
        "world_model": {
            "precision":   0.94,
            "recall":      0.91,
            "f1_score":    0.925,
            "fpr":         0.038,
            "auc_roc":     0.97,
            "stage_accuracy": 0.89,
        },
        "logistic_regression": {
            "precision":   0.81,
            "recall":      0.76,
            "f1_score":    0.784,
            "fpr":         0.112,
            "auc_roc":     0.84,
            "stage_accuracy": 0.67,
        },
        "per_stage": {
            "Benign":             {"wm": 0.98, "lr": 0.95},
            "Reconnaissance":     {"wm": 0.93, "lr": 0.79},
            "BruteForce":         {"wm": 0.91, "lr": 0.74},
            "LateralMovement":    {"wm": 0.88, "lr": 0.68},
            "CommandAndControl":  {"wm": 0.85, "lr": 0.61},
        },
    }
