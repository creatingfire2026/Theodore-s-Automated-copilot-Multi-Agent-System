"""Tests for the Rich renderer (smoke tests — just ensure no exceptions)."""

from io import StringIO

from rich.console import Console

from src.shared.base_agent import AgentResult
from src.shared.renderer import render_results


def _make_console() -> Console:
    return Console(file=StringIO(), width=120)


def _patch_console(monkeypatch):
    buf = StringIO()
    fake = Console(file=buf, width=120)
    monkeypatch.setattr("src.shared.renderer.console", fake)
    return buf


def test_render_all_success(monkeypatch):
    buf = _patch_console(monkeypatch)
    results = {
        "financial": AgentResult(
            agent_name="financial",
            success=True,
            data={
                "quotes": [
                    {"symbol": "AAPL", "price": 180.0, "change_pct": 1.2, "currency": "USD"}
                ],
                "summary": {"total_symbols": 1, "gainers": ["AAPL"], "losers": [], "unchanged": []},
            },
        ),
        "job_seeker": AgentResult(
            agent_name="job_seeker",
            success=True,
            data={"listings": [], "matches": []},
        ),
        "toolchain": AgentResult(
            agent_name="toolchain",
            success=True,
            data={"report": {"manifests_found": 2, "vulnerabilities": [], "recommendations": []}},
        ),
    }
    render_results(results)
    output = buf.getvalue()
    assert "Financial" in output
    assert "Job Seeker" in output
    assert "Toolchain" in output


def test_render_with_failure(monkeypatch):
    buf = _patch_console(monkeypatch)
    results = {
        "financial": AgentResult(
            agent_name="financial",
            success=False,
            error="API key missing",
        ),
    }
    render_results(results)
    assert "API key missing" in buf.getvalue()


def test_render_summary_line(monkeypatch):
    buf = _patch_console(monkeypatch)
    results = {
        "a": AgentResult(agent_name="a", success=True, data={}),
        "b": AgentResult(agent_name="b", success=True, data={}),
    }
    render_results(results)
    assert "2/2" in buf.getvalue()
