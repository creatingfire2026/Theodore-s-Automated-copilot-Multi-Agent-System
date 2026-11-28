"""B3: Ed25519 approval verifier - happy path and every rejection path (test keys only)."""
import base64
import os
import shutil
import subprocess
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from approval_verifier import (
    ApprovalError, Ed25519ApprovalVerifier, NonceStore, approval_payload, args_sha256, format_expiry,
    parse_approval_payload,
)
from dissent_store import _canonical
from sentinel import ActionRequest, Decision, HumanApproval, Sentinel

NOW = datetime(2026, 11, 28, 12, 0, 0, tzinfo=timezone.utc)
AUD = "sentinel-mcp"
ARGS = {"repo": "demo", "branch": "main", "count": 2}
REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def human_key():
    return Ed25519PrivateKey.generate()


@pytest.fixture
def verifier(tmp_path, human_key):
    return Ed25519ApprovalVerifier(
        audience=AUD, trusted_humans={"theodore": human_key.public_key()},
        nonce_store=NonceStore(tmp_path / "nonces.db"), clock=lambda: NOW,
    )


def fields(**over):
    base = dict(
        action_id="act-1", trace_id="trace-1", human_id="theodore", aud=AUD, tool="git.push",
        args_sha256=args_sha256(ARGS), intent="push demo branch", scope=["repo:demo"], risk="high",
        nonce="ab" * 16, expires_at=format_expiry(NOW + timedelta(minutes=10)),
    )
    base.update(over)
    return base


def sign(key, payload: bytes) -> str:
    return base64.b64encode(key.sign(payload)).decode("ascii")


def build(key, *, payload_fields=None, payload_bytes=None, request_over=None, approval_over=None):
    f = payload_fields or fields()
    payload = payload_bytes if payload_bytes is not None else approval_payload(**f)
    request = ActionRequest(actor="agent", intent="push demo branch", scope=["repo:demo"], authority="test",
                            risk="high", trace_id="trace-1", aud=AUD, tool="git.push",
                            args_sha256=args_sha256(ARGS))
    if request_over:
        request = replace(request, **request_over)
    approval = HumanApproval("act-1", "theodore", "trace-1", "push demo branch", ("repo:demo",),
                             f["expires_at"], sign(key, payload),
                             payload_b64=base64.b64encode(payload).decode("ascii"))
    if approval_over:
        approval = replace(approval, **approval_over)
    return approval, request


def test_happy_path_verifies_and_consumes_nonce(verifier, human_key):
    approval, request = build(human_key)
    result = verifier.check(approval, request)
    assert result.ok, result.reason
    assert verifier.nonce_store.is_used("ab" * 16)


def test_sentinel_authorizes_with_real_verifier(verifier, human_key):
    approval, request = build(human_key)
    record = Sentinel(AUD, human_approval_verifier=verifier).authorize(request, human_approval=approval)
    assert record.decision is Decision.AUTHORIZED


def test_sentinel_blocks_tampered_args_with_real_verifier(verifier, human_key):
    approval, request = build(human_key, request_over={"args_sha256": args_sha256({**ARGS, "branch": "prod"})})
    record = Sentinel(AUD, human_approval_verifier=verifier).authorize(request, human_approval=approval)
    assert record.decision is Decision.HUMAN_REVIEW
    assert "args_sha256 mismatch" in verifier.last_reason


def test_bad_signature(verifier, human_key):
    approval, request = build(human_key)
    sig = bytearray(base64.b64decode(approval.signature))
    sig[0] ^= 0x01
    approval = replace(approval, signature=base64.b64encode(bytes(sig)).decode())
    result = verifier.check(approval, request)
    assert not result.ok and "signature does not verify" in result.reason


def test_wrong_key(verifier):
    approval, request = build(Ed25519PrivateKey.generate())
    result = verifier.check(approval, request)
    assert not result.ok and "signature does not verify" in result.reason


def test_unknown_human(verifier, human_key):
    approval, request = build(human_key, payload_fields=fields(human_id="mallory"),
                              approval_over={"human_id": "mallory"})
    result = verifier.check(approval, request)
    assert not result.ok and "human_id" in result.reason


def test_approval_human_id_must_match_payload(verifier, human_key):
    approval, request = build(human_key, approval_over={"human_id": "someone-else"})
    assert not verifier.check(approval, request).ok


