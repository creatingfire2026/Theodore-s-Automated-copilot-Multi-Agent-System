"""B4 core: gateway tools + hash-chained audit log (no MCP SDK needed)."""
import base64
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from approval_verifier import Ed25519ApprovalVerifier, NonceStore
from audit_log import AuditLog, AuditLogError
from dissent_store import Dissent
from sentinel import Sentinel
from sentinel_gateway import SentinelGateway

AUD = "sentinel-mcp"
ARGS = {"repo": "demo", "branch": "feature"}


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 28, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


class OpenDissentStore:
    def open_dissents(self):
        return [Dissent(1, "D-1", "*", "A7 objects", "A7", "2026-11-28T00:00:00Z", "h" * 64)]

    def known_dissent_ids(self):
        return {"D-1"}


@pytest.fixture
def key():
    return Ed25519PrivateKey.generate()


@pytest.fixture
def clock():
    return Clock()


def make_gateway(tmp_path, key, clock, *, verifier=True, dry_run=True, dissent_store=None):
    v = Ed25519ApprovalVerifier(audience=AUD, trusted_humans={"theodore": key.public_key()},
                                nonce_store=NonceStore(tmp_path / "nonces.db"), clock=clock) if verifier else None
    sentinel = Sentinel(AUD, human_approval_verifier=v, dissent_store=dissent_store)
    return SentinelGateway(sentinel, AuditLog(tmp_path / "audit.db"), clock=clock, dry_run=dry_run)


@pytest.fixture
def gw(tmp_path, key, clock):
    return make_gateway(tmp_path, key, clock)


def propose(gw, **over):
    params = dict(tool="git.push", args=ARGS, intent="push feature branch", scope=["repo:demo"])
    params.update(over)
    return gw.propose_action(**params)


def sign(key, proposal):
    return base64.b64encode(key.sign(base64.b64decode(proposal["payload_b64"]))).decode()


def kinds(gw):
    return [e["kind"] for e in gw.audit.entries()]


def test_read_status_needs_no_approval(gw):
    status = gw.read_status()
    assert status["audience"] == AUD and status["dry_run"] is True
    assert status["approval_verifier"] == "Ed25519ApprovalVerifier"
    assert status["audit_log"]["ok"] and status["audit_log"]["entries"] == 0
    assert status["dissent_store"] == {"configured": False}


def test_read_status_reports_open_dissents(tmp_path, key, clock):
    gw = make_gateway(tmp_path, key, clock, dissent_store=OpenDissentStore())
    assert gw.read_status()["dissent_store"]["open_dissents"] == ["D-1"]


def test_propose_logs_and_returns_signable_payload(gw):
    p = propose(gw, risk="low")
    assert p["payload"]["aud"] == AUD and p["payload"]["risk"] == "high"  # execute is always high risk
    assert p["payload"]["expires_at"] == "2026-11-28T12:15:00Z"
    assert kinds(gw) == ["proposal"]
    assert "args" not in gw.audit.entries()[0]["body"]  # only the hash is bound, args are not stored


def test_propose_critical_stays_critical(gw):
    assert propose(gw, risk="critical")["payload"]["risk"] == "critical"


@pytest.mark.parametrize("over", [
    {"risk": "LOWISH"}, {"tool": ""}, {"scope": []}, {"scope": "repo:demo"}, {"intent": " "},
    {"args": {"x": float("inf")}}, {"args": ["not", "dict"]},
])
def test_propose_rejects_bad_input(gw, over):
    with pytest.raises(Exception):
        propose(gw, **over)
    assert kinds(gw) == []


def test_execute_happy_path_is_dry_run(gw, key):
    p = propose(gw)
    out = gw.execute_action(action_id=p["action_id"], args=ARGS, signature_b64=sign(key, p))
    assert out["status"] == "dry_run" and out["decision"] == "authorized"
    assert out["would"]["tool"] == "git.push"
    assert kinds(gw) == ["proposal", "decision", "dry_run_execution"]


def test_execute_without_verifier_fails_closed(tmp_path, key, clock):
    gw = make_gateway(tmp_path, key, clock, verifier=False)
    p = propose(gw)
    out = gw.execute_action(action_id=p["action_id"], args=ARGS, signature_b64=sign(key, p))
    assert out["status"] == "rejected" and "no independent human-approval verifier" in out["reason"]
    assert "dry_run_execution" not in kinds(gw)


