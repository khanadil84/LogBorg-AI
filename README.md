# LogBorg AI

## The Autonomous Google-Tier Log Triage & Self-Healing SRE Sandbox

> A Level-5-inspired autonomous SRE control-plane prototype that detects runtime faults from live telemetry, diagnoses root causes, applies bounded sandbox repairs, and independently verifies recovery — all without human intervention.

---

## Executive Summary

LogBorg AI is a production-inspired autonomous reliability system that closes the loop between **failure detection** and **verified recovery**. It ingests live runtime telemetry, matches fault signatures against known patterns, applies configurable repair policies within an isolated sandbox, and re-executes the workload to confirm the fix actually worked — not just that it was applied.

The system is built on Google SRE and Borg principles: **desired-state reconciliation**, **bounded recovery actions**, **independent verification**, and **safe failure for unknown conditions**. It runs entirely locally as a reproducible sandbox, with a real-time SVG topology dashboard driven exclusively by actual execution state — no synthetic telemetry.

---

## Problem → Solution

### The Problem

In production SRE environments, the gap between **detecting a fault** and **verifying recovery** is where incidents live or die. Most monitoring tools stop at alerting. The human operator must then:

1. Read the logs and understand the error
2. Determine a remediation action
3. Apply the fix
4. Re-run the workload to check if it worked
5. Repeat if the fix exposed a different fault

This loop takes minutes to hours, during which the system is degraded.

### The Solution

LogBorg AI automates this entire loop as a closed control plane:

```
LIVE FAILURE → DETECTION → DECISION → SAFE ACTION → VERIFICATION → ADAPTATION → CONVERGENCE
```

Every phase is observable. Every action is bounded. Every repair is independently verified. Unknown faults fail safely instead of guessing.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                           LogBorg AI Recovery Pipeline                                │
│                                                                                      │
│  ┌──────────┐   ┌───────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────┐│
│  │  INGEST   │──▶│  DIAGNOSE │──▶│  SAFETY  │──▶│  REPAIR  │──▶│  VERIFY  │──▶│RECOV││
│  │          │   │           │   │  GATE    │   │          │   │          │   │ERED ││
│  │ Execute  │   │ Match     │   │ Evaluate │   │ Apply    │   │ Re-exec  │   │     ││
│  │ workload │   │ fault     │   │ policy   │   │ bounded  │   │ workload │   │ Done││
│  │ stream   │   │ signatures│   │ constraints│  │ sandbox  │   │ check    │   │     ││
│  │ live     │   │ select    │   │ block if │   │ repair   │   │ signals  │   │     ││
│  │ telemetry│   │ policy    │   │ unsafe   │   │ config   │   │ reconcile│   │     ││
│  └──────────┘   └───────────┘   └──────────┘   └──────────┘   └──────────┘   └─────┘│
│       │              │               │               │              │             │   │
│       └──────────────┴───────────────┴───────────────┴──────────────┴─────────────┘   │
│                          ExecutionState (thread-safe)                                 │
│                          ↕ SSE stream to dashboard                                   │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### Module Map

| Module | Responsibility |
|---|---|
| `logborg/ingestion/` | Execute runtime workloads, capture stdout/stderr, stream live telemetry |
| `logorg/detection/` | Signature-based fault matching and live fault observation |
| `logborg/diagnosis/` | Translate detected signatures into structured diagnoses |
| `logborg/policy/` | Recovery policy selection and safety gate evaluation |
| `logborg/repair/` | Apply bounded, reversible sandbox repair configurations |
| `logborg/verification/` | Independently verify recovery, reconcile desired vs actual state |
| `logborg/manifest/` | Write structured evidence manifests with schema versioning |
| `logborg/incident_memory.py` | Query historical verified playbook evidence from archived incidents |
| `logborg/supervisor.py` | Run bounded recovery supervision cycles |
| `logborg/supervision.py` | Detect runtime drift from desired healthy state |
| `logborg/execution_state.py` | Thread-safe live execution state — single source of truth for the dashboard |
| `logborg/runtime_orchestrator.py` | Autonomous recovery pipeline orchestrating all six phases |
| `logborg/dashboard/` | HTTP server with SSE streaming, SVG topology visualization |

