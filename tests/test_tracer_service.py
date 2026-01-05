import unittest
from decimal import Decimal

from tracer.adapters.chain.static_chain_adapter import StaticChainAdapter
from tracer.core.dto import RawErc20Transfer, RawEthTransfer
from tracer.core.models import TraceConfig
from tracer.ports.price_port import PricePort
from tracer.services.tracer_service import TracerService


class _StaticPrice(PricePort):
    def __init__(self, token_prices=None, eth_price=Decimal("2000")) -> None:
        self._token_prices = {k.lower(): v for k, v in (token_prices or {}).items()}
        self._eth_price = eth_price

    def get_eth_usd_price(self, timestamp: int) -> Decimal:
        return self._eth_price

    def get_token_usd_price(self, token_address: str, timestamp: int):
        return self._token_prices.get(token_address.lower())


class TracerServiceTests(unittest.TestCase):
    def _make_cfg(self, address: str, **overrides) -> TraceConfig:
        defaults = dict(
            address=address,
            days=0,
            hops=0,
            min_usd=Decimal("0"),
            now_ts=1000,
        )
        defaults.update(overrides)
        return TraceConfig(**defaults)

    def test_eth_transfer_creates_edge_and_nodes(self) -> None:
        seed = "0xaaaa"
        dest = "0xbbbb"
        eth_tx = RawEthTransfer(
            tx_hash="0xeth",
            block_number=10,
            timestamp=900,
            from_address=seed,
            to_address=dest,
            value_wei=10**18,
        )
        chain = StaticChainAdapter(
            eth_transfers=[eth_tx],
            ts_to_block={1000: 10},
        )
        price = _StaticPrice(eth_price=Decimal("2500"))
        svc = TracerService(chain=chain, price=price)

        graph = svc.trace(self._make_cfg(seed))

        self.assertEqual(len(graph.edges), 1)
        self.assertIn(seed, graph.nodes)
        self.assertIn(dest, graph.nodes)
        self.assertEqual(graph.edges[0].usd_value, Decimal("2500"))

    def test_hop_expansion_follows_neighbors(self) -> None:
        seed = "0xaaaa"
        mid = "0xbbbb"
        end = "0xcccc"
        token = "0xtoken"
        t1 = RawErc20Transfer(
            tx_hash="0x1",
            block_number=10,
            timestamp=900,
            from_address=seed,
            to_address=mid,
            token_address=token,
            value_raw=100,
            token_symbol="TKN",
            token_decimals=2,
        )
        t2 = RawErc20Transfer(
            tx_hash="0x2",
            block_number=10,
            timestamp=901,
            from_address=mid,
            to_address=end,
            token_address=token,
            value_raw=200,
            token_symbol="TKN",
            token_decimals=2,
        )
        chain = StaticChainAdapter(
            erc20_transfers=[t1, t2],
            ts_to_block={1000: 10},
        )
        price = _StaticPrice(token_prices={token: Decimal("1")})
        svc = TracerService(chain=chain, price=price)

        cfg = self._make_cfg(seed, hops=2)
        graph = svc.trace(cfg)

        self.assertEqual(len(graph.edges), 2)
        self.assertIn(end, graph.nodes)

    def test_ignore_unknown_price_skips_erc20(self) -> None:
        seed = "0xaaaa"
        token = "0xtoken"
        t1 = RawErc20Transfer(
            tx_hash="0x1",
            block_number=10,
            timestamp=900,
            from_address=seed,
            to_address="0xbbbb",
            token_address=token,
            value_raw=100,
            token_symbol="TKN",
            token_decimals=2,
        )
        chain = StaticChainAdapter(
            erc20_transfers=[t1],
            ts_to_block={1000: 10},
        )
        price = _StaticPrice()
        svc = TracerService(chain=chain, price=price)

        cfg = self._make_cfg(seed, ignore_unknown_price=True)
        graph = svc.trace(cfg)

        self.assertEqual(len(graph.edges), 0)


if __name__ == "__main__":
    unittest.main()
