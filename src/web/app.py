"""FastAPI web dashboard for Theodore's Multi-Agent System.

Run with:
    uvicorn src.web.app:app --reload
or via the convenience script:
    python serve.py
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from ..orchestrator import Orchestrator
from ..shared.base_agent import AgentResult
from ..shared.config import Config
from ..shared.logger import get_logger

logger = get_logger("web")

app = FastAPI(
    title="Theodore's Copilot Multi-Agent System",
    description="Real-time dashboard for financial, job-seeking, and toolchain agents.",
    version="1.0.0",
)

# In-memory cache of the last run results
_cache: Dict[str, Any] = {
    "results": {},
    "last_run": None,
    "running": False,
}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse, summary="Dashboard UI")
async def dashboard() -> HTMLResponse:
    """Serve a minimal HTML dashboard."""
    last_run = _cache["last_run"] or "Never"
    running = _cache["running"]
    results = _cache["results"]

    rows = ""
    for name, r in results.items():
        status = "✅" if r.get("success") else "❌"
        error = r.get("error") or ""
        data_preview = str(r.get("data", {}))[:200]
        rows += f"""
        <tr>
          <td><b>{name.replace('_', ' ').title()}</b></td>
          <td>{status}</td>
          <td style="color:red">{error}</td>
          <td><code>{data_preview}</code></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Theodore's Copilot MAS</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 2rem; }}
    h1 {{ color: #58a6ff; }}
    p.meta {{ color: #8b949e; font-size: .9rem; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
    th {{ background: #161b22; color: #58a6ff; padding: .6rem 1rem; text-align: left; }}
    td {{ padding: .6rem 1rem; border-bottom: 1px solid #21262d; vertical-align: top; }}
    tr:hover td {{ background: #161b22; }}
    code {{ font-size: .8rem; color: #79c0ff; word-break: break-all; }}
    a.btn {{
      display: inline-block; margin-top: 1rem; padding: .5rem 1.2rem;
      background: #238636; color: #fff; border-radius: 6px; text-decoration: none;
      font-weight: bold;
    }}
    a.btn:hover {{ background: #2ea043; }}
    .badge-running {{ color: #f0883e; }}
  </style>
</head>
<body>
  <h1>🤖 Theodore's Copilot Multi-Agent System</h1>
  <p class="meta">Last run: <b>{last_run}</b>
  {'<span class="badge-running"> · Running…</span>' if running else ''}
  </p>
  <a class="btn" href="/run">▶ Run All Agents Now</a>
  &nbsp;
  <a class="btn" href="/results" style="background:#1f6feb">📄 JSON Results</a>
  <table>
    <thead><tr><th>Agent</th><th>Status</th><th>Error</th><th>Data Preview</th></tr></thead>
    <tbody>{rows if rows else '<tr><td colspan="4" style="color:#8b949e">No results yet — click Run.</td></tr>'}</tbody>
  </table>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/results", summary="Latest agent results as JSON")
async def get_results() -> Dict[str, Any]:
    """Return the cached results from the last orchestration run."""
    return {
        "last_run": _cache["last_run"],
        "running": _cache["running"],
        "results": _cache["results"],
    }


@app.get("/results/{agent_name}", summary="Results for a single agent")
async def get_agent_result(agent_name: str) -> Dict[str, Any]:
    """Return the result for a specific agent."""
    r = _cache["results"].get(agent_name)
    if r is None:
        raise HTTPException(status_code=404, detail=f"No result for agent '{agent_name}'")
    return r


@app.post("/run", summary="Trigger a full orchestration run")
async def trigger_run() -> Dict[str, str]:
    """Kick off all agents in the background and return immediately."""
    if _cache["running"]:
        return {"status": "already_running"}
    asyncio.create_task(_background_run())
    return {"status": "started"}


@app.get("/run", summary="Trigger run (GET convenience)")
async def trigger_run_get() -> HTMLResponse:
    """Convenience GET endpoint that triggers a run then redirects home."""
    from fastapi.responses import RedirectResponse
    if not _cache["running"]:
        asyncio.create_task(_background_run())
    return RedirectResponse(url="/")


@app.get("/health", summary="Health check")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------


async def _background_run() -> None:
    _cache["running"] = True
    _cache["last_run"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        config = Config()
        orch = Orchestrator(config)
        loop = asyncio.get_event_loop()
        raw: Dict[str, AgentResult] = await loop.run_in_executor(None, orch.run_all)
        _cache["results"] = {
            name: {"success": r.success, "data": r.data, "error": r.error}
            for name, r in raw.items()
        }
        logger.info("Web-triggered run complete")
    except Exception as exc:  # noqa: BLE001
        logger.error("Background run failed: %s", exc)
    finally:
        _cache["running"] = False
