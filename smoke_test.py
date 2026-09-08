"""
smoke_test.py — Import and logic verification.
Run: python smoke_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("── Import check ────────────────────────────────────")
modules = [
    "frontend.utils.constants",
    "frontend.services.data_loader",
    "frontend.services.mock_predictions",
    "frontend.services.state_builder",
    "frontend.components.metrics",
    "frontend.components.charts",
    "frontend.components.risk_cards",
    "frontend.components.device_table",
    "frontend.components.alert_cards",
    "frontend.components.attack_path",
    "frontend.pages.dashboard",
    "frontend.pages.upload",
    "frontend.pages.network_state",
    "frontend.pages.forecast",
    "frontend.pages.attack_stages",
    "frontend.pages.alerts",
    "frontend.pages.explainability",
    "frontend.pages.performance",
    "frontend.pages.system",
]

errors = []
for m in modules:
    try:
        __import__(m)
        print(f"  OK  {m}")
    except Exception as exc:
        errors.append((m, str(exc)))
        print(f"  ERR {m}: {exc}")

if errors:
    print(f"\nFAILED: {len(errors)} import error(s)")
    sys.exit(1)

print("\n── Data pipeline ───────────────────────────────────")

from frontend.services.data_loader import load_default_simulated, get_summary_stats

df = load_default_simulated()
assert df is not None, "Dataset failed to load"
assert len(df) == 50_000, f"Expected 50 000 rows, got {len(df)}"
print(f"  OK  Dataset: {len(df):,} rows  columns={list(df.columns)}")

stats = get_summary_stats(df)
assert stats["total_records"] == 50_000
assert stats["unique_src_ips"] > 0
print(f"  OK  Stats: {stats['total_records']:,} records, "
      f"{stats['unique_src_ips']} src IPs, "
      f"attack_ratio={stats['attack_ratio']:.2%}")

print("\n── State builder ───────────────────────────────────")

from frontend.services.state_builder import get_current_state, build_state_sequence

state = get_current_state(df)
assert "syn_rate" in state
assert "avg_packet_size" in state
print(f"  OK  State: syn_rate={state['syn_rate']}, avg_pkt={state['avg_packet_size']}")

seq = build_state_sequence(df, n_windows=5)
assert len(seq) == 5
print(f"  OK  Sequence: {len(seq)} windows")

print("\n── Mock predictions ────────────────────────────────")

from frontend.services.mock_predictions import get_mock_prediction, get_mock_model_performance

pred = get_mock_prediction(df)
assert pred.overall_risk > 0
assert len(pred.risky_devices) > 0
assert len(pred.security_alerts) > 0
assert len(pred.future_probabilities) == 5
print(f"  OK  Risk: {pred.overall_risk:.0%}  stage: {pred.current_stage} → {pred.predicted_stage}")
print(f"  OK  Devices: {len(pred.risky_devices)}  Alerts: {len(pred.security_alerts)}")

perf = get_mock_model_performance()
assert "world_model" in perf and "logistic_regression" in perf
wm_f1 = perf["world_model"]["f1_score"]
lr_f1 = perf["logistic_regression"]["f1_score"]
print(f"  OK  WM F1={wm_f1}  LR F1={lr_f1}")

print("\n── Chart builders ──────────────────────────────────")
from frontend.components.charts import (
    risk_timeline_chart, protocol_pie_chart, attack_distribution_bar,
    stage_forecast_chart, feature_importance_chart, model_comparison_chart,
    network_state_radar, state_sequence_chart, traffic_volume_chart,
)

fig = risk_timeline_chart(["T0","T1","T2"], [0.3, 0.6, 0.87])
assert fig is not None
print("  OK  risk_timeline_chart")

fig = protocol_pie_chart({"TCP": 35000, "UDP": 12000, "ICMP": 3000})
assert fig is not None
print("  OK  protocol_pie_chart")

fig = attack_distribution_bar({"Benign": 20000, "Reconnaissance": 10000})
assert fig is not None
print("  OK  attack_distribution_bar")

fig = stage_forecast_chart(pred.future_probabilities)
assert fig is not None
print("  OK  stage_forecast_chart")

fig = feature_importance_chart(pred.contributing_features)
assert fig is not None
print("  OK  feature_importance_chart")

fig = model_comparison_chart(perf)
assert fig is not None
print("  OK  model_comparison_chart")

fig = network_state_radar(state)
assert fig is not None
print("  OK  network_state_radar")

fig = state_sequence_chart(seq)
assert fig is not None
print("  OK  state_sequence_chart")

fig = traffic_volume_chart(df.head(5000))
assert fig is not None
print("  OK  traffic_volume_chart")

print("\n" + "=" * 52)
print("  ALL SMOKE TESTS PASSED")
print("=" * 52)
