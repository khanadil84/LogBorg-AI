from dataclasses import dataclass

from logborg.detection.signatures import FaultSignature


@dataclass(frozen=True)
class Diagnosis:
    fault: str
    severity: str
    root_cause: str
    recommended_action: str


def analyze(signature: FaultSignature) -> Diagnosis:
    """Translate a detected fault into an actionable diagnosis."""
    if signature.name == "BUFFER_OVERFLOW":
        return Diagnosis(
            fault=signature.name,
            severity=signature.severity,
            root_cause="Stream buffer capacity was exhausted.",
            recommended_action="Activate a sandbox buffer override and reroute volatile traffic.",
        )

    if signature.name == "MEMORY_PRESSURE":
        return Diagnosis(
            fault=signature.name,
            severity=signature.severity,
            root_cause="Runtime memory pressure was detected.",
            recommended_action="Isolate the unhealthy workload and activate the recovery sandbox.",
        )

    return Diagnosis(
        fault=signature.name,
        severity=signature.severity,
        root_cause="Unknown fault signature.",
        recommended_action="Escalate for manual investigation.",
    )
