"""
simulate_temporal_traffic.py
============================
Temporal multi-campaign synthetic network telemetry generator.

SIH "AI World Models for Predictive Cyber Defence"

Generates ~250 000 packet events and ~250 000 flow events spread across
~60 independent attack campaigns.  Each campaign cycles through:

    Benign/gap -> Benign(pre) -> Reconnaissance -> BruteForce
               -> LateralMovement -> CommandAndControl -> (next campaign)

Key design goals
----------------
* All five stages appear in every chronological split (70/15/15).
* No stage dominates >35-40% of the resulting 10-second network-state
  windows — achieved by keeping per-stage mean IATs in the same order
  of magnitude (~80-350 ms).
* Genuine per-campaign variation in stage duration, traffic volume,
  packet sizing, flow characteristics, IP/port selection, and
  attack intensity — so campaigns are not identical clones.
* ~5-8% plausible neighbouring-stage label noise.
* Packet and flow telemetry share the same timestamp spine for fusion.

Outputs
-------
data/simulated/simulated_packets.csv
data/simulated/simulated_flow.csv

Regenerate
----------
    python src/simulate_temporal_traffic.py
"""

from __future__ import annotations

import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ============================================================
# Paths
# ============================================================

ROOT    = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "simulated"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PACKET_FILE = OUT_DIR / "simulated_packets.csv"
FLOW_FILE   = OUT_DIR / "simulated_flow.csv"

# ============================================================
# Global parameters
# ============================================================

RANDOM_SEED   = 42
NUM_EVENTS    = 250_000      # target total packet events
NUM_CAMPAIGNS = 60           # independent attack cycles
NOISE_RATE    = 0.065        # 6.5 % neighbouring-stage label noise
START_TIME    = datetime(2026, 9, 1, 8, 0, 0)

random.seed(RANDOM_SEED)
rng = np.random.default_rng(RANDOM_SEED)

# ============================================================
# Network topology  (varied per campaign — see helpers below)
# ============================================================

# Base subnets — campaigns pick sub-ranges to vary the IPs
BENIGN_CLIENTS_BASE = [f"10.0.{s}.{h}" for s in range(1, 5)
                       for h in range(10, 20)]   # 40 clients
INTERNAL_HOSTS_BASE = [f"10.0.{s}.{h}" for s in range(2, 6)
                       for h in range(10, 16)]   # 24 internal hosts
SERVERS_BASE        = [f"10.0.2.{h}" for h in range(10, 20)]  # 10 servers
ATTACKER_POOL       = [f"10.0.{s}.100" for s in range(9, 13)]  # 4 attacker IPs
C2_EXTERNAL_BASE    = [f"203.0.{s}.{h}" for s in range(113, 117)
                       for h in range(10, 20)]  # 40 C2 addresses

COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 135, 137,
                139, 143, 443, 445, 3306, 3389, 8080, 8443]

# ============================================================
# Stage ordering  (used for noise selection and label maps)
# ============================================================

STAGE_ORDER = [
    "Benign",
    "Reconnaissance",
    "BruteForce",
    "LateralMovement",
    "CommandAndControl",
]

LABEL_MAP = {s: (0 if s == "Benign" else 1) for s in STAGE_ORDER}

# ============================================================
# Campaign blueprint
#
# Stage weights control event-count allocation.
# IAT ranges control wall-clock time per stage.
# Both are jittered per campaign to produce genuine variation.
#
# Rationale for IAT ranges
# -------------------------
# mean(IAT) × event_count ≈ wall-clock time consumed by that stage.
# Keeping all means within ~80-350 ms ensures no stage monopolises
# the 10-second state windows.
#
#   Stage           IAT range    mean IAT   evts(~)   wall-clock(~)
#   Benign          80-350 ms    215 ms     ~10k/60   ~36 min total
#   Recon           30-180 ms    105 ms     ~17k/60   ~30 min total
#   BruteForce      30-180 ms    105 ms     ~17k/60   ~30 min total
#   LateralMovement 60-300 ms    180 ms     ~14k/60   ~42 min total
#   C2              80-400 ms    240 ms     ~8k/60    ~32 min total
#   Gap (benign)    80-300 ms    190 ms     ~5k/60    ~16 min total
# ============================================================

# (stage, weight_mean, weight_std)
# weight_std drives per-campaign duration variation
STAGE_WEIGHTS = [
    ("Benign",             0.10, 0.025),   # in-campaign pre-attack benign
    ("Reconnaissance",     0.20, 0.040),   # boosted: fast IAT needs more events
    ("BruteForce",         0.20, 0.040),   # boosted: fast IAT needs more events
    ("LateralMovement",    0.17, 0.035),   # moderate
    ("CommandAndControl",  0.10, 0.025),   # cut back: prevent wall-clock dominance
]

