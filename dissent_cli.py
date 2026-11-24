"""Operator CLI for the Sentinel dissent store (F34 fix).

Every option falls back to an environment variable (see sentinel.env):
  SENTINEL_DISSENT_DB, SENTINEL_DISSENT_ANCHOR, SENTINEL_HUMAN_PUBKEY, SENTINEL_A7_PUBKEY,
  SENTINEL_A7_KEY, SENTINEL_HUMAN_KEY, SENTINEL_HUMAN_KEY_PASSPHRASE_FILE

  python dissent_cli.py gen-passphrase --out ~/.sentinel/human_key.passphrase
  python dissent_cli.py keygen --out ~/.sentinel/human_ed25519 --passphrase-file ~/.sentinel/human_key.passphrase
  python dissent_cli.py keygen --out ~/.sentinel/a7_ed25519 --unencrypted
  python dissent_cli.py init
  python dissent_cli.py add-dissent --id D-1 --target deploy-prod --reason "..."     (signed by A7)
  python dissent_cli.py status
  python dissent_cli.py clear --id D-1 --human theodore --reason "risk accepted because ..."

Private keys are written 0600 and never printed. Passphrases are read from a
0600 file or an interactive getpass prompt, never from the command line.
Requires the `cryptography` package.
"""
from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys
from pathlib import Path

from dissent_store import (
    DissentStore, DissentStoreError, ENV_A7_PUBKEY, ENV_ANCHOR, ENV_DB, ENV_PUBKEY,
    clear_dissent, load_private_key,
)

ENV_A7_KEY = "SENTINEL_A7_KEY"
ENV_HUMAN_KEY = "SENTINEL_HUMAN_KEY"
ENV_HUMAN_PASSFILE = "SENTINEL_HUMAN_KEY_PASSPHRASE_FILE"


def _env(value, name):
    return value or os.environ.get(name)


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
    print(f"chain, signatures and anchor OK: {count} rows, head={head}")
    for d in store.open_dissents():
        print(f"OPEN {d.dissent_id} target={d.target!r} by {d.author} at {d.ts}: {d.reason}")
    return 0


def _clear(args) -> int:
    key_path = _env(args.key, ENV_HUMAN_KEY)
    if not key_path:
        raise DissentStoreError(f"--key or {ENV_HUMAN_KEY} is required")
    pass_file = _env(args.passphrase_file, ENV_HUMAN_PASSFILE)
    passphrase = _read_passphrase_file(pass_file) if pass_file else getpass.getpass("Human key passphrase: ").encode()
    human_key = load_private_key(key_path, passphrase)
    h = clear_dissent(_store(args), human_key, dissent_id=args.id, human=args.human, reason=args.reason)
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
    for name, fn in (("init", _init), ("add-dissent", _add), ("status", _status), ("clear", _clear)):
        p = sub.add_parser(name)
        p.add_argument("--db")
        p.add_argument("--pubkey", help="human public key")
        p.add_argument("--a7-pubkey")
        p.add_argument("--anchor")
        p.set_defaults(fn=fn)
        if name in ("init", "add-dissent"):
            p.add_argument("--a7-key")
        if name == "add-dissent":
            p.add_argument("--id", required=True)
            p.add_argument("--target", required=True, help="trace_id, intent, scope entry, or '*'")
            p.add_argument("--reason", required=True)
            p.add_argument("--author", default="A7")
        if name == "clear":
            p.add_argument("--id", required=True)
            p.add_argument("--key", help="human private key")
            p.add_argument("--passphrase-file")
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
