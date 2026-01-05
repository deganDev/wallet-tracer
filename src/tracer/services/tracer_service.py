from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Deque, Dict, Iterable, List, Optional, Set, Tuple

from tracer.ports.chain_data_port import ChainDataPort
from tracer.ports.price_port import PricePort
from tracer.core.models import Graph, Node, Edge, TraceConfig


WEI_PER_ETH = Decimal("1000000000000000000")


@dataclass(frozen=True)
class _hopItem:
    address: str
    depth: int


class TracerService:
    """
    Builds an investigator-friendly value-flow graph from a seed address.

    - Traversal: hops (depth)
    - Data: ETH transfers + ERC-20 Transfer events
    - Ignores: internal tx tracing, approvals, NFTs, contract decoding
    """

    def __init__(self, chain: ChainDataPort, price: PricePort) -> None:
        self.chain = chain
        self.price = price

    def trace(self, cfg: TraceConfig) -> Graph:
        now_ts = int(getattr(cfg, "now_ts", 0)) or int(time.time())
        start_ts = now_ts - int(cfg.days) * 24 * 3600

        # Block window
        start_block = self.chain.get_block_number_by_time(start_ts, closest="after")
        end_block = self.chain.get_block_number_by_time(now_ts, closest="before")

        graph = Graph(nodes={}, edges=[])

        # Hops
        q: Deque[_hopItem] = deque([_hopItem(cfg.address.lower(), 0)])
        seen_addr_depth: Set[Tuple[str, int]] = set()

        # limits
        total_edges_added = 0

        while q:
            item = q.popleft()
            addr = item.address.lower()
            depth = item.depth

            if depth > int(cfg.hops):
                continue

            key = (addr, depth)
            if key in seen_addr_depth:
                continue
            seen_addr_depth.add(key)

            # ensure node
            self._ensure_node(graph, addr)

            # collect edges for this address
            new_edges: List[Edge] = []
            new_edges.extend(self._eth_edges_for(addr, start_block, end_block))
            new_edges.extend(self._erc20_edges_for(addr, start_block, end_block))

            # apply min_usd filter
            new_edges = self._apply_min_usd(new_edges, Decimal(str(cfg.min_usd)))

            # dedupe edges (by tx_hash + from + to + asset + token)
            new_edges = self._dedupe_edges(new_edges)

            # prioritize by usd_value desc (unknowns last)
            new_edges.sort(key=self._edge_sort_key, reverse=True)

            # limit edges per address per hop (optional config)
            per_addr_limit = int(getattr(cfg, "max_edges_per_address", 0) or 0)
            if per_addr_limit > 0:
                new_edges = new_edges[:per_addr_limit]

            # limit total edges (optional config)
            max_total = int(getattr(cfg, "max_total_edges", 0) or 0)
            if max_total > 0:
                remaining = max_total - total_edges_added
                if remaining <= 0:
                    break
                new_edges = new_edges[:remaining]

            # add edges + nodes
            for e in new_edges:
                graph.edges.append(e)
                total_edges_added += 1
                self._ensure_node(graph, e.from_address)
                self._ensure_node(graph, e.to_address)

            # enqueue neighbors for next hop
            if depth < int(cfg.hops):
                neighbors = self._neighbor_addresses(addr, new_edges)
                for n in neighbors:
                    q.append(_hopItem(n, depth + 1))

        return graph

    # -------------------------
    # Edge builders
    # -------------------------

    def _eth_edges_for(self, address: str, start_block: int, end_block: int) -> List[Edge]:
        edges: List[Edge] = []
        eth_usd = self.price.get_eth_usd_price

        for tx in self.chain.iter_normal_txs(address, start_block, end_block, sort="asc"):
            # ETH transfer means value > 0
            if tx.value_wei <= 0:
                continue

            amount_eth = (Decimal(tx.value_wei) / WEI_PER_ETH)
            usd_value = amount_eth * eth_usd(tx.timestamp)

            edges.append(
                Edge(
                    from_address=tx.from_address.lower(),
                    to_address=tx.to_address.lower(),
                    tx_hash=tx.tx_hash,
                    timestamp=tx.timestamp,
                    asset_type="ETH",
                    token_address=None,
                    symbol="ETH",
                    amount=amount_eth,
                    usd_value=usd_value,
                )
            )

        return edges

    def _erc20_edges_for(self, address: str, start_block: int, end_block: int) -> List[Edge]:
        edges: List[Edge] = []

        for tx in self.chain.iter_erc20_transfers(address, start_block, end_block, sort="asc"):
            decimals = tx.token_decimals
            symbol = tx.token_symbol

            amount = Decimal(tx.value_raw)
            if decimals is not None:
                # token amount normalization
                amount = amount / (Decimal(10) ** Decimal(decimals))

            token_price = self.price.get_token_usd_price(tx.token_address, tx.timestamp)
            usd_value = (amount * token_price) if token_price is not None else None

            edges.append(
                Edge(
                    from_address=tx.from_address.lower(),
                    to_address=tx.to_address.lower(),
                    tx_hash=tx.tx_hash,
                    timestamp=tx.timestamp,
                    asset_type="ERC20",
                    token_address=tx.token_address.lower(),
                    symbol=symbol,
                    amount=amount,
                    usd_value=usd_value,
                )
            )

        return edges

    # -------------------------
    # Helpers
    # -------------------------

    def _ensure_node(self, graph: Graph, address: str) -> None:
        addr = address.lower()
        if addr in graph.nodes:
            return

        # best-effort contract tagging (nice for investigators)
        try:
            is_contract = bool(self.chain.is_contract(addr))
        except Exception:
            is_contract = False

        graph.nodes[addr] = Node(address=addr, is_contract=is_contract)

    def _apply_min_usd(self, edges: List[Edge], min_usd: Decimal) -> List[Edge]:
        if min_usd <= 0:
            return edges

        kept: List[Edge] = []
        for e in edges:
            # unknown price -> keep (but will rank lower)
            if e.usd_value is None:
                kept.append(e)
            elif e.usd_value >= min_usd:
                kept.append(e)
        return kept

    def _dedupe_edges(self, edges: List[Edge]) -> List[Edge]:
        seen: Set[Tuple[str, str, str, str, Optional[str]]] = set()
        out: List[Edge] = []
        for e in edges:
            k = (e.tx_hash, e.from_address, e.to_address, e.asset_type, e.token_address)
            if k in seen:
                continue
            seen.add(k)
            out.append(e)
        return out

    def _neighbor_addresses(self, focus: str, edges: List[Edge]) -> List[str]:
        s: Set[str] = set()
        for e in edges:
            s.add(e.from_address)
            s.add(e.to_address)
        s.discard(focus.lower())
        return sorted(s)

    @staticmethod
    def _edge_sort_key(e: Edge) -> Decimal:
        # unknown usd_value goes last
        if e.usd_value is None:
            return Decimal("-1")
        return Decimal(e.usd_value)