# Inter-campaign calm Benign gap
GAP_WEIGHT = (0.07, 0.025)

# Base IAT ranges (ms) — jittered ±20% per campaign
IAT_BASE = {
    "Benign":            (80,  350),
    "Reconnaissance":    (30,  180),
    "BruteForce":        (30,  180),
    "LateralMovement":   (60,  300),
    "CommandAndControl": (80,  400),
}


# ============================================================
# Per-campaign context
# Each campaign draws a slightly different network context and
# intensity multiplier so traffic profiles are not identical.
# ============================================================

def sample_campaign_context(campaign_idx: int) -> dict:
    """
    Sample a unique-but-reproducible context for one campaign.
    Returns dicts of IPs, ports, intensity scale, IAT jitter, etc.
    """
    c_rng = np.random.default_rng(RANDOM_SEED + campaign_idx * 97 + 13)

    # Pick a sub-slice of the address pools so source/dest IPs vary
    n_clients  = c_rng.integers(6, len(BENIGN_CLIENTS_BASE))
    n_internal = c_rng.integers(4, len(INTERNAL_HOSTS_BASE))
    n_servers  = c_rng.integers(3, len(SERVERS_BASE))
    n_c2       = c_rng.integers(3, len(C2_EXTERNAL_BASE))

    clients  = list(c_rng.choice(BENIGN_CLIENTS_BASE,  n_clients,  replace=False))
    internal = list(c_rng.choice(INTERNAL_HOSTS_BASE,  n_internal, replace=False))
    servers  = list(c_rng.choice(SERVERS_BASE,         n_servers,  replace=False))
    c2_hosts = list(c_rng.choice(C2_EXTERNAL_BASE,     n_c2,       replace=False))
    attacker = str(c_rng.choice(ATTACKER_POOL))

    # Per-campaign IAT multiplier (0.7 – 1.4)  → varied traffic density
    iat_scale = float(c_rng.uniform(0.70, 1.40))

    # Per-campaign attack intensity shift (±0.15)
    intensity_offset = float(c_rng.uniform(-0.15, 0.15))

    # Port favourites for scanning / brute-force in this campaign
    scan_ports  = list(c_rng.choice(COMMON_PORTS, size=c_rng.integers(6, 14), replace=False))
    brute_ports = list(c_rng.choice([22, 21, 23, 3389, 3306, 110, 143],
                                     size=c_rng.integers(2, 5), replace=False))

    return dict(
        clients         = clients,
        internal        = internal,
        servers         = servers,
        c2_hosts        = c2_hosts,
        attacker        = attacker,
        iat_scale       = iat_scale,
        intensity_offset= intensity_offset,
        scan_ports      = scan_ports,
        brute_ports     = brute_ports,
    )


# ============================================================
# Per-stage packet event generators
# Each generator accepts the campaign context so IPs / ports vary.
# ============================================================

def _pkt_benign(ts: datetime, ctx: dict) -> dict:
    src  = random.choice(ctx["clients"])
    dst  = random.choice(ctx["servers"])
    tcp  = random.random() < 0.75
    if tcp:
        dst_port = random.choice([80, 443, 22, 25, 110])
        syn = int(random.random() < 0.12)
        ack = int(random.random() < 0.82)
        rst = int(random.random() < 0.03)
        fin = int(random.random() < 0.10)
        win = random.randint(8192, 65535)
        prot = "TCP"
    else:
        dst_port = random.choice([53, 123, 161])
        syn = ack = rst = fin = win = 0
        prot = "UDP"
    return dict(
        timestamp   = ts,
        src_ip      = src,
        dst_ip      = dst,
        src_port    = random.randint(1024, 65535),
        dst_port    = dst_port,
        protocol    = prot,
        packet_size = random.randint(60, 1400),
        ttl         = random.randint(50, 128),
        tcp_window  = win,
        syn=syn, ack=ack, rst=rst, fin=fin,
        attack_type = "Benign",
        label       = 0,
    )


def _pkt_recon(ts: datetime, ctx: dict) -> dict:
    """Port scanning: high SYN rate, wide destination port range."""
    dst_port = random.choice(ctx["scan_ports"]) if random.random() < 0.6 \
               else random.randint(1, 1024)
    return dict(
        timestamp   = ts,
        src_ip      = ctx["attacker"],
        dst_ip      = random.choice(ctx["servers"]),
        src_port    = random.randint(30000, 60000),
        dst_port    = dst_port,
        protocol    = "TCP",
        packet_size = random.randint(40, 120),
        ttl         = random.randint(40, 70),
        tcp_window  = random.randint(512, 8192),
        syn=1, ack=0,
        rst         = int(random.random() < 0.50),
        fin=0,
        attack_type = "Reconnaissance",
        label       = 1,
    )


