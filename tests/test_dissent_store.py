"""Regression tests for F34: protected A7 dissent can no longer be bypassed by omitting its ID."""
import json
import os
import sqlite3
import stat

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import dissent_cli
from aip001_council import file_protected_dissent
from dissent_store import (
    DissentStore, DissentStoreError, DissentWriteRejected, GENESIS_HASH, clear_dissent, compute_row_hash,
    dissent_payload, load_private_key, receipt_payload, sign_b64,
)
from sentinel import ActionRequest, Decision, HumanApproval, Sentinel

TRIGGERS = """
CREATE TRIGGER dissent_log_no_update BEFORE UPDATE ON dissent_log BEGIN SELECT RAISE(ABORT,'x'); END;
CREATE TRIGGER dissent_log_no_delete BEFORE DELETE ON dissent_log BEGIN SELECT RAISE(ABORT,'x'); END;
"""


def req(**kw):
    kw.setdefault("aud", "sentinel")
    return ActionRequest("agent", kw.pop("intent", "deploy"), kw.pop("scope", ["prod"]), "policy", **kw)


def _write_pub(key, path):
    path.write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    return path


@pytest.fixture
def human_key():
    return Ed25519PrivateKey.generate()


@pytest.fixture
def a7_key():
    return Ed25519PrivateKey.generate()


@pytest.fixture
def store(tmp_path, human_key, a7_key):
    (tmp_path / "db").mkdir()
    (tmp_path / "anchor").mkdir()
    s = DissentStore(tmp_path / "db" / "dissent.db", _write_pub(human_key, tmp_path / "human.pub"),
                     _write_pub(a7_key, tmp_path / "a7.pub"), tmp_path / "anchor" / "head.json")
    s.initialize(("A7", a7_key))
    return s


def decide(store, request=None, **kw):
    return Sentinel(dissent_store=store, **kw).authorize(request or req())


def file(store, a7_key, dissent_id="D-1", target="prod", reason="unsafe rollout"):
    return file_protected_dissent(store, a7_key, dissent_id=dissent_id, target=target, reason=reason)


def raw(store):
    return sqlite3.connect(store.path)


def rows_of(store):
    with raw(store) as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute("SELECT * FROM dissent_log ORDER BY seq")]


def rewrite_chain(store, rows):
    """Attacker with file access: drop triggers, replace all rows with a self-consistent chain."""
    prev = "0" * 64
    c = raw(store)
    c.executescript("DROP TRIGGER dissent_log_no_update; DROP TRIGGER dissent_log_no_delete;")
    c.execute("DELETE FROM dissent_log")
    for seq, row in enumerate(rows, start=1):
        row = dict(row, seq=seq, prev_hash=prev)
        row["row_hash"] = compute_row_hash(row, prev)
        c.execute("INSERT INTO dissent_log VALUES (:seq,:kind,:dissent_id,:target,:reason,:author,:ts,"
                  ":dissent_row_hash,:signature,:prev_hash,:row_hash)", row)
        prev = row["row_hash"]
    c.executescript(TRIGGERS)
    c.commit()
    c.close()


# --- the bypass itself ----------------------------------------------------

def test_omitted_dissent_id_with_open_dissent_is_human_review(store, a7_key):
    file(store, a7_key)
    result = decide(store)  # no protected_dissent_id supplied
    assert result.decision is Decision.HUMAN_REVIEW
    assert "D-1" in result.reason


def test_a7_council_dissent_blocks_until_human_receipt(store, a7_key, human_key):
    file_protected_dissent(store, a7_key, dissent_id="A7-2026-001", target="deploy", reason="unreviewed migration")
    assert decide(store).decision is Decision.HUMAN_REVIEW
    assert decide(store, req(risk="medium")).decision is Decision.HUMAN_REVIEW
    clear_dissent(store, human_key, dissent_id="A7-2026-001", human="theodore", reason="reviewed migration plan")
    assert decide(store).decision is Decision.AUTHORIZED


def test_dissent_matches_intent(store, a7_key):
    file(store, a7_key, "D-int", target="deploy")
    assert decide(store, req(scope=["other"])).decision is Decision.HUMAN_REVIEW


def test_wildcard_dissent_blocks_everything(store, a7_key):
    file(store, a7_key, "D-all", target="*")
    assert decide(store, req(intent="x", scope=["y"])).decision is Decision.HUMAN_REVIEW


def test_unrelated_dissent_does_not_block(store, a7_key):
    file(store, a7_key, "D-9", target="billing")
    assert decide(store).decision is Decision.AUTHORIZED


def test_human_approval_envelope_cannot_bypass_store_dissent(store, a7_key):
    file(store, a7_key)
    request = req(protected_dissent_node="A7", protected_dissent_id="D-1")
    approval = HumanApproval("a", "h", request.trace_id, request.intent, tuple(request.scope), "2099", "sig", "D-1", "ok")
    sentinel = Sentinel(dissent_store=store, human_approval_verifier=lambda g, a: True)
    assert sentinel.authorize(request, human_approval=approval).decision is Decision.HUMAN_REVIEW


