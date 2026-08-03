"""Shared utility functions used across all agents."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)


def format_response(status: str, data: Any = None, message: str = "") -> Dict[str, Any]:
    """Build a standardised response envelope.

    Args:
        status:  ``"ok"`` or ``"error"``.
        data:    The payload to return (optional).
        message: A human-readable description (optional).

    Returns:
        A dictionary with ``status``, ``data``, ``message``, and ``timestamp`` keys.
    """
    return {
        "status": status,
        "data": data,
        "message": message,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


def log_event(event_type: str, payload: Dict[str, Any]) -> None:
    """Log a structured event for auditing and debugging.

    Args:
        event_type: A short label for the event (e.g. ``"dispatch"``).
        payload:    Arbitrary key-value pairs associated with the event.
    """
    logger.debug("EVENT [%s]: %s", event_type, payload)
