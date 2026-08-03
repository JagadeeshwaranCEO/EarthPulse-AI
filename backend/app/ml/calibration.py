"""Probability calibration & retrospective evaluation (pure NumPy).

Forecasts are deterministic (same components → same probability), so a
*retrospective* against historical outcomes is the honest way to reason about
precision: does p=0.8 actually flood 80% of the time?

measure:
  - Brier score (lower = better; 0 = perfect, ~0.25 = uninformative)
  - Reliability diagram    (mean_prediction vs observed_frequency per bin)
  - Beta calibration         (recalibrates with logit slope + bias from the data)
"""

from __future__ import annotations

import math

import numpy as np


def brier(y_true: list[float], y_pred: list[float]) -> float:
    a = np.asarray(y_true, dtype=float)
    b = np.asarray(y_pred, dtype=float)
    return float(np.mean((a - b) ** 2))


def reliability(y_true: list[float], y_pred: list[float], bins: int = 10) -> list[dict]:
    a = np.asarray(y_true, dtype=float)
    b = np.asarray(y_pred, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    rows = []
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        idx = np.where((b >= lo) & (b < hi))[0]
        if hi == 1.0:
            idx = np.where(b >= lo)[0]
        if len(idx) == 0:
            continue
        rows.append({
            "bin": f"{lo:.1f}-{hi:.1f}",
            "n": int(len(idx)),
            "mean_prediction": round(float(b[idx].mean()), 3),
            "observed_frequency": round(float(a[idx].mean()), 3),
        })
    return rows


def reliability_error(y_true, y_pred, bins: int = 10) -> float:
    """Mean |observed - predicted| over populated bins (calibration error)."""
    rows = reliability(y_true, y_pred, bins)
    if not rows:
        return 0.0
    return float(np.mean([abs(r["observed_frequency"] - r["mean_prediction"]) for r in rows]))


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def beta_calibration(y_true: list[float], y_pred: list[float],
                     lr: float = 0.5, iters: int = 300) -> dict:
    """Platt-like logistic recalibration: logit(p') = a + b·logit(p).

    Returns a + b coefficients and the Brier score before/after on the same set
    (fit-in-sample for transparency; the harness reports it as such).
    """
    a = np.asarray(y_true, dtype=float)
    x = _logit(np.asarray(y_pred, dtype=float))  # logit(p)
    bias = 0.0
    slope = 1.0
    v_bias = v_slope = 0.0
    n = len(a)
    for _ in range(iters):
        logitp = bias + slope * x
        p = 1.0 / (1.0 + np.exp(-np.clip(logitp, -30, 30)))
        grad_bias = np.mean(p - a)
        grad_slope = np.mean((p - a) * x)
        v_bias = 0.9 * v_bias + 0.1 * grad_bias
        v_slope = 0.9 * v_slope + 0.1 * grad_slope
        bias -= lr * v_bias
        slope -= lr * v_slope
    cal = 1.0 / (1.0 + np.exp(-(bias + slope * _logit(np.asarray(y_pred))))).ravel()
    return bias, slope, brier(list(a), list(np.asarray(y_pred))), brier(list(a), list(cal))


def calibrate_report(y_true: list[float], y_pred: list[float], bins: int = 10) -> dict:
    bias, slope, b_before, b_after = beta_calibration(y_true, y_pred)
    return {
        "n": len(y_true),
        "base_rate": round(float(np.mean(y_true)), 3),
        "brier_before": round(b_before, 4),
        "brier_after": round(b_after, 4),
        "reliability_error_before": round(reliability_error(y_true, y_pred, bins), 4),
        "recalib_bias": round(bias, 4),
        "recalib_slope": round(slope, 4),
    }