from __future__ import annotations

from tracer.core.models import Graph, WalletRisk
from tracer.ml.wallet_scorer import WalletMLScorer
from tracer.ports.wallet_risk_port import WalletRiskPort


class WalletRiskMLAdapter(WalletRiskPort):
    def __init__(self, scorer: WalletMLScorer | None = None) -> None:
        self._scorer = scorer or WalletMLScorer()

    def get_wallet_risk(self, address: str, graph: Graph) -> WalletRisk:
        addr = address.lower()
        scored = self._scorer.score(addr, graph)
        if not scored:
            return WalletRisk(address=addr, label="UNKNOWN", score=0.0, signals=None)
        prob = float(scored.get("prob_scam", 0.0))
        label = str(scored.get("label", "UNKNOWN"))
        score = prob * 100.0
        return WalletRisk(
            address=addr,
            label=label,
            score=score,
            signals={"ml": scored},
        )


__all__ = ["WalletRiskMLAdapter"]
