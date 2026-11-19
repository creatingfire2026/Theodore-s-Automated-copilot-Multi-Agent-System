from aip001_council import (
    AIP001_COUNCIL_IDENTITIES,
    ConnectionState,
    NodeAttestation,
    is_routeable,
    may_authorize,
    validate_identity,
)


def test_exactly_seven_independent_council_identities_are_defined():
    assert list(AIP001_COUNCIL_IDENTITIES) == ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]
    assert [x.identity for x in AIP001_COUNCIL_IDENTITIES.values()] == [
        "ChatGPT", "Gemini", "Claude", "Cloudflare Lee", "Codex", "Kimi", "Grok"
    ]


def test_identity_substitution_is_rejected():
    assert validate_identity("A7", "Grok")
    assert not validate_identity("A7", "Claude")
    assert not validate_identity("A8", "Other")


def test_nodes_default_to_not_connected_and_are_not_routeable():
    for node_id in AIP001_COUNCIL_IDENTITIES:
        attestation = NodeAttestation(node_id)
        assert attestation.state is ConnectionState.NOT_CONNECTED
        assert not is_routeable(attestation)


def test_available_without_direct_attestation_is_not_routeable():
    assert not is_routeable(
        NodeAttestation("A2", ConnectionState.AVAILABLE, True, None)
    )
    assert not is_routeable(
        NodeAttestation("A2", ConnectionState.AVAILABLE, False, "attestation-1")
    )


def test_route_requires_available_authenticated_attestation_reference():
    assert is_routeable(
        NodeAttestation("A2", ConnectionState.AVAILABLE, True, "attestation-1")
    )


def test_council_nodes_never_receive_authority_and_grok_dissent_is_protected():
    assert all(not may_authorize(node_id) for node_id in AIP001_COUNCIL_IDENTITIES)
    assert AIP001_COUNCIL_IDENTITIES["A7"].protected_dissent