---

## Autonomous Decision Loop

The pipeline operates as a strict, observable state machine with **six phases**:

```
INGEST → DIAGNOSE → SAFETY → REPAIR → VERIFY → RECOVERED
```

### Phase 1: INGEST

The system executes the target workload via `subprocess` and streams live stdout/stderr telemetry. A `LiveFaultObserver` detects known fault signatures in real time as output arrives. If the workload exits cleanly (return code 0), the system marks it `HEALTHY` and exits early.

```python
# From logborg/ingestion/runtime.py
process = subprocess.run(["python3", source], capture_output=True, text=True, env=env)
return RuntimeResult(return_code=process.returncode, stdout=process.stdout, stderr=process.stderr)
```

### Phase 2: DIAGNOSE

The captured stderr is analyzed against known fault signatures. Each signature maps to a structured `Diagnosis` containing the fault name, severity, root cause, and recommended action. The system also queries **incident memory** to assess historical recovery evidence for the diagnosed fault.

**Currently supported fault signatures:**

| Fault | Severity | Detection Keywords | Automated Playbook |
|---|---|---|---|
| `BUFFER_OVERFLOW` | CRITICAL | `buffer overflow`, `stream buffer exhausted` | `BUFFER_SANDBOX_OVERRIDE` |
| `MEMORY_PRESSURE` | HIGH | `out of memory`, `memory exhausted`, `oom` | `MEMORY_RECOVERY_SANDBOX` |

```python
# From logborg/detection/signatures.py
SIGNATURES = (
    FaultSignature(name="BUFFER_OVERFLOW", severity="CRITICAL",
                   keywords=("buffer overflow", "stream buffer exhausted")),
    FaultSignature(name="MEMORY_PRESSURE", severity="HIGH",
                   keywords=("out of memory", "memory exhausted", "oom")),
)
```

If no signature matches, the system returns `UNDIAGNOSED` and exits safely. If a signature matches but no recovery policy exists, the system returns `UNSUPPORTED_FAULT`.

### Phase 3: SAFETY GATE

Before any repair is applied, the system evaluates the selected recovery policy against safety constraints. The safety gate ensures every policy is:

- **Bounded**: Must have a valid attempt limit (`max_attempts >= 1`)
- **Rollback-capable**: Must permit rollback on failure (`rollback_on_failure=True`)
- **Independently verifiable**: Must require verification (`requires_verification=True`)

```python
# From logborg/policy/safety.py
def evaluate_safety(policy: RecoveryPolicy) -> SafetyDecision:
    if policy.max_attempts < 1:
        return SafetyDecision(False, "Recovery policy has no valid attempt bound.")
    if not policy.rollback_on_failure:
        return SafetyDecision(False, "Recovery policy does not permit rollback.")
    if not policy.requires_verification:
        return SafetyDecision(False, "Recovery policy does not require verification.")
    return SafetyDecision(True, f"Policy {policy.playbook} passed safety constraints.")
```

If the safety gate blocks the policy, the status is `SAFETY_BLOCKED` — no repair is attempted.

### Phase 4: REPAIR

For supported faults with automated playbooks, the system applies a bounded, reversible sandbox repair. Repairs are **configuration changes only** — no destructive actions, no external API calls, no infrastructure mutations. Previous configurations are backed up before modification.

| Fault | Playbook | Repair Action | Env Variable |
|---|---|---|---|
| `BUFFER_OVERFLOW` | `BUFFER_SANDBOX_OVERRIDE` | `BUFFER_OVERFLOW_RUNTIME_REPAIR` | `LOGBORG_BUFFER_LIMIT=8` |
| `MEMORY_PRESSURE` | `MEMORY_RECOVERY_SANDBOX` | `MEMORY_PRESSURE_RUNTIME_REPAIR` | `LOGBORG_MEMORY_MODE=sandbox` |

