from __future__ import annotations

from abc import ABC, abstractmethod

from tracer.core.models import Graph, WalletRisk


class WalletRiskPort(ABC):
    @abstractmethod
    def get_wallet_risk(self, address: str, graph: Graph) -> WalletRisk:
        raise NotImplementedError

