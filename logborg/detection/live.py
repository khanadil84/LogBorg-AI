from dataclasses import dataclass

from logborg.detection.signatures import FaultSignature, detect_fault


@dataclass(frozen=True)
class LiveFault:
    stream: str
    line: str
    signature: FaultSignature


class LiveFaultObserver:
    """Detect known faults from live runtime telemetry once per incident."""

    def __init__(self) -> None:
        self.detected: list[LiveFault] = []
        self._seen_signatures: set[str] = set()

    def observe(self, stream: str, line: str) -> LiveFault | None:
        signature = detect_fault(line)

        if signature is None:
            return None

        if signature.name in self._seen_signatures:
            return None

        self._seen_signatures.add(signature.name)

        fault = LiveFault(
            stream=stream,
            line=line,
            signature=signature,
        )
        self.detected.append(fault)
        return fault