def test_hint_for_unknown_dissent_fails_closed(store):
    assert decide(store, req(protected_dissent_node="A7", protected_dissent_id="D-ghost")).decision is Decision.HUMAN_REVIEW


# --- risk labels (PR #17 behavior kept) -----------------------------------

def test_odd_case_risk_label_with_store_still_human_review(store):
    for label in ("High", "HIGH", " Critical "):
        assert decide(store, req(risk=label)).decision is Decision.HUMAN_REVIEW


def test_unknown_risk_label_with_store_never_authorizes(store):
    for label in ("severe", "", None, "lowish"):
        assert decide(store, req(risk=label)).decision is not Decision.AUTHORIZED


# --- dissent writers: A7 only, signed -------------------------------------

@pytest.mark.parametrize("author", ["A1", "A3", "Grok", "a7", "", "sentinel"])
def test_non_a7_dissent_write_rejected(store, a7_key, author):
    with pytest.raises(DissentWriteRejected):
        file_protected_dissent(store, a7_key, dissent_id="D-x", target="prod", reason="r", node_id=author)
    assert store.head()[0] == 0


def test_unsigned_dissent_rejected_on_write(store, a7_key):
    with pytest.raises(DissentWriteRejected, match="unsigned"):
        store.append_dissent(author="A7", dissent_id="D-1", target="prod", reason="r", ts="t",
                             signature_b64="", anchor_signer=("A7", a7_key))
    assert store.head()[0] == 0


def test_fake_a7_wrong_key_dissent_rejected(store):
    with pytest.raises(DissentWriteRejected):
        file_protected_dissent(store, Ed25519PrivateKey.generate(), dissent_id="D-1", target="prod", reason="r")
    assert store.head()[0] == 0


def test_unsigned_dissent_smuggled_into_file_is_human_review(store, a7_key):
    file(store, a7_key, "D-0", target="billing")
    forged = dict(rows_of(store)[0], dissent_id="D-fake", signature="")
    rewrite_chain(store, rows_of(store) + [forged])
    result = decide(store)
    assert result.decision is Decision.HUMAN_REVIEW
    assert "invalid A7 signature" in result.reason


def test_duplicate_dissent_id_rejected(store, a7_key):
    file(store, a7_key)
    with pytest.raises(DissentWriteRejected):
        file(store, a7_key, "D-1", target="other")


# --- receipts --------------------------------------------------------------

def _receipt(store, key, dissent_id, human="theodore", reason="risk accepted", ts="2026-11-24T06:00:00Z"):
    d = store.dissent(dissent_id)
    payload = receipt_payload(d.dissent_id, d.row_hash, d.target, reason, human, ts)
    return dict(dissent_id=dissent_id, author=human, reason=reason, ts=ts, signature_b64=sign_b64(key, payload))


def test_receipt_with_wrong_key_does_not_clear(store, a7_key, human_key):
    file(store, a7_key)
    with pytest.raises(DissentWriteRejected):
        store.append_receipt(**_receipt(store, Ed25519PrivateKey.generate(), "D-1"), anchor_signer=("human", human_key))
    assert decide(store).decision is Decision.HUMAN_REVIEW


def test_a7_cannot_clear_its_own_dissent(store, a7_key):
    file(store, a7_key)
    with pytest.raises(DissentWriteRejected):
        clear_dissent(store, a7_key, dissent_id="D-1", human="A7", reason="self-clear")
    assert decide(store).decision is Decision.HUMAN_REVIEW


def test_forged_receipt_inserted_directly_fails_closed(store, a7_key):
    file(store, a7_key)
    d = store.dissent("D-1")
    bad = _receipt(store, Ed25519PrivateKey.generate(), "D-1")
    row = {"kind": "receipt", "dissent_id": "D-1", "target": d.target, "reason": bad["reason"],
           "author": bad["author"], "ts": bad["ts"], "dissent_row_hash": d.row_hash, "signature": bad["signature_b64"]}
    rewrite_chain(store, rows_of(store) + [row])
    result = decide(store)
    assert result.decision is Decision.HUMAN_REVIEW
    assert "invalid human signature" in result.reason


def test_valid_receipt_clears_and_request_authorizes(store, a7_key, human_key):
    file(store, a7_key)
    clear_dissent(store, human_key, dissent_id="D-1", human="theodore", reason="risk accepted")
    assert store.open_dissents() == []
    assert decide(store).decision is Decision.AUTHORIZED
    assert decide(store, req(protected_dissent_node="A7", protected_dissent_id="D-1")).decision is Decision.AUTHORIZED


