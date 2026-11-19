"""Read-only verifier for authoritative GitHub Actions evidence."""
from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sentinel import ActionRequest, TestResult


Transport = Callable[[str, dict[str, str], float], dict[str, Any]]


class GitHubActionsEvidenceVerifier:
    """Verify a run against GitHub's API; never trust TestResult.conclusion.

    Configure a narrowly scoped token with Actions read access. The verifier
    checks repository, exact commit, workflow path and ID, completed success,
    a successful required job, and an executed required test step.
    """

    def __init__(
        self,
        *,
        repository: str,
        workflow_path: str,
        workflow_id: int,
        expected_commit_sha: str,
        token: str | None = None,
        required_job: str = "test",
        required_step: str = "Run regression suite",
        transport: Transport | None = None,
        timeout: float = 8.0,
    ) -> None:
        self.repository = repository
        self.workflow_path = workflow_path
        self.workflow_id = workflow_id
        self.expected_commit_sha = expected_commit_sha
        self.token = token if token is not None else os.getenv("GITHUB_TOKEN", "")
        self.required_job = required_job
        self.required_step = required_step
        self.transport = transport or self._http_get
        self.timeout = timeout

    @staticmethod
    def _http_get(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
        request = Request(url, headers=headers, method="GET")
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def __call__(self, result: TestResult, request: ActionRequest | None) -> bool:
        if (
            not self.token
            or request is None
            or not self.expected_commit_sha
            or not result.run_id
            or not result.run_id.isdecimal()
        ):
            return False

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        base = f"https://api.github.com/repos/{self.repository}/actions/runs/{result.run_id}"
        try:
            run = self.transport(base, headers, self.timeout)
            run_path = str(run.get("path", "")).split("@", 1)[0]
            if (
                run.get("repository", {}).get("full_name") != self.repository
                or run.get("head_sha") != self.expected_commit_sha
                or run_path != self.workflow_path
                or run.get("workflow_id") != self.workflow_id
                or run.get("status") != "completed"
                or run.get("conclusion") != "success"
            ):
                return False

            jobs_payload = self.transport(f"{base}/jobs", headers, self.timeout)
            jobs = jobs_payload.get("jobs")
            if not isinstance(jobs, list) or not jobs:
                return False

            matching_jobs = [job for job in jobs if job.get("name") == self.required_job]
            if not matching_jobs:
                return False
            for job in matching_jobs:
                if job.get("status") != "completed" or job.get("conclusion") != "success":
                    continue
                steps = job.get("steps")
                if not isinstance(steps, list):
                    continue
                if any(
                    step.get("name") == self.required_step
                    and step.get("status") == "completed"
                    and step.get("conclusion") == "success"
                    for step in steps
                ):
                    return True
            return False
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError, TypeError, AttributeError, OSError):
            return False
