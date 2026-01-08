from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time
from decimal import Decimal

from tracer.config import settings
from tracer.core.models import TraceConfig
from tracer.services.tracer_service import TracerService
from tracer.io.output_writer import write_graph_json, write_summary_md, write_graph_html

from tracer.adapters.chain.etherscan_chain_adapter import EtherscanChainAdapter
from tracer.adapters.chain.static_chain_adapter import StaticChainAdapter 
from tracer.adapters.pricing.price_adapter import PriceAdapter
from tracer.adapters.risk.token_risk_adapter import TokenRiskAdapter
from tracer.adapters.risk.wallet_risk_ml_adapter import WalletRiskMLAdapter
from tracer.adapters.risk.dexscreener_adapter import DexScreenerAdapter
from tracer.ml.token_scorer import TokenMLScorer
from tracer.ml.wallet_scorer import WalletMLScorer
from tracer.ml.training import (
    build_token_dataset,
    build_token_dataset_from_graph,
    build_token_labels_from_graph,
    build_wallet_dataset,
    eval_token_model,
    eval_wallet_model,
    load_graph_for_scoring,
    train_token_model,
    train_wallet_model,
)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tracer", description="Value-flow tracer (ETH + ERC20)")
    p.add_argument("--address", required=False, help="Seed address to trace")
    p.add_argument("--days", type=int, default=30, help="Lookback window in days")
    p.add_argument("--hops", type=int, default=1, help="Number of hops")
    p.add_argument("--min-usd", type=str, default="1000", help="Filter transfers below this USD value")
    p.add_argument("--out", default="out", help="Output folder")
    p.add_argument("--max-edges-per-address", type=int, default=0, help="Limit edges per address per hop (0=unlimited)")
    p.add_argument("--max-total-edges", type=int, default=0, help="Limit total edges (0=unlimited)")
    p.add_argument("--use-static", action="store_true", help="Use static adapter (dev/testing)")
    p.add_argument("--ignore-unknown-price", action="store_true", help="Skip transfers where USD price cannot be determined",)
    p.add_argument("--enable-contract-check", action="store_true", help="Enable contract checks (slower, uses eth_getCode)",)
    p.add_argument("--html", action="store_true", help="Write a basic HTML visualization alongside graph.json",)
    p.add_argument("--ml-token-labels", help="CSV with token_address,label (build dataset)")
    p.add_argument("--ml-token-dataset", help="Token feature CSV (output for build, input for train/eval)")
    p.add_argument("--ml-token-model", help="Token model path (output for train, input for eval/smoke)")
    p.add_argument("--ml-token-eval", action="store_true", help="Evaluate token model using dataset CSV")
    p.add_argument("--ml-token-smoke", help="Token address to score via ML")
    p.add_argument("--ml-wallet-labels", help="CSV with graph_path,address,label (build dataset)")
    p.add_argument("--ml-wallet-dataset", help="Wallet feature CSV (output for build, input for train/eval)")
    p.add_argument("--ml-wallet-model", help="Wallet model path (output for train, input for eval/smoke)")
    p.add_argument("--ml-wallet-eval", action="store_true", help="Evaluate wallet model using dataset CSV")
    p.add_argument("--ml-wallet-smoke-graph", help="graph.json path for wallet smoke test")
    p.add_argument("--ml-wallet-smoke-address", help="Wallet address for smoke test")
    p.add_argument("--ml-auto-train", action="store_true", help="Auto-build token CSVs and train after tracing")
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

    if any(
        [
            args.ml_token_labels,
            args.ml_token_dataset,
            args.ml_token_model,
            args.ml_token_eval,
            args.ml_token_smoke,
            args.ml_wallet_labels,
            args.ml_wallet_dataset,
            args.ml_wallet_model,
            args.ml_wallet_eval,
            args.ml_wallet_smoke_graph,
            args.ml_wallet_smoke_address,
        ]
    ):
        if args.ml_token_labels:
            if not args.ml_token_dataset:
                print("Missing --ml-token-dataset for token dataset build", file=sys.stderr)
                return 2
            build_token_dataset(args.ml_token_labels, args.ml_token_dataset)
            print(f"Wrote token dataset: {args.ml_token_dataset}")

        if args.ml_token_model and args.ml_token_dataset:
            metrics = train_token_model(args.ml_token_dataset, args.ml_token_model)
            roc_auc = metrics.get("roc_auc")
            accuracy = (metrics.get("report") or {}).get("accuracy")
            print(f"Wrote token model: {args.ml_token_model}")
            if accuracy is not None:
                print("Token accuracy:", accuracy)
            if roc_auc is not None:
                print("Token ROC AUC:", roc_auc)

        if args.ml_token_eval:
            if not args.ml_token_model or not args.ml_token_dataset:
                print("Token eval requires --ml-token-model and --ml-token-dataset", file=sys.stderr)
                return 2
            metrics = eval_token_model(args.ml_token_dataset, args.ml_token_model)
            roc_auc = metrics.get("roc_auc")
            accuracy = (metrics.get("report") or {}).get("accuracy")
            if accuracy is not None:
                print("Token accuracy:", accuracy)
            if roc_auc is not None:
                print("Token ROC AUC:", roc_auc)

        if args.ml_token_smoke:
            model_path = args.ml_token_model or settings.ML_TOKEN_MODEL_PATH
            scorer = TokenMLScorer(model_path=model_path)
            analysis = DexScreenerAdapter().analyze_token(args.ml_token_smoke)
            scored = scorer.score(analysis)
            if not scored:
                print("Token smoke test failed: model not loaded or no score", file=sys.stderr)
                return 2
            print("Token smoke result:", scored)

        if args.ml_wallet_labels:
            if not args.ml_wallet_dataset:
                print("Missing --ml-wallet-dataset for wallet dataset build", file=sys.stderr)
                return 2
            build_wallet_dataset(args.ml_wallet_labels, args.ml_wallet_dataset)
            print(f"Wrote wallet dataset: {args.ml_wallet_dataset}")

        if args.ml_wallet_model and args.ml_wallet_dataset:
            metrics = train_wallet_model(args.ml_wallet_dataset, args.ml_wallet_model)
            roc_auc = metrics.get("roc_auc")
            accuracy = (metrics.get("report") or {}).get("accuracy")
            print(f"Wrote wallet model: {args.ml_wallet_model}")
            if accuracy is not None:
                print("Wallet accuracy:", accuracy)
            if roc_auc is not None:
                print("Wallet ROC AUC:", roc_auc)

        if args.ml_wallet_eval:
            if not args.ml_wallet_model or not args.ml_wallet_dataset:
                print("Wallet eval requires --ml-wallet-model and --ml-wallet-dataset", file=sys.stderr)
                return 2
            metrics = eval_wallet_model(args.ml_wallet_dataset, args.ml_wallet_model)
            roc_auc = metrics.get("roc_auc")
            accuracy = (metrics.get("report") or {}).get("accuracy")
            if accuracy is not None:
                print("Wallet accuracy:", accuracy)
            if roc_auc is not None:
                print("Wallet ROC AUC:", roc_auc)

        if args.ml_wallet_smoke_graph or args.ml_wallet_smoke_address:
            if not args.ml_wallet_smoke_graph or not args.ml_wallet_smoke_address:
                print("Wallet smoke requires --ml-wallet-smoke-graph and --ml-wallet-smoke-address", file=sys.stderr)
                return 2
            graph = load_graph_for_scoring(args.ml_wallet_smoke_graph)
            model_path = args.ml_wallet_model or settings.ML_WALLET_MODEL_PATH
            scorer = WalletMLScorer(model_path=model_path)
            scored = scorer.score(args.ml_wallet_smoke_address, graph)
            if not scored:
                print("Wallet smoke test failed: model not loaded or no score", file=sys.stderr)
                return 2
            print("Wallet smoke result:", scored)

        return 0

    if not args.address:
        print("Missing --address for tracing", file=sys.stderr)
        return 2

    cfg = TraceConfig(
        address=args.address,
        days=args.days,
        hops=args.hops,
        min_usd=Decimal(args.min_usd),
        max_edges_per_address=args.max_edges_per_address,
        max_total_edges=args.max_total_edges,
        ignore_unknown_price=args.ignore_unknown_price,
        skip_contract_check=not args.enable_contract_check,
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
    risk = TokenRiskAdapter()
    wallet_risk = None
    if settings.ML_WALLET_MODEL_PATH and os.path.exists(settings.ML_WALLET_MODEL_PATH):
        wallet_risk = WalletRiskMLAdapter()
    svc = TracerService(chain=chain, price=price, token_risk=risk, wallet_risk=wallet_risk)
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
    html_path = None
    if args.html:
        html_path = write_graph_html(graph, args.out)

    print(f"Wrote: {graph_path}")
    print(f"Wrote: {summary_path}")
    if html_path:
        print(f"Wrote: {html_path}")

    if args.ml_auto_train:
        token_labels_path = os.path.join(args.out, "tokens.csv")
        token_dataset_path = os.path.join(args.out, "token_features.csv")
        print("ML auto-train: building token labels...")
        build_token_labels_from_graph(graph, token_labels_path)
        print("ML auto-train: building token dataset...")
        build_token_dataset_from_graph(graph, token_dataset_path)
        if os.path.exists(token_dataset_path):
            model_path = args.ml_token_model or settings.ML_TOKEN_MODEL_PATH
            print(f"ML auto-train: training token model ({token_dataset_path})...")
            metrics = train_token_model(token_dataset_path, model_path)
            roc_auc = metrics.get("roc_auc")
            accuracy = (metrics.get("report") or {}).get("accuracy")
            n_samples = metrics.get("n_samples")
            print(f"Wrote token labels: {token_labels_path}")
            print(f"Wrote token dataset: {token_dataset_path}")
            print(f"Wrote token model: {model_path}")
            if n_samples is not None:
                print("Token samples:", n_samples)
            if accuracy is not None:
                print("Token accuracy:", accuracy)
            if roc_auc is not None:
                print("Token ROC AUC:", roc_auc)
        else:
            print("No token dataset generated; skipping ML training.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