def test_receipt_cannot_be_replayed_onto_another_dissent(store, a7_key, human_key):
    file(store, a7_key, "D-1")
    file(store, a7_key, "D-2")
    receipt = _receipt(store, human_key, "D-1")
    receipt["dissent_id"] = "D-2"
    with pytest.raises(DissentWriteRejected):
        store.append_receipt(**receipt, anchor_signer=("human", human_key))


# --- tamper / integrity ------------------------------------------------------

def test_triggers_block_update_and_delete(store, a7_key):
    file(store, a7_key)
    with raw(store) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("UPDATE dissent_log SET target='nothing'")
    with raw(store) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("DELETE FROM dissent_log")


def test_tampered_row_after_dropping_triggers_is_human_review(store, a7_key):
    file(store, a7_key)
    with raw(store) as c:
        c.execute("DROP TRIGGER dissent_log_no_update")
        c.execute("UPDATE dissent_log SET target='nothing-real' WHERE dissent_id='D-1'")
        c.execute("CREATE TRIGGER dissent_log_no_update BEFORE UPDATE ON dissent_log BEGIN SELECT RAISE(ABORT,'x'); END")
    result = decide(store)
    assert result.decision is Decision.HUMAN_REVIEW
    assert "hash chain broken" in result.reason


def test_dropped_triggers_alone_fail_closed(store):
    with raw(store) as c:
        c.execute("DROP TRIGGER dissent_log_no_delete")
    assert decide(store).decision is Decision.HUMAN_REVIEW


def test_deleted_middle_row_breaks_chain_is_human_review(store, a7_key):
    for i, t in enumerate(("billing", "prod", "billing")):
        file(store, a7_key, f"D-{i}", target=t)
    with raw(store) as c:
        c.execute("DROP TRIGGER dissent_log_no_delete")
        c.execute("DELETE FROM dissent_log WHERE dissent_id='D-1'")
    assert decide(store).decision is Decision.HUMAN_REVIEW


def test_truncation_of_newest_rows_detected_by_anchor(store, a7_key):
    file(store, a7_key, "D-0", target="billing")
    file(store, a7_key, "D-1", target="prod")
    with raw(store) as c:  # remove the newest row: the chain alone would still verify
        c.execute("DROP TRIGGER dissent_log_no_delete")
        c.execute("DELETE FROM dissent_log WHERE seq=2")
        c.execute("CREATE TRIGGER dissent_log_no_delete BEFORE DELETE ON dissent_log BEGIN SELECT RAISE(ABORT,'x'); END")
    result = decide(store)
    assert result.decision is Decision.HUMAN_REVIEW
    assert "truncated" in result.reason


def test_consistent_full_chain_rewrite_detected_by_anchor(store, a7_key):
    file(store, a7_key, "D-0", target="billing")
    file(store, a7_key, "D-1", target="prod")
    file(store, a7_key, "D-2", target="billing")
    rows = rows_of(store)
    # Every row keeps its valid A7 signature and the rewritten chain is self-consistent,
    # so only the signed head anchor can catch these.
    rewrite_chain(store, [rows[0], rows[2]])  # D-1 silently removed, chain re-linked
    assert "truncated" in decide(store).reason
    rewrite_chain(store, [rows[0], rows[2], rows[1]])  # same count, reordered
    result = decide(store)
    assert result.decision is Decision.HUMAN_REVIEW
    assert "head anchor" in result.reason


def test_anchor_missing_tampered_or_wrongly_signed_is_human_review(store, a7_key):
    file(store, a7_key)
    original = store.anchor_path.read_text()
    data = json.loads(original)
    store.anchor_path.write_text(json.dumps(dict(data, count=0, head_hash="0" * 64)))
    assert "signature invalid" in decide(store).reason
    store.anchor_path.unlink()
    assert "anchor missing" in decide(store).reason
    store.anchor_path.write_text("{not json")
    assert decide(store).decision is Decision.HUMAN_REVIEW
    store.anchor_path.write_text(original)
    with pytest.raises(DissentWriteRejected):  # anchor signer must be a configured key
        store.append_dissent(author="A7", dissent_id="D-2", target="x", reason="r", ts="t",
                             signature_b64=sign_b64(a7_key, dissent_payload("D-2", "x", "r", "A7", "t")),
                             anchor_signer=("A7", Ed25519PrivateKey.generate()))
    assert decide(store).decision is Decision.HUMAN_REVIEW  # D-1 still open, store intact


def test_anchor_inside_db_dir_is_rejected(tmp_path, human_key, a7_key):
    s = DissentStore(tmp_path / "d.db", _write_pub(human_key, tmp_path / "h.pub"),
                     _write_pub(a7_key, tmp_path / "a.pub"), tmp_path / "anchor.json")
    with pytest.raises(DissentStoreError, match="outside"):
        s.initialize(("A7", a7_key))


def test_missing_store_is_human_review(tmp_path, store):
    s = DissentStore(tmp_path / "nope" / "nope.db", store.human_pubkey_path, store.a7_pubkey_path, store.anchor_path)
    assert decide(s).decision is Decision.HUMAN_REVIEW
    assert not (tmp_path / "nope" / "nope.db").exists()  # read path must not create it


