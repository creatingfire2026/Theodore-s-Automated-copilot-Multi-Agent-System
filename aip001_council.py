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
