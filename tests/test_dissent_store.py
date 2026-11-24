"""Regression tests for F34: protected A7 dissent can no longer be bypassed by omitting its ID."""
import base64
import os
import sqlite3
import stat

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import dissent_cli
from dissent_store import DissentStore, DissentStoreError, DissentWriteRejected, receipt_payload
from sentinel import ActionRequest, Decision, HumanApproval, Sentinel


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
def store(tmp_path, human_key):
    s = DissentStore(tmp_path / "dissent.db", _write_pub(human_key, tmp_path / "human.pub"))
    s.initialize()
    return s


def sign_receipt(store, key, dissent_id, human="theodore", reason="risk accepted", ts="2026-11-24T06:00:00Z"):
    d = store.dissent(dissent_id)
    payload = receipt_payload(d.dissent_id, d.row_hash, d.target, reason, human, ts)
    return dict(dissent_id=dissent_id, author=human, reason=reason, ts=ts,
                signature_b64=base64.b64encode(key.sign(payload)).decode())


def raw(store):
    return sqlite3.connect(store.path)


# --- the bypass itself ----------------------------------------------------

def test_omitted_dissent_id_with_open_dissent_is_human_review(store):
    store.append_dissent(author="A7", dissent_id="D-1", target="prod", reason="unsafe rollout")
    result = Sentinel(dissent_store=store).authorize(req())  # no protected_dissent_id supplied
    assert result.decision is Decision.HUMAN_REVIEW
    assert "D-1" in result.reason


def test_dissent_matches_trace_intent_scope_or_wildcard(store):
    store.append_dissent(author="A7", dissent_id="D-int", target="deploy", reason="r")
    assert Sentinel(dissent_store=store).authorize(req(scope=["other"])).decision is Decision.HUMAN_REVIEW


def test_wildcard_dissent_blocks_everything(store):
    store.append_dissent(author="A7", dissent_id="D-all", target="*", reason="freeze")
    assert Sentinel(dissent_store=store).authorize(req(intent="x", scope=["y"])).decision is Decision.HUMAN_REVIEW


def test_unrelated_dissent_does_not_block(store):
    store.append_dissent(author="A7", dissent_id="D-9", target="billing", reason="r")
    assert Sentinel(dissent_store=store).authorize(req()).decision is Decision.AUTHORIZED


def test_human_approval_envelope_cannot_bypass_store_dissent(store):
    store.append_dissent(author="A7", dissent_id="D-1", target="prod", reason="r")
    request = req(protected_dissent_node="A7", protected_dissent_id="D-1")
    approval = HumanApproval("a", "h", request.trace_id, request.intent, tuple(request.scope), "2099", "sig", "D-1", "ok")
    sentinel = Sentinel(dissent_store=store, human_approval_verifier=lambda g, a: True)
    assert sentinel.authorize(request, human_approval=approval).decision is Decision.HUMAN_REVIEW


def test_hint_for_unknown_dissent_fails_closed(store):
    request = req(protected_dissent_node="A7", protected_dissent_id="D-ghost")
    assert Sentinel(dissent_store=store).authorize(request).decision is Decision.HUMAN_REVIEW


# --- risk labels (PR #17 behavior kept) -----------------------------------

def test_odd_case_risk_label_with_store_still_human_review(store):
    for label in ("High", "HIGH", " Critical "):
        assert Sentinel(dissent_store=store).authorize(req(risk=label)).decision is Decision.HUMAN_REVIEW


def test_unknown_risk_label_with_store_never_authorizes(store):
    for label in ("severe", "", None, "lowish"):
        assert Sentinel(dissent_store=store).authorize(req(risk=label)).decision is not Decision.AUTHORIZED


# --- writers ----------------------------------------------------------------

@pytest.mark.parametrize("author", ["A1", "A3", "Grok", "a7", "", "sentinel"])
def test_non_a7_dissent_write_rejected(store, author):
    with pytest.raises(DissentWriteRejected):
        store.append_dissent(author=author, dissent_id="D-x", target="prod", reason="r")
    assert store.head()[0] == 0


def test_duplicate_dissent_id_rejected(store):
    store.append_dissent(author="A7", dissent_id="D-1", target="prod", reason="r")
    with pytest.raises(DissentWriteRejected):
        store.append_dissent(author="A7", dissent_id="D-1", target="other", reason="r")


def test_receipt_with_wrong_key_does_not_clear(store):
    store.append_dissent(author="A7", dissent_id="D-1", target="prod", reason="r")
    with pytest.raises(DissentWriteRejected):
        store.append_receipt(**sign_receipt(store, Ed25519PrivateKey.generate(), "D-1"))
    assert Sentinel(dissent_store=store).authorize(req()).decision is Decision.HUMAN_REVIEW


