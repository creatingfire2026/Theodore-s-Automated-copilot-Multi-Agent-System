"""Financial Agent: handles market data retrieval, budgeting, and forecasting."""

import logging
from functools import cached_property
from typing import Any, Dict

from ..core.base_agent import BaseAgent
from ..core.workflow_spec import WorkflowSpec, InputField, OutputField, ErrorCase

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

    @cached_property
    def workflow_spec(self) -> WorkflowSpec:
        return WorkflowSpec(
            name="Financial Intelligence Workflow",
            objective=(
                "Provide financial analysis capabilities including real-time market "
                "summaries, income/expense budget evaluation, and linear trend "
                "forecasting to support data-driven financial decisions."
            ),
            inputs=[
                InputField(
                    name="type",
                    type="str",
                    required=True,
                    description="Task type selector.",
                    example="market_summary",
                ),
                InputField(
                    name="ticker",
                    type="str",
                    required=False,
                    description="Stock ticker symbol (used by 'market_summary').",
                    example="AAPL",
                ),
                InputField(
                    name="income",
                    type="float",
                    required=False,
                    description="Total income amount (used by 'budget_check').",
                    example=5000.0,
                ),
                InputField(
                    name="expenses",
                    type="float",
                    required=False,
                    description="Total expenses amount (used by 'budget_check').",
                    example=3200.0,
                ),
                InputField(
                    name="series",
                    type="List[float]",
                    required=False,
                    description="Historical numeric series (used by 'forecast'). Min 2 values.",
                    example=[100, 110, 120, 130],
                ),
                InputField(
                    name="periods",
                    type="int",
                    required=False,
                    description="Number of future periods to project (used by 'forecast').",
                    example=3,
                ),
            ],
            outputs=[
                OutputField(
                    name="status",
                    type="str",
                    description="'ok' on success, 'error' on failure.",
                    example="ok",
                ),
                OutputField(
                    name="ticker",
                    type="str",
                    description="Echo of the requested ticker (market_summary only).",
                    example="AAPL",
                ),
                OutputField(
                    name="summary",
                    type="str",
                    description="Human-readable market summary text (market_summary only).",
                ),
                OutputField(
                    name="balance",
                    type="float",
                    description="income − expenses (budget_check only).",
                    example=1800.0,
                ),
                OutputField(
                    name="assessment",
                    type="str",
                    description="'surplus' or 'deficit' (budget_check only).",
                    example="surplus",
                ),
                OutputField(
                    name="projected",
                    type="List[float]",
                    description="Projected values for requested periods (forecast only).",
                    example=[140.0, 150.0, 160.0],
                ),
                OutputField(
                    name="trend_per_period",
                    type="float",
                    description="Average change per period (forecast only).",
                    example=10.0,
                ),
                OutputField(
                    name="message",
                    type="str",
                    description="Error description when status is 'error'.",
                ),
            ],
            dependencies=[
                "Python standard library only (no external runtime dependencies for base implementation)",
                "Future: 'requests' or 'yfinance' for live market data",
                "Future: 'pandas' for advanced time-series analysis",
            ],
            error_handling=[
                ErrorCase(
                    condition="Unknown task type supplied in 'type' field",
                    response="Returns {'status': 'error', 'message': '...'} listing supported types",
                    example_payload={"type": "unknown_task"},
                ),
                ErrorCase(
                    condition="'forecast' called with fewer than 2 data points",
                    response="Returns {'status': 'error', 'message': 'Need at least 2 data points to forecast.'}",
                    example_payload={"type": "forecast", "series": [100]},
                ),
                ErrorCase(
                    condition="Non-numeric values passed to 'income' or 'expenses'",
                    response="Python raises ValueError at float() conversion; caller must validate inputs",
                    example_payload={"type": "budget_check", "income": "abc"},
                ),
            ],
            use_cases=[
                "Retrieve a market summary for a given stock ticker before a trading decision.",
                "Check whether monthly household income covers planned expenses.",
                "Project revenue for the next quarter based on the last 12 months of actuals.",
                "Integrate with a dashboard agent to display live financial KPIs.",
            ],
        )

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
