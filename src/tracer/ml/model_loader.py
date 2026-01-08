from __future__ import annotations

import os
from typing import Any, Dict, Optional

import joblib

_MODEL_CACHE: Dict[str, Optional[Any]] = {}


def load_model(path: str) -> Optional[Any]:
    if not path:
        return None
    if path in _MODEL_CACHE:
        return _MODEL_CACHE[path]
    if not os.path.exists(path):
        _MODEL_CACHE[path] = None
        return None
    try:
        model = joblib.load(path)
    except Exception:
        _MODEL_CACHE[path] = None
        return None
    _MODEL_CACHE[path] = model
    return model