def test_corrupt_store_is_human_review(store):
    store.path.write_bytes(b"this is not a sqlite database" * 100)
    assert decide(store).decision is Decision.HUMAN_REVIEW


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="chmod is not enforced for root")
def test_unreadable_store_is_human_review(store):
    os.chmod(store.path, 0)
    try:
        assert decide(store).decision is Decision.HUMAN_REVIEW
    finally:
        os.chmod(store.path, 0o600)


def test_store_that_raises_unexpectedly_is_human_review(store, monkeypatch):
    def boom():
        raise RuntimeError("disk on fire")
    monkeypatch.setattr(store, "open_dissents", boom)
    assert decide(store).decision is Decision.HUMAN_REVIEW


@pytest.mark.parametrize("missing", ["human_pubkey_path", "a7_pubkey_path", "anchor_path"])
def test_missing_key_or_anchor_config_is_human_review(store, missing):
    setattr(store, missing, None)
    assert decide(store).decision is Decision.HUMAN_REVIEW


# --- configuration --------------------------------------------------------

def test_require_store_env_with_no_store_is_human_review(monkeypatch):
    monkeypatch.delenv("SENTINEL_DISSENT_DB", raising=False)
    monkeypatch.setenv("SENTINEL_REQUIRE_DISSENT_STORE", "1")
    result = Sentinel().authorize(req())
    assert result.decision is Decision.HUMAN_REVIEW
    assert "not configured" in result.reason


def test_required_store_kwarg_not_configured_is_human_review(monkeypatch):
    monkeypatch.delenv("SENTINEL_DISSENT_DB", raising=False)
    assert Sentinel(require_dissent_store=True).authorize(req()).decision is Decision.HUMAN_REVIEW


def test_env_configures_store(monkeypatch, store, a7_key):
    file(store, a7_key)
    monkeypatch.setenv("SENTINEL_DISSENT_DB", str(store.path))
    monkeypatch.setenv("SENTINEL_HUMAN_PUBKEY", str(store.human_pubkey_path))
    monkeypatch.setenv("SENTINEL_A7_PUBKEY", str(store.a7_pubkey_path))
    monkeypatch.setenv("SENTINEL_DISSENT_ANCHOR", str(store.anchor_path))
    monkeypatch.setenv("SENTINEL_REQUIRE_DISSENT_STORE", "1")
    assert Sentinel().authorize(req()).decision is Decision.HUMAN_REVIEW
    assert Sentinel().authorize(req(scope=["elsewhere"], intent="read")).decision is Decision.AUTHORIZED


# --- CLI, keys and passphrases ---------------------------------------------

def _cli_env(tmp_path, monkeypatch):
    sec = tmp_path / "secrets"
    for name, val in {
        "SENTINEL_DISSENT_DB": sec / "db" / "dissent.db",
        "SENTINEL_DISSENT_ANCHOR": sec / "anchor" / "head.json",
        "SENTINEL_HUMAN_PUBKEY": sec / "keys" / "human_ed25519.pub",
        "SENTINEL_HUMAN_KEY": sec / "keys" / "human_ed25519",
        "SENTINEL_HUMAN_KEY_PASSPHRASE_FILE": sec / "human_key.passphrase",
        "SENTINEL_A7_PUBKEY": sec / "keys" / "a7_ed25519.pub",
        "SENTINEL_A7_KEY": sec / "keys" / "a7_ed25519",
    }.items():
        monkeypatch.setenv(name, str(val))
    return sec


def test_cli_full_flow_with_passphrase(tmp_path, monkeypatch, capsys):
    sec = _cli_env(tmp_path, monkeypatch)
    pf, hk, ak = sec / "human_key.passphrase", sec / "keys" / "human_ed25519", sec / "keys" / "a7_ed25519"
    assert dissent_cli.main(["gen-passphrase", "--out", str(pf)]) == 0
    assert dissent_cli.main(["keygen", "--out", str(hk), "--passphrase-file", str(pf)]) == 0
    assert dissent_cli.main(["keygen", "--out", str(ak), "--unencrypted"]) == 0
    printed = capsys.readouterr().out
    passphrase = pf.read_text().strip()
    assert len(passphrase) >= 40 and passphrase not in printed and "PRIVATE KEY" not in printed
    for p in (pf, hk, ak):
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert b"ENCRYPTED PRIVATE KEY" in hk.read_bytes()
    with pytest.raises(DissentStoreError):
        load_private_key(hk)  # no passphrase -> cannot load
    assert dissent_cli.main(["init"]) == 0
    assert dissent_cli.main(["add-dissent", "--id", "D-1", "--target", "prod", "--reason", "r"]) == 0
    store = DissentStore.from_env()
    assert decide(store).decision is Decision.HUMAN_REVIEW
    assert dissent_cli.main(["clear", "--id", "D-1", "--human", "theodore", "--reason", "accepted"]) == 0
    assert decide(store).decision is Decision.AUTHORIZED
    assert dissent_cli.main(["status"]) == 0
    assert passphrase not in capsys.readouterr().out


