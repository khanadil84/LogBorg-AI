import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_manifest(
    project_root: Path,
    *,
    target: str,
    run_id: str,
    diagnosis: dict[str, Any],
    memory: dict[str, Any],
    policy: dict[str, Any],
    safety: dict[str, Any],
    repair: dict[str, Any],
    verification: dict[str, Any],
) -> Path:
    """Write complete LogBorg remediation evidence."""
    generated_at = datetime.now(timezone.utc).isoformat()

    manifest = {
        "schema_version": "1.1",
        "generated_at": generated_at,
        "metadata": {
            "platform": "Modiqo",
            "author": "@Modiqo",
            "tag": "#rote",
            "system": "LogBorg AI",
        },
        "autonomy": {
            "telemetry": "live_stdout_stderr",
            "fault_detection": "automatic",
            "diagnosis": "automatic",
            "repair": "automatic",
            "verification": "independent_rerun",
        },
        "incident": {
            "run_id": run_id,
            "lifecycle": "RECOVERED",
        },
        "target": target,
        "remediation_timeline": [
            "LIVE_TELEMETRY_CAPTURED",
            "FAULT_DETECTED",
            "ROOT_CAUSE_DIAGNOSED",
            "REPAIR_APPLIED",
            "WORKLOAD_RERUN",
            "RECOVERY_VERIFIED",
        ],
        "diagnosis": diagnosis,
        "memory": memory,
        "policy": policy,
        "safety": safety,
        "repair": repair,
        "verification": verification,
    }

    payload = json.dumps(manifest, indent=2)

    output = project_root / "logborg-manifest.json"
    output.write_text(payload, encoding="utf-8")

    incident_dir = project_root / "incidents" / run_id
    incident_dir.mkdir(parents=True, exist_ok=True)
    archive = incident_dir / "manifest.json"
    archive.write_text(payload, encoding="utf-8")

    return output
