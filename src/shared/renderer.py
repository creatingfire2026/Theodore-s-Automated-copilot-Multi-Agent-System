"""Rich terminal renderer for agent results."""

from typing import Dict

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .base_agent import AgentResult

console = Console()


def render_results(results: Dict[str, AgentResult]) -> None:
    """Print a styled dashboard of all agent results to the terminal."""
    console.rule("[bold cyan]Theodore's Copilot Multi-Agent System[/bold cyan]")

    for name, result in results.items():
        _render_agent(name, result)

    _render_summary(results)


def _render_agent(name: str, result: AgentResult) -> None:
    status_icon = "[green]✓[/green]" if result.success else "[red]✗[/red]"
    title = f"{status_icon}  [bold]{name.replace('_', ' ').title()}[/bold]"

    if not result.success:
        panel = Panel(
            f"[red]{result.error}[/red]",
            title=title,
            border_style="red",
        )
        console.print(panel)
        return

    content = _format_agent_data(name, result)
    panel = Panel(content, title=title, border_style="cyan", padding=(0, 1))
    console.print(panel)


def _format_agent_data(name: str, result: AgentResult) -> Table:
    """Dispatch to the appropriate formatter based on agent name."""
    if name == "financial":
        return _financial_table(result.data)
    if name == "job_seeker":
        return _job_seeker_table(result.data)
    if name == "toolchain":
        return _toolchain_table(result.data)
    return _generic_table(result.data)


def _financial_table(data: dict) -> Table:
    quotes = data.get("quotes", [])
    summary = data.get("summary", {})

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold magenta")
    table.add_column("Symbol", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("Change %", justify="right")
    table.add_column("Currency")

    for q in quotes:
        chg = q.get("change_pct")
        if chg is None:
            chg_str = Text("N/A", style="dim")
        elif chg > 0:
            chg_str = Text(f"+{chg:.2f}%", style="green")
        elif chg < 0:
            chg_str = Text(f"{chg:.2f}%", style="red")
        else:
            chg_str = Text("0.00%", style="dim")

        price = q.get("price")
        table.add_row(
            q.get("symbol", ""),
            f"{price:.2f}" if price is not None else "N/A",
            chg_str,
            q.get("currency") or "—",
        )

    console.print(
        f"  Gainers: [green]{len(summary.get('gainers', []))}[/green]  "
        f"Losers: [red]{len(summary.get('losers', []))}[/red]  "
        f"Flat: [dim]{len(summary.get('unchanged', []))}[/dim]",
        end="\n",
    )
    return table


def _job_seeker_table(data: dict) -> Table:
    matches = data.get("matches", [])[:10]

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold magenta")
    table.add_column("Title", max_width=40)
    table.add_column("Company")
    table.add_column("Score", justify="right")
    table.add_column("URL", max_width=35, overflow="fold")

    if not matches:
        table.add_row("[dim]No matches found[/dim]", "", "", "")
        return table

    for job in matches:
        table.add_row(
            job.get("title", ""),
            job.get("company", ""),
            str(job.get("match_score", 0)),
            job.get("url", ""),
        )
    return table


def _toolchain_table(data: dict) -> Table:
    report = data.get("report", {})
    vulns = report.get("vulnerabilities", [])
    recs = report.get("recommendations", [])
    manifests = report.get("manifests", [])

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold magenta")
    table.add_column("Metric")
    table.add_column("Value", justify="right")

    table.add_row("Manifests found", str(report.get("manifests_found", 0)))
    table.add_row(
        "Vulnerabilities",
        Text(str(len(vulns)), style="red bold" if vulns else "green"),
    )
    table.add_row("Recommendations", str(len(recs)))

    for rec in recs[:5]:
        table.add_row("  ↳", f"[yellow]{rec}[/yellow]")

    return table


def _generic_table(data: dict) -> Table:
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold magenta")
    table.add_column("Key")
    table.add_column("Value")
    for k, v in data.items():
        table.add_row(str(k), str(v)[:120])
    return table


def _render_summary(results: Dict[str, AgentResult]) -> None:
    successes = sum(1 for r in results.values() if r.success)
    failures = len(results) - successes
    color = "green" if failures == 0 else "yellow"
    console.rule(
        f"[{color}]{successes}/{len(results)} agents succeeded[/{color}]"
    )