def test_cli_clear_wrong_passphrase_fails_and_dissent_stays_open(tmp_path, monkeypatch, capsys):
    sec = _cli_env(tmp_path, monkeypatch)
    pf, hk, ak = sec / "human_key.passphrase", sec / "keys" / "human_ed25519", sec / "keys" / "a7_ed25519"
    dissent_cli.main(["gen-passphrase", "--out", str(pf)])
    dissent_cli.main(["keygen", "--out", str(hk), "--passphrase-file", str(pf)])
    dissent_cli.main(["keygen", "--out", str(ak), "--unencrypted"])
    dissent_cli.main(["init"])
    dissent_cli.main(["add-dissent", "--id", "D-1", "--target", "prod", "--reason", "r"])
    monkeypatch.delenv("SENTINEL_HUMAN_KEY_PASSPHRASE_FILE")
    monkeypatch.setattr(dissent_cli.getpass, "getpass", lambda prompt="": "wrong passphrase")
    assert dissent_cli.main(["clear", "--id", "D-1", "--human", "t", "--reason", "x"]) == 1
    monkeypatch.setattr(dissent_cli.getpass, "getpass", lambda prompt="": pf.read_text().strip())
    assert decide(DissentStore.from_env()).decision is Decision.HUMAN_REVIEW
    assert dissent_cli.main(["clear", "--id", "D-1", "--human", "t", "--reason", "x"]) == 0  # prompt path
    assert decide(DissentStore.from_env()).decision is Decision.AUTHORIZED


def test_cli_refuses_overwrite_and_world_readable_passphrase(tmp_path):
    pf = tmp_path / "p"
    assert dissent_cli.main(["gen-passphrase", "--out", str(pf)]) == 0
    assert dissent_cli.main(["gen-passphrase", "--out", str(pf)]) == 2
    os.chmod(pf, 0o644)
    assert dissent_cli.main(["keygen", "--out", str(tmp_path / "k"), "--passphrase-file", str(pf)]) == 1


# --- SPKI PEM + offline Magic openssl signing flow --------------------------

MAGIC_PUB_PEM = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MCowBQYDK2VwAyEAeiha/mcljXBJJNbhn9U4ppV7XEFVuyCPS1kz+g/pRsY=\n"
    "-----END PUBLIC KEY-----\n"
)


def test_spki_pem_magic_pubkey_parses_and_fingerprints(tmp_path):
    from dissent_store import load_public_key, public_key_info

    pub_file = tmp_path / "human_ed25519.magic.pub.pem"
    pub_file.write_text("\r\n  " + MAGIC_PUB_PEM.replace("\n", "\r\n") + "  \r\n", encoding="utf-8")
    key = load_public_key(pub_file)
    info = public_key_info(key)
    assert info["raw_hex"] == "7a285afe67258d704924d6e19fd538a6957b5c4155bb208f4b5933fa0fe946c6"
    assert info["raw_b64"] == "eiha/mcljXBJJNbhn9U4ppV7XEFVuyCPS1kz+g/pRsY="
    assert info["sha256_hex"] == "eff19af26c00ff02578c37b6264e1d9be77a56f4354026a2d93ddee632256605"
    assert info["fingerprint"] == "SHA256:7/Ga8mwA/wJXjDe2Jk4dm+d6VvQ1QCai2T3e5jIlZgU"


