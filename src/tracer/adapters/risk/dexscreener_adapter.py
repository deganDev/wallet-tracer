from __future__ import annotations

import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

import requests

from tracer.adapters.chain.rate_limiter import SimpleRateLimiter, backoff_sleep
from tracer.config import settings
from tracer.core.enums import TokenRiskFlag
from tracer.core.dto import DexScreenerAnalysis, DexScreenerPair
from tracer.core.errors import DataSourceError


class DexScreenerAdapter:
    def __init__(
        self,
        base_url: str = settings.DEXSCREENER_BASE_URL,
        requests_per_sec: float = settings.DEXSCREENER_REQUESTS_PER_SEC,
        timeout_sec: int = settings.DEXSCREENER_TIMEOUT_SEC,
        max_retries: int = settings.DEXSCREENER_MAX_RETRIES,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_sec
        self._max_retries = max_retries
        self._rl = SimpleRateLimiter(requests_per_sec)
        self._session = requests.Session()

    def _call(self, path: str) -> Dict[str, Any]:
        last_err: Optional[Exception] = None
        url = f"{self._base_url}/{path.lstrip('/')}"
        for attempt in range(self._max_retries):
            try:
                self._rl.wait()
                resp = self._session.get(url, timeout=self._timeout)
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict):
                    raise DataSourceError(f"Invalid DexScreener response: {data}")
                return data
            except Exception as e:
                last_err = e
                backoff_sleep(attempt)
        raise DataSourceError(f"DexScreener failed after retries: {last_err}")

    @staticmethod
    def _dec(val: Any) -> Optional[Decimal]:
        if val is None:
            return None
        try:
            return Decimal(str(val))
        except Exception:
            return None

    def get_pairs(self, token_address: str) -> List[DexScreenerPair]:
        data = self._call(f"tokens/{token_address}")
        pairs = data.get("pairs") if isinstance(data.get("pairs"), list) else []
        out: List[DexScreenerPair] = []
        for p in pairs:
            if not isinstance(p, dict):
                continue
            chain_id = str(p.get("chainId") or "")
            if settings.DEXSCREENER_CHAIN_ID and chain_id != settings.DEXSCREENER_CHAIN_ID:
                continue
            base = p.get("baseToken") or {}
            quote = p.get("quoteToken") or {}
            out.append(
                DexScreenerPair(
                    chain_id=chain_id,
                    dex_id=str(p.get("dexId") or ""),
                    pair_address=str(p.get("pairAddress") or ""),
                    base_token=str(base.get("address") or ""),
                    quote_token=str(quote.get("address") or ""),
                    price_usd=self._dec(p.get("priceUsd")),
                    liquidity_usd=self._dec((p.get("liquidity") or {}).get("usd")),
                    volume_24h=self._dec((p.get("volume") or {}).get("h24")),
                    fdv=self._dec(p.get("fdv")),
                    market_cap=self._dec(p.get("marketCap")),
                    pair_created_at=self._pair_created_at_seconds(p.get("pairCreatedAt")),
                )
            )
        return out

    def analyze_token(
        self,
        token_address: str,
        min_liquidity_usd: Decimal = settings.DEXSCREENER_MIN_LIQUIDITY_USD,
        new_pair_hours: int = settings.DEXSCREENER_NEW_PAIR_HOURS,
    ) -> DexScreenerAnalysis:
        pairs = self.get_pairs(token_address)
        total_liquidity = Decimal("0")
        max_liquidity = Decimal("0")
        created_ts: List[int] = []
        max_volume = Decimal("0")
        for p in pairs:
            if p.liquidity_usd is not None:
                total_liquidity += p.liquidity_usd
                max_liquidity = max(max_liquidity, p.liquidity_usd)
            if p.volume_24h is not None:
                max_volume = max(max_volume, p.volume_24h)
            if p.pair_created_at:
                created_ts.append(p.pair_created_at)

        now = int(time.time())
        newest_age = self._age_hours(now, max(created_ts) if created_ts else None)
        oldest_age = self._age_hours(now, min(created_ts) if created_ts else None)

        flags: List[str] = []
        if total_liquidity > 0 and total_liquidity < min_liquidity_usd:
            flags.append(TokenRiskFlag.LIQUIDITY_THIN.value)
        if total_liquidity == 0 or not pairs:
            flags.append(TokenRiskFlag.LIQUIDITY_THIN.value)
        if len(pairs) == 1:
            flags.append(TokenRiskFlag.SINGLE_DEX_PAIR_ONLY.value)
        if newest_age is not None and newest_age <= Decimal(str(new_pair_hours)):
            flags.append(TokenRiskFlag.PAIR_CREATED_RECENTLY.value)
        if max_liquidity > 0 and max_volume > max_liquidity * Decimal("5"):
            flags.append(TokenRiskFlag.LIQUIDITY_THIN.value)

        return DexScreenerAnalysis(
            pairs=pairs,
            total_liquidity_usd=total_liquidity,
            max_liquidity_usd=max_liquidity,
            pair_count=len(pairs),
            newest_pair_age_hours=newest_age,
            oldest_pair_age_hours=oldest_age,
            flags=flags,
        )

    @staticmethod
    def _pair_created_at_seconds(raw: Any) -> Optional[int]:
        if raw is None:
            return None
        try:
            val = int(raw)
            # DexScreener uses ms; treat large values as ms.
            if val > 10_000_000_000:
                return val // 1000
            return val
        except Exception:
            return None

    @staticmethod
    def _age_hours(now_ts: int, created_ts: Optional[int]) -> Optional[Decimal]:
        if not created_ts:
            return None
        try:
            seconds = max(0, now_ts - int(created_ts))
            return Decimal(seconds) / Decimal(3600)
        except Exception:
            return None
