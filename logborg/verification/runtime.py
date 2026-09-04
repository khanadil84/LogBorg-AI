from logborg.ingestion.runtime import RuntimeResult


def verify_runtime_recovery(result: RuntimeResult) -> bool:
    """Independently verify that the repaired runtime recovered."""
    return (
        result.return_code == 0
        and "TRAFFIC STABLE" in result.stdout
        and result.stderr.strip() == ""
    )
