"""B4: MCP protocol layer - in-memory client and a real stdio subprocess (test keys only)."""
import base64
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")
import anyio  # noqa: E402  (installed with mcp)
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from mcp.client import Client  # noqa: E402
from mcp.client.stdio import StdioServerParameters  # noqa: E402

from approval_verifier import Ed25519ApprovalVerifier, NonceStore  # noqa: E402
from audit_log import AuditLog  # noqa: E402
from mcp_server import build_server  # noqa: E402
from sentinel import Sentinel  # noqa: E402
from sentinel_gateway import SentinelGateway  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
ARGS = {"repo": "demo"}
PROPOSAL = {"tool": "git.push", "args": ARGS, "intent": "push demo", "scope": ["repo:demo"]}


def _flow(target, key):
    async def run():
        async with Client(target) as client:
            names = sorted(t.name for t in (await client.list_tools()).tools)
            status = (await client.call_tool("read_status", {})).structured_content
            proposal = (await client.call_tool("propose_action", PROPOSAL)).structured_content
            sig = base64.b64encode(key.sign(base64.b64decode(proposal["payload_b64"]))).decode()
            tampered = (await client.call_tool("execute_action", {
                "action_id": proposal["action_id"], "args": {"repo": "prod"}, "signature_b64": sig,
            })).structured_content
            ok = (await client.call_tool("execute_action", {
                "action_id": proposal["action_id"], "args": ARGS, "signature_b64": sig,
            })).structured_content
            replay = (await client.call_tool("execute_action", {
                "action_id": proposal["action_id"], "args": ARGS, "signature_b64": sig,
            })).structured_content
            bad_risk = await client.call_tool("propose_action", {**PROPOSAL, "risk": "weird"})
            return names, status, tampered, ok, replay, bad_risk
    return anyio.run(run)


def _check(results):
    names, status, tampered, ok, replay, bad_risk = results
    assert names == ["execute_action", "propose_action", "read_status"]
    assert status["dry_run"] is True and status["approval_verifier"] == "Ed25519ApprovalVerifier"
    assert tampered["status"] == "rejected" and "args_sha256" in tampered["verifier_detail"]
    assert ok["status"] == "dry_run" and ok["would"]["tool"] == "git.push"
    assert replay["status"] == "rejected" and "replay" in replay["verifier_detail"]
    assert bad_risk.is_error and "unknown risk label" in bad_risk.content[0].text


def test_in_memory_mcp_flow(tmp_path):
    key = Ed25519PrivateKey.generate()
    verifier = Ed25519ApprovalVerifier(audience="sentinel-mcp", trusted_humans={"theodore": key.public_key()},
                                       nonce_store=NonceStore(tmp_path / "n.db"))
    gw = SentinelGateway(Sentinel("sentinel-mcp", human_approval_verifier=verifier), AuditLog(tmp_path / "a.db"))
    _check(_flow(build_server(gw), key))
    assert [e["kind"] for e in gw.audit.entries()] == ["proposal", "decision", "decision", "dry_run_execution",
                                                       "decision"]


def test_stdio_subprocess_flow(tmp_path):
    key = Ed25519PrivateKey.generate()
    pub = tmp_path / "human.pub.pem"
    pub.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
                                                  serialization.PublicFormat.SubjectPublicKeyInfo))
    env = {k: v for k, v in os.environ.items() if not k.startswith("SENTINEL_")}
    env.update({
        "PYTHONPATH": str(REPO_ROOT), "SENTINEL_HUMAN_PUBKEY": str(pub),
        "SENTINEL_APPROVAL_NONCE_DB": str(tmp_path / "n.db"), "SENTINEL_MCP_AUDIT_DB": str(tmp_path / "a.db"),
    })
    params = StdioServerParameters(command=sys.executable, args=[str(REPO_ROOT / "mcp_server.py")], env=env,
                                   cwd=str(tmp_path))
    _check(_flow(params, key))
    assert AuditLog(tmp_path / "a.db").head()[0] == 5
