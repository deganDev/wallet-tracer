from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional


class PricePort(ABC):

    @abstractmethod
    def get_eth_usd_price(self, timestamp: int) -> Decimal:
        raise NotImplementedError

    @abstractmethod
    def get_token_usd_price(self, token_address: str, timestamp: int) -> Optional[Decimal]:
        raise NotImplementedError
