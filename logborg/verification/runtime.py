from logborg.ingestion.runtime import RuntimeResult


def verify_runtime_recovery(
    result: RuntimeResult,
    fault: str = "BUFFER_OVERFLOW",
) -> bool:
    """Independently verify that the repaired runtime recovered."""
    return bool(assess_runtime_recovery(result, fault)["passed"])


def assess_runtime_recovery(
    result: RuntimeResult,
    fault: str = "BUFFER_OVERFLOW",
) -> dict[str, bool | int]:
    """Return structured verification evidence for recovery reassessment."""
    return_code_ok = result.return_code == 0
    stderr_empty = not result.stderr.strip()
    health_check = "HEALTH CHECK: PASS" in result.stdout

    if fault == "BUFFER_OVERFLOW":
        stability_signal = "TRAFFIC STABLE" in result.stdout
    elif fault == "MEMORY_PRESSURE":
        stability_signal = (
            "MEMORY STABLE" in result.stdout
            or "TRAFFIC STABLE" in result.stdout
        )
    else:
        stability_signal = False

    passed = (
        return_code_ok
        and stderr_empty
        and health_check
        and stability_signal
    )

    return {
        "passed": passed,
        "return_code_ok": return_code_ok,
        "stderr_empty": stderr_empty,
        "health_check": health_check,
        "stability_signal": stability_signal,
        "return_code": result.return_code,
    }
