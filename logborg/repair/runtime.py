from pathlib import Path


def apply_runtime_repair(
    source: str,
    project_root: Path,
    fault: str = "BUFFER_OVERFLOW",
) -> bool:
    """Apply a reversible runtime repair configuration."""
    repair_config = project_root / "sandbox" / "runtime_repair.conf"
    backup_config = project_root / "sandbox" / "runtime_repair.conf.bak"

    repair_config.parent.mkdir(parents=True, exist_ok=True)

    if repair_config.exists() and not backup_config.exists():
        backup_config.write_text(
            repair_config.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    if fault == "BUFFER_OVERFLOW":
        content = (
            "LOGBORG_BUFFER_LIMIT=8\n"
            "REPAIR=BUFFER_OVERFLOW\n"
        )
    elif fault == "MEMORY_PRESSURE":
        content = (
            "LOGBORG_MEMORY_MODE=sandbox\n"
            "REPAIR=MEMORY_PRESSURE\n"
        )
    else:
        return False

    repair_config.write_text(content, encoding="utf-8")
    return True


def rollback_runtime_repair(project_root: Path) -> bool:
    """Restore the previous runtime configuration after failed recovery."""
    repair_config = project_root / "sandbox" / "runtime_repair.conf"
    backup_config = project_root / "sandbox" / "runtime_repair.conf.bak"

    if backup_config.exists():
        repair_config.write_text(
            backup_config.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        backup_config.unlink()
        return True

    if repair_config.exists():
        repair_config.unlink()
        return True

    return False