### Phase 5: VERIFY

The system **re-executes the workload** with the repair configuration injected, up to `max_attempts` bounded attempts. Each attempt is independently assessed and reconciled against the desired healthy state.

**Verification checks (fault-aware):**

| Check | BUFFER_OVERFLOW | MEMORY_PRESSURE |
|---|---|---|
| Return code | Must be `0` | Must be `0` |
| Stability signal | `TRAFFIC STABLE` in stdout | `MEMORY STABLE` or `TRAFFIC STABLE` in stdout |
| Health check | `HEALTH CHECK: PASS` in stdout | `HEALTH CHECK: PASS` in stdout |
| Stderr | Must be empty | Must be empty |

**Adaptive recovery**: If verification fails and the re-executed workload exposes a *different* supported fault, the system adaptively selects a new recovery policy, passes it through the safety gate, and applies the next repair step — all within the same recovery run.

```python
# From logborg/runtime_orchestrator.py — adaptive recovery loop
if (
    next_diagnosis is not None
    and next_diagnosis.fault != diagnosis.fault
    and next_diagnosis.fault in {"BUFFER_OVERFLOW", "MEMORY_PRESSURE"}
    and attempt < policy.max_attempts
):
    # Adaptive: new fault detected, select new policy, apply next repair step
```

If all bounded attempts fail, the system **rolls back** the repair configuration and returns `RECOVERY_FAILED`.

### Phase 6: RECOVERED

Only reached when all verification checks pass. The evidence is persisted to both `runtime-evidence.json` and an archived incident manifest. The dashboard reflects the final verified state.

---

## Adaptive Multi-Step Recovery

The system demonstrates adaptive recovery when verification exposes a different supported fault. Here is the actual demonstrated path:

```
┌──────────┐   ┌───────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  INGEST   │──▶│  DIAGNOSE │──▶│  SAFETY  │──▶│  REPAIR  │──▶│  VERIFY  │──▶│ RECOVERED│
│ execute   │   │ BUFFER_   │   │ gate     │   │ increase │   │ re-exec  │   │ done     │
│ workload  │   │ OVERFLOW  │   │ passed   │   │ buffer   │   │ check    │   │          │
└──────────┘   └───────────┘   └──────────┘   └──────────┘   └────┬─────┘   └──────────┘
                                                                   │
                                                           return_code=0
                                                           but stderr has
                                                           new fault
                                                                   │
                                                                   ▼
                                                           ┌───────────┐
                                                           │  DIAGNOSE │
                                                           │ MEMORY_   │
                                                           │ PRESSURE  │
                                                           └─────┬─────┘
                                                                 │
                                                         ┌───────┴───────┐
                                                         │               │
                                                  adaptive repair   UNSUPPORTED
                                                  select policy     (safe fail)
                                                         │
                                                         ▼
                                                  ┌──────────┐
                                                  │  REPAIR  │
                                                  │ memory   │
                                                  │ sandbox  │
                                                  └────┬─────┘
                                                       │
                                                       ▼
                                                  ┌──────────┐
                                                  │  VERIFY  │
                                                  │ re-exec  │
                                                  │ check    │
                                                  └────┬─────┘
                                                       │
                                                       ▼
                                                  ┌──────────┐
                                                  │RECOVERED │
                                                  └──────────┘
```

**Evidence of adaptive recovery** (from `test_adaptive_reassessment_event_is_recorded`):

```json
{
  "recovery_steps": [
    {"step": 1, "fault": "BUFFER_OVERFLOW", "action": "BUFFER_OVERFLOW_RUNTIME_REPAIR"},
    {"step": 2, "fault": "MEMORY_PRESSURE", "action": "MEMORY_PRESSURE_RUNTIME_REPAIR"}
  ]
}
```

