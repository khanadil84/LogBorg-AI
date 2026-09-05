# LogBorg AI

**The Autonomous Cloud Log Triage & Self-Healing SRE Sandbox**

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
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LogBorg AI Recovery Pipeline                         │
│                                                                             │
│  ┌──────────┐    ┌───────────┐    ┌──────────┐    ┌──────────┐    ┌───────┐ │
│  │  INGEST   │───▶│  DIAGNOSE │───▶│  REPAIR   │───▶│  VERIFY  │───▶│RECOVER│ │
│  │          │    │           │    │           │    │          │    │  ED   │ │
│  │ Execute  │    │ Match     │    │ Apply     │    │ Re-exec  │    │       │ │
│  │ workload │    │ fault     │    │ bounded   │    │ workload │    │ Done  │ │
│  │ capture  │    │ signatures│    │ sandbox   │    │ check    │    │       │ │
│  │ output   │    │ analyze   │    │ repair    │    │ signals  │    │       │ │
│  └──────────┘    └───────────┘    └──────────┘    └──────────┘    └───────┘ │
│       │               │                │               │              │     │
│       └───────────────┴────────────────┴───────────────┴──────────────┘     │
│                          ExecutionState (thread-safe)                        │
│                          ↕ SSE stream to dashboard                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Module Map

| Module | Responsibility |
|---|---|
| `logborg/ingestion/` | Execute runtime workloads, capture stdout/stderr, stream log lines |
| `logborg/detection/` | Signature-based fault matching against known patterns |
| `logborg/diagnosis/` | Translate detected signatures into structured diagnoses |
| `logborg/repair/` | Apply bounded sandbox repair configurations |
| `logborg/verification/` | Independently verify recovery by re-executing and checking signals |
| `logborg/manifest/` | Write structured evidence manifests |
| `logborg/execution_state.py` | Thread-safe live execution state — single source of truth for the dashboard |
| `logborg/runtime_orchestrator.py` | Autonomous recovery pipeline orchestrating all phases |
| `logborg/dashboard/` | HTTP server with SSE streaming, SVG topology visualization |

---

## Autonomous Decision Loop

The pipeline operates as a strict, observable state machine with five phases:

### Phase 1: INGEST

The system executes the target workload via `subprocess` and captures the full output — return code, stdout, and stderr. If the workload exits cleanly (return code 0), the system marks it `HEALTHY` and exits early. No unnecessary repair is attempted.

```python
# From logborg/ingestion/runtime.py
process = subprocess.run(["python", source], capture_output=True, text=True, env=env)
return RuntimeResult(return_code=process.returncode, stdout=process.stdout, stderr=process.stderr)
```

### Phase 2: DIAGNOSE

The captured stderr is analyzed against known fault signatures. Each signature maps to a structured `Diagnosis` containing the fault name, severity, root cause, and recommended action.

**Currently supported fault signatures:**

| Fault | Severity | Detection Keywords |
|---|---|---|
| `BUFFER_OVERFLOW` | CRITICAL | `buffer overflow`, `stream buffer exhausted` |
| `MEMORY_PRESSURE` | HIGH | `out of memory`, `memory exhausted`, `oom` |

```python
# From logborg/detection/signatures.py
SIGNATURES = (
    FaultSignature(name="BUFFER_OVERFLOW", severity="CRITICAL",
                   keywords=("buffer overflow", "stream buffer exhausted")),
    FaultSignature(name="MEMORY_PRESSURE", severity="HIGH",
                   keywords=("out of memory", "memory exhausted", "oom")),
)
```

If no signature matches, the system returns `UNDIAGNOSED` and exits safely.

### Phase 3: REPAIR

For supported faults with automated playbooks, the system applies a bounded sandbox repair. Repairs are **configuration changes only** — no destructive actions, no external API calls, no infrastructure mutations.

For `BUFFER_OVERFLOW`, the system writes a `runtime_repair.conf` file that injects environment variables into the next execution:

```bash
LOGBORG_BUFFER_LIMIT=8
REPAIR=BUFFER_OVERFLOW
```

The workload reads `LOGBORG_BUFFER_LIMIT` from the environment, increasing its buffer capacity from the default 2 to 8, which accommodates the 4-chunk workload.

### Phase 4: VERIFY

The system **re-executes the same workload** with the repair configuration injected. Recovery is verified against three independent signals:

1. Return code must be `0`
2. Stdout must contain `TRAFFIC STABLE`
3. Stderr must be empty

