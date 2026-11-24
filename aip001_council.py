"""Canonical AIP-001 council identity contract.

This module defines identity and connection-state semantics only. It does not
connect nodes, attest credentials, grant authority, or claim availability.
"""
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType


class ConnectionState(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CONNECTED = "NOT_CONNECTED"
    DEGRADED = "DEGRADED"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class CouncilIdentity:
    node_id: str
    identity: str
    responsibility: str
    may_authorize: bool = False
    protected_dissent: bool = False


@dataclass(frozen=True)
class NodeAttestation:
    node_id: str
    state: ConnectionState = ConnectionState.NOT_CONNECTED
    authenticated: bool = False
    attestation_ref: str | None = None


_IDENTITIES = {
    "A1": CouncilIdentity("A1", "ChatGPT", "Orchestration and synthesis"),
    "A2": CouncilIdentity("A2", "Gemini", "Multimodal analysis and research"),
    "A3": CouncilIdentity("A3", "Claude", "Formal reasoning and specification review"),
    "A4": CouncilIdentity("A4", "Cloudflare Lee", "Cloud infrastructure and edge operations"),
    "A5": CouncilIdentity("A5", "Codex", "Repository engineering and verification"),
    "A6": CouncilIdentity("A6", "Kimi", "Long-context research and discovery"),
    "A7": CouncilIdentity(
        "A7", "Grok", "Adversarial review and independent dissent",
        may_authorize=False, protected_dissent=True,
    ),
}

AIP001_COUNCIL_IDENTITIES = MappingProxyType(_IDENTITIES)


def validate_identity(node_id: str, identity: str) -> bool:
    """Reject unknown IDs and identity substitutions."""
    expected = AIP001_COUNCIL_IDENTITIES.get(node_id)
    return expected is not None and expected.identity == identity


def is_routeable(attestation: NodeAttestation) -> bool:
    """A node is routable only after direct authenticated attestation."""
    return (
        attestation.node_id in AIP001_COUNCIL_IDENTITIES
        and attestation.state is ConnectionState.AVAILABLE
        and attestation.authenticated
        and bool(attestation.attestation_ref)
    )


def may_authorize(node_id: str) -> bool:
    """Council membership never confers operational authorization."""
    identity = AIP001_COUNCIL_IDENTITIES.get(node_id)
    return bool(identity and identity.may_authorize)


def may_file_protected_dissent(node_id: str) -> bool:
    """Only a council node flagged protected_dissent (A7) may write to the dissent store.

    This checks the declared author string only; it does not authenticate the
    writer. Filing a dissent can only add blocks, never remove them.
    """
    identity = AIP001_COUNCIL_IDENTITIES.get(node_id) if isinstance(node_id, str) else None
    return bool(identity and identity.protected_dissent)


def load_a7_signing_key(path: str | None = None):
    """Load A7's Ed25519 private key (default path: $SENTINEL_A7_KEY)."""
    import os
    from dissent_store import DissentStoreError, load_private_key

    path = path or os.environ.get("SENTINEL_A7_KEY")
    if not path:
        raise DissentStoreError("no A7 signing key configured (SENTINEL_A7_KEY)")
    return load_private_key(path)


def file_protected_dissent(store, a7_signing_key, *, dissent_id: str, target: str, reason: str,
                           node_id: str = "A7") -> str:
    """A7 files a protected dissent: signed with the A7 key, appended to the store,
    and the new head anchor signed by A7. Returns the new row hash."""
    from dissent_store import DissentWriteRejected, dissent_payload, now_ts, sign_b64

    if not may_file_protected_dissent(node_id):
        raise DissentWriteRejected(f"council node {node_id!r} may not file a protected dissent")
    ts = now_ts()
    signature = sign_b64(a7_signing_key, dissent_payload(dissent_id, target, reason, node_id, ts))
    return store.append_dissent(author=node_id, dissent_id=dissent_id, target=target, reason=reason,
                                ts=ts, signature_b64=signature, anchor_signer=("A7", a7_signing_key))
