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

    return None