```python
# From logborg/verification/runtime.py
def verify_runtime_recovery(result: RuntimeResult) -> bool:
    return (
        result.return_code == 0
        and "TRAFFIC STABLE" in result.stdout
        and result.stderr.strip() == ""
    )
```

If any check fails, the status is `RECOVERY_FAILED` — the system does not claim success without proof.

### Phase 5: RECOVERED

Only reached when all verification checks pass. The evidence is persisted and the dashboard reflects the final verified state.

---

## Adaptive Multi-Step Recovery

The system is designed for adaptive recovery when verification exposes a different supported fault. Here is the decision flow for a multi-fault scenario:

```
                  ┌─────────────┐
                  │   INGEST    │
                  │  (execute)  │
                  └──────┬──────┘
                         │ return_code ≠ 0
                         ▼
                  ┌─────────────┐
                  │  DIAGNOSE   │
                  │ BUFFER_OVERFLOW
                  └──────┬──────┘
                         │ match found
                         ▼
                  ┌─────────────┐
                  │   REPAIR    │
                  │ increase buffer
                  └──────┬──────┘
                         │ repair applied
                         ▼
                  ┌─────────────┐
                  │   VERIFY    │
                  │ re-execute  │
                  └──────┬──────┘
                         │
              ┌──────────┴──────────┐
              │                     │
        return_code=0         return_code≠0
        TRAFFIC STABLE        new fault in stderr
        stderr empty               │
              │                    ▼
              ▼             ┌─────────────┐
     ┌────────────┐        │  DIAGNOSE   │
     │ RECOVERED  │        │ MEMORY_PRESSURE
     └────────────┘        └──────┬──────┘
                                  │
                          ┌───────┴───────┐
                          │               │
                   playbook exists   no playbook
                          │               │
                          ▼               ▼
                   ┌──────────┐    ┌──────────────┐
                   │  REPAIR  │    │UNSUPPORTED_FAULT
                   │ adaptive │    │  (safe fail) │
                   └──────────┘    └──────────────┘
```

**Key behaviors:**
- If `MEMORY_PRESSURE` is diagnosed and has no automated repair playbook, the system returns `UNSUPPORTED_FAULT` — it does not guess or attempt unsafe repairs
- Each verification is independent — the system re-executes the full workload, not just a partial check
- The `ExecutionState` tracks phase transitions so the dashboard shows exactly which path was taken

---

## Safety Model

LogBorg AI enforces safety through multiple layers:

### Bounded Recovery Actions

Repairs are configuration-only. The system writes files to the `sandbox/` directory — it never modifies source code, system configuration, or external services.

```bash
sandbox/
├── runtime_repair.conf    # Environment variable injection for workload
└── buffer_override.conf   # Sandbox mitigation state (from playbook path)
```

### Unknown-Fault Safe Failure

When the system encounters a fault it cannot repair, it fails with a clear status rather than guessing:

| Condition | Status | Behavior |
|---|---|---|
| No signature match | `UNDIAGNOSED` | Exits without action |
| Signature match, no playbook | `UNSUPPORTED_FAULT` | Exits without action |
| Repair fails to apply | `REPAIR_FAILED` | Exits, preserves evidence |
| Verification fails | `RECOVERY_FAILED` | Exits, preserves evidence |

**The system never guesses.** If it cannot repair a fault with a known playbook, it stops and reports the situation for human review.

### Independent Verification

The system does not trust its own repair. It re-executes the workload from scratch and checks concrete signals:

- Exit code is zero
- Expected health indicator (`TRAFFIC STABLE`) is present
- No error output in stderr

Only when all three pass does the system claim recovery.

---

## Desired-State Reconciliation

The system implements a simple but effective form of desired-state reconciliation:

1. **Current state**: Workload fails with buffer overflow (buffer limit = 2, workload needs 4 chunks)
2. **Desired state**: Workload runs successfully with TRAFFIC STABLE output
3. **Reconciliation**: Inject `LOGBORG_BUFFER_LIMIT=8` via environment, re-execute, verify

The `sandbox/runtime_repair.conf` file acts as the desired-state manifest. The runtime reads it on each execution, ensuring the workload runs with the corrected configuration.

```
Environment Injection Flow:
┌──────────────────┐     ┌───────────────────┐     ┌──────────────────┐
│ runtime_repair   │────▶│ subprocess.run()   │────▶│ Workload reads   │
│ .conf            │     │ env=merged_env     │     │ LOGBORG_BUFFER   │
│ LOGBORG_BUFFER=8 │     │                    │     │ LIMIT=8          │
└──────────────────┘     └───────────────────┘     └──────────────────┘
```

