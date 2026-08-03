"""Entry point for Theodore's Automated Copilot Multi-Agent System."""

import json
import sys

from src.orchestrator import Orchestrator
from src.shared.config import Config
from src.shared.logger import get_logger

logger = get_logger("main")


def main() -> int:
    config = Config()
    logger.setLevel(config.log_level)
    logger.info("Theodore's Copilot Multi-Agent System starting…")

    orch = Orchestrator(config)
    results = orch.run_all()

    report = {
        name: {
            "success": r.success,
            "data": r.data,
            "error": r.error,
        }
        for name, r in results.items()
    }

    print(json.dumps(report, indent=2, default=str))

    failed = [name for name, r in results.items() if not r.success]
    if failed:
        logger.warning("Failed agents: %s", failed)
        return 1

    logger.info("All agents completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
