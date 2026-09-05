from dataclasses import dataclass

from logborg.policy.recovery import RecoveryPolicy


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    reason: str


def evaluate_safety(policy: RecoveryPolicy) -> SafetyDecision:
    """Allow only bounded, rollback-capable, independently verifiable recovery."""
    if policy.max_attempts < 1:
        return SafetyDecision(False, "Recovery policy has no valid attempt bound.")

    if not policy.rollback_on_failure:
        return SafetyDecision(False, "Recovery policy does not permit rollback.")

    if not policy.requires_verification:
        return SafetyDecision(False, "Recovery policy does not require verification.")

    return SafetyDecision(
        True,
        f"Policy {policy.playbook} passed safety constraints.",
    )
