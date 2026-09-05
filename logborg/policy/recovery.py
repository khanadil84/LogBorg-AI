from dataclasses import dataclass
from typing import Any


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


def select_recovery_policy(
    fault: str,
    memory: dict[str, Any] | None = None,
) -> RecoveryPolicy | None:
    """Select a bounded and verifiable recovery policy using historical evidence."""
    policy = POLICIES.get(fault)

    if policy is None:
        return None

    verified_playbooks = (memory or {}).get("verified_playbooks", {})

    if verified_playbooks:
        preferred_playbook = max(
            verified_playbooks,
            key=verified_playbooks.get,
        )

        for candidate in POLICIES.values():
            if (
                candidate.fault == fault
                and candidate.playbook == preferred_playbook
            ):
                return candidate

    return policy
