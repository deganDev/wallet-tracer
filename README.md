# Wallet Tracer

This is a small, weekend‑style Ethereum wallet tracer. You point it at a seed
address and it builds a value‑flow graph that an investigator can scan quickly.
It’s intentionally scoped: ETH transfers + ERC‑20 Transfer events, a time window,
and a hop limit. Nothing fancy, just clear signal.

## What it does

- Traces ETH transfers + ERC‑20 Transfer events
- Expands across hops from a seed address
- Filters by USD value (simple pricing rules)
- Outputs `graph.json` (machine‑readable) and `summary.md` (human‑readable)

## Install

This repo uses a plain Python setup. You can run it with your current environment
or create a virtualenv.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

If you prefer `uv`:

```bash
uv pip install -e .
```

## Quick start

```bash
export ETHERSCAN_API_KEY=your_key_here
python -m tracer.cli.main --address 0xdadb0d80178819f2319190d340ce9a924f783711 --days 1 --hops 2
```

Outputs land in `./out` by default:

- `out/graph.json` — full node/edge graph
- `out/summary.md` — human‑readable summary

## Options

```bash
python -m tracer.cli.main \
  --address <address> \
  --days 30 \
  --hops 2 \
  --min-usd 1000 \
  --max-edges-per-address 0 \
  --max-total-edges 0 \
  --ignore-unknown-price \
  --enable-contract-check \
  --html \
  --out out
```

## ML training and evaluation

Token dataset build + train + eval:

```bash
python -m tracer.cli.main \
  --ml-token-labels data/tokens.csv \
  --ml-token-dataset data/token_features.csv \
  --ml-token-model models/token_risk.pkl \
  --ml-token-eval
```

Wallet dataset build + train + eval:

```bash
python -m tracer.cli.main \
  --ml-wallet-labels data/wallets.csv \
  --ml-wallet-dataset data/wallet_features.csv \
  --ml-wallet-model models/wallet_risk.pkl \
  --ml-wallet-eval
```

Smoke tests:

```bash
python -m tracer.cli.main --ml-token-smoke 0xTOKEN --ml-token-model models/token_risk.pkl
python -m tracer.cli.main --ml-wallet-smoke-graph out/graph.json --ml-wallet-smoke-address 0xWALLET --ml-wallet-model models/wallet_risk.pkl
```

Expected CSV formats:

- Tokens: `token_address,label`
- Wallets: `graph_path,address,label`

Note: token dataset building calls DexScreener, so it needs network access.

### Static adapter (dev/testing)

If you want to run without Etherscan:

```bash
python -m tracer.cli.main --address <address> --use-static
```

### Auto-train token ML from a trace

This uses heuristic token labels (SCAM_CONFIRMED/HIGH_RISK -> 1, else 0) and
builds `out/tokens.csv`, `out/token_features.csv`, then trains a model.

```bash
python -m tracer.cli.main \
  --address <address> \
  --days 30 \
  --hops 0 \
  --min-usd 1 \
  --out out \
  --ml-auto-train
```

## Notes

- Pricing is intentionally simple (see `src/tracer/adapters/pricing/price_adapter.py`).
- Contract detection calls `eth_getCode` per new node, which can be slow on rate limits.
- This is a graph builder, not a transaction debugger (no internal txs, approvals, NFTs).
- Runtime knobs (Etherscan key, rate limits, pricing defaults) live in `src/tracer/config/settings.py`.
  See that file for the full list and comments.

## Scope (what’s in / out)

Included:

- ETH transfers
- ERC‑20 Transfer events

Not included (by design):

- NFTs (ERC‑721 / ERC‑1155)
- Internal tx tracing via debug APIs
- Approvals / contract decoding
- Cross‑chain activity

## Output

`graph.json` includes nodes and edges with:

- from, to
- tx_hash
- timestamp
- asset (ETH or token address + symbol if available)
- amount
- usd_value (best‑effort)

`summary.md` is a short investigator‑friendly report.

If you pass `--html`, the tracer also writes `out/index.html`. Open it with a local server:

```bash
cd out
python -m http.server
```

## Troubleshooting

- **Missing ETHERSCAN_API_KEY**: set it in your environment or a `.env` file.
- **Looks stuck**: large wallets can take time; you’ll see live progress in the CLI.
- **Rate limits**: reduce hop count or raise `ETHERSCAN_REQUESTS_PER_SEC` in settings.

## Tests

TracerService tests run against the `StaticChainAdapter` with deterministic data.

```bash
python -m unittest tests.test_tracer_service
```

## Repo structure

```
src/tracer/cli        # CLI entrypoint
src/tracer/services   # tracer logic
src/tracer/adapters   # Etherscan + pricing adapters
src/tracer/core       # models + DTOs
```
