from logborg.diagnosis.analyzer import Diagnosis


def diagnose_runtime_failure(stderr: str) -> Diagnosis | None:
    """Diagnose a captured runtime failure."""
    normalized = stderr.lower()

    if "stream buffer overflow" in normalized:
        return Diagnosis(
            fault="BUFFER_OVERFLOW",
            severity="CRITICAL",
            root_cause="Runtime stream buffer capacity was exceeded.",
            recommended_action="Increase the sandbox buffer limit and rerun the workload.",
        )

    if (
        "out of memory" in normalized
        or "memory exhausted" in normalized
        or "oom" in normalized
    ):
        return Diagnosis(
            fault="MEMORY_PRESSURE",
            severity="HIGH",
            root_cause="Runtime memory pressure was detected.",
            recommended_action="Isolate the unhealthy workload and activate the recovery sandbox.",
        )

    return None