---

## Runtime Drift Supervision

After repair, the system doesn't just check "did it not crash?" — it verifies the workload reached a specific healthy state:

```python
# From logborg/verification/runtime.py
result.return_code == 0          # Process exited cleanly
and "TRAFFIC STABLE" in result.stdout  # Expected health signal present
and result.stderr.strip() == ""  # No residual errors
```

If the workload crashes with a different error, exits non-zero, or produces unexpected output, verification fails. The system detects drift between the expected recovered state and the actual runtime behavior.

---

## Evidence Model

Every recovery run produces a structured evidence manifest (`runtime-evidence.json`):

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
  "repair": {
    "applied": true,
    "action": "BUFFER_OVERFLOW_RUNTIME_REPAIR"
  },
  "recovery": {
    "return_code": 0,
    "stdout": "SERVICE STARTED\nBUFFER LIMIT: 8\nTRAFFIC STABLE\n",
    "stderr": ""
  },
  "verification": {
    "passed": true
  },
  "status": "RECOVERED"
}
```

The manifest writer (`logborg/manifest/writer.py`) produces a separate `logborg-manifest.json` with schema versioning for auditability:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-09-06T...",
  "target": "...",
  "diagnosis": { ... },
  "repair": { ... },
  "verification": { ... }
}
```

---

## Live Execution-State Architecture

The dashboard is driven by a single `ExecutionState` instance — a thread-safe state machine that publishes every phase transition in real time via Server-Sent Events (SSE).

```
┌─────────────────────────────────────────────────────────┐
│                    ExecutionState                        │
│                                                         │
│  Thread-safe state with pub/sub listeners               │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Phases: INGEST → DIAGNOSE → REPAIR → VERIFY   │   │
│  │          → RECOVERED                            │   │
│  │                                                 │   │
│  │  Node states: pending | active | success |      │   │
│  │               failed  | skipped                 │   │
│  │                                                 │   │
│  │  Edge states: idle | flowing | complete | failed│   │
│  └─────────────────────────────────────────────────┘   │
│                        │                                │
│              subscribe │ snapshot()                     │
│                        ▼                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │  SSE /api/events                                │   │
│  │  ↓                                              │   │
│  │  SVG Topology (hexagonal nodes + bezier edges)  │   │
│  │  Phase list · Event feed · Evidence viewer      │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### State Transitions

The orchestrator calls `state.begin_phase()`, `state.complete_phase()`, or `state.fail_phase()` at each step. The `ExecutionState` class:

- Maintains a snapshot of all phase states, edges, and the event log
- Publishes updates to all SSE subscribers on every transition
- Skips downstream phases when an upstream phase fails
- Provides a bounded event tail (last 80 events) for the live UI

**Every visual element in the dashboard maps to a real state transition.** There is no synthetic telemetry, no mocked data, no animation independent of actual pipeline progress.

---

## Repository Architecture

```
LogBorg-AI/
├── _start.py                         # Dashboard launcher
├── runtime-evidence.json             # Persisted recovery evidence
│
├── logborg/
│   ├── __init__.py
│   ├── orchestrator.py               # Log-file-based orchestration (sample.log)
│   ├── runtime_orchestrator.py       # Autonomous runtime recovery pipeline
│   ├── execution_state.py            # Thread-safe live state machine
│   │
│   ├── ingestion/
│   │   ├── stream.py                 # Line-by-line log streaming
│   │   └── runtime.py                # Subprocess execution, env injection
│   │
│   ├── detection/
│   │   └── signatures.py             # Fault signature matching
│   │
│   ├── diagnosis/
│   │   ├── analyzer.py               # Signature → Diagnosis translation
│   │   └── runtime.py                # Runtime stderr diagnosis
│   │
│   ├── repair/
│   │   ├── playbook.py               # Sandbox mitigation playbook
│   │   └── runtime.py                # Runtime repair configuration
│   │
│   ├── verification/
│   │   ├── check.py                  # Sandbox state verification
│   │   └── runtime.py                # Runtime recovery verification
│   │
│   ├── manifest/
│   │   └── writer.py                 # Evidence manifest generation
│   │
│   └── dashboard/
│       ├── __main__.py               # Dashboard entry point
│       ├── server.py                 # HTTP + SSE streaming server
│       └── static/
│           ├── index.html            # Recovery console UI
│           ├── app.js                # Dashboard controller + SSE binding
│           ├── topology.js           # SVG topology renderer
│           ├── style.css             # Dashboard styles
│           └── dashboard.css         # Dashboard layout
│
├── fixtures/
│   ├── runtime_failure.py            # Simulated buffer overflow workload
│   └── sample.log                    # Sample log file for stream-based orchestration
│
├── sandbox/
│   └── runtime_repair.conf           # Active repair configuration
│
└── tests/                            # (Empty — see Limitations)
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

