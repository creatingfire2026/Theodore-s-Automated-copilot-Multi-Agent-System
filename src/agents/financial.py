"""Financial Intelligence Agent.

Monitors market symbols, tracks portfolio metrics, and surfaces
actionable insights for Theodore's financial decision-making.
"""

from typing import Any, Dict, List, Optional

from ..shared.base_agent import AgentResult, BaseAgent
from ..shared.config import Config


class FinancialAgent(BaseAgent):
    """Fetches market data and generates financial intelligence reports."""

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
        """Retrieve current market data for each symbol.

        Replace this stub with a real market-data API call
        (e.g. yfinance, Alpha Vantage, Polygon.io).
        """
        self.logger.debug("Fetching quotes for: %s", symbols)
        return [{"symbol": s, "price": None, "change_pct": None} for s in symbols]

    def _build_summary(self, quotes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate raw quotes into a human-readable summary."""
        return {
            "total_symbols": len(quotes),
            "gainers": [],
            "losers": [],
            "unchanged": [q["symbol"] for q in quotes],
        }
