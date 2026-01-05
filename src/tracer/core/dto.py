from dataclasses import dataclass
from typing import Optional

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
