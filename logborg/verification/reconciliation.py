from dataclasses import dataclass

from logborg.ingestion.runtime import RuntimeResult


@dataclass(frozen=True)
class DesiredRuntimeState:
    return_code: int = 0
    stderr_empty: bool = True
    traffic_stable: bool = True
    health_check: bool = True


@dataclass(frozen=True)
class ReconciliationResult:
    converged: bool
    return_code_ok: bool
    stderr_empty: bool
    traffic_stable: bool
    health_check: bool
    drift: tuple[str, ...]


def reconcile_runtime_state(
    result: RuntimeResult,
    desired: DesiredRuntimeState | None = None,
) -> ReconciliationResult:
    """Compare actual runtime evidence with the desired healthy state."""
    desired = desired or DesiredRuntimeState()

    return_code_ok = result.return_code == desired.return_code
    stderr_empty = (not result.stderr.strip()) if desired.stderr_empty else True
    traffic_stable = (
        "TRAFFIC STABLE" in result.stdout
        if desired.traffic_stable
        else True
    )
    health_check = (
        "HEALTH CHECK: PASS" in result.stdout
        if desired.health_check
        else True
    )

    drift: list[str] = []

    if not return_code_ok:
        drift.append(
            f"return_code={result.return_code}, expected={desired.return_code}"
        )

    if not stderr_empty:
        drift.append("stderr_not_empty")

    if not traffic_stable:
        drift.append("traffic_not_stable")

    if not health_check:
        drift.append("health_check_failed")

    return ReconciliationResult(
        converged=not drift,
        return_code_ok=return_code_ok,
        stderr_empty=stderr_empty,
        traffic_stable=traffic_stable,
        health_check=health_check,
        drift=tuple(drift),
    )
