"""Generate the dedicated Ed25519 keypair used only by the Cloudflare dissent witness."""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-out", required=True, help="0600 file for base64 PKCS#8 DER; upload only to Cloudflare")
    parser.add_argument("--public-out", required=True, help="PEM public key installed on the Sentinel host")
    args = parser.parse_args(argv)
    private_path = Path(args.private_out).expanduser()
    public_path = Path(args.public_out).expanduser()
    if private_path.exists() or public_path.exists():
        print("refusing to overwrite an existing witness key file", file=sys.stderr)
        return 2

    key = Ed25519PrivateKey.generate()
    private_der = key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(base64.b64encode(private_der) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    fd = os.open(public_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as handle:
        handle.write(public_pem)
        handle.flush()
        os.fsync(handle.fileno())

    print(f"Cloudflare-only private key file: {private_path} (0600)")
    print(f"Sentinel verification public key: {public_path}")
    print("Do not copy the private key to Sentinel, A7, source control, or chat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