---

## Safety Model

LogBorg AI enforces safety through multiple layers:

### Safety Gate

Every recovery policy must pass the safety gate before any repair is attempted. The gate is evaluated **after** diagnosis and policy selection, **before** any repair configuration is written.

| Constraint | Required | Blocked If |
|---|---|---|
| `max_attempts >= 1` | Yes | Policy has no valid attempt bound |
| `rollback_on_failure` | Yes | Policy does not permit rollback |
| `requires_verification` | Yes | Policy does not require verification |

### Bounded Recovery Actions

Repairs are configuration-only. The system writes files to the `sandbox/` directory — it never modifies source code, system configuration, or external services. Previous configurations are backed up before modification and restored on rollback.

### Unknown-Fault Safe Failure

When the system encounters a fault it cannot repair, it fails with a clear status rather than guessing:

| Condition | Status | Behavior |
|---|---|---|
| No signature match | `UNDIAGNOSED` | Exits without action |
| Signature match, no recovery policy | `UNSUPPORTED_FAULT` | Exits without action |
| Safety gate blocks policy | `SAFETY_BLOCKED` | Exits without action |
| Repair fails to apply | `REPAIR_FAILED` | Exits, preserves evidence |
| All verification attempts fail | `RECOVERY_FAILED` | Rolls back, preserves evidence |

**The system never guesses.** If it cannot repair a fault with a known playbook, it stops and reports the situation for human review.

### Independent Verification

The system does not trust its own repair. It re-executes the workload from scratch and checks concrete signals — return code, stability signal, health check, and stderr. Each verification attempt produces structured reconciliation evidence.

---

## Desired-State Reconciliation

The system compares actual runtime evidence against a `DesiredRuntimeState` and computes a `ReconciliationResult`:

```python
# From logborg/verification/reconciliation.py
@dataclass(frozen=True)
class DesiredRuntimeState:
    return_code: int = 0
    stderr_empty: bool = True
    traffic_stable: bool = True
    health_check: bool = True
```

The reconciliation checks:
- Return code equals desired (0)
- Stderr is empty
- Traffic stability signal present (`TRAFFIC STABLE`)
- Health check passed (`HEALTH CHECK: PASS`)

Any mismatch is recorded as **drift** in the reconciliation evidence:

```json
{
  "reconciliation": {
    "converged": false,
    "return_code_ok": false,
    "stderr_empty": false,
    "traffic_stable": false,
    "health_check": false,
    "drift": ["return_code=1, expected=0", "stderr_not_empty", "traffic_not_stable", "health_check_failed"]
  }
}
```

---

## Runtime Drift Supervision

The `supervisor.py` module runs bounded recovery supervision cycles. After each cycle, `supervision.py` inspects the reconciliation evidence to detect drift from the desired healthy state:

```python
# From logborg/supervision.py
def detect_runtime_drift(evidence: dict) -> tuple[bool, list[str]]:
    latest = reconciliation[-1]
    if latest.get("converged") is not True:
        return True, drift or ["runtime_not_converged"]
    return False, []
```

If drift is detected, the supervision cycle reports failure — even if the recovery pipeline itself reported success. This provides an independent second-check on runtime health.

---

## Incident Memory

LogBorg AI maintains an **incident memory** — a historical record of all past recovery runs stored as archived manifests in the `incidents/` directory. Each incident contains the complete diagnosis, policy, safety decision, repair, and verification evidence.

### How It Works

1. Every recovery run archives its manifest to `incidents/{run_id}/manifest.json`
2. `incident_memory.py` queries these archived manifests to build historical evidence
3. The recovery policy selector uses this evidence to prefer **historically verified playbooks**

