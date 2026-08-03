"""Financial Agent: handles market data retrieval, budgeting, and forecasting."""

import logging
from typing import Any, Dict

from ..core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class FinancialAgent(BaseAgent):
    """Agent responsible for financial intelligence tasks.

    Supported task types (set ``task["type"]``):
        - ``"market_summary"``  – return a placeholder market summary.
        - ``"budget_check"``    – evaluate income vs. expenses.
        - ``"forecast"``        – simple linear forecast of a value series.
    """

    def __init__(self):
        super().__init__(name="financial_agent")

    def describe(self) -> str:
        return (
            "FinancialAgent: market data retrieval, budgeting analysis, "
            "and financial forecasting."
        )

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch the task to the appropriate financial handler.

        Args:
            task: Must contain a ``"type"`` key. Additional keys depend on
                  the task type (see class docstring).

        Returns:
            A result dictionary with at least a ``"status"`` key.
        """
        task_type = task.get("type")
        logger.info("FinancialAgent received task: %s", task_type)

        handlers = {
            "market_summary": self._market_summary,
            "budget_check": self._budget_check,
            "forecast": self._forecast,
        }

        handler = handlers.get(task_type)
        if handler is None:
            return {
                "status": "error",
                "message": (
                    f"Unknown task type {task_type!r}. "
                    f"Supported: {list(handlers.keys())}"
                ),
            }
        return handler(task)

    # ------------------------------------------------------------------
    # Private handlers
    # ------------------------------------------------------------------

    def _market_summary(self, task: Dict[str, Any]) -> Dict[str, Any]:
        ticker = task.get("ticker", "N/A")
        return {
            "status": "ok",
            "ticker": ticker,
            "summary": f"Placeholder market summary for {ticker}.",
        }

    def _budget_check(self, task: Dict[str, Any]) -> Dict[str, Any]:
        income = float(task.get("income", 0))
        expenses = float(task.get("expenses", 0))
        balance = income - expenses
        return {
            "status": "ok",
            "income": income,
            "expenses": expenses,
            "balance": balance,
            "assessment": "surplus" if balance >= 0 else "deficit",
        }

    def _forecast(self, task: Dict[str, Any]) -> Dict[str, Any]:
        series = task.get("series", [])
        periods = int(task.get("periods", 1))
        if len(series) < 2:
            return {"status": "error", "message": "Need at least 2 data points to forecast."}
        delta = (series[-1] - series[0]) / (len(series) - 1)
        projected = [series[-1] + delta * (i + 1) for i in range(periods)]
        return {"status": "ok", "projected": projected, "trend_per_period": delta}
