#!/usr/bin/env sh
set -eu

SENTINEL_DIR="${SENTINEL_DIR:-$HOME/.sentinel}"
KEY="${SENTINEL_HUMAN_KEY:-$SENTINEL_DIR/human_ed25519.pem}"
PASS="${SENTINEL_HUMAN_PASS:-$SENTINEL_DIR/human_key.pass}"

if [ ! -f "$KEY" ]; then
    echo "error: human private key not found: $KEY" >&2
    exit 1
fi

umask 077
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if [ -t 0 ]; then
    printf 'Paste payload base64, then press Enter and Ctrl-D:\n' >&2
fi

tr -d '[:space:]' | openssl base64 -d -A > "$WORK/payload.bin"
if [ ! -s "$WORK/payload.bin" ]; then
    echo "error: empty or invalid base64 payload on stdin" >&2
    exit 1
fi

if [ -f "$PASS" ]; then
    openssl pkeyutl -sign -rawin -inkey "$KEY" -passin "file:$PASS" -in "$WORK/payload.bin" -out "$WORK/sig.bin"
else
    openssl pkeyutl -sign -rawin -inkey "$KEY" -in "$WORK/payload.bin" -out "$WORK/sig.bin"
fi

openssl base64 -A -in "$WORK/sig.bin"
printf '\n'
