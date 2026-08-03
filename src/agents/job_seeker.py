"""Job-Seeking Automation Agent.

Searches job boards, filters listings against Theodore's profile,
and prepares tailored application materials.
"""

from typing import Any, Dict, List, Optional

from ..shared.base_agent import AgentResult, BaseAgent
from ..shared.config import Config


class JobSeekerAgent(BaseAgent):
    """Automates job discovery and application pipeline."""

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
        """Query job boards for matching listings.

        Replace this stub with real API calls (e.g. LinkedIn, Indeed,
        Greenhouse, Lever) or scraping pipelines.
        """
        self.logger.debug("Querying job boards for %s in %s", keywords, location)
        return []

    def _rank_matches(self, listings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Score and rank listings against Theodore's profile."""
        return sorted(listings, key=lambda x: x.get("match_score", 0), reverse=True)
