"""Operator CLI for the Sentinel dissent store (F34 fix).

  python dissent_cli.py keygen --out ~/.sentinel/human_ed25519
  python dissent_cli.py init --db sentinel_dissent.db
  python dissent_cli.py add-dissent --db sentinel_dissent.db --id D-1 --target deploy-prod --reason "..."
  python dissent_cli.py status --db sentinel_dissent.db --pubkey ~/.sentinel/human_ed25519.pub
  python dissent_cli.py clear --db sentinel_dissent.db --pubkey ~/.sentinel/human_ed25519.pub \
      --key ~/.sentinel/human_ed25519 --id D-1 --human theodore --reason "risk accepted because ..."

The private key is written with 0600 permissions and is never printed.
Requires the `cryptography` package.
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dissent_store import DissentStore, DissentStoreError, ENV_DB, ENV_PUBKEY, receipt_payload


def _keygen(args) -> int:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    priv_path = Path(args.out).expanduser()
    pub_path = priv_path.with_name(priv_path.name + ".pub")
    if priv_path.exists() or pub_path.exists():
        print(f"refusing to overwrite existing key at {priv_path}", file=sys.stderr)
        return 2
    priv_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    fd = os.open(priv_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(pem)
    os.chmod(priv_path, 0o600)
    pub_path.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
                                                       serialization.PublicFormat.SubjectPublicKeyInfo))
    print(f"private key: {priv_path} (0600, keep secret, never commit)")
    print(f"public key:  {pub_path} (set {ENV_PUBKEY} to this path)")
    return 0


def _load_private_key(path: str):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    p = Path(path).expanduser()
    if os.name == "posix" and p.stat().st_mode & 0o077:
        raise SystemExit(f"private key {p} is readable by others; run: chmod 600 {p}")
    key = load_pem_private_key(p.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("private key is not Ed25519")
    return key


def _store(args) -> DissentStore:
    db = args.db or os.environ.get(ENV_DB)
    if not db:
        raise SystemExit(f"--db or {ENV_DB} is required")
    return DissentStore(db, getattr(args, "pubkey", None) or os.environ.get(ENV_PUBKEY))


def _init(args) -> int:
    _store(args).initialize()
    print("dissent store initialized")
    return 0


def _add(args) -> int:
    h = _store(args).append_dissent(author=args.author, dissent_id=args.id, target=args.target, reason=args.reason)
    print(f"dissent {args.id} recorded, row_hash={h}")
    return 0


def _status(args) -> int:
    store = _store(args)
    count, head = store.head()
    print(f"chain OK: {count} rows, head={head}")
    for d in store.open_dissents():
        print(f"OPEN {d.dissent_id} target={d.target!r} by {d.author} at {d.ts}: {d.reason}")
    return 0


def _clear(args) -> int:
    store = _store(args)
    dissent = store.dissent(args.id)
    if dissent is None:
        raise SystemExit(f"no dissent {args.id!r}")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    payload = receipt_payload(dissent.dissent_id, dissent.row_hash, dissent.target, args.reason, args.human, ts)
    sig = base64.b64encode(_load_private_key(args.key).sign(payload)).decode("ascii")
    h = store.append_receipt(dissent_id=args.id, author=args.human, reason=args.reason, ts=ts, signature_b64=sig)
    print(f"dissent {args.id} cleared by signed receipt, row_hash={h}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen", help="create a dedicated Ed25519 human keypair")
    k.add_argument("--out", required=True)
    k.set_defaults(fn=_keygen)
    for name, fn in (("init", _init), ("add-dissent", _add), ("status", _status), ("clear", _clear)):
        p = sub.add_parser(name)
        p.add_argument("--db")
        p.add_argument("--pubkey")
        p.set_defaults(fn=fn)
        if name == "add-dissent":
            p.add_argument("--id", required=True)
            p.add_argument("--target", required=True, help="trace_id, intent, scope entry, or '*'")
            p.add_argument("--reason", required=True)
            p.add_argument("--author", default="A7")
        if name == "clear":
            p.add_argument("--id", required=True)
            p.add_argument("--key", required=True, help="path to the human private key")
            p.add_argument("--human", required=True)
            p.add_argument("--reason", required=True)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except DissentStoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
