from __future__ import annotations

from decimal import Decimal
from typing import Dict

from tracer.core.models import Graph


def _dec_to_float(val: Decimal | None) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except Exception:
        return 0.0


def wallet_features_from_graph(address: str, graph: Graph) -> Dict[str, float]:
    addr = address.lower()
    in_edges = [e for e in graph.edges if e.to_address == addr]
    out_edges = [e for e in graph.edges if e.from_address == addr]
    all_edges = in_edges + out_edges

    def sum_usd(edges):
        total = Decimal("0")
        count = 0
        for e in edges:
            if e.usd_value is None:
                continue
            total += e.usd_value
            count += 1
        return total, count

    in_total, in_count = sum_usd(in_edges)
    out_total, out_count = sum_usd(out_edges)

    uniq = set()
    for e in all_edges:
        uniq.add(e.from_address)
        uniq.add(e.to_address)
    uniq.discard(addr)

    timestamps = [e.timestamp for e in all_edges if e.timestamp]
    if timestamps:
        active_hours = (max(timestamps) - min(timestamps)) / 3600.0
    else:
        active_hours = 0.0

    erc20_count = sum(1 for e in all_edges if e.asset_type == "ERC20")
    eth_count = sum(1 for e in all_edges if e.asset_type == "ETH")
    total_count = len(all_edges)

    in_out_ratio = float(in_total / out_total) if out_total > 0 else float(in_total > 0)

    return {
        "in_tx_count": float(len(in_edges)),
        "out_tx_count": float(len(out_edges)),
        "unique_counterparties": float(len(uniq)),
        "total_in_usd": _dec_to_float(in_total),
        "total_out_usd": _dec_to_float(out_total),
        "avg_in_usd": _dec_to_float(in_total / in_count) if in_count else 0.0,
        "avg_out_usd": _dec_to_float(out_total / out_count) if out_count else 0.0,
        "in_out_ratio": in_out_ratio,
        "active_hours": float(active_hours),
        "erc20_ratio": float(erc20_count / total_count) if total_count else 0.0,
        "eth_ratio": float(eth_count / total_count) if total_count else 0.0,
    }

