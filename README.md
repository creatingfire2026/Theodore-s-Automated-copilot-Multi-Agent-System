# Theodore-s-Automated-copilot-Multi-Agent-System
A commanding Copilot‑driven multi‑agent system forged for stability, opportunity, and precision. Financial intelligence, job‑seeking automation, and toolchain optimization unite under a disciplined orchestration core, empowering Theodore’s digital ecosystem to rise, adapt, and endure. And scale with new and exsitinal pioneers in technology sector.

## Sentinel MCP server (B3 approval verifier + B4 tools)

`mcp_server.py` is a minimal [Model Context Protocol](https://modelcontextprotocol.io) server
(official Python SDK, `mcp==2.3.0`, stdio transport). In mcp 2.x the high-level server class is
`MCPServer`; it was called `FastMCP` in mcp 1.x, and both imports are supported.

| Tool | Risk | What it does |
| --- | --- | --- |
| `read_status` | low, no approval | Reports audience, dry-run flag, verifier, dissent-store and audit-log health. |
| `propose_action` | logs only | Records the proposal in the hash-chained audit log and returns the canonical approval payload (base64) to sign. |
| `execute_action` | high | Needs a valid Ed25519 human signature (`approval_verifier.py`), goes through `Sentinel.authorize` (risk labels, dissent store, fail closed), logs the decision. **Dry-run only:** it records what it would do and never calls anything. |

The approval payload binds action id, trace id, human id, audience, tool name, SHA-256 of the
canonical args, intent, scope, risk, a one-shot nonce and an expiry (max 1 hour). The verifier rejects
a bad signature, a wrong key, an expired or too-far-out expiry, a replayed nonce (persisted in
SQLite), an audience mismatch, changed args, and any parse error. The payload is plain bytes, so the
existing offline Magic flow (`magic_sign_receipt.sh`) signs it unchanged.

### Install and run (stdio)

```bash
cat > "$HOME/run_sentinel_mcp.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/Theodore-s-Automated-copilot-Multi-Agent-System"
python -m pip install -q cryptography -r requirements-mcp.txt
export SENTINEL_HUMAN_PUBKEY="$HOME/.sentinel/human_ed25519.pub.pem"   # public key only
export SENTINEL_HUMAN_ID=theodore
export SENTINEL_MCP_AUDIENCE=sentinel-mcp
export SENTINEL_MCP_AUDIT_DB="$HOME/.sentinel/mcp_audit.db"
export SENTINEL_APPROVAL_NONCE_DB="$HOME/.sentinel/approval_nonces.db"
exec python mcp_server.py   # speaks MCP over stdin/stdout; logs go to stderr
SH
chmod +x "$HOME/run_sentinel_mcp.sh"
```

MCP client config (Cursor / Claude Desktop style):

```json
{ "mcpServers": { "sentinel": { "command": "/home/YOU/run_sentinel_mcp.sh" } } }
```

### Sign an approval

Real key (offline, on Magic): copy `payload_b64` from `propose_action`, then

```bash
printf '%s\n' 'PASTE_PAYLOAD_B64' | ~/.sentinel/magic_sign_receipt.sh
```

and pass the printed signature to `execute_action` as `signature_b64` with the **same** `args`.

### Try the whole flow with a throwaway test key (never your real key)

```bash
cat > /tmp/sentinel_mcp_demo.py <<'PY'
import base64, os, subprocess, sys, tempfile
import anyio
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

repo = os.getcwd()
work = tempfile.mkdtemp(prefix="sentinel-demo-")
sdir = os.path.join(work, ".sentinel"); os.makedirs(sdir, mode=0o700)
priv, pub = os.path.join(sdir, "human_ed25519.pem"), os.path.join(work, "human.pub.pem")
subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", priv], check=True); os.chmod(priv, 0o600)
subprocess.run(["openssl", "pkey", "-in", priv, "-pubout", "-out", pub], check=True)
env = {**os.environ, "PYTHONPATH": repo, "SENTINEL_HUMAN_PUBKEY": pub,
       "SENTINEL_MCP_AUDIT_DB": os.path.join(work, "audit.db"),
       "SENTINEL_APPROVAL_NONCE_DB": os.path.join(work, "nonces.db")}
args = {"repo": "demo", "branch": "feature"}

async def main():
    params = StdioServerParameters(command=sys.executable, args=[os.path.join(repo, "mcp_server.py")], env=env)
    async with Client(params) as c:
        print("status:", (await c.call_tool("read_status", {})).structured_content)
        p = (await c.call_tool("propose_action", {"tool": "git.push", "args": args,
             "intent": "push feature branch", "scope": ["repo:demo"]})).structured_content
        sig = subprocess.run(["sh", os.path.join(repo, "magic_sign_receipt.sh")], input=p["payload_b64"] + "\n",
                             capture_output=True, text=True, check=True, env={**env, "SENTINEL_DIR": sdir}).stdout.strip()
        r = (await c.call_tool("execute_action", {"action_id": p["action_id"], "args": args,
             "signature_b64": sig})).structured_content
        print("execute:", r["status"], r.get("would"))
        r = (await c.call_tool("execute_action", {"action_id": p["action_id"], "args": args,
             "signature_b64": sig})).structured_content
        print("replay:", r["status"], r["verifier_detail"])

anyio.run(main)
PY
python /tmp/sentinel_mcp_demo.py   # run from the repo root
```

Not done yet: no OAuth/OIDC token check on the MCP transport (B1), no live executor (dry-run
only), and the MCP audit log is hash-chained but not signed or witnessed (the A7 dissent store is).
