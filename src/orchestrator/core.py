"""Orchestrator — coordinates all agents in the system."""

import concurrent.futures
from typing import Any, Dict, List, Optional

from ..agents import FinancialAgent, JobSeekerAgent, ToolchainAgent
from ..shared.base_agent import AgentResult, BaseAgent
from ..shared.config import Config
from ..shared.logger import get_logger


class Orchestrator:
    """Runs agents concurrently and collects their results.

    Usage::

        from src.orchestrator import Orchestrator
        from src.shared.config import Config

        config = Config()
        orch = Orchestrator(config)
        report = orch.run_all()
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = get_logger("orchestrator")

        self._agents: List[BaseAgent] = [
            FinancialAgent(self.config),
            JobSeekerAgent(self.config),
            ToolchainAgent(self.config),
        ]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run_all(self, **kwargs) -> Dict[str, AgentResult]:
        """Run all registered agents concurrently.

        Returns:
            A mapping of agent name → AgentResult.
        """
        self.logger.info(
            "Starting orchestration run with %d agents (max_workers=%d)",
            len(self._agents),
            self.config.max_concurrent_agents,
        )

        results: Dict[str, AgentResult] = {}

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.max_concurrent_agents
        ) as executor:
            future_to_agent = {
                executor.submit(self._run_agent, agent, kwargs): agent
                for agent in self._agents
            }
            for future in concurrent.futures.as_completed(
                future_to_agent,
                timeout=self.config.agent_timeout_seconds,
            ):
                agent = future_to_agent[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    result = AgentResult(
                        agent_name=agent.name,
                        success=False,
                        error=f"Unhandled exception: {exc}",
                    )
                results[agent.name] = result
                status = "✓" if result.success else "✗"
                self.logger.info("[%s] %s", status, agent.name)

        self._log_summary(results)
        return results

    def run_agent(self, name: str, **kwargs) -> AgentResult:
        """Run a single registered agent by name."""
        for agent in self._agents:
            if agent.name == name:
                return self._run_agent(agent, kwargs)
        raise ValueError(f"No agent registered with name '{name}'")

    def register_agent(self, agent: BaseAgent) -> None:
        """Dynamically add a new agent to the orchestration pool."""
        self.logger.info("Registering agent: %s", agent.name)
        self._agents.append(agent)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_agent(self, agent: BaseAgent, kwargs: Dict[str, Any]) -> AgentResult:
        self.logger.debug("Dispatching agent: %s", agent.name)
        return agent.run(**kwargs)

    def _log_summary(self, results: Dict[str, AgentResult]) -> None:
        successes = sum(1 for r in results.values() if r.success)
        failures = len(results) - successes
        self.logger.info(
            "Orchestration complete — %d succeeded, %d failed", successes, failures
        )
