#!/usr/bin/env python3
"""EarthPulse calibration harness — retrospective precision check.

Replays stored historical flood signatures (outcome = occurred) plus calm
counterfactual states (outcome = not occurred) through the SAME deterministic
probability function used in production, then reports Brier score, a reliability
diagram, and a Platt-style recalibration fit.

Run from backend/:
    uv run python -m scripts.calibrate        # writes calibration_report.json

Honesty note: the retrospective is built from the synthetic signature store, so
it validates *internal* consistency — the metric that makes it externally
meaningful is a real feed + ground-truth replay, which this harness is the
scaffold for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.calibration import calibrate_report, reliability  # noqa: E402
from app.ml.forecaster import probability_from_components  # noqa: E402
from app.services.environmental_memory import _features, memory_for  # noqa: E402


def build_retrospective() -> tuple[list[float], list[float]]:
    """Return (outcomes, predictions) from memory signatures + calm baselines."""
    y_true: list[float] = []
    y_pred: list[float] = []

    # Positive examples: every stored historical flood event that occurred
    features = _features("flood")
    for zone in ["velachery", "mylapore", "north_chennai", "other"]:
        mem = memory_for(zone)
        for ev in mem.events:
            if ev.hazard != "flood":
                continue
            comps = {k: ev.signature[k] for k in features}
            comps["citizen_pressure"] = 4.0
            y_true.append(1.0)
            y_pred.append(probability_from_components(comps))

    # Negative examples: calm states (low drivers) — no flood outcome
    calm_specs = [
        {"rain_intensity": 1.2, "soil_moisture": 1.0, "headroom_deficit": 0.8, "drainage_stress": 0.5, "citizen_pressure": 0.2},
        {"rain_intensity": 2.0, "soil_moisture": 1.8, "headroom_deficit": 1.2, "drainage_stress": 0.8, "citizen_pressure": 0.3},
        {"rain_intensity": 1.5, "soil_moisture": 1.4, "headroom_deficit": 1.0, "drainage_stress": 0.6, "citizen_pressure": 0.1},
        {"rain_intensity": 0.8, "soil_moisture": 0.9, "headroom_deficit": 0.6, "drainage_stress": 0.3, "citizen_pressure": 0.0},
        {"rain_intensity": 2.8, "soil_moisture": 2.2, "headroom_deficit": 1.6, "drainage_stress": 1.1, "citizen_pressure": 0.4},
    ]
    for i in range(12):
        spec = calm_specs[i % len(calm_specs)]
        y_true.append(0.0)
        y_pred.append(probability_from_components(spec))
    return y_true, y_pred


def main() -> None:
    y_true, y_pred = build_retrospective()
    report = calibrate_report(y_true, y_pred)
    report["reliability"] = reliability(y_true, y_pred, bins=5)
    report["applied_to_production"] = False  # recalib coefficients are advisory until enabled

    out = Path("calibration_report.json")
    out.write_text(json.dumps(report, indent=2))
    print(f"n={report['n']} base_rate={report['base_rate']}")
    print(f"brier: before={report['brier_before']} after={report['brier_after']}")
    print(f"reliability error: {report['reliability_error_before']}")
    print(f"recalib: bias={report['recalib_bias']} slope={report['recalib_slope']}")
    for row in report["reliability"]:
        print(f"  bin {row['bin']:7s} n={row['n']:3d} pred={row['mean_prediction']:.3f} observed={row['observed_frequency']:.3f}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
