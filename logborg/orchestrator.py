from pathlib import Path

from logborg.ingestion.stream import stream_lines
from logborg.detection.signatures import detect_fault
from logborg.diagnosis.analyzer import analyze
from logborg.repair.playbook import apply_buffer_mitigation
from logborg.verification.check import verify_mitigation
from logborg.manifest.writer import write_manifest


def run(source: str, project_root: Path) -> bool:
    for line in stream_lines(source):
        signature = detect_fault(line)

        if signature is None:
            continue

        diagnosis = analyze(signature)

        if signature.name == "BUFFER_OVERFLOW":
            repair = apply_buffer_mitigation(project_root)
        else:
            return False

        verification = verify_mitigation(project_root)

        write_manifest(
            project_root,
            target=source,
            diagnosis={
                "fault": diagnosis.fault,
                "severity": diagnosis.severity,
                "root_cause": diagnosis.root_cause,
                "recommended_action": diagnosis.recommended_action,
            },
            repair={
                "applied": repair.applied,
                "action": repair.action,
                "message": repair.message,
            },
            verification={
                "passed": verification.passed,
                "checks": verification.checks,
            },
        )

        return verification.passed

    return False


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    target = root / "fixtures" / "sample.log"

    result = run(str(target), root)
    print(f"LOGBORG RESULT: {'SUCCESS' if result else 'FAILURE'}")
