import logging

from sentinel import ActionRequest, Decision, HumanApproval, Sentinel, TestResult
from github_actions_evidence import GitHubActionsEvidenceVerifier


def req(**kw):
    kw.setdefault("aud", "sentinel")
    return ActionRequest("agent", "test", ["demo"], kw.pop("authority", "policy"), **kw)


def test_low_risk_authorizes():
    assert Sentinel().authorize(req()).decision is Decision.AUTHORIZED


def test_high_risk_requires_human():
    assert Sentinel().authorize(req(risk="high")).decision is Decision.HUMAN_REVIEW


def test_high_risk_requires_verifiable_human_approval():
    request = req(risk="critical")
    approval = HumanApproval("approval-1", "human-1", request.trace_id, request.intent, tuple(request.scope), "2099-01-01T00:00:00Z", "test-signature")
    sentinel = Sentinel(human_approval_verifier=lambda grant, action: grant.approval_id == "approval-1")
    assert sentinel.authorize(request, human_approval=approval).decision is Decision.AUTHORIZED


def test_high_risk_boolean_or_missing_verifier_cannot_authorize():
    request = req(risk="critical")
    approval = HumanApproval("approval-1", "human-1", request.trace_id, request.intent, tuple(request.scope), "2099-01-01T00:00:00Z", "test-signature")
    assert Sentinel().authorize(request, human_approval=approval).decision is Decision.HUMAN_REVIEW


def test_protected_grok_dissent_blocks_without_exact_human_override():
    request = req(protected_dissent_node="A7", protected_dissent_id="dissent-77")
    assert Sentinel().authorize(request).decision is Decision.HUMAN_REVIEW


def test_protected_grok_dissent_requires_exact_override_and_verified_signature():
    request = req(protected_dissent_node="A7", protected_dissent_id="dissent-77")
    wrong = HumanApproval("approval-2", "human-1", request.trace_id, request.intent, tuple(request.scope), "2099-01-01T00:00:00Z", "sig", "dissent-other", "reason")
    assert Sentinel(human_approval_verifier=lambda grant, action: True).authorize(request, human_approval=wrong).decision is Decision.HUMAN_REVIEW
    correct = HumanApproval("approval-3", "human-1", request.trace_id, request.intent, tuple(request.scope), "2099-01-01T00:00:00Z", "sig", "dissent-77", "documented risk acceptance")
    sentinel = Sentinel(human_approval_verifier=lambda grant, action: grant.dissent_override_id == "dissent-77")
    assert sentinel.authorize(request, human_approval=correct).decision is Decision.AUTHORIZED


def test_non_a7_node_cannot_claim_protected_grok_dissent():
    request = req(protected_dissent_node="A3", protected_dissent_id="dissent-77")
    approval = HumanApproval("approval-4", "human-1", request.trace_id, request.intent, tuple(request.scope), "2099-01-01T00:00:00Z", "sig", "dissent-77", "reason")
    sentinel = Sentinel(human_approval_verifier=lambda grant, action: True)
    assert sentinel.authorize(request, human_approval=approval).decision is Decision.BLOCKED


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
    result = Sentinel("eth-desk").authorize(req(aud="other", risk="critical"))
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


def _github_run_fixture(conclusion="success", head_sha="abc123", path=".github/workflows/sentinel-ci.yml@refs/heads/main"):
    return {
        "repository": {"full_name": "creatingfire2026/Theodore-s-Automated-copilot-Multi-Agent-System"},
        "head_sha": head_sha,
        "path": path,
        "workflow_id": 390163888,
        "status": "completed",
        "conclusion": conclusion,
    }


def _github_jobs_fixture(conclusion="success", test_step="success"):
    return {
        "jobs": [{
            "name": "test",
            "status": "completed",
            "conclusion": conclusion,
            "steps": [
                {"name": "Compile Sentinel and tests", "status": "completed", "conclusion": "success"},
                {"name": "Run regression suite", "status": "completed", "conclusion": test_step},
            ],
        }]
    }


def test_github_actions_verifier_checks_authoritative_run_and_required_test_step():
    payloads = {
        "/actions/runs/77": _github_run_fixture(),
        "/actions/runs/77/jobs": _github_jobs_fixture(),
    }

    def transport(url, headers, timeout):
        return payloads["/actions/runs/77/jobs"] if url.endswith("/jobs") else payloads["/actions/runs/77"]

    verifier = GitHubActionsEvidenceVerifier(
        repository="creatingfire2026/Theodore-s-Automated-copilot-Multi-Agent-System",
        workflow_path=".github/workflows/sentinel-ci.yml",
        workflow_id=390163888,
        expected_commit_sha="abc123",
        token="fixture-token",
        transport=transport,
    )
    request = req()
    assert verifier(TestResult("77", "failure"), request) is True


