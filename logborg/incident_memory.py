import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_incident_memory(project_root: Path) -> dict[str, Any]:
    """Build incident memory from archived manifests."""
    incident_root = Path(project_root) / "incidents"

    incidents = []

    for manifest_path in sorted(incident_root.glob("*/manifest.json")):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        diagnosis = data.get("diagnosis", {})
        repair = data.get("repair", {})
        verification = data.get("verification", {})

        incidents.append(
            {
                "run_id": data.get("incident", {}).get("run_id"),
                "fault": diagnosis.get("fault"),
                "severity": diagnosis.get("severity"),
                "root_cause": diagnosis.get("root_cause"),
                "repair_action": repair.get("action"),
                "verified": verification.get("passed"),
                "attempts": verification.get("attempts"),
            }
        )

    faults = Counter(
        incident["fault"]
        for incident in incidents
        if incident.get("fault")
    )

    verified = sum(
        1 for incident in incidents if incident.get("verified") is True
    )

    return {
        "incident_count": len(incidents),
        "verified_count": verified,
        "fault_counts": dict(faults),
        "incidents": incidents,
    }
