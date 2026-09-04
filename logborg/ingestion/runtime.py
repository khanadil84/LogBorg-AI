import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable


@dataclass(frozen=True)
class RuntimeResult:
    return_code: int
    stdout: str
    stderr: str


def _environment(project_root: Path | None) -> dict[str, str]:
    env = os.environ.copy()

    if project_root is not None:
        repair_config = project_root / "sandbox" / "runtime_repair.conf"

        if repair_config.exists():
            for line in repair_config.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    env[key] = value

    return env


def run_runtime(
    source: str,
    project_root: Path | None = None,
) -> RuntimeResult:
    """Execute the runtime fixture and capture stdout/stderr."""
    process = subprocess.run(
        ["python", source],
        capture_output=True,
        text=True,
        env=_environment(project_root),
    )

    return RuntimeResult(
        return_code=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )


def stream_runtime(
    source: str,
    project_root: Path | None = None,
    on_stdout: Callable[[str], None] | None = None,
    on_stderr: Callable[[str], None] | None = None,
) -> RuntimeResult:
    """Run a workload while consuming stdout and stderr concurrently."""
    process = subprocess.Popen(
        ["python", "-u", source],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=_environment(project_root),
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def consume(
        pipe,
        target: list[str],
        callback: Callable[[str], None] | None,
    ) -> None:
        for raw_line in iter(pipe.readline, ""):
            line = raw_line.rstrip("\n")
            target.append(line)
            if callback:
                callback(line)
        pipe.close()

    assert process.stdout is not None
    assert process.stderr is not None

    stdout_thread = threading.Thread(
        target=consume,
        args=(process.stdout, stdout_lines, on_stdout),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=consume,
        args=(process.stderr, stderr_lines, on_stderr),
        daemon=True,
    )

    stdout_thread.start()
    stderr_thread.start()

    return_code = process.wait()

    stdout_thread.join()
    stderr_thread.join()

    return RuntimeResult(
        return_code=return_code,
        stdout="\n".join(stdout_lines),
        stderr="\n".join(stderr_lines),
    )
