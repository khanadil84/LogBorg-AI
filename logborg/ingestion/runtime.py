import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeResult:
    return_code: int
    stdout: str
    stderr: str


def run_runtime(source: str, project_root: Path | None = None) -> RuntimeResult:
    """Execute the runtime fixture with optional LogBorg repair configuration."""
    env = os.environ.copy()

    if project_root is not None:
        repair_config = project_root / "sandbox" / "runtime_repair.conf"

        if repair_config.exists():
            for line in repair_config.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env[key] = value

    process = subprocess.run(
        ["python", source],
        capture_output=True,
        text=True,
        env=env,
    )

    return RuntimeResult(
        return_code=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )
