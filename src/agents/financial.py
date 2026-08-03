"""Financial Intelligence Agent.

Monitors market symbols, tracks portfolio metrics, and surfaces
actionable insights for Theodore's financial decision-making.
Uses yfinance for real-time market data.
"""

from typing import Any, Dict, List, Optional

try:
    import yfinance as yf
    _YFINANCE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _YFINANCE_AVAILABLE = False

from ..shared.base_agent import AgentResult, BaseAgent
from ..shared.config import Config


class FinancialAgent(BaseAgent):
    """Fetches market data via yfinance and generates financial intelligence reports."""

    def __init__(self, config: Optional[Config] = None):
        super().__init__("financial", config or Config())

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, symbols: Optional[List[str]] = None, **kwargs) -> AgentResult:
        """Fetch quotes for the given symbols and return a summary report.

        Args:
            symbols: Ticker symbols to query. Falls back to config default.

        Returns:
            AgentResult with ``data["quotes"]`` and ``data["summary"]``.
        """
        watch = symbols or self.config.financial_symbols
        self.logger.info("Running financial intelligence for symbols: %s", watch)

        try:
            quotes = self._fetch_quotes(watch)
            summary = self._build_summary(quotes)
            return self._success({"quotes": quotes, "summary": summary}, symbols=watch)
        except Exception as exc:  # noqa: BLE001
            return self._failure(str(exc))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_quotes(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Retrieve current market data via yfinance."""
        if not _YFINANCE_AVAILABLE:
            self.logger.warning("yfinance not installed — returning stub data")
            return [{"symbol": s, "price": None, "change_pct": None, "currency": None} for s in symbols]

        self.logger.debug("Fetching quotes via yfinance for: %s", symbols)
        quotes: List[Dict[str, Any]] = []
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.fast_info
                price = getattr(info, "last_price", None)
                prev_close = getattr(info, "previous_close", None)
                currency = getattr(info, "currency", "USD")
                change_pct: Optional[float] = None
                if price is not None and prev_close and prev_close != 0:
                    change_pct = round((price - prev_close) / prev_close * 100, 2)
                quotes.append({
                    "symbol": symbol,
                    "price": round(float(price), 2) if price is not None else None,
                    "prev_close": round(float(prev_close), 2) if prev_close is not None else None,
                    "change_pct": change_pct,
                    "currency": currency,
                })
            except Exception as exc:  # noqa: BLE001
                self.logger.warning("Failed to fetch %s: %s", symbol, exc)
                quotes.append({"symbol": symbol, "price": None, "change_pct": None, "currency": None})
        return quotes

    def _build_summary(self, quotes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate raw quotes into a human-readable summary."""
        gainers = [q["symbol"] for q in quotes if (q.get("change_pct") or 0) > 0]
        losers = [q["symbol"] for q in quotes if (q.get("change_pct") or 0) < 0]
        unchanged = [q["symbol"] for q in quotes if q.get("change_pct") is None or q.get("change_pct") == 0]
        return {
            "total_symbols": len(quotes),
            "gainers": gainers,
            "losers": losers,
            "unchanged": unchanged,
        }
