from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Optional

from tracer.core.models import Graph
from tracer.io.schemas import graph_to_dict


def write_graph_json(graph: Graph, out_dir: str, filename: str = "graph.json") -> str:
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)

    out_path = p / filename
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(graph_to_dict(graph), f, indent=2)

    return str(out_path)


def write_summary_md(
    graph: Graph,
    out_dir: str,
    filename: str = "summary.md",
    seed_address: Optional[str] = None,
) -> str:
    """
    Minimal, investigator-friendly summary.
    """
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)

    out_path = p / filename

    total_nodes = len(graph.nodes)
    total_edges = len(graph.edges)
    seed = (seed_address or "").lower()

    def sort_key(e):
        return (e.usd_value is not None, e.usd_value or 0)

    top = sorted(graph.edges, key=sort_key, reverse=True)[:15]

    def sum_by_address(edges, key):
        totals = {}
        for e in edges:
            if e.usd_value is None:
                continue
            addr = key(e)
            totals[addr] = totals.get(addr, Decimal("0")) + e.usd_value
        return totals

    inflow_edges = [e for e in graph.edges if seed and e.to_address == seed]
    outflow_edges = [e for e in graph.edges if seed and e.from_address == seed]

    inflow_totals = sum_by_address(inflow_edges, lambda e: e.from_address)
    outflow_totals = sum_by_address(outflow_edges, lambda e: e.to_address)

    def top_n(totals, n=10):
        return sorted(totals.items(), key=lambda x: x[1], reverse=True)[:n]

    top_in = top_n(inflow_totals)
    top_out = top_n(outflow_totals)

    total_in_usd = sum(inflow_totals.values(), Decimal("0"))
    total_out_usd = sum(outflow_totals.values(), Decimal("0"))

    def fmt_usd(x: Decimal) -> str:
        return f"{x:.2f}"

    def short(addr: str) -> str:
        return addr if len(addr) <= 14 else f"{addr[:10]}..."

    def interpretation() -> str:
        if not seed:
            return "No seed address was provided to the summary writer."
        if not inflow_edges and not outflow_edges:
            return "No value movements touched the seed address in this window."
        uniq_in = len(inflow_totals)
        uniq_out = len(outflow_totals)
        if uniq_out >= uniq_in * 2 and total_out_usd > total_in_usd:
            return (
                "This wallet looks like a distributor: many outbound destinations "
                "and higher outflow than inflow during the window."
            )
        if uniq_in >= uniq_out * 2 and total_in_usd > total_out_usd:
            return (
                "This wallet looks like a collector: many inbound sources and "
                "higher inflow than outflow during the window."
            )
        return (
            "Flows are mixed without a strong directional skew, which often matches "
            "an active wallet used for routine transfers."
        )

    lines = []
    lines.append("# Trace Summary\n")
    lines.append(f"- Nodes: **{total_nodes}**\n")
    lines.append(f"- Edges: **{total_edges}**\n")
    if seed:
        lines.append(f"- Seed: **{seed}**\n")
    lines.append("\n")

    lines.append("## Top 10 Inflow Sources (by USD)\n\n")
    if not top_in:
        lines.append("_No inbound transfers found in the selected window._\n\n")
    else:
        for addr, usd in top_in:
            lines.append(f"- **{fmt_usd(usd)} USD** | {addr}\n")
        lines.append("\n")

    lines.append("## Top 10 Outflow Destinations (by USD)\n\n")
    if not top_out:
        lines.append("_No outbound transfers found in the selected window._\n\n")
    else:
        for addr, usd in top_out:
            lines.append(f"- **{fmt_usd(usd)} USD** | {addr}\n")
        lines.append("\n")

    lines.append("## Interpretation\n\n")
    lines.append(f"{interpretation()}\n\n")

    lines.append("## Limitations / Next steps\n\n")
    lines.append("- Only ETH + ERC-20 transfers are included.\n")
    lines.append("- No internal tx tracing, approvals, or NFT activity.\n")
    lines.append("- USD values are best-effort and may be missing for unknown tokens.\n")
    lines.append("- Large wallets may require tighter limits or better caching.\n\n")

    lines.append("## Top Transfers (by USD value)\n\n")
    if not top:
        lines.append("_No transfers found in the selected window._\n")
    else:
        for e in top:
            usd = f"{e.usd_value:.2f}" if e.usd_value is not None else "unknown"
            lines.append(
                f"- **{usd} USD** | {e.asset_type} {e.symbol or ''} "
                f"| {short(e.from_address)} -> {short(e.to_address)} "
                f"| tx: {e.tx_hash}\n"
            )

    with out_path.open("w", encoding="utf-8") as f:
        f.writelines(lines)

    return str(out_path)
