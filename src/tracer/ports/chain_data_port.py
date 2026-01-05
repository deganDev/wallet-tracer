from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Optional
from tracer.core.dto import RawEthTransfer, RawErc20Transfer, TokenMeta

class ChainDataPort(ABC):
    """
    Abstract Class for fetching chain-related facts for tracing.
    """

    # --- Blocks / time window helpers ---

    @abstractmethod
    def get_block_number_by_time(self, unix_ts: int, closest: str = "before") -> int:
        raise NotImplementedError

    # --- ETH transfers (normal transactions) ---

    @abstractmethod
    def iter_normal_txs(
        self,
        address: str,
        start_block: int,
        end_block: int,
        sort: str = "asc",
    ) -> Iterable[RawEthTransfer]:
        raise NotImplementedError

    # --- ERC-20 Transfer events ---

    @abstractmethod
    def iter_erc20_transfers(
        self,
        address: str,
        start_block: int,
        end_block: int,
        sort: str = "asc",
        token_address: Optional[str] = None,
    ) -> Iterable[RawErc20Transfer]:
        raise NotImplementedError

    # --- Is-Contrcat checker ---

    @abstractmethod
    def is_contract(self, address: str) -> bool:
        raise NotImplementedError
    
    # --- check token metadata ---
    @abstractmethod
    def get_token_meta(self, token_address: str) -> TokenMeta:
        raise NotImplementedError
