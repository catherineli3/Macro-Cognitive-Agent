"""Quick M1 pipeline smoke test."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data_pipeline.macro_pipeline import MacroPipeline

pipeline = MacroPipeline()
print("Running M1 pipeline with real Yahoo Finance data...")
snapshot = pipeline.build_daily_macro_snapshot()
print("SUCCESS!\n")

print("=== State Vector ===")
sv = snapshot.get("state_vector", {})
for k, v in sv.items():
    score = v.get("score", 0)
    direction = v.get("direction", "?")
    confidence = v.get("confidence", 0)
    bar = "#" * int(score * 20) + "-" * (20 - int(score * 20))
    print(f"  {k:15s} [{bar}] {score:.2f}  {direction}  (conf={confidence:.2f})")

print(f"\nRisk Regime:    {snapshot.get('meta', {}).get('risk_regime')}")
print(f"Dominant Theme: {snapshot.get('meta', {}).get('dominant_theme')}")
print(f"Aggregate Score: {snapshot.get('meta', {}).get('aggregate_score', 0):.2f}")

qr = snapshot.get("quality_report", {})
print(f"\nQuality: {qr.get('valid', 0)} valid, {qr.get('degraded', 0)} degraded, {qr.get('failed', 0)} failed")
