from __future__ import annotations

from typing import Optional

from tracer.adapters.risk.dexscreener_adapter import DexScreenerAdapter
from tracer.core.enums import TokenRiskFlag, TokenRiskLabel
from tracer.core.errors import DataSourceError
from tracer.core.models import TokenRisk
from tracer.ports.token_risk_port import TokenRiskPort


class TokenRiskAdapter(TokenRiskPort):
    def __init__(self, dexscreener: Optional[DexScreenerAdapter] = None) -> None:
        self._dexscreener = dexscreener or DexScreenerAdapter()

    def get_token_risk(self, token_address: str, timestamp: int) -> TokenRisk:
        signals = None
        flags = []
        score = 0
        try:
            analysis = self._dexscreener.analyze_token(token_address)
            flags = [TokenRiskFlag(f) for f in analysis.flags]
            score = self._score_from_flags(flags)
            signals = {
                "dexscreener": {
                    "pair_count": analysis.pair_count,
                    "total_liquidity_usd": str(analysis.total_liquidity_usd),
                    "max_liquidity_usd": str(analysis.max_liquidity_usd),
                    "newest_pair_age_hours": (
                        str(analysis.newest_pair_age_hours)
                        if analysis.newest_pair_age_hours is not None
                        else None
                    ),
                    "oldest_pair_age_hours": (
                        str(analysis.oldest_pair_age_hours)
                        if analysis.oldest_pair_age_hours is not None
                        else None
                    ),
                }
            }
        except DataSourceError as exc:
            signals = {"dexscreener_error": str(exc)}

        return TokenRisk(
            token_address=token_address.lower(),
            label=self._label_from_score(score),
            score=score,
            risk_flags=flags,
            signals=signals,
        )

    @staticmethod
    def _score_from_flags(flags: list[TokenRiskFlag]) -> int:
        weights = {
            TokenRiskFlag.LIQUIDITY_THIN: 15,
            TokenRiskFlag.PAIR_CREATED_RECENTLY: 10,
            TokenRiskFlag.SINGLE_DEX_PAIR_ONLY: 10,
        }
        total = 0
        for f in flags:
            total += weights.get(f, 0)
        return min(100, total)

    @staticmethod
    def _label_from_score(score: int) -> TokenRiskLabel:
        if score >= 80:
            return TokenRiskLabel.SCAM_CONFIRMED
        if score >= 50:
            return TokenRiskLabel.HIGH_RISK
        if score >= 25:
            return TokenRiskLabel.MEDIUM_RISK
        if score > 0:
            return TokenRiskLabel.LOW_RISK
        return TokenRiskLabel.UNKNOWN


__all__ = ["TokenRiskAdapter"]
