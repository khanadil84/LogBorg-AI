import json
import shutil
from pathlib import Path

from logborg.diagnosis.runtime import diagnose_runtime_failure
from logborg.execution_state import LIVE, new_run_id
from logborg.ingestion.runtime import run_runtime
from logborg.manifest.writer import write_manifest
from logborg.repair.runtime import apply_runtime_repair
from logborg.verification.runtime import verify_runtime_recovery


def recover(
    source: str,
    project_root: Path,
    *,
    reset_sandbox: bool = False,
    state=LIVE,
) -> bool:
    """Run autonomous recovery and persist real execution evidence.

    Phase transitions are published to ``state`` so the dashboard SVG
    reflects actual LogBorg progress — never synthetic telemetry.
    """
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

    # --- INGEST -----------------------------------------------------------
    state.begin_phase("INGEST", "Executing runtime workload and capturing output.")
    initial = run_runtime(source, project_root)
    evidence["initial"] = {
        "return_code": initial.return_code,
        "stdout": initial.stdout,
        "stderr": initial.stderr,
    }

    if initial.return_code == 0:
        state.complete_phase("INGEST", "Runtime exited cleanly (return code 0).")
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
    state.begin_phase("DIAGNOSE", "Analyzing stderr for known fault signatures.")
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

    if diagnosis.fault != "BUFFER_OVERFLOW":
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
    state.begin_phase("REPAIR", "Applying BUFFER_OVERFLOW runtime repair configuration.")
    repair_applied = apply_runtime_repair(source, project_root)
    evidence["repair"] = {
        "applied": repair_applied,
        "action": "BUFFER_OVERFLOW_RUNTIME_REPAIR",
    }

    if not repair_applied:
        state.fail_phase(
            "REPAIR",
            "REPAIR_FAILED",
            "Runtime repair configuration could not be applied.",
        )
        evidence["status"] = "REPAIR_FAILED"
        _write_evidence(project_root, evidence)
        state.set_evidence(evidence)
        return False

    state.complete_phase("REPAIR", "Sandbox runtime_repair.conf applied.")

    # --- VERIFY -----------------------------------------------------------
    state.begin_phase("VERIFY", "Re-executing workload and verifying recovery signals.")
    recovered = run_runtime(source, project_root)

    evidence["recovery"] = {
        "return_code": recovered.return_code,
        "stdout": recovered.stdout,
        "stderr": recovered.stderr,
    }

    verified = verify_runtime_recovery(recovered)
    evidence["verification"] = {"passed": verified}

    if not verified:
        state.fail_phase(
            "VERIFY",
            "RECOVERY_FAILED",
            "Post-repair runtime did not satisfy recovery checks.",
        )
        evidence["status"] = "RECOVERY_FAILED"
        _write_evidence(project_root, evidence)
        state.set_evidence(evidence)
        return False

    state.complete_phase(
        "VERIFY",
        "Return code 0, TRAFFIC STABLE present, stderr empty.",
    )

    # --- RECOVERED --------------------------------------------------------
    state.begin_phase("RECOVERED", "Finalizing verified recovery.")
    evidence["status"] = "RECOVERED"

    write_manifest(
        project_root,
        target=source,
        diagnosis=evidence["diagnosis"],
        repair=evidence["repair"],
        verification=evidence["verification"],
    )

    _write_evidence(project_root, evidence)
    state.set_evidence(evidence)
    state.complete_phase("RECOVERED", "Workload recovered and independently verified.")
    state.finish_success("RECOVERED", "Workload recovered and verified.")
    return True


def _reset_sandbox(project_root: Path) -> None:
    sandbox = project_root / "sandbox"
    if sandbox.exists():
        shutil.rmtree(sandbox)


def _write_evidence(project_root: Path, evidence: dict) -> None:
    output = project_root / "runtime-evidence.json"
    output.write_text(
        json.dumps(evidence, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    source = root / "fixtures" / "runtime_failure.py"

    result = recover(str(source), root, reset_sandbox=True)
    print(f"LOGBORG RECOVERY: {'SUCCESS' if result else 'FAILURE'}")
