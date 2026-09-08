"""
Simulated packet telemetry generator.
Produces 50,000 synthetic network events representing a realistic attack progression:
  Benign → Reconnaissance → BruteForce → LateralMovement → CommandAndControl

This is SYNTHETIC development data. It is NOT derived from real PCAP captures.
Run once to produce data/simulated/simulated_packets.csv.
"""

import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)

# ── Attack stage windows (row ranges) ────────────────────────────────────────
STAGES = [
    ("Benign",             0,     19999),
    ("Reconnaissance",    20000,  29999),
    ("BruteForce",        30000,  37499),
    ("LateralMovement",   37500,  44999),
    ("CommandAndControl", 45000,  49999),
]

N = 50_000

# ── IP pools ──────────────────────────────────────────────────────────────────
INTERNAL_IPS = [f"192.168.1.{i}" for i in range(1, 21)]
EXTERNAL_IPS = [f"10.0.{RNG.integers(0,255)}.{RNG.integers(1,254)}" for _ in range(30)]
C2_IPS       = ["185.220.101.42", "94.102.49.190", "198.251.89.25"]

COMMON_PORTS = [80, 443, 22, 21, 25, 53, 8080, 3389, 445, 3306]
PROTOCOLS    = ["TCP", "UDP", "ICMP"]


def stage_for(idx: int) -> str:
    for name, lo, hi in STAGES:
        if lo <= idx <= hi:
            return name
    return "Benign"


def make_row(idx: int) -> dict:
    stage = stage_for(idx)

    # ── Base values ────────────────────────────────────────────────────────
    src_ip  = RNG.choice(INTERNAL_IPS)
    dst_ip  = RNG.choice(INTERNAL_IPS + EXTERNAL_IPS)
    proto   = RNG.choice(PROTOCOLS, p=[0.70, 0.25, 0.05])
    pkt_sz  = int(RNG.normal(512, 150))
    ttl     = int(RNG.normal(64, 5))
    win     = int(RNG.normal(65535, 5000))
    syn, ack, rst, fin = 0, 0, 0, 0

    src_port = int(RNG.integers(1024, 65535))
    dst_port = int(RNG.choice(COMMON_PORTS))

    # ── Stage-specific overrides ────────────────────────────────────────────
    if stage == "Benign":
        ack = 1
        syn = int(RNG.random() < 0.05)
        pkt_sz = int(RNG.normal(600, 200))

    elif stage == "Reconnaissance":
        # Port scanning: many small SYN packets to varied ports
        syn = 1; ack = 0; rst = int(RNG.random() < 0.4)
        dst_port = int(RNG.integers(1, 65535))
        pkt_sz   = int(RNG.normal(64, 10))
        ttl      = int(RNG.normal(128, 3))
        dst_ip   = RNG.choice(INTERNAL_IPS)   # scanning internal network
        src_ip   = RNG.choice(EXTERNAL_IPS)

    elif stage == "BruteForce":
        # Rapid repeated connections to SSH/RDP/FTP
        syn = 1; ack = int(RNG.random() < 0.6)
        dst_port = int(RNG.choice([22, 3389, 21, 23]))
        pkt_sz   = int(RNG.normal(120, 20))
        win      = int(RNG.normal(8192, 500))
        src_ip   = RNG.choice(EXTERNAL_IPS)

    elif stage == "LateralMovement":
        # Internal east-west SMB / RDP traffic
        proto    = "TCP"
        dst_port = int(RNG.choice([445, 3389, 135, 139]))
        src_ip   = RNG.choice(INTERNAL_IPS)
        dst_ip   = RNG.choice(INTERNAL_IPS)
        syn = int(RNG.random() < 0.3)
        ack = 1
        pkt_sz   = int(RNG.normal(900, 150))

    elif stage == "CommandAndControl":
        # Beaconing: regular small packets to C2 IPs
        dst_ip   = RNG.choice(C2_IPS)
        src_ip   = RNG.choice(INTERNAL_IPS)
        dst_port = int(RNG.choice([443, 80, 8080, 4444, 1337]))
        pkt_sz   = int(RNG.normal(256, 30))
        ttl      = int(RNG.normal(48, 4))
        syn = int(RNG.random() < 0.15)
        ack = 1

    # Clamp values
    pkt_sz = max(20, min(9000, pkt_sz))
    ttl    = max(1,  min(255,  ttl))
    win    = max(0,  min(65535, win))

    label = 0 if stage == "Benign" else 1

    return {
        "timestamp":   idx,          # sequential counter — UI will format it
        "src_ip":      src_ip,
        "dst_ip":      dst_ip,
        "src_port":    src_port,
        "dst_port":    dst_port,
        "protocol":    proto,
        "packet_size": pkt_sz,
        "ttl":         ttl,
        "tcp_window":  win,
        "syn":         syn,
        "ack":         ack,
        "rst":         rst,
        "fin":         fin,
        "attack_type": stage,
        "label":       label,
    }


def main():
    out = Path("data/simulated/simulated_packets.csv")
    out.parent.mkdir(parents=True, exist_ok=True)

    rows = [make_row(i) for i in range(N)]
    df   = pd.DataFrame(rows)

    # Convert sequential index to readable timestamps
    base = pd.Timestamp("2024-01-15 08:00:00")
    df["timestamp"] = pd.date_range(start=base, periods=N, freq="100ms")

    df.to_csv(out, index=False)
    print(f"[OK] Written {len(df):,} rows → {out}")
    print(df["attack_type"].value_counts().to_string())


if __name__ == "__main__":
    main()
