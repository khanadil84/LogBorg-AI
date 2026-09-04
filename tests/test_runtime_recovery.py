from pathlib import Path

from logborg.runtime_orchestrator import recover


def test_runtime_recovery(tmp_path: Path):
    source = Path("fixtures/runtime_failure.py").resolve()

    assert recover(
        str(source),
        tmp_path,
        reset_sandbox=True,
    ) is True

    evidence = tmp_path / "runtime-evidence.json"
    manifest = tmp_path / "logborg-manifest.json"
    override = tmp_path / "sandbox" / "runtime_repair.conf"

    assert evidence.exists()
    assert manifest.exists()
    assert override.exists()

    assert "BUFFER_OVERFLOW" in evidence.read_text()
    assert '"passed": true' in evidence.read_text()


def test_unsupported_fault_fails_safely(tmp_path: Path):
    source = Path("fixtures/unsupported_failure.py").resolve()

    assert recover(
        str(source),
        tmp_path,
        reset_sandbox=True,
    ) is False

    evidence = tmp_path / "runtime-evidence.json"

    assert evidence.exists()
    assert '"status": "UNDIAGNOSED"' in evidence.read_text()
