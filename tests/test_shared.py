"""Tests for shared utilities."""

from src.shared.base_agent import AgentResult, BaseAgent
from src.shared.config import Config
from src.shared.logger import get_logger


class _ConcreteAgent(BaseAgent):
    def run(self, **kwargs):
        return self._success({"key": "value"})


def test_base_agent_success():
    agent = _ConcreteAgent("test_agent", Config())
    result = agent.run()
    assert isinstance(result, AgentResult)
    assert result.success
    assert result.data == {"key": "value"}
    assert result.error is None


def test_base_agent_failure():
    agent = _ConcreteAgent("test_agent", Config())
    result = agent._failure("something went wrong")
    assert not result.success
    assert result.error == "something went wrong"


def test_config_defaults():
    config = Config()
    assert config.max_concurrent_agents == 3
    assert config.log_level == "INFO"
    assert isinstance(config.financial_symbols, list)


def test_get_logger_returns_logger():
    import logging
    logger = get_logger("test.logger")
    assert isinstance(logger, logging.Logger)
