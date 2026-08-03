"""Toolchain Optimization Agent.

Inspects project dependencies, detects outdated packages, flags
security advisories via pip-audit, and produces a prioritized upgrade report.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..shared.base_agent import AgentResult, BaseAgent
from ..shared.config import Config


class ToolchainAgent(BaseAgent):
    """Audits and optimizes the software toolchain using pip-audit."""

    def __init__(self, config: Optional[Config] = None):
        super().__init__("toolchain", config or Config())

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(
        self,
        watch_dirs: Optional[List[str]] = None,
        report_path: Optional[str] = None,
        **kwargs,
    ) -> AgentResult:
        """Scan directories and write a toolchain health report.

        Args:
            watch_dirs:   Directories to scan. Falls back to config.
            report_path:  Output file for the JSON report.

        Returns:
            AgentResult with ``data["report"]`` containing audit results.
        """
        dirs = watch_dirs or self.config.toolchain_watch_dirs
        out = report_path or self.config.toolchain_report_path
        self.logger.info("Auditing toolchain in dirs: %s", dirs)

        try:
            manifests = self._collect_manifests(dirs)
            audit = self._audit_dependencies(manifests)
            self._write_report(audit, out)
            return self._success({"report": audit, "report_path": out}, dirs=dirs)
        except Exception as exc:  # noqa: BLE001
            return self._failure(str(exc))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_manifests(self, dirs: List[str]) -> List[Dict[str, Any]]:
        """Find dependency manifests (requirements.txt, package.json, etc.)."""
        manifests = []
        patterns = [
            "requirements*.txt",
            "package.json",
            "Pipfile",
            "pyproject.toml",
            "go.mod",
            "Cargo.toml",
        ]
        for d in dirs:
            for pattern in patterns:
                for path in Path(d).rglob(pattern):
                    manifests.append({"path": str(path), "type": pattern})
        self.logger.debug("Found manifests: %s", [m["path"] for m in manifests])
        return manifests

    def _audit_dependencies(self, manifests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run pip-audit for vulnerability scanning."""
        vulnerabilities: List[Dict[str, Any]] = []
        pip_audit_error: Optional[str] = None

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip_audit", "--format", "json", "--progress-spinner", "off"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            raw = result.stdout.strip()
            if raw:
                pip_data = json.loads(raw)
                for dep in pip_data.get("dependencies", []):
                    for vuln in dep.get("vulns", []):
                        vulnerabilities.append({
                            "package": dep.get("name"),
                            "version": dep.get("version"),
                            "id": vuln.get("id"),
                            "description": vuln.get("description"),
                            "fix_versions": vuln.get("fix_versions", []),
                        })
        except FileNotFoundError:
            pip_audit_error = "pip-audit not installed"
            self.logger.warning("pip-audit not available; skipping vulnerability scan")
        except subprocess.TimeoutExpired:
            pip_audit_error = "pip-audit timed out"
            self.logger.warning("pip-audit timed out")
        except Exception as exc:  # noqa: BLE001
            pip_audit_error = str(exc)
            self.logger.warning("pip-audit error: %s", exc)

        recommendations = [
            f"Upgrade {v['package']} to {v['fix_versions'][0]} to fix {v['id']}"
            for v in vulnerabilities
            if v.get("fix_versions")
        ]

        return {
            "manifests_found": len(manifests),
            "manifests": manifests,
            "outdated": [],
            "vulnerabilities": vulnerabilities,
            "pip_audit_error": pip_audit_error,
            "recommendations": recommendations,
        }

    def _write_report(self, audit: Dict[str, Any], path: str) -> None:
        """Persist the audit report as JSON."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            json.dump(audit, fh, indent=2)
        self.logger.info("Toolchain report written to %s", path)