```python
# From logborg/incident_memory.py
def incident_memory_evidence(project_root: Path, fault: str) -> dict:
    return {
        "fault": fault,
        "historical_incidents": memory["incident_count"],
        "historical_verified": memory["verified_count"],
        "verification_rate": verified_count / incident_count,
        "verified_playbooks": memory["verified_playbook_counts"],
    }
```

### Historical Playbook Selection

When multiple playbooks exist for a fault, the policy selector prefers the playbook with the most historical verified incidents:

```python
# From logborg/policy/recovery.py
verified_playbooks = (memory or {}).get("verified_playbooks", {})
if verified_playbooks:
    preferred_playbook = max(verified_playbooks, key=verified_playbooks.get)
    # Return the policy matching the historically verified playbook
```

---

## Evidence Model

Every recovery run produces structured evidence in two forms: `runtime-evidence.json` (execution trace) and `logborg-manifest.json` (versioned remediation manifest).

### Evidence Structure

| Field | Records |
|---|---|
| `initial` | Raw output from the first execution (before any repair) |
| `live_faults` | Faults detected from live stdout/stderr telemetry during INGEST |
| `diagnosis` | Structured fault analysis from the DIAGNOSE phase |
| `memory` | Historical incident memory evidence for the diagnosed fault |
| `policy` | Selected recovery policy with playbook, attempt bounds, and selection reason |
| `safety` | Safety gate decision (allowed/blocked with reason) |
| `repair` | Repair action applied and whether it succeeded |
| `recovery_steps` | Ordered list of actual repair actions applied (e.g., step 1: BUFFER, step 2: MEMORY) |
| `recovery_attempts` | Each verification attempt with return code, stdout, stderr, assessment, and reconciliation |
| `verification` | Aggregate pass/fail, attempt count, and per-attempt reconciliation evidence |
| `rollback` | Rollback action if all attempts failed |
| `status` | Final pipeline outcome (`RECOVERED`, `SAFETY_BLOCKED`, `RECOVERY_FAILED`, etc.) |

**`recovery_steps` vs `recovery_attempts`**: `recovery_steps` records the actual repair actions applied (which faults were repaired, in what order). `recovery_attempts` records each verification re-execution attempt with its full output and reconciliation evidence. They are separate because the system tracks *what it did* (steps) independently from *how many times it checked* (attempts).

### Runtime Evidence Example

```json
{
  "source": "fixtures/runtime_failure.py",
  "run_id": "run-1788541410837",
  "initial": {
    "return_code": 1,
    "stdout": "SERVICE STARTED\nBUFFER LIMIT: 2\n",
    "stderr": "RuntimeError: Stream buffer overflow: 4 chunks > limit 2"
  },
  "diagnosis": {
    "fault": "BUFFER_OVERFLOW",
    "severity": "CRITICAL",
    "root_cause": "Runtime stream buffer capacity was exceeded.",
    "recommended_action": "Increase the sandbox buffer limit and rerun the workload."
  },
  "policy": {
    "playbook": "BUFFER_SANDBOX_OVERRIDE",
    "selection_reason": "Selected from historical evidence: 7 verified incidents...",
    "max_attempts": 2,
    "rollback_on_failure": true,
    "requires_verification": true
  },
  "safety": {
    "allowed": true,
    "reason": "Policy BUFFER_SANDBOX_OVERRIDE passed safety constraints."
  },
  "repair": {
    "applied": true,
    "action": "BUFFER_OVERFLOW_RUNTIME_REPAIR"
  },
  "recovery_steps": [
    {"step": 1, "fault": "BUFFER_OVERFLOW", "action": "BUFFER_OVERFLOW_RUNTIME_REPAIR", "applied": true}
  ],
  "recovery_attempts": [
    {
      "attempt": 1,
      "return_code": 0,
      "stdout": "SERVICE STARTED\nBUFFER LIMIT: 8\nTRAFFIC STABLE\nHEALTH CHECK: PASS\n",
      "stderr": "",
      "assessment": {"passed": true, "return_code_ok": true, "stderr_empty": true, "health_check": true, "stability_signal": true},
      "reconciliation": {"converged": true, "return_code_ok": true, "stderr_empty": true, "traffic_stable": true, "health_check": true, "drift": []}
    }
  ],
  "verification": {
    "passed": true,
    "attempts": 1,
    "reconciliation": [{"converged": true, "return_code_ok": true, "stderr_empty": true, "traffic_stable": true, "health_check": true, "drift": []}]
  },
  "status": "RECOVERED"
}
```