def test_non_ed25519_spki_pem_rejected(tmp_path):
    from cryptography.hazmat.primitives.asymmetric import rsa
    from dissent_store import load_public_key

    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    bad = tmp_path / "rsa.pub.pem"
    bad.write_bytes(rsa_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    with pytest.raises(DissentStoreError, match="not Ed25519"):
        load_public_key(bad)


def test_cli_pubkey_info_prints_magic_fingerprint(tmp_path, capsys):
    pub_file = tmp_path / "human_ed25519.magic.pub.pem"
    pub_file.write_text(MAGIC_PUB_PEM, encoding="utf-8")
    assert dissent_cli.main(["pubkey-info", "--pubkey", str(pub_file)]) == 0
    out = capsys.readouterr().out
    assert "eff19af26c00ff02578c37b6264e1d9be77a56f4354026a2d93ddee632256605" in out
    assert "SHA256:7/Ga8mwA/wJXjDe2Jk4dm+d6VvQ1QCai2T3e5jIlZgU" in out


def test_parse_receipt_payload_rejects_non_canonical_or_tampered():
    from dissent_store import parse_receipt_payload

    valid = receipt_payload("D-1", "a" * 64, "prod", "ok", "theodore", "2026-11-24T00:00:00Z")
    parsed = parse_receipt_payload(valid)
    assert parsed["dissent_id"] == "D-1"
    # Pretty-printed JSON has identical data but is non-canonical -> rejected
    pretty = json.dumps(json.loads(valid.decode("utf-8")), indent=2).encode("utf-8")
    with pytest.raises(DissentWriteRejected, match="canonical"):
        parse_receipt_payload(pretty)
    with pytest.raises(DissentWriteRejected):
        parse_receipt_payload(b'{"kind":"dissent"}')


def test_e2e_openssl_magic_signing_flow(tmp_path, monkeypatch, capsys):
    """End-to-end with real openssl commands matching Magic (Termux) + magic_sign_receipt.sh."""
    import base64
    import shutil
    import subprocess
    from pathlib import Path

    if not shutil.which("openssl"):
        pytest.skip("openssl binary not installed")

    sec = _cli_env(tmp_path, monkeypatch)
    # Remove box human private key & passphrase from env: human key lives ONLY offline (Magic).
    monkeypatch.delenv("SENTINEL_HUMAN_KEY")
    monkeypatch.delenv("SENTINEL_HUMAN_KEY_PASSPHRASE_FILE")

    magic_dir = tmp_path / "magic_home" / ".sentinel"
    magic_dir.mkdir(parents=True, mode=0o700)
    pass_file = magic_dir / "human_key.pass"
    priv_pem = magic_dir / "human_ed25519.pem"
    pub_pem = sec / "keys" / "human_ed25519.magic.pub.pem"
    pub_pem.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SENTINEL_HUMAN_PUBKEY", str(pub_pem))

    # Generate keypair using exact Magic Termux openssl commands
    subprocess.run(f"openssl rand -base64 24 > '{pass_file}' && chmod 600 '{pass_file}'",
                   shell=True, check=True)
    subprocess.run([
        "openssl", "genpkey", "-algorithm", "ed25519", "-aes-256-cbc",
        "-pass", f"file:{pass_file}", "-out", str(priv_pem),
    ], check=True)
    os.chmod(priv_pem, 0o600)
    subprocess.run([
        "openssl", "pkey", "-in", str(priv_pem), "-passin", f"file:{pass_file}",
        "-pubout", "-out", str(pub_pem),
    ], check=True)

    # A7 key on box initializes store and files dissent
    ak = sec / "keys" / "a7_ed25519"
    assert dissent_cli.main(["keygen", "--out", str(ak), "--unencrypted"]) == 0
    assert dissent_cli.main(["init"]) == 0
    assert dissent_cli.main(["add-dissent", "--id", "D-MAGIC-1", "--target", "prod", "--reason", "needs human signoff"]) == 0
    capsys.readouterr()

    store = DissentStore.from_env()
    assert decide(store).decision is Decision.HUMAN_REVIEW

    # 1. Box emits canonical receipt payload (short base64 + optional binary file)
    payload_bin = tmp_path / "payload.bin"
    assert dissent_cli.main([
        "receipt-payload", "D-MAGIC-1",
        "--human", "theodore", "--reason", "verified offline on Magic",
        "--out", str(payload_bin),
    ]) == 0
    payload_b64 = capsys.readouterr().out.strip()
    assert len(payload_b64) < 512
    assert base64.b64decode(payload_b64, validate=True) == payload_bin.read_bytes()

    # 2a. Sign directly with openssl pkeyutl -sign -rawin (exact prompt command)
    sig_bin = tmp_path / "sig.bin"
    subprocess.run([
        "openssl", "pkeyutl", "-sign", "-rawin",
        "-inkey", str(priv_pem), "-passin", f"file:{pass_file}",
        "-in", str(payload_bin), "-out", str(sig_bin),
    ], check=True)
    sig_raw_b64 = base64.b64encode(sig_bin.read_bytes()).decode("ascii")
    assert len(sig_raw_b64) == 88

    # 2b. Sign via magic_sign_receipt.sh reading base64 from stdin
    script_path = Path(__file__).resolve().parent.parent / "magic_sign_receipt.sh"
    res = subprocess.run(
        ["sh", str(script_path)],
        input=payload_b64 + "\n",
        text=True,
        capture_output=True,
        env={**os.environ, "SENTINEL_DIR": str(magic_dir)},
        check=True,
    )
    sig_script_b64 = res.stdout.strip()
    assert sig_script_b64 == sig_raw_b64

    # 3. Clear on box with --payload-b64 and --sig-b64 (no human private key on box!)
    assert dissent_cli.main(["clear", "--payload-b64", payload_b64, "--sig-b64", sig_script_b64]) == 0
    assert decide(store).decision is Decision.AUTHORIZED
    assert dissent_cli.main(["status"]) == 0


def test_offline_clear_with_ts_and_negative_cases(tmp_path, monkeypatch, capsys):
    import base64
    import subprocess
    import shutil

    if not shutil.which("openssl"):
        pytest.skip("openssl binary not installed")

    sec = _cli_env(tmp_path, monkeypatch)
    monkeypatch.delenv("SENTINEL_HUMAN_KEY")
    monkeypatch.delenv("SENTINEL_HUMAN_KEY_PASSPHRASE_FILE")

    priv_pem = tmp_path / "human.pem"
    pub_pem = sec / "keys" / "human_ed25519.magic.pub.pem"
    pub_pem.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SENTINEL_HUMAN_PUBKEY", str(pub_pem))
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(priv_pem)], check=True)
    subprocess.run(["openssl", "pkey", "-in", str(priv_pem), "-pubout", "-out", str(pub_pem)], check=True)

    ak = sec / "keys" / "a7_ed25519"
    dissent_cli.main(["keygen", "--out", str(ak), "--unencrypted"])
    dissent_cli.main(["init"])
    dissent_cli.main(["add-dissent", "--id", "D-1", "--target", "prod", "--reason", "r"])
    capsys.readouterr()

    ts = "2026-11-24T22:55:00.000000Z"
    payload_bin = tmp_path / "p.bin"
    assert dissent_cli.main([
        "receipt-payload", "--id", "D-1", "--human", "theodore", "--reason", "ok", "--ts", ts,
        "--out", str(payload_bin),
    ]) == 0
    payload_b64 = capsys.readouterr().out.strip()
    sig_bin = tmp_path / "s.bin"
    subprocess.run(["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(priv_pem),
                    "-in", str(payload_bin), "-out", str(sig_bin)], check=True)
    sig_b64 = base64.b64encode(sig_bin.read_bytes()).decode("ascii")

    # Wrong sig rejected
    bad_sig = base64.b64encode(b"\x00" * 64).decode("ascii")
    assert dissent_cli.main(["clear", "--payload-b64", payload_b64, "--sig-b64", bad_sig]) == 1
    # Mismatched reason vs payload-b64 rejected
    assert dissent_cli.main(["clear", "--payload-b64", payload_b64, "--sig-b64", sig_b64, "--reason", "other"]) == 1
    # Combining --sig-b64 with --key rejected
    assert dissent_cli.main(["clear", "--payload-b64", payload_b64, "--sig-b64", sig_b64, "--key", str(priv_pem)]) == 1
    # Missing --ts when --payload-b64 omitted rejected
    assert dissent_cli.main(["clear", "--id", "D-1", "--human", "theodore", "--reason", "ok", "--sig-b64", sig_b64]) == 1
    # Valid explicit --ts mode succeeds
    assert dissent_cli.main([
        "clear", "--id", "D-1", "--human", "theodore", "--reason", "ok", "--ts", ts, "--sig-b64", sig_b64,
    ]) == 0
    assert decide(DissentStore.from_env()).decision is Decision.AUTHORIZED


