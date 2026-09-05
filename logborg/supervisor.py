import json
from pathlib import Path
from typing import Callable

from logborg.supervision import detect_runtime_drift

from logborg.execution_state import LIVE
from logborg.runtime_orchestrator import recover


def supervise(
    source: str,
    project_root: Path,
    *,
    cycles: int = 1,
    reset_sandbox: bool = False,
    state=None,
    on_cycle: Callable[[int, bool], None] | None = None,
) -> bool:
    """Run bounded autonomous recovery supervision cycles."""
    if cycles < 1:
        raise ValueError("cycles must be at least 1")

    result = True

    for cycle in range(1, cycles + 1):
        result = recover(
            source,
            project_root,
            reset_sandbox=reset_sandbox if cycle == 1 else False,
            state=state or LIVE,
        )

        evidence_path = Path(project_root) / "runtime-evidence.json"

        if result and evidence_path.exists():
            try:
                evidence = json.loads(
                    evidence_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                return False

            drifted, reasons = detect_runtime_drift(evidence)

            if drifted:
                result = False

        if on_cycle is not None:
            on_cycle(cycle, result)

        if not result:
            return False

    return result
