"""
OpenQuant-FNO: OpenBB Platform SDK & Market Data Bridge
======================================================
Retrieves real-time index snapshots, underlying spot prices, and volatility proxies.
Employs an institutional multi-tiered fallback architecture:
1. OpenBB Platform SDK (`openbb.obb`)
2. yfinance NSE Index Bridge (`^NSEI`, `^NSEBANK`, `NIFTY_FIN_SERVICE.NS`)
3. Synthetic deterministic baseline (ensuring zero crash risk during network outages)
"""

import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("openquant.openbb")

# Benchmark Index Symbol Mappings
INDEX_TICKERS = {
    "NIFTY": {"openbb": "^NSEI", "yfinance": "^NSEI", "default_spot": 24250.0},
    "BANKNIFTY": {"openbb": "^NSEBANK", "yfinance": "^NSEBANK", "default_spot": 51200.0},
    "FINNIFTY": {"openbb": "NIFTY_FIN_SERVICE.NS", "yfinance": "NIFTY_FIN_SERVICE.NS", "default_spot": 23400.0},
    "MIDCPNIFTY": {"openbb": "^NSEMDCP50", "yfinance": "^NSEMDCP50", "default_spot": 12800.0},
    "SENSEX": {"openbb": "^BSESN", "yfinance": "^BSESN", "default_spot": 79500.0}
}


class OpenBBMarketService:
    """
    Resilient market data provider with in-memory caching and graceful tier degradation.
    """

    def __init__(self, cache_ttl_seconds: float = 30.0):
        self.cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._has_openbb = False

        # Attempt to dynamically import OpenBB SDK
        try:
            from openbb import obb  # noqa: F401
            self._has_openbb = True
            logger.info("[MARKET DATA] OpenBB Platform SDK detected and initialized.")
        except ImportError:
            logger.info("[MARKET DATA] OpenBB SDK not present in environment. Falling back to yfinance bridge.")

    def get_index_spot(self, underlying: str) -> Dict[str, Any]:
        """
        Retrieves current spot price and daily performance metrics for a given index.
        """
        clean_symbol = underlying.upper().replace(" ", "")
        meta = INDEX_TICKERS.get(clean_symbol, {
            "openbb": f"^{clean_symbol}",
            "yfinance": f"^{clean_symbol}",
            "default_spot": 24000.0
        })

        # Check Cache
        cached = self._cache.get(clean_symbol)
        if cached and (time.time() - cached["cached_at"] < self.cache_ttl):
            return cached["data"]

        # Tier 1: Try OpenBB Platform SDK
        if self._has_openbb:
            try:
                from openbb import obb
                ticker = meta["openbb"]
                quote = obb.equity.price.quote(symbol=ticker, provider="yfinance")
                if quote and hasattr(quote, "results") and quote.results:
                    res = quote.results[0]
                    spot = float(res.last_price if hasattr(res, "last_price") else res.close)
                    change = float(getattr(res, "change", 0.0) or 0.0)
                    pct_change = float(getattr(res, "percent_change", 0.0) or 0.0)
                    data = {
                        "symbol": clean_symbol,
                        "spot_price": spot,
                        "change_pts": change,
                        "change_pct": pct_change,
                        "source": "OpenBB Platform SDK",
                        "status": "LIVE"
                    }
                    self._cache[clean_symbol] = {"data": data, "cached_at": time.time()}
                    return data
            except Exception as exc:
                logger.debug(f"[MARKET DATA] OpenBB fetch error for {clean_symbol}: {exc}. Trying yfinance.")

        # Tier 2: Try Direct yfinance
        try:
            import yfinance as yf
            ticker_str = meta["yfinance"]
            ticker = yf.Ticker(ticker_str)
            fast_info = getattr(ticker, "fast_info", None)
            if fast_info and hasattr(fast_info, "last_price") and fast_info.last_price:
                spot = float(fast_info.last_price)
                prev_close = float(getattr(fast_info, "previous_close", spot))
                change = spot - prev_close
                pct_change = (change / prev_close * 100.0) if prev_close > 0 else 0.0

                data = {
                    "symbol": clean_symbol,
                    "spot_price": spot,
                    "change_pts": round(change, 2),
                    "change_pct": round(pct_change, 2),
                    "source": "yfinance Engine",
                    "status": "LIVE"
                }
                self._cache[clean_symbol] = {"data": data, "cached_at": time.time()}
                return data
        except Exception as exc:
            logger.debug(f"[MARKET DATA] yfinance fetch error for {clean_symbol}: {exc}")

        # Tier 3: Synthetic Deterministic Baseline (Guarantees system continuity)
        default_spot = meta["default_spot"]
        data = {
            "symbol": clean_symbol,
            "spot_price": default_spot,
            "change_pts": 0.0,
            "change_pct": 0.0,
            "source": "Deterministic Synthetic Model",
            "status": "FALLBACK"
        }
        self._cache[clean_symbol] = {"data": data, "cached_at": time.time()}
        return data

    def validate_strike_proximity(
        self,
        underlying: str,
        strike: float,
        option_type: str,
        max_deviation_pct: float = 8.0
    ) -> bool:
        """
        Confirms the option strike is within a reasonable percentage of the underlying spot.
        """
        spot_info = self.get_index_spot(underlying)
        spot = spot_info.get("spot_price", 0.0)
        if spot <= 0:
            return True

        deviation = abs(strike - spot) / spot * 100.0
        return deviation <= max_deviation_pct
