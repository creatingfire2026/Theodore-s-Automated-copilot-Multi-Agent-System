# Theodore's Automated Copilot Multi-Agent System

A commanding Copilot‑driven multi‑agent system forged for stability, opportunity, and precision. Financial intelligence, job‑seeking automation, and toolchain optimization unite under a disciplined orchestration core, empowering Theodore's digital ecosystem to rise, adapt, and endure — and scale with new and existing pioneers in the technology sector.

## Architecture

```
main.py                        ← Entry point
src/
├── orchestrator/
│   └── core.py                ← Concurrent agent dispatcher
├── agents/
│   ├── financial.py           ← Market data & portfolio intelligence
│   ├── job_seeker.py          ← Job discovery & application pipeline
│   └── toolchain.py           ← Dependency audit & upgrade recommendations
└── shared/
    ├── base_agent.py          ← Abstract agent contract (AgentResult)
    ├── config.py              ← Environment-driven configuration
    └── logger.py              ← Centralized logging factory
tests/
├── test_agents.py
├── test_orchestrator.py
└── test_shared.py
```

## Quick Start

```bash
# 1. Copy and fill in your environment variables
cp .env.example .env

# 2. Install dev dependencies
pip install -r requirements-dev.txt

# 3. Run all agents
python main.py

# 4. Run tests
pytest
```

## Agents

| Agent | Responsibility | Key Config Variables |
|-------|---------------|----------------------|
| **FinancialAgent** | Fetches market quotes, surfaces gainers/losers | `FINANCIAL_API_KEY`, `FINANCIAL_SYMBOLS` |
| **JobSeekerAgent** | Searches job boards, ranks matches | `JOB_SEARCH_KEYWORDS`, `JOB_SEARCH_LOCATION`, `RESUME_PATH` |
| **ToolchainAgent** | Audits dependencies, detects vulnerabilities | `TOOLCHAIN_WATCH_DIRS`, `TOOLCHAIN_REPORT_PATH` |

## Extending

Register a custom agent at runtime:

```python
from src.orchestrator import Orchestrator
from src.shared.base_agent import BaseAgent, AgentResult

class MyAgent(BaseAgent):
    def run(self, **kwargs) -> AgentResult:
        return self._success({"result": "done"})

orch = Orchestrator()
orch.register_agent(MyAgent("my_agent"))
orch.run_all()
```

## Configuration

All settings are read from environment variables. Copy `.env.example` to `.env` and fill in your values. See `src/shared/config.py` for the full list.