def _pkt_bruteforce(ts: datetime, ctx: dict) -> dict:
    """Rapid repeated auth attempts toward a narrow service set."""
    return dict(
        timestamp   = ts,
        src_ip      = ctx["attacker"],
        dst_ip      = random.choice(ctx["servers"]),
        src_port    = random.randint(30000, 60000),
        dst_port    = random.choice(ctx["brute_ports"]),
        protocol    = "TCP",
        packet_size = random.randint(80, 600),
        ttl         = random.randint(40, 70),
        tcp_window  = random.randint(4096, 20480),
        syn         = int(random.random() < 0.50),
        ack=1,
        rst         = int(random.random() < 0.22),
        fin         = int(random.random() < 0.12),
        attack_type = "BruteForce",
        label       = 1,
    )


def _pkt_lateral(ts: datetime, ctx: dict) -> dict:
    """Internal east-west movement: wide internal destination set."""
    return dict(
        timestamp   = ts,
        src_ip      = ctx["attacker"],
        dst_ip      = random.choice(ctx["internal"] + ctx["clients"]),
        src_port    = random.randint(30000, 60000),
        dst_port    = random.choice([22, 445, 3389, 135, 137, 139, 3306]),
        protocol    = "TCP",
        packet_size = random.randint(200, 1400),
        ttl         = random.randint(40, 70),
        tcp_window  = random.randint(8192, 40960),
        syn         = int(random.random() < 0.30),
        ack=1,
        rst         = int(random.random() < 0.08),
        fin         = int(random.random() < 0.18),
        attack_type = "LateralMovement",
        label       = 1,
    )


def _pkt_c2(ts: datetime, ctx: dict) -> dict:
    """Periodic beacon: compromised internal host calls external C2."""
    return dict(
        timestamp   = ts,
        src_ip      = random.choice(ctx["internal"]),
        dst_ip      = random.choice(ctx["c2_hosts"]),
        src_port    = random.randint(30000, 60000),
        dst_port    = random.choice([80, 443, 8080, 8443]),
        protocol    = "TCP",
        packet_size = random.randint(50, 380),
        ttl         = random.randint(40, 70),
        tcp_window  = random.randint(2048, 16384),
        syn         = int(random.random() < 0.08),
        ack=1, rst=0, fin=0,
        attack_type = "CommandAndControl",
        label       = 1,
    )


PKT_GEN = {
    "Benign":            _pkt_benign,
    "Reconnaissance":    _pkt_recon,
    "BruteForce":        _pkt_bruteforce,
    "LateralMovement":   _pkt_lateral,
    "CommandAndControl": _pkt_c2,
}


# ============================================================
# Neighbouring-stage label noise
# ============================================================

def apply_label_noise(
    stages: list[str],
    noise_rate: float,
    seed: int,
) -> list[str]:
    """
    Replace ~noise_rate fraction of stage labels with a plausible
    neighbour (±1 in STAGE_ORDER).  Benign only confused with Recon;
    C&C only confused with LateralMovement.
    """
    local_rng = np.random.default_rng(seed)
    noisy = stages.copy()
    for i, s in enumerate(stages):
        if local_rng.random() < noise_rate:
            idx        = STAGE_ORDER.index(s)
            lo         = max(0, idx - 1)
            hi         = min(len(STAGE_ORDER) - 1, idx + 1)
            candidates = [STAGE_ORDER[j] for j in range(lo, hi + 1) if j != idx]
            if candidates:
                noisy[i] = local_rng.choice(candidates)
    return noisy


# ============================================================
# Campaign schedule builder
# Returns flat list of (stage, n_events) segments
# ============================================================

def build_campaign_schedule(
    total_events: int,
    n_campaigns:  int,
    seed:         int,
) -> list[tuple[str, int]]:
    """
    Sample per-campaign stage weights from Gaussians then scale to
    total_events.  A minimum of 80 events per stage segment prevents
    degenerate campaigns.
    """
    loc_rng = np.random.default_rng(seed)
    MIN_EVT = 80

    # Sample raw weights for every segment across all campaigns
    raw: list[float] = []
    for _ in range(n_campaigns):
        g = float(np.clip(loc_rng.normal(GAP_WEIGHT[0], GAP_WEIGHT[1]),
                          0.02, 0.18))
        raw.append(g)
        for (_, w_mu, w_sigma) in STAGE_WEIGHTS:
            w = float(np.clip(loc_rng.normal(w_mu, w_sigma), 0.03, 0.40))
            raw.append(w)

    total_raw = sum(raw)
    schedule: list[tuple[str, int]] = []
    used = 0
    idx  = 0

    for c in range(n_campaigns):
        is_last = (c == n_campaigns - 1)

        # Gap / inter-campaign benign
        gap_n = max(MIN_EVT, round(raw[idx] / total_raw * total_events))
        schedule.append(("Benign", gap_n))
        used += gap_n
        idx  += 1

        for s_i, (stage, _, _) in enumerate(STAGE_WEIGHTS):
            last_segment = is_last and (s_i == len(STAGE_WEIGHTS) - 1)
            if last_segment:
                n_ev = max(MIN_EVT, total_events - used)
            else:
                n_ev = max(MIN_EVT, round(raw[idx] / total_raw * total_events))
            schedule.append((stage, n_ev))
            used += n_ev
            idx  += 1

    return schedule