### Manifest Writer

The manifest writer (`logborg/manifest/writer.py`) produces `logborg-manifest.json` with schema versioning and archives it to `incidents/{run_id}/manifest.json`:

```json
{
  "schema_version": "1.1",
  "generated_at": "2026-09-06T...",
  "metadata": {"platform": "Modiqo", "system": "LogBorg AI"},
  "autonomy": {
    "telemetry": "live_stdout_stderr",
    "fault_detection": "automatic",
    "diagnosis": "automatic",
    "repair": "automatic",
    "verification": "independent_rerun"
  },
  "incident": {"run_id": "...", "lifecycle": "RECOVERED"},
  "remediation_timeline": [
    "LIVE_TELEMETRY_CAPTURED", "FAULT_DETECTED", "ROOT_CAUSE_DIAGNOSED",
    "REPAIR_APPLIED", "WORKLOAD_RERUN", "RECOVERY_VERIFIED"
  ],
  "diagnosis": { ... },
  "memory": { ... },
  "policy": { ... },
  "safety": { ... },
  "repair": { ... },
  "verification": { ... },
  "recovery_steps": [ ... ]
}
```

---

## Live Execution-State Architecture

The dashboard is driven by a single `ExecutionState` instance — a thread-safe state machine that publishes every phase transition in real time via Server-Sent Events (SSE).

