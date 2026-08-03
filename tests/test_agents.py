"""Tests for individual agents."""

from src.agents import FinancialAgent, JobSeekerAgent, ToolchainAgent
from src.shared.config import Config


def _config():
    return Config()


def test_financial_agent_run_returns_result():
    agent = FinancialAgent(_config())
    result = agent.run(symbols=["AAPL", "MSFT"])
    assert result.success
    assert "quotes" in result.data
    assert "summary" in result.data
    assert len(result.data["quotes"]) == 2


def test_job_seeker_agent_run_returns_result():
    agent = JobSeekerAgent(_config())
    result = agent.run(keywords=["python"], location="Remote")
    assert result.success
    assert "listings" in result.data
    assert "matches" in result.data


def test_toolchain_agent_run_returns_result(tmp_path):
    config = _config()
    config.toolchain_report_path = str(tmp_path / "report.json")
    agent = ToolchainAgent(config)
    result = agent.run(watch_dirs=[str(tmp_path)])
    assert result.success
    assert "report" in result.data
    assert (tmp_path / "report.json").exists()
