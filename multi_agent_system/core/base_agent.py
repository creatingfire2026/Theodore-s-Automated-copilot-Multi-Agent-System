"""Abstract base class that all agents must implement."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from .workflow_spec import WorkflowSpec


class BaseAgent(ABC):
    """Common interface for all agents in the multi-agent system."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task and return a result dictionary.

        Args:
            task: A dictionary describing the task to perform.

        Returns:
            A dictionary containing the result and any metadata.
        """

    @property
    @abstractmethod
    def workflow_spec(self) -> WorkflowSpec:
        """Return the structured WorkflowSpec for this agent.

        Every concrete agent must declare its objective, inputs, outputs,
        dependencies, error handling, and use cases via a WorkflowSpec.
        """

    def describe(self) -> str:
        """Return a short description of the agent's capabilities."""
        return f"Agent: {self.name}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
