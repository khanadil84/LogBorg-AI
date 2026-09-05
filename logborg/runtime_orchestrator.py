import json
import shutil
from pathlib import Path

from logborg.detection.live import LiveFaultObserver
from logborg.diagnosis.runtime import diagnose_runtime_failure
from logborg.execution_state import LIVE, new_run_id
from logborg.ingestion.runtime import run_runtime, stream_runtime
from logborg.manifest.writer import write_manifest
from logborg.policy.recovery import select_recovery_policy
from logborg.policy.safety import evaluate_safety
from logborg.incident_memory import incident_memory_evidence, assess_historical_recovery
from logborg.repair.runtime import apply_runtime_repair, rollback_runtime_repair
from logborg.verification.runtime import assess_runtime_recovery
from logborg.verification.reconciliation import reconcile_runtime_state



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

    evidence["memory"] = incident_memory_evidence(project_root, diagnosis.fault)
    evidence["historical_assessment"] = assess_historical_recovery(project_root, diagnosis.fault)

    policy = select_recovery_policy(
        diagnosis.fault,
        evidence["memory"],
    )

    if policy is None:
        state.fail_phase(
            "DIAGNOSE",
            "NO_RECOVERY_POLICY",
            f"No recovery policy exists for {diagnosis.fault}.",
        )
        evidence["status"] = "NO_RECOVERY_POLICY"
        state.set_evidence(evidence)
        _write_evidence(project_root, evidence)
        return False

    historical_verified = evidence["memory"].get("historical_verified", 0)
    verified_playbooks = evidence["memory"].get("verified_playbooks", {})

    if policy.playbook in verified_playbooks:
        playbook_verified = verified_playbooks[policy.playbook]
        selection_reason = (
            f"Selected from historical evidence: {playbook_verified} "
            f"verified incidents explicitly support {policy.playbook}; "
            f"{historical_verified} total incidents for this fault were verified."
        )
    else:
        selection_reason = (
            "Selected from the bounded default policy because no verified "
            "historical playbook was available."
        )

    evidence["policy"] = {
        "playbook": policy.playbook,
        "selection_reason": selection_reason,
        "max_attempts": policy.max_attempts,
        "rollback_on_failure": policy.rollback_on_failure,
        "requires_verification": policy.requires_verification,
    }

    state.complete_phase(
        "DIAGNOSE",
        f"{diagnosis.fault} ({diagnosis.severity}) — {diagnosis.root_cause} Recovery policy selected: {policy.playbook}.",
    )

    # --- SAFETY GATE -----------------------------------------------------
    state.begin_phase(
        "SAFETY",
        f"Evaluating safety constraints for {policy.playbook}.",
    )

    safety = evaluate_safety(policy)

    evidence["safety"] = {
        "allowed": safety.allowed,
        "reason": safety.reason,
    }

    if not safety.allowed:
        state.fail_phase(
            "SAFETY",
            "SAFETY_BLOCKED",
            safety.reason,
        )
        evidence["status"] = "SAFETY_BLOCKED"
        state.set_evidence(evidence)
        _write_evidence(project_root, evidence)
        return False

    state.complete_phase(
        "SAFETY",
        safety.reason,
    )

    # --- REPAIR -----------------------------------------------------------
    state.begin_phase(
        "REPAIR",
        f"Applying {diagnosis.fault} runtime repair configuration.",
    )

    recovery_steps: list[dict] = []

    repair_applied = apply_runtime_repair(source, project_root, diagnosis.fault)

    evidence["repair"] = {
        "applied": repair_applied,
        "action": f"{diagnosis.fault}_RUNTIME_REPAIR",
    }

    if repair_applied:
        recovery_steps.append({
            "step": 1,
            "fault": diagnosis.fault,
            "action": f"{diagnosis.fault}_RUNTIME_REPAIR",
            "applied": True,
        })

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
        f"Re-executing workload with at most {policy.max_attempts} recovery attempts.",
    )

    attempts: list[dict] = []
    verified = False

    for attempt in range(1, policy.max_attempts + 1):
        recovered = run_runtime(source, project_root)
        assessment = assess_runtime_recovery(recovered, diagnosis.fault)
        reconciliation = reconcile_runtime_state(recovered)

        attempt_evidence = {
            "attempt": attempt,
            "return_code": recovered.return_code,
            "stdout": recovered.stdout,
            "stderr": recovered.stderr,
            "assessment": assessment,
            "reconciliation": {
                "converged": reconciliation.converged,
                "return_code_ok": reconciliation.return_code_ok,
                "stderr_empty": reconciliation.stderr_empty,
                "traffic_stable": reconciliation.traffic_stable,
                "health_check": reconciliation.health_check,
                "drift": list(reconciliation.drift),
            },
        }
        attempts.append(attempt_evidence)

        if assessment["passed"]:
            verified = True
            break

        state.publish_runtime_event(
            "verification",
            (
                f"Recovery reassessment failed on attempt {attempt}: "
                f"return_code_ok={assessment['return_code_ok']}, "
                f"stderr_empty={assessment['stderr_empty']}, "
                f"health_check={assessment['health_check']}, "
                f"stability_signal={assessment['stability_signal']}."
            ),
        )

        next_diagnosis = diagnose_runtime_failure(recovered.stderr)

        if (
            next_diagnosis is not None
            and next_diagnosis.fault != diagnosis.fault
            and next_diagnosis.fault in {"BUFFER_OVERFLOW", "MEMORY_PRESSURE"}
            and attempt < policy.max_attempts
        ):
            state.publish_runtime_event(
                "verification",
                f"Adaptive diagnosis: new fault detected — {next_diagnosis.fault} ({next_diagnosis.severity}).",
            )

            next_memory = incident_memory_evidence(
                project_root,
                next_diagnosis.fault,
            )

            next_policy = select_recovery_policy(
                next_diagnosis.fault,
                next_memory,
            )

            if next_policy is not None:
                next_safety = evaluate_safety(next_policy)

                state.publish_runtime_event(
                    "verification",
                    f"Adaptive policy selected: {next_policy.playbook}.",
                )

                if next_safety.allowed:
                    diagnosis = next_diagnosis
                    policy = next_policy

                    state.publish_runtime_event(
                        "verification",
                        f"Adaptive safety gate passed for {policy.playbook}; applying next recovery step.",
                    )

                    next_repair = apply_runtime_repair(
                        source,
                        project_root,
                        diagnosis.fault,
                    )

                    if not next_repair:
                        state.publish_runtime_event(
                            "verification",
                            f"Adaptive repair failed for {diagnosis.fault}.",
                        )
                    else:
                        evidence["diagnosis"] = {
                            "fault": diagnosis.fault,
                            "severity": diagnosis.severity,
                            "root_cause": diagnosis.root_cause,
                            "recommended_action": diagnosis.recommended_action,
                        }
                        evidence["policy"] = {
                            "playbook": policy.playbook,
                            "selection_reason": "Selected adaptively after verification detected a new supported fault.",
                            "max_attempts": policy.max_attempts,
                            "rollback_on_failure": policy.rollback_on_failure,
                            "requires_verification": policy.requires_verification,
                        }
                        evidence["safety"] = {
                            "allowed": next_safety.allowed,
                            "reason": next_safety.reason,
                        }
                        evidence["repair"] = {
                            "applied": True,
                            "action": f"{diagnosis.fault}_RUNTIME_REPAIR",
                        }

                        recovery_steps.append({
                            "step": len(recovery_steps) + 1,
                            "fault": diagnosis.fault,
                            "action": f"{diagnosis.fault}_RUNTIME_REPAIR",
                            "applied": True,
                        })

                        state.publish_runtime_event(
                            "verification",
                            f"Adaptive repair applied: {diagnosis.fault}_RUNTIME_REPAIR.",
                        )

        elif attempt < policy.max_attempts:
            state.publish_runtime_event(
                "verification",
                "Adaptive recovery decision: reassess before next bounded attempt.",
            )

    evidence["recovery_steps"] = recovery_steps
    evidence["recovery_attempts"] = attempts
    evidence["verification"] = {
        "passed": verified,
        "attempts": len(attempts),
        "reconciliation": [
            attempt["reconciliation"]
            for attempt in attempts
            if "reconciliation" in attempt
        ],
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
        memory=evidence["memory"],
        policy=evidence["policy"],
        safety=evidence["safety"],
        repair=evidence["repair"],
        verification=evidence["verification"],
        recovery_steps=evidence.get("recovery_steps", []),
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