def test_wrong_openssl_key_rejected_by_real_magic_pubkey(tmp_path):
    import base64
    import shutil
    import subprocess

    if not shutil.which("openssl"):
        pytest.skip("openssl binary not installed")

    pub_pem = tmp_path / "magic.pub.pem"
    pub_pem.write_text(MAGIC_PUB_PEM, encoding="utf-8")
    wrong_priv = tmp_path / "wrong.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(wrong_priv)], check=True)

    a7 = Ed25519PrivateKey.generate()
    a7_pub = _write_pub(a7, tmp_path / "a7.pub")
    (tmp_path / "db").mkdir()
    (tmp_path / "anchor").mkdir()
    store = DissentStore(tmp_path / "db" / "dissent.db", pub_pem, a7_pub, tmp_path / "anchor" / "head.json")
    store.initialize(("A7", a7))
    file_protected_dissent(store, a7, dissent_id="D-REAL", target="prod", reason="hold")
    d = store.dissent("D-REAL")
    ts = "2026-11-24T22:55:00.000000Z"
    p_bin = tmp_path / "p.bin"
    p_bin.write_bytes(receipt_payload(d.dissent_id, d.row_hash, d.target, "ok", "theodore", ts))
    s_bin = tmp_path / "s.bin"
    subprocess.run(["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(wrong_priv),
                    "-in", str(p_bin), "-out", str(s_bin)], check=True)
    sig_b64 = base64.b64encode(s_bin.read_bytes()).decode("ascii")
    with pytest.raises(DissentWriteRejected, match="does not verify"):
        store.append_receipt(dissent_id="D-REAL", author="theodore", reason="ok", ts=ts,
                             signature_b64=sig_b64, anchor_signer=("A7", a7))


# --- integrity hardening follow-ups ---------------------------------------