def test_github_actions_verifier_rejects_startup_failure_and_zero_jobs():
    payloads = {
        "run": _github_run_fixture(conclusion="startup_failure"),
        "jobs": {"jobs": []},
    }

    def transport(url, headers, timeout):
        return payloads["jobs"] if url.endswith("/jobs") else payloads["run"]

    verifier = GitHubActionsEvidenceVerifier(
        repository="creatingfire2026/Theodore-s-Automated-copilot-Multi-Agent-System",
        workflow_path=".github/workflows/sentinel-ci.yml",
        workflow_id=390163888,
        expected_commit_sha="abc123",
        token="fixture-token",
        transport=transport,
    )
    assert not verifier(TestResult("77", "success"), req())


def test_github_actions_verifier_rejects_wrong_commit_or_workflow():
    run = _github_run_fixture(head_sha="different")
    jobs = _github_jobs_fixture()

    def transport(url, headers, timeout):
        return jobs if url.endswith("/jobs") else run

    verifier = GitHubActionsEvidenceVerifier(
        repository="creatingfire2026/Theodore-s-Automated-copilot-Multi-Agent-System",
        workflow_path=".github/workflows/sentinel-ci.yml",
        workflow_id=390163888,
        expected_commit_sha="abc123",
        token="fixture-token",
        transport=transport,
    )
    assert not verifier(TestResult("77", "success"), req())


def test_github_actions_verifier_rejects_skipped_or_failed_test_step():
    run = _github_run_fixture()
    jobs = _github_jobs_fixture(test_step="skipped")

    def transport(url, headers, timeout):
        return jobs if url.endswith("/jobs") else run

    verifier = GitHubActionsEvidenceVerifier(
        repository="creatingfire2026/Theodore-s-Automated-copilot-Multi-Agent-System",
        workflow_path=".github/workflows/sentinel-ci.yml",
        workflow_id=390163888,
        expected_commit_sha="abc123",
        token="fixture-token",
        transport=transport,
    )
    assert not verifier(TestResult("77", "success"), req())


def test_github_actions_verifier_fails_closed_without_token_or_commit():
    verifier = GitHubActionsEvidenceVerifier(
        repository="creatingfire2026/Theodore-s-Automated-copilot-Multi-Agent-System",
        workflow_path=".github/workflows/sentinel-ci.yml",
        workflow_id=390163888,
        expected_commit_sha="abc123",
        token="",
        transport=lambda url, headers, timeout: {},
    )
    assert not verifier(TestResult("77", "success"), req())
    verifier.token = "fixture-token"
    verifier.expected_commit_sha = ""
    assert not verifier(TestResult("77", "success"), req())


# --- Audit hardening regression tests (local audit branch, 2026-11-21) ---

def test_miscased_high_risk_still_requires_human():
    for label in ("High", "HIGH", " critical "):
        assert Sentinel().authorize(req(risk=label)).decision is Decision.HUMAN_REVIEW


def test_unknown_or_missing_risk_label_fails_closed():
    for label in ("severe", "", None, "lowish"):
        assert Sentinel().authorize(req(risk=label)).decision is Decision.BLOCKED


def test_medium_risk_authorizes_without_human():
    assert Sentinel().authorize(req(risk="medium")).decision is Decision.AUTHORIZED


def test_every_authorize_rejection_reaches_the_hook():
    graves = []
    sentinel = Sentinel(on_reject=lambda r, d: graves.append(d.decision))
    sentinel.authorize(ActionRequest("agent", "test", [], "policy", aud="sentinel"))
    sentinel.authorize(req(authority=""))
    sentinel.authorize(req(risk="high"))
    sentinel.authorize(req(risk="severe"))
    assert graves == [Decision.BLOCKED, Decision.BLOCKED, Decision.HUMAN_REVIEW, Decision.BLOCKED]


def test_github_verifier_rejects_non_ascii_run_id_and_bad_repository():
    calls = []
    def transport(url, headers, timeout):
        calls.append(url)
        return {}
    request = req()
    good = dict(workflow_path=".github/workflows/sentinel-ci.yml", workflow_id=1,
                expected_commit_sha="a" * 40, token="fixture-token", transport=transport)
    unicode_digits = "\u0661\u0662\u0663"
    assert GitHubActionsEvidenceVerifier(repository="o/r", **good)(TestResult(unicode_digits, "success"), request) is False
    assert GitHubActionsEvidenceVerifier(repository="o/r/../../x", **good)(TestResult("123", "success"), request) is False
    assert calls == []


def test_default_transport_refuses_non_github_api_urls():
    import pytest
    for url in ("file:///etc/passwd", "http://api.github.com/x", "https://evil.example/x"):
        with pytest.raises(ValueError):
            GitHubActionsEvidenceVerifier._http_get(url, {}, 1.0)