def test_expired(verifier, human_key):
    f = fields(expires_at=format_expiry(NOW - timedelta(seconds=1)))
    approval, request = build(human_key, payload_fields=f)
    result = verifier.check(approval, request)
    assert not result.ok and "expired" in result.reason


def test_expiry_beyond_max_ttl(verifier, human_key):
    f = fields(expires_at=format_expiry(NOW + timedelta(days=30)))
    approval, request = build(human_key, payload_fields=f)
    result = verifier.check(approval, request)
    assert not result.ok and "max TTL" in result.reason


def test_replayed_nonce(verifier, human_key):
    approval, request = build(human_key)
    assert verifier.check(approval, request).ok
    result = verifier.check(approval, request)
    assert not result.ok and "replay" in result.reason


def test_replay_detected_across_restart(tmp_path, verifier, human_key):
    approval, request = build(human_key)
    assert verifier.check(approval, request).ok
    fresh = Ed25519ApprovalVerifier(audience=AUD, trusted_humans={"theodore": human_key.public_key()},
                                    nonce_store=NonceStore(tmp_path / "nonces.db"), clock=lambda: NOW)
    assert "replay" in fresh.check(approval, request).reason


def test_failed_check_does_not_burn_nonce(verifier, human_key):
    good, request = build(human_key)
    bad = replace(good, signature=sign(Ed25519PrivateKey.generate(), b"x"))
    assert not verifier.check(bad, request).ok
    assert verifier.check(good, request).ok


def test_audience_mismatch_in_signed_payload(verifier, human_key):
    approval, request = build(human_key, payload_fields=fields(aud="some-other-server"))
    result = verifier.check(approval, request)
    assert not result.ok and "aud mismatch" in result.reason


def test_audience_mismatch_on_request(verifier, human_key):
    approval, request = build(human_key, request_over={"aud": "other"})
    assert "aud mismatch" in verifier.check(approval, request).reason


def test_args_tampering(verifier, human_key):
    approval, request = build(human_key, request_over={"args_sha256": args_sha256({**ARGS, "count": 3})})
    result = verifier.check(approval, request)
    assert not result.ok and "args_sha256 mismatch" in result.reason


@pytest.mark.parametrize("over, name", [
    ({"tool": "git.force_push"}, "tool"),
    ({"trace_id": "trace-2"}, "trace_id"),
    ({"intent": "delete repo"}, "intent"),
    ({"scope": ["repo:prod"]}, "scope"),
    ({"risk": "critical"}, "risk"),
])
def test_request_binding_mismatch(verifier, human_key, over, name):
    approval, request = build(human_key, request_over=over)
    result = verifier.check(approval, request)
    assert not result.ok and f"{name} mismatch" in result.reason


@pytest.mark.parametrize("over, name", [
    ({"approval_id": "act-2"}, "action_id"),
    ({"expires_at": "2026-11-28T12:05:00Z"}, "expires_at"),
])
def test_approval_binding_mismatch(verifier, human_key, over, name):
    approval, request = build(human_key, approval_over=over)
    result = verifier.check(approval, request)
    assert not result.ok and f"{name} mismatch" in result.reason


def _signed_raw(key, payload: bytes):
    return build(key, payload_bytes=payload)


@pytest.mark.parametrize("mutate", [
    lambda d: {**d, "extra": "x"},
    lambda d: {k: v for k, v in d.items() if k != "nonce"},
    lambda d: {**d, "v": 2},
    lambda d: {**d, "kind": "receipt"},
    lambda d: {**d, "scope": []},
    lambda d: {**d, "scope": "repo:demo"},
    lambda d: {**d, "nonce": "short"},
    lambda d: {**d, "args_sha256": "ABC"},
    lambda d: {**d, "expires_at": "tomorrow"},
    lambda d: {**d, "tool": ""},
    lambda d: {**d, "intent": 7},
])
def test_malformed_payload_fails_closed_even_when_signed(verifier, human_key, mutate):
    import json
    data = json.loads(approval_payload(**fields()))
    approval, request = _signed_raw(human_key, _canonical(mutate(data)))
    assert not verifier.check(approval, request).ok


def test_non_canonical_payload_rejected_even_when_signed(verifier, human_key):
    import json
    loose = json.dumps(json.loads(approval_payload(**fields())), indent=1).encode()
    approval, request = _signed_raw(human_key, loose)
    result = verifier.check(approval, request)
    assert not result.ok and "canonical" in result.reason


