from __future__ import annotations

from decimal import Decimal
from typing import Dict

from tracer.core.dto import DexScreenerAnalysis
from tracer.core.models import TokenRisk


def _dec_to_float(val: Decimal | None) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except Exception:
        return 0.0


def token_features_from_analysis(analysis: DexScreenerAnalysis) -> Dict[str, float]:
    flags = set(analysis.flags)
    return {
        "pair_count": float(analysis.pair_count),
        "total_liquidity_usd": _dec_to_float(analysis.total_liquidity_usd),
        "max_liquidity_usd": _dec_to_float(analysis.max_liquidity_usd),
        "newest_pair_age_hours": _dec_to_float(analysis.newest_pair_age_hours),
        "oldest_pair_age_hours": _dec_to_float(analysis.oldest_pair_age_hours),
        "flag_count": float(len(flags)),
        "flag_liquidity_thin": 1.0 if "LIQUIDITY_THIN" in flags else 0.0,
        "flag_single_pair": 1.0 if "SINGLE_DEX_PAIR_ONLY" in flags else 0.0,
        "flag_recent_pair": 1.0 if "PAIR_CREATED_RECENTLY" in flags else 0.0,
    }


def _to_float(val: object) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except Exception:
        return 0.0


def token_features_from_risk(risk: TokenRisk) -> Dict[str, float]:
    flags = set(f.value for f in (risk.risk_flags or []))
    signals = risk.signals if isinstance(risk.signals, dict) else {}
    ds = signals.get("dexscreener", {}) if isinstance(signals, dict) else {}
    return {
        "pair_count": _to_float(ds.get("pair_count")),
        "total_liquidity_usd": _to_float(ds.get("total_liquidity_usd")),
        "max_liquidity_usd": _to_float(ds.get("max_liquidity_usd")),
        "newest_pair_age_hours": _to_float(ds.get("newest_pair_age_hours")),
        "oldest_pair_age_hours": _to_float(ds.get("oldest_pair_age_hours")),
        "flag_count": float(len(flags)),
        "flag_liquidity_thin": 1.0 if "LIQUIDITY_THIN" in flags else 0.0,
        "flag_single_pair": 1.0 if "SINGLE_DEX_PAIR_ONLY" in flags else 0.0,
        "flag_recent_pair": 1.0 if "PAIR_CREATED_RECENTLY" in flags else 0.0,
    }
