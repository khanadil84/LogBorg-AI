from logborg.policy.recovery import RecoveryPolicy
from logborg.policy.safety import evaluate_safety


def test_safe_policy_is_allowed():
    policy = RecoveryPolicy(
        fault="TEST",
        playbook="SAFE_TEST",
        max_attempts=2,
        rollback_on_failure=True,
        requires_verification=True,
    )

    decision = evaluate_safety(policy)

    assert decision.allowed is True
    assert "passed safety constraints" in decision.reason


def test_unbounded_policy_is_blocked():
    policy = RecoveryPolicy(
        fault="TEST",
        playbook="UNSAFE_TEST",
        max_attempts=0,
        rollback_on_failure=True,
        requires_verification=True,
    )

    decision = evaluate_safety(policy)

    assert decision.allowed is False
    assert "attempt bound" in decision.reason


def test_no_rollback_policy_is_blocked():
    policy = RecoveryPolicy(
        fault="TEST",
        playbook="UNSAFE_TEST",
        max_attempts=2,
        rollback_on_failure=False,
        requires_verification=True,
    )

    decision = evaluate_safety(policy)

    assert decision.allowed is False
    assert "rollback" in decision.reason


def test_no_verification_policy_is_blocked():
    policy = RecoveryPolicy(
        fault="TEST",
        playbook="UNSAFE_TEST",
        max_attempts=2,
        rollback_on_failure=True,
        requires_verification=False,
    )

    decision = evaluate_safety(policy)

    assert decision.allowed is False
    assert "verification" in decision.reason
