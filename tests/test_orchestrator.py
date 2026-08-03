"""Tests for the Orchestrator."""

import pytest

from src.orchestrator import Orchestrator
from src.shared.base_agent import AgentResult, BaseAgent
from src.shared.config import Config


class _EchoAgent(BaseAgent):
    def __init__(self, name="echo", fail=False):
        super().__init__(name, Config())
        self._fail = fail

    def run(self, **kwargs):
        if self._fail:
            return self._failure("intentional test failure")
        return self._success({"echo": "ok"})


def test_orchestrator_run_all_success():
    orch = Orchestrator(Config())
    # Replace default agents with lightweight echo agents
    orch._agents = [_EchoAgent("alpha"), _EchoAgent("beta")]
    results = orch.run_all()

    assert len(results) == 2
    assert results["alpha"].success
    assert results["beta"].success


def test_orchestrator_run_all_partial_failure():
    orch = Orchestrator(Config())
    orch._agents = [_EchoAgent("ok"), _EchoAgent("bad", fail=True)]
    results = orch.run_all()

    assert results["ok"].success
    assert not results["bad"].success
    assert "intentional" in results["bad"].error


def test_orchestrator_run_agent_by_name():
    orch = Orchestrator(Config())
    orch._agents = [_EchoAgent("target")]
    result = orch.run_agent("target")
    assert result.success


def test_orchestrator_run_unknown_agent_raises():
    orch = Orchestrator(Config())
    orch._agents = []
    with pytest.raises(ValueError, match="No agent registered"):
        orch.run_agent("ghost")


def test_register_agent():
    orch = Orchestrator(Config())
    orch._agents = []
    orch.register_agent(_EchoAgent("new"))
    assert any(a.name == "new" for a in orch._agents)