def test_forged_receipt_inserted_directly_fails_closed(store):
    """A bad-signature receipt smuggled in with a correct hash chain still fails closed."""
    from dissent_store import compute_row_hash
    store.append_dissent(author="A7", dissent_id="D-1", target="prod", reason="r")
    d = store.dissent("D-1")
    good = sign_receipt(store, Ed25519PrivateKey.generate(), "D-1")
    row = {"seq": 2, "kind": "receipt", "dissent_id": "D-1", "target": d.target, "reason": good["reason"],
           "author": good["author"], "ts": good["ts"], "dissent_row_hash": d.row_hash,
           "signature": good["signature_b64"], "prev_hash": d.row_hash}
    row["row_hash"] = compute_row_hash(row, d.row_hash)
    with raw(store) as c:
        c.execute("INSERT INTO dissent_log VALUES (:seq,:kind,:dissent_id,:target,:reason,:author,:ts,"
                  ":dissent_row_hash,:signature,:prev_hash,:row_hash)", row)
    result = Sentinel(dissent_store=store).authorize(req())
    assert result.decision is Decision.HUMAN_REVIEW
    assert "invalid human signature" in result.reason


def test_valid_receipt_clears_and_request_authorizes(store, human_key):
    store.append_dissent(author="A7", dissent_id="D-1", target="prod", reason="r")
    store.append_receipt(**sign_receipt(store, human_key, "D-1"))
    assert store.open_dissents() == []
    assert Sentinel(dissent_store=store).authorize(req()).decision is Decision.AUTHORIZED
    hinted = req(protected_dissent_node="A7", protected_dissent_id="D-1")
    assert Sentinel(dissent_store=store).authorize(hinted).decision is Decision.AUTHORIZED


def test_receipt_cannot_be_replayed_onto_another_dissent(store, human_key):
    store.append_dissent(author="A7", dissent_id="D-1", target="prod", reason="r")
    store.append_dissent(author="A7", dissent_id="D-2", target="prod", reason="r")
    receipt = sign_receipt(store, human_key, "D-1")
    receipt["dissent_id"] = "D-2"
    with pytest.raises(DissentWriteRejected):
        store.append_receipt(**receipt)


# --- tamper / integrity ------------------------------------------------------

def test_triggers_block_update_and_delete(store):
    store.append_dissent(author="A7", dissent_id="D-1", target="prod", reason="r")
    with raw(store) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("UPDATE dissent_log SET target='nothing'")
    with raw(store) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute("DELETE FROM dissent_log")


def test_tampered_row_after_dropping_triggers_is_human_review(store):
    store.append_dissent(author="A7", dissent_id="D-1", target="prod", reason="r")
    with raw(store) as c:
        c.execute("DROP TRIGGER dissent_log_no_update")
        c.execute("UPDATE dissent_log SET target='nothing-real' WHERE dissent_id='D-1'")
        # restore the trigger so only the chain can catch it
        c.execute("CREATE TRIGGER dissent_log_no_update BEFORE UPDATE ON dissent_log "
                  "BEGIN SELECT RAISE(ABORT, 'dissent_log is append-only'); END")
    result = Sentinel(dissent_store=store).authorize(req())
    assert result.decision is Decision.HUMAN_REVIEW
    assert "hash chain broken" in result.reason


def test_dropped_triggers_alone_fail_closed(store):
    with raw(store) as c:
        c.execute("DROP TRIGGER dissent_log_no_delete")
    assert Sentinel(dissent_store=store).authorize(req()).decision is Decision.HUMAN_REVIEW


def test_deleted_row_breaks_chain_is_human_review(store):
    store.append_dissent(author="A7", dissent_id="D-0", target="billing", reason="r")
    store.append_dissent(author="A7", dissent_id="D-1", target="prod", reason="r")
    store.append_dissent(author="A7", dissent_id="D-2", target="billing", reason="r")
    with raw(store) as c:
        c.execute("DROP TRIGGER dissent_log_no_delete")
        c.execute("DELETE FROM dissent_log WHERE dissent_id='D-1'")
        c.execute("CREATE TRIGGER dissent_log_no_delete BEFORE DELETE ON dissent_log "
                  "BEGIN SELECT RAISE(ABORT, 'dissent_log is append-only'); END")
    assert Sentinel(dissent_store=store).authorize(req()).decision is Decision.HUMAN_REVIEW


