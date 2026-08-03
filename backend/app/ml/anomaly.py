"""Multivariate anomaly detection with IsolationForest.

Runs on a rolling feature window per location (rain, soil moisture anomaly, water
level headroom). Returns anomaly score 0..1 and a human-readable flag. LLMs never
touch this path — this is specialized-model territory per the blueprint.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest


@dataclass
class AnomalyResult:
    score: float  # 0..1 (higher = more anomalous)
    flag: str  # normal | elevated | anomalous | severe
    features: dict[str, float]
    explanation: str


class AnomalyDetector:
    def __init__(self, contamination: float = 0.12, seed: int = 7):
        self.contamination = contamination
        self._model: IsolationForest | None = None
        self._seed = seed

    def _ensure_model(self, X: np.ndarray) -> IsolationForest:
        if self._model is None or self._model.n_features_in_ != X.shape[1]:
            self._model = IsolationForest(
                contamination=self.contamination, random_state=self._seed, n_estimators=64
            ).fit(X)
        return self._model

    def detect(self, feature_rows: list[dict[str, float]]) -> AnomalyResult:
        keys = list(feature_rows[-1].keys())
        X = np.array([[row.get(k, 0.0) for k in keys] for row in feature_rows[-64:]])
        if len(X) < 10:
            return AnomalyResult(0.0, "normal", feature_rows[-1], "insufficient history")

        model = self._ensure_model(X)
        scores = model.decision_function(X)
        latest = float(scores[-1])
        # normal anomaly scores are ~0; decision_function: higher = more normal
        anomaly_score = float(np.clip((0.0 - latest) / 0.25, 0.0, 1.0))

        if anomaly_score >= 0.75:
            flag = "severe"
        elif anomaly_score >= 0.5:
            flag = "anomalous"
        elif anomaly_score >= 0.25:
            flag = "elevated"
        else:
            flag = "normal"

        top = max(keys, key=lambda k: abs(feature_rows[-1].get(k, 0.0) - np.mean(X[:, keys.index(k)])))
        return AnomalyResult(
            score=anomaly_score,
            flag=flag,
            features=feature_rows[-1],
            explanation=f"strongest deviation in '{top}' relative to recent history",
        )
