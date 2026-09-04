from dataclasses import dataclass


@dataclass(frozen=True)
class FaultSignature:
    name: str
    severity: str
    keywords: tuple[str, ...]


SIGNATURES = (
    FaultSignature(
        name="BUFFER_OVERFLOW",
        severity="CRITICAL",
        keywords=("buffer overflow", "stream buffer exhausted"),
    ),
    FaultSignature(
        name="MEMORY_PRESSURE",
        severity="HIGH",
        keywords=("out of memory", "memory exhausted", "oom"),
    ),
)


def detect_fault(line: str) -> FaultSignature | None:
    """Return the first matching fault signature for a log line."""
    normalized = line.lower()

    for signature in SIGNATURES:
        if any(keyword in normalized for keyword in signature.keywords):
            return signature

    return None