# ============================================================
# Packet telemetry generator
# ============================================================

def generate_packets(
    schedule: list[tuple[str, int]],
    campaign_contexts: list[dict],
) -> list[dict]:
    """
    Emit one packet event per schedule slot.
    IAT is jittered per campaign (ctx["iat_scale"]).
    Label noise is applied over the full sequence.
    """
    # Build true stage sequence
    true_stages: list[str] = []
    campaign_of_event: list[int] = []

    # Map schedule segments to campaign index
    # Segments layout: for each campaign c:
    #   segment[c * (1+S)]         = gap (Benign)
    #   segment[c * (1+S) + 1 ..S] = the S attack stages
    n_stages = len(STAGE_WEIGHTS)
    segs_per_campaign = 1 + n_stages  # gap + 5 stages

    for seg_idx, (stage, n_ev) in enumerate(schedule):
        c_idx = seg_idx // segs_per_campaign
        true_stages.extend([stage] * n_ev)
        campaign_of_event.extend([c_idx] * n_ev)

    noisy_stages = apply_label_noise(true_stages, NOISE_RATE, RANDOM_SEED + 1)

    events: list[dict] = []
    current_time = START_TIME
    total = len(true_stages)

    for i in range(total):
        c_idx  = campaign_of_event[i]
        ctx    = campaign_contexts[c_idx]
        stage  = noisy_stages[i]       # use noisy stage for generation

        ev = PKT_GEN[stage](current_time, ctx)
        ev["attack_type"] = stage
        ev["label"]       = LABEL_MAP[stage]
        events.append(ev)

        # Per-stage base IAT scaled by campaign IAT multiplier
        true_stage = true_stages[i]   # use true stage for timing rhythm
        iat_lo, iat_hi = IAT_BASE[true_stage]
        scale   = ctx["iat_scale"]
        lo_s    = max(1, int(iat_lo * scale))
        hi_s    = max(lo_s + 1, int(iat_hi * scale))
        current_time += timedelta(milliseconds=random.randint(lo_s, hi_s))

    return events


# ============================================================
# Flow feature parameters per stage
# ============================================================

FLOW_STAGE_PARAMS: dict[str, dict] = {
    "Benign": dict(
        flow_duration_log = (math.log(280),  0.60),
        fwd_pkt_lambda    = 4,
        bwd_pkt_lambda    = 3,
        fwd_len_mu        = 580,  fwd_len_sigma  = 130,
        bwd_len_mu        = 480,  bwd_len_sigma  = 110,
        syn_prob          = 0.08,
        rst_prob          = 0.02,
        fin_prob          = 0.12,
        dst_port_probs    = [0.03, 0.02, 0.04, 0.02, 0.28, 0.06, 0.22,
                             0.06, 0.04, 0.04, 0.03, 0.06, 0.04, 0.02, 0.01, 0.02, 0.01],
    ),
    "Reconnaissance": dict(
        flow_duration_log = (math.log(18),   0.50),   # short probe
        fwd_pkt_lambda    = 2,
        bwd_pkt_lambda    = 1,
        fwd_len_mu        = 72,   fwd_len_sigma  = 28,
        bwd_len_mu        = 55,   bwd_len_sigma  = 20,
        syn_prob          = 0.92,
        rst_prob          = 0.62,
        fin_prob          = 0.01,
        dst_port_probs    = [0.06, 0.08, 0.04, 0.03, 0.10, 0.22, 0.06,
                             0.08, 0.08, 0.06, 0.03, 0.06, 0.05, 0.02, 0.02, 0.05, 0.06],
    ),
    "BruteForce": dict(
        flow_duration_log = (math.log(140),  0.50),
        fwd_pkt_lambda    = 9,
        bwd_pkt_lambda    = 7,
        fwd_len_mu        = 280,  fwd_len_sigma  = 80,
        bwd_len_mu        = 230,  bwd_len_sigma  = 70,
        syn_prob          = 0.52,
        rst_prob          = 0.20,
        fin_prob          = 0.16,
        dst_port_probs    = [0.10, 0.28, 0.08, 0.04, 0.04, 0.12, 0.02,
                             0.04, 0.04, 0.04, 0.06, 0.04, 0.04, 0.02, 0.02, 0.01, 0.01],
    ),
    "LateralMovement": dict(
        flow_duration_log = (math.log(480),  0.60),
        fwd_pkt_lambda    = 11,
        bwd_pkt_lambda    = 9,
        fwd_len_mu        = 680,  fwd_len_sigma  = 160,
        bwd_len_mu        = 620,  bwd_len_sigma  = 140,
        syn_prob          = 0.32,
        rst_prob          = 0.09,
        fin_prob          = 0.20,
        dst_port_probs    = [0.04, 0.06, 0.03, 0.02, 0.06, 0.08, 0.02,
                             0.08, 0.10, 0.08, 0.02, 0.06, 0.28, 0.04, 0.06, 0.04, 0.03],
    ),
    "CommandAndControl": dict(
        flow_duration_log = (math.log(550),  0.50),   # periodic beacon flows
        fwd_pkt_lambda    = 3,
        bwd_pkt_lambda    = 2,
        fwd_len_mu        = 195,  fwd_len_sigma  = 48,
        bwd_len_mu        = 170,  bwd_len_sigma  = 38,
        syn_prob          = 0.09,
        rst_prob          = 0.01,
        fin_prob          = 0.02,
        dst_port_probs    = [0.02, 0.02, 0.02, 0.02, 0.06, 0.34, 0.02,
                             0.02, 0.02, 0.02, 0.02, 0.36, 0.02, 0.01, 0.01, 0.06, 0.02],
    ),
}

