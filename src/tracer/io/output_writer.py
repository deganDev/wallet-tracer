from __future__ import annotations

import json
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


def write_summary_md(graph: Graph, out_dir: str, filename: str = "summary.md") -> str:
    """
    Minimal, investigator-friendly summary.
    """
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)

    out_path = p / filename

    total_nodes = len(graph.nodes)
    total_edges = len(graph.edges)

    # top edges by usd_value
    def sort_key(e):
        return (e.usd_value is not None, e.usd_value or 0)

    top = sorted(graph.edges, key=sort_key, reverse=True)[:15]

    lines = []
    lines.append("# Trace Summary\n")
    lines.append(f"- Nodes: **{total_nodes}**\n")
    lines.append(f"- Edges: **{total_edges}**\n\n")

    lines.append("## Top Transfers (by USD value)\n\n")
    if not top:
        lines.append("_No transfers found in the selected window._\n")
    else:
        for e in top:
            usd = f"{e.usd_value:.2f}" if e.usd_value is not None else "unknown"
            lines.append(
                f"- **{usd} USD** | {e.asset_type} {e.symbol or ''} "
                f"| {e.from_address[:10]}… → {e.to_address[:10]}… "
                f"| tx: {e.tx_hash}\n"
            )

    with out_path.open("w", encoding="utf-8") as f:
        f.writelines(lines)

    return str(out_path)
