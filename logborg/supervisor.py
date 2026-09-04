from pathlib import Path
from typing import Callable

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
            state=state,
        )

        if on_cycle is not None:
            on_cycle(cycle, result)

        if not result:
            return False

    return result
