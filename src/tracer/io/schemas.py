from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from tracer.core.models import Graph


def _dec_to_str(x: Decimal) -> str:
    # keep as string for JSON precision safety
    return format(x, "f")


def graph_to_dict(g: Graph) -> Dict[str, Any]:
    return {
        "nodes": [
            {
                "address": n.address,
                "is_contract": n.is_contract,
            }
            for n in g.nodes.values()
        ],
        "tokens": [
            {
                "token_address": t.token_address,
                "label": t.label.value,
                "score": t.score,
                "risk_flags": [f.value for f in t.risk_flags],
                "signals": t.signals,
            }
            for t in g.tokens.values()
        ],
        "edges": [
            {
                "from": e.from_address,
                "to": e.to_address,
                "tx_hash": e.tx_hash,
                "timestamp": e.timestamp,
                "asset_type": e.asset_type,
                "token_address": e.token_address,
                "symbol": e.symbol,
                "amount": _dec_to_str(e.amount),
                "usd_value": _dec_to_str(e.usd_value) if e.usd_value is not None else None,
            }
            for e in g.edges
        ],
    }