def test_duplicate_dissent_ids_are_rejected_even_if_unique_index_is_dropped(store, a7_key):
    file(store, a7_key, "D-1", target="prod", reason="first")
    second = {
        "kind": "dissent", "dissent_id": "D-1", "target": "billing",
        "reason": "second", "author": "A7", "ts": "2026-11-27T00:00:00Z",
        "dissent_row_hash": "",
        "signature": sign_b64(a7_key, dissent_payload(
            "D-1", "billing", "second", "A7", "2026-11-27T00:00:00Z")),
    }
    rows = rows_of(store) + [second]
    with raw(store) as c:
        c.execute("DROP INDEX dissent_log_one_dissent_per_id")
    rewrite_chain(store, rows)
    result = decide(store)
    assert result.decision is Decision.HUMAN_REVIEW
    assert "duplicate dissent ID" in result.reason


def test_anchor_update_happens_while_sqlite_writer_lock_is_held(store, a7_key, monkeypatch):
    original = store._write_anchor

    def assert_writer_lock_then_write(count, head, signer):
        probe = sqlite3.connect(store.path, timeout=0)
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                probe.execute("BEGIN IMMEDIATE")
        finally:
            probe.close()
        original(count, head, signer)

    monkeypatch.setattr(store, "_write_anchor", assert_writer_lock_then_write)
    file(store, a7_key, "D-LOCK")
    assert store.head()[0] == 1


@pytest.mark.xfail(strict=True, reason="requires an independent monotonic witness; local db+anchor rollback is not detectable")
def test_restoring_database_and_matching_old_anchor_is_rejected(store, a7_key, tmp_path):
    import shutil

    old_db = tmp_path / "old.db"
    old_anchor = tmp_path / "old-anchor.json"
    shutil.copy2(store.path, old_db)
    shutil.copy2(store.anchor_path, old_anchor)
    file(store, a7_key, "D-ROLLBACK")
    assert decide(store).decision is Decision.HUMAN_REVIEW
    shutil.copy2(old_db, store.path)
    shutil.copy2(old_anchor, store.anchor_path)
    result = decide(store)
    assert result.decision is Decision.HUMAN_REVIEW


# --- independent monotonic witness ----------------------------------------

class FakeMonotonicWitness:
    def __init__(self):
        self.seq = 0
        self.head_hash = GENESIS_HASH
        self.fail_next = False

    def assert_matches(self, seq, head_hash):
        if (seq, head_hash) != (self.seq, self.head_hash):
            raise DissentStoreError("local state differs from independent witness")

    def advance(self, row):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("simulated witness transport failure")
        if row["seq"] == self.seq and row["row_hash"] == self.head_hash:
            return {"seq": self.seq, "head_hash": self.head_hash}
        if row["seq"] != self.seq + 1 or row["prev_hash"] != self.head_hash:
            raise DissentStoreError("stale or forked advancement")
        self.seq = row["seq"]
        self.head_hash = row["row_hash"]
        return {"seq": self.seq, "head_hash": self.head_hash}


def test_independent_witness_detects_paired_database_and_anchor_rollback(store, a7_key):
    import shutil

    witness = FakeMonotonicWitness()
    witnessed = DissentStore(
        store.path, store.human_pubkey_path, store.a7_pubkey_path, store.anchor_path,
        witness=witness, require_witness=True,
    )
    old_db = store.path.parent / "before-witness.db"
    old_anchor = store.anchor_path.parent / "before-witness-anchor.json"
    shutil.copy2(store.path, old_db)
    shutil.copy2(store.anchor_path, old_anchor)

    file_protected_dissent(witnessed, a7_key, dissent_id="D-WITNESS", target="prod", reason="rollback test")
    assert witness.seq == 1
    assert decide(witnessed).decision is Decision.HUMAN_REVIEW

    shutil.copy2(old_db, store.path)
    shutil.copy2(old_anchor, store.anchor_path)
    result = decide(witnessed)
    assert result.decision is Decision.HUMAN_REVIEW
    assert "witness" in result.reason.lower()


def test_required_witness_missing_fails_closed(store):
    required = DissentStore(
        store.path, store.human_pubkey_path, store.a7_pubkey_path, store.anchor_path,
        require_witness=True,
    )
    result = decide(required)
    assert result.decision is Decision.HUMAN_REVIEW
    assert "witness" in result.reason.lower()


def test_explicit_witness_sync_recovers_interrupted_append(store, a7_key):
    witness = FakeMonotonicWitness()
    witnessed = DissentStore(
        store.path, store.human_pubkey_path, store.a7_pubkey_path, store.anchor_path,
        witness=witness, require_witness=True,
    )
    witness.fail_next = True
    with pytest.raises(DissentStoreError, match="witness advancement failed"):
        file_protected_dissent(
            witnessed, a7_key, dissent_id="D-RETRY", target="prod", reason="interrupted witness call"
        )

    # The local transaction committed, but the remote witness did not. Authorization
    # remains HUMAN_REVIEW until the explicit operator reconciliation succeeds.
    assert witness.seq == 0
    assert decide(witnessed).decision is Decision.HUMAN_REVIEW
    count, head = witnessed.sync_witness()
    assert count == 1
    assert head == witness.head_hash
    assert witnessed.head() == (1, head)
