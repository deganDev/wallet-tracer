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
python -m tracer.cli.main --seed 0xdadb0d80178819f2319190d340ce9a924f783711 --days 1 --hops 2
```

Outputs land in `./out` by default:

- `out/graph.json` — full node/edge graph
- `out/summary.md` — human‑readable summary

## Options

```bash
python -m tracer.cli.main \
  --seed <address> \
  --days 30 \
  --hops 2 \
  --min-usd 1000 \
  --max-edges-per-address 0 \
  --max-total-edges 0 \
  --out out
```

### Static adapter (dev/testing)

If you want to run without Etherscan:

```bash
python -m tracer.cli.main --seed <address> --use-static
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

## Troubleshooting

- **Missing ETHERSCAN_API_KEY**: set it in your environment or a `.env` file.
- **Looks stuck**: large wallets can take time; you’ll see live progress in the CLI.
- **Rate limits**: reduce hop count or raise `ETHERSCAN_REQUESTS_PER_SEC` in settings.

## Repo structure

```
src/tracer/cli        # CLI entrypoint
src/tracer/services   # tracer logic
src/tracer/adapters   # Etherscan + pricing adapters
src/tracer/core       # models + DTOs
```