# Sanity-check port probability vectors sum to 1
for _s, _p in FLOW_STAGE_PARAMS.items():
    _arr = np.array(_p["dst_port_probs"], dtype=float)
    assert len(_arr) == len(COMMON_PORTS), \
        f"Port prob length mismatch for {_s}: {len(_arr)} vs {len(COMMON_PORTS)}"
    _p["dst_port_probs"] = (_arr / _arr.sum()).tolist()


# ============================================================
# Flow telemetry generator
# ============================================================

def generate_flows(
    packet_timestamps:   list[datetime],
    true_stage_sequence: list[str],
    campaign_of_event:   list[int],
    campaign_contexts:   list[dict],
) -> pd.DataFrame:
    """
    Build one flow record per packet event on the same timestamp spine.
    Flow features are drawn from per-stage distributions, further jittered
    by per-campaign intensity offset so campaigns differ statistically.
    """
    n            = len(packet_timestamps)
    noisy_stages = apply_label_noise(true_stage_sequence, NOISE_RATE, RANDOM_SEED + 2)

    timestamps = pd.to_datetime(
        [ts.strftime("%Y-%m-%d %H:%M:%S.%f") for ts in packet_timestamps]
    )

    # Pre-allocate output arrays
    flow_dur_arr   = np.empty(n)
    fwd_pkts_arr   = np.empty(n, dtype=int)
    bwd_pkts_arr   = np.empty(n, dtype=int)
    fwd_bytes_arr  = np.empty(n)
    bwd_bytes_arr  = np.empty(n)
    iat_mean_arr   = np.empty(n)
    iat_std_arr    = np.empty(n)
    plen_mean_arr  = np.empty(n)
    plen_std_arr   = np.empty(n)
    syn_arr        = np.zeros(n, dtype=int)
    ack_arr        = np.zeros(n, dtype=int)
    rst_arr        = np.zeros(n, dtype=int)
    fin_arr        = np.zeros(n, dtype=int)
    dst_port_arr   = np.empty(n, dtype=int)
    src_port_arr   = rng.integers(1024, 65535, size=n)
    protocol_arr   = np.empty(n, dtype=object)
    src_ip_arr     = np.empty(n, dtype=object)
    dst_ip_arr     = np.empty(n, dtype=object)

    indices = np.arange(n)

    for stage in STAGE_ORDER:
        mask = np.array([s == stage for s in noisy_stages], dtype=bool)
        if not mask.any():
            continue

        p   = FLOW_STAGE_PARAMS[stage]
        cnt = int(mask.sum())
        idx = indices[mask]

        # Per-campaign intensity offsets for events in this stage
        c_offsets = np.array(
            [campaign_contexts[campaign_of_event[i]]["intensity_offset"]
             for i in idx])
        base_inten = {"Benign": 0.15, "Reconnaissance": 0.42,
                      "BruteForce": 0.65, "LateralMovement": 0.78,
                      "CommandAndControl": 0.55}[stage]
        inten = np.clip(
            rng.normal(base_inten, 0.07, cnt) + c_offsets, 0.02, 1.0)

        # Flow duration (log-normal, jittered by intensity)
        log_mu  = p["flow_duration_log"][0] + 0.3 * (inten - base_inten)
        log_sig = p["flow_duration_log"][1]
        flow_dur_arr[mask] = np.clip(
            rng.lognormal(log_mu, log_sig), 1.0, 90_000.0)

        # Packet counts
        fwd_p = np.maximum(1, rng.poisson(p["fwd_pkt_lambda"] * (0.6 + 0.8*inten), cnt))
        bwd_p = np.maximum(0, rng.poisson(p["bwd_pkt_lambda"] * (0.6 + 0.8*inten), cnt))
        fwd_pkts_arr[mask] = fwd_p
        bwd_pkts_arr[mask] = bwd_p

        # Packet lengths (per-campaign size variation via intensity)
        fwd_len = np.clip(
            rng.normal(p["fwd_len_mu"] * (0.8 + 0.4*inten), p["fwd_len_sigma"], cnt),
            40, 1500)
        bwd_len = np.clip(
            rng.normal(p["bwd_len_mu"] * (0.8 + 0.4*inten), p["bwd_len_sigma"], cnt),
            40, 1500)

        fwd_bytes_arr[mask] = np.maximum(40, fwd_p * fwd_len)
        bwd_bytes_arr[mask] = np.maximum(0,  bwd_p * bwd_len)

        # IAT features
        dur_s = np.maximum(flow_dur_arr[mask] / 1000.0, 0.001)
        tot_p = (fwd_p + bwd_p).astype(float)
        iat_m = dur_s / np.maximum(tot_p - 1.0, 1.0)
        iat_mean_arr[mask] = np.maximum(0.001, iat_m)
        iat_std_arr[mask]  = np.maximum(0.001,
            iat_m * rng.uniform(0.10, 0.80, cnt))

        # Packet length stats
        tot_bytes = fwd_bytes_arr[mask] + bwd_bytes_arr[mask]
        plen_mean_arr[mask] = tot_bytes / np.maximum(tot_p, 1.0)
        plen_std_arr[mask]  = np.clip(
            rng.normal(
                (p["fwd_len_sigma"] + p["bwd_len_sigma"]) / 2.0, 20.0, cnt),
            5.0, 400.0)

        # Protocol
        tcp_flag = rng.random(cnt) < (0.65 + 0.20 * inten)
        protocol_arr[mask] = np.where(
            tcp_flag, "TCP",
            np.where(rng.random(cnt) < 0.68, "UDP", "ICMP"))

        # TCP flags
        syn_arr[mask] = (tcp_flag & (rng.random(cnt) < p["syn_prob"])).astype(int)
        ack_base = np.maximum(1, rng.binomial(
            (fwd_p + bwd_p).astype(int),
            np.clip(0.55 - 0.25 * inten, 0.05, 0.92)))
        ack_arr[mask] = (tcp_flag * ack_base).astype(int)
        rst_arr[mask] = (tcp_flag & (rng.random(cnt) < p["rst_prob"])).astype(int)
        fin_arr[mask] = (tcp_flag & (rng.random(cnt) < p["fin_prob"])).astype(int)

        # Destination ports
        port_probs = np.array(p["dst_port_probs"], dtype=float)
        dst_port_arr[mask] = rng.choice(COMMON_PORTS, size=cnt, p=port_probs)

        # IP addresses (use campaign context)
        if stage == "Benign":
            src_ip_arr[mask] = np.array(
                [random.choice(campaign_contexts[campaign_of_event[i]]["clients"])
                 for i in idx])
            dst_ip_arr[mask] = np.array(
                [random.choice(campaign_contexts[campaign_of_event[i]]["servers"])
                 for i in idx])
        elif stage in ("Reconnaissance", "BruteForce"):
            src_ip_arr[mask] = np.array(
                [campaign_contexts[campaign_of_event[i]]["attacker"] for i in idx])
            dst_ip_arr[mask] = np.array(
                [random.choice(campaign_contexts[campaign_of_event[i]]["servers"])
                 for i in idx])
        elif stage == "LateralMovement":
            src_ip_arr[mask] = np.array(
                [campaign_contexts[campaign_of_event[i]]["attacker"] for i in idx])
            dst_ip_arr[mask] = np.array(
                [random.choice(
                    campaign_contexts[campaign_of_event[i]]["internal"] +
                    campaign_contexts[campaign_of_event[i]]["clients"])
                 for i in idx])
        else:  # CommandAndControl
            src_ip_arr[mask] = np.array(
                [random.choice(campaign_contexts[campaign_of_event[i]]["internal"])
                 for i in idx])
            dst_ip_arr[mask] = np.array(
                [random.choice(campaign_contexts[campaign_of_event[i]]["c2_hosts"])
                 for i in idx])

    # ── Derived columns ────────────────────────────────────────────────
    total_bytes = fwd_bytes_arr + bwd_bytes_arr
    total_pkts  = fwd_pkts_arr  + bwd_pkts_arr
    dur_s       = np.maximum(flow_dur_arr / 1000.0, 0.001)

    labels = np.array([LABEL_MAP[s] for s in noisy_stages])

    df = pd.DataFrame({
        "timestamp":            timestamps,
        "src_ip":               src_ip_arr,
        "dst_ip":               dst_ip_arr,
        "src_port":             src_port_arr,
        "dst_port":             dst_port_arr,
        "protocol":             protocol_arr,
        "flow_duration":        np.round(flow_dur_arr,           2),
        "total_fwd_packets":    fwd_pkts_arr,
        "total_bwd_packets":    bwd_pkts_arr,
        "fwd_bytes":            np.round(fwd_bytes_arr,          2),
        "bwd_bytes":            np.round(bwd_bytes_arr,          2),
        "total_bytes":          np.round(total_bytes,            2),
        "flow_bytes_per_sec":   np.round(total_bytes / dur_s,    2),
        "flow_packets_per_sec": np.round(total_pkts  / dur_s,    2),
        "flow_iat_mean":        np.round(iat_mean_arr,           6),
        "flow_iat_std":         np.round(iat_std_arr,            6),
        "packet_length_mean":   np.round(plen_mean_arr,          2),
        "packet_length_std":    np.round(plen_std_arr,           2),
        "fwd_packets_per_sec":  np.round(fwd_pkts_arr / dur_s,  2),
        "bwd_packets_per_sec":  np.round(bwd_pkts_arr / dur_s,  2),
        "down_up_ratio":        np.round(
            bwd_pkts_arr / np.maximum(fwd_pkts_arr, 1), 4),
        "syn_flag_count":       syn_arr,
        "ack_flag_count":       ack_arr,
        "rst_flag_count":       rst_arr,
        "fin_flag_count":       fin_arr,
        "attack_stage":         noisy_stages,
        "label":                labels,
    })

    return df


