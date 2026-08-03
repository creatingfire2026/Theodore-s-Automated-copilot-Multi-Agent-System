"""Entry point for the Theodore Multi-Agent System."""

import json
import logging

from multi_agent_system.core import Orchestrator
from multi_agent_system.agents import FinancialAgent, JobAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    orchestrator = Orchestrator()

    orchestrator.register(FinancialAgent())
    orchestrator.register(JobAgent())

    logger.info("Registered agents: %s", orchestrator.list_agents())

    # --- Print workflow specs for all agents ---
    workflows = orchestrator.describe_workflows()
    logger.info("Workflow specifications:\n%s", json.dumps(workflows, indent=2))

    # --- Example: financial tasks ---
    market = orchestrator.dispatch("financial_agent", {"type": "market_summary", "ticker": "AAPL"})
    logger.info("Market summary: %s", market)

    budget = orchestrator.dispatch(
        "financial_agent",
        {"type": "budget_check", "income": 5000, "expenses": 3200},
    )
    logger.info("Budget check: %s", budget)

    forecast = orchestrator.dispatch(
        "financial_agent",
        {"type": "forecast", "series": [100, 110, 120, 130], "periods": 3},
    )
    logger.info("Forecast: %s", forecast)

    # --- Example: job tasks ---
    jobs = orchestrator.dispatch(
        "job_agent",
        {"type": "search", "keywords": ["Python", "AI"], "location": "Austin, TX"},
    )
    logger.info("Job search: %s", jobs)

    orchestrator.dispatch(
        "job_agent",
        {
            "type": "track_application",
            "company": "Acme Corp",
            "role": "Senior Engineer",
            "application_status": "applied",
            "date": "2026-08-03",
        },
    )

    apps = orchestrator.dispatch("job_agent", {"type": "list_applications"})
    logger.info("Applications: %s", apps)


if __name__ == "__main__":
    main()
