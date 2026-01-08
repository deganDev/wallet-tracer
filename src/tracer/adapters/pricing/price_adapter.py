from __future__ import annotations

from decimal import Decimal
from typing import Optional

from tracer.adapters.risk.dexscreener_adapter import DexScreenerAdapter
from tracer.ports.price_port import PricePort
from tracer.config import settings


class PriceAdapter(PricePort):
    def __init__(self) -> None:
        self._dexscreener = DexScreenerAdapter()
        self._price_cache: dict[str, Decimal] = {}

    def get_eth_usd_price(self, timestamp: int) -> Decimal:
        return settings.ETH_USD_FALLBACK

    def get_token_usd_price(self, token_address: str, timestamp: int) -> Optional[Decimal]:
        addr = token_address.lower()

        if addr in settings.FIXED_TOKEN_USD:
            return settings.FIXED_TOKEN_USD[addr]

        if addr in settings.STABLECOIN_ADDRESSES:
            return Decimal("1")

        if addr in self._price_cache:
            return self._price_cache[addr]

        try:
            pairs = self._dexscreener.get_pairs(addr)
        except Exception:
            return None

        best_price = None
        best_liquidity = Decimal("-1")
        for p in pairs:
            if p.price_usd is None:
                continue
            liquidity = p.liquidity_usd or Decimal("0")
            if liquidity >= best_liquidity:
                best_liquidity = liquidity
                best_price = p.price_usd

        if best_price is not None:
            self._price_cache[addr] = best_price
            return best_price

        return None
