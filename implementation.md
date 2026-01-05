# Scam Token Detection Implementation Plan

This document describes the data sources, APIs, and step-by-step tasks to implement
the full Ethereum scam-token detection policy described in the request.

## Goals
- Detect and label token risks using the full label set and policies provided.
- Combine static analysis, on-chain state, and simulation where possible.
- Emit token-level labels + risk score in outputs.

## Data Sources / APIs

### 1) Etherscan (existing adapter, extend)
Purpose: chain time windows, transfers, contract code, ABI, and metadata.
Base: `https://api.etherscan.io/v2/api`

Planned endpoints (module/action):
- `block/getblocknobytime` for timestamps to blocks (already used).
- `account/txlist` for normal transactions (already used).
- `account/tokentx` for ERC20 transfers (already used).
- `proxy/eth_getCode` for contract detection (already used).
- `contract/getsourcecode` for verified source + metadata (new).
- `contract/getabi` for ABI analysis (new).

Notes:
- Use existing rate limiter and retry logic.
- Cache contract meta responses to reduce API usage.

### 2) Ethereum JSON-RPC (new adapter/port)
Purpose: on-chain calls and simulations that Etherscan cannot provide.
Examples: `eth_call`, `eth_getLogs`, `eth_getCode`, `debug_traceCall` (if supported).

Provider options:
- Alchemy, Infura, or a self-hosted node.
- Require environment variable (e.g., `ETH_RPC_URL`).

Use cases:
- Transfer simulations (transfer to EOA or router).
- Detect blacklist/whitelist behavior via `eth_call` to `transfer`.
- Query owner/role storage, `owner()`/`getRoleMember`, etc.
- Pull logs for liquidity remove events or mint events.

### 3) DexScreener API (new)
Purpose: liquidity, pairs, volume, and market metadata.
Base: `https://api.dexscreener.com/latest/dex/`

Planned endpoints:
- `tokens/{tokenAddress}` to list pairs, liquidity USD, volume, and pair creation.

Use cases:
- Liquidity thin, pair age, single pair only, LP concentration heuristics.

### 4) RugCheck API (new)
Purpose: curated risk flags and holder/LP breakdowns when available.
Base: `https://api.rugcheck.xyz/` (or provider-specific base)

Planned endpoints (example):
- `v1/tokens/{tokenAddress}` for risk report.

Use cases:
- LP lock status, top holders, mint/blacklist flags, known reports.

### 5) GoPlus / Honeypot.is (optional, new)
Purpose: honeypot and tax detection via simulation proxies.

Planned endpoints (example):
- GoPlus: `token_security` / `token_security/{chainId}?contract_addresses=...`
- Honeypot.is: `v2/IsHoneypot?address=...&chain=eth`

Use cases:
- Honeypot sell blocked, buy/sell tax extremes, transfer restrictions.

### 6) Known Scam Lists (optional)
Purpose: curated blocklists.

Potential sources:
- Internal lists (CSV/JSON).
- Public lists (if you have licensing/permission).

Use cases:
- `KNOWN_SCAM_REPORTS`.

## Data Model Changes

### Token risk model (new)
- Add `TokenRisk` dataclass with:
  - `token_address`
  - `label` (SCAM_CONFIRMED/HIGH_RISK/MEDIUM_RISK/LOW_RISK/UNKNOWN)
  - `score` (0-100)
  - `risk_flags` (list of specific labels)
  - `signals` (optional details for audit/debug)

### Graph output
- Add `Graph.tokens` map or attach `risk` to `Edge`.
- Update JSON schema and summary output to include token risk metadata.

## New Ports / Adapters

### TokenRiskPort (new)
Interface methods:
- `get_token_risk(token_address: str, timestamp: int) -> TokenRisk`

Adapters:
- `CompositeTokenRiskAdapter` that merges signals from:
  - EtherscanTokenAnalyzer (source + ABI)
  - DexScreenerAdapter
  - RugCheckAdapter
  - Honeypot/GoPlusAdapter
  - RpcSimulatorAdapter

## Detection Pipeline (high-level)

1) Collect base metadata:
   - Token metadata (symbol, decimals, name).
   - Verified source status, ABI, proxy detection.

2) Static analysis (contract source/ABI):
   - Detect owner roles, mint, blacklist, pause, fee setters.
   - Detect proxy upgradeability.
   - Label code-quality issues (unverified, suspicious patterns).

