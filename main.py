"""Entry point for Theodore's Automated Copilot Multi-Agent System."""

import sys

from src.orchestrator import Orchestrator
from src.shared.config import Config
from src.shared.logger import get_logger
from src.shared.renderer import render_results

logger = get_logger("main")


def main() -> int:
    config = Config()
    logger.setLevel(config.log_level)

    orch = Orchestrator(config)
    results = orch.run_all()

    render_results(results)

    failed = [name for name, r in results.items() if not r.success]
    if failed:
        logger.warning("Failed agents: %s", failed)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
