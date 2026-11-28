"""Operator CLI for the Sentinel dissent store (F34 fix).

Every option falls back to an environment variable (see sentinel.env):
  SENTINEL_DISSENT_DB, SENTINEL_DISSENT_ANCHOR, SENTINEL_HUMAN_PUBKEY, SENTINEL_A7_PUBKEY,
  SENTINEL_A7_KEY, SENTINEL_HUMAN_KEY, SENTINEL_HUMAN_KEY_PASSPHRASE_FILE

  python dissent_cli.py gen-passphrase --out ~/.sentinel/human_key.passphrase
  python dissent_cli.py keygen --out ~/.sentinel/human_ed25519 --passphrase-file ~/.sentinel/human_key.passphrase
  python dissent_cli.py keygen --out ~/.sentinel/a7_ed25519 --unencrypted
  python dissent_cli.py pubkey-info
  python dissent_cli.py init
  python dissent_cli.py add-dissent --id D-1 --target deploy-prod --reason "..."     (signed by A7)
  python dissent_cli.py status
  python dissent_cli.py receipt-payload D-1 --human theodore --reason "risk accepted"
  python dissent_cli.py clear --payload-b64 <B64> --sig-b64 <SIG_B64>
  python dissent_cli.py clear --id D-1 --human theodore --reason "risk accepted"     (local key)

Private keys are written 0600 and never printed. Passphrases are read from a
0600 file or an interactive getpass prompt, never from the command line.
Requires the `cryptography` package.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import getpass
import os
import secrets
import sys
from pathlib import Path

from dissent_store import (
    DissentStore, DissentStoreError, DissentWriteRejected, ENV_A7_PUBKEY, ENV_ANCHOR, ENV_DB, ENV_PUBKEY,
    clear_dissent, clear_dissent_signed, load_private_key, load_public_key, now_ts,
    parse_receipt_payload, public_key_info, receipt_payload,
)

ENV_A7_KEY = "SENTINEL_A7_KEY"
ENV_HUMAN_KEY = "SENTINEL_HUMAN_KEY"
ENV_HUMAN_PASSFILE = "SENTINEL_HUMAN_KEY_PASSPHRASE_FILE"


def _env(value, name):
    return value or os.environ.get(name)


def _decode_b64(text: str, label: str) -> bytes:
    cleaned = "".join(text.split())
    if not cleaned:
        raise DissentStoreError(f"{label} is empty")
    try:
        return base64.b64decode(cleaned, validate=True)
    except (binascii.Error, ValueError):
        raise DissentStoreError(f"{label} is not valid base64") from None


def _create_0600(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.chmod(path, 0o600)


def _read_passphrase_file(path) -> bytes:
    p = Path(path).expanduser()
    if os.name == "posix" and p.stat().st_mode & 0o077:
        raise DissentStoreError(f"passphrase file {p} is readable by others; chmod 600 it")
    data = p.read_bytes().strip()
    if not data:
        raise DissentStoreError("passphrase file is empty")
    return data


def _gen_passphrase(args) -> int:
    out = Path(args.out).expanduser()
    if out.exists():
        print(f"refusing to overwrite {out}", file=sys.stderr)
        return 2
    _create_0600(out, secrets.token_urlsafe(32).encode("ascii") + b"\n")
    print(f"passphrase written to {out} (0600, not shown)")
    return 0


def _keygen(args) -> int:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv_path = Path(args.out).expanduser()
    pub_path = priv_path.with_name(priv_path.name + ".pub")
    if priv_path.exists() or pub_path.exists():
        print(f"refusing to overwrite existing key at {priv_path}", file=sys.stderr)
        return 2
    if args.unencrypted:
        encryption = serialization.NoEncryption()
    else:
        if args.passphrase_file:
            passphrase = _read_passphrase_file(args.passphrase_file)
        else:
            passphrase = getpass.getpass("New key passphrase: ").encode()
            if passphrase != getpass.getpass("Repeat passphrase: ").encode() or len(passphrase) < 12:
                print("passphrases differ or are shorter than 12 characters", file=sys.stderr)
                return 2
        encryption = serialization.BestAvailableEncryption(passphrase)
    key = Ed25519PrivateKey.generate()
    _create_0600(priv_path, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, encryption))
    pub_path.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
                                                       serialization.PublicFormat.SubjectPublicKeyInfo))
    state = "unencrypted" if args.unencrypted else "passphrase-encrypted"
    print(f"private key: {priv_path} (0600, {state}, never commit)")
    print(f"public key:  {pub_path}")
    return 0


def _store(args) -> DissentStore:
    db = _env(args.db, ENV_DB)
    if not db:
        raise DissentStoreError(f"--db or {ENV_DB} is required")
    return DissentStore(db, _env(args.pubkey, ENV_PUBKEY), _env(args.a7_pubkey, ENV_A7_PUBKEY),
                        _env(args.anchor, ENV_ANCHOR))


def _a7_key(args):
    path = _env(args.a7_key, ENV_A7_KEY)
    if not path:
        raise DissentStoreError(f"--a7-key or {ENV_A7_KEY} is required")
    return load_private_key(path)


def _init(args) -> int:
    _store(args).initialize(("A7", _a7_key(args)))
    print("dissent store initialized and anchored")
    return 0


def _add(args) -> int:
    from aip001_council import file_protected_dissent

    h = file_protected_dissent(_store(args), _a7_key(args), dissent_id=args.id, target=args.target,
                               reason=args.reason, node_id=args.author)
    print(f"dissent {args.id} recorded, row_hash={h}")
    return 0


def _status(args) -> int:
    store = _store(args)
    count, head = store.head()
    print(f"chain, signatures, local anchor and independent witness OK: {count} rows, head={head}")
    for d in store.open_dissents():
        print(f"OPEN {d.dissent_id} target={d.target!r} by {d.author} at {d.ts}: {d.reason}")
    return 0


def _witness_sync(args) -> int:
    count, head = _store(args).sync_witness()
    print(f"independent witness reconciled to verified local chain: {count} rows, head={head}")
    return 0


def _witness_bootstrap_payload(args) -> int:
    payload = _store(args).create_witness_bootstrap_payload(
        human=args.human, reason=args.reason, ts=args.ts or now_ts(),
    )
    print(base64.b64encode(payload).decode("ascii"))
    return 0


def _witness_bootstrap(args) -> int:
    count, head = _store(args).bootstrap_witness(
        payload_b64=args.payload_b64, signature_b64=args.sig_b64,
    )
    print(f"independent witness bootstrapped from human-signed local chain: {count} rows, head={head}")
    return 0


def _pubkey_info(args) -> int:
    env_var = ENV_PUBKEY if args.role == "human" else ENV_A7_PUBKEY
    path = _env(args.pubkey, env_var)
    if not path:
        raise DissentStoreError(f"--pubkey or {env_var} is required")
    key = load_public_key(path)
    info = public_key_info(key)
    print(f"role={args.role} format=SPKI-PEM algorithm=Ed25519 path={path}")
    print(f"raw_hex={info['raw_hex']}")
    print(f"raw_b64={info['raw_b64']}")
    print(f"sha256_hex={info['sha256_hex']}")
    print(f"fingerprint={info['fingerprint']}")
    return 0


def _receipt_payload(args) -> int:
    if args.dissent_id and args.dissent_id_flag and args.dissent_id != args.dissent_id_flag:
        raise DissentStoreError("positional dissent_id and --id differ")
    dissent_id = args.dissent_id or args.dissent_id_flag
    if not dissent_id:
        raise DissentStoreError("dissent_id (or --id) is required")
    if not (args.human and args.reason and args.reason.strip()):
        raise DissentStoreError("--human and a non-empty --reason are required")
    store = _store(args)
    dissent = store.dissent(dissent_id)
    if dissent is None:
        raise DissentStoreError(f"no dissent {dissent_id!r}")
    if dissent_id not in {d.dissent_id for d in store.open_dissents()}:
        print(f"warning: dissent {dissent_id!r} is already cleared", file=sys.stderr)
    ts = args.ts or now_ts()
    payload = receipt_payload(dissent.dissent_id, dissent.row_hash, dissent.target, args.reason, args.human, ts)
    if args.out:
        out_path = Path(args.out).expanduser()
        out_path.write_bytes(payload)
        print(f"wrote {len(payload)} canonical bytes to {out_path}", file=sys.stderr)
    print(base64.b64encode(payload).decode("ascii"))
    return 0


def _clear(args) -> int:
    store = _store(args)
    if args.sig_b64:
        if args.key or args.passphrase_file:
            raise DissentStoreError("cannot combine --sig-b64 with --key or --passphrase-file")
        sig_bytes = _decode_b64(args.sig_b64, "--sig-b64")
        sig_b64 = base64.b64encode(sig_bytes).decode("ascii")
        if args.payload_b64:
            payload_bytes = _decode_b64(args.payload_b64, "--payload-b64")
            parsed = parse_receipt_payload(payload_bytes)
            for flag_name, flag_val, key_name in (
                ("--id", args.id, "dissent_id"),
                ("--human", args.human, "author"),
                ("--reason", args.reason, "reason"),
                ("--ts", args.ts, "ts"),
            ):
                if flag_val is not None and flag_val != parsed[key_name]:
                    raise DissentStoreError(f"{flag_name} does not match --payload-b64 {key_name}")
            dissent_id = parsed["dissent_id"]
            human = parsed["author"]
            reason = parsed["reason"]
            ts = parsed["ts"]
            dissent = store.dissent(dissent_id)
            if dissent is None:
                raise DissentWriteRejected(f"no dissent {dissent_id!r} to clear")
            if dissent.row_hash != parsed["dissent_row_hash"] or dissent.target != parsed["target"]:
                raise DissentWriteRejected("receipt payload does not match stored dissent row_hash or target")
        else:
            if not (args.id and args.human and args.reason and args.ts):
                raise DissentStoreError("--sig-b64 without --payload-b64 requires --id, --human, --reason, and --ts")
            dissent_id, human, reason, ts = args.id, args.human, args.reason, args.ts
        h = clear_dissent_signed(
            store, dissent_id=dissent_id, human=human, reason=reason, ts=ts,
            signature_b64=sig_b64, anchor_signer=("A7", _a7_key(args)),
        )
        print(f"dissent {dissent_id} cleared by signed human receipt, row_hash={h}")
        return 0

    if args.payload_b64 or args.ts:
        raise DissentStoreError("--payload-b64 and --ts require --sig-b64")
    if not (args.id and args.human and args.reason):
        raise DissentStoreError("--id, --human, and --reason are required")
    key_path = _env(args.key, ENV_HUMAN_KEY)
    if not key_path:
        raise DissentStoreError(f"--key or {ENV_HUMAN_KEY} (or --sig-b64) is required")
    pass_file = _env(args.passphrase_file, ENV_HUMAN_PASSFILE)
    passphrase = _read_passphrase_file(pass_file) if pass_file else getpass.getpass("Human key passphrase: ").encode()
    human_key = load_private_key(key_path, passphrase)
    h = clear_dissent(store, human_key, dissent_id=args.id, human=args.human, reason=args.reason)
    print(f"dissent {args.id} cleared by signed human receipt, row_hash={h}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen-passphrase", help="write a strong random passphrase to a 0600 file")
    g.add_argument("--out", required=True)
    g.set_defaults(fn=_gen_passphrase)
    k = sub.add_parser("keygen", help="create a dedicated Ed25519 keypair")
    k.add_argument("--out", required=True)
    mode = k.add_mutually_exclusive_group()
    mode.add_argument("--passphrase-file")
    mode.add_argument("--unencrypted", action="store_true", help="for the A7 service key only")
    k.set_defaults(fn=_keygen)
    pi = sub.add_parser("pubkey-info", help="validate an SPKI PEM Ed25519 public key and print its fingerprint")
    pi.add_argument("--pubkey", help="SPKI PEM public key path")
    pi.add_argument("--role", choices=("human", "a7"), default="human")
    pi.set_defaults(fn=_pubkey_info)
    for name, fn in (("init", _init), ("add-dissent", _add), ("status", _status),
                     ("witness-sync", _witness_sync),
                     ("witness-bootstrap-payload", _witness_bootstrap_payload),
                     ("witness-bootstrap", _witness_bootstrap),
                     ("receipt-payload", _receipt_payload), ("clear", _clear)):
        p = sub.add_parser(name)
        p.add_argument("--db")
        p.add_argument("--pubkey", help="human public key (SPKI PEM)")
        p.add_argument("--a7-pubkey")
        p.add_argument("--anchor")
        p.set_defaults(fn=fn)
        if name in ("init", "add-dissent", "clear"):
            p.add_argument("--a7-key")
        if name == "add-dissent":
            p.add_argument("--id", required=True)
            p.add_argument("--target", required=True, help="trace_id, intent, scope entry, or '*'")
            p.add_argument("--reason", required=True)
            p.add_argument("--author", default="A7")
        if name == "witness-bootstrap-payload":
            p.add_argument("--human", required=True)
            p.add_argument("--reason", required=True)
            p.add_argument("--ts", help="override UTC timestamp (defaults to now)")
        if name == "witness-bootstrap":
            p.add_argument("--payload-b64", required=True)
            p.add_argument("--sig-b64", required=True)
        if name == "receipt-payload":
            p.add_argument("dissent_id", nargs="?", help="dissent ID")
            p.add_argument("--id", dest="dissent_id_flag", help="dissent ID (alternative to positional)")
            p.add_argument("--human", default="theodore")
            p.add_argument("--reason", default="human review accepted")
            p.add_argument("--ts", help="override UTC timestamp (defaults to now)")
            p.add_argument("--out", help="optional file path for raw canonical payload bytes")
        if name == "clear":
            p.add_argument("--id")
            p.add_argument("--key", help="human private key (local mode)")
            p.add_argument("--passphrase-file")
            p.add_argument("--human")
            p.add_argument("--reason")
            p.add_argument("--ts", help="timestamp from receipt-payload (offline signature mode)")
            p.add_argument("--payload-b64", help="base64 canonical receipt payload from receipt-payload")
            p.add_argument("--sig-b64", help="base64 Ed25519 signature from offline human key")
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except DissentStoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
