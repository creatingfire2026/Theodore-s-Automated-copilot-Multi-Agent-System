"""B4: minimal Sentinel MCP server (stdio). Built on the official MCP Python SDK.

mcp 2.x calls the high-level server ``MCPServer`` (it was ``FastMCP`` in mcp 1.x); both are
supported. Pinned version: see requirements-mcp.txt.

    python mcp_server.py            # stdio transport; configure with SENTINEL_* env vars

stdout is the MCP channel, so all logging goes to stderr.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # pragma: no cover - mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer
    from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from approval_verifier import ApprovalError
from audit_log import AuditLogError
from sentinel_gateway import SentinelGateway


def build_server(gateway: SentinelGateway) -> MCPServer:
    server = MCPServer(
        "sentinel-mcp",
        instructions=("Sentinel-gated tools. read_status is read-only. propose_action returns a payload a "
                      "human must sign offline; execute_action requires that Ed25519 signature and is dry-run."),
    )

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True))
    def read_status() -> dict[str, Any]:
        """Low risk, no approval: Sentinel audience, dry-run flag, verifier, dissent store and audit-log health."""
        return gateway.read_status()

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    def propose_action(tool: str, args: dict[str, Any], intent: str, scope: list[str],
                       risk: str = "high") -> dict[str, Any]:
        """Log a proposed action and return the canonical approval payload (base64) for the human to sign."""
        try:
            return gateway.propose_action(tool=tool, args=args, intent=intent, scope=scope, risk=risk)
        except (ValueError, ApprovalError, AuditLogError) as exc:
            raise ToolError(f"proposal rejected: {exc}") from None

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
    def execute_action(action_id: str, args: dict[str, Any], signature_b64: str) -> dict[str, Any]:
        """High risk: requires a valid Ed25519 human approval; routed through Sentinel; dry-run records only."""
        return gateway.execute_action(action_id=action_id, args=args, signature_b64=signature_b64)

    return server


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    build_server(SentinelGateway.from_env()).run("stdio")


if __name__ == "__main__":
    main()
