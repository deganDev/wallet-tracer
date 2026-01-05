from __future__ import annotations

import argparse
import os
from decimal import Decimal

from tracer.core.models import TraceConfig
from tracer.services.tracer_service import TracerService
from tracer.io.output_writer import write_graph_json, write_summary_md

from tracer.adapters.chain.etherscan_chain_adapter import EtherscanChainAdapter
from tracer.adapters.chain.static_chain_adapter import StaticChainAdapter 
from tracer.adapters.pricing.price_adapter import PriceAdapter


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tracer", description="Value-flow tracer (ETH + ERC20)")
    p.add_argument("--seed", required=True, help="Seed address to trace")
    p.add_argument("--days", type=int, default=30, help="Lookback window in days")
    p.add_argument("--hops", type=int, default=2, help="Number of hops")
    p.add_argument("--min-usd", type=str, default="100", help="Filter transfers below this USD value")
    p.add_argument("--out", default="out", help="Output folder")
    p.add_argument("--max-edges-per-address", type=int, default=0, help="Limit edges per address per hop (0=unlimited)")
    p.add_argument("--max-total-edges", type=int, default=0, help="Limit total edges (0=unlimited)")
    p.add_argument("--use-static", action="store_true", help="Use static adapter (dev/testing)")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()

    cfg = TraceConfig(
        address=args.seed,
        days=args.days,
        hops=args.hops,
        min_usd=Decimal(args.min_usd),
        max_edges_per_address=args.max_edges_per_address,
        max_total_edges=args.max_total_edges,
    )

    # Ports
    if args.use_static:
        chain = StaticChainAdapter()
    else:
        # Etherscan key should come from env or settings file
        if not os.getenv("ETHERSCAN_API_KEY"):
            raise SystemExit("Missing ETHERSCAN_API_KEY environment variable")
        chain = EtherscanChainAdapter()

    price = PriceAdapter()

    # Service
    svc = TracerService(chain=chain, price=price)
    graph = svc.trace(cfg)

    # Outputs
    graph_path = write_graph_json(graph, args.out)
    summary_path = write_summary_md(graph, args.out)

    print(f"Wrote: {graph_path}")
    print(f"Wrote: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