# ============================================================
# Validation report
# ============================================================

def print_validation_report(
    pkt_events:       list[dict],
    flow_df:          pd.DataFrame,
    n_campaigns:      int,
    window_seconds:   int = 10,
) -> None:
    pkt_df = pd.DataFrame(pkt_events)
    pkt_df["timestamp"] = pd.to_datetime(pkt_df["timestamp"])

    sep = "=" * 68

    print(sep)
    print("  TEMPORAL TRAFFIC SIMULATOR — VALIDATION REPORT")
    print(sep)

    # ── Record counts ──────────────────────────────────────────────────
    print(f"\n{'Packet records':<36} {len(pkt_df):>12,}")
    print(f"{'Flow records':<36} {len(flow_df):>12,}")

    # ── Timestamp range ────────────────────────────────────────────────
    for name, ts_col, df_chk in [
        ("Packet", "timestamp", pkt_df),
        ("Flow",   "timestamp", flow_df),
    ]:
        ts = pd.to_datetime(df_chk[ts_col])
        print(f"\n{name} timestamp range:")
        print(f"  start : {ts.min()}")
        print(f"  end   : {ts.max()}")
        print(f"  span  : {ts.max() - ts.min()}")

    # ── Campaign count ─────────────────────────────────────────────────
    print(f"\n{'Attack campaigns':<36} {n_campaigns:>12}")

    # ── Approximate 10-second state windows ───────────────────────────
    ts_pkt = pd.to_datetime(pkt_df["timestamp"])
    n_windows = len(pd.Series(ts_pkt.dt.floor(f"{window_seconds}s").unique()))
    print(f"{'Approx 10-s windows (packets)':<36} {n_windows:>12,}")

    # ── Overall stage distribution ─────────────────────────────────────
    print("\nPacket stage distribution:")
    for stage in STAGE_ORDER:
        cnt = (pkt_df["attack_type"] == stage).sum()
        pct = cnt / len(pkt_df) * 100
        print(f"  {stage:<24} {cnt:>10,}  ({pct:5.1f} %)")

    print("\nFlow stage distribution:")
    for stage in STAGE_ORDER:
        cnt = (flow_df["attack_stage"] == stage).sum()
        pct = cnt / len(flow_df) * 100
        print(f"  {stage:<24} {cnt:>10,}  ({pct:5.1f} %)")

    # ── Label distribution ─────────────────────────────────────────────
    print("\nPacket label distribution (0=benign, 1=attack):")
    for lbl, cnt in pkt_df["label"].value_counts().sort_index().items():
        print(f"  label {lbl}: {cnt:>10,}  ({cnt/len(pkt_df)*100:5.1f} %)")

    print("\nFlow label distribution (0=benign, 1=attack):")
    for lbl, cnt in flow_df["label"].value_counts().sort_index().items():
        print(f"  label {lbl}: {cnt:>10,}  ({cnt/len(flow_df)*100:5.1f} %)")

    # ── Stage distribution by temporal region ─────────────────────────
    print("\nStage distribution by temporal region (packet):")
    n = len(pkt_df)
    boundaries = [(0, n//3, "Early (0-33%)"),
                  (n//3, 2*n//3, "Mid   (33-67%)"),
                  (2*n//3, n, "Late  (67-100%)")]
    for lo, hi, label in boundaries:
        region   = pkt_df.iloc[lo:hi]
        stage_ct = region["attack_type"].value_counts()
        stages   = [f"{s}:{stage_ct.get(s,0)}" for s in STAGE_ORDER]
        print(f"  {label}: {', '.join(stages)}")

    # ── Missing values ─────────────────────────────────────────────────
    print(f"\n{'Packet missing values':<36} {pkt_df.isnull().sum().sum():>12,}")
    print(f"{'Flow missing values':<36} {flow_df.isnull().sum().sum():>12,}")

    # ── Chronological split stage coverage ────────────────────────────
    print("\nChronological 70/15/15 split stage coverage:")
    for ds_name, df_chk, stage_col in [
        ("Packets", pkt_df, "attack_type"),
        ("Flows",   flow_df, "attack_stage"),
    ]:
        n  = len(df_chk)
        t  = int(n * 0.70)
        v  = int(n * 0.85)
        print(f"\n  {ds_name}:")
        for split_name, sdf in [
            ("Train", df_chk.iloc[:t]),
            ("Val",   df_chk.iloc[t:v]),
            ("Test",  df_chk.iloc[v:]),
        ]:
            stages_present = sorted(str(s) for s in sdf[stage_col].unique())
            print(f"    {split_name:<6} ({len(sdf):>8,} records): {stages_present}")

    # ── First few rows ─────────────────────────────────────────────────
    print("\nPacket telemetry — first 5 rows:")
    print(pkt_df[["timestamp", "src_ip", "dst_ip", "protocol",
                   "packet_size", "syn", "attack_type", "label"]]
          .head().to_string(index=False))

    print("\nFlow telemetry — first 5 rows:")
    print(flow_df[["timestamp", "src_ip", "dst_ip", "protocol",
                    "flow_duration", "total_bytes",
                    "attack_stage", "label"]]
          .head().to_string(index=False))

    print(f"\n{sep}")
    print(f"  Packets -> {PACKET_FILE}")
    print(f"  Flows   -> {FLOW_FILE}")
    print(sep)


# ============================================================
# Main
# ============================================================

def main() -> None:
    print(f"Building campaign schedule ({NUM_CAMPAIGNS} campaigns, "
          f"target {NUM_EVENTS:,} events) ...")
    schedule = build_campaign_schedule(
        total_events = NUM_EVENTS,
        n_campaigns  = NUM_CAMPAIGNS,
        seed         = RANDOM_SEED,
    )
    total_scheduled = sum(n for _, n in schedule)
    print(f"  Scheduled {total_scheduled:,} events")

    # ── Per-campaign contexts ───────────────────────────────────────────
    print("Sampling per-campaign network contexts ...")
    campaign_contexts = [
        sample_campaign_context(c) for c in range(NUM_CAMPAIGNS)
    ]

    # ── Build campaign-of-event index ──────────────────────────────────
    n_stages_per_seg = 1 + len(STAGE_WEIGHTS)  # gap + 5 attack stages
    campaign_of_event: list[int] = []
    for seg_idx, (_, n_ev) in enumerate(schedule):
        c_idx = seg_idx // n_stages_per_seg
        campaign_of_event.extend([c_idx] * n_ev)

    # ── True stage sequence ────────────────────────────────────────────
    true_stage_seq: list[str] = []
    for (stage, n_ev) in schedule:
        true_stage_seq.extend([stage] * n_ev)

    # ── Packet telemetry ────────────────────────────────────────────────
    print("Generating packet telemetry ...")
    pkt_events = generate_packets(schedule, campaign_contexts)

    # ── Flow telemetry ──────────────────────────────────────────────────
    print("Generating flow telemetry ...")
    pkt_timestamps = [e["timestamp"] for e in pkt_events]
    flow_df = generate_flows(
        pkt_timestamps, true_stage_seq,
        campaign_of_event, campaign_contexts,
    )

    # ── Save packets ────────────────────────────────────────────────────
    print("Writing packet CSV ...")
    PKT_FIELDS = [
        "timestamp", "src_ip", "dst_ip", "src_port", "dst_port",
        "protocol", "packet_size", "ttl", "tcp_window",
        "syn", "ack", "rst", "fin",
        "attack_type", "label",
    ]
    with open(PACKET_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PKT_FIELDS)
        writer.writeheader()
        for ev in pkt_events:
            ev["timestamp"] = ev["timestamp"].strftime("%Y-%m-%d %H:%M:%S.%f")
            writer.writerow(ev)

    # ── Save flows ──────────────────────────────────────────────────────
    print("Writing flow CSV ...")
    flow_df.to_csv(FLOW_FILE, index=False)

    # ── Validation report ───────────────────────────────────────────────
    print_validation_report(pkt_events, flow_df, NUM_CAMPAIGNS)


if __name__ == "__main__":
    main()
