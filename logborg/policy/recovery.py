from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryPolicy:
    fault: str
    playbook: str
    max_attempts: int
    rollback_on_failure: bool
    requires_verification: bool


POLICIES = {
    "BUFFER_OVERFLOW": RecoveryPolicy(
        fault="BUFFER_OVERFLOW",
        playbook="BUFFER_SANDBOX_OVERRIDE",
        max_attempts=2,
        rollback_on_failure=True,
        requires_verification=True,
    ),
    "MEMORY_PRESSURE": RecoveryPolicy(
        fault="MEMORY_PRESSURE",
        playbook="MEMORY_RECOVERY_SANDBOX",
        max_attempts=2,
        rollback_on_failure=True,
        requires_verification=True,
    ),
}


def select_recovery_policy(fault: str) -> RecoveryPolicy | None:
    """Select a bounded and verifiable recovery policy for a known fault."""
    return POLICIES.get(fault)
