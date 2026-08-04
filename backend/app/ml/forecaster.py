"""Streaming risk forecaster.

Holt-style exponential smoothing (Brown's double smoothing) over a per-location
risk-driving series, with residual-based quantile bands. Deterministic, dependency-
light, explainable — the right v1 for a demoable early-warning system. Upgrade path:
satellite-ml / Prophet behind the same interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np


@dataclass
class ForecastResult:
    series_t: list[datetime]
    mean: list[float]
    lower: list[float]
    upper: list[float]
    horizon_h: int
    model_name: str = "earthpulse-stream-v1"
    residual_std: float = 0.0


@dataclass
class Forecaster:
    alpha: float = 0.45  # level smoothing
    beta: float = 0.25  # trend smoothing
    window: int = 96
    quantile: float = 0.9

    def _smooth(self, x: np.ndarray) -> np.ndarray:
        """Brown's double exponential smoothing over the series."""
        n = len(x)
        if n == 0:
            return np.zeros(1)
        level, trend = float(x[0]), float(x[1] - x[0]) if n > 1 else 0.0
        smoothed = np.zeros(n)
        for i in range(n):
            if i > 0:
                new_level = self.alpha * x[i] + (1 - self.alpha) * (level + trend)
                trend = self.beta * (new_level - level) + (1 - self.beta) * trend
                level = new_level
            smoothed[i] = level + trend
        return smoothed

    def fit_forecast(self, values: list[float], t0: datetime, horizon_h: int = 24,
                     trend_decay: float = 0.0, bounded: bool = True) -> ForecastResult:
        """Brown smoothing forecast.

        `trend_decay` damps the trend per hour (exp decay) — long-horizon
        outlooks converge to the level instead of running away on a stale
        slope. `bounded=True` treats the series as a probability: growth is
        scaled by (1 - level) for rising trends and level for falling ones,
        so extrapolation asymptotes toward 0/1 instead of overshooting —
        calibrated forecasts, not runaway slopes.
        """
        x = np.asarray(values[-self.window :], dtype=float)
        if len(x) < 3:
            # Pad with the *first observed value*, not zeros — zero-padding a
            # young series fabricates a rising slope (0 -> level) that the
            # smoother reads as trend, over-forecasting at short history.
            pad_val = x[0] if len(x) else 0.0
            x = np.array([pad_val] * (3 - len(x)) + list(x))
        smoothed = self._smooth(x)
        resid = x - smoothed
        resid_std = float(np.std(resid)) if len(resid) > 1 else 0.05
        z = float(np.quantile(np.abs(resid), self.quantile)) if len(resid) else 0.05

        level, trend = smoothed[-1], (smoothed[-1] - smoothed[-2]) if len(smoothed) > 1 else 0.0
        mean_vals, t_vals = [], []
        lvl = level
        for h in range(1, horizon_h + 1):
            damp = np.exp(-trend_decay * h) if trend_decay > 0 else 1.0
            if bounded:
                cap = (1.0 - lvl) if trend >= 0 else lvl
                lvl = min(1.0, max(0.0, lvl + trend * cap * damp))
                mean_vals.append(lvl)
            else:
                mean_vals.append(max(0.0, float(level + trend * h * damp)))
            t_vals.append(t0 + timedelta(hours=h))
        spread = z + 0.03 * np.sqrt(np.arange(1, horizon_h + 1))
        mean_arr = np.asarray(mean_vals)
        lower = np.clip(mean_arr - spread, 0, None)
        upper = np.clip(mean_arr + spread, 0, 1.0)
        return ForecastResult(
            series_t=t_vals,
            mean=mean_arr.tolist(),
            lower=lower.tolist(),
            upper=upper.tolist(),
            horizon_h=horizon_h,
            residual_std=resid_std,
        )

    @staticmethod
    def to_probability(x: float, scale: float = 10.0) -> float:
        """Logistic squash of a driving signal into [0,1] probability."""
        return float(1.0 / (1.0 + np.exp(-(x - scale / 2.0) / (scale / 6.0))))


def probability_from_components(components: dict[str, float]) -> float:
    """Canonical flood risk probability from fused 0-12 components.

    Kept as the flood-specific entry point for back-compat; the pipeline
    dispatches through `probability_for` so every hazard owns its formula.
    """
    return probability_for("flood", components)


def probability_for(hazard: str | None, components: dict[str, float]) -> float:
    """Hazard-templated risk probability — dispatch via the hazard registry."""
    from app.hazards.registry import get_hazard

    return get_hazard(hazard).probability(components)


DEFAULT_FORECASTER = Forecaster()
