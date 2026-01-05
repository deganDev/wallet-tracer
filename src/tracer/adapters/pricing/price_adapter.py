from __future__ import annotations

from decimal import Decimal
from typing import Optional

from tracer.ports.price_port import PricePort
from tracer.config import settings


class PriceAdapter(PricePort):

    def get_eth_usd_price(self, timestamp: int) -> Decimal:
        return settings.ETH_USD_FALLBACK

    def get_token_usd_price(self, token_address: str, timestamp: int) -> Optional[Decimal]:
        addr = token_address.lower()

        if addr in settings.FIXED_TOKEN_USD:
            return settings.FIXED_TOKEN_USD[addr]

        if addr in settings.STABLECOIN_ADDRESSES:
            return Decimal("1")

        return None
