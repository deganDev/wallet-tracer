from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time
from decimal import Decimal

from tracer.core.models import TraceConfig
from tracer.services.tracer_service import TracerService
from tracer.io.output_writer import write_graph_json, write_summary_md

from tracer.adapters.chain.etherscan_chain_adapter import EtherscanChainAdapter
from tracer.adapters.chain.static_chain_adapter import StaticChainAdapter 
from tracer.adapters.pricing.price_adapter import PriceAdapter


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tracer", description="Value-flow tracer (ETH + ERC20)")
    p.add_argument("--address", required=True, help="Seed address to trace")
    p.add_argument("--days", type=int, default=30, help="Lookback window in days")
    p.add_argument("--hops", type=int, default=2, help="Number of hops")
    p.add_argument("--min-usd", type=str, default="1000", help="Filter transfers below this USD value")
    p.add_argument("--out", default="out", help="Output folder")
    p.add_argument("--max-edges-per-address", type=int, default=0, help="Limit edges per address per hop (0=unlimited)")
    p.add_argument("--max-total-edges", type=int, default=0, help="Limit total edges (0=unlimited)")
    p.add_argument("--use-static", action="store_true", help="Use static adapter (dev/testing)")
    p.add_argument("--ignore-unknown-price", default=True, action="store_true", help="Skip transfers where USD price cannot be determined")
    return p


def _make_progress_reporter(cfg: TraceConfig):
    start_time = time.time()
    last_print = 0.0
    is_tty = sys.stdout.isatty()

    def _short_addr(addr: str) -> str:
        if not addr:
            return ""
        if len(addr) <= 12:
            return addr
        return f"{addr[:6]}...{addr[-4:]}"

    def _ts() -> str:
        return dt.datetime.now().strftime("%H:%M:%S")

    def _print_line(message: str) -> None:
        if is_tty:
            sys.stdout.write("\r" + message.ljust(88))
            sys.stdout.flush()
        else:
            print(message)

    def _clear_line() -> None:
        if is_tty:
            sys.stdout.write("\r" + (" " * 88) + "\r")
            sys.stdout.flush()

    def progress(event: str, data: dict) -> None:
        nonlocal last_print
        now = time.time()
        if event == "start":
            print(f"[{_ts()}] Tracing {cfg.address} • {cfg.days}d • {cfg.hops} hop(s)")
            return
        if event == "visit":
            if not is_tty and data["processed"] % 100 != 0:
                return
            if is_tty and now - last_print < 0.2:
                return
            msg = (
                f"Hop {data['depth']}/{cfg.hops} • "
                f"queue {data['queue']} • "
                f"processed {data['processed']} • "
                f"edges {data['edges']}"
            )
            _print_line(msg)
            last_print = now
            return
        if event == "fetch":
            phase = data.get("phase", "data").upper()
            addr = _short_addr(str(data.get("address", "")))
            msg = f"Fetching {phase} for {addr}..."
            _print_line(msg)
            last_print = now
            return
        if event == "fetch_done":
            phase = data.get("phase", "data").upper()
            count = data.get("count", 0)
            msg = f"Fetched {phase}: {count} transfer(s)"
            _print_line(msg)
            last_print = now
            return
        if event == "contract_progress":
            checked = data.get("checked", 0)
            errors = data.get("errors", 0)
            msg = f"Tagging contracts... {checked} checked (errors {errors})"
            _print_line(msg)
            last_print = now
            return
        if event == "done":
            _clear_line()
            elapsed = time.time() - start_time
            print(
                f"[{_ts()}] Done in {elapsed:.1f}s • "
                f"{data['nodes']} nodes • {data['edges']} edges"
            )
            return
        if event == "error":
            _clear_line()
            print(f"[{_ts()}] Error: {data.get('message', 'Unknown error')}", file=sys.stderr)

    return progress


def main() -> int:
    args = build_arg_parser().parse_args()

    cfg = TraceConfig(
        address=args.address,
        days=args.days,
        hops=args.hops,
        min_usd=Decimal(args.min_usd),
        max_edges_per_address=args.max_edges_per_address,
        max_total_edges=args.max_total_edges,
        ignore_unknown_price=args.ignore_unknown_price,
    )
    progress = _make_progress_reporter(cfg)

    # Ports
    if args.use_static:
        chain = StaticChainAdapter()
        adapter_label = "StaticChainAdapter (dev/testing)"
    else:
        # Etherscan key should come from env or settings file
        if not os.getenv("ETHERSCAN_API_KEY"):
            progress("error", {"message": "Missing ETHERSCAN_API_KEY environment variable"})
            return 2
        chain = EtherscanChainAdapter()
        adapter_label = "EtherscanChainAdapter"

    price = PriceAdapter()

    # Service
    svc = TracerService(chain=chain, price=price)
    print(f"Adapter: {adapter_label}")
    try:
        graph = svc.trace(cfg, on_progress=progress)
    except Exception as exc:
        progress("error", {"message": f"{exc.__class__.__name__}: {exc}"})
        return 1

    # Outputs
    print("Writing outputs...")
    graph_path = write_graph_json(graph, args.out)
    summary_path = write_summary_md(graph, args.out, seed_address=cfg.address)

    print(f"Wrote: {graph_path}")
    print(f"Wrote: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