3) On-chain state analysis:
   - Holder distribution (top holders %).
   - Liquidity providers + lock/burn status.
   - Liquidity removal events.

4) Simulation checks:
   - Buy/sell simulation, transfer calls.
   - Estimate buy/sell tax.
   - Honeypot sell blocked.

5) Score aggregation:
   - Apply weights and thresholds per policy.
   - Apply positive signals (LP burned, owner renounced).
   - Emit final label + risk flags.

## Change Sets (what will change)

1) **Core models + schema**
   - Update `src/tracer/core/models.py` to add `TokenRisk` and store token risk in `Graph`.
   - Update `src/tracer/io/schemas.py` to emit token risk fields in JSON.
   - Update `src/tracer/io/output_writer.py` to include risk summary items.

2) **Ports**
   - Add `src/tracer/ports/token_risk_port.py`.
   - Extend `src/tracer/ports/chain_data_port.py` if any new chain calls are needed.

3) **Adapters**
   - Extend `src/tracer/adapters/chain/etherscan_chain_adapter.py` with:
     `get_contract_source`, `get_contract_abi`, and cached contract meta.
   - Add `src/tracer/adapters/chain/rpc_chain_adapter.py` for JSON-RPC calls.
   - Add `src/tracer/adapters/risk/` adapters:
     - `dexscreener_adapter.py`
     - `rugcheck_adapter.py`
     - `honeypot_adapter.py` or `goplus_adapter.py`
     - `scamlist_adapter.py` (optional)
   - Add `src/tracer/adapters/risk/composite_risk_adapter.py` to aggregate signals.

4) **Services**
   - Update `src/tracer/services/tracer_service.py` to resolve token risk
     once per token and attach results to edges or `Graph.tokens`.

5) **CLI + config**
   - Update `src/tracer/cli/main.py` to add flags to enable/disable risk checks
     and to supply provider keys.
   - Update `src/tracer/config/settings.py` to add API base URLs and keys.

6) **Tests**
   - Add unit tests under `tests/` for scoring, flags, and adapters.
   - Add fixtures for API responses.

## Task Breakdown (small steps, ordered)

1) **Define data models**
   - Add `TokenRisk` dataclass.
   - Decide where token risk is stored (`Graph.tokens` vs `Edge.risk`).

2) **Add TokenRiskPort**
   - Create `token_risk_port.py` with `get_token_risk`.
   - Create a stub implementation returning UNKNOWN.

3) **Extend Etherscan adapter**
   - Implement `get_contract_source` and `get_contract_abi`.
   - Add cached contract metadata.

4) **Add JSON-RPC adapter**
   - Implement `eth_call`, `eth_getLogs`, and helper call encoders.
   - Use `ETH_RPC_URL` from config/env.

5) **Static analyzer (ABI/source)**
   - Detect mint/fee/blacklist/pause/owner methods.
   - Detect proxy upgradeability.
   - Emit owner/admin control flags.

6) **Liquidity + holders analyzer**
   - Pull pairs and liquidity from DexScreener.
   - Pull LP lock/holder concentration from RugCheck.
   - Emit liquidity and distribution flags.

7) **Honeypot + tax analyzer**
   - Use Honeypot/GoPlus or RPC simulations to estimate buy/sell tax.
   - Emit honeypot and tax flags.

8) **Known scam list integration**
   - Load optional curated lists.
   - Emit `KNOWN_SCAM_REPORTS`.

9) **Scoring engine**
   - Apply weights + thresholds.
   - Add positive signals and caps.
   - Produce final label.

10) **Service integration**
   - Attach token risk in `TracerService`.
   - Add CLI option for risk checks.

11) **Outputs**
   - Update JSON and markdown outputs to include risk labels and flags.

12) **Testing**
   - Unit tests for scoring + label logic.
   - Adapter tests with mocked HTTP/JSON-RPC responses.

## Open Config Knobs (defaults)
- `max_buy_tax_pct` (15)
- `max_sell_tax_pct` (15)
- `min_liquidity_usd` (25000)
- `min_lp_lock_days` (30)
- `max_top10_holder_pct` (60)
- `new_token_age_hours_high_risk` (24)
- `require_verified_source` (false)
