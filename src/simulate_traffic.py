import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


# ============================================================
# Configuration
# ============================================================

OUTPUT = Path("data/simulated/simulated_packets.csv")

NUM_EVENTS = 50000
START_TIME = datetime(2026, 9, 1, 10, 0, 0)

random.seed(42)


# ============================================================
# Network entities
# ============================================================

BENIGN_CLIENTS = [
    "10.0.1.10",
    "10.0.1.11",
    "10.0.1.12",
    "10.0.1.13",
    "10.0.1.14",
]

SERVERS = [
    "10.0.2.10",
    "10.0.2.11",
    "10.0.2.12",
]

COMMON_PORTS = [
    80,
    443,
    53,
    22,
    25,
    110,
    123,
]

ATTACKER = "10.0.9.100"


# ============================================================
# Event generation
# ============================================================

def generate_benign_event(timestamp):
    src = random.choice(BENIGN_CLIENTS)
    dst = random.choice(SERVERS)

    protocol = random.choice(["TCP", "TCP", "TCP", "UDP"])

    if protocol == "TCP":
        dst_port = random.choice([80, 443, 22])
        syn = random.choice([0, 0, 1])
        ack = random.choice([1, 1, 1, 0])
        rst = random.choice([0, 0, 0, 1])
        fin = random.choice([0, 0, 1])
        window = random.randint(16000, 65535)
    else:
        dst_port = random.choice([53, 123])
        syn = 0
        ack = 0
        rst = 0
        fin = 0
        window = 0

    packet_size = random.randint(60, 1400)
    ttl = random.randint(50, 128)

    return {
        "timestamp": timestamp,
        "src_ip": src,
        "dst_ip": dst,
        "src_port": random.randint(1024, 65535),
        "dst_port": dst_port,
        "protocol": protocol,
        "packet_size": packet_size,
        "ttl": ttl,
        "tcp_window": window,
        "syn": syn,
        "ack": ack,
        "rst": rst,
        "fin": fin,
        "attack_type": "Benign",
        "label": 0,
    }


def generate_recon_event(timestamp):
    return {
        "timestamp": timestamp,
        "src_ip": ATTACKER,
        "dst_ip": random.choice(SERVERS),
        "src_port": random.randint(30000, 60000),
        "dst_port": random.randint(1, 1024),
        "protocol": "TCP",
        "packet_size": random.randint(40, 100),
        "ttl": random.randint(45, 70),
        "tcp_window": random.randint(1000, 10000),
        "syn": 1,
        "ack": 0,
        "rst": random.choice([0, 1]),
        "fin": 0,
        "attack_type": "Reconnaissance",
        "label": 1,
    }


def generate_bruteforce_event(timestamp):
    return {
        "timestamp": timestamp,
        "src_ip": ATTACKER,
        "dst_ip": random.choice(SERVERS),
        "src_port": random.randint(30000, 60000),
        "dst_port": random.choice([22, 21]),
        "protocol": "TCP",
        "packet_size": random.randint(100, 800),
        "ttl": random.randint(40, 70),
        "tcp_window": random.randint(2000, 20000),
        "syn": random.choice([0, 1]),
        "ack": 1,
        "rst": random.choice([0, 0, 1]),
        "fin": random.choice([0, 1]),
        "attack_type": "BruteForce",
        "label": 1,
    }


def generate_lateral_event(timestamp):
    return {
        "timestamp": timestamp,
        "src_ip": ATTACKER,
        "dst_ip": random.choice(BENIGN_CLIENTS + SERVERS),
        "src_port": random.randint(30000, 60000),
        "dst_port": random.choice([22, 445, 3389]),
        "protocol": "TCP",
        "packet_size": random.randint(200, 1400),
        "ttl": random.randint(40, 70),
        "tcp_window": random.randint(5000, 40000),
        "syn": random.choice([0, 1]),
        "ack": 1,
        "rst": random.choice([0, 0, 1]),
        "fin": random.choice([0, 1]),
        "attack_type": "LateralMovement",
        "label": 1,
    }


def generate_c2_event(timestamp):
    return {
        "timestamp": timestamp,
        "src_ip": ATTACKER,
        "dst_ip": random.choice(SERVERS),
        "src_port": random.randint(30000, 60000),
        "dst_port": random.choice([80, 443, 8080]),
        "protocol": "TCP",
        "packet_size": random.randint(50, 500),
        "ttl": random.randint(40, 70),
        "tcp_window": random.randint(2000, 30000),
        "syn": random.choice([0, 0, 1]),
        "ack": 1,
        "rst": 0,
        "fin": 0,
        "attack_type": "CommandAndControl",
        "label": 1,
    }


# ============================================================
# Generate timeline
# ============================================================

events = []

current_time = START_TIME

for i in range(NUM_EVENTS):

    # 0 - 30%: benign
    # 30 - 45%: reconnaissance
    # 45 - 60%: brute force
    # 60 - 75%: lateral movement
    # 75 - 100%: command and control

    progress = i / NUM_EVENTS

    if progress < 0.30:
        event = generate_benign_event(current_time)

    elif progress < 0.45:
        event = generate_recon_event(current_time)

    elif progress < 0.60:
        event = generate_bruteforce_event(current_time)

    elif progress < 0.75:
        event = generate_lateral_event(current_time)

    else:
        event = generate_c2_event(current_time)

    events.append(event)

    # Variable inter-arrival time
    current_time += timedelta(
        milliseconds=random.randint(1, 500)
    )


# ============================================================
# Write CSV
# ============================================================

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

fieldnames = [
    "timestamp",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "protocol",
    "packet_size",
    "ttl",
    "tcp_window",
    "syn",
    "ack",
    "rst",
    "fin",
    "attack_type",
    "label",
]

with open(OUTPUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(events)


print("=" * 60)
print("SIMULATION COMPLETE")
print("=" * 60)
print(f"Output : {OUTPUT}")
print(f"Events : {len(events)}")
print()
print("Attack progression:")
print("Benign → Reconnaissance → BruteForce →")
print("LateralMovement → CommandAndControl")
print("=" * 60)