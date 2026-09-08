"""
constants.py — Shared constants used throughout the frontend.
All colour tokens, stage definitions, risk thresholds, and label maps live here
so that a single change propagates everywhere.
"""

from pathlib import Path

# ── Project paths ─────────────────────────────────────────────────────────────
ROOT_DIR            = Path(__file__).resolve().parents[2]
SIMULATED_DATA_PATH = ROOT_DIR / "data" / "simulated" / "simulated_packets.csv"

# ── Attack stage ordering ─────────────────────────────────────────────────────
ATTACK_STAGES = [
    "Benign",
    "Reconnaissance",
    "BruteForce",
    "LateralMovement",
    "CommandAndControl",
]

STAGE_INDEX = {stage: i for i, stage in enumerate(ATTACK_STAGES)}

STAGE_DESCRIPTIONS = {
    "Benign":             "Normal network traffic — no threat detected.",
    "Reconnaissance":     "Attacker is scanning hosts/ports to map the network.",
    "BruteForce":         "Repeated credential-stuffing or password spray attempts.",
    "LateralMovement":    "Attacker is moving between internal hosts (SMB/RDP).",
    "CommandAndControl":  "Compromised host is beaconing to an external C2 server.",
}

STAGE_COLORS = {
    "Benign":             "#22c55e",   # green
    "Reconnaissance":     "#f59e0b",   # amber
    "BruteForce":         "#f97316",   # orange
    "LateralMovement":    "#ef4444",   # red
    "CommandAndControl":  "#7c3aed",   # purple
}

STAGE_ICONS = {
    "Benign":             "✅",
    "Reconnaissance":     "🔍",
    "BruteForce":         "🔨",
    "LateralMovement":    "↔️",
    "CommandAndControl":  "☠️",
}

# ── Risk thresholds ───────────────────────────────────────────────────────────
RISK_THRESHOLDS = {
    "LOW":      (0.0,  0.40),
    "MEDIUM":   (0.40, 0.65),
    "HIGH":     (0.65, 0.85),
    "CRITICAL": (0.85, 1.01),
}

RISK_COLORS = {
    "LOW":      "#22c55e",
    "MEDIUM":   "#f59e0b",
    "HIGH":     "#ef4444",
    "CRITICAL": "#7c3aed",
}

RISK_BG_COLORS = {
    "LOW":      "#052e16",
    "MEDIUM":   "#422006",
    "HIGH":     "#450a0a",
    "CRITICAL": "#2e1065",
}

def risk_level(score: float) -> str:
    """Return the risk label for a given 0-1 probability score."""
    for label, (lo, hi) in RISK_THRESHOLDS.items():
        if lo <= score < hi:
            return label
    return "CRITICAL"

# ── Protocol colours ──────────────────────────────────────────────────────────
PROTOCOL_COLORS = {
    "TCP":  "#3b82f6",
    "UDP":  "#8b5cf6",
    "ICMP": "#06b6d4",
    "Other": "#6b7280",
}

# ── Data source types ─────────────────────────────────────────────────────────
DATA_SOURCES = {
    "Simulated Packet Telemetry": "simulated",
    "CIC-IDS2018 Flow Data":      "cicids",
    "PCAP File (future)":         "pcap",
}

# ── Streamlit page config ─────────────────────────────────────────────────────
APP_TITLE    = "Predictive Cyber Defence — World Model"
APP_ICON     = "🛡️"
LAYOUT       = "wide"
SIDEBAR_STATE = "expanded"

# ── Colour palette (Plotly / Streamlit agnostic) ──────────────────────────────
COLOR_PRIMARY    = "#3b82f6"   # blue
COLOR_DANGER     = "#ef4444"   # red
COLOR_WARNING    = "#f59e0b"   # amber
COLOR_SUCCESS    = "#22c55e"   # green
COLOR_PURPLE     = "#7c3aed"
COLOR_BG_DARK    = "#0f172a"   # page background hint
COLOR_BG_CARD    = "#1e293b"   # card background
COLOR_TEXT_MUTED = "#94a3b8"

# ── Demo/mock watermark text ──────────────────────────────────────────────────
DEMO_BADGE = "⚠️ DEMO — Mock prediction. Real model not yet connected."
