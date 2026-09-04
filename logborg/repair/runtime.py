from pathlib import Path


def apply_runtime_repair(source: str, project_root: Path) -> bool:
    """Create a repaired runtime configuration for the failed workload."""
    repair_config = project_root / "sandbox" / "runtime_repair.conf"
    repair_config.parent.mkdir(exist_ok=True)

    repair_config.write_text(
        "LOGBORG_BUFFER_LIMIT=8\n"
        "REPAIR=BUFFER_OVERFLOW\n",
        encoding="utf-8",
    )

    return True
