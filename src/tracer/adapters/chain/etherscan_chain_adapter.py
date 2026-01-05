from typing import Any, Dict, Iterable, Optional
import requests

from tracer.config.settings import (
    ETHERSCAN_API_KEY,
    ETHERSCAN_CHAIN_ID,
    ETHERSCAN_BASE_URL,
    ETHERSCAN_REQUESTS_PER_SEC,
    ETHERSCAN_TIMEOUT_SEC,
    ETHERSCAN_MAX_RETRIES,
    ETHERSCAN_PAGE_SIZE,
)

from tracer.adapters.chain.rate_limiter import SimpleRateLimiter, backoff_sleep
from tracer.core.errors import DataSourceError, RateLimitError
from tracer.ports.chain_data_port import ChainDataPort
from tracer.core.dto import RawErc20Transfer, RawEthTransfer, TokenMeta


class EtherscanChainAdapter(ChainDataPort):

    def __init__(self) -> None:
        self._api_key = ETHERSCAN_API_KEY
        self._chainid = ETHERSCAN_CHAIN_ID
        self._base_url = ETHERSCAN_BASE_URL
        self._timeout = ETHERSCAN_TIMEOUT_SEC
        self._max_retries = ETHERSCAN_MAX_RETRIES
        self._page_size = ETHERSCAN_PAGE_SIZE

        self._rl = SimpleRateLimiter(ETHERSCAN_REQUESTS_PER_SEC)
        self._session = requests.Session()

        self._is_contract_cache: Dict[str, bool] = {}
        self._token_meta_cache: Dict[str, TokenMeta] = {}

    # ---------- internal ----------

    def _call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        req = dict(params)
        req["apikey"] = self._api_key
        req["chainid"] = str(self._chainid)

        last_err: Optional[Exception] = None

        for attempt in range(self._max_retries):
            try:
                self._rl.wait()
                resp = self._session.get(
                    self._base_url,
                    params=req,
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                data = resp.json()

                status = str(data.get("status", "1"))
                message = str(data.get("message", "OK"))

                if status == "0" and "rate" in message.lower():
                    last_err = RateLimitError(message)
                    backoff_sleep(attempt)
                    continue

                return data

            except Exception as e:
                last_err = e
                backoff_sleep(attempt)

        raise DataSourceError(f"Etherscan failed after retries: {last_err}")

    @staticmethod
    def _list_result(data: Dict[str, Any]) -> list:
        res = data.get("result")
        return res if isinstance(res, list) else []

    # ---------- port methods ----------

    def get_block_number_by_time(self, unix_ts: int, closest: str = "before") -> int:
        data = self._call({
            "module": "block",
            "action": "getblocknobytime",
            "timestamp": str(int(unix_ts)),
            "closest": closest,
        })
        try:
            return int(data["result"])
        except Exception as e:
            raise DataSourceError(f"Invalid block result: {data}") from e

    def iter_normal_txs(
        self,
        address: str,
        start_block: int,
        end_block: int,
        sort: str = "asc",
    ) -> Iterable[RawEthTransfer]:

        page = 1
        while True:
            data = self._call({
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": start_block,
                "endblock": end_block,
                "page": page,
                "offset": self._page_size,
                "sort": sort,
            })

            rows = self._list_result(data)
            if not rows:
                break

            for r in rows:
                yield RawEthTransfer(
                    tx_hash=r.get("hash", ""),
                    block_number=int(r.get("blockNumber", 0)),
                    timestamp=int(r.get("timeStamp", 0)),
                    from_address=(r.get("from") or "").lower(),
                    to_address=(r.get("to") or "").lower(),
                    value_wei=int(r.get("value", 0)),
                )

            if len(rows) < self._page_size:
                break
            page += 1

    def iter_erc20_transfers(
        self,
        address: str,
        start_block: int,
        end_block: int,
        sort: str = "asc",
        token_address: Optional[str] = None,
    ) -> Iterable[RawErc20Transfer]:

        page = 1
        while True:
            params: Dict[str, Any] = {
                "module": "account",
                "action": "tokentx",
                "address": address,
                "startblock": start_block,
                "endblock": end_block,
                "page": page,
                "offset": self._page_size,
                "sort": sort,
            }
            if token_address:
                params["contractaddress"] = token_address

            data = self._call(params)
            rows = self._list_result(data)
            if not rows:
                break

            for r in rows:
                ta = (r.get("contractAddress") or "").lower()
                sym = r.get("tokenSymbol")
                dec = r.get("tokenDecimal")

                if ta not in self._token_meta_cache:
                    self._token_meta_cache[ta] = TokenMeta(
                        token_address=ta,
                        symbol=sym,
                        decimals=int(dec) if dec and str(dec).isdigit() else None,
                        name=None,
                    )

                yield RawErc20Transfer(
                    tx_hash=r.get("hash", ""),
                    block_number=int(r.get("blockNumber", 0)),
                    timestamp=int(r.get("timeStamp", 0)),
                    from_address=(r.get("from") or "").lower(),
                    to_address=(r.get("to") or "").lower(),
                    token_address=ta,
                    value_raw=int(r.get("value", 0)),
                    token_symbol=sym,
                    token_decimals=int(dec) if dec and str(dec).isdigit() else None,
                )

            if len(rows) < self._page_size:
                break
            page += 1

    def is_contract(self, address: str) -> bool:
        addr = address.lower()
        if addr in self._is_contract_cache:
            return self._is_contract_cache[addr]

        data = self._call({
            "module": "proxy",
            "action": "eth_getCode",
            "address": addr,
            "tag": "latest",
        })

        code = data.get("result") or "0x"
        is_c = code not in ("0x", "0x0")
        self._is_contract_cache[addr] = is_c
        return is_c

    def get_token_meta(self, token_address: str) -> TokenMeta:
        ta = token_address.lower()
        return self._token_meta_cache.get(
            ta,
            TokenMeta(token_address=ta, symbol=None, decimals=None, name=None),
        )
