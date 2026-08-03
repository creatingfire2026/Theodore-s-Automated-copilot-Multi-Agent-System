"""Job Agent: handles job search, resume parsing, and application tracking."""

import logging
from typing import Any, Dict, List

from ..core.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class JobAgent(BaseAgent):
    """Agent responsible for job-seeking automation tasks.

    Supported task types (set ``task["type"]``):
        - ``"search"``          – search for jobs by keywords/location.
        - ``"parse_resume"``    – extract key sections from resume text.
        - ``"track_application"`` – log a job application to the tracker.
        - ``"list_applications"`` – return the current application list.
    """

    def __init__(self):
        super().__init__(name="job_agent")
        self._applications: List[Dict[str, Any]] = []

    def describe(self) -> str:
        return (
            "JobAgent: job search automation, resume parsing, "
            "and application tracking."
        )

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch the task to the appropriate job handler.

        Args:
            task: Must contain a ``"type"`` key. Additional keys depend on
                  the task type (see class docstring).

        Returns:
            A result dictionary with at least a ``"status"`` key.
        """
        task_type = task.get("type")
        logger.info("JobAgent received task: %s", task_type)

        handlers = {
            "search": self._search,
            "parse_resume": self._parse_resume,
            "track_application": self._track_application,
            "list_applications": self._list_applications,
        }

        handler = handlers.get(task_type)
        if handler is None:
            return {
                "status": "error",
                "message": (
                    f"Unknown task type {task_type!r}. "
                    f"Supported: {list(handlers.keys())}"
                ),
            }
        return handler(task)

    # ------------------------------------------------------------------
    # Private handlers
    # ------------------------------------------------------------------

    def _search(self, task: Dict[str, Any]) -> Dict[str, Any]:
        keywords = task.get("keywords", [])
        location = task.get("location", "Remote")
        return {
            "status": "ok",
            "query": {"keywords": keywords, "location": location},
            "results": [
                f"Placeholder job #{i + 1} matching {keywords} in {location}"
                for i in range(3)
            ],
        }

    def _parse_resume(self, task: Dict[str, Any]) -> Dict[str, Any]:
        text = task.get("text", "")
        if not text:
            return {"status": "error", "message": "No resume text provided."}
        sections = {
            "name": "Extracted Name (placeholder)",
            "skills": ["Skill A", "Skill B"],
            "experience": ["Role 1 at Company X"],
            "education": ["Degree in Field at University Y"],
        }
        return {"status": "ok", "parsed": sections}

    def _track_application(self, task: Dict[str, Any]) -> Dict[str, Any]:
        entry = {
            "company": task.get("company", "Unknown"),
            "role": task.get("role", "Unknown"),
            "status": task.get("application_status", "applied"),
            "date": task.get("date", ""),
        }
        self._applications.append(entry)
        return {"status": "ok", "tracked": entry, "total": len(self._applications)}

    def _list_applications(self, _task: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "ok", "applications": list(self._applications)}
