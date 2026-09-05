import json
import shutil
from pathlib import Path

from logborg.detection.live import LiveFaultObserver
from logborg.diagnosis.runtime import diagnose_runtime_failure
from logborg.execution_state import LIVE, new_run_id
from logborg.ingestion.runtime import run_runtime, stream_runtime
from logborg.manifest.writer import write_manifest
from logborg.repair.runtime import apply_runtime_repair, rollback_runtime_repair
from logborg.verification.runtime import verify_runtime_recovery

MAX_RECOVERY_ATTEMPTS = 2


def recover(
    source: str,
    project_root: Path,
    *,
    reset_sandbox: bool = False,
    state=LIVE,
) -> bool:
    """Run autonomous recovery from live runtime telemetry."""
    project_root = Path(project_root)

    if reset_sandbox:
        _reset_sandbox(project_root)

    run_id = new_run_id()
    state.reset(source=source, run_id=run_id)

    evidence: dict = {
        "source": source,
        "run_id": run_id,
        "initial": None,
    }

    observer = LiveFaultObserver()

    def on_stdout(line: str) -> None:
        state.publish_runtime_event("stdout", line)
        observer.observe("stdout", line)

    def on_stderr(line: str) -> None:
        state.publish_runtime_event("stderr", line)
        fault = observer.observe("stderr", line)

        if fault is not None:
            state.publish_runtime_event(
                "stderr",
                f"LIVE FAULT DETECTED: {fault.signature.name} ({fault.signature.severity})",
            )

    # --- INGEST -----------------------------------------------------------
    state.begin_phase(
        "INGEST",
        "Executing runtime workload and capturing live stdout/stderr telemetry.",
    )

    initial = stream_runtime(
        source,
        project_root,
        on_stdout=on_stdout,
        on_stderr=on_stderr,
    )

    evidence["initial"] = {
        "return_code": initial.return_code,
        "stdout": initial.stdout,
        "stderr": initial.stderr,
    }

    evidence["live_faults"] = [
        {
            "stream": fault.stream,
            "line": fault.line,
            "fault": fault.signature.name,
            "severity": fault.signature.severity,
        }
        for fault in observer.detected
    ]

    if initial.return_code == 0:
        state.complete_phase(
            "INGEST",
            "Runtime exited cleanly (return code 0).",
        )
        evidence["status"] = "HEALTHY"
        _write_evidence(project_root, evidence)
        state.set_evidence(evidence)
        state.mark_healthy("Runtime already healthy; no remediation required.")
        return True

    state.complete_phase(
        "INGEST",
        f"Captured runtime failure (return code {initial.return_code}).",
    )

    # --- DIAGNOSE ---------------------------------------------------------
    state.begin_phase(
        "DIAGNOSE",
        "Analyzing the fault detected from live runtime telemetry.",
    )

    diagnosis = diagnose_runtime_failure(initial.stderr)

    if diagnosis is None:
        state.fail_phase(
            "DIAGNOSE",
            "UNDIAGNOSED",
            "No matching fault signature in captured stderr.",
        )
        evidence["status"] = "UNDIAGNOSED"
        _write_evidence(project_root, evidence)
        state.set_evidence(evidence)
        return False

    evidence["diagnosis"] = {
        "fault": diagnosis.fault,
        "severity": diagnosis.severity,
        "root_cause": diagnosis.root_cause,
        "recommended_action": diagnosis.recommended_action,
    }

    if diagnosis.fault not in {"BUFFER_OVERFLOW", "MEMORY_PRESSURE"}:
        state.fail_phase(
            "DIAGNOSE",
            "UNSUPPORTED_FAULT",
            f"Fault {diagnosis.fault} has no automated repair playbook.",
        )
        evidence["status"] = "UNSUPPORTED_FAULT"
        _write_evidence(project_root, evidence)
        state.set_evidence(evidence)
        return False

    state.complete_phase(
        "DIAGNOSE",
        f"{diagnosis.fault} ({diagnosis.severity}) — {diagnosis.root_cause}",
    )

    # --- REPAIR -----------------------------------------------------------
    state.begin_phase(
        "REPAIR",
        f"Applying {diagnosis.fault} runtime repair configuration.",
    )

    repair_applied = apply_runtime_repair(source, project_root, diagnosis.fault)

    evidence["repair"] = {
        "applied": repair_applied,
        "action": f"{diagnosis.fault}_RUNTIME_REPAIR",
    }

    if not repair_applied:
        state.fail_phase(
            "REPAIR",
            "REPAIR_FAILED",
            "Runtime repair configuration could not be applied.",
        )
        evidence["status"] = "REPAIR_FAILED"
        state.set_evidence(evidence)
        return False

    state.complete_phase(
        "REPAIR",
        "Sandbox runtime_repair.conf applied.",
    )

    # --- VERIFY -----------------------------------------------------------
    state.begin_phase(
        "VERIFY",
        f"Re-executing workload with at most {MAX_RECOVERY_ATTEMPTS} recovery attempts.",
    )

    attempts: list[dict] = []
    verified = False

    for attempt in range(1, MAX_RECOVERY_ATTEMPTS + 1):
        recovered = run_runtime(source, project_root)

        attempt_evidence = {
            "attempt": attempt,
            "return_code": recovered.return_code,
            "stdout": recovered.stdout,
            "stderr": recovered.stderr,
        }
        attempts.append(attempt_evidence)

        if verify_runtime_recovery(recovered, diagnosis.fault):
            verified = True
            break

    evidence["recovery_attempts"] = attempts
    evidence["verification"] = {
        "passed": verified,
        "attempts": len(attempts),
    }

    if not verified:
        rollback_applied = rollback_runtime_repair(project_root)
        evidence["rollback"] = {
            "applied": rollback_applied,
            "reason": "All bounded recovery attempts failed.",
        }

        state.fail_phase(
            "VERIFY",
            "RECOVERY_FAILED",
            f"Recovery failed after {len(attempts)} bounded attempt(s); rollback executed.",
        )
        evidence["status"] = "RECOVERY_FAILED"
        state.set_evidence(evidence)
        _write_evidence(project_root, evidence)
        return False

    recovered = attempts[-1]

    recovery_signal = {
        "BUFFER_OVERFLOW": "TRAFFIC STABLE",
        "MEMORY_PRESSURE": "MEMORY STABLE",
    }.get(diagnosis.fault, "RECOVERY SIGNAL")

    state.complete_phase(
        "VERIFY",
        f"Recovery verified on attempt {recovered['attempt']}: return code 0, {recovery_signal} present, health check passed, stderr empty.",
    )

    # --- RECOVERED --------------------------------------------------------
    state.begin_phase(
        "RECOVERED",
        "Finalizing verified recovery.",
    )

    evidence["status"] = "RECOVERED"

    write_manifest(
        project_root,
        target=source,
        run_id=run_id,
        diagnosis=evidence["diagnosis"],
        repair=evidence["repair"],
        verification=evidence["verification"],
    )

    _write_evidence(project_root, evidence)

    state.set_evidence(evidence)

    state.complete_phase(
        "RECOVERED",
        "Workload recovered and independently verified.",
    )

    state.finish_success(
        "RECOVERED",
        "Workload recovered and verified.",
    )

    return True


def _reset_sandbox(project_root: Path) -> None:
    sandbox = project_root / "sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)


def _write_evidence(project_root: Path, evidence: dict) -> None:
    payload = json.dumps(evidence, indent=2)

    output = project_root / "runtime-evidence.json"
    output.write_text(payload, encoding="utf-8")

    run_id = evidence.get("run_id")
    if run_id:
        incident_dir = project_root / "incidents" / run_id
        incident_dir.mkdir(parents=True, exist_ok=True)
        archive = incident_dir / "evidence.json"
        archive.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    source = root / "fixtures" / "runtime_failure.py"

    result = recover(
        str(source),
        root,
        reset_sandbox=True,
    )

    print(
        f"LOGBORG RECOVERY: {'SUCCESS' if result else 'FAILURE'}"
    )
