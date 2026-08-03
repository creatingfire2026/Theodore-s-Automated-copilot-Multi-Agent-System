"""Job-Seeking Automation Agent.

Searches job boards via the Remotive public API (no auth required),
filters listings against Theodore's profile, and returns ranked results.
"""

from typing import Any, Dict, List, Optional

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _REQUESTS_AVAILABLE = False

from ..shared.base_agent import AgentResult, BaseAgent
from ..shared.config import Config

_REMOTIVE_URL = "https://remotive.com/api/remote-jobs"


class JobSeekerAgent(BaseAgent):
    """Automates job discovery via Remotive and ranks results."""

    def __init__(self, config: Optional[Config] = None):
        super().__init__("job_seeker", config or Config())

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(
        self,
        keywords: Optional[List[str]] = None,
        location: Optional[str] = None,
        **kwargs,
    ) -> AgentResult:
        """Search for jobs and return ranked listings.

        Args:
            keywords: Job-search keywords. Falls back to config default.
            location: Target location or "Remote". Falls back to config.

        Returns:
            AgentResult with ``data["listings"]`` and ``data["matches"]``.
        """
        terms = keywords or self.config.job_search_keywords
        loc = location or self.config.job_search_location
        self.logger.info("Searching jobs — keywords=%s location=%s", terms, loc)

        try:
            listings = self._search_listings(terms, loc)
            matches = self._rank_matches(listings)
            return self._success(
                {"listings": listings, "matches": matches},
                keywords=terms,
                location=loc,
            )
        except Exception as exc:  # noqa: BLE001
            return self._failure(str(exc))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _search_listings(self, keywords: List[str], location: str) -> List[Dict[str, Any]]:
        """Query the Remotive public API for remote job listings."""
        if not _REQUESTS_AVAILABLE:
            self.logger.warning("requests not installed — returning empty listings")
            return []

        query = " ".join(keywords)
        self.logger.debug("Querying Remotive for '%s'", query)
        try:
            resp = _requests.get(
                _REMOTIVE_URL,
                params={"search": query, "limit": 20},
                timeout=10,
            )
            resp.raise_for_status()
            raw_jobs = resp.json().get("jobs", [])
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Remotive API call failed: %s", exc)
            return []

        return [
            {
                "id": job.get("id"),
                "title": job.get("title"),
                "company": job.get("company_name"),
                "category": job.get("category"),
                "tags": job.get("tags", []),
                "url": job.get("url"),
                "published": job.get("publication_date"),
                "salary": job.get("salary"),
                "match_score": self._score(job, keywords),
            }
            for job in raw_jobs
        ]

    def _score(self, job: Dict[str, Any], keywords: List[str]) -> int:
        """Naive keyword-match score against title + tags."""
        text = (job.get("title", "") + " " + " ".join(job.get("tags", []))).lower()
        return sum(1 for kw in keywords if kw.lower() in text)

    def _rank_matches(self, listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort listings by match score descending."""
        return sorted(listings, key=lambda x: x.get("match_score", 0), reverse=True)
