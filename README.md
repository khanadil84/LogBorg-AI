# LogBorg AI

## The Autonomous Log Triage & Self-Healing SRE Sandbox

LogBorg AI captures runtime stdout/stderr telemetry, detects known fault signatures, diagnoses supported failures, applies bounded runtime repairs, and independently verifies recovery.

## Architecture

```text
LIVE RUNTIME
     ↓
INGESTION → DETECTION → DIAGNOSIS → REPAIR → VERIFICATION
                                      ↓
                                  RECOVERY
```

## Discovered Python Modules

- `logborg/dashboard/server.py`
- `logborg/detection/live.py`
- `logborg/detection/signatures.py`
- `logborg/diagnosis/analyzer.py`
- `logborg/diagnosis/runtime.py`
- `logborg/execution_state.py`
- `logborg/ingestion/runtime.py`
- `logborg/ingestion/stream.py`
- `logborg/manifest/writer.py`
- `logborg/orchestrator.py`
- `logborg/readme_generator.py`
- `logborg/repair/playbook.py`
- `logborg/repair/runtime.py`
- `logborg/runtime_orchestrator.py`
- `logborg/supervisor.py`
- `logborg/verification/check.py`
- `logborg/verification/runtime.py`

## Evidence

- Runtime recovery evidence is written to `runtime-evidence.json`.
- Remediation metadata is written to `logborg-manifest.json`.
- Recovery is bounded and failed recovery triggers rollback.

## Tests

Run:

```bash
pytest -q
```