```
┌─────────────────────────────────────────────────────────────────┐
│                       ExecutionState                             │
│                                                                 │
│  Thread-safe state with pub/sub listeners                       │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Phases: INGEST → DIAGNOSE → SAFETY → REPAIR → VERIFY  │   │
│  │          → RECOVERED                                     │   │
│  │                                                         │   │
│  │  Node states: pending | active | success |              │   │
│  │               failed  | skipped                         │   │
│  │                                                         │   │
│  │  Edge states: idle | flowing | complete | failed        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │                                      │
│                subscribe │ snapshot()                           │
│                          ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  SSE /api/events                                        │   │
│  │  ↓                                                      │   │
│  │  SVG Topology (hexagonal nodes + bezier edges)          │   │
│  │  Phase list · Event feed · Evidence viewer              │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### State Transitions

The orchestrator calls `state.begin_phase()`, `state.complete_phase()`, or `state.fail_phase()` at each step. The `ExecutionState` class:

- Maintains a snapshot of all phase states, edges, and the event log
- Publishes updates to all SSE subscribers on every transition
- Skips downstream phases when an upstream phase fails
- Provides a bounded event tail (last 80 events) for the live UI
- Streams live runtime events (stdout/stderr) via `publish_runtime_event()`

**Every visual element in the dashboard maps to a real state transition.** There is no synthetic telemetry, no mocked data, no animation independent of actual pipeline progress.

---

## Repository Architecture

```
LogBorg-AI/
├── _start.py                         # Dashboard launcher
├── runtime-evidence.json             # Persisted recovery evidence
├── logborg-manifest.json             # Versioned remediation manifest
│
├── logborg/
│   ├── __init__.py
│   ├── orchestrator.py               # Log-file-based orchestration (sample.log)
│   ├── runtime_orchestrator.py       # Autonomous runtime recovery pipeline (6 phases)
│   ├── execution_state.py            # Thread-safe live state machine
│   ├── incident_memory.py            # Historical verified playbook evidence
│   ├── supervisor.py                 # Bounded recovery supervision cycles
│   ├── supervision.py                # Runtime drift detection
│   │
│   ├── ingestion/
│   │   ├── stream.py                 # Line-by-line log streaming
│   │   └── runtime.py                # Subprocess execution, env injection, live streaming
│   │
│   ├── detection/
│   │   ├── signatures.py             # Fault signature matching
│   │   └── live.py                   # Live fault observation from runtime telemetry
│   │
│   ├── diagnosis/
│   │   ├── analyzer.py               # Signature → Diagnosis translation
│   │   └── runtime.py                # Runtime stderr diagnosis (BUFFER_OVERFLOW + MEMORY_PRESSURE)
│   │
│   ├── policy/
│   │   ├── recovery.py               # Recovery policy selection with historical evidence
│   │   └── safety.py                 # Safety gate evaluation
│   │
│   ├── repair/
│   │   ├── playbook.py               # Sandbox mitigation playbook
│   │   └── runtime.py                # Reversible runtime repair configuration
│   │
│   ├── verification/
│   │   ├── check.py                  # Sandbox state verification
│   │   ├── runtime.py                # Fault-aware recovery verification
│   │   └── reconciliation.py         # Desired-state reconciliation with drift detection
│   │
│   ├── manifest/
│   │   └── writer.py                 # Evidence manifest generation (schema v1.1)
│   │
│   └── dashboard/
│       ├── __main__.py               # Dashboard entry point
│       ├── server.py                 # HTTP + SSE streaming server
│       └── static/
│           ├── index.html            # Recovery console UI
│           ├── app.js                # Dashboard controller + SSE binding
│           └── style.css             # Dashboard styles
│
├── fixtures/
│   ├── runtime_failure.py            # Simulated buffer overflow workload
│   ├── memory_failure.py             # Simulated memory pressure workload
│   ├── runtime_adaptive_failure.py   # Adaptive multi-fault workload
│   ├── unsupported_failure.py        # Unsupported fault (database corruption)
│   └── sample.log                    # Sample log file for stream-based orchestration
│
├── incidents/                        # Archived incident evidence (memory)
│   └── {run_id}/
│       ├── evidence.json             # Complete execution trace
│       └── manifest.json             # Versioned remediation manifest
│
├── sandbox/
│   └── runtime_repair.conf           # Active repair configuration
│
└── tests/                            # 28 passing tests
    ├── test_runtime_recovery.py      # End-to-end recovery, adaptive, reconciliation tests
    ├── test_safety_policy.py         # Safety gate constraint tests
    └── test_incident_memory.py       # Incident memory and historical evidence tests
```

---

## Quick Start

### Run the Dashboard

```bash
python _start.py
```

Opens the Recovery Console at `http://127.0.0.1:8792`. Click **Run Recovery** to trigger the autonomous pipeline.

### Run the Orchestrator Directly

```bash
python -m logborg.runtime_orchestrator
```

This executes the full 6-phase pipeline against `fixtures/runtime_failure.py` and prints `LOGBORG RECOVERY: SUCCESS` or `FAILURE`.

### Run the Log-Based Orchestrator

```bash
python -m logborg.orchestrator
```

Streams `fixtures/sample.log`, detects the buffer overflow signature, and applies the sandbox mitigation.

### Run the Tests

```bash
pytest tests/ -v
```

28 passing tests covering runtime recovery, safety policy enforcement, incident memory, reconciliation, drift detection, and adaptive multi-step recovery.

---

## Testing

The test suite contains **28 passing tests** across three test files:

### `test_runtime_recovery.py` (17 tests)

- End-to-end BUFFER_OVERFLOW recovery
- Unsupported fault safe failure (UNDIAGNOSED)
- MEMORY_PRESSURE recovery
- Health check requirement enforcement
- Unsafe policy blocking before repair
- Verification assessment reporting
- Adaptive multi-step recovery (BUFFER_OVERFLOW → MEMORY_PRESSURE)
- Reconciliation drift detection and convergence
- Supervisor bounded recovery cycles
- Supervision drift detection

