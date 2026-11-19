import logging

from sentinel import ActionRequest, Decision, Sentinel, TestResult


def req(**kw):
    kw.setdefault("aud", "sentinel")
    return ActionRequest("agent", "test", ["demo"], kw.pop("authority", "policy"), **kw)


def test_low_risk_authorizes():
    assert Sentinel().authorize(req()).decision is Decision.AUTHORIZED


def test_high_risk_requires_human():
    assert Sentinel().authorize(req(risk="high")).decision is Decision.HUMAN_REVIEW


def test_high_risk_can_be_approved():
    assert Sentinel().authorize(req(risk="critical"), human_approved=True).decision is Decision.AUTHORIZED


def test_missing_authority_is_blocked():
    assert Sentinel().authorize(req(authority="")).decision is Decision.BLOCKED


def test_verification_failure_stays_failed():
    sentinel = Sentinel()
    assert sentinel.verify(sentinel.authorize(req()), success=False).decision is Decision.FAILED


def test_missing_audience_is_blocked_and_logged(caplog):
    with caplog.at_level(logging.WARNING, logger="sentinel"):
        result = Sentinel().authorize(req(aud=""))
    assert result.decision is Decision.BLOCKED
    assert result.reason == "missing audience (aud)"
    assert "missing audience" in caplog.text


def test_wrong_audience_is_blocked_with_reason(caplog):
    with caplog.at_level(logging.WARNING, logger="sentinel"):
        result = Sentinel("eth-desk").authorize(req(aud="aether-sentinel"))
    assert result.decision is Decision.BLOCKED
    assert "'aether-sentinel'" in result.reason and "'eth-desk'" in result.reason
    assert "wrong audience" in caplog.text


def test_audience_is_checked_before_human_approval():
    result = Sentinel("eth-desk").authorize(req(aud="other", risk="critical"), human_approved=True)
    assert result.decision is Decision.BLOCKED


def test_matching_audience_authorizes():
    assert Sentinel("eth-desk").authorize(req(aud="eth-desk")).decision is Decision.AUTHORIZED


def test_rejections_reach_the_tombstone_hook():
    graves = []
    sentinel = Sentinel("eth-desk", on_reject=lambda r, d: graves.append((r.trace_id, d.reason)))
    request = req(aud="someone-else")
    sentinel.authorize(request)
    assert graves == [(request.trace_id, "wrong audience: envelope addressed to 'someone-else', receiver is 'eth-desk'")]


def test_empty_agent_id_is_refused():
    try:
        Sentinel("")
    except ValueError:
        return
    raise AssertionError("Sentinel('') should raise")


def test_caller_supplied_success_cannot_verify_without_trusted_verifier():
    sentinel = Sentinel()
    result = sentinel.verify(
        sentinel.authorize(req()), True, TestResult("fake-run-id", "success")
    )
    assert result.decision is Decision.FAILED
    assert "no independent CI evidence verifier" in result.reason


def test_trusted_verifier_rejects_startup_failure_fixture():
    sentinel = Sentinel(run_evidence_verifier=lambda run, request: run.conclusion == "success")
    result = sentinel.verify(
        sentinel.authorize(req()), True, TestResult("42774884628", "startup_failure")
    )
    assert result.decision is Decision.FAILED
    assert "rejected run 42774884628" in result.reason


def test_trusted_verifier_positive_control_uses_test_double():
    # This validates the dependency seam only; it is not a live GitHub attestation.
    sentinel = Sentinel(
        run_evidence_verifier=lambda run, request: (
            run.run_id == "fixture-success-run" and run.conclusion == "success"
        )
    )
    result = sentinel.verify(
        sentinel.authorize(req()), True, TestResult("fixture-success-run", "success")
    )
    assert result.decision is Decision.VERIFIED
    assert "fixture-success-run" in result.reason


def test_missing_attestation_or_verifier_fails_closed():
    sentinel = Sentinel()
    authorized = sentinel.authorize(req())
    assert sentinel.verify(authorized, True).decision is Decision.FAILED
    assert sentinel.verify(authorized, True, TestResult("", "success")).decision is Decision.FAILED


def test_verifier_exception_fails_closed():
    def broken_verifier(run, request):
        raise RuntimeError("provider unavailable")

    sentinel = Sentinel(run_evidence_verifier=broken_verifier)
    result = sentinel.verify(
        sentinel.authorize(req()), True, TestResult("fixture-run", "success")
    )
    assert result.decision is Decision.FAILED
    assert "rejected run fixture-run" in result.reason


def test_request_attestation_uses_verifier_and_failures_are_tombstoned():
    graves = []
    sentinel = Sentinel(
        on_reject=lambda r, d: graves.append(d.reason),
        run_evidence_verifier=lambda run, request: run.conclusion == "success",
    )
    request = req(test_result=TestResult("123", "failure"))
    result = sentinel.verify(sentinel.authorize(request), True, request=request)
    assert result.decision is Decision.FAILED
    assert graves == ["independent CI evidence verification rejected run 123"]
