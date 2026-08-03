"""Scheduler — runs all agents on a configurable cron/interval cadence.

Usage:
    python -m src.scheduler                  # use env defaults
    python -m src.scheduler --interval 30    # run every 30 minutes
    python -m src.scheduler --cron "0 9 * * *"  # run daily at 09:00
"""

import argparse
import signal
import sys
import time

try:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    _APS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _APS_AVAILABLE = False

from .orchestrator import Orchestrator
from .shared.config import Config
from .shared.logger import get_logger
from .shared.renderer import console, render_results

logger = get_logger("scheduler")


def _run_cycle() -> None:
    """One full orchestration cycle."""
    logger.info("Scheduler triggered — starting orchestration cycle")
    config = Config()
    orch = Orchestrator(config)
    results = orch.run_all()
    render_results(results)


def run_scheduler(interval_minutes: int = 60, cron_expr: str = "") -> None:
    """Start the blocking scheduler.

    Args:
        interval_minutes: Run every N minutes (used when cron_expr is empty).
        cron_expr:        A 5-field cron expression, e.g. ``"0 9 * * *"``.
    """
    if not _APS_AVAILABLE:
        logger.error("APScheduler not installed. Run: pip install apscheduler")
        sys.exit(1)

    scheduler = BlockingScheduler(timezone="UTC")

    if cron_expr:
        fields = cron_expr.split()
        if len(fields) != 5:
            logger.error("cron_expr must be 5 fields (min hour dom mon dow)")
            sys.exit(1)
        trigger = CronTrigger(
            minute=fields[0],
            hour=fields[1],
            day=fields[2],
            month=fields[3],
            day_of_week=fields[4],
        )
        schedule_desc = f"cron '{cron_expr}'"
    else:
        trigger = IntervalTrigger(minutes=interval_minutes)
        schedule_desc = f"every {interval_minutes} minute(s)"

    scheduler.add_job(_run_cycle, trigger, id="orchestration", max_instances=1)

    console.print(
        f"[bold cyan]Scheduler started[/bold cyan] — {schedule_desc}. "
        "Press Ctrl+C to stop."
    )

    # Run once immediately on start
    _run_cycle()

    def _shutdown(sig, frame):  # noqa: ANN001
        logger.info("Scheduler shutting down…")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    scheduler.start()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Theodore's Multi-Agent Scheduler"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        metavar="MINUTES",
        help="Run every N minutes (default: 60). Ignored when --cron is set.",
    )
    parser.add_argument(
        "--cron",
        type=str,
        default="",
        metavar="EXPR",
        help='5-field cron expression, e.g. "0 9 * * *" for daily at 09:00 UTC.',
    )
    args = parser.parse_args()
    run_scheduler(interval_minutes=args.interval, cron_expr=args.cron)


if __name__ == "__main__":
    main()
