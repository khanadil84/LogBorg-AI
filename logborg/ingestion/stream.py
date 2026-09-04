from collections.abc import Iterator


def stream_lines(source: str) -> Iterator[str]:
    """Read a log source line by line."""
    with open(source, "r", encoding="utf-8") as log_file:
        for line in log_file:
            yield line.rstrip("\n")
