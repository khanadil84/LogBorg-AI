from logborg.ingestion.runtime import RuntimeResult


def verify_runtime_recovery(
    result: RuntimeResult,
    fault: str = "BUFFER_OVERFLOW",
) -> bool:
    """Independently verify that the repaired runtime recovered."""
    if result.return_code != 0 or result.stderr.strip():
        return False

    if "HEALTH CHECK: PASS" not in result.stdout:
        return False

    if fault == "BUFFER_OVERFLOW":
        return "TRAFFIC STABLE" in result.stdout

    if fault == "MEMORY_PRESSURE":
        return "MEMORY STABLE" in result.stdout

    return False