@pytest.mark.parametrize("payload_b64, signature", [
    ("", None), ("!!!not base64!!!", None), (base64.b64encode(b"not json").decode(), None),
    (base64.b64encode(b"\xff\xfe").decode(), None), (None, "%%%"), (None, ""),
])
def test_parse_errors_fail_closed(verifier, human_key, payload_b64, signature):
    approval, request = build(human_key)
    if payload_b64 is not None:
        approval = replace(approval, payload_b64=payload_b64)
    if signature is not None:
        approval = replace(approval, signature=signature)
    assert verifier(approval, request) is False


def test_non_string_fields_fail_closed(verifier, human_key):
    approval, request = build(human_key, approval_over={"payload_b64": 12345})
    assert verifier(approval, request) is False


def test_unusable_nonce_store_fails_closed(tmp_path, human_key):
    blocker = tmp_path / "dir"
    blocker.mkdir()
    v = Ed25519ApprovalVerifier(audience=AUD, trusted_humans={"theodore": human_key.public_key()},
                                nonce_store=NonceStore(blocker), clock=lambda: NOW)
    approval, request = build(human_key)
    result = v.check(approval, request)
    assert not result.ok and "nonce store" in result.reason


def test_args_hash_is_canonical_and_strict():
    assert args_sha256({"b": 1, "a": 2}) == args_sha256({"a": 2, "b": 1})
    with pytest.raises(ApprovalError):
        args_sha256({"x": float("nan")})
    with pytest.raises(ApprovalError):
        args_sha256(["not", "a", "dict"])


def test_parse_round_trip():
    assert parse_approval_payload(approval_payload(**fields()))["nonce"] == "ab" * 16


def test_from_env_without_pubkey_is_none():
    assert Ed25519ApprovalVerifier.from_env() is None


def test_from_env_loads_spki_pem(tmp_path, monkeypatch, human_key):
    pem = tmp_path / "human.pub.pem"
    pem.write_bytes(human_key.public_key().public_bytes(serialization.Encoding.PEM,
                                                       serialization.PublicFormat.SubjectPublicKeyInfo))
    monkeypatch.setenv("SENTINEL_HUMAN_PUBKEY", str(pem))
    monkeypatch.setenv("SENTINEL_APPROVAL_NONCE_DB", str(tmp_path / "n.db"))
    v = Ed25519ApprovalVerifier.from_env(audience=AUD)
    assert v is not None and "theodore" in v.trusted_humans


def test_magic_sign_receipt_script_signs_approval_payload(tmp_path, monkeypatch):
    """Same offline flow as dissent receipts: base64 payload -> magic_sign_receipt.sh -> signature."""
    if not shutil.which("openssl"):
        pytest.skip("openssl binary not installed")
    magic = tmp_path / "magic" / ".sentinel"
    magic.mkdir(parents=True, mode=0o700)
    pass_file, priv, pub = magic / "human_key.pass", magic / "human_ed25519.pem", tmp_path / "human.pub.pem"
    subprocess.run(f"openssl rand -base64 24 > '{pass_file}' && chmod 600 '{pass_file}'", shell=True, check=True)
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-aes-256-cbc", "-pass", f"file:{pass_file}",
                    "-out", str(priv)], check=True)
    os.chmod(priv, 0o600)
    subprocess.run(["openssl", "pkey", "-in", str(priv), "-passin", f"file:{pass_file}", "-pubout",
                    "-out", str(pub)], check=True)

    payload = approval_payload(**fields())
    env = {**os.environ, "SENTINEL_DIR": str(magic)}
    sig = subprocess.run(["sh", str(REPO_ROOT / "magic_sign_receipt.sh")],
                         input=base64.b64encode(payload).decode() + "\n", capture_output=True, text=True,
                         env=env, check=True).stdout.strip()

    monkeypatch.setenv("SENTINEL_HUMAN_PUBKEY", str(pub))
    monkeypatch.setenv("SENTINEL_APPROVAL_NONCE_DB", str(tmp_path / "n.db"))
    v = Ed25519ApprovalVerifier.from_env(audience=AUD)
    v.clock = lambda: NOW
    request = ActionRequest(actor="agent", intent="push demo branch", scope=["repo:demo"], authority="test",
                            risk="high", trace_id="trace-1", aud=AUD, tool="git.push",
                            args_sha256=args_sha256(ARGS))
    approval = HumanApproval("act-1", "theodore", "trace-1", "push demo branch", ("repo:demo",),
                             fields()["expires_at"], sig, payload_b64=base64.b64encode(payload).decode())
    result = v.check(approval, request)
    assert result.ok, result.reason
