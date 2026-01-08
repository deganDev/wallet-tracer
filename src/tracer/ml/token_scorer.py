from __future__ import annotations

from math import exp
from typing import Any, Dict, Optional

from tracer.config import settings
from tracer.core.dto import DexScreenerAnalysis
from tracer.ml.model_loader import load_model
from tracer.ml.token_features import token_features_from_analysis


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + exp(-x))
    except Exception:
        return 0.0


def _predict_proba(model: Any, features: Dict[str, float]) -> Optional[float]:
    if model is None:
        return None
    X = [list(features.values())]
    if hasattr(model, "predict_proba"):
        prob = model.predict_proba(X)[0]
        return float(prob[1]) if len(prob) > 1 else float(prob[0])
    if hasattr(model, "decision_function"):
        score = model.decision_function(X)[0]
        return _sigmoid(float(score))
    if hasattr(model, "predict"):
        pred = model.predict(X)[0]
        return float(pred)
    return None


def _label_from_prob(prob: float) -> str:
    if prob >= float(settings.ML_TOKEN_HIGH_THRESHOLD):
        return "HIGH_RISK"
    if prob >= float(settings.ML_TOKEN_MEDIUM_THRESHOLD):
        return "MEDIUM_RISK"
    if prob > 0:
        return "LOW_RISK"
    return "UNKNOWN"


class TokenMLScorer:
    def __init__(self, model_path: str = settings.ML_TOKEN_MODEL_PATH) -> None:
        self._model_path = model_path
        self._model = load_model(model_path)

    def score(self, analysis: DexScreenerAnalysis) -> Optional[Dict[str, object]]:
        if self._model is None:
            return None
        features = token_features_from_analysis(analysis)
        prob = _predict_proba(self._model, features)
        if prob is None:
            return None
        return {
            "prob_scam": prob,
            "label": _label_from_prob(prob),
            "features": features,
            "model_path": self._model_path,
        }

