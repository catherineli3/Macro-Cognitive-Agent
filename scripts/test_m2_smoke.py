"""Quick M2 Mental Model Library smoke test."""
import sys, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.research.models.model_registry import build_default_registry

registry = build_default_registry()
print(f"Registered {len(registry)} models: {registry.registered_models}")

# Build a test snapshot with some extremes
test_snap = {
    "state_vector": {
        "Liquidity": {"score": 0.25, "direction": "tightening", "confidence": 0.8, "drivers": ["DXY", "US10Y"]},
        "Credit": {"score": 0.30, "direction": "contraction", "confidence": 0.7, "drivers": ["HYG", "LQD"]},
        "Inflation": {"score": 0.75, "direction": "rising", "confidence": 0.7, "drivers": ["Gold", "Oil"]},
        "Growth": {"score": 0.70, "direction": "expansion", "confidence": 0.7, "drivers": ["Copper", "SP500"]},
        "Risk_Appetite": {"score": 0.35, "direction": "risk_off", "confidence": 0.8, "drivers": ["VIX"]},
        "Dollar": {"score": 0.80, "direction": "strengthening", "confidence": 0.7, "drivers": ["DXY"]},
        "Policy": {"score": 0.25, "direction": "hawkish", "confidence": 0.7, "drivers": ["US2Y", "US10Y"]},
        "AI_Capex": {"score": 0.75, "direction": "expansion", "confidence": 0.7, "drivers": ["NVDA", "ASML"]},
    },
    "feature_summary": {
        "indicators": {
            "DXY": {"raw_value": 106.5, "features": []},
            "US10Y": {"raw_value": 4.55, "features": []},
            "HYG": {"raw_value": 70.2, "features": []},
            "LQD": {"raw_value": 103.5, "features": []},
            "Gold": {"raw_value": 2050, "features": []},
            "Oil": {"raw_value": 88.5, "features": []},
            "Copper": {"raw_value": 4.62, "features": []},
            "SP500": {"raw_value": 4800, "features": []},
            "VIX": {"raw_value": 28.5, "features": []},
            "US2Y": {"raw_value": 4.80, "features": []},
            "NVDA": {"raw_value": 850, "features": []},
            "ASML": {"raw_value": 920, "features": []},
        }
    }
}

print("\nEvaluating models...\n")
try:
    conclusions = registry.evaluate_all(test_snap)
    for i, c in enumerate(conclusions, 1):
        conf_bar = "\u2605" * int(c.confidence * 5) + "\u2606" * (5 - int(c.confidence * 5))
        print(f"{i}. [{c.domain:12s}] {conf_bar} ({c.confidence:.2f})")
        print(f"   Score: {c.raw_score:.2f} | Direction: {c.direction}")
        print(f"   {c.conclusion[:100]}...")
        print(f"   Supporting evidence: {len(c.supporting_evidence)}, Contradicting: {len(c.contradicting_evidence)}")
        if c.narrative_seeds:
            print(f"   Narratives: {c.narrative_seeds[0][:60]}...")
        print()
    print(f"Total: {len(conclusions)} conclusions from {len(registry)} models")
except Exception as e:
    print("ERROR:", e)
    traceback.print_exc()
