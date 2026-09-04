from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepairResult:
    applied: bool
    action: str
    message: str


def apply_buffer_mitigation(project_root: Path) -> RepairResult:
    """Apply a controlled local sandbox mitigation."""
    sandbox = project_root / "sandbox"
    sandbox.mkdir(exist_ok=True)

    override = sandbox / "buffer_override.conf"
    override.write_text(
        "BUFFER_MODE=sandbox\n"
        "TRAFFIC_MODE=stable\n"
        "MITIGATION=buffer_overflow\n",
        encoding="utf-8",
    )

    return RepairResult(
        applied=True,
        action="BUFFER_SANDBOX_OVERRIDE",
        message="Sandbox buffer override activated and volatile traffic redirected.",
    )
