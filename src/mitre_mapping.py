"""
mitre_mapping.py
================
Prototype stage-to-MITRE ATT&CK mapping for
SIH "AI World Models for Predictive Cyber Defence".

IMPORTANT DISCLAIMER
--------------------
This is a *prototype* mapping used for demonstration purposes only.
The World Model predicts network-state attack stages derived from
synthetic telemetry features.  Those predicted stages are then mapped
to a *representative* MITRE ATT&CK technique to aid analyst
interpretation.

The model does NOT directly detect the exact ATT&CK technique from
raw packet or flow telemetry.  The correct wording is:

    "Predicted attack stage mapped to a representative
     MITRE ATT&CK technique."

Only the five stages modelled in this prototype are covered.
No additional techniques have been fabricated.
"""

from __future__ import annotations

# ============================================================
# Mapping table
# ============================================================

_MITRE_TABLE: dict[str, dict[str, str | None]] = {
    "Benign": {
        "mitre_attack_id":   None,
        "mitre_attack_name": None,
    },
    "Reconnaissance": {
        "mitre_attack_id":   "T1595",
        "mitre_attack_name": "Active Scanning",
    },
    "BruteForce": {
        "mitre_attack_id":   "T1110",
        "mitre_attack_name": "Brute Force",
    },
    "LateralMovement": {
        "mitre_attack_id":   "T1021",
        "mitre_attack_name": "Remote Services",
    },
    "CommandAndControl": {
        "mitre_attack_id":   "T1071",
        "mitre_attack_name": "Application Layer Protocol",
    },
}

# ============================================================
# Public API
# ============================================================

def get_mitre_mapping(stage: str) -> dict[str, str | None]:
    """
    Return the representative MITRE ATT&CK mapping for a predicted
    attack stage.

    Parameters
    ----------
    stage : str
        One of "Benign", "Reconnaissance", "BruteForce",
        "LateralMovement", "CommandAndControl".

    Returns
    -------
    dict with keys:
        mitre_attack_id   : str or None
        mitre_attack_name : str or None

    Raises
    ------
    KeyError if stage is not in the mapping table.
    """
    if stage not in _MITRE_TABLE:
        raise KeyError(
            f"Unknown stage '{stage}'. "
            f"Valid stages: {list(_MITRE_TABLE.keys())}"
        )
    return dict(_MITRE_TABLE[stage])


def format_mitre(stage: str) -> str:
    """
    Return a human-readable ATT&CK string for display.

    Examples
    --------
    "T1071 - Application Layer Protocol"
    "None"
    """
    mapping = get_mitre_mapping(stage)
    mid  = mapping["mitre_attack_id"]
    name = mapping["mitre_attack_name"]
    if mid is None:
        return "None"
    return f"{mid} - {name}"


def all_stages() -> list[str]:
    """Return the list of all modelled stage names."""
    return list(_MITRE_TABLE.keys())


# ============================================================
# Quick self-test when run directly
# ============================================================

if __name__ == "__main__":
    print("MITRE ATT&CK prototype mapping")
    print("=" * 50)
    for stage in all_stages():
        m = get_mitre_mapping(stage)
        print(f"  {stage:<22} -> {format_mitre(stage)}")
