from __future__ import annotations

from tracer.core.enums import TokenRiskLabel
from tracer.core.models import TokenRisk
from tracer.ports.token_risk_port import TokenRiskPort


class TokenRiskAdapter(TokenRiskPort):
    def get_token_risk(self, token_address: str, timestamp: int) -> TokenRisk:
        return TokenRisk(
            token_address=token_address.lower(),
            label=TokenRiskLabel.UNKNOWN,
            score=0,
            risk_flags=[],
            signals=None,
        )


__all__ = ["TokenRiskAdapter"]
