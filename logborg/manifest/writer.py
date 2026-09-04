import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_manifest(
    project_root: Path,
    *,
    target: str,
    diagnosis: dict[str, Any],
    repair: dict[str, Any],
    verification: dict[str, Any],
) -> Path:
    """Write the complete LogBorg remediation evidence manifest."""
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "diagnosis": diagnosis,
        "repair": repair,
        "verification": verification,
    }

    output = project_root / "logborg-manifest.json"
    output.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    return output
