"""Job Agent: handles job search, resume parsing, and application tracking."""

import logging
from functools import cached_property
from typing import Any, Dict, List

from ..core.base_agent import BaseAgent
from ..core.workflow_spec import WorkflowSpec, InputField, OutputField, ErrorCase

logger = logging.getLogger(__name__)


class JobAgent(BaseAgent):
    """Agent responsible for job-seeking automation tasks.

    Supported task types (set ``task["type"]``):
        - ``"search"``            – search for jobs by keywords/location.
        - ``"parse_resume"``      – extract key sections from resume text.
        - ``"track_application"`` – log a job application to the tracker.
        - ``"list_applications"`` – return the current application list.
    """

    def __init__(self):
        super().__init__(name="job_agent")
        self._applications: List[Dict[str, Any]] = []

    @cached_property
    def workflow_spec(self) -> WorkflowSpec:
        return WorkflowSpec(
            name="Job-Seeking Automation Workflow",
            objective=(
                "Automate the end-to-end job-seeking process by enabling keyword-based "
                "job discovery, structured resume parsing, and persistent application "
                "tracking so candidates can manage their pipeline from a single interface."
            ),
            inputs=[
                InputField(
                    name="type",
                    type="str",
                    required=True,
                    description="Task type selector.",
                    example="search",
                ),
                InputField(
                    name="keywords",
                    type="List[str]",
                    required=False,
                    description="Job search keywords (used by 'search').",
                    example=["Python", "AI"],
                ),
                InputField(
                    name="location",
                    type="str",
                    required=False,
                    description="Preferred job location (used by 'search'). Defaults to 'Remote'.",
                    example="Austin, TX",
                ),
                InputField(
                    name="text",
                    type="str",
                    required=False,
                    description="Raw resume text to parse (used by 'parse_resume').",
                    example="Jane Doe\nPython Developer\n5 years experience...",
                ),
                InputField(
                    name="company",
                    type="str",
                    required=False,
                    description="Company name for the application (used by 'track_application').",
                    example="Acme Corp",
                ),
                InputField(
                    name="role",
                    type="str",
                    required=False,
                    description="Job role/title (used by 'track_application').",
                    example="Senior Engineer",
                ),
                InputField(
                    name="application_status",
                    type="str",
                    required=False,
                    description=(
                        "Current application status (used by 'track_application'). "
                        "E.g. 'applied', 'interview', 'offer', 'rejected'."
                    ),
                    example="applied",
                ),
                InputField(
                    name="date",
                    type="str",
                    required=False,
                    description="Application date in YYYY-MM-DD format (used by 'track_application').",
                    example="2026-08-03",
                ),
            ],
            outputs=[
                OutputField(
                    name="status",
                    type="str",
                    description="'ok' on success, 'error' on failure.",
                    example="ok",
                ),
                OutputField(
                    name="results",
                    type="List[str]",
                    description="List of job listing descriptions (search only).",
                    example=["Job #1 matching Python in Austin, TX"],
                ),
                OutputField(
                    name="parsed",
                    type="Dict[str, Any]",
                    description=(
                        "Extracted resume sections: name, skills, experience, education "
                        "(parse_resume only)."
                    ),
                ),
                OutputField(
                    name="tracked",
                    type="Dict[str, Any]",
                    description="The application entry that was saved (track_application only).",
                ),
                OutputField(
                    name="total",
                    type="int",
                    description="Total number of tracked applications after adding (track_application only).",
                    example=1,
                ),
                OutputField(
                    name="applications",
                    type="List[Dict[str, Any]]",
                    description="Full list of tracked applications (list_applications only).",
                ),
                OutputField(
                    name="message",
                    type="str",
                    description="Error description when status is 'error'.",
                ),
            ],
            dependencies=[
                "Python standard library only (no external runtime dependencies for base implementation)",
                "Future: 'requests' or a job-board API client for live search results",
                "Future: 'spacy' or 'transformers' for NLP-based resume parsing",
                "Future: a database adapter (SQLite/PostgreSQL) for persistent application storage",
            ],
            error_handling=[
                ErrorCase(
                    condition="Unknown task type supplied in 'type' field",
                    response="Returns {'status': 'error', 'message': '...'} listing supported types",
                    example_payload={"type": "unknown_task"},
                ),
                ErrorCase(
                    condition="'parse_resume' called with empty or missing 'text'",
                    response="Returns {'status': 'error', 'message': 'No resume text provided.'}",
                    example_payload={"type": "parse_resume", "text": ""},
                ),
                ErrorCase(
                    condition="'track_application' called without company/role fields",
                    response=(
                        "Defaults missing fields to 'Unknown'; no error is raised, "
                        "so callers should validate required fields before dispatch."
                    ),
                    example_payload={"type": "track_application"},
                ),
            ],
            use_cases=[
                "Search for Python/AI roles in a specific city and surface the top results.",
                "Parse a candidate's résumé text to extract skills and experience before matching.",
                "Log each job application as it is submitted to maintain a searchable pipeline.",
                "List all tracked applications to review status and prioritise follow-ups.",
                "Integrate with an email agent to auto-update application status based on inbox replies.",
            ],
        )

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
