"""Abstract base class for all agents in the system."""

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .logger import get_logger


@dataclass
class AgentResult:
    """Standardized result returned by every agent run."""

    agent_name: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(abc.ABC):
    """All agents inherit from this class and implement `run`."""

    def __init__(self, name: str, config=None):
        self.name = name
        self.config = config
        self.logger = get_logger(f"agent.{name}")

    @abc.abstractmethod
    def run(self, **kwargs) -> AgentResult:
        """Execute the agent's primary task and return an AgentResult."""

    def _success(self, data: Dict[str, Any], **metadata) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            success=True,
            data=data,
            metadata=metadata,
        )

    def _failure(self, error: str, **metadata) -> AgentResult:
        self.logger.error("Agent '%s' failed: %s", self.name, error)
        return AgentResult(
            agent_name=self.name,
            success=False,
            error=error,
            metadata=metadata,
        )
