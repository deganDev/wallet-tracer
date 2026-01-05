from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Deque, Dict, Iterable, List, Optional, Set, Tuple

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

    def trace(
        self,
        cfg: TraceConfig,
        on_progress: Optional[Callable[[str, Dict[str, object]], None]] = None,
    ) -> Graph:
        now_ts_raw = getattr(cfg, "now_ts", 0)
        if now_ts_raw is None:
            now_ts = int(time.time())
        else:
            now_ts = int(now_ts_raw) or int(time.time())
        start_ts = now_ts - int(cfg.days) * 24 * 3600
        processed = 0

        def _emit(event: str, data: Dict[str, object]) -> None:
            if on_progress is None:
                return
            try:
                on_progress(event, data)
            except Exception:
                # Progress is best-effort; avoid breaking tracing on UI issues.
                return

        _emit(
            "start",
            {
                "address": cfg.address,
                "days": cfg.days,
                "hops": cfg.hops,
                "min_usd": cfg.min_usd,
                "start_ts": start_ts,
                "now_ts": now_ts,
            },
        )

        # Block window
        start_block = self.chain.get_block_number_by_time(start_ts, closest="after")
        end_block = self.chain.get_block_number_by_time(now_ts, closest="before")

        graph = Graph(nodes={}, edges=[])

        # Hops
        q: Deque[_hopItem] = deque([_hopItem(cfg.address.lower(), 0)])
        seen_addr_depth: Set[Tuple[str, int]] = set()

        # limits
        total_edges_added = 0
        contract_stats = {"checked": 0, "errors": 0}
        seen_edge_keys: Set[Tuple[str, str, str, str, Optional[str]]] = set()

        while q:
            item = q.popleft()
            addr = item.address.lower()
            depth = item.depth
            processed += 1

            if depth > int(cfg.hops):
                continue

            key = (addr, depth)
            if key in seen_addr_depth:
                continue
            seen_addr_depth.add(key)

            # ensure node
            self._ensure_node(
                graph,
                addr,
                on_progress=on_progress,
                stats=contract_stats,
                skip_contract_check=bool(getattr(cfg, "skip_contract_check", True)),
            )

            # collect edges for this address
            new_edges: List[Edge] = []
            _emit("fetch", {"phase": "eth", "address": addr, "depth": depth})
            eth_edges = self._eth_edges_for(addr, start_block, end_block)
            _emit("fetch_done", {"phase": "eth", "address": addr, "count": len(eth_edges)})
            new_edges.extend(eth_edges)

            _emit("fetch", {"phase": "erc20", "address": addr, "depth": depth})
            erc20_edges = self._erc20_edges_for(
                addr,
                start_block,
                end_block,
                ignore_unknown_price=bool(getattr(cfg, "ignore_unknown_price", False)),
            )
            _emit("fetch_done", {"phase": "erc20", "address": addr, "count": len(erc20_edges)})
            new_edges.extend(erc20_edges)

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
                edge_key = (e.tx_hash, e.from_address, e.to_address, e.asset_type, e.token_address)
                if edge_key in seen_edge_keys:
                    continue
                seen_edge_keys.add(edge_key)
                graph.edges.append(e)
                total_edges_added += 1
                self._ensure_node(
                    graph,
                    e.from_address,
                    on_progress=on_progress,
                    stats=contract_stats,
                    skip_contract_check=bool(getattr(cfg, "skip_contract_check", True)),
                )
                self._ensure_node(
                    graph,
                    e.to_address,
                    on_progress=on_progress,
                    stats=contract_stats,
                    skip_contract_check=bool(getattr(cfg, "skip_contract_check", True)),
                )

            # enqueue neighbors for next hop
            if depth < int(cfg.hops):
                neighbors = self._neighbor_addresses(addr, new_edges)
                for n in neighbors:
                    q.append(_hopItem(n, depth + 1))

            _emit(
                "visit",
                {
                    "address": addr,
                    "depth": depth,
                    "queue": len(q),
                    "processed": processed,
                    "edges": total_edges_added,
                },
            )

        _emit(
            "done",
            {
                "processed": processed,
                "nodes": len(graph.nodes),
                "edges": len(graph.edges),
                "contract_checked": contract_stats["checked"],
                "contract_errors": contract_stats["errors"],
            },
        )
        return graph

    # -------------------------
    # Edge builders
    # -------------------------

    def _eth_edges_for(self, address: str, start_block: int, end_block: int) -> List[Edge]:
        edges: List[Edge] = []
        

        for tx in self.chain.iter_normal_txs(address, start_block, end_block, sort="asc"):
            # ETH transfer means value > 0
            if tx.value_wei <= 0:
                continue
           
            eth_usd = self.price.get_eth_usd_price(tx.timestamp)
            amount_eth = (Decimal(tx.value_wei) / WEI_PER_ETH)
            usd_value = amount_eth * eth_usd

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

    def _erc20_edges_for(
        self,
        address: str,
        start_block: int,
        end_block: int,
        ignore_unknown_price: bool = False,
    ) -> List[Edge]:
        edges: List[Edge] = []

        for tx in self.chain.iter_erc20_transfers(address, start_block, end_block, sort="asc"):
            decimals = tx.token_decimals
            symbol = tx.token_symbol

            amount = Decimal(tx.value_raw)
            if decimals is not None:
                # token amount normalization
                amount = amount / (Decimal(10) ** Decimal(decimals))

            token_price = self.price.get_token_usd_price(tx.token_address, tx.timestamp)
            if ignore_unknown_price and token_price is None:
                continue
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

    def _ensure_node(
        self,
        graph: Graph,
        address: str,
        on_progress: Optional[Callable[[str, Dict[str, object]], None]] = None,
        stats: Optional[Dict[str, int]] = None,
        skip_contract_check: bool = True,
    ) -> None:
        addr = address.lower()
        if addr in graph.nodes:
            return

        # best-effort contract tagging (nice for investigators)
        if skip_contract_check:
            is_contract = False
        else:
            try:
                is_contract = bool(self.chain.is_contract(addr))
            except Exception:
                if stats is not None:
                    stats["errors"] += 1
                is_contract = False
            if stats is not None:
                stats["checked"] += 1
                if on_progress is not None and stats["checked"] % 25 == 0:
                    on_progress(
                        "contract_progress",
                        {"checked": stats["checked"], "errors": stats["errors"]},
                    )

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
