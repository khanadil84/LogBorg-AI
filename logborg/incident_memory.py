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


def query_incident_memory(
    project_root: Path,
    fault: str,
) -> dict[str, Any]:
    """Return historical memory relevant to a specific fault."""
    memory = load_incident_memory(project_root)

    matches = [
        incident
        for incident in memory["incidents"]
        if incident.get("fault") == fault
    ]

    return {
        "fault": fault,
        "incident_count": len(matches),
        "verified_count": sum(
            1 for incident in matches if incident.get("verified") is True
        ),
        "incidents": matches,
    }


def incident_memory_evidence(
    project_root: Path,
    fault: str,
) -> dict[str, Any]:
    """Summarize historical recovery evidence for a fault."""
    memory = query_incident_memory(project_root, fault)

    return {
        "fault": memory["fault"],
        "historical_incidents": memory["incident_count"],
        "historical_verified": memory["verified_count"],
        "verification_rate": (
            memory["verified_count"] / memory["incident_count"]
            if memory["incident_count"]
            else 0.0
        ),
    }


def assess_historical_recovery(
    project_root: Path,
    fault: str,
) -> dict[str, Any]:
    """Assess whether historical evidence supports prior recovery success."""
    evidence = incident_memory_evidence(project_root, fault)

    return {
        "known": evidence["historical_incidents"] > 0,
        "verified_before": evidence["historical_verified"] > 0,
        "verification_rate": evidence["verification_rate"],
    }
