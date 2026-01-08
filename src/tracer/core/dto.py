from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional


@dataclass(frozen=True)
class RawEthTransfer:
    tx_hash: str
    block_number: int
    timestamp: int
    from_address: str
    to_address: str
    value_wei: int          # ETH value in wei (raw)


@dataclass(frozen=True)
class RawErc20Transfer:
    tx_hash: str
    block_number: int
    timestamp: int
    from_address: str
    to_address: str
    token_address: str
    value_raw: int          # token amount in raw units (before decimals)
    token_symbol: Optional[str] = None
    token_decimals: Optional[int] = None


@dataclass(frozen=True)
class TokenMeta:
    token_address: str
    symbol: Optional[str]
    decimals: Optional[int]
    name: Optional[str] = None       


@dataclass(frozen=True)
class DexScreenerPair:
    chain_id: str
    dex_id: str
    pair_address: str
    base_token: str
    quote_token: str
    price_usd: Optional[Decimal]
    liquidity_usd: Optional[Decimal]
    volume_24h: Optional[Decimal]
    fdv: Optional[Decimal]
    market_cap: Optional[Decimal]
    pair_created_at: Optional[int]


@dataclass(frozen=True)
class DexScreenerAnalysis:
    pairs: List[DexScreenerPair]
    total_liquidity_usd: Decimal
    max_liquidity_usd: Decimal
    pair_count: int
    newest_pair_age_hours: Optional[Decimal]
    oldest_pair_age_hours: Optional[Decimal]
    flags: List[str]
