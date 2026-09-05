import json
from pathlib import Path

from logborg.incident_memory import load_incident_memory


def test_incident_memory_reads_archived_manifests(tmp_path: Path):
    manifest_dir = tmp_path / "incidents" / "run-test-1"
    manifest_dir.mkdir(parents=True)

    manifest = {
        "incident": {
            "run_id": "run-test-1",
            "lifecycle": "RECOVERED",
        },
        "diagnosis": {
            "fault": "BUFFER_OVERFLOW",
            "severity": "CRITICAL",
            "root_cause": "Runtime stream buffer capacity was exceeded.",
        },
        "repair": {
            "action": "BUFFER_OVERFLOW_RUNTIME_REPAIR",
        },
        "verification": {
            "passed": True,
            "attempts": 1,
        },
    }

    (manifest_dir / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    memory = load_incident_memory(tmp_path)

    assert memory["incident_count"] == 1
    assert memory["verified_count"] == 1
    assert memory["fault_counts"] == {"BUFFER_OVERFLOW": 1}

    incident = memory["incidents"][0]
    assert incident["run_id"] == "run-test-1"
    assert incident["repair_action"] == "BUFFER_OVERFLOW_RUNTIME_REPAIR"
    assert incident["verified"] is True


def test_incident_memory_ignores_invalid_manifests(tmp_path: Path):
    manifest_dir = tmp_path / "incidents" / "broken"
    manifest_dir.mkdir(parents=True)

    (manifest_dir / "manifest.json").write_text(
        "{invalid json",
        encoding="utf-8",
    )

    memory = load_incident_memory(tmp_path)

    assert memory["incident_count"] == 0
    assert memory["verified_count"] == 0
    assert memory["fault_counts"] == {}
