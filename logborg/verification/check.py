from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    checks: tuple[str, ...]


def verify_mitigation(project_root: Path) -> VerificationResult:
    """Independently verify the sandbox mitigation state."""
    override = project_root / "sandbox" / "buffer_override.conf"

    if not override.exists():
        return VerificationResult(
            passed=False,
            checks=("buffer_override.conf missing",),
        )

    content = override.read_text(encoding="utf-8")
    required = (
        "BUFFER_MODE=sandbox",
        "TRAFFIC_MODE=stable",
        "MITIGATION=buffer_overflow",
    )

    missing = tuple(
        f"missing:{item}" for item in required if item not in content
    )

    if missing:
        return VerificationResult(
            passed=False,
            checks=missing,
        )

    return VerificationResult(
        passed=True,
        checks=(
            "buffer override exists",
            "sandbox mode active",
            "stable traffic mode active",
            "buffer overflow mitigation active",
        ),
    )