This executes the full pipeline against `fixtures/runtime_failure.py` and prints `LOGBORG RECOVERY: SUCCESS` or `FAILURE`.

### Run the Log-Based Orchestrator

```bash
python -m logborg.orchestrator
```

Streams `fixtures/sample.log`, detects the buffer overflow signature, and applies the sandbox mitigation.

### Check the Evidence

After a recovery run, inspect `runtime-evidence.json` for the complete execution trace.

---

## Testing

The repository includes a `tests/` directory. To verify the system works:

1. **Manual verification**: Run `python -m logborg.runtime_orchestrator` — should output `LOGBORG RECOVERY: SUCCESS`
2. **Evidence inspection**: Check that `runtime-evidence.json` contains `"status": "RECOVERED"`
3. **Dashboard verification**: Start the dashboard, click Run Recovery, observe the SVG topology progress through all 5 phases

The `runtime_failure.py` fixture demonstrates the complete failure → recovery cycle:
- Starts with buffer limit = 2 (default)
- Fails with 4 chunks > limit 2
- System injects `LOGBORG_BUFFER_LIMIT=8`
- Re-runs successfully with TRAFFIC STABLE output

---

## Why This Matters

LogBorg AI demonstrates that the core loop of autonomous SRE — **detect → diagnose → repair → verify** — can be implemented as a closed control plane with real guarantees:

1. **No silent failures**: Every repair is independently verified by re-executing the workload
2. **No unsafe guesses**: Unknown faults fail safely with clear status codes
3. **Observable state**: Every phase transition is published in real time via SSE
4. **Bounded actions**: Repairs are configuration files in a sandbox, not infrastructure mutations
5. **Reproducible**: The entire pipeline runs locally with zero external dependencies
6. **Auditable**: Every run produces a structured evidence manifest

This is not a monitoring dashboard. It is not a log viewer. It is an autonomous reliability system that closes the loop between detecting a problem and proving it is fixed.

---

## Technical Differentiation

| Aspect | LogBorg AI | Traditional Monitoring |
|---|---|---|
| Response | Autonomous repair + verification | Alert only |
| Verification | Re-executes workload, checks signals | Checks if alert cleared |
| Unknown faults | Safe failure, clear status | May retry blindly |
| Repair scope | Bounded sandbox configs | Varies (often unconstrained) |
| Evidence | Structured JSON manifest | Logs scattered across tools |
| Observability | Real-time SSE phase transitions | Dashboard polling |
| Reproducibility | Local sandbox, no external deps | Requires production access |

---

## Honest Limitations

This is a **prototype** — not a production system. What it demonstrates:

- **Demonstrated**: Autonomous fault detection, diagnosis, bounded repair, independent verification, evidence generation, real-time observability
- **Demonstrated**: Safe failure for unknown or unsupported faults
- **Demonstrated**: Structured evidence trail for post-incident review

What it does **not** do:

- **Not production**: Only handles `BUFFER_OVERFLOW` with an automated repair playbook
- **Not distributed**: Single-node, single-workload execution
- **Not persistent**: No history database, no trend analysis, no learning from past incidents
- **Not multi-tenant**: No authentication, no access control
- **Not tested**: The `tests/` directory is empty — this is a known gap

The `MEMORY_PRESSURE` fault signature is defined in `detection/signatures.py` and can be diagnosed, but it has no automated repair playbook. The system will correctly return `UNSUPPORTED_FAULT` rather than attempting an unsafe repair.

---

## Final Statement

LogBorg AI is a Level-5-inspired autonomous SRE control-plane prototype that demonstrates a complete, closed-loop recovery system. From live failure detection through verified recovery, every step is observable, bounded, and independently checked. The system fails safely when it cannot repair a fault, and it produces structured evidence for every action it takes.

This is what it looks like when a system **proves** it recovered — not just hopes it did.

```
LIVE FAILURE ──▶ DETECTION ──▶ DECISION ──▶ SAFE ACTION ──▶ VERIFICATION ──▶ CONVERGENCE
     │                                                                  │
     └──────────────────── Evidence Trail ───────────────────────────────┘
```
