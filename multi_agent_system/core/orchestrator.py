"""Orchestrator: coordinates task routing between registered agents."""

import logging
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent
from .workflow_spec import WorkflowSpec
from ..utils.helpers import log_event

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates communication and task dispatch between agents."""

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent by its name.

        Args:
            agent: An instance of BaseAgent to register.
        """
        if agent.name in self._agents:
            logger.warning("Agent %r is already registered; overwriting.", agent.name)
        self._agents[agent.name] = agent
        log_event("register", {"agent": agent.name})
        logger.info("Registered agent: %s", agent.name)

    def dispatch(self, agent_name: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Route a task to the named agent and return its result.

        Args:
            agent_name: The name of the target agent.
            task: A dictionary describing the task to perform.

        Returns:
            The result dictionary from the agent.

        Raises:
            KeyError: If no agent with the given name is registered.
        """
        if agent_name not in self._agents:
            available = list(self._agents.keys())
            raise KeyError(
                f"No agent named {agent_name!r}. Available agents: {available}"
            )
        log_event("dispatch", {"agent": agent_name, "task": task})
        result = self._agents[agent_name].run(task)
        log_event("result", {"agent": agent_name, "result": result})
        return result

    def list_agents(self) -> List[str]:
        """Return the names of all registered agents."""
        return list(self._agents.keys())

    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """Return the agent instance for the given name, or None."""
        return self._agents.get(agent_name)

    def get_workflow_spec(self, agent_name: str) -> WorkflowSpec:
        """Return the WorkflowSpec for the named agent.

        Raises:
            KeyError: If no agent with the given name is registered.
        """
        if agent_name not in self._agents:
            raise KeyError(f"No agent named {agent_name!r}.")
        return self._agents[agent_name].workflow_spec

    def describe_workflows(self) -> Dict[str, Any]:
        """Return serialised WorkflowSpec dictionaries for all registered agents.

        Returns:
            A mapping of agent name → workflow spec dictionary, suitable for
            logging, display, or exporting to documentation.
        """
        return {
            name: agent.workflow_spec.to_dict()
            for name, agent in self._agents.items()
        }