### `test_safety_policy.py` (6 tests)

- Safe policy allowed
- Unbounded policy blocked (max_attempts=0)
- No-rollback policy blocked
- No-verification policy blocked
- Historical playbook preference
- Fallback when no verified history exists

### `test_incident_memory.py` (5 tests)

- Archived manifest reading
- Invalid manifest handling
- Fault-filtered memory queries
- Verification rate calculation
- Historical recovery assessment

---

## Why This Matters

LogBorg AI demonstrates that the core loop of autonomous SRE — **detect → diagnose → safety gate → repair → verify → reconcile** — can be implemented as a closed control plane with real guarantees:

1. **No silent failures**: Every repair is independently verified by re-executing the workload
2. **No unsafe guesses**: Unknown faults fail safely with clear status codes; the safety gate blocks unbounded or unverifiable policies
3. **Observable state**: Every phase transition is published in real time via SSE
4. **Bounded actions**: Repairs are reversible configuration files in a sandbox, not infrastructure mutations
5. **Historical intelligence**: Incident memory selects playbooks based on verified historical evidence
6. **Reproducible**: The entire pipeline runs locally with zero external dependencies
7. **Auditable**: Every run produces a versioned evidence manifest archived to the incidents directory

This is not a monitoring dashboard. It is not a log viewer. It is an autonomous reliability system that closes the loop between detecting a problem and proving it is fixed.

---

## Technical Differentiation

| Aspect | LogBorg AI | Traditional Monitoring |
|---|---|---|
| Response | Autonomous repair + verification | Alert only |
| Safety | Pre-repair safety gate with constraint checks | No pre-action validation |
| Verification | Re-executes workload, reconciles desired state | Checks if alert cleared |
| Adaptation | Multi-step adaptive recovery across fault types | Single-action remediation |
| Unknown faults | Safe failure, clear status | May retry blindly |
| History | Incident memory with verified playbook selection | No historical learning |
| Repair scope | Bounded, reversible sandbox configs | Varies (often unconstrained) |
| Evidence | Versioned JSON manifests with reconciliation | Logs scattered across tools |
| Observability | Real-time SSE phase transitions | Dashboard polling |
| Reproducibility | Local sandbox, no external deps | Requires production access |

---

## Honest Limitations

This is a **prototype** — not a production system. What it demonstrates:

- **Demonstrated**: Autonomous fault detection, diagnosis, safety-gated repair, independent verification, adaptive multi-step recovery, evidence generation, real-time observability
- **Demonstrated**: Incident memory with historical verified playbook evidence
- **Demonstrated**: Desired-state reconciliation with drift detection
- **Demonstrated**: Safe failure for unknown or unsupported faults
- **Demonstrated**: 28 passing tests covering the full recovery lifecycle

What it does **not** do:

- **Not distributed**: Single-node, single-workload execution
- **Not persistent**: No database — incident memory is rebuilt from archived manifests on each query
- **Not multi-tenant**: No authentication, no access control
- **Not production-grade**: The safety gate is deterministic, not probabilistic; repair configurations are simple env-var injections

---

## Final Statement

LogBorg AI is a Level-5-inspired autonomous SRE control-plane prototype that demonstrates a complete, closed-loop recovery system. From live failure detection through verified recovery, every step is observable, bounded, and independently checked. The system fails safely when it cannot repair a fault, learns from historical incidents, and produces structured evidence for every action it takes.

This is what it looks like when a system **proves** it recovered — not just hopes it did.

```
LIVE FAILURE ──▶ DETECTION ──▶ DECISION ──▶ SAFE ACTION ──▶ VERIFICATION ──▶ CONVERGENCE
     │                                                                  │
     └──────────────────── Evidence Trail ───────────────────────────────┘
```
