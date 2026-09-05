from pathlib import Path


def _read_runtime_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}

    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if key and key != "REPAIR":
            values[key] = value

    return values


def apply_runtime_repair(
    source: str,
    project_root: Path,
    fault: str = "BUFFER_OVERFLOW",
) -> bool:
    """Apply a reversible and composable runtime repair configuration."""
    repair_config = project_root / "sandbox" / "runtime_repair.conf"
    backup_config = project_root / "sandbox" / "runtime_repair.conf.bak"

    repair_config.parent.mkdir(parents=True, exist_ok=True)

    if repair_config.exists() and not backup_config.exists():
        backup_config.write_text(
            repair_config.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    values = _read_runtime_config(repair_config)

    if fault == "BUFFER_OVERFLOW":
        values["LOGBORG_BUFFER_LIMIT"] = "8"
    elif fault == "MEMORY_PRESSURE":
        values["LOGBORG_MEMORY_MODE"] = "sandbox"
    else:
        return False

    values["REPAIR"] = fault

    content = "\n".join(
        f"{key}={value}"
        for key, value in values.items()
    ) + "\n"

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
