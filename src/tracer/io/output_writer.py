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

    lines.append("## Token Risk Summary\n\n")
    if not graph.tokens:
        lines.append("_No token risk data available._\n\n")
    else:
        label_counts = {}
        for t in graph.tokens.values():
            label_counts[t.label.value] = label_counts.get(t.label.value, 0) + 1
        for label, count in sorted(label_counts.items()):
            lines.append(f"- **{label}**: {count}\n")
        lines.append("\n")

    lines.append("## Limitations / Next steps\n\n")
    lines.append("- Only ETH + ERC-20 transfers are included.\n")
    lines.append("- No internal tx tracing, approvals, or NFT activity.\n")
    lines.append("- USD values are best-effort and may be missing for unknown tokens.\n")
    lines.append("- Token risk labels are best-effort and depend on external data sources.\n")
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


def write_graph_html(graph: Graph, out_dir: str, filename: str = "index.html") -> str:
    p = Path(out_dir)
    p.mkdir(parents=True, exist_ok=True)

    out_path = p / filename

    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Wallet Tracer</title>
  <style>
    :root {
      --bg: #0f1115;
      --panel: #151824;
      --text: #e6e8ef;
      --muted: #9aa3b2;
      --accent: #5bd1d7;
      --edge-eth: #7bd389;
      --edge-erc20: #f7b32b;
    }
    body {
      margin: 0;
      font-family: "SF Mono", "Menlo", "Consolas", monospace;
      background: radial-gradient(circle at 20% 20%, #1b2130 0%, #0f1115 60%);
      color: var(--text);
    }
    header {
      padding: 16px 20px;
      border-bottom: 1px solid #23283a;
      background: var(--panel);
    }
    header h1 {
      margin: 0;
      font-size: 18px;
      letter-spacing: 0.5px;
    }
    header p {
      margin: 6px 0 0 0;
      font-size: 12px;
      color: var(--muted);
    }
    #wrap {
      display: grid;
      grid-template-columns: 260px 1fr;
      height: calc(100vh - 64px);
    }
    #sidebar {
      padding: 14px;
      border-right: 1px solid #23283a;
      background: var(--panel);
    }
    #sidebar h2 {
      font-size: 13px;
      margin: 10px 0 6px 0;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    #sidebar .stat {
      font-size: 13px;
      margin-bottom: 8px;
    }
    #network {
      width: 100%;
      height: 100%;
      min-height: 600px;
      background: #0b0d12;
    }
    .legend {
      font-size: 12px;
      color: var(--muted);
    }
    .legend span {
      display: inline-block;
      width: 10px;
      height: 10px;
      margin-right: 6px;
      border-radius: 2px;
    }
  </style>
</head>
<body>
  <header>
    <h1>Wallet Tracer</h1>
    <p>Interactive graph view of graph.json</p>
  </header>
  <div id="wrap">
    <div id="sidebar">
      <div class="stat" id="stats">Loading...</div>
      <h2>Legend</h2>
      <div class="legend"><span style="background: var(--edge-eth);"></span>ETH transfer</div>
      <div class="legend"><span style="background: var(--edge-erc20);"></span>ERC-20 transfer</div>
    </div>
    <div id="network"></div>
  </div>

  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <script>
    const short = (addr) => {
      if (!addr) return "";
      return addr.length > 14 ? addr.slice(0, 10) + "..." : addr;
    };

    fetch("./graph.json")
      .then((r) => r.json())
      .then((data) => {
        if (!window.vis || !window.vis.Network) {
          document.getElementById("stats").textContent = "Graph library failed to load.";
          return;
        }
        const nodes = data.nodes.map((n) => ({
          id: n.address,
          label: short(n.address),
          title: n.address + (n.is_contract ? " (contract)" : ""),
          shape: n.is_contract ? "box" : "dot",
          color: n.is_contract ? "#8aa6ff" : "#5bd1d7",
          size: 16,
          font: { color: "#e6e8ef" },
        }));

        const edges = data.edges.map((e) => ({
          from: e.from,
          to: e.to,
          arrows: "to",
          color: e.asset_type === "ETH" ? "#7bd389" : "#f7b32b",
          title: `${e.asset_type} ${e.symbol || ""} | ${e.amount} | ${e.usd_value || "unknown"} USD`,
        }));

        const container = document.getElementById("network");
        const networkData = { nodes, edges };
        const options = {
          layout: { improvedLayout: true },
          physics: { stabilization: { iterations: 200 } },
          interaction: { hover: true },
          nodes: { size: 12 },
          edges: { smooth: false, width: 1.2, arrows: { to: { enabled: true, scaleFactor: 0.6 } } },
        };
        const network = new vis.Network(container, networkData, options);
        network.once("stabilizationIterationsDone", () => {
          network.fit({ animation: true });
        });
        setTimeout(() => {
          network.fit({ animation: true });
        }, 500);

        const stats = document.getElementById("stats");
        stats.textContent = `Nodes: ${nodes.length} • Edges: ${edges.length}`;
      })
      .catch((err) => {
        document.getElementById("stats").textContent = "Failed to load graph.json";
        console.error(err);
      });
  </script>
</body>
</html>
"""

    with out_path.open("w", encoding="utf-8") as f:
        f.write(html)

    return str(out_path)
