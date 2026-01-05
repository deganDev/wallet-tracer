from __future__ import annotations

from abc import ABC, abstractmethod
from tracer.core.models import TokenRisk


class TokenRiskPort(ABC):
    @abstractmethod
    def get_token_risk(self, token_address: str, timestamp: int) -> TokenRisk:
        raise NotImplementedError