def test_deleted_row_with_seq_renumbered_still_breaks_chain(store):
    store.append_dissent(author="A7", dissent_id="D-1", target="prod", reason="r")
    store.append_dissent(author="A7", dissent_id="D-2", target="billing", reason="r")
    with raw(store) as c:
        c.execute("DROP TRIGGER dissent_log_no_delete")
        c.execute("DROP TRIGGER dissent_log_no_update")
        c.execute("DELETE FROM dissent_log WHERE seq=1")
        c.execute("UPDATE dissent_log SET seq=1 WHERE seq=2")
        c.executescript("""
            CREATE TRIGGER dissent_log_no_update BEFORE UPDATE ON dissent_log BEGIN SELECT RAISE(ABORT,'x'); END;
            CREATE TRIGGER dissent_log_no_delete BEFORE DELETE ON dissent_log BEGIN SELECT RAISE(ABORT,'x'); END;""")
    assert Sentinel(dissent_store=store).authorize(req()).decision is Decision.HUMAN_REVIEW


def test_missing_store_is_human_review(tmp_path, human_key):
    s = DissentStore(tmp_path / "nope.db", _write_pub(human_key, tmp_path / "h.pub"))
    assert Sentinel(dissent_store=s).authorize(req()).decision is Decision.HUMAN_REVIEW
    assert not (tmp_path / "nope.db").exists()  # read path must not create it


def test_corrupt_store_is_human_review(store):
    store.path.write_bytes(b"this is not a sqlite database" * 100)
    assert Sentinel(dissent_store=store).authorize(req()).decision is Decision.HUMAN_REVIEW


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="chmod is not enforced for root")
def test_unreadable_store_is_human_review(store):
    os.chmod(store.path, 0)
    try:
        assert Sentinel(dissent_store=store).authorize(req()).decision is Decision.HUMAN_REVIEW
    finally:
        os.chmod(store.path, 0o600)


def test_store_that_raises_unexpectedly_is_human_review(store, monkeypatch):
    def boom():
        raise RuntimeError("disk on fire")
    monkeypatch.setattr(store, "open_dissents", boom)
    assert Sentinel(dissent_store=store).authorize(req()).decision is Decision.HUMAN_REVIEW


def test_missing_human_pubkey_is_human_review(tmp_path):
    s = DissentStore(tmp_path / "d.db", None)
    s.initialize()
    assert Sentinel(dissent_store=s).authorize(req()).decision is Decision.HUMAN_REVIEW


def test_required_store_not_configured_is_human_review(monkeypatch):
    monkeypatch.delenv("SENTINEL_DISSENT_DB", raising=False)
    assert Sentinel(require_dissent_store=True).authorize(req()).decision is Decision.HUMAN_REVIEW


def test_env_configures_store(monkeypatch, store):
    store.append_dissent(author="A7", dissent_id="D-1", target="prod", reason="r")
    monkeypatch.setenv("SENTINEL_DISSENT_DB", str(store.path))
    monkeypatch.setenv("SENTINEL_HUMAN_PUBKEY", str(store.human_pubkey_path))
    assert Sentinel().authorize(req()).decision is Decision.HUMAN_REVIEW


# --- CLI --------------------------------------------------------------------

def test_cli_keygen_writes_0600_key_and_never_prints_it(tmp_path, capsys):
    out = tmp_path / "keys" / "human_ed25519"
    assert dissent_cli.main(["keygen", "--out", str(out)]) == 0
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    printed = capsys.readouterr().out
    assert "PRIVATE KEY" not in printed and out.read_text().splitlines()[1] not in printed
    assert dissent_cli.main(["keygen", "--out", str(out)]) == 2  # refuses to overwrite


def test_cli_end_to_end_clear(tmp_path):
    key, db = tmp_path / "k", tmp_path / "d.db"
    assert dissent_cli.main(["keygen", "--out", str(key)]) == 0
    common = ["--db", str(db), "--pubkey", f"{key}.pub"]
    assert dissent_cli.main(["init", *common]) == 0
    assert dissent_cli.main(["add-dissent", *common, "--id", "D-1", "--target", "prod", "--reason", "r"]) == 0
    s = DissentStore(db, f"{key}.pub")
    assert Sentinel(dissent_store=s).authorize(req()).decision is Decision.HUMAN_REVIEW
    assert dissent_cli.main(["clear", *common, "--key", str(key), "--id", "D-1",
                             "--human", "theodore", "--reason", "accepted"]) == 0
    assert Sentinel(dissent_store=s).authorize(req()).decision is Decision.AUTHORIZED
    assert dissent_cli.main(["status", *common]) == 0
