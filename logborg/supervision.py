from typing import Any


def detect_runtime_drift(evidence: dict[str, Any]) -> tuple[bool, list[str]]:
    """Detect drift from the desired healthy runtime state."""
    reconciliation = evidence.get("verification", {}).get("reconciliation", [])

    if not reconciliation:
        if evidence.get("status") == "HEALTHY":
            return False, []
        return True, ["reconciliation_evidence_missing"]

    latest = reconciliation[-1]
    drift = list(latest.get("drift", []))

    if latest.get("converged") is not True:
        return True, drift or ["runtime_not_converged"]

    return False, []