def test_execute_bad_signature(gw):
    p = propose(gw)
    out = gw.execute_action(action_id=p["action_id"], args=ARGS,
                            signature_b64=sign(Ed25519PrivateKey.generate(), p))
    assert out["status"] == "rejected" and "signature does not verify" in out["verifier_detail"]


def test_execute_args_tampering(gw, key):
    p = propose(gw)
    out = gw.execute_action(action_id=p["action_id"], args={**ARGS, "branch": "main"}, signature_b64=sign(key, p))
    assert out["status"] == "rejected" and "args_sha256 mismatch" in out["verifier_detail"]
    assert "dry_run_execution" not in kinds(gw)


def test_execute_replay(gw, key):
    p = propose(gw)
    sig = sign(key, p)
    assert gw.execute_action(action_id=p["action_id"], args=ARGS, signature_b64=sig)["status"] == "dry_run"
    again = gw.execute_action(action_id=p["action_id"], args=ARGS, signature_b64=sig)
    assert again["status"] == "rejected" and "replay" in again["verifier_detail"]


def test_execute_expired(gw, key, clock):
    p = propose(gw)
    clock.now += timedelta(minutes=16)
    out = gw.execute_action(action_id=p["action_id"], args=ARGS, signature_b64=sign(key, p))
    assert out["status"] == "rejected" and "expired" in out["verifier_detail"]


def test_execute_unknown_action(gw, key):
    out = gw.execute_action(action_id="act-nope", args=ARGS, signature_b64="AAAA")
    assert out["status"] == "rejected" and "no logged proposal" in out["reason"]
    assert kinds(gw) == ["rejected"]


@pytest.mark.parametrize("bad", [{"action_id": ""}, {"signature_b64": ""}, {"args": "nope"}])
def test_execute_bad_input_fails_closed(gw, key, bad):
    p = propose(gw)
    params = dict(action_id=p["action_id"], args=ARGS, signature_b64=sign(key, p))
    params.update(bad)
    assert gw.execute_action(**params)["status"] == "rejected"


def test_execute_blocked_by_open_dissent(tmp_path, key, clock):
    gw = make_gateway(tmp_path, key, clock, dissent_store=OpenDissentStore())
    p = propose(gw)
    out = gw.execute_action(action_id=p["action_id"], args=ARGS, signature_b64=sign(key, p))
    assert out["status"] == "rejected" and "open protected A7 dissent" in out["reason"]


def test_live_mode_refuses(tmp_path, key, clock):
    gw = make_gateway(tmp_path, key, clock, dry_run=False)
    p = propose(gw)
    out = gw.execute_action(action_id=p["action_id"], args=ARGS, signature_b64=sign(key, p))
    assert out["status"] == "refused" and kinds(gw)[-1] == "execution_refused"


def test_tampered_audit_log_fails_closed(gw, key):
    p = propose(gw)
    conn = sqlite3.connect(gw.audit.path)
    conn.execute("DROP TRIGGER audit_log_no_update")
    conn.execute("UPDATE audit_log SET body = replace(body, 'mcp-client', 'evil') WHERE seq = 1")
    conn.commit()
    conn.close()
    out = gw.execute_action(action_id=p["action_id"], args=ARGS, signature_b64=sign(key, p))
    assert out["status"] == "rejected" and "audit log" in out["reason"]
    assert gw.read_status()["audit_log"]["ok"] is False


# --- audit log ------------------------------------------------------------------------
def test_audit_log_chain_and_append_only(tmp_path):
    log = AuditLog(tmp_path / "a.db")
    h1 = log.append("x", {"n": 1})
    h2 = log.append("y", {"n": 2})
    assert log.head() == (2, h2) and h1 != h2
    conn = sqlite3.connect(log.path)
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM audit_log")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE audit_log SET kind = 'z'")
    conn.close()
    assert (log.path.stat().st_mode & 0o077) == 0


def test_audit_log_detects_truncation_gap(tmp_path):
    log = AuditLog(tmp_path / "a.db")
    for i in range(3):
        log.append("x", {"n": i})
    conn = sqlite3.connect(log.path)
    conn.execute("DROP TRIGGER audit_log_no_delete")
    conn.execute("DELETE FROM audit_log WHERE seq = 2")
    conn.commit()
    conn.close()
    with pytest.raises(AuditLogError):
        log.entries()
    with pytest.raises(AuditLogError):
        log.append("x", {})


def test_from_env_without_key_has_no_verifier(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINEL_MCP_AUDIT_DB", str(tmp_path / "a.db"))
    gw = SentinelGateway.from_env()
    assert gw.sentinel.human_approval_verifier is None and gw.dry_run is True
